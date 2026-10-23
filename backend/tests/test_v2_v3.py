"""
Test Suite for RouteOpt Versions 2 & 3
Verifies CVRPTW solver, regional road regulations, traffic matrices, and AI What-If simulations.
"""

from datetime import datetime

import pytest

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
from backend.app.services.regulation_engine import RegionalRegulationEngine
from backend.app.services.traffic_engine import TrafficEngine


def test_regional_regulations_no_entry_window():
    engine = RegionalRegulationEngine()
    # 09:30 AM = 34200 seconds into shift
    is_banned, name = engine.check_time_in_no_entry_window(34200)
    assert is_banned is True
    assert "Morning Peak" in name

    # 14:00 PM (2:00 PM) = 50400 seconds into shift (unrestricted)
    is_banned, name = engine.check_time_in_no_entry_window(50400)
    assert is_banned is False

    # 18:30 PM (6:30 PM) = 66600 seconds into shift (evening peak ban)
    is_banned, name = engine.check_time_in_no_entry_window(66600)
    assert is_banned is True
    assert "Evening Peak" in name

def test_pune_pmc_regulations():
    engine = RegionalRegulationEngine("PUNE_PMC")
    assert engine.violation_fine_inr == 15000.0
    assert engine.bridge_gvw_limit_tonnes == 5.0

    # 10:00 AM = 36000s (inside Pune morning ban 09:00 - 12:00)
    is_banned, name = engine.check_time_in_no_entry_window(36000)
    assert is_banned is True
    assert "Pune PMC Morning Peak" in name

    # 13:00 PM (1:00 PM) = 46800s (open window)
    is_banned, name = engine.check_time_in_no_entry_window(46800)
    assert is_banned is False

    # 18:00 PM (6:00 PM) = 64800s (inside Pune evening ban 16:30 - 20:30)
    is_banned, name = engine.check_time_in_no_entry_window(64800)
    assert is_banned is True
    assert "Pune PMC Evening Peak" in name

def test_nagpur_nmc_regulations():
    engine = RegionalRegulationEngine("NAGPUR_NMC")
    assert engine.violation_fine_inr == 10000.0
    assert engine.bridge_gvw_limit_tonnes == 5.0

    # 09:30 AM = 34200s (inside Nagpur morning ban 08:30 - 11:30)
    is_banned, name = engine.check_time_in_no_entry_window(34200)
    assert is_banned is True
    assert "Nagpur NMC Morning Peak" in name

    # 14:00 PM (2:00 PM) = 50400s (open window)
    is_banned, name = engine.check_time_in_no_entry_window(50400)
    assert is_banned is False

    # 19:00 PM (7:00 PM) = 68400s (inside Nagpur evening ban 17:30 - 21:00)
    is_banned, name = engine.check_time_in_no_entry_window(68400)
    assert is_banned is True
    assert "Nagpur NMC Evening Peak" in name

def test_flyover_height_clearance():
    engine = RegionalRegulationEngine()
    # Truck with 3.2m height attempting to take 2.5m flyover
    truck = CommercialVehicleSpec(
        vehicle_id="TRUCK-01",
        vehicle_class=VehicleClass.FREIGHT_TRUCK,
        gross_vehicle_weight_tonnes=10.0,
        height_meters=3.2,
        payload_capacity_kg=5000.0
    )
    can_pass, reason = engine.check_vehicle_access(truck, is_flyover=True)
    assert can_pass is False
    assert reason is not None and "height" in reason.lower()

    # Van with 1.9m height
    van = CommercialVehicleSpec(
        vehicle_id="VAN-01",
        vehicle_class=VehicleClass.DELIVERY_VAN,
        gross_vehicle_weight_tonnes=2.2,
        height_meters=1.9,
        payload_capacity_kg=1200.0
    )
    can_pass_van, _ = engine.check_vehicle_access(van, is_flyover=True)
    assert can_pass_van is True

def test_traffic_multiplier():
    morning_peak = datetime.fromisoformat("2026-10-09T09:00:00")
    assert TrafficEngine.get_congestion_factor(morning_peak) == 1.65

    night_time = datetime.fromisoformat("2026-10-09T02:00:00")
    assert TrafficEngine.get_congestion_factor(night_time) == 1.00

@pytest.mark.asyncio
async def test_cvrptw_solver_execution():
    depot = DepotLocation(depot_id="D1", name="Hub", lat=19.2967, lon=73.0631)
    stops = [
        DeliveryStop(stop_id="S1", name="Mulund", lat=19.1726, lon=72.9565, demand_kg=400),
        DeliveryStop(stop_id="S2", name="Dadar", lat=19.0178, lon=72.8478, demand_kg=500),
        DeliveryStop(stop_id="S3", name="BKC", lat=19.0674, lon=72.8687, demand_kg=300)
    ]
    fleet = [
        CommercialVehicleSpec(
            vehicle_id="VAN-01",
            vehicle_class=VehicleClass.DELIVERY_VAN,
            payload_capacity_kg=1200,
            gross_vehicle_weight_tonnes=2.2,
            height_meters=1.9
        ),
        CommercialVehicleSpec(
            vehicle_id="TRUCK-01",
            vehicle_class=VehicleClass.FREIGHT_TRUCK,
            payload_capacity_kg=4000,
            gross_vehicle_weight_tonnes=7.5,
            height_meters=3.1
        )
    ]

    coords = [[depot.lat, depot.lon]] + [[s.lat, s.lon] for s in stops]
    dist_m, dur_s, _ = await OSRMService.get_matrices(coords)

    solver = CVRPTWSolver(
        distance_matrix=dist_m,
        duration_matrix=dur_s,
        depot=depot,
        stops=stops,
        fleet=fleet,
        enforce_guidelines=True
    )
    solution = solver.solve()
    assert solution is not None
    assert "routes" in solution
    assert len(solution["routes"]) == 2

@pytest.mark.asyncio
async def test_ai_what_if_simulation():
    depot = DepotLocation(depot_id="D1", name="Hub", lat=19.2967, lon=73.0631)
    stops = [
        DeliveryStop(stop_id="S1", name="Mulund", lat=19.1726, lon=72.9565, demand_kg=400)
    ]
    fleet = [
        CommercialVehicleSpec(
            vehicle_id="TRUCK-01",
            vehicle_class=VehicleClass.FREIGHT_TRUCK,
            payload_capacity_kg=4000,
            gross_vehicle_weight_tonnes=7.5,
            height_meters=3.1
        )
    ]

    req = SimulationScenarioRequest(
        scenario_type="BORDER_ENTRY_DELAY",
        depot=depot,
        stops=stops,
        fleet=fleet,
        parameters={"delay_minutes": 60}
    )

    res = await AISimulationEngine.run_scenario(req)
    assert res.feasibility_status == "VIOLATION_DETECTED"
    assert res.cost_difference_inr > 0
    assert len(res.violations) > 0
    assert len(res.ai_advisory_recommendation) > 20
