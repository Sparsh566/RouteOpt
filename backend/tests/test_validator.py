"""
Phase 2: Independent Route Validator Test Suite
Verifies that RouteValidator catches valid solutions, partial solutions,
and detects deliberately invalid routes with structured error codes.
"""

import pytest

from backend.app.models.fleet_v2 import (
    CommercialVehicleSpec,
    DeliveryStop,
    DepotLocation,
    VehicleClass,
)
from backend.app.services.cvrptw_solver import CVRPTWSolver
from backend.app.services.validator import RouteValidator


@pytest.fixture
def depot():
    return DepotLocation(
        depot_id="DEPOT-01",
        name="Bhiwandi Hub",
        lat=19.2967,
        lon=73.0631,
        operating_hours_sec=43200
    )

@pytest.fixture
def van():
    return CommercialVehicleSpec(
        vehicle_id="VAN-01",
        name="Tata Ace",
        vehicle_class=VehicleClass.DELIVERY_VAN,
        payload_capacity_kg=1200,
        gross_vehicle_weight_tonnes=2.2,
        height_meters=1.9,
        fixed_dispatch_cost=250.0,
        running_cost_per_km=12.0
    )

@pytest.fixture
def truck():
    return CommercialVehicleSpec(
        vehicle_id="TRUCK-01",
        name="Tata 407",
        vehicle_class=VehicleClass.FREIGHT_TRUCK,
        payload_capacity_kg=4000,
        gross_vehicle_weight_tonnes=7.5,
        height_meters=3.1,
        fixed_dispatch_cost=600.0,
        running_cost_per_km=22.0
    )

DIST_MATRIX = [
    [0.0, 15000.0, 20000.0],
    [15000.0, 0.0, 10000.0],
    [20000.0, 10000.0, 0.0]
]

DUR_MATRIX = [
    [0.0, 1800.0, 2400.0],
    [1800.0, 0.0, 1200.0],
    [2400.0, 1200.0, 0.0]
]

def test_validator_on_valid_ortools_solution(depot, van):
    stops = [
        DeliveryStop(stop_id="S1", name="Mulund", lat=19.1726, lon=72.9565, demand_kg=200),
        DeliveryStop(stop_id="S2", name="Dadar", lat=19.0178, lon=72.8478, demand_kg=300)
    ]
    solver = CVRPTWSolver(
        distance_matrix=DIST_MATRIX,
        duration_matrix=DUR_MATRIX,
        depot=depot,
        stops=stops,
        fleet=[van],
        departure_time_sec=30600
    )
    sol = solver.solve()
    assert sol is not None

    validator = RouteValidator(
        depot=depot,
        stops=stops,
        fleet=[van],
        distance_matrix=DIST_MATRIX,
        duration_matrix=DUR_MATRIX,
        departure_time_sec=30600
    )
    report = validator.validate(sol["routes"], sol["dropped_stops"])
    assert report["is_valid"] is True
    assert report["status"] == "SUCCESS"
    assert len(report["errors"]) == 0

def test_validator_on_valid_greedy_solution(depot, van):
    stops = [
        DeliveryStop(stop_id="S1", name="Mulund", lat=19.1726, lon=72.9565, demand_kg=200),
        DeliveryStop(stop_id="S2", name="Dadar", lat=19.0178, lon=72.8478, demand_kg=300)
    ]
    solver = CVRPTWSolver(
        distance_matrix=DIST_MATRIX,
        duration_matrix=DUR_MATRIX,
        depot=depot,
        stops=stops,
        fleet=[van],
        departure_time_sec=30600
    )
    sol = solver._solve_greedy_fallback()

    validator = RouteValidator(
        depot=depot,
        stops=stops,
        fleet=[van],
        distance_matrix=DIST_MATRIX,
        duration_matrix=DUR_MATRIX,
        departure_time_sec=30600
    )
    report = validator.validate(sol["routes"], sol["dropped_stops"])
    assert report["is_valid"] is True
    assert report["status"] == "SUCCESS"
    assert len(report["errors"]) == 0

def test_validator_rejects_duplicate_stop(depot, van):
    stops = [
        DeliveryStop(stop_id="S1", name="Mulund", lat=19.1726, lon=72.9565, demand_kg=200)
    ]
    # Deliberately invalid route: node 1 visited twice
    invalid_routes = [{
        "vehicle_id": "VAN-01",
        "schedule": [
            {"node_index": 0, "arrival_time_sec": 30600.0, "load_kg": 0.0},
            {"node_index": 1, "arrival_time_sec": 32400.0, "load_kg": 200.0},
            {"node_index": 1, "arrival_time_sec": 34000.0, "load_kg": 400.0},
            {"node_index": 0, "arrival_time_sec": 36000.0, "load_kg": 0.0}
        ]
    }]
    validator = RouteValidator(
        depot=depot,
        stops=stops,
        fleet=[van],
        distance_matrix=DIST_MATRIX,
        duration_matrix=DUR_MATRIX,
        departure_time_sec=30600
    )
    report = validator.validate(invalid_routes, [])
    assert report["is_valid"] is False
    assert report["status"] == "INFEASIBLE"
    assert any(e["code"] == "DUPLICATE_STOP_SERVED" for e in report["errors"])

def test_validator_rejects_missing_stop(depot, van):
    stops = [
        DeliveryStop(stop_id="S1", name="Mulund", lat=19.1726, lon=72.9565, demand_kg=200),
        DeliveryStop(stop_id="S2", name="Dadar", lat=19.0178, lon=72.8478, demand_kg=300)
    ]
    # S2 is omitted from both routes and dropped_stops
    routes = [{
        "vehicle_id": "VAN-01",
        "schedule": [
            {"node_index": 0, "arrival_time_sec": 30600.0, "load_kg": 0.0},
            {"node_index": 1, "arrival_time_sec": 32400.0, "load_kg": 200.0},
            {"node_index": 0, "arrival_time_sec": 35000.0, "load_kg": 0.0}
        ]
    }]
    validator = RouteValidator(
        depot=depot,
        stops=stops,
        fleet=[van],
        distance_matrix=DIST_MATRIX,
        duration_matrix=DUR_MATRIX,
        departure_time_sec=30600
    )
    report = validator.validate(routes, [])  # S2 missing from dropped_stops
    assert report["is_valid"] is False
    assert report["status"] == "INFEASIBLE"
    assert any(e["code"] == "MISSING_STOP" and e["stop_id"] == "S2" for e in report["errors"])

def test_validator_rejects_capacity_overflow(depot, van):
    # Van max payload is 1200kg
    stops = [
        DeliveryStop(stop_id="S1", name="Heavy Stop 1", lat=19.1726, lon=72.9565, demand_kg=700),
        DeliveryStop(stop_id="S2", name="Heavy Stop 2", lat=19.0178, lon=72.8478, demand_kg=700)
    ]
    # Route loads 1400kg on 1200kg van
    routes = [{
        "vehicle_id": "VAN-01",
        "schedule": [
            {"node_index": 0, "arrival_time_sec": 30600.0, "load_kg": 0.0},
            {"node_index": 1, "arrival_time_sec": 32400.0, "load_kg": 700.0},
            {"node_index": 2, "arrival_time_sec": 34000.0, "load_kg": 1400.0},
            {"node_index": 0, "arrival_time_sec": 37000.0, "load_kg": 0.0}
        ]
    }]
    validator = RouteValidator(
        depot=depot,
        stops=stops,
        fleet=[van],
        distance_matrix=DIST_MATRIX,
        duration_matrix=DUR_MATRIX,
        departure_time_sec=30600
    )
    report = validator.validate(routes, [])
    assert report["is_valid"] is False
    assert any(e["code"] == "VEHICLE_CAPACITY_EXCEEDED" for e in report["errors"])

def test_validator_rejects_time_window_deadline_violation(depot, van):
    stops = [
        DeliveryStop(
            stop_id="S1",
            name="Strict Morning Stop",
            lat=19.1726,
            lon=72.9565,
            demand_kg=100,
            time_window_start_sec=28800,
            time_window_end_sec=32000  # Cutoff at 32000s (~08:53 AM)
        )
    ]
    # Deliberately arrive at 35000s (> 32000s)
    routes = [{
        "vehicle_id": "VAN-01",
        "schedule": [
            {"node_index": 0, "arrival_time_sec": 30600.0, "load_kg": 0.0},
            {"node_index": 1, "arrival_time_sec": 35000.0, "load_kg": 100.0},
            {"node_index": 0, "arrival_time_sec": 37000.0, "load_kg": 0.0}
        ]
    }]
    validator = RouteValidator(
        depot=depot,
        stops=stops,
        fleet=[van],
        distance_matrix=DIST_MATRIX,
        duration_matrix=DUR_MATRIX,
        departure_time_sec=30600
    )
    report = validator.validate(routes, [])
    assert report["is_valid"] is False
    assert any(e["code"] == "TIME_WINDOW_MISSED" for e in report["errors"])

def test_validator_rejects_shift_limit_violation(depot, van):
    # Depot operating hours: 43200s (ends at 30600 + 43200 = 73800s)
    stops = [
        DeliveryStop(stop_id="S1", name="Stop 1", lat=19.1726, lon=72.9565, demand_kg=100)
    ]
    # Return to depot at 75000s (> 73800s)
    routes = [{
        "vehicle_id": "VAN-01",
        "schedule": [
            {"node_index": 0, "arrival_time_sec": 30600.0, "load_kg": 0.0},
            {"node_index": 1, "arrival_time_sec": 40000.0, "load_kg": 100.0},
            {"node_index": 0, "arrival_time_sec": 75000.0, "load_kg": 0.0}
        ]
    }]
    validator = RouteValidator(
        depot=depot,
        stops=stops,
        fleet=[van],
        distance_matrix=DIST_MATRIX,
        duration_matrix=DUR_MATRIX,
        departure_time_sec=30600
    )
    report = validator.validate(routes, [])
    assert report["is_valid"] is False
    assert any(e["code"] == "SHIFT_LIMIT_EXCEEDED" for e in report["errors"])

def test_validator_rejects_truck_peak_ban_violation(depot, truck):
    # Truck serving urban core stop at 34000s (09:26 AM, during 28800-41400 morning peak ban)
    stops = [
        DeliveryStop(
            stop_id="S1",
            name="Urban Core Market",
            lat=19.1726,
            lon=72.9565,
            demand_kg=500,
            is_in_restricted_urban_core=True
        )
    ]
    routes = [{
        "vehicle_id": "TRUCK-01",
        "schedule": [
            {"node_index": 0, "arrival_time_sec": 30600.0, "load_kg": 0.0},
            {"node_index": 1, "arrival_time_sec": 34000.0, "load_kg": 500.0},
            {"node_index": 0, "arrival_time_sec": 37000.0, "load_kg": 0.0}
        ]
    }]
    validator = RouteValidator(
        depot=depot,
        stops=stops,
        fleet=[truck],
        distance_matrix=DIST_MATRIX,
        duration_matrix=DUR_MATRIX,
        departure_time_sec=30600,
        enforce_guidelines=True
    )
    report = validator.validate(routes, [])
    assert report["is_valid"] is False
    assert any(e["code"] == "TRUCK_PEAK_BAN_VIOLATION" for e in report["errors"])

def test_validator_rejects_flyover_height_and_bridge_gvw(depot, truck):
    stops = [
        DeliveryStop(
            stop_id="S1",
            name="Overpass Stop",
            lat=19.1726,
            lon=72.9565,
            demand_kg=500,
            requires_flyover=True,  # 2.5m limit, truck is 3.1m
            max_access_gvw_tonnes=5.0  # 5T limit, truck is 7.5T
        )
    ]
    routes = [{
        "vehicle_id": "TRUCK-01",
        "schedule": [
            {"node_index": 0, "arrival_time_sec": 30600.0, "load_kg": 0.0},
            {"node_index": 1, "arrival_time_sec": 45000.0, "load_kg": 500.0},
            {"node_index": 0, "arrival_time_sec": 48000.0, "load_kg": 0.0}
        ]
    }]
    validator = RouteValidator(
        depot=depot,
        stops=stops,
        fleet=[truck],
        distance_matrix=DIST_MATRIX,
        duration_matrix=DUR_MATRIX,
        departure_time_sec=30600,
        enforce_guidelines=True
    )
    report = validator.validate(routes, [])
    assert report["is_valid"] is False
    codes = [e["code"] for e in report["errors"]]
    assert "FLYOVER_HEIGHT_CLEARANCE_EXCEEDED" in codes
    assert "BRIDGE_GVW_EXCEEDED" in codes
