"""
FastAPI Controller: Commercial Fleet Route Optimization (Vans & Trucks)
"""

import asyncio
import time
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query

from backend.app.models.fleet_v2 import (
    OptimizeV2Request,
    OptimizeV2Response,
    StopVisit,
    VehicleRouteResult,
)
from backend.app.services.audit_service import AuditService
from backend.app.services.cvrptw_solver import CVRPTWSolver
from backend.app.services.osrm_service import OSRMService
from backend.app.services.traffic_engine import TrafficEngine
from backend.app.services.validator import RouteValidator
from backend.app.utils import parse_departure_datetime

router = APIRouter(tags=["Commercial Fleet Optimization"])



@router.post("/optimize", response_model=OptimizeV2Response)
async def optimize_fleet_routes(payload: OptimizeV2Request):
    t0 = time.perf_counter()

    if not payload.stops:
        raise HTTPException(status_code=400, detail="At least 1 delivery stop is required.")
    if not payload.fleet:
        raise HTTPException(status_code=400, detail="At least 1 commercial vehicle (Van or Truck) is required.")

    # 1. Parse Departure Time & Unified Time Axis (B4 & B5)
    departure_dt, departure_sec = parse_departure_datetime(payload.departure_time_iso)

    # 2. Prepare waypoint coordinate list (Depot + Stops)
    all_coords = [[payload.depot.lat, payload.depot.lon]] + [[s.lat, s.lon] for s in payload.stops]

    # 3. Query OSRM matrices (with automatic high-fidelity road winding fallback)
    dist_matrix, base_dur_matrix, is_real_osrm = await OSRMService.get_matrices(all_coords)

    # 4. Apply peak-hour traffic degradation multipliers (B6)
    if payload.apply_traffic_congestion:
        traffic_factor = TrafficEngine.get_congestion_factor(payload.departure_time_iso)
        dur_matrix = TrafficEngine.apply_traffic(base_dur_matrix, payload.departure_time_iso)
    else:
        traffic_factor = 1.0
        dur_matrix = base_dur_matrix

    # 5. Execute CVRPTW Solver with Road Guidelines & Single Time Axis
    solver = CVRPTWSolver(
        distance_matrix=dist_matrix,
        duration_matrix=dur_matrix,
        depot=payload.depot,
        stops=payload.stops,
        fleet=payload.fleet,
        enforce_guidelines=payload.enforce_government_guidelines,
        departure_time_sec=departure_sec,
        region=payload.region
    )

    # Execute CVRPTW solver non-blockingly on worker thread to avoid blocking FastAPI event loop
    solution = await asyncio.to_thread(solver.solve)
    if not solution:
        raise HTTPException(
            status_code=400,
            detail="Infeasible routing constraints. Verify that vehicle capacities and time windows allow delivery."
        )

    # 6. Build detailed vehicle routes and GeoJSON polylines
    routes: list[VehicleRouteResult] = []
    total_fleet_dist = 0.0
    total_fleet_dur = 0.0
    total_fleet_cost = 0.0
    total_fixed_cost = 0.0
    total_variable_cost = 0.0

    midnight_dt = departure_dt.replace(hour=0, minute=0, second=0, microsecond=0)

    for route_data in solution["routes"]:
        v_id = route_data["vehicle_id"]
        vehicle_spec = next(v for v in payload.fleet if v.vehicle_id == v_id)
        schedule_nodes = route_data["schedule"]

        if not route_data["utilized"]:
            continue

        stops_visited: list[StopVisit] = []
        route_coords = []

        for item in schedule_nodes:
            node_idx = item["node_index"]
            arrival_sec = float(item["arrival_time_sec"])

            if node_idx == 0:
                name = payload.depot.name
                lat, lon = payload.depot.lat, payload.depot.lon
                s_id = payload.depot.depot_id
            else:
                stop = payload.stops[node_idx - 1]
                name = stop.name
                lat, lon = stop.lat, stop.lon
                s_id = stop.stop_id

            route_coords.append([lat, lon])

            # Datetime arithmetic from parsed departure time (B4)
            arrival_dt = midnight_dt + timedelta(seconds=arrival_sec)
            clock_str = arrival_dt.strftime("%H:%M IST")

            dwell_sec = 300 if node_idx > 0 else 0
            stops_visited.append(StopVisit(
                stop_id=s_id,
                name=name,
                lat=lat,
                lon=lon,
                arrival_time_sec=int(round(arrival_sec)),
                departure_time_sec=int(round(arrival_sec + dwell_sec)),
                waiting_time_sec=0,
                current_load_kg=float(item["load_kg"]),
                clock_time_str=clock_str
            ))

        # Query real road geometry
        geometry = await OSRMService.get_route_geometry(route_coords)

        dist_m = route_data["total_distance_m"]
        dur_s = route_data["total_duration_s"]
        fixed_c = vehicle_spec.fixed_dispatch_cost
        var_c = (dist_m / 1000.0) * vehicle_spec.running_cost_per_km
        cost_inr = fixed_c + var_c

        total_fleet_dist += dist_m
        total_fleet_dur += dur_s
        total_fleet_cost += cost_inr
        total_fixed_cost += fixed_c
        total_variable_cost += var_c

        routes.append(VehicleRouteResult(
            vehicle_id=vehicle_spec.vehicle_id,
            vehicle_name=vehicle_spec.name,
            vehicle_class=vehicle_spec.vehicle_class,
            color_hex=vehicle_spec.color_hex or "#06b6d4",
            stops_visited=stops_visited,
            total_distance_m=round(dist_m, 1),
            total_duration_s=round(dur_s, 1),
            total_load_kg=round(sum(s.demand_kg for s in payload.stops if s.stop_id in [sv.stop_id for sv in stops_visited]), 1),
            total_wait_s=0.0,
            estimated_cost_inr=round(cost_inr, 2),
            route_geometry=geometry
        ))

    # Compliance Notes
    compliance_notes = []
    if payload.enforce_government_guidelines:
        compliance_notes.append("Enforced: Municipal Corporation peak-hour HCV No-Entry restrictions (08:00-11:30 & 17:00-21:30).")
        compliance_notes.append("Enforced: Flyover 2.5m overhead height clearance gantry checks for freight trucks.")
    if is_real_osrm:
        compliance_notes.append("Live OSRM road graph queried successfully.")
    else:
        compliance_notes.append("Calculated using urban high-fidelity road winding model (1.35x detour factor).")

    # 6. Independent Route Validation (Phase 2)
    validator = RouteValidator(
        depot=payload.depot,
        stops=payload.stops,
        fleet=payload.fleet,
        distance_matrix=dist_matrix,
        duration_matrix=dur_matrix,
        departure_time_sec=departure_sec,
        region=payload.region,
        enforce_guidelines=payload.enforce_government_guidelines
    )
    val_report = validator.validate(
        routes=solution["routes"],
        dropped_stops=solution["dropped_stops"]
    )

    solve_ms = (time.perf_counter() - t0) * 1000
    solver_used = solution.get("solver_used", "Google OR-Tools (CVRPTW)")
    dist_km = round(total_fleet_dist / 1000.0, 2)
    dur_hours = round(total_fleet_dur / 3600.0, 2)
    cost_inr = round(total_fleet_cost, 2)

    # Asynchronously / reliably persist optimization audit record
    AuditService.record_run(
        region=payload.region,
        status=val_report["status"],
        solver_used=solver_used,
        stops_count=len(payload.stops),
        fleet_count=len(payload.fleet),
        total_distance_km=dist_km,
        total_duration_hours=dur_hours,
        total_cost_inr=cost_inr,
        solve_duration_ms=round(solve_ms, 2),
        dropped_stops_count=len(solution["dropped_stops"]),
        compliance_notes=compliance_notes,
        validation_errors_count=len(val_report["errors"]),
    )

    return OptimizeV2Response(
        status=val_report["status"],
        routes=routes,
        dropped_stops=solution["dropped_stops"],
        total_fleet_distance_km=dist_km,
        total_fleet_duration_hours=dur_hours,
        total_fleet_cost_inr=cost_inr,
        fixed_dispatch_cost_inr=round(total_fixed_cost, 2),
        variable_running_cost_inr=round(total_variable_cost, 2),
        solver_used=solver_used,
        departure_time=payload.departure_time_iso or "",
        traffic_factor_applied=traffic_factor,
        regulatory_compliance_notes=compliance_notes,
        regulatory_data_status="simulated_regulatory_model",
        solve_duration_ms=round(solve_ms, 2),
        is_real_road_data=is_real_osrm,
        validation_errors=val_report["errors"]
    )


# API Versioning Aliases & History Endpoints
@router.post("/v2/optimize", response_model=OptimizeV2Response)
async def optimize_fleet_routes_v2(payload: OptimizeV2Request):
    """v2 API alias for fleet route optimization."""
    return await optimize_fleet_routes(payload)


@router.get("/history", tags=["Commercial Fleet Optimization"])
@router.get("/v2/history", tags=["Commercial Fleet Optimization"])
async def get_route_history(limit: int = Query(default=20, ge=1, le=100)):
    """Retrieve recent route optimization and compliance audit logs."""
    return {
        "status": "SUCCESS",
        "count": len(AuditService.get_recent_runs(limit=limit)),
        "history": AuditService.get_recent_runs(limit=limit)
    }
