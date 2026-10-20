import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OK"
    assert "app" in data

def test_optimize_endpoint_success():
    payload = {
        "depot": {
            "depot_id": "DEPOT-01",
            "name": "Bhiwandi Hub",
            "lat": 19.2967,
            "lon": 73.0631
        },
        "stops": [
            {
                "stop_id": "STOP-01",
                "name": "Mulund Drop",
                "lat": 19.1726,
                "lon": 72.9565,
                "demand_kg": 250
            },
            {
                "stop_id": "STOP-02",
                "name": "Dadar Drop",
                "lat": 19.0178,
                "lon": 72.8478,
                "demand_kg": 350
            }
        ],
        "fleet": [
            {
                "vehicle_id": "VAN-01",
                "name": "Tata Ace",
                "vehicle_class": "van",
                "payload_capacity_kg": 1200,
                "gross_vehicle_weight_tonnes": 2.2,
                "height_meters": 1.9
            }
        ]
    }
    response = client.post("/api/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["SUCCESS", "PARTIAL"]
    assert "routes" in data
    assert len(data["routes"]) >= 1
    assert data["total_fleet_distance_km"] > 0

def test_optimize_invalid_depot():
    payload = {
        "depot": "invalid-depot-format",
        "stops": [
            {"stop_id": "S1", "name": "Stop 1", "lat": 19.1726, "lon": 72.9565, "demand_kg": 100}
        ],
        "fleet": [
            {"vehicle_id": "V1", "name": "Van", "vehicle_class": "van", "payload_capacity_kg": 1000}
        ]
    }
    response = client.post("/api/optimize", json=payload)
    assert response.status_code == 422  # validation error

def test_optimize_no_stops():
    payload = {
        "depot": {
            "depot_id": "DEPOT-01",
            "name": "Hub",
            "lat": 19.2967,
            "lon": 73.0631
        },
        "stops": [],
        "fleet": [
            {"vehicle_id": "V1", "name": "Van", "vehicle_class": "van", "payload_capacity_kg": 1000}
        ]
    }
    response = client.post("/api/optimize", json=payload)
    assert response.status_code == 422  # validation error
