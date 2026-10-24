"""
Tests for Issue #7 / #31:
Explicit window_mode field on DeliveryStop to replace relative/absolute guessing heuristic.
"""

import pytest

from backend.app.models.fleet_v2 import (
    CommercialVehicleSpec,
    DeliveryStop,
    DepotLocation,
    TimeWindowMode,
    VehicleClass,
)
from backend.app.services.cvrptw_solver import CVRPTWSolver
from backend.app.services.validator import RouteValidator


def test_delivery_stop_window_mode_defaults_and_validation():
    """Verify default window_mode is AUTO and string inputs deserialize correctly."""
    # Default is AUTO
    stop_default = DeliveryStop(stop_id="S1", name="Stop 1", lat=19.0, lon=72.8)
    assert stop_default.window_mode == TimeWindowMode.AUTO

    # String values accepted
    stop_rel = DeliveryStop(stop_id="S2", name="Stop 2", lat=19.0, lon=72.8, window_mode="relative")
    assert stop_rel.window_mode == TimeWindowMode.RELATIVE

    stop_abs = DeliveryStop(stop_id="S3", name="Stop 3", lat=19.0, lon=72.8, window_mode="absolute")
    assert stop_abs.window_mode == TimeWindowMode.ABSOLUTE


def test_absolute_window_mode_edge_cases():
    """
    Early morning hours (< 14400 seconds since midnight) were previously misclassified
    as relative offsets by the guessing heuristic.
    In ABSOLUTE mode, they must remain exact seconds since midnight.
    """
    departure = 28800  # 08:00 AM
    op_hours = 43200   # 12 hours shift (until 20:00)

    # 01:00 AM to 03:00 AM (3600s - 10800s since midnight)
    stop_early_morning = DeliveryStop(
        stop_id="S_EARLY",
        name="Night Market Delivery",
        lat=19.0,
        lon=72.8,
        time_window_start_sec=3600,
        time_window_end_sec=10800,
        window_mode=TimeWindowMode.ABSOLUTE
    )

    w_start, w_end = stop_early_morning.get_normalized_window(departure, op_hours)
    assert w_start == 3600
    assert w_end == 10800

    # In AUTO mode, the same values would be treated as relative offsets
    stop_auto = DeliveryStop(
        stop_id="S_AUTO",
        name="Auto Guess Delivery",
        lat=19.0,
        lon=72.8,
        time_window_start_sec=3600,
        time_window_end_sec=10800,
        window_mode=TimeWindowMode.AUTO
    )
    w_start_auto, w_end_auto = stop_auto.get_normalized_window(departure, op_hours)
    assert w_start_auto == departure + 3600  # 32400
    assert w_end_auto == departure + 10800    # 39600


def test_relative_window_mode_edge_cases():
    """
    In RELATIVE mode, offsets greater than 14400s (e.g. 5 hours into shift)
    must still be added to departure_time_sec without falling back to absolute mode.
    """
    departure = 28800  # 08:00 AM
    op_hours = 43200   # 12 hours

    # Delivery starting 5 hours (18000s) and ending 7 hours (25200s) into shift
    stop_rel = DeliveryStop(
        stop_id="S_AFTERNOON",
        name="Mid-shift Delivery",
        lat=19.0,
        lon=72.8,
        time_window_start_sec=18000,
        time_window_end_sec=25200,
        window_mode=TimeWindowMode.RELATIVE
    )

    w_start, w_end = stop_rel.get_normalized_window(departure, op_hours)
    assert w_start == departure + 18000  # 46800 (13:00 PM)
    assert w_end == departure + 25200    # 54000 (15:00 PM)

    # In AUTO mode, 18000s > 14400s would be treated as absolute seconds
    stop_auto = DeliveryStop(
        stop_id="S_AUTO",
        name="Auto Fallback Delivery",
        lat=19.0,
        lon=72.8,
        time_window_start_sec=18000,
        time_window_end_sec=25200,
        window_mode=TimeWindowMode.AUTO
    )
    w_start_auto, w_end_auto = stop_auto.get_normalized_window(departure, op_hours)
    assert w_start_auto == 18000
    assert w_end_auto == 25200


def test_auto_backward_compatibility():
    """Verify AUTO mode preserves all existing heuristic rules."""
    departure = 30600  # 08:30 AM
    op_hours = 36000   # 10 hours

    # 1. Start == 0 with full shift duration
    stop_0 = DeliveryStop(
        stop_id="S0",
        name="Default Window",
        lat=19.0,
        lon=72.8,
        time_window_start_sec=0,
        time_window_end_sec=43200
    )
    w0_s, w0_e = stop_0.get_normalized_window(departure, op_hours)
    assert w0_s == departure
    assert w0_e == departure + op_hours

    # 2. Relative offset: start < 14400 and end <= op_hours
    stop_offset = DeliveryStop(
        stop_id="S_OFF",
        name="Offset Window",
        lat=19.0,
        lon=72.8,
        time_window_start_sec=3600,
        time_window_end_sec=7200
    )
    ws, we = stop_offset.get_normalized_window(departure, op_hours)
    assert ws == departure + 3600
    assert we == departure + 7200

    # 3. Absolute seconds: start >= 14400 (e.g. 09:00 AM = 32400)
    stop_abs = DeliveryStop(
        stop_id="S_ABS",
        name="Absolute Window",
        lat=19.0,
        lon=72.8,
        time_window_start_sec=32400,
        time_window_end_sec=36000
    )
    ws, we = stop_abs.get_normalized_window(departure, op_hours)
    assert ws == 32400
    assert we == 36000


def test_solver_and_validator_consistency_with_explicit_mode():
    """Verify CVRPTWSolver and RouteValidator normalize windows identically under explicit mode."""
    depot = DepotLocation(depot_id="DEPOT-01", name="Hub", lat=19.1, lon=72.8, operating_hours_sec=36000)
    departure = 28800

    stop_rel = DeliveryStop(
        stop_id="S_REL",
        name="Relative Window Stop",
        lat=19.11,
        lon=72.81,
        time_window_start_sec=7200,
        time_window_end_sec=14400,
        window_mode=TimeWindowMode.RELATIVE
    )
    stop_abs = DeliveryStop(
        stop_id="S_ABS",
        name="Absolute Window Stop",
        lat=19.12,
        lon=72.82,
        time_window_start_sec=36000,
        time_window_end_sec=40000,
        window_mode=TimeWindowMode.ABSOLUTE
    )
    stops = [stop_rel, stop_abs]

    fleet = [CommercialVehicleSpec(
        vehicle_id="VAN-01",
        vehicle_class=VehicleClass.DELIVERY_VAN,
        payload_capacity_kg=1000.0,
        fixed_dispatch_cost=100.0,
        running_cost_per_km=5.0
    )]

    matrix = [[0.0, 10.0, 10.0], [10.0, 0.0, 10.0], [10.0, 10.0, 0.0]]
    durations = [[0.0, 300.0, 300.0], [300.0, 0.0, 300.0], [300.0, 300.0, 0.0]]

    solver = CVRPTWSolver(
        distance_matrix=matrix,
        duration_matrix=durations,
        depot=depot,
        stops=stops,
        fleet=fleet,
        departure_time_sec=departure
    )

    validator = RouteValidator(
        depot=depot,
        stops=stops,
        fleet=fleet,
        distance_matrix=matrix,
        duration_matrix=durations,
        departure_time_sec=departure
    )

    # Check solver normalized windows
    assert solver.normalized_windows[0] == (departure + 7200, departure + 14400)
    assert solver.normalized_windows[1] == (36000, 40000)

    # Check validator normalized windows
    assert validator.normalized_windows["S_REL"] == solver.normalized_windows[0]
    assert validator.normalized_windows["S_ABS"] == solver.normalized_windows[1]
