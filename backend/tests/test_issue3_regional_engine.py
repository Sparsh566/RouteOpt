"""
Tests for Issue #3:
Remove keyword-based rule detection and enforce RegionalRegulationEngine + RouteValidator boundaries.
"""

import pytest

from backend.app.models.fleet_v2 import (
    CommercialVehicleSpec,
    DeliveryStop,
    DepotLocation,
    VehicleClass,
)
from backend.app.models.simulation_v3 import SimulationScenarioRequest
from backend.app.services.ai_simulation_engine import AISimulationEngine


@pytest.mark.asyncio
async def test_keyword_ban_on_compliant_van_does_not_trigger_violation():
    """Van mentioning 'police ban fine' in custom situation should stay COMPLIANT because vans are exempt."""
    depot = DepotLocation(depot_id="D1", name="Bhiwandi Hub", lat=19.2967, lon=73.0631)
    stops = [
        DeliveryStop(
            stop_id="S1",
            name="Mulund",
            lat=19.1726,
            lon=72.9565,
            demand_kg=200,
            is_in_restricted_urban_core=True,
            time_window_start_sec=32400, # 9:00 AM
            time_window_end_sec=36000   # 10:00 AM
        )
    ]
    fleet = [
        CommercialVehicleSpec(
            vehicle_id="VAN-01",
            name="Tata Ace",
            vehicle_class=VehicleClass.DELIVERY_VAN,
            payload_capacity_kg=1200,
            gross_vehicle_weight_tonnes=2.2,
            height_meters=1.9
        )
    ]

    req = SimulationScenarioRequest(
        scenario_type="CUSTOM_SITUATION",
        custom_situation_text="Driver heard about police no-entry ban and 5 pm fine on this highway.",
        depot=depot,
        stops=stops,
        fleet=fleet,
        departure_time_iso="2026-10-09T08:30:00+05:30",
        parameters={"region": "MUMBAI_MMRDA"}
    )
    res = await AISimulationEngine.run_scenario(req)
    # The van is exempt from HCV ban, so despite 'ban' and 'fine' in the prompt, it must be COMPLIANT
    assert res.feasibility_status == "COMPLIANT"
    assert len(res.violations) == 0

@pytest.mark.asyncio
async def test_regional_rules_enforced_pune_fine():
    """In PUNE_PMC, truck violation penalty must reflect Pune regulations (15,000 INR)."""
    depot = DepotLocation(depot_id="D1", name="Pune Swargate", lat=18.5018, lon=73.8586)
    stops = [
        DeliveryStop(
            stop_id="S1",
            name="FC Road",
            lat=18.5284,
            lon=73.8418,
            demand_kg=500,
            is_in_restricted_urban_core=True,
            time_window_start_sec=36000, # 10:00 AM (inside Pune peak ban 09:00 - 12:00)
            time_window_end_sec=39600   # 11:00 AM
        )
    ]
    fleet = [
        CommercialVehicleSpec(
            vehicle_id="TRUCK-01",
            name="Tata 407",
            vehicle_class=VehicleClass.FREIGHT_TRUCK,
            payload_capacity_kg=4000,
            gross_vehicle_weight_tonnes=7.5,
            height_meters=3.1
        )
    ]

    req = SimulationScenarioRequest(
        scenario_type="CUSTOM_SITUATION",
        custom_situation_text="Client requesting urgent morning freight drop off FC Road corridor.",
        depot=depot,
        stops=stops,
        fleet=fleet,
        departure_time_iso="2026-10-09T09:30:00+05:30",
        parameters={"region": "PUNE_PMC"}
    )
    res = await AISimulationEngine.run_scenario(req)
    assert res.feasibility_status in ["VIOLATION_DETECTED", "INFEASIBLE"]
    if res.violations:
        assert res.violations[0].penalty_fine_inr == 15000.0

@pytest.mark.asyncio
async def test_regional_rules_enforced_nagpur_fine():
    """In NAGPUR_NMC, truck violation penalty must reflect Nagpur regulations (10,000 INR)."""
    depot = DepotLocation(depot_id="D1", name="Nagpur Hub", lat=21.1458, lon=79.0882)
    stops = [
        DeliveryStop(
            stop_id="S1",
            name="Sitabuldi",
            lat=21.1498,
            lon=79.0806,
            demand_kg=500,
            is_in_restricted_urban_core=True,
            time_window_start_sec=32400, # 09:00 AM (inside Nagpur morning ban 08:30 - 11:30)
            time_window_end_sec=36000
        )
    ]
    fleet = [
        CommercialVehicleSpec(
            vehicle_id="TRUCK-01",
            name="Tata 407",
            vehicle_class=VehicleClass.FREIGHT_TRUCK,
            payload_capacity_kg=4000,
            gross_vehicle_weight_tonnes=7.5,
            height_meters=3.1
        )
    ]

    req = SimulationScenarioRequest(
        scenario_type="CUSTOM_SITUATION",
        custom_situation_text="Morning freight drop in Sitabuldi commercial area.",
        depot=depot,
        stops=stops,
        fleet=fleet,
        departure_time_iso="2026-10-09T08:30:00+05:30",
        parameters={"region": "NAGPUR_NMC"}
    )
    res = await AISimulationEngine.run_scenario(req)
    assert res.feasibility_status in ["VIOLATION_DETECTED", "INFEASIBLE"]
    if res.violations:
        assert res.violations[0].penalty_fine_inr == 10000.0

