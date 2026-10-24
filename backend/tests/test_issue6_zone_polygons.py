"""
Tests for Issue #6 / #29:
Restricted zone polygons in regulation data and deriving restricted urban core status
from stop coordinates.
"""

from backend.app.models.fleet_v2 import CommercialVehicleSpec, DeliveryStop, DepotLocation, VehicleClass
from backend.app.services.cvrptw_solver import CVRPTWSolver
from backend.app.services.regulation_engine import RegionalRegulationEngine
from backend.app.services.validator import RouteValidator


def test_polygon_containment_in_engine():
    """Verify RegionalRegulationEngine.is_coordinate_in_restricted_zone accurately detects polygon membership."""
    engine_mumbai = RegionalRegulationEngine("MUMBAI_MMRDA")

    # Inside Mumbai Core: [18.90, 72.80] to [19.10, 72.89]
    assert engine_mumbai.is_coordinate_in_restricted_zone(18.95, 72.83) is True
    assert engine_mumbai.is_coordinate_in_restricted_zone(19.05, 72.85) is True

    # Outside Mumbai Core: Thane / Navi Mumbai / Kalyan
    assert engine_mumbai.is_coordinate_in_restricted_zone(19.22, 73.00) is False
    assert engine_mumbai.is_coordinate_in_restricted_zone(18.70, 72.70) is False

    # Pune
    engine_pune = RegionalRegulationEngine("PUNE_PMC")
    # Inside Pune Core: [18.50, 73.82] to [18.55, 73.88]
    assert engine_pune.is_coordinate_in_restricted_zone(18.52, 73.85) is True
    assert engine_pune.is_coordinate_in_restricted_zone(18.40, 73.70) is False


def test_solver_auto_derives_restricted_status_from_stop_coordinates():
    """Verify CVRPTWSolver derives is_in_restricted_urban_core=True for stops inside the zone."""
    depot = DepotLocation(depot_id="DEPOT-01", name="Central Depot", lat=19.15, lon=72.90, operating_hours_sec=36000)

    # Stop 1 is inside South/Central Mumbai core, but is_in_restricted_urban_core=False by default
    stop_inside = DeliveryStop(
        stop_id="STOP-INSIDE",
        name="Colaba Shop",
        lat=18.95,
        lon=72.83,
        demand_kg=100.0,
        is_in_restricted_urban_core=False
    )

    # Stop 2 is outside in Thane
    stop_outside = DeliveryStop(
        stop_id="STOP-OUTSIDE",
        name="Thane Hub",
        lat=19.25,
        lon=73.02,
        demand_kg=100.0,
        is_in_restricted_urban_core=False
    )

    vehicle = CommercialVehicleSpec(
        vehicle_id="VAN-01",
        vehicle_class=VehicleClass.DELIVERY_VAN,
        payload_capacity_kg=1000.0,
        fixed_dispatch_cost=100.0,
        running_cost_per_km=5.0
    )

    matrix = [[0.0, 10.0, 10.0], [10.0, 0.0, 10.0], [10.0, 10.0, 0.0]]
    _ = CVRPTWSolver(
        distance_matrix=matrix,
        duration_matrix=matrix,
        depot=depot,
        stops=[stop_inside, stop_outside],
        fleet=[vehicle],
        region="MUMBAI_MMRDA"
    )

    # Stop inside should have been auto-flagged
    assert stop_inside.is_in_restricted_urban_core is True
    # Stop outside should remain unflagged
    assert stop_outside.is_in_restricted_urban_core is False


def test_validator_auto_derives_restricted_status_and_flags_violation():
    """Verify RouteValidator derives restricted status and enforces peak ban violation for heavy trucks."""
    depot = DepotLocation(depot_id="DEPOT-01", name="Central Depot", lat=19.15, lon=72.90, operating_hours_sec=36000)

    # Stop inside Mumbai restricted polygon, default False
    stop_inside = DeliveryStop(
        stop_id="STOP-01",
        name="Parel Retailer",
        lat=19.00,
        lon=72.84,
        demand_kg=200.0,
        time_window_start_sec=28800,  # 08:00 AM (Peak morning ban)
        time_window_end_sec=36000,
        service_duration_sec=300,
        is_in_restricted_urban_core=False
    )

    truck = CommercialVehicleSpec(
        vehicle_id="TRUCK-01",
        vehicle_class=VehicleClass.FREIGHT_TRUCK,
        payload_capacity_kg=5000.0,
        fixed_dispatch_cost=500.0,
        running_cost_per_km=15.0
    )

    matrix = [[0.0, 300.0], [300.0, 0.0]]
    durations = [[0.0, 300.0], [300.0, 0.0]]

    validator = RouteValidator(
        depot=depot,
        stops=[stop_inside],
        fleet=[truck],
        distance_matrix=matrix,
        duration_matrix=durations,
        departure_time_sec=28800,  # Departs at 08:00 AM
        region="MUMBAI_MMRDA",
        enforce_guidelines=True
    )

    # Derived flag should now be True
    assert stop_inside.is_in_restricted_urban_core is True

    # Validate route where heavy truck visits this stop during morning peak ban
    routes = [{
        "vehicle_id": "TRUCK-01",
        "schedule": [
            {"node_index": 0, "arrival_time_sec": 28800.0, "load_kg": 0.0},
            {"node_index": 1, "arrival_time_sec": 29400.0, "load_kg": 200.0},  # 08:10 AM (inside ban)
            {"node_index": 0, "arrival_time_sec": 30500.0, "load_kg": 0.0}
        ]
    }]

    report = validator.validate(routes, dropped_stops=[])

    assert not report["is_valid"]
    ban_errors = [e for e in report["errors"] if e["code"] == "TRUCK_PEAK_BAN_VIOLATION"]
    assert len(ban_errors) == 1
    assert ban_errors[0]["stop_id"] == "STOP-01"
