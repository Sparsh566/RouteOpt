"""
Tests for Issue #6:
Synthetic Mumbai & Pune benchmark instance generator.
"""

import json
import os

from benchmarks.generator import generate_instance, save_instance_to_file


def test_generator_reproducibility():
    """Generating with same seed produces identical instances."""
    inst1 = generate_instance(seed=123, stop_count=10, region="MUMBAI_MMRDA", fleet_mix="mixed")
    inst2 = generate_instance(seed=123, stop_count=10, region="MUMBAI_MMRDA", fleet_mix="mixed")
    assert inst1 == inst2

    # Different seed produces different coordinates
    inst3 = generate_instance(seed=456, stop_count=10, region="MUMBAI_MMRDA", fleet_mix="mixed")
    assert inst1["stops"][0]["lat"] != inst3["stops"][0]["lat"]

def test_generator_stop_counts_and_fleet_mixes():
    """Tests 10, 25, 50 stop counts and different fleet combinations."""
    for n in [10, 25, 50]:
        inst = generate_instance(seed=42, stop_count=n, region="PUNE_PMC", fleet_mix="all_vans")
        assert len(inst["stops"]) == n
        assert all(v["vehicle_class"] == "van" for v in inst["fleet"])

    inst_trucks = generate_instance(seed=42, stop_count=10, region="MUMBAI_MMRDA", fleet_mix="all_trucks")
    assert all(v["vehicle_class"] == "truck" for v in inst_trucks["fleet"])

def test_generator_file_saving(tmp_path):
    """Verifies that instances save as valid JSON in target directory."""
    inst = generate_instance(seed=99, stop_count=10)
    saved_path = save_instance_to_file(inst, output_dir=str(tmp_path))
    assert os.path.exists(saved_path)

    with open(saved_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["instance_id"] == inst["instance_id"]
    assert len(loaded["stops"]) == 10
