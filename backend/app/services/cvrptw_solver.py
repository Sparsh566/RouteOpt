"""
Commercial Fleet CVRPTW Solver Service
Formulates Capacitated Vehicle Routing Problem with Time Windows & Road Guidelines using Google OR-Tools.
Provides deterministic, constraint-respecting greedy fallback when OR-Tools is unavailable.
"""

try:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    ORTOOLS_AVAILABLE = True
except (ImportError, Exception):
    pywrapcp = None
    routing_enums_pb2 = None
    ORTOOLS_AVAILABLE = False

import logging
import time
from typing import Any

from backend.app.models.fleet_v2 import (
    CommercialVehicleSpec,
    DeliveryStop,
    DepotLocation,
    VehicleClass,
)
from backend.app.services.regulation_engine import RegionalRegulationEngine

logger = logging.getLogger("routeopt.cvrptw")

if ORTOOLS_AVAILABLE and pywrapcp is not None:
    class FirstSolutionMonitor(pywrapcp.SearchMonitor):  # type: ignore[name-defined]
        """Monitors OR-Tools search to capture exact time-to-first-solution."""
        def __init__(self, solver: Any) -> None:
            super().__init__(solver)
            self.t0: float | None = None
            self.first_solution_time_ms: float | None = None

        def EnterSearch(self) -> None:
            self.t0 = time.perf_counter()

        def AtSolution(self) -> bool:
            if self.first_solution_time_ms is None and self.t0 is not None:
                self.first_solution_time_ms = (time.perf_counter() - self.t0) * 1000.0
            return True
else:
    FirstSolutionMonitor = None  # type: ignore[assignment,misc]

class CVRPTWSolver:
    def __init__(
        self,
        distance_matrix: list[list[float]],
        duration_matrix: list[list[float]],
        depot: DepotLocation,
        stops: list[DeliveryStop],
        fleet: list[CommercialVehicleSpec],
        enforce_guidelines: bool = True,
        departure_time_sec: int = 30600,  # Default: 08:30:00 (30600s since midnight)
        region: str = "MUMBAI_MMRDA"
    ):
        self.distance_matrix = distance_matrix
        self.duration_matrix = duration_matrix
        self.depot = depot
        self.stops = stops
        self.fleet = fleet
        self.enforce_guidelines = enforce_guidelines
        self.departure_time_sec = departure_time_sec
        self.region = region
        self.reg_engine = RegionalRegulationEngine(region)

        # Auto-derive restricted urban core status from stop coordinates if not explicitly set
        for s in self.stops:
            if not s.is_in_restricted_urban_core:
                s.is_in_restricted_urban_core = self.reg_engine.is_coordinate_in_restricted_zone(s.lat, s.lon)

        # Node 0 is Depot, Nodes 1..N are stops
        self.all_nodes = [depot] + stops
        self.num_nodes = len(self.all_nodes)
        self.num_vehicles = len(fleet)
        self.depot_index = 0

        # Shift horizon
        self.shift_end_sec = self.departure_time_sec + self.depot.operating_hours_sec

        # Normalized time windows for all stops in seconds since midnight
        self.normalized_windows: list[tuple[int, int]] = [
            s.get_normalized_window(self.departure_time_sec, self.depot.operating_hours_sec)
            for s in self.stops
        ]

    def solve(self) -> dict[str, Any] | None:
        if not ORTOOLS_AVAILABLE:
            logger.info("OR-Tools not available in environment. Running greedy CVRPTW solver fallback.")
            return self._solve_greedy_fallback()

        try:
            sol = self._solve_ortools()
            if sol is not None:
                return sol
            logger.warning("OR-Tools returned no solution. Falling back to greedy CVRPTW solver.")
            return self._solve_greedy_fallback()
        except Exception as e:
            logger.warning(f"OR-Tools solver execution failed: {e}. Falling back to greedy CVRPTW.")
            return self._solve_greedy_fallback()

    def check_stop_feasibility(
        self,
        vehicle: CommercialVehicleSpec,
        stop_idx: int,
        current_node: int,
        current_time_sec: float,
        current_load_kg: float,
        penalty: float
    ) -> tuple[bool, float, float]:
        """
        Shared feasibility evaluation used by greedy solver and validator.
        Returns (is_feasible, arrival_time_sec, depot_return_time_sec).
        """
        stop = self.stops[stop_idx - 1]
        w_start, w_end = self.normalized_windows[stop_idx - 1]

        # 1. Capacity check
        if current_load_kg + stop.demand_kg > vehicle.payload_capacity_kg:
            return False, 0.0, 0.0

        # 2. Structural access check (Height / GVW)
        if self.enforce_guidelines:
            if stop.requires_flyover and vehicle.height_meters > self.reg_engine.flyover_height_limit_m:
                return False, 0.0, 0.0
            if stop.max_access_gvw_tonnes is not None and vehicle.gross_vehicle_weight_tonnes > stop.max_access_gvw_tonnes:
                return False, 0.0, 0.0
            if stop.requires_flyover:
                can_pass, _ = self.reg_engine.check_vehicle_access(vehicle, is_flyover=True)
                if not can_pass:
                    return False, 0.0, 0.0

        # 3. Leg travel & arrival
        leg_dur = self.duration_matrix[current_node][stop_idx] * penalty
        arrival_time = current_time_sec + leg_dur
        service_start = max(arrival_time, float(w_start))

        # Check latest deadline
        if service_start > float(w_end):
            return False, 0.0, 0.0

        # 4. Heavy Commercial Vehicle Peak Ban check (Shared ban rule matching OR-Tools arrival constraint)
        if (
            self.enforce_guidelines
            and vehicle.vehicle_class == VehicleClass.FREIGHT_TRUCK
            and stop.is_in_restricted_urban_core
        ):
            if self.reg_engine.is_peak_ban_active(service_start):
                return False, 0.0, 0.0

        # 5. Feasibility of returning to depot within operating hours
        service_end = service_start + float(stop.service_duration_sec)
        return_dur = self.duration_matrix[stop_idx][0] * penalty
        depot_return_time = service_end + return_dur
        if depot_return_time > float(self.shift_end_sec):
            return False, 0.0, 0.0

        return True, service_start, depot_return_time

    def _solve_ortools(self) -> dict[str, Any] | None:
        manager = pywrapcp.RoutingIndexManager(
            self.num_nodes,
            self.num_vehicles,
            self.depot_index
        )
        routing = pywrapcp.RoutingModel(manager)
        solver = routing.solver()

        # 1. Register Vehicle-Specific Transit Duration Callbacks (B2 Fix)
        transit_callback_indices = []
        for v in self.fleet:
            # Freight trucks face 1.30x speed penalty in dense urban roads
            speed_penalty = 1.30 if v.vehicle_class == VehicleClass.FREIGHT_TRUCK else 1.0

            def create_duration_callback(penalty):
                def callback(from_index: int, to_index: int) -> int:
                    u = manager.IndexToNode(from_index)
                    v_node = manager.IndexToNode(to_index)
                    base_dur = self.duration_matrix[u][v_node]
                    dwell = self.stops[u - 1].service_duration_sec if u > 0 else 0
                    return int(round((base_dur * penalty) + dwell))
                return callback

            cb = routing.RegisterTransitCallback(create_duration_callback(speed_penalty))
            transit_callback_indices.append(cb)

        # 2. Add Dimension with Vehicle-Specific Transits (B2 Fix)
        # Horizon covers maximum possible timestamp (departure + operating hours + buffer)
        max_horizon_sec = self.shift_end_sec + 14400
        routing.AddDimensionWithVehicleTransits(
            transit_callback_indices,
            7200,             # 2 hours slack waiting time allowed if driver arrives early
            max_horizon_sec,  # Maximum horizon
            False,            # Don't force start to zero
            "Time"
        )
        time_dimension = routing.GetDimensionOrDie("Time")

        # Set Start & End bounds per vehicle on the Time dimension
        for v_idx in range(self.num_vehicles):
            start_idx = routing.Start(v_idx)
            end_idx = routing.End(v_idx)
            time_dimension.CumulVar(start_idx).SetValue(self.departure_time_sec)
            time_dimension.CumulVar(end_idx).SetRange(self.departure_time_sec, self.shift_end_sec)

        # 3. Vehicle-Specific Arc Cost Callbacks & Fixed Costs (B7 Cost Model Alignment)
        # Scale: paise (1 INR = 100 paise) so OR-Tools works with integer units
        for v_idx, v in enumerate(self.fleet):
            rate_per_meter_paise = (v.running_cost_per_km / 1000.0) * 100.0

            def create_cost_callback(rate):
                def cost_callback(from_index: int, to_index: int) -> int:
                    u = manager.IndexToNode(from_index)
                    v_node = manager.IndexToNode(to_index)
                    return int(round(self.distance_matrix[u][v_node] * rate))
                return cost_callback

            cost_cb = routing.RegisterTransitCallback(create_cost_callback(rate_per_meter_paise))
            routing.SetArcCostEvaluatorOfVehicle(cost_cb, v_idx)
            routing.SetFixedCostOfVehicle(int(round(v.fixed_dispatch_cost * 100)), v_idx)

        # 4. Capacity Dimension (Payload kg)
        def demand_callback(from_index: int) -> int:
            u = manager.IndexToNode(from_index)
            if u == 0:
                return 0
            return int(round(self.stops[u - 1].demand_kg))

        demand_cb_index = routing.RegisterUnaryTransitCallback(demand_callback)
        capacities = [int(round(v.payload_capacity_kg)) for v in self.fleet]
        routing.AddDimensionWithVehicleCapacity(
            demand_cb_index,
            0,
            capacities,
            True,
            "Capacity"
        )
        capacity_dim = routing.GetDimensionOrDie("Capacity")

        # 5. Stop Time Windows & Vehicle-Specific Restriction Constraints (B1 & B8 Fix)
        m_start, m_end = self.reg_engine.morning_ban_start, self.reg_engine.morning_ban_end
        e_start, e_end = self.reg_engine.evening_ban_start, self.reg_engine.evening_ban_end

        for i, stop in enumerate(self.stops):
            node_idx = i + 1
            idx = manager.NodeToIndex(node_idx)
            w_start, w_end = self.normalized_windows[i]

            # Set allowed stop time window on CumulVar
            time_dimension.CumulVar(idx).SetRange(w_start, w_end)

            vvar = routing.VehicleVar(idx)

            for v_idx, v in enumerate(self.fleet):
                # B8: Structural access check (Flyover height clearance & Bridge GVW)
                if self.enforce_guidelines:
                    if stop.requires_flyover and v.height_meters > self.reg_engine.flyover_height_limit_m:
                        vvar.RemoveValue(v_idx)
                        continue
                    if stop.max_access_gvw_tonnes is not None and v.gross_vehicle_weight_tonnes > stop.max_access_gvw_tonnes:
                        vvar.RemoveValue(v_idx)
                        continue

                # B1: Truck Peak-Hour Ban (Conditional per vehicle, never hitting vans)
                if (
                    self.enforce_guidelines
                    and v.vehicle_class == VehicleClass.FREIGHT_TRUCK
                    and stop.is_in_restricted_urban_core
                ):
                    # Check if stop window falls entirely inside a peak ban
                    entirely_in_morning = (w_start >= m_start and w_end <= m_end)
                    entirely_in_evening = (w_start >= e_start and w_end <= e_end)

                    if entirely_in_morning or entirely_in_evening:
                        # Trucks cannot serve this stop at all during its time window
                        vvar.RemoveValue(v_idx)
                    else:
                        # Conditional ban: If this truck visits the stop, arrival cannot fall in peak hours
                        tvar = time_dimension.CumulVar(idx)
                        in_m_ban = solver.IsBetweenVar(tvar, m_start, m_end)
                        in_e_ban = solver.IsBetweenVar(tvar, e_start, e_end)
                        is_this_v = solver.IsEqualCstVar(vvar, v_idx)
                        solver.Add(is_this_v * in_m_ban == 0)
                        solver.Add(is_this_v * in_e_ban == 0)

        # 6. Disjunctions (Drop penalty in paise: ₹50,000 = 5,000,000 paise)
        penalty_paise = 5_000_000
        for i in range(len(self.stops)):
            node_idx = i + 1
            routing.AddDisjunction([manager.NodeToIndex(node_idx)], penalty_paise)

        # 7. Search Strategy
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
        )
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_parameters.time_limit.seconds = 3

        monitor = None
        if FirstSolutionMonitor is not None:
            monitor = FirstSolutionMonitor(routing.solver())
            routing.AddSearchMonitor(monitor)

        solution = routing.SolveWithParameters(search_parameters)
        if not solution:
            return None

        first_solution_time_ms = monitor.first_solution_time_ms if monitor else None

        # 8. Extract Solution
        routes = []
        dropped_stops = []

        for i, stop in enumerate(self.stops):
            node_idx = i + 1
            idx = manager.NodeToIndex(node_idx)
            if solution.Value(routing.NextVar(idx)) == idx:
                dropped_stops.append(stop.stop_id)

        for v_idx in range(self.num_vehicles):
            vehicle = self.fleet[v_idx]
            speed_penalty = 1.30 if vehicle.vehicle_class == VehicleClass.FREIGHT_TRUCK else 1.0
            idx = routing.Start(v_idx)
            schedule = []
            route_dist = 0.0
            route_dur = 0.0

            while not routing.IsEnd(idx):
                node = manager.IndexToNode(idx)
                time_val = solution.Min(time_dimension.CumulVar(idx))
                load_val = solution.Value(capacity_dim.CumulVar(idx))

                schedule.append({
                    "node_index": node,
                    "arrival_time_sec": float(time_val),
                    "load_kg": float(load_val)
                })
                next_idx = solution.Value(routing.NextVar(idx))
                next_node = manager.IndexToNode(next_idx)
                route_dist += self.distance_matrix[node][next_node]
                route_dur += (self.duration_matrix[node][next_node] * speed_penalty)
                idx = next_idx

            # Final depot arrival
            node = manager.IndexToNode(idx)
            time_val = solution.Min(time_dimension.CumulVar(idx))
            schedule.append({
                "node_index": node,
                "arrival_time_sec": float(time_val),
                "load_kg": 0.0
            })

            utilized = len(schedule) > 2
            routes.append({
                "vehicle_id": vehicle.vehicle_id,
                "vehicle_name": vehicle.name,
                "vehicle_class": vehicle.vehicle_class,
                "color_hex": vehicle.color_hex,
                "schedule": schedule,
                "total_distance_m": route_dist,
                "total_duration_s": route_dur,
                "utilized": utilized
            })

        return {
            "routes": routes,
            "dropped_stops": dropped_stops,
            "time_to_first_solution_ms": round(first_solution_time_ms, 2) if first_solution_time_ms is not None else None,
        }

    def _solve_greedy_fallback(self) -> dict[str, Any]:
        """
        Greedy CVRPTW solver fallback with strict constraint checking.
        Shares the exact feasibility logic with OR-Tools.
        """
        t_greedy_start = time.perf_counter()
        unassigned = list(range(1, self.num_nodes))
        routes = []
        dropped_stops = []

        for vehicle in self.fleet:
            speed_penalty = 1.30 if vehicle.vehicle_class == VehicleClass.FREIGHT_TRUCK else 1.0

            if not unassigned:
                routes.append({
                    "vehicle_id": vehicle.vehicle_id,
                    "vehicle_name": vehicle.name,
                    "vehicle_class": vehicle.vehicle_class,
                    "color_hex": vehicle.color_hex,
                    "schedule": [
                        {"node_index": 0, "arrival_time_sec": float(self.departure_time_sec), "load_kg": 0.0},
                        {"node_index": 0, "arrival_time_sec": float(self.departure_time_sec), "load_kg": 0.0}
                    ],
                    "total_distance_m": 0.0,
                    "total_duration_s": 0.0,
                    "utilized": False
                })
                continue

            current_node = 0
            current_time = float(self.departure_time_sec)
            current_load = 0.0
            schedule = [{"node_index": 0, "arrival_time_sec": current_time, "load_kg": 0.0}]
            total_dist = 0.0
            total_dur = 0.0

            while unassigned:
                best_stop_idx = None
                best_arrival_time = 0.0
                best_cost = float("inf")

                for candidate_node in unassigned:
                    is_feasible, arrival_time, _ = self.check_stop_feasibility(
                        vehicle=vehicle,
                        stop_idx=candidate_node,
                        current_node=current_node,
                        current_time_sec=current_time,
                        current_load_kg=current_load,
                        penalty=speed_penalty
                    )
                    if not is_feasible:
                        continue

                    # Evaluate candidate cost (incremental distance * running cost)
                    d = self.distance_matrix[current_node][candidate_node]
                    cost = (d / 1000.0) * vehicle.running_cost_per_km

                    if cost < best_cost:
                        best_cost = cost
                        best_stop_idx = candidate_node
                        best_arrival_time = arrival_time

                if best_stop_idx is None:
                    break

                # Assign best stop
                unassigned.remove(best_stop_idx)
                stop_data = self.stops[best_stop_idx - 1]
                leg_dist = self.distance_matrix[current_node][best_stop_idx]
                leg_dur = self.duration_matrix[current_node][best_stop_idx] * speed_penalty

                current_load += stop_data.demand_kg
                current_time = best_arrival_time

                schedule.append({
                    "node_index": best_stop_idx,
                    "arrival_time_sec": current_time,
                    "load_kg": current_load
                })

                current_time += float(stop_data.service_duration_sec)
                total_dist += leg_dist
                total_dur += leg_dur + float(stop_data.service_duration_sec)
                current_node = best_stop_idx

            # Return to depot
            return_dist = self.distance_matrix[current_node][0]
            return_dur = self.duration_matrix[current_node][0] * speed_penalty
            depot_arrival = current_time + return_dur
            total_dist += return_dist
            total_dur += return_dur

            schedule.append({
                "node_index": 0,
                "arrival_time_sec": depot_arrival,
                "load_kg": 0.0
            })

            utilized = len(schedule) > 2
            routes.append({
                "vehicle_id": vehicle.vehicle_id,
                "vehicle_name": vehicle.name,
                "vehicle_class": vehicle.vehicle_class,
                "color_hex": vehicle.color_hex,
                "schedule": schedule,
                "total_distance_m": total_dist,
                "total_duration_s": total_dur,
                "utilized": utilized
            })

        for remaining_node in unassigned:
            dropped_stops.append(self.stops[remaining_node - 1].stop_id)

        greedy_time_ms = (time.perf_counter() - t_greedy_start) * 1000.0
        return {
            "routes": routes,
            "dropped_stops": dropped_stops,
            "time_to_first_solution_ms": round(greedy_time_ms, 2),
        }
