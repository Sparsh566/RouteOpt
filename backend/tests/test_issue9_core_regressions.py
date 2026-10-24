"""
Core Invariant Regression Tests (Issue #9 / #36):
1. Vans are never banned (exempt from municipal peak-hour no-entry regulations).
2. Trucks arriving at restricted stops during peak ban hours are rejected.
3. Google OR-Tools and Greedy fallback agree on operational and regulatory feasibility.
"""

import pytest

from backend.app.models.fleet_v2 import (
    CommercialVehicleSpec,
    DeliveryStop,
    DepotLocation,
    TimeWindowMode,
    VehicleClass,
)
from backend.app.services.cvrptw_solver import ORTOOLS_AVAILABLE, CVRPTWSolver
from backend.app.services.validator import RouteValidator


@pytest.fixture
def depot() -> DepotLocation:
    return DepotLocation(
        depot_id="DEPOT-MUMBAI",
        name="Bhiwandi Central Hub",
        lat=19.2967,
        lon=73.0631,
        operating_hours_sec=50400  # 14-hour operating horizon (08:00 to 22:00)
    )


@pytest.fixture
def van() -> CommercialVehicleSpec:
    return CommercialVehicleSpec(
        vehicle_id="VAN-01",
        name="Tata Ace Gold",
        vehicle_class=VehicleClass.DELIVERY_VAN,
        gross_vehicle_weight_tonnes=2.1,
        height_meters=1.85,
        payload_capacity_kg=1000.0,
        fixed_dispatch_cost=250.0,
        running_cost_per_km=12.0
    )


@pytest.fixture
def truck() -> CommercialVehicleSpec:
    return CommercialVehicleSpec(
        vehicle_id="TRUCK-01",
        name="Tata 407 Freight",
        vehicle_class=VehicleClass.FREIGHT_TRUCK,
        gross_vehicle_weight_tonnes=7.5,
        height_meters=3.1,
        payload_capacity_kg=4000.0,
        fixed_dispatch_cost=600.0,
        running_cost_per_km=22.0
    )


def test_vans_never_banned_during_morning_and_evening_peaks(depot, van):
    """
    Delivery vans (LCV < 3.5T) are legally exempt from municipal truck bans.
    Verify they are NEVER rejected or penalized when serving restricted urban stops
    during morning peak (08:00 - 11:30 AM) and evening peak (05:00 - 09:30 PM).
    """
    matrix = [[0.0, 1000.0, 1000.0], [1000.0, 0.0, 1000.0], [1000.0, 1000.0, 0.0]]
    durations = [[0.0, 300.0, 300.0], [300.0, 0.0, 300.0], [300.0, 300.0, 0.0]]

    # Stop 1 in morning peak (09:00 - 10:30 AM)
    stop_morning = DeliveryStop(
        stop_id="STOP-PEAK-AM",
        name="Colaba Morning Mart",
        lat=18.92,
        lon=72.83,
        demand_kg=200.0,
        time_window_start_sec=32400,  # 09:00 AM (inside 08:00 - 11:30 morning ban)
        time_window_end_sec=37800,    # 10:30 AM
        is_in_restricted_urban_core=True,
        window_mode=TimeWindowMode.ABSOLUTE
    )

    # Stop 2 in evening peak (18:00 - 20:00 PM)
    stop_evening = DeliveryStop(
        stop_id="STOP-PEAK-PM",
        name="Nariman Point Evening Express",
        lat=18.93,
        lon=72.82,
        demand_kg=200.0,
        time_window_start_sec=64800,  # 18:00 PM (inside 17:00 - 21:30 evening ban)
        time_window_end_sec=72000,    # 20:00 PM
        is_in_restricted_urban_core=True,
        window_mode=TimeWindowMode.ABSOLUTE
    )

    stops = [stop_morning, stop_evening]

    # 1. Verify Solver Feasibility
    solver = CVRPTWSolver(
        distance_matrix=matrix,
        duration_matrix=durations,
        depot=depot,
        stops=stops,
        fleet=[van],
        departure_time_sec=28800,  # 08:00 AM departure
        region="MUMBAI_MMRDA",
        enforce_guidelines=True
    )

    # Van serving stop 1 at 09:00 AM (32400s) during morning peak ban
    is_feasible_morning, _, _ = solver.check_stop_feasibility(
        vehicle=van,
        stop_idx=1,
        current_node=0,
        current_time_sec=32100.0,
        current_load_kg=0.0,
        penalty=1.0
    )
    assert is_feasible_morning is True, "Van must be feasible during morning peak"

    # Van serving stop 2 at 18:00 PM (64800s) during evening peak ban
    is_feasible_evening, _, _ = solver.check_stop_feasibility(
        vehicle=van,
        stop_idx=2,
        current_node=0,
        current_time_sec=64500.0,
        current_load_kg=0.0,
        penalty=1.0
    )
    assert is_feasible_evening is True, "Van must be feasible during evening peak"

    # 2. Verify RouteValidator confirms complete compliance with 0 violations
    validator = RouteValidator(
        depot=depot,
        stops=stops,
        fleet=[van],
        distance_matrix=matrix,
        duration_matrix=durations,
        departure_time_sec=28800,
        region="MUMBAI_MMRDA",
        enforce_guidelines=True
    )

    routes = [{
        "vehicle_id": "VAN-01",
        "schedule": [
            {"node_index": 0, "arrival_time_sec": 28800.0, "load_kg": 0.0},
            {"node_index": 1, "arrival_time_sec": 32400.0, "load_kg": 200.0},
            {"node_index": 2, "arrival_time_sec": 64800.0, "load_kg": 400.0},
            {"node_index": 0, "arrival_time_sec": 66000.0, "load_kg": 0.0}
        ]
    }]

    report = validator.validate(routes=routes, dropped_stops=[])
    assert report["is_valid"] is True
    assert len(report["errors"]) == 0


def test_truck_arriving_in_peak_ban_window_is_rejected(depot, truck):
    """
    Heavy trucks (MCV/HCV >= 3.5T) are prohibited from entering restricted cores during peak windows.
    Verify that an arrival inside morning or evening peak is strictly rejected by both solver and validator.
    """
    matrix = [[0.0, 1000.0], [1000.0, 0.0]]
    durations = [[0.0, 300.0], [300.0, 0.0]]

    stop = DeliveryStop(
        stop_id="STOP-RESTRICTED",
        name="South Mumbai Core Retailer",
        lat=18.95,
        lon=72.83,
        demand_kg=500.0,
        time_window_start_sec=28800,  # 08:00 AM (start of morning ban)
        time_window_end_sec=41400,    # 11:30 AM (end of morning ban)
        is_in_restricted_urban_core=True,
        window_mode=TimeWindowMode.ABSOLUTE
    )

    solver = CVRPTWSolver(
        distance_matrix=matrix,
        duration_matrix=durations,
        depot=depot,
        stops=[stop],
        fleet=[truck],
        departure_time_sec=28800,
        region="MUMBAI_MMRDA",
        enforce_guidelines=True
    )

    # Check solver feasibility check at 08:30 AM (30600s) - inside morning ban
    is_feasible, _, _ = solver.check_stop_feasibility(
        vehicle=truck,
        stop_idx=1,
        current_node=0,
        current_time_sec=30300.0,
        current_load_kg=0.0,
        penalty=1.30
    )
    assert is_feasible is False, "Truck arrival inside morning peak ban must be rejected"

    # Check solver feasibility check at 18:00 PM (64800s) - inside evening ban
    is_feasible_pm, _, _ = solver.check_stop_feasibility(
        vehicle=truck,
        stop_idx=1,
        current_node=0,
        current_time_sec=64500.0,
        current_load_kg=0.0,
        penalty=1.30
    )
    assert is_feasible_pm is False, "Truck arrival inside evening peak ban must be rejected"

    # Verify RouteValidator flags TRUCK_PEAK_BAN_VIOLATION
    validator = RouteValidator(
        depot=depot,
        stops=[stop],
        fleet=[truck],
        distance_matrix=matrix,
        duration_matrix=durations,
        departure_time_sec=28800,
        region="MUMBAI_MMRDA",
        enforce_guidelines=True
    )

    violating_route = [{
        "vehicle_id": "TRUCK-01",
        "schedule": [
            {"node_index": 0, "arrival_time_sec": 28800.0, "load_kg": 0.0},
            {"node_index": 1, "arrival_time_sec": 30600.0, "load_kg": 500.0},
            {"node_index": 0, "arrival_time_sec": 32000.0, "load_kg": 0.0}
        ]
    }]

    report = validator.validate(routes=violating_route, dropped_stops=[])
    assert report["is_valid"] is False
    ban_errors = [e for e in report["errors"] if e["code"] == "TRUCK_PEAK_BAN_VIOLATION"]
    assert len(ban_errors) == 1
    assert ban_errors[0]["stop_id"] == "STOP-RESTRICTED"


def test_ortools_and_greedy_agree_on_feasibility_matrix(depot, van, truck):
    """
    Test systematic agreement between OR-Tools and Greedy fallback on multiple constraint types:
    1. Peak ban constraint: Van is feasible, truck is infeasible.
    2. Flyover height limit: Van (1.85m) passes, truck (3.1m) exceeds gantry (2.5m).
    3. Bridge GVW limit: Van (2.1T) passes, truck (7.5T) exceeds bridge rating (5.0T).
    """
    matrix = [[0.0, 1000.0], [1000.0, 0.0]]
    durations = [[0.0, 300.0], [300.0, 0.0]]

    # Scenario 1: Peak Ban Stop
    stop_ban = DeliveryStop(
        stop_id="S-BAN",
        name="Peak Ban Stop",
        lat=19.0,
        lon=72.85,
        time_window_start_sec=30600,
        time_window_end_sec=36000,
        is_in_restricted_urban_core=True,
        window_mode=TimeWindowMode.ABSOLUTE
    )

    # Scenario 2: Flyover Height Stop
    stop_height = DeliveryStop(
        stop_id="S-HEIGHT",
        name="Flyover Overpass Stop",
        lat=19.1,
        lon=72.85,
        requires_flyover=True,  # 2.5m limit
        time_window_start_sec=43200,
        time_window_end_sec=46800,
        window_mode=TimeWindowMode.ABSOLUTE
    )

    # Scenario 3: Bridge Weight Limit Stop
    stop_weight = DeliveryStop(
        stop_id="S-WEIGHT",
        name="Old Bridge Stop",
        lat=19.15,
        lon=72.85,
        max_access_gvw_tonnes=5.0,  # 5T limit
        time_window_start_sec=43200,
        time_window_end_sec=46800,
        window_mode=TimeWindowMode.ABSOLUTE
    )

    # 1. Peak ban
    solver_ban = CVRPTWSolver(
        distance_matrix=matrix,
        duration_matrix=durations,
        depot=depot,
        stops=[stop_ban],
        fleet=[van, truck],
        departure_time_sec=28800,
        enforce_guidelines=True
    )
    assert solver_ban.check_stop_feasibility(van, 1, 0, 30300.0, 0.0, 1.0)[0] is True
    assert solver_ban.check_stop_feasibility(truck, 1, 0, 30300.0, 0.0, 1.30)[0] is False

    # 2. Height gantry
    solver_height = CVRPTWSolver(
        distance_matrix=matrix,
        duration_matrix=durations,
        depot=depot,
        stops=[stop_height],
        fleet=[van, truck],
        departure_time_sec=28800,
        enforce_guidelines=True
    )
    assert solver_height.check_stop_feasibility(van, 1, 0, 42900.0, 0.0, 1.0)[0] is True
    assert solver_height.check_stop_feasibility(truck, 1, 0, 42900.0, 0.0, 1.30)[0] is False

    # 3. Bridge GVW
    solver_weight = CVRPTWSolver(
        distance_matrix=matrix,
        duration_matrix=durations,
        depot=depot,
        stops=[stop_weight],
        fleet=[van, truck],
        departure_time_sec=28800,
        enforce_guidelines=True
    )
    assert solver_weight.check_stop_feasibility(van, 1, 0, 42900.0, 0.0, 1.0)[0] is True
    assert solver_weight.check_stop_feasibility(truck, 1, 0, 42900.0, 0.0, 1.30)[0] is False

    # Check solver end-to-end when only truck is available on peak ban stop:
    # Both OR-Tools and Greedy fallback agree that the stop must be dropped.
    solver_truck_only = CVRPTWSolver(
        distance_matrix=matrix,
        duration_matrix=durations,
        depot=depot,
        stops=[stop_ban],
        fleet=[truck],
        departure_time_sec=28800,
        enforce_guidelines=True
    )

    greedy_res = solver_truck_only._solve_greedy_fallback()
    assert "S-BAN" in greedy_res["dropped_stops"]

    if ORTOOLS_AVAILABLE:
        ortools_res = solver_truck_only._solve_ortools()
        if ortools_res is not None:
            assert "S-BAN" in ortools_res["dropped_stops"]
