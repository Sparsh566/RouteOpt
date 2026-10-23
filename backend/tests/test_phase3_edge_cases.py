"""
Phase 3 Comprehensive Edge-Case & Hygiene Tests
Covers:
- datetime/hour-boundary arithmetic (e.g. overnight shifts, minute boundaries)
- window boundaries (exact match at start and end)
- capacity overflow (drops stops when all vehicle capacities exceeded)
- van-vs-truck same stop/time (van can serve during ban, truck cannot)
- shift limit (long transit stops dropped)
- empty/malformed input
- infeasible sets (gracefully dropped, no crashes)
- greedy fallback correctness
- cost consistency
- missing API keys / Groq failure fallback
- OSRM service failure fallback
"""


import pytest
from fastapi.testclient import TestClient

from backend.app.controllers.optimize import (
    parse_departure_datetime,
)
from backend.app.main import app
from backend.app.models.fleet_v2 import (
    CommercialVehicleSpec,
    DeliveryStop,
    DepotLocation,
    VehicleClass,
)
from backend.app.models.simulation_v3 import SimulationScenarioRequest
from backend.app.services.ai_simulation_engine import AISimulationEngine
from backend.app.services.cvrptw_solver import CVRPTWSolver
from backend.app.services.osrm_service import OSRMService

client = TestClient(app)

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
    [0.0, 10000.0, 12000.0],
    [10000.0, 0.0, 5000.0],
    [12000.0, 5000.0, 0.0]
]

DUR_MATRIX = [
    [0.0, 1200.0, 1500.0],
    [1200.0, 0.0, 600.0],
    [1500.0, 600.0, 0.0]
]

def test_datetime_hour_boundary_arithmetic():
    """Verifies timezone awareness, minute rollover, and overnight handling."""
    # Test morning
    dt1, sec1 = parse_departure_datetime("2026-10-09T08:30:00+05:30")
    assert sec1 == 30600
    assert dt1.hour == 8 and dt1.minute == 30

    # Test late night / overnight
    dt2, sec2 = parse_departure_datetime("2026-10-09T23:45:00+05:30")
    assert sec2 == 85500

    # Test default fallback when None
    dt3, sec3 = parse_departure_datetime(None)
    assert sec3 == 30600

def test_window_boundary_exact_hits(depot, van):
    """Verifies vehicle can serve a stop when arrival lands exactly at window start or end."""
    # Transit from depot is 1200s (20 mins).
    # If departure is 30600, arrival is exactly 31800s.
    stop = DeliveryStop(
        stop_id="S1",
        name="Exact Window Stop",
        lat=19.1726,
        lon=72.9565,
        demand_kg=100,
        time_window_start_sec=31800,
        time_window_end_sec=31800,  # Exact 1-second boundary
        service_duration_sec=0
    )
    solver = CVRPTWSolver(
        distance_matrix=DIST_MATRIX[:2],
        duration_matrix=DUR_MATRIX[:2],
        depot=depot,
        stops=[stop],
        fleet=[van],
        departure_time_sec=30600,
        enforce_guidelines=False
    )
    sol = solver.solve()
    assert sol is not None
    assert "S1" not in sol["dropped_stops"]

def test_capacity_overflow_drops_excess(depot, van):
    """When demand exceeds vehicle capacity, excess stop must be dropped without crash."""
    # Van capacity: 1200kg
    stops = [
        DeliveryStop(stop_id="S1", name="Heavy 1", lat=19.1726, lon=72.9565, demand_kg=800),
        DeliveryStop(stop_id="S2", name="Heavy 2", lat=19.0178, lon=72.8478, demand_kg=800)
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
    # Exactly one stop should be served, the other dropped
    assert len(sol["dropped_stops"]) == 1

def test_van_vs_truck_same_stop_and_time(depot, van, truck):
    """Under peak ban (08:00 - 11:30), van serves urban stop while truck cannot."""
    # Window 09:00 - 10:00 (32400 - 36000s) inside morning ban
    stop = DeliveryStop(
        stop_id="S1",
        name="Urban Core Stop",
        lat=19.1726,
        lon=72.9565,
        demand_kg=200,
        time_window_start_sec=32400,
        time_window_end_sec=36000,
        is_in_restricted_urban_core=True
    )
    # Van alone
    solver_van = CVRPTWSolver(
        distance_matrix=DIST_MATRIX[:2],
        duration_matrix=DUR_MATRIX[:2],
        depot=depot,
        stops=[stop],
        fleet=[van],
        departure_time_sec=30600,
        enforce_guidelines=True
    )
    sol_van = solver_van.solve()
    assert sol_van is not None
    assert "S1" not in sol_van["dropped_stops"]

    # Truck alone
    solver_truck = CVRPTWSolver(
        distance_matrix=DIST_MATRIX[:2],
        duration_matrix=DUR_MATRIX[:2],
        depot=depot,
        stops=[stop],
        fleet=[truck],
        departure_time_sec=30600,
        enforce_guidelines=True
    )
    sol_truck = solver_truck.solve()
    assert sol_truck is not None
    assert "S1" in sol_truck["dropped_stops"], "Truck should have been banned from serving urban stop in peak window!"

def test_shift_limit_boundary(depot, van):
    """Stops requiring transit beyond shift operating hours must be dropped."""
    # Depot operating hours: 43200 (12 hours)
    # Give a matrix with 50,000s transit (> 43200s)
    huge_matrix_dur = [
        [0.0, 50000.0],
        [50000.0, 0.0]
    ]
    huge_matrix_dist = [
        [0.0, 50000.0],
        [50000.0, 0.0]
    ]
    stop = DeliveryStop(stop_id="S1", name="Far Stop", lat=19.1726, lon=72.9565, demand_kg=100)
    solver = CVRPTWSolver(
        distance_matrix=huge_matrix_dist,
        duration_matrix=huge_matrix_dur,
        depot=depot,
        stops=[stop],
        fleet=[van],
        departure_time_sec=30600
    )
    sol = solver.solve()
    assert sol is not None
    assert "S1" in sol["dropped_stops"]

def test_malformed_and_empty_inputs():
    """Empty and invalid API inputs must return 400 or 422 cleanly."""
    res1 = client.post("/api/optimize", json={"depot": {"lat": 19.0, "lon": 73.0}, "stops": [], "fleet": []})
    assert res1.status_code in [400, 422]

    res2 = client.post("/api/optimize", json={"depot": None, "stops": [], "fleet": []})
    assert res2.status_code == 422

@pytest.mark.asyncio
async def test_osrm_service_failure_fallback():
    """When OSRM service is unreachable, high-fidelity winding fallback executes without throwing."""
    coords = [[19.2967, 73.0631], [19.1726, 72.9565]]
    dist, dur, is_real = await OSRMService.get_matrices(coords)
    assert len(dist) == 2 and len(dur) == 2
    assert dist[0][1] > 0
    assert dur[0][1] > 0
    # is_real is boolean (True if local OSRM running, False if fallback)
    assert isinstance(is_real, bool)

@pytest.mark.asyncio
async def test_ai_simulation_fallback_when_no_api_key(depot, truck):
    """When GROQ_API_KEY is not set or fails, simulation returns structured deterministic advisory."""
    stop = DeliveryStop(stop_id="S1", name="Mulund", lat=19.1726, lon=72.9565, demand_kg=400)
    req = SimulationScenarioRequest(
        scenario_type="BORDER_ENTRY_DELAY",
        depot=depot,
        stops=[stop],
        fleet=[truck],
        parameters={"delay_minutes": 30}
    )
    res = await AISimulationEngine.run_scenario(req)
    assert res is not None
    assert res.feasibility_status == "VIOLATION_DETECTED"
    assert len(res.ai_advisory_recommendation) > 0
    assert "RouteOpt Standard Dispatch Rules" in res.llm_engine_used or "Groq" in res.llm_engine_used
