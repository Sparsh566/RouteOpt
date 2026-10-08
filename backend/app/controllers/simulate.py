"""
FastAPI Controller: AI 'What-If' Simulation & Regulatory Guidelines
"""

from fastapi import APIRouter, HTTPException
from backend.app.models.simulation_v3 import (
    SimulationScenarioRequest,
    SimulationScenarioResponse
)
from backend.app.services.ai_simulation_engine import AISimulationEngine
from backend.app.services.regulation_engine import RegionalRegulationEngine

router = APIRouter(tags=["AI Simulation Sandbox"])

@router.post("/simulate", response_model=SimulationScenarioResponse)
async def run_simulation(payload: SimulationScenarioRequest):
    """
    Executes an AI 'What-If' scenario simulation for regulatory breaches, delays, and vehicle swaps.
    """
    try:
        result = await AISimulationEngine.run_scenario(payload)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Simulation execution failed: {str(e)}")

@router.get("/guidelines")
async def get_regional_guidelines(region: str = "MUMBAI_MMRDA"):
    """
    Returns regional municipal road rules and commercial vehicle guidelines.
    """
    engine = RegionalRegulationEngine(region)
    return engine.get_guideline_summary()
