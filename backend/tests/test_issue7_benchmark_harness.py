"""
Tests for Issue #7:
Unified CLI benchmark harness with policies, CSV, and plot outputs.
"""

import os

from benchmarks.run import run_benchmark_suite


def test_benchmark_suite_execution(tmp_path):
    """Run a lightweight benchmark run and verify CSV and plots are generated."""
    out_dir = str(tmp_path / "results")
    res = run_benchmark_suite(
        runs=1,
        stop_counts=[10],
        regions=["MUMBAI_MMRDA"],
        output_dir=out_dir
    )
    assert "summary" in res
    assert len(res["summary"]) > 0
    assert os.path.exists(res["csv_path"])

    # Check that CSV contains headers and data rows including Policy_D and time_to_first_solution_ms
    with open(res["csv_path"], "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) >= 6
    assert "policy" in lines[0]
    assert "time_to_first_solution_ms" in lines[0]
    assert any(d["policy"] == "Policy_D" for d in res["summary"])
    for row in res["summary"]:
        assert "time_to_first_solution_ms" in row
        assert row["time_to_first_solution_ms"] > 0
        assert "cost_mean_inr" in row


def test_cvrptw_solver_reports_first_solution_time():
    """Verify CVRPTWSolver returns time_to_first_solution_ms for both OR-Tools and Greedy fallback."""
    from backend.app.models.fleet_v2 import CommercialVehicleSpec, DeliveryStop, DepotLocation
    from backend.app.services.cvrptw_solver import CVRPTWSolver
    from benchmarks.generator import generate_instance
    from benchmarks.run import _compute_haversine_matrices

    inst = generate_instance(seed=42, stop_count=10, region="MUMBAI_MMRDA", fleet_mix="mixed")
    depot = DepotLocation(**inst["depot"])
    stops = [DeliveryStop(**s) for s in inst["stops"]]
    fleet = [CommercialVehicleSpec(**v) for v in inst["fleet"]]
    all_coords = [(depot.lat, depot.lon)] + [(s.lat, s.lon) for s in stops]
    dist_m, dur_m = _compute_haversine_matrices(all_coords)

    solver = CVRPTWSolver(
        distance_matrix=dist_m,
        duration_matrix=dur_m,
        depot=depot,
        stops=stops,
        fleet=fleet,
        enforce_guidelines=True,
        departure_time_sec=30600,
        region="MUMBAI_MMRDA"
    )

    sol_ortools = solver.solve()
    assert sol_ortools is not None
    assert "time_to_first_solution_ms" in sol_ortools
    assert sol_ortools["time_to_first_solution_ms"] is not None
    assert sol_ortools["time_to_first_solution_ms"] > 0

    sol_greedy = solver._solve_greedy_fallback()
    assert sol_greedy is not None
    assert "time_to_first_solution_ms" in sol_greedy
    assert sol_greedy["time_to_first_solution_ms"] is not None
    assert sol_greedy["time_to_first_solution_ms"] > 0

