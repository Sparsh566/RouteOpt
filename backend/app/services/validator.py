"""
Route Validator Service (backend/app/services/validator.py)
Independently verifies route feasibility and compliance with hard constraints:
- Stop uniqueness and completeness (served exactly once or listed in dropped_stops)
- Vehicle payload capacity
- Time windows, dwell durations, and waiting times
- Shift operating limits and return to depot
- Vehicle access eligibility (height clearance, GVW bridge ratings, HCV peak bans)
"""

import logging
from datetime import date
from typing import Any, Literal

from backend.app.models.fleet_v2 import (
    CommercialVehicleSpec,
    DeliveryStop,
    DepotLocation,
    VehicleClass,
)
from backend.app.services.regulation_engine import RegionalRegulationEngine

logger = logging.getLogger("routeopt.validator")

class RouteValidationError:
    def __init__(self, code: str, message: str, stop_id: str | None = None, vehicle_id: str | None = None):
        self.code = code
        self.message = message
        self.stop_id = stop_id
        self.vehicle_id = vehicle_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "stop_id": self.stop_id,
            "vehicle_id": self.vehicle_id
        }

class RouteValidator:
    def __init__(
        self,
        depot: DepotLocation,
        stops: list[DeliveryStop],
        fleet: list[CommercialVehicleSpec],
        distance_matrix: list[list[float]],
        duration_matrix: list[list[float]],
        departure_time_sec: int = 30600,
        region: str = "MUMBAI_MMRDA",
        enforce_guidelines: bool = True,
        as_of_date: date | str | None = None
    ):
        self.depot = depot
        self.stops = stops
        self.fleet = fleet
        self.distance_matrix = distance_matrix
        self.duration_matrix = duration_matrix
        self.departure_time_sec = departure_time_sec
        self.region = region
        self.enforce_guidelines = enforce_guidelines
        self.as_of_date = as_of_date
        self.reg_engine = RegionalRegulationEngine(region, as_of_date=as_of_date)

        # Auto-derive restricted urban core status from stop coordinates if not explicitly set
        for s in self.stops:
            if not s.is_in_restricted_urban_core:
                s.is_in_restricted_urban_core = self.reg_engine.is_coordinate_in_restricted_zone(s.lat, s.lon)

        self.stop_by_id = {s.stop_id: s for s in stops}
        self.stop_by_node = {i + 1: s for i, s in enumerate(stops)}
        self.vehicle_by_id = {v.vehicle_id: v for v in fleet}
        self.shift_end_sec = departure_time_sec + depot.operating_hours_sec

        # Normalized time windows (in seconds since midnight)
        self.normalized_windows: dict[str, tuple[int, int]] = {
            s.stop_id: s.get_normalized_window(departure_time_sec, depot.operating_hours_sec)
            for s in stops
        }

    def validate(
        self,
        routes: list[dict[str, Any]],
        dropped_stops: list[str]
    ) -> dict[str, Any]:
        """
        Validates solution routes and dropped stops against all operational and regulatory constraints.
        Returns:
            is_valid: bool
            status: "SUCCESS" | "PARTIAL" | "INFEASIBLE"
            errors: List[Dict[str, Any]]
            summary: Dict[str, Any]
        """
        errors: list[RouteValidationError] = []
        served_stop_counts: dict[str, int] = {s.stop_id: 0 for s in self.stops}

        for r in routes:
            v_id = str(r.get("vehicle_id") or "")
            vehicle = self.vehicle_by_id.get(v_id)
            if not vehicle:
                errors.append(RouteValidationError(
                    code="UNKNOWN_VEHICLE",
                    message=f"Route references vehicle '{v_id}' not found in fleet specification.",
                    vehicle_id=v_id
                ))
                continue

            schedule = r.get("schedule", [])
            if not schedule or len(schedule) <= 2:
                # Idle vehicle
                continue

            # 1. Depot start and end check
            if schedule[0].get("node_index") != 0:
                errors.append(RouteValidationError(
                    code="ROUTE_MUST_START_AT_DEPOT",
                    message="First node of route must be depot (node 0).",
                    vehicle_id=v_id
                ))
            if schedule[-1].get("node_index") != 0:
                errors.append(RouteValidationError(
                    code="ROUTE_MUST_END_AT_DEPOT",
                    message="Final node of route must be depot (node 0).",
                    vehicle_id=v_id
                ))

            speed_penalty = 1.30 if vehicle.vehicle_class == VehicleClass.FREIGHT_TRUCK else 1.0
            current_load = 0.0
            prev_node = 0
            prev_departure_time = float(self.departure_time_sec)

            for step_idx, step in enumerate(schedule):
                node_idx = step.get("node_index")
                arrival_time = float(step.get("arrival_time_sec", 0.0))

                if step_idx == 0:
                    prev_departure_time = arrival_time
                    continue

                if node_idx == 0:
                    # Returning to depot at end
                    min_leg_dur = self.duration_matrix[prev_node][0] * speed_penalty
                    if arrival_time < prev_departure_time + min_leg_dur - 1.0:
                        errors.append(RouteValidationError(
                            code="PHYSICALLY_IMPOSSIBLE_TRANSIT",
                            message=f"Arrival time {arrival_time}s is earlier than physical transit duration from node {prev_node}.",
                            vehicle_id=v_id
                        ))
                    if arrival_time > float(self.shift_end_sec):
                        errors.append(RouteValidationError(
                            code="SHIFT_LIMIT_EXCEEDED",
                            message=f"Depot return arrival time {arrival_time}s exceeds shift limit {self.shift_end_sec}s.",
                            vehicle_id=v_id
                        ))
                    continue

                # Visiting a stop
                stop = self.stop_by_node.get(node_idx)
                if not stop:
                    errors.append(RouteValidationError(
                        code="UNKNOWN_STOP_NODE",
                        message=f"Node index {node_idx} does not correspond to any valid stop.",
                        vehicle_id=v_id
                    ))
                    continue

                served_stop_counts[stop.stop_id] = served_stop_counts.get(stop.stop_id, 0) + 1

                # Transit time check
                min_leg_dur = self.duration_matrix[prev_node][node_idx] * speed_penalty
                if arrival_time < prev_departure_time + min_leg_dur - 1.0:
                    errors.append(RouteValidationError(
                        code="PHYSICALLY_IMPOSSIBLE_TRANSIT",
                        message=f"Arrival at stop '{stop.name}' ({arrival_time}s) violates minimum driving duration from node {prev_node}.",
                        stop_id=stop.stop_id,
                        vehicle_id=v_id
                    ))

                # Time window check
                w_start, w_end = self.normalized_windows[stop.stop_id]
                effective_arrival = max(arrival_time, float(w_start))
                if effective_arrival > float(w_end):
                    errors.append(RouteValidationError(
                        code="TIME_WINDOW_MISSED",
                        message=f"Arrival time {effective_arrival}s at stop '{stop.name}' exceeds deadline {w_end}s.",
                        stop_id=stop.stop_id,
                        vehicle_id=v_id
                    ))

                # Vehicle capacity check
                current_load += stop.demand_kg
                if current_load > vehicle.payload_capacity_kg:
                    errors.append(RouteValidationError(
                        code="VEHICLE_CAPACITY_EXCEEDED",
                        message=f"Vehicle '{vehicle.name}' load ({current_load}kg) exceeds max payload capacity ({vehicle.payload_capacity_kg}kg).",
                        stop_id=stop.stop_id,
                        vehicle_id=v_id
                    ))

                # Structural clearance checks (B8)
                if self.enforce_guidelines:
                    if stop.requires_flyover and vehicle.height_meters > self.reg_engine.flyover_height_limit_m:
                        errors.append(RouteValidationError(
                            code="FLYOVER_HEIGHT_CLEARANCE_EXCEEDED",
                            message=f"Vehicle height ({vehicle.height_meters}m) exceeds flyover clearance gantry ({self.reg_engine.flyover_height_limit_m}m) for stop '{stop.name}'.",
                            stop_id=stop.stop_id,
                            vehicle_id=v_id
                        ))
                    if stop.max_access_gvw_tonnes is not None and vehicle.gross_vehicle_weight_tonnes > stop.max_access_gvw_tonnes:
                        errors.append(RouteValidationError(
                            code="BRIDGE_GVW_EXCEEDED",
                            message=f"Vehicle weight ({vehicle.gross_vehicle_weight_tonnes}T) exceeds corridor bridge limit ({stop.max_access_gvw_tonnes}T) for stop '{stop.name}'.",
                            stop_id=stop.stop_id,
                            vehicle_id=v_id
                        ))

                # HCV Urban Peak Ban check (B1 - unified arrival ban rule)
                if (
                    self.enforce_guidelines
                    and vehicle.vehicle_class == VehicleClass.FREIGHT_TRUCK
                    and stop.is_in_restricted_urban_core
                ):
                    if self.reg_engine.is_peak_ban_active(effective_arrival):
                        errors.append(RouteValidationError(
                            code="TRUCK_PEAK_BAN_VIOLATION",
                            message=f"Freight truck '{vehicle.name}' served urban core stop '{stop.name}' during restricted peak ban hours (arrival: {effective_arrival}s).",
                            stop_id=stop.stop_id,
                            vehicle_id=v_id
                        ))

                prev_departure_time = effective_arrival + float(stop.service_duration_sec)
                prev_node = node_idx

        # 2. Global Stop Completeness and Uniqueness Checks
        dropped_set = set(dropped_stops)

        for s_id, count in served_stop_counts.items():
            if count > 1:
                errors.append(RouteValidationError(
                    code="DUPLICATE_STOP_SERVED",
                    message=f"Stop '{s_id}' was served {count} times across routes.",
                    stop_id=s_id
                ))
            elif count == 1 and s_id in dropped_set:
                errors.append(RouteValidationError(
                    code="STOP_BOTH_SERVED_AND_DROPPED",
                    message=f"Stop '{s_id}' was served in a route but also listed as dropped.",
                    stop_id=s_id
                ))
            elif count == 0 and s_id not in dropped_set:
                errors.append(RouteValidationError(
                    code="MISSING_STOP",
                    message=f"Stop '{s_id}' was neither served by any vehicle nor listed in dropped_stops.",
                    stop_id=s_id
                ))

        # Check for invalid stop IDs in dropped_stops
        for s_id in dropped_stops:
            if s_id not in self.stop_by_id:
                errors.append(RouteValidationError(
                    code="UNKNOWN_DROPPED_STOP",
                    message=f"Dropped stop list contains unknown stop ID '{s_id}'.",
                    stop_id=s_id
                ))

        # Overall Status
        if errors:
            status: Literal["SUCCESS", "PARTIAL", "INFEASIBLE"] = "INFEASIBLE"
            is_valid = False
        elif dropped_stops:
            status = "PARTIAL"
            is_valid = True
        else:
            status = "SUCCESS"
            is_valid = True

        return {
            "is_valid": is_valid,
            "status": status,
            "errors": [e.to_dict() for e in errors],
            "total_stops_requested": len(self.stops),
            "total_stops_served": sum(1 for c in served_stop_counts.values() if c == 1),
            "total_stops_dropped": len(dropped_stops)
        }
