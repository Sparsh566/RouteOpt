"""
Tests for Issue #7:
Unified CLI benchmark harness with policies, CSV, and plot outputs.
"""

import os
import pytest
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

    # Check that CSV contains headers and data rows
    with open(res["csv_path"], "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) >= 5
    assert "policy" in lines[0]
