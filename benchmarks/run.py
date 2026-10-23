"""
Unified CLI Benchmark Harness for RouteOpt

Compares dispatch policies and solver architectures across synthetic and real benchmark instances:
  - Policy A: Ban-ignorant trucks (incurs fines & delays)
  - Policy B: Ban-aware trucks only (drops peak urban stops)
  - Policy C: Ban-aware mixed fleet (vans + trucks)
  - Solver comparison: OR-Tools vs Greedy heuristic fallback

Computes mean & standard deviation for cost, distance, vehicles, missed deadlines,
unserved stops, and solver runtime. Outputs CSV summaries and matplotlib visual plots.
"""

import os
import sys
import time
import json
import csv
import argparse
import statistics
from typing import Dict, Any, List, Tuple, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.models.fleet_v2 import CommercialVehicleSpec, VehicleClass, DeliveryStop, DepotLocation
from backend.app.services.cvrptw_solver import CVRPTWSolver
from backend.app.services.regulation_engine import RegionalRegulationEngine
from backend.app.services.validator import RouteValidator
from benchmarks.generator import generate_instance

# Try importing matplotlib
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


def _compute_haversine_matrices(coords: List[Tuple[float, float]]) -> Tuple[List[List[float]], List[List[float]]]:
    import math
    n = len(coords)
    dist_matrix = [[0.0] * n for _ in range(n)]
    dur_matrix = [[0.0] * n for _ in range(n)]
    R = 6371000.0  # Earth radius in meters
    WINDING_FACTOR = 1.35
    SPEED_MPS = 8.33

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            lat1, lon1 = coords[i]
            lat2, lon2 = coords[j]
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
            c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
            d_meters = R * c * WINDING_FACTOR
            dist_matrix[i][j] = d_meters
            dur_matrix[i][j] = d_meters / SPEED_MPS
    return dist_matrix, dur_matrix


def run_single_simulation(
    instance: Dict[str, Any],
    policy: str,
    force_greedy: bool = False
) -> Dict[str, Any]:
    """
    Executes one simulation run under a given policy:
      - Policy A: Ban-ignorant trucks (enforce_guidelines=False, fleet=all trucks)
      - Policy B: Ban-aware trucks (enforce_guidelines=True, fleet=all trucks)
      - Policy C: Ban-aware mixed (enforce_guidelines=True, fleet=mixed)
    """
    region = instance["metadata"]["region"]
    reg_engine = RegionalRegulationEngine(region)
    depot_raw = instance["depot"]
    depot = DepotLocation(**depot_raw)
    stops = [DeliveryStop(**s) for s in instance["stops"]]

    # Setup fleet according to policy
    total_demand = sum(s.demand_kg for s in stops)
    if policy == "Policy_A" or policy == "Policy_B":
        # All trucks
        num_trucks = max(2, int((total_demand / 2800.0) + 1))
        fleet = [
            CommercialVehicleSpec(
                vehicle_id=f"TRUCK-{i+1:02d}",
                name=f"Tata 407 Truck {i+1}",
                vehicle_class=VehicleClass.FREIGHT_TRUCK,
                payload_capacity_kg=4000.0,
                gross_vehicle_weight_tonnes=7.5,
                height_meters=3.1,
                fixed_dispatch_cost=1200.0,
                running_cost_per_km=24.0
            ) for i in range(num_trucks)
        ]
        enforce = (policy == "Policy_B")
    else:  # Policy_C
        fleet = [CommercialVehicleSpec(**v) for v in instance["fleet"]]
        enforce = True

    all_coords = [(depot.lat, depot.lon)] + [(s.lat, s.lon) for s in stops]
    dist_matrix, dur_matrix = _compute_haversine_matrices(all_coords)

    departure_sec = 30600  # 08:30 AM

    solver = CVRPTWSolver(
        distance_matrix=dist_matrix,
        duration_matrix=dur_matrix,
        depot=depot,
        stops=stops,
        fleet=fleet,
        enforce_guidelines=enforce,
        departure_time_sec=departure_sec,
        region=region
    )

    t0 = time.perf_counter()
    if force_greedy:
        sol = solver._solve_greedy_fallback()
    else:
        sol = solver.solve()
    runtime_ms = (time.perf_counter() - t0) * 1000.0

    if not sol or not sol.get("routes"):
        return {
            "policy": policy,
            "cost_inr": 0.0,
            "distance_km": 0.0,
            "vehicles_used": 0,
            "missed_deadlines": 0,
            "unserved_stops": len(stops),
            "runtime_ms": round(runtime_ms, 2),
            "fines_inr": 0.0
        }

    # Evaluate validation & penalties
    validator = RouteValidator(
        depot=depot,
        stops=stops,
        fleet=fleet,
        distance_matrix=dist_matrix,
        duration_matrix=dur_matrix,
        departure_time_sec=departure_sec,
        region=region,
        enforce_guidelines=True
    )
    report = validator.validate(sol["routes"], sol.get("dropped_stops", []))

    # Base operational cost
    total_cost = 0.0
    total_dist_m = 0.0
    vehicles_used = 0
    for r in sol["routes"]:
        if r.get("utilized", False):
            vehicles_used += 1
            v_spec = next((v for v in fleet if v.vehicle_id == r["vehicle_id"]), None)
            fixed_c = v_spec.fixed_dispatch_cost if v_spec else 500.0
            km_rate = v_spec.running_cost_per_km if v_spec else 15.0
            d_km = r["total_distance_m"] / 1000.0
            total_dist_m += r["total_distance_m"]
            total_cost += fixed_c + (d_km * km_rate)

    # If Policy A (ban ignorant), add fines for peak-hour breaches
    fines_incurred = 0.0
    if policy == "Policy_A":
        # Each truck that entered restricted stops during peak windows gets fined
        ban_violations = [e for e in report["errors"] if e.get("error_type") == "TRUCK_PEAK_BAN_VIOLATION"]
        fines_incurred = len(ban_violations) * reg_engine.violation_fine_inr
        total_cost += fines_incurred

    # Drop penalty for unserved stops (Rs 2,500 per dropped stop)
    dropped_count = len(sol.get("dropped_stops", []))
    total_cost += dropped_count * 2500.0

    missed_tw = sum(1 for e in report["errors"] if e.get("error_type") == "TIME_WINDOW_MISSED")

    return {
        "policy": policy,
        "cost_inr": round(total_cost, 2),
        "distance_km": round(total_dist_m / 1000.0, 2),
        "vehicles_used": vehicles_used,
        "missed_deadlines": missed_tw,
        "unserved_stops": dropped_count,
        "runtime_ms": round(runtime_ms, 2),
        "fines_inr": fines_incurred
    }


def run_benchmark_suite(
    runs: int = 5,
    stop_counts: List[int] = [10, 25],
    regions: List[str] = ["MUMBAI_MMRDA"],
    output_dir: str = "results"
) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    summary_data = []

    policies = ["Policy_A", "Policy_B", "Policy_C"]

    print(f"Starting RouteOpt Benchmark Suite: {runs} runs per experiment...")

    for region in regions:
        for n_stops in stop_counts:
            # 1. Compare Policies (A vs B vs C) with OR-Tools
            for policy in policies:
                records = []
                for seed_idx in range(runs):
                    seed = 42 + seed_idx * 17
                    inst = generate_instance(seed=seed, stop_count=n_stops, region=region, fleet_mix="mixed")
                    res = run_single_simulation(inst, policy=policy, force_greedy=False)
                    records.append(res)

                cost_mean = statistics.mean([r["cost_inr"] for r in records])
                cost_std = statistics.stdev([r["cost_inr"] for r in records]) if len(records) > 1 else 0.0
                dist_mean = statistics.mean([r["distance_km"] for r in records])
                veh_mean = statistics.mean([r["vehicles_used"] for r in records])
                unserved_mean = statistics.mean([r["unserved_stops"] for r in records])
                deadlines_mean = statistics.mean([r["missed_deadlines"] for r in records])
                runtime_mean = statistics.mean([r["runtime_ms"] for r in records])

                summary_data.append({
                    "region": region,
                    "stops": n_stops,
                    "solver": "OR-Tools",
                    "policy": policy,
                    "cost_mean_inr": round(cost_mean, 2),
                    "cost_std_inr": round(cost_std, 2),
                    "distance_mean_km": round(dist_mean, 2),
                    "vehicles_mean": round(veh_mean, 2),
                    "unserved_stops_mean": round(unserved_mean, 2),
                    "missed_deadlines_mean": round(deadlines_mean, 2),
                    "runtime_mean_ms": round(runtime_mean, 2)
                })

            # 2. Compare OR-Tools vs Greedy on Policy C
            greedy_records = []
            for seed_idx in range(runs):
                seed = 42 + seed_idx * 17
                inst = generate_instance(seed=seed, stop_count=n_stops, region=region, fleet_mix="mixed")
                res = run_single_simulation(inst, policy="Policy_C", force_greedy=True)
                greedy_records.append(res)

            g_cost_mean = statistics.mean([r["cost_inr"] for r in greedy_records])
            g_cost_std = statistics.stdev([r["cost_inr"] for r in greedy_records]) if len(greedy_records) > 1 else 0.0
            g_dist_mean = statistics.mean([r["distance_km"] for r in greedy_records])
            g_veh_mean = statistics.mean([r["vehicles_used"] for r in greedy_records])
            g_unserved_mean = statistics.mean([r["unserved_stops"] for r in greedy_records])
            g_deadlines_mean = statistics.mean([r["missed_deadlines"] for r in greedy_records])
            g_runtime_mean = statistics.mean([r["runtime_ms"] for r in greedy_records])

            summary_data.append({
                "region": region,
                "stops": n_stops,
                "solver": "Greedy-Fallback",
                "policy": "Policy_C",
                "cost_mean_inr": round(g_cost_mean, 2),
                "cost_std_inr": round(g_cost_std, 2),
                "distance_mean_km": round(g_dist_mean, 2),
                "vehicles_mean": round(g_veh_mean, 2),
                "unserved_stops_mean": round(g_unserved_mean, 2),
                "missed_deadlines_mean": round(g_deadlines_mean, 2),
                "runtime_mean_ms": round(g_runtime_mean, 2)
            })

    # Save to CSV
    csv_path = os.path.join(output_dir, "benchmark_summary.csv")
    fieldnames = [
        "region", "stops", "solver", "policy",
        "cost_mean_inr", "cost_std_inr", "distance_mean_km",
        "vehicles_mean", "unserved_stops_mean", "missed_deadlines_mean", "runtime_mean_ms"
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_data)

    print(f"\nBenchmark summary written to: {csv_path}")

    # Generate Matplotlib plots
    if HAS_MATPLOTLIB:
        _generate_plots(summary_data, output_dir)

    return {"summary": summary_data, "csv_path": csv_path}


def _generate_plots(data: List[Dict[str, Any]], output_dir: str):
    # Plot 1: Policy Comparison (Cost vs Unserved) for 25 stops
    subset_25 = [d for d in data if d["stops"] == 25 and d["solver"] == "OR-Tools"]
    if subset_25:
        policies = [d["policy"].replace("_", " ") for d in subset_25]
        costs = [d["cost_mean_inr"] for d in subset_25]
        unserved = [d["unserved_stops_mean"] for d in subset_25]

        fig, ax1 = plt.subplots(figsize=(8, 5))
        ax2 = ax1.twinx()

        bars = ax1.bar(policies, costs, color="#3b82f6", alpha=0.8, width=0.4, label="Total Cost (INR)")
        line = ax2.plot(policies, unserved, color="#ef4444", marker="o", linewidth=2.5, label="Unserved Stops")

        ax1.set_ylabel("Mean Cost (INR)", color="#1e3a8a", fontsize=11)
        ax2.set_ylabel("Mean Unserved Stops", color="#991b1b", fontsize=11)
        ax1.set_title("Policy Comparison: Ban-Ignorant vs Ban-Aware vs Mixed Fleet (N=25)", fontsize=12, pad=15)

        plot1_path = os.path.join(output_dir, "policy_comparison.png")
        plt.tight_layout()
        plt.savefig(plot1_path, dpi=150)
        plt.close()
        print(f"Policy comparison plot saved to: {plot1_path}")

    # Plot 2: Solver Comparison (OR-Tools vs Greedy) runtime and cost
    solver_data = [d for d in data if d["policy"] == "Policy_C" and d["stops"] == 25]
    if len(solver_data) >= 2:
        solvers = [d["solver"] for d in solver_data]
        costs = [d["cost_mean_inr"] for d in solver_data]
        runtimes = [d["runtime_mean_ms"] for d in solver_data]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
        ax1.bar(solvers, costs, color=["#10b981", "#f59e0b"], width=0.4)
        ax1.set_title("Cost Comparison (INR)", fontsize=11)
        ax1.set_ylabel("Mean Cost (INR)")

        ax2.bar(solvers, runtimes, color=["#6366f1", "#8b5cf6"], width=0.4)
        ax2.set_title("Runtime Comparison (ms)", fontsize=11)
        ax2.set_ylabel("Solver Runtime (ms)")

        plot2_path = os.path.join(output_dir, "solver_comparison.png")
        plt.tight_layout()
        plt.savefig(plot2_path, dpi=150)
        plt.close()
        print(f"Solver comparison plot saved to: {plot2_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run RouteOpt Benchmark Suite")
    parser.add_argument("--runs", type=int, default=5, help="Number of runs per scenario")
    parser.add_argument("--out", type=str, default="results", help="Output directory")
    args = parser.parse_args()

    run_benchmark_suite(runs=args.runs, output_dir=args.out)
