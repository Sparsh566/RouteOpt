"""
Tests for Issue #5:
Solomon CVRPTW benchmark validation and gap reporting.
"""

import os
import pytest
from benchmarks.solomon_validator import SolomonInstance, run_solomon_benchmark, SOLOMON_25_BKS

def test_solomon_instance_loader():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    c101_path = os.path.join(base_dir, "benchmarks", "data", "solomon", "C101.txt")
    instance = SolomonInstance.load_from_file(c101_path)
    assert instance.name == "C101"
    assert instance.num_vehicles == 25
    assert instance.capacity == 200.0
    assert len(instance.customers) == 25
    assert instance.depot["id"] == 0

def test_solomon_c101_benchmark_solve_and_gap():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    c101_path = os.path.join(base_dir, "benchmarks", "data", "solomon", "C101.txt")
    res = run_solomon_benchmark(c101_path, max_customers=25)
    assert res["solved"] is True
    assert res["status"] in ["OPTIMAL_OR_FEASIBLE", "PARTIAL"]
    assert res["vehicles_used"] > 0
    assert res["total_distance"] > 0
    assert res["bks_distance"] == 191.3
    assert res["gap_percent"] is not None
    assert isinstance(res["gap_percent"], float)
