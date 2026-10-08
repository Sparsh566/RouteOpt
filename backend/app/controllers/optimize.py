"""
FastAPI Controller: Commercial Fleet Route Optimization (Vans & Trucks)
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import time
from backend.app.models.fleet_v2 import (
    OptimizeV2Request,
    OptimizeV2Response,
    VehicleRouteResult,
    StopVisit
)
from backend.app.services.osrm_service import OSRMService
from backend.app.services.traffic_engine import TrafficEngine
from backend.app.services.cvrptw_solver import CVRPTWSolver
from backend.app.services.regulation_engine import RegionalRegulationEngine

router = APIRouter(tags=["Commercial Fleet Optimization"])

@router.post("/optimize", response_model=OptimizeV2Response)
async def optimize_fleet_routes(payload: OptimizeV2Request):
    t0 = time.perf_counter()

    if not payload.stops:
        raise HTTPException(status_code=400, detail="At least 1 delivery stop is required.")
    if not payload.fleet:
        raise HTTPException(status_code=400, detail="At least 1 commercial vehicle (Van or Truck) is required.")

    # 1. Prepare waypoint coordinate list (Depot + Stops)
    all_coords = [[payload.depot.lat, payload.depot.lon]] + [[s.lat, s.lon] for s in payload.stops]

    # 2. Query OSRM matrices (with automatic high-fidelity road winding fallback)
    dist_matrix, base_dur_matrix, is_real_osrm = await OSRMService.get_matrices(all_coords)

    # 3. Apply peak-hour traffic degradation multipliers
    if payload.apply_traffic_congestion:
        dur_matrix = TrafficEngine.apply_traffic(base_dur_matrix, payload.departure_time_iso or "")
        traffic_factor = TrafficEngine.get_congestion_factor(payload.departure_time_iso)
    else:
        dur_matrix = base_dur_matrix
        traffic_factor = 1.0

    # 4. Execute CVRPTW Solver with Road Guidelines
    solver = CVRPTWSolver(
        distance_matrix=dist_matrix,
        duration_matrix=dur_matrix,
        depot=payload.depot,
        stops=payload.stops,
        fleet=payload.fleet,
        enforce_guidelines=payload.enforce_government_guidelines
    )

    solution = solver.solve()
    if not solution:
        raise HTTPException(
            status_code=400,
            detail="Infeasible routing constraints. Verify that vehicle capacities and time windows allow delivery."
        )

    # 5. Build detailed vehicle routes and GeoJSON polylines
    routes: List[VehicleRouteResult] = []
    total_fleet_dist = 0.0
    total_fleet_dur = 0.0
    total_fleet_cost = 0.0

    reg_engine = RegionalRegulationEngine(payload.region)
    compliance_notes = []

    for route_data in solution["routes"]:
        v_id = route_data["vehicle_id"]
        # Find matching vehicle spec
        vehicle_spec = next(v for v in payload.fleet if v.vehicle_id == v_id)
        schedule_nodes = route_data["schedule"]

        if not route_data["utilized"]:
            continue

        stops_visited: List[StopVisit] = []
        route_coords = []

        for item in schedule_nodes:
            node_idx = item["node_index"]
            arrival_sec = item["arrival_time_sec"]

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

            # Format clock time (e.g. 08:30 + arrival_sec)
            hrs = (8 + (arrival_sec // 3600)) % 24
            mins = (30 + ((arrival_sec % 3600) // 60)) % 60
            clock_str = f"{hrs:02d}:{mins:02d} IST"

            stops_visited.append(StopVisit(
                stop_id=s_id,
                name=name,
                lat=lat,
                lon=lon,
                arrival_time_sec=arrival_sec,
                departure_time_sec=arrival_sec + (300 if node_idx > 0 else 0),
                waiting_time_sec=0,
                current_load_kg=float(item["load_kg"]),
                clock_time_str=clock_str
            ))

        # Query real road geometry
        geometry = await OSRMService.get_route_geometry(route_coords)

        dist_m = route_data["total_distance_m"]
        dur_s = route_data["total_duration_s"]
        cost_inr = vehicle_spec.fixed_dispatch_cost + ((dist_m / 1000.0) * vehicle_spec.running_cost_per_km)

        total_fleet_dist += dist_m
        total_fleet_dur += dur_s
        total_fleet_cost += cost_inr

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

    # Notes
    if payload.enforce_government_guidelines:
        compliance_notes.append("Enforced: Municipal Corporation peak-hour HCV No-Entry restrictions (08:00-11:30 & 17:00-21:30).")
        compliance_notes.append("Enforced: Flyover 2.5m overhead height clearance gantry checks for freight trucks.")
    if is_real_osrm:
        compliance_notes.append("Live OSRM road graph queried successfully.")
    else:
        compliance_notes.append("Calculated using urban high-fidelity road winding model (1.35x detour factor).")

    solve_ms = (time.perf_counter() - t0) * 1000

    return OptimizeV2Response(
        status="SUCCESS" if not solution["dropped_stops"] else "PARTIAL",
        routes=routes,
        dropped_stops=solution["dropped_stops"],
        total_fleet_distance_km=round(total_fleet_dist / 1000.0, 2),
        total_fleet_duration_hours=round(total_fleet_dur / 3600.0, 2),
        total_fleet_cost_inr=round(total_fleet_cost, 2),
        traffic_factor_applied=1.65 if payload.apply_traffic_congestion else 1.0,
        regulatory_compliance_notes=compliance_notes,
        solve_duration_ms=round(solve_ms, 2)
    )
