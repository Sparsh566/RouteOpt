"""
Tests for Issue #5:
Shared peak-hour truck ban rule and solver agreement on feasibility between OR-Tools and Greedy fallback.
"""

from backend.app.models.fleet_v2 import CommercialVehicleSpec, DeliveryStop, DepotLocation, VehicleClass
from backend.app.services.cvrptw_solver import CVRPTWSolver
from backend.app.services.regulation_engine import RegionalRegulationEngine


def test_shared_ban_function_peak_windows():
    """Verify is_peak_ban_active correctly identifies ban and unrestricted windows."""
    engine = RegionalRegulationEngine("MUMBAI_MMRDA")

    # Mumbai morning ban: 08:00 - 11:00 (28800s - 39600s)
    assert not engine.is_peak_ban_active(28799)   # 07:59:59 AM (unrestricted)
    assert engine.is_peak_ban_active(28800)       # 08:00:00 AM (banned)
    assert engine.is_peak_ban_active(36000)       # 10:00:00 AM (banned)
    assert engine.is_peak_ban_active(39600)       # 11:00:00 AM (banned boundary)
    assert not engine.is_peak_ban_active(39601)   # 11:00:01 AM (unrestricted)

    # Mumbai evening ban: 17:00 - 21:00 (61200s - 75600s)
    assert not engine.is_peak_ban_active(61199)   # 04:59:59 PM (unrestricted)
    assert engine.is_peak_ban_active(61200)       # 05:00:00 PM (banned)
    assert engine.is_peak_ban_active(75600)       # 09:00:00 PM (banned boundary)
    assert not engine.is_peak_ban_active(75601)   # 09:00:01 PM (unrestricted)


def test_ortools_and_greedy_agree_on_service_overlapping_ban():
    """
    Verify OR-Tools and Greedy fallback agree when truck arrives BEFORE ban window (e.g. 07:50 AM)
    even if service duration extends past 08:00 AM.
    Both must consider arrival feasible under the shared ban rule.
    """
    depot = DepotLocation(depot_id="DEPOT-01", name="Central Depot", lat=19.076, lon=72.877, operating_hours_sec=36000)
    # Stop opening at 07:45 AM (27900) to 07:55 AM (28500), service takes 900s (15 min, ending at 08:10 AM into ban)
    stop = DeliveryStop(
        stop_id="STOP-01",
        name="South Mumbai Core Shop",
        lat=19.078,
        lon=72.879,
        demand_kg=500.0,
        time_window_start_sec=27900,  # 07:45 AM
        time_window_end_sec=28500,    # 07:55 AM
        service_duration_sec=900,     # 15 minutes
        is_in_restricted_urban_core=True
    )

    truck = CommercialVehicleSpec(
        vehicle_id="TRUCK-01",
        name="Tata 407",
        vehicle_class=VehicleClass.FREIGHT_TRUCK,
        payload_capacity_kg=4000.0,
        gross_vehicle_weight_tonnes=7.5,
        height_meters=2.4,
        fixed_dispatch_cost=1200.0,
        running_cost_per_km=24.0
    )

    dist_matrix = [[0.0, 1000.0], [1000.0, 0.0]]
    dur_matrix = [[0.0, 300.0], [300.0, 0.0]]

    # Departure at 07:40 AM (27600s) -> arrival at stop is 27600 + 390 = 27990s (07:46:30 AM), before 08:00 AM
    solver = CVRPTWSolver(
        distance_matrix=dist_matrix,
        duration_matrix=dur_matrix,
        depot=depot,
        stops=[stop],
        fleet=[truck],
        enforce_guidelines=True,
        departure_time_sec=27600,
        region="MUMBAI_MMRDA"
    )

    # 1. Check greedy feasibility directly
    is_feasible_greedy, arrival_sec, _ = solver.check_stop_feasibility(
        vehicle=truck,
        stop_idx=1,
        current_node=0,
        current_time_sec=27600,
        current_load_kg=0.0,
        penalty=1.30
    )
    assert is_feasible_greedy is True
    assert arrival_sec < 28800  # Arrives before 08:00 AM morning ban

    # 2. Check full greedy fallback
    sol_greedy = solver._solve_greedy_fallback()
    assert len(sol_greedy["dropped_stops"]) == 0
    assert sol_greedy["routes"][0]["utilized"] is True

    # 3. Check OR-Tools solver
    sol_ortools = solver.solve()
    assert sol_ortools is not None
    assert len(sol_ortools["dropped_stops"]) == 0
    assert sol_ortools["routes"][0]["utilized"] is True


def test_ortools_and_greedy_agree_on_banned_arrival():
    """Verify both solvers reject a truck when arrival falls inside the ban window."""
    depot = DepotLocation(depot_id="DEPOT-01", name="Central Depot", lat=19.076, lon=72.877, operating_hours_sec=36000)
    # Stop window inside morning peak ban (09:00 - 10:00 AM, 32400 - 36000)
    stop = DeliveryStop(
        stop_id="STOP-BANNED",
        name="Downtown Shop",
        lat=19.078,
        lon=72.879,
        demand_kg=500.0,
        time_window_start_sec=32400,
        time_window_end_sec=36000,
        service_duration_sec=300,
        is_in_restricted_urban_core=True
    )

    truck = CommercialVehicleSpec(
        vehicle_id="TRUCK-01",
        name="Tata 407",
        vehicle_class=VehicleClass.FREIGHT_TRUCK,
        payload_capacity_kg=4000.0,
        gross_vehicle_weight_tonnes=7.5,
        height_meters=2.4,
        fixed_dispatch_cost=1200.0,
        running_cost_per_km=24.0
    )

    dist_matrix = [[0.0, 1000.0], [1000.0, 0.0]]
    dur_matrix = [[0.0, 300.0], [300.0, 0.0]]

    # Departure at 08:30 AM (30600s) -> arrival during peak ban
    solver = CVRPTWSolver(
        distance_matrix=dist_matrix,
        duration_matrix=dur_matrix,
        depot=depot,
        stops=[stop],
        fleet=[truck],
        enforce_guidelines=True,
        departure_time_sec=30600,
        region="MUMBAI_MMRDA"
    )

    # Greedy feasibility
    is_feasible_greedy, _, _ = solver.check_stop_feasibility(
        vehicle=truck,
        stop_idx=1,
        current_node=0,
        current_time_sec=30600,
        current_load_kg=0.0,
        penalty=1.30
    )
    assert is_feasible_greedy is False

    # Greedy fallback drops stop
    sol_greedy = solver._solve_greedy_fallback()
    assert "STOP-BANNED" in sol_greedy["dropped_stops"]

    # OR-Tools drops stop
    sol_ortools = solver.solve()
    assert sol_ortools is not None
    assert "STOP-BANNED" in sol_ortools["dropped_stops"]
