"""
FastAPI Controller: AI 'What-If' Simulation & Regulatory Guidelines
Includes rate limiting, LLM input sanitization, and structured disruption analysis.
"""

import html
import re
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request

from backend.app.models.simulation_v3 import (
    SimulationScenarioRequest,
    SimulationScenarioResponse,
)
from backend.app.services.ai_simulation_engine import AISimulationEngine
from backend.app.services.regulation_engine import RegionalRegulationEngine

router = APIRouter(tags=["AI Simulation Sandbox"])

# In-memory sliding window rate limiter: max 20 requests per 60 seconds per IP
RATE_LIMIT_MAX_REQUESTS = 20
RATE_LIMIT_WINDOW_SECONDS = 60
_request_timestamps: dict[str, list[float]] = defaultdict(list)

def _check_rate_limit(client_ip: str):
    now = time.time()
    timestamps = [t for t in _request_timestamps[client_ip] if now - t < RATE_LIMIT_WINDOW_SECONDS]
    _request_timestamps[client_ip] = timestamps
    if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: maximum {RATE_LIMIT_MAX_REQUESTS} requests per minute."
        )
    _request_timestamps[client_ip].append(now)

def _sanitize_text(text: str | None) -> str | None:
    if not text:
        return text
    # Limit length
    truncated = text.strip()[:500]
    # Escape HTML entities
    escaped = html.escape(truncated)
    # Filter prompt injection phrases
    filtered = re.sub(r"(?i)(ignore\s+(all\s+)?previous\s+instructions|system\s+prompt|developer\s+mode)", "[filtered]", escaped)
    return filtered

@router.post("/simulate", response_model=SimulationScenarioResponse)
@router.post("/v2/simulate", response_model=SimulationScenarioResponse)
async def run_simulation(payload: SimulationScenarioRequest, request: Request):
    """
    Executes an AI 'What-If' scenario simulation for regulatory breaches, delays, and vehicle swaps.
    Rate limited to 20 requests per minute per IP.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    _check_rate_limit(client_ip)

    if payload.custom_situation_text:
        payload.custom_situation_text = _sanitize_text(payload.custom_situation_text)

    try:
        result = await AISimulationEngine.run_scenario(payload)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Simulation execution failed: {e!s}")

@router.get("/guidelines")
async def get_regional_guidelines(region: str = "MUMBAI_MMRDA"):
    """
    Returns regional municipal road rules and commercial vehicle guidelines.
    """
    engine = RegionalRegulationEngine(region)
    return engine.get_guideline_summary()
