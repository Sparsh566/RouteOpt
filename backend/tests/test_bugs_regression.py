"""
Bug Reproduction & Regression Test Suite (B1 - B9)
These tests reproduce known bugs first, and verify fixes once applied.
"""

import pytest
from datetime import datetime
from backend.app.services.cvrptw_solver import CVRPTWSolver
from backend.app.models.fleet_v2 import CommercialVehicleSpec, VehicleClass, DeliveryStop, DepotLocation
from backend.app.controllers.optimize import optimize_fleet_routes
from backend.app.models.fleet_v2 import OptimizeV2Request
from backend.app.services.traffic_engine import TrafficEngine

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

# Mock 2-node distance/duration matrix:
# Node 0 (depot), Node 1 (stop)
# Base distance: 24000m (24km), base duration: 2879.4s (~48 min)
DIST_MATRIX = [
    [0.0, 24000.0],
    [24000.0, 0.0]
]
DUR_MATRIX = [
    [0.0, 2879.4],
    [2879.4, 0.0]
]

def test_b1_truck_ban_applied_to_vans(depot, van, truck):
    """
    B1: Repro fleet [truck, van], one stop flagged is_in_restricted_urban_core with
    its time window entirely inside 28800-41400 (08:00 - 11:30 AM).
    Expected: Van serves it. Solver must NOT return None or drop it when a van is available.
    """
    stop = DeliveryStop(
        stop_id="S1",
        name="Urban Core Stop",
        lat=19.1726,
        lon=72.9565,
        demand_kg=200,
        time_window_start_sec=28800,
        time_window_end_sec=41400,
        service_duration_sec=300,
        is_in_restricted_urban_core=True
    )
    solver = CVRPTWSolver(
        distance_matrix=DIST_MATRIX,
        duration_matrix=DUR_MATRIX,
        depot=depot,
        stops=[stop],
        fleet=[truck, van],  # Fleet contains truck first, then van
        enforce_guidelines=True
    )
    solution = solver.solve()
    assert solution is not None, "Solver returned None because RemoveInterval hit the van!"
    # Van must serve the stop, not dropped
    assert "S1" not in solution["dropped_stops"], "Van was exempt but stop S1 was dropped!"
    # Find which vehicle served S1
    serving_vehicles = [
        r["vehicle_id"] for r in solution["routes"]
        if any(item["node_index"] == 1 for item in r["schedule"])
    ]
    assert serving_vehicles == ["VAN-01"], f"Expected VAN-01 to serve S1, but got {serving_vehicles}"

def test_b2_vehicle_specific_travel_time(depot, van, truck):
    """
    B2: Vehicle-specific travel time ignored.
    Repro: Single stop, truck alone arrives at 3743s (2879.4 * 1.30 = 3743s),
    but the same truck in fleet [van, truck] arrives at 2879s if transit_callback_indices[0] is used.
    """
    stop = DeliveryStop(
        stop_id="S1",
        name="Stop 1",
        lat=19.1726,
        lon=72.9565,
        demand_kg=200,
        time_window_start_sec=0,
        time_window_end_sec=50000,
        service_duration_sec=0
    )
    # 1. Truck alone
    solver_truck_alone = CVRPTWSolver(
        distance_matrix=DIST_MATRIX,
        duration_matrix=DUR_MATRIX,
        depot=depot,
        stops=[stop],
        fleet=[truck],
        enforce_guidelines=False
    )
    sol_alone = solver_truck_alone.solve()
    assert sol_alone is not None
    truck_alone_arr = next(
        item["arrival_time_sec"] for r in sol_alone["routes"]
        for item in r["schedule"] if item["node_index"] == 1
    )
    # Expected: round(2879.4 * 1.30) = 3743s
    assert round(truck_alone_arr) == 3743 or round(truck_alone_arr - 30600) == 3743

    # 2. Truck in fleet [van, truck] where van capacity=10kg (so truck must serve the 200kg stop)
    small_van = CommercialVehicleSpec(
        vehicle_id="VAN-01",
        name="Small Van",
        vehicle_class=VehicleClass.DELIVERY_VAN,
        payload_capacity_kg=10,  # Cannot fit 200kg
        gross_vehicle_weight_tonnes=2.0,
        height_meters=1.8
    )
    solver_mixed = CVRPTWSolver(
        distance_matrix=DIST_MATRIX,
        duration_matrix=DUR_MATRIX,
        depot=depot,
        stops=[stop],
        fleet=[small_van, truck],
        enforce_guidelines=False
    )
    sol_mixed = solver_mixed.solve()
    assert sol_mixed is not None
    truck_mixed_route = next(r for r in sol_mixed["routes"] if r["vehicle_id"] == "TRUCK-01")
    truck_mixed_arr = next(
        item["arrival_time_sec"] for item in truck_mixed_route["schedule"]
        if item["node_index"] == 1
    )
    # Must also be ~3743s (with 1.30x penalty), NOT 2879s!
    diff_from_start = truck_mixed_arr if truck_mixed_arr < 20000 else truck_mixed_arr - 30600
    assert round(diff_from_start) == 3743, (
        f"Truck in mixed fleet got arrival diff {diff_from_start} instead of 3743 (1.30x penalty ignored!)"
    )

def test_b3_greedy_fallback_violates_time_window(depot, van):
    """
    B3: Greedy fallback ignores time_window_end.
    Repro: Stop with time_window_end_sec=60 is served at ~2879s and not dropped.
    """
    stop = DeliveryStop(
        stop_id="S1",
        name="Tight Window Stop",
        lat=19.1726,
        lon=72.9565,
        demand_kg=100,
        time_window_start_sec=0,
        time_window_end_sec=60,  # Deadline 60s
        service_duration_sec=300
    )
    solver = CVRPTWSolver(
        distance_matrix=DIST_MATRIX,
        duration_matrix=DUR_MATRIX,
        depot=depot,
        stops=[stop],
        fleet=[van],
        enforce_guidelines=False
    )
    # Force greedy fallback
    sol = solver._solve_greedy_fallback()
    assert "S1" in sol["dropped_stops"], (
        f"Greedy solver should have dropped S1 because arrival (~2879s) violates deadline (60s), but got routes: {sol['routes']}"
    )

@pytest.mark.asyncio
async def test_b4_optimize_clock_time_and_departure_iso(depot, van):
    """
    B4: optimize.py hardcodes clock time to 08:30, ignores departure_time_iso,
    and crashes on float arrival times.
    """
    # 1. Float arrival formatting crash check
    stop = DeliveryStop(
        stop_id="S1",
        name="Stop 1",
        lat=19.1726,
        lon=72.9565,
        demand_kg=100,
        time_window_start_sec=0,
        time_window_end_sec=50000
    )
    req = OptimizeV2Request(
        depot=depot,
        stops=[stop],
        fleet=[van],
        departure_time_iso="2026-10-09T14:15:00+05:30",  # Afternoon departure
        apply_traffic_congestion=False,
        enforce_government_guidelines=False
    )
    res = await optimize_fleet_routes(req)
    # Check that clock time reflects 14:15 departure, not 08:30
    depot_clock = res.routes[0].stops_visited[0].clock_time_str
    assert "14:15" in depot_clock, f"Expected 14:15 departure time, but got {depot_clock}"

@pytest.mark.asyncio
async def test_b6_traffic_factor_applied_accuracy(depot, van):
    """
    B6: traffic_factor_applied is hardcoded to 1.65 even when departure is nighttime (factor 1.0)
    or evening (factor 1.85).
    """
    stop = DeliveryStop(
        stop_id="S1",
        name="Stop 1",
        lat=19.1726,
        lon=72.9565,
        demand_kg=100
    )
    # Nighttime departure at 02:00 AM -> TrafficEngine gives 1.00
    req = OptimizeV2Request(
        depot=depot,
        stops=[stop],
        fleet=[van],
        departure_time_iso="2026-10-09T02:00:00+05:30",
        apply_traffic_congestion=True
    )
    res = await optimize_fleet_routes(req)
    assert res.traffic_factor_applied == 1.0, (
        f"Expected traffic factor 1.0 for 02:00 AM departure, but got {res.traffic_factor_applied}"
    )

def test_b7_cost_model_consistency(depot):
    """
    B7: Solver objective vs reported cost mismatch.
    When two vehicles have same capacity and fixed cost, but vehicle A has running_cost_per_km=10
    and vehicle B has running_cost_per_km=50, the solver should choose vehicle A to minimize cost.
    Currently, the solver only minimizes raw distance (meters), treating both vehicles identically.
    """
    v_cheap = CommercialVehicleSpec(
        vehicle_id="VAN-CHEAP",
        name="Cheap Van",
        vehicle_class=VehicleClass.DELIVERY_VAN,
        payload_capacity_kg=1000,
        fixed_dispatch_cost=200.0,
        running_cost_per_km=10.0
    )
    v_expensive = CommercialVehicleSpec(
        vehicle_id="VAN-EXPENSIVE",
        name="Expensive Van",
        vehicle_class=VehicleClass.DELIVERY_VAN,
        payload_capacity_kg=1000,
        fixed_dispatch_cost=200.0,
        running_cost_per_km=50.0
    )
    stop = DeliveryStop(
        stop_id="S1",
        name="Stop 1",
        lat=19.1726,
        lon=72.9565,
        demand_kg=200
    )
    solver = CVRPTWSolver(
        distance_matrix=DIST_MATRIX,
        duration_matrix=DUR_MATRIX,
        depot=depot,
        stops=[stop],
        fleet=[v_expensive, v_cheap],  # Expensive vehicle is first in list
        enforce_guidelines=False
    )
    sol = solver.solve()
    assert sol is not None
    used_v = [r["vehicle_id"] for r in sol["routes"] if r["utilized"]]
    assert used_v == ["VAN-CHEAP"], f"Expected solver to choose VAN-CHEAP to minimize total cost, but chose {used_v}"

def test_b8_structural_access_enforcement(depot, truck):
    """
    B8: Flyover clearance and Bridge GVW rules must be enforced by solver when requested.
    If a stop requires flyover access (2.5m limit) and the fleet only has a 3.1m truck,
    the truck cannot serve the stop and it must be dropped.
    """
    stop = DeliveryStop(
        stop_id="S1",
        name="Flyover Stop",
        lat=19.1726,
        lon=72.9565,
        demand_kg=200,
        requires_flyover=True  # 2.5m clearance required
    )
    solver = CVRPTWSolver(
        distance_matrix=DIST_MATRIX,
        duration_matrix=DUR_MATRIX,
        depot=depot,
        stops=[stop],
        fleet=[truck],  # 3.1m height exceeds 2.5m
        enforce_guidelines=True
    )
    sol = solver.solve()
    assert sol is not None
    assert "S1" in sol["dropped_stops"], "Truck exceeding flyover clearance served the stop instead of dropping it!"

