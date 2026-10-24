"""
Integration tests for RouteOpt FastAPI endpoints:
Validates HTTP request/response lifecycles, v2 API routes, history logging, and regulatory metadata.
"""

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OK"
    assert "app" in data
    assert "osrm_endpoint" in data


def test_guidelines_endpoint():
    response = client.get("/api/guidelines?region=MUMBAI_MMRDA")
    assert response.status_code == 200
    data = response.json()
    assert "region_name" in data
    assert "rules" in data
    assert "citations" in data


def test_optimize_endpoint_v1_and_v2():
    payload = {
        "depot": {
            "depot_id": "DEPOT-01",
            "name": "Bhiwandi Central Hub",
            "lat": 19.2965,
            "lon": 73.0631,
            "operating_hours_sec": 43200,
        },
        "stops": [
            {
                "stop_id": "STOP-01",
                "name": "Dadar Retail Market",
                "lat": 19.0178,
                "lon": 72.8478,
                "demand_kg": 100.0,
                "time_window_start_sec": 32400,
                "time_window_end_sec": 43200,
                "window_mode": "absolute",
            },
            {
                "stop_id": "STOP-02",
                "name": "BKC Commercial Hub",
                "lat": 19.0607,
                "lon": 72.8683,
                "demand_kg": 80.0,
                "time_window_start_sec": 36000,
                "time_window_end_sec": 50400,
                "window_mode": "absolute",
            },
        ],
        "fleet": [
            {
                "vehicle_id": "VAN-01",
                "name": "Tata Ace Gold",
                "vehicle_class": "van",
                "gross_vehicle_weight_tonnes": 1.6,
                "height_meters": 1.85,
                "payload_capacity_kg": 800.0,
                "fixed_dispatch_cost": 300.0,
                "running_cost_per_km": 12.0,
            }
        ],
        "departure_time_iso": "2026-10-09T08:30:00+05:30",
        "region": "MUMBAI_MMRDA",
        "apply_traffic_congestion": True,
        "enforce_government_guidelines": True,
    }

    # Test v1 /api/optimize
    resp_v1 = client.post("/api/optimize", json=payload)
    assert resp_v1.status_code == 200
    data_v1 = resp_v1.json()
    assert data_v1["status"] in ["SUCCESS", "PARTIAL"]
    assert "routes" in data_v1
    assert data_v1["regulatory_data_status"] == "simulated_regulatory_model"
    assert len(data_v1["routes"]) >= 1

    # Test v2 alias /api/v2/optimize
    resp_v2 = client.post("/api/v2/optimize", json=payload)
    assert resp_v2.status_code == 200
    data_v2 = resp_v2.json()
    assert data_v2["status"] in ["SUCCESS", "PARTIAL"]
    assert data_v2["regulatory_data_status"] == "simulated_regulatory_model"


def test_history_endpoint_records_runs():
    # Verify that prior runs were saved to the route history
    resp = client.get("/api/v2/history?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert "history" in data
    assert isinstance(data["history"], list)
    assert len(data["history"]) >= 1
    recent = data["history"][0]
    assert "total_cost_inr" in recent
    assert "solver_used" in recent
    assert "region" in recent


def test_simulation_endpoint_v1_and_v2():
    sim_payload = {
        "scenario_type": "URGENT_STOP",
        "depot": {
            "depot_id": "DEPOT-01",
            "name": "Bhiwandi Central Hub",
            "lat": 19.2965,
            "lon": 73.0631,
            "operating_hours_sec": 43200,
        },
        "stops": [
            {
                "stop_id": "STOP-01",
                "name": "Dadar Retail Market",
                "lat": 19.0178,
                "lon": 72.8478,
                "demand_kg": 100.0,
                "time_window_start_sec": 32400,
                "time_window_end_sec": 43200,
                "window_mode": "absolute",
            }
        ],
        "fleet": [
            {
                "vehicle_id": "VAN-01",
                "name": "Tata Ace Gold",
                "vehicle_class": "van",
                "gross_vehicle_weight_tonnes": 1.6,
                "height_meters": 1.85,
                "payload_capacity_kg": 800.0,
                "fixed_dispatch_cost": 300.0,
                "running_cost_per_km": 12.0,
            }
        ],
        "departure_time_iso": "2026-10-09T08:30:00+05:30",
        "parameters": {},
    }

    # Test v1 /api/simulate
    resp1 = client.post("/api/simulate", json=sim_payload)
    assert resp1.status_code == 200
    res1 = resp1.json()
    assert res1["feasibility_status"] in ["COMPLIANT", "VIOLATION_DETECTED", "REROUTED_SUCCESSFULLY", "INFEASIBLE"]
    assert "ai_advisory_recommendation" in res1

    # Test v2 alias /api/v2/simulate
    resp2 = client.post("/api/v2/simulate", json=sim_payload)
    assert resp2.status_code == 200
    res2 = resp2.json()
    assert res2["feasibility_status"] in ["COMPLIANT", "VIOLATION_DETECTED", "REROUTED_SUCCESSFULLY", "INFEASIBLE"]
