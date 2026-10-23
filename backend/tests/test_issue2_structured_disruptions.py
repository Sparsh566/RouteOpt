"""
Unit tests for Issue #2:
Structured disruption scenarios in AISimulationEngine:
- LEG_DELAY
- ARC_CLOSURE
- VEHICLE_BREAKDOWN
- URGENT_STOP
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


@pytest.fixture
def base_scenario_setup():
    depot = DepotLocation(depot_id="D1", name="Bhiwandi Hub", lat=19.2967, lon=73.0631)
    stops = [
        DeliveryStop(stop_id="S1", name="Mulund", lat=19.1726, lon=72.9565, demand_kg=400, time_window_start_sec=28800, time_window_end_sec=64800),
        DeliveryStop(stop_id="S2", name="Dadar", lat=19.0178, lon=72.8478, demand_kg=500, time_window_start_sec=28800, time_window_end_sec=64800),
        DeliveryStop(stop_id="S3", name="BKC", lat=19.0674, lon=72.8687, demand_kg=300, time_window_start_sec=28800, time_window_end_sec=64800)
    ]
    fleet = [
        CommercialVehicleSpec(
            vehicle_id="VAN-01",
            name="Tata Ace 1",
            vehicle_class=VehicleClass.DELIVERY_VAN,
            payload_capacity_kg=1200,
            gross_vehicle_weight_tonnes=2.2,
            height_meters=1.9,
            fixed_dispatch_cost=800.0,
            running_cost_per_km=14.0
        ),
        CommercialVehicleSpec(
            vehicle_id="VAN-02",
            name="Tata Ace 2",
            vehicle_class=VehicleClass.DELIVERY_VAN,
            payload_capacity_kg=1200,
            gross_vehicle_weight_tonnes=2.2,
            height_meters=1.9,
            fixed_dispatch_cost=800.0,
            running_cost_per_km=14.0
        )
    ]
    return depot, stops, fleet

@pytest.mark.asyncio
async def test_vehicle_breakdown_scenario(base_scenario_setup):
    depot, stops, fleet = base_scenario_setup
    req = SimulationScenarioRequest(
        scenario_type="VEHICLE_BREAKDOWN",
        depot=depot,
        stops=stops,
        fleet=fleet,
        departure_time_iso="2026-10-09T08:30:00+05:30",
        parameters={"breakdown_vehicle_id": "VAN-01"}
    )
    res = await AISimulationEngine.run_scenario(req)
    assert res.scenario_type == "VEHICLE_BREAKDOWN"
    # When 1 van breaks down, the single remaining van must either serve all stops or drop if capacity exceeded
    assert res.simulated_cost_inr > 0
    assert hasattr(res, "unserved_stops_count")

@pytest.mark.asyncio
async def test_arc_closure_scenario(base_scenario_setup):
    depot, stops, fleet = base_scenario_setup
    req = SimulationScenarioRequest(
        scenario_type="ARC_CLOSURE",
        depot=depot,
        stops=stops,
        fleet=fleet,
        departure_time_iso="2026-10-09T08:30:00+05:30",
        parameters={"from_node_index": 0, "to_node_index": 1}
    )
    res = await AISimulationEngine.run_scenario(req)
    assert res.scenario_type == "ARC_CLOSURE"
    # Rerouting around closed arc should succeed or report detour
    assert res.feasibility_status in ["REROUTED_SUCCESSFULLY", "COMPLIANT"]
    assert res.cost_difference_inr >= 0

@pytest.mark.asyncio
async def test_leg_delay_scenario(base_scenario_setup):
    depot, stops, fleet = base_scenario_setup
    req = SimulationScenarioRequest(
        scenario_type="LEG_DELAY",
        depot=depot,
        stops=stops,
        fleet=fleet,
        departure_time_iso="2026-10-09T08:30:00+05:30",
        parameters={"delay_minutes": 45, "delay_node_index": 1}
    )
    res = await AISimulationEngine.run_scenario(req)
    assert res.scenario_type == "LEG_DELAY"
    assert res.simulated_duration_hours >= res.baseline_duration_hours

@pytest.mark.asyncio
async def test_urgent_stop_scenario(base_scenario_setup):
    depot, stops, fleet = base_scenario_setup
    urgent_stop = {
        "stop_id": "URGENT-01",
        "name": "Kandivali Hospital",
        "lat": 19.2062,
        "lon": 72.8526,
        "demand_kg": 150,
        "time_window_start_sec": 30000,
        "time_window_end_sec": 40000
    }
    req = SimulationScenarioRequest(
        scenario_type="URGENT_STOP",
        depot=depot,
        stops=stops,
        fleet=fleet,
        departure_time_iso="2026-10-09T08:30:00+05:30",
        parameters={"urgent_stop": urgent_stop}
    )
    res = await AISimulationEngine.run_scenario(req)
    assert res.scenario_type == "URGENT_STOP"
    assert res.simulated_cost_inr >= res.baseline_cost_inr
