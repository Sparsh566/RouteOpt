import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "OK"}

def test_optimize_endpoint_success():
    payload = {
        "depot": [18.5204, 73.8567],
        "stops": [
            [18.5304, 73.8667],
            [18.5404, 73.8767]
        ]
    }
    response = client.post("/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "order" in data
    assert "distance_m" in data
    assert "duration_s" in data
    assert "polyline" in data
    # The order must start and end at depot index 0, and visit stop indices (1 and 2)
    assert data["order"][0] == 0
    assert data["order"][-1] == 0
    assert len(data["order"]) == 4  # depot -> stopA -> stopB -> depot

def test_optimize_invalid_depot():
    # depot must have exactly 2 elements
    payload = {
        "depot": [18.5204],
        "stops": [[18.5304, 73.8667]]
    }
    response = client.post("/optimize", json=payload)
    assert response.status_code == 422  # validation error

def test_optimize_no_stops():
    # stops must have at least 1 item
    payload = {
        "depot": [18.5204, 73.8567],
        "stops": []
    }
    response = client.post("/optimize", json=payload)
    assert response.status_code == 422  # validation error
