"""
Tests for Issue #4:
Restrict LLM to explaining computed numbers and label deterministic vs AI text.
"""

from unittest.mock import patch

import pytest

from backend.app.models.fleet_v2 import (
    CommercialVehicleSpec,
    DeliveryStop,
    DepotLocation,
    VehicleClass,
)
from backend.app.models.simulation_v3 import (
    SimulationScenarioRequest,
    SimulationScenarioResponse,
)
from backend.app.services.ai_simulation_engine import AISimulationEngine


@pytest.fixture
def basic_scenario_request():
    depot = DepotLocation(depot_id="D1", name="Bhiwandi Hub", lat=19.2967, lon=73.0631)
    stops = [
        DeliveryStop(
            stop_id="S1",
            name="Mulund",
            lat=19.1726,
            lon=72.9565,
            demand_kg=200,
            is_in_restricted_urban_core=False,
            time_window_start_sec=32400,
            time_window_end_sec=36000
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
    return SimulationScenarioRequest(
        scenario_type="FLEET_SWAP_TRUCK_TO_VANS",
        depot=depot,
        stops=stops,
        fleet=fleet,
        departure_time_iso="2026-10-09T08:30:00+05:30",
        parameters={"region": "MUMBAI_MMRDA"}
    )

@pytest.mark.asyncio
async def test_schema_includes_ai_advisory_explanation_and_is_ai_generated(basic_scenario_request):
    """Verify response model separates deterministic fields and includes is_ai_generated label."""
    res = await AISimulationEngine.run_scenario(basic_scenario_request)
    assert isinstance(res, SimulationScenarioResponse)
    assert hasattr(res, "ai_advisory_explanation")
    assert res.ai_advisory_explanation is not None
    assert len(res.ai_advisory_explanation) > 0
    assert hasattr(res, "is_ai_generated")
    assert isinstance(res.is_ai_generated, bool)

@pytest.mark.asyncio
async def test_deterministic_fallback_when_llm_fails(basic_scenario_request):
    """When GROQ API fails or is not available, deterministic rule fallback must trigger cleanly."""
    with patch("backend.app.config.settings.GROQ_API_KEY", ""):
        res = await AISimulationEngine.run_scenario(basic_scenario_request)
        assert res.is_ai_generated is False
        assert "RouteOpt Deterministic Rules (Fallback)" in res.llm_engine_used
        assert len(res.ai_advisory_explanation) > 10
        # Deterministic text must reference computed numbers
        assert "Rs" in res.ai_advisory_explanation

@pytest.mark.asyncio
async def test_strict_system_prompt_grounding_content():
    """Verify system prompt contains strict instructions forbidding hallucinating numbers."""
    prompt = AISimulationEngine.SYSTEM_PROMPT
    assert "STRICT NUMERICAL AND DECISION BOUNDARIES" in prompt
    assert "ONLY reference the exact numbers" in prompt
    assert "NEVER invent new cost figures" in prompt
