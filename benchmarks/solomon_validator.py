"""
Solomon CVRPTW Benchmark Validator and Optimality Gap Reporter

Evaluates RouteOpt's OR-Tools engine on standard Solomon CVRPTW benchmark instances
(e.g., C101, R101, RC101) and computes the optimality gap against Best-Known Solutions (BKS).
"""

import math
import os
import sys
import re
from typing import Dict, Any, List, Tuple, Optional
import logging

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.models.fleet_v2 import CommercialVehicleSpec, VehicleClass, DeliveryStop, DepotLocation
from backend.app.services.cvrptw_solver import CVRPTWSolver

logger = logging.getLogger("routeopt.benchmarks.solomon")

# Literature Best-Known Solutions for 25-customer Solomon instances
SOLOMON_25_BKS: Dict[str, Dict[str, float]] = {
    "C101": {"vehicles": 3.0, "distance": 191.3},
    "C102": {"vehicles": 3.0, "distance": 190.3},
    "R101": {"vehicles": 8.0, "distance": 617.1},
    "R102": {"vehicles": 7.0, "distance": 547.1},
    "RC101": {"vehicles": 4.0, "distance": 461.1},
    "RC102": {"vehicles": 3.0, "distance": 351.8},
}

class SolomonInstance:
    def __init__(
        self,
        name: str,
        num_vehicles: int,
        capacity: float,
        depot: Dict[str, float],
        customers: List[Dict[str, float]]
    ):
        self.name = name
        self.num_vehicles = num_vehicles
        self.capacity = capacity
        self.depot = depot
        self.customers = customers

    @classmethod
    def load_from_file(cls, filepath: str) -> "SolomonInstance":
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Solomon benchmark file not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        name = os.path.splitext(os.path.basename(filepath))[0]
        if lines:
            first_line = lines[0].split()
            if first_line:
                name = first_line[0]

        # Locate VEHICLE section
        num_vehicles = 25
        capacity = 200.0
        try:
            veh_idx = next(i for i, line in enumerate(lines) if "VEHICLE" in line.upper())
            # Line after headers contains vehicle numbers
            vals = lines[veh_idx + 2].split()
            num_vehicles = int(vals[0])
            capacity = float(vals[1])
        except Exception:
            pass

        # Locate CUSTOMER section
        cust_idx = next(i for i, line in enumerate(lines) if "CUSTOMER" in line.upper())
        # Skip header lines
        data_lines = lines[cust_idx + 2:]

        records = []
        for line in data_lines:
            parts = line.split()
            if len(parts) >= 7 and parts[0].isdigit():
                records.append({
                    "id": int(parts[0]),
                    "x": float(parts[1]),
                    "y": float(parts[2]),
                    "demand": float(parts[3]),
                    "ready_time": float(parts[4]),
                    "due_date": float(parts[5]),
                    "service_time": float(parts[6])
                })

        if not records:
            raise ValueError(f"No customer records found in {filepath}")

        depot_record = records[0]
        customer_records = records[1:]

        return cls(
            name=name,
            num_vehicles=num_vehicles,
            capacity=capacity,
            depot=depot_record,
            customers=customer_records
        )


def euclidean_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)


def run_solomon_benchmark(filepath: str, max_customers: Optional[int] = 25) -> Dict[str, Any]:
    """
    Loads Solomon instance, solves it using RouteOpt's CVRPTWSolver, and computes optimality gap against BKS.
    """
    instance = SolomonInstance.load_from_file(filepath)
    customers = instance.customers[:max_customers] if max_customers else instance.customers

    all_coords = [(instance.depot["x"], instance.depot["y"])] + [(c["x"], c["y"]) for c in customers]
    n = len(all_coords)

    # 1 unit distance in Solomon = 1 unit time
    dist_matrix = [[0.0] * n for _ in range(n)]
    dur_matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            d = euclidean_distance(all_coords[i], all_coords[j])
            dist_matrix[i][j] = d
            dur_matrix[i][j] = d

    # Convert coordinates to synthetic lat/lon for RouteOpt models
    depot_loc = DepotLocation(
        depot_id="DEPOT-0",
        name="Solomon Depot",
        lat=instance.depot["x"] / 10.0,
        lon=instance.depot["y"] / 10.0,
        operating_hours_sec=int(instance.depot["due_date"])
    )

    delivery_stops = []
    for c in customers:
        delivery_stops.append(DeliveryStop(
            stop_id=f"CUST-{c['id']}",
            name=f"Customer {c['id']}",
            lat=c["x"] / 10.0,
            lon=c["y"] / 10.0,
            demand_kg=c["demand"],
            time_window_start_sec=int(c["ready_time"]),
            time_window_end_sec=int(c["due_date"]),
            service_duration_sec=int(c["service_time"]),
            is_in_restricted_urban_core=False
        ))

    # Standard homogeneous fleet matching Solomon instance
    fleet = []
    for v_idx in range(instance.num_vehicles):
        fleet.append(CommercialVehicleSpec(
            vehicle_id=f"VEH-{v_idx+1}",
            name=f"Solomon Vehicle {v_idx+1}",
            vehicle_class=VehicleClass.DELIVERY_VAN,
            payload_capacity_kg=instance.capacity,
            gross_vehicle_weight_tonnes=3.5,
            height_meters=2.5,
            fixed_dispatch_cost=0.0,
            running_cost_per_km=1.0  # pure distance objective
        ))

    # Solve using CVRPTWSolver without municipal guidelines (pure benchmark mode)
    solver = CVRPTWSolver(
        distance_matrix=dist_matrix,
        duration_matrix=dur_matrix,
        depot=depot_loc,
        stops=delivery_stops,
        fleet=fleet,
        enforce_guidelines=False,
        departure_time_sec=0,
        region="MUMBAI_MMRDA"
    )

    solution = solver.solve()

    if not solution:
        return {
            "instance_name": instance.name,
            "status": "INFEASIBLE",
            "solved": False,
            "routes_count": 0,
            "total_distance": 0.0,
            "bks_distance": SOLOMON_25_BKS.get(instance.name, {}).get("distance"),
            "gap_percent": None
        }

    total_distance = sum(r.get("total_distance_m", 0.0) for r in solution.get("routes", []) if r.get("utilized", False))
    vehicles_used = sum(1 for r in solution.get("routes", []) if r.get("utilized", False))
    dropped_stops = solution.get("dropped_stops", [])

    bks_info = SOLOMON_25_BKS.get(instance.name, {})
    bks_dist = bks_info.get("distance")
    gap_pct = None
    status = "OPTIMAL_OR_FEASIBLE" if not dropped_stops else "PARTIAL"

    # Only compute and report optimality gap if 100% of customers are served.
    # When customers are dropped, comparing route distance against full BKS is mathematically invalid.
    if not dropped_stops and bks_dist is not None and bks_dist > 0:
        gap_pct = ((total_distance - bks_dist) / bks_dist) * 100.0

    return {
        "instance_name": instance.name,
        "status": status,
        "solved": True,
        "vehicles_used": vehicles_used,
        "bks_vehicles": bks_info.get("vehicles"),
        "total_distance": round(total_distance, 2),
        "bks_distance": bks_dist,
        "gap_percent": round(gap_pct, 2) if gap_pct is not None else None,
        "dropped_stops_count": len(dropped_stops),
        "solver_used": solution.get("solver_used", "OR-Tools")
    }


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    solomon_dir = os.path.join(base_dir, "data", "solomon")

    instances = ["C101.txt", "R101.txt", "RC101.txt"]
    print("=" * 98)
    print(f"{'Instance':<10} | {'Status':<10} | {'Vehicles':<9} | {'BKS Veh':<8} | {'Distance':<10} | {'BKS Dist':<9} | {'Dropped':<8} | {'Gap %':<18} | {'Solver'}")
    print("-" * 98)

    for inst in instances:
        path = os.path.join(solomon_dir, inst)
        if os.path.exists(path):
            res = run_solomon_benchmark(path, max_customers=25)
            if res["dropped_stops_count"] > 0:
                gap_str = f"N/A ({res['dropped_stops_count']} dropped)"
            elif res["gap_percent"] is not None:
                gap_str = f"{res['gap_percent']:+.2f}%"
            else:
                gap_str = "N/A"
            print(f"{res['instance_name']:<10} | {res['status']:<10} | {res['vehicles_used']:<9} | {str(res['bks_vehicles']):<8} | {res['total_distance']:<10.2f} | {str(res['bks_distance']):<9} | {res['dropped_stops_count']:<8} | {gap_str:<18} | {res['solver_used']}")
    print("=" * 98)
