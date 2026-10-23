"""
Tests for Issue #8:
Frontend research-ready metrics response fields and error/cost reporting.
"""

import pytest
from starlette.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_optimize_response_has_research_metrics():
    payload = {
        "depot": {"depot_id": "D1", "name": "Bhiwandi Hub", "lat": 19.2967, "lon": 73.0631},
        "stops": [
            {"stop_id": "S1", "name": "Mulund", "lat": 19.1726, "lon": 72.9565, "demand_kg": 150}
        ],
        "fleet": [
            {
                "vehicle_id": "VAN-01",
                "name": "Tata Ace",
                "vehicle_class": "van",
                "payload_capacity_kg": 1200,
                "gross_vehicle_weight_tonnes": 2.2,
                "height_meters": 1.9,
                "fixed_dispatch_cost": 500,
                "running_cost_per_km": 14
            }
        ],
        "departure_time_iso": "2026-10-09T08:30:00+05:30",
        "region": "MUMBAI_MMRDA",
        "apply_traffic_congestion": True,
        "enforce_government_guidelines": True
    }
    res = client.post("/api/optimize", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert "status" in data
    assert data["status"] in ["SUCCESS", "PARTIAL", "INFEASIBLE"]
    assert "solver_used" in data
    assert "departure_time" in data
    assert "is_real_road_data" in data
    assert "fixed_dispatch_cost_inr" in data
    assert "variable_running_cost_inr" in data
    assert data["fixed_dispatch_cost_inr"] > 0
    assert "validation_errors" in data
    assert isinstance(data["validation_errors"], list)
