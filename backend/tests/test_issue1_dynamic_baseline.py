"""
Reproduction and validation tests for Issue #1:
Dynamic baseline re-solving in AISimulationEngine.
"""

import pytest
from backend.app.models.fleet_v2 import CommercialVehicleSpec, VehicleClass, DeliveryStop, DepotLocation
from backend.app.models.simulation_v3 import SimulationScenarioRequest
from backend.app.services.ai_simulation_engine import AISimulationEngine

@pytest.mark.asyncio
async def test_baseline_is_dynamic_not_hardcoded():
    """Verify that baseline cost & duration are computed from solver, not hardcoded 3850.0 / 4.8."""
    depot = DepotLocation(depot_id="D1", name="Bhiwandi Hub", lat=19.2967, lon=73.0631)
    
    stop_small = [
        DeliveryStop(stop_id="S1", name="Mulund", lat=19.1726, lon=72.9565, demand_kg=200)
    ]
    stops_large = [
        DeliveryStop(stop_id="S1", name="Mulund", lat=19.1726, lon=72.9565, demand_kg=200),
        DeliveryStop(stop_id="S2", name="Dadar", lat=19.0178, lon=72.8478, demand_kg=300),
        DeliveryStop(stop_id="S3", name="Colaba", lat=18.9067, lon=72.8147, demand_kg=400),
    ]

    fleet_van = [
        CommercialVehicleSpec(
            vehicle_id="VAN-01",
            name="Tata Ace",
            vehicle_class=VehicleClass.DELIVERY_VAN,
            payload_capacity_kg=1200,
            gross_vehicle_weight_tonnes=2.2,
            height_meters=1.9,
            fixed_dispatch_cost=1000.0,
            running_cost_per_km=15.0
        )
    ]

    fleet_two_vans = [
        CommercialVehicleSpec(
            vehicle_id="VAN-01",
            name="Tata Ace 1",
            vehicle_class=VehicleClass.DELIVERY_VAN,
            payload_capacity_kg=1200,
            gross_vehicle_weight_tonnes=2.2,
            height_meters=1.9,
            fixed_dispatch_cost=1000.0,
            running_cost_per_km=15.0
        ),
        CommercialVehicleSpec(
            vehicle_id="VAN-02",
            name="Tata Ace 2",
            vehicle_class=VehicleClass.DELIVERY_VAN,
            payload_capacity_kg=1200,
            gross_vehicle_weight_tonnes=2.2,
            height_meters=1.9,
            fixed_dispatch_cost=1000.0,
            running_cost_per_km=15.0
        )
    ]

    # Run scenario with 1 stop
    req1 = SimulationScenarioRequest(
        scenario_type="URGENT_DELIVERY",
        depot=depot,
        stops=stop_small,
        fleet=fleet_van,
        departure_time_iso="2026-10-09T08:30:00+05:30",
        parameters={}
    )
    res1 = await AISimulationEngine.run_scenario(req1)

    # Run scenario with 3 stops
    req2 = SimulationScenarioRequest(
        scenario_type="URGENT_DELIVERY",
        depot=depot,
        stops=stops_large,
        fleet=fleet_van,
        departure_time_iso="2026-10-09T08:30:00+05:30",
        parameters={}
    )
    res2 = await AISimulationEngine.run_scenario(req2)

    # Neither should equal the old hardcoded 3850.0 / 4.8
    assert res1.baseline_cost_inr != 3850.0, "Baseline cost is still hardcoded to 3850.0"
    assert res1.baseline_duration_hours != 4.8, "Baseline duration is still hardcoded to 4.8"

    # 3 stops should cost more and take longer than 1 stop
    assert res2.baseline_cost_inr > res1.baseline_cost_inr, "Baseline cost must scale with stops"
    assert res2.baseline_duration_hours > res1.baseline_duration_hours, "Baseline duration must scale with stops"
