"""
AI 'What-If' Scenario Simulation and Advisory Engine
Powered by Groq / xAI Grok API with structured heuristic fallbacks.
"""

import time
import httpx
from typing import Dict, Any, List
import logging
from backend.app.config import settings
from backend.app.models.simulation_v3 import (
    SimulationScenarioRequest,
    SimulationScenarioResponse,
    RuleViolationDetail
)
from backend.app.services.regulation_engine import RegionalRegulationEngine

logger = logging.getLogger("routeopt.simulation")

class AISimulationEngine:
    SYSTEM_PROMPT = """
You are the RouteOpt AI Logistics & Regulatory Simulation Advisor for Indian commercial logistics (Delivery Vans like Tata Ace vs Freight Trucks).
You specialize in municipal road rules (Mumbai MMRDA / Pune PMC), peak-hour HCV No-Entry bans (08:00-11:30 AM & 17:00-21:30 PM), flyover height barriers (2.5m), and commercial fleet economics.
Analyze the given simulation scenario and metrics.
Provide a concise, professional 3-sentence executive briefing:
1. Exact consequence (regulatory breach, delays, or cost impact).
2. Economic trade-off explanation.
3. Recommended actionable strategy.
"""

    @classmethod
    async def run_scenario(cls, request: SimulationScenarioRequest) -> SimulationScenarioResponse:
        t0 = time.perf_counter()
        reg_engine = RegionalRegulationEngine()

        baseline_cost = 3850.0
        baseline_duration = 4.8
        violations: List[RuleViolationDetail] = []
        scenario = request.scenario_type
        params = request.parameters

        if scenario == "BORDER_ENTRY_DELAY":
            # Scenario: Delay at border toll/octroi causes truck to arrive during 17:00-21:30 No-Entry ban
            delay_mins = params.get("delay_minutes", 60)
            sim_cost = baseline_cost + (delay_mins * 12.0) + reg_engine.violation_fine_inr
            # Forced idle layover waiting for 21:30 PM opening = +4.0 hours
            sim_duration = baseline_duration + (delay_mins / 60.0) + 4.0
            status = "VIOLATION_DETECTED"
            title = "Highway Toll Delay Leading to Evening Peak No-Entry Breach"
            action = "Hold truck at Bhiwandi outer logistics park until 21:30 PM opening, or transship urgency parcels onto two Tata Ace delivery vans."

            violations.append(RuleViolationDetail(
                vehicle_id=params.get("vehicle_id", "TRUCK-01 (Tata 407)"),
                rule_breached="Mumbai Traffic Police Sec 115/116: HCV Urban No-Entry Ban",
                location="Thane / Mulund Checkpost Corridor",
                scheduled_arrival="17:20 PM",
                legal_hours_window="11:30 AM - 17:00 PM or after 21:30 PM",
                penalty_fine_inr=reg_engine.violation_fine_inr,
                delay_minutes=delay_mins + 240.0
            ))

        elif scenario == "FLEET_SWAP_TRUCK_TO_VANS":
            # Scenario: Replacing 1 heavy truck with 3 Tata Ace delivery vans
            sim_cost = baseline_cost + 720.0   # Added driver and commercial toll fees
            sim_duration = baseline_duration - 1.6  # Vans bypass all peak HCV bans and alley delays
            status = "COMPLIANT"
            title = "Fleet Reconfiguration: 1 Heavy Truck Swapped for 3 Tata Ace Vans"
            action = "Deploy 3 Tata Ace vans. Despite +₹720 higher driver/toll overhead, delivery completes 1.6 hours earlier with zero legal no-entry exposure."

        elif scenario == "FLYOVER_HEIGHT_CLOSURE":
            # Scenario: Flyover closed for VIP / metro work, forcing diversion through low bridge gantry (2.5m)
            sim_cost = baseline_cost + 480.0
            sim_duration = baseline_duration + 1.2
            status = "REROUTED_SUCCESSFULLY"
            title = "Flyover Clearance Barrier Diversion Simulation"
            action = "Reroute tall freight trucks via Eastern Freeway ground corridor; dispatch vans via Western arterial surface lanes."

        else:  # SUDDEN_VIP_ORDER_INSERTION
            sim_cost = baseline_cost + 350.0
            sim_duration = baseline_duration + 0.9
            status = "COMPLIANT"
            title = "Ad-Hoc VIP Order Mid-Route Insertion"
            action = "Assign dynamic pickup to nearest available Tata Ace Van with surplus payload capacity."

        cost_diff = sim_cost - baseline_cost
        dur_diff = sim_duration - baseline_duration

        # LLM advisory generation
        ai_recommendation, engine_name = await cls._query_llm(
            scenario_title=title,
            status=status,
            cost_diff=cost_diff,
            dur_diff=dur_diff,
            violations=violations,
            suggested_action=action
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000

        return SimulationScenarioResponse(
            scenario_type=scenario,
            scenario_title=title,
            feasibility_status=status,
            baseline_cost_inr=round(baseline_cost, 2),
            simulated_cost_inr=round(sim_cost, 2),
            cost_difference_inr=round(cost_diff, 2),
            baseline_duration_hours=round(baseline_duration, 2),
            simulated_duration_hours=round(sim_duration, 2),
            violations=violations,
            ai_advisory_recommendation=ai_recommendation,
            suggested_action=action,
            llm_engine_used=engine_name,
            simulation_duration_ms=round(elapsed_ms, 2)
        )

    @classmethod
    async def _query_llm(
        cls,
        scenario_title: str,
        status: str,
        cost_diff: float,
        dur_diff: float,
        violations: List[RuleViolationDetail],
        suggested_action: str
    ) -> tuple[str, str]:
        user_prompt = (
            f"Scenario: {scenario_title}\n"
            f"Status: {status}\n"
            f"Cost Variance: ₹{cost_diff:+.2f}, Time Variance: {dur_diff:+.2f} hours\n"
            f"Violations: {[v.rule_breached for v in violations]}\n"
            f"Operational Remedy: {suggested_action}"
        )

        # 1. Try xAI Grok API if key is available
        if settings.GROK_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    res = await client.post(
                        "https://api.x.ai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {settings.GROK_API_KEY}"},
                        json={
                            "model": "grok-beta",
                            "messages": [
                                {"role": "system", "content": cls.SYSTEM_PROMPT},
                                {"role": "user", "content": user_prompt}
                            ],
                            "temperature": 0.2
                        }
                    )
                    if res.status_code == 200:
                        text = res.json()["choices"][0]["message"]["content"].strip()
                        return text, "xAI Grok (grok-beta)"
            except Exception as e:
                logger.warning(f"Grok API call failed: {e}")

        # 2. Try Groq API (Llama 3.3 70B) if key is available
        if settings.GROQ_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    res = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                        json={
                            "model": "llama-3.3-70b-versatile",
                            "messages": [
                                {"role": "system", "content": cls.SYSTEM_PROMPT},
                                {"role": "user", "content": user_prompt}
                            ],
                            "temperature": 0.2
                        }
                    )
                    if res.status_code == 200:
                        text = res.json()["choices"][0]["message"]["content"].strip()
                        return text, "Groq AI (Llama 3.3 70B)"
            except Exception as e:
                logger.warning(f"Groq API call failed: {e}")

        # 3. Built-in Deterministic Heuristic Advisor (Guarantees zero-failure live demos)
        if status == "VIOLATION_DETECTED":
            advice = (
                f"Regulatory Alert: Scheduled arrival directly breaches municipal peak-hour truck restrictions, "
                f"incurring an immediate fine risk of ₹20,000 and +{dur_diff:.1f} hrs delay. "
                f"Economic analysis indicates holding at an outer logistics bay saves ₹19,280 in net violation penalties. "
                f"Action Plan: {suggested_action}"
            )
        elif status == "COMPLIANT" and "SWAP" in scenario_title.upper():
            advice = (
                f"Fleet Optimization Analysis: Reallocating freight to 3 Tata Ace LCVs incurs an operational premium of "
                f"₹{cost_diff:+.0f}, but reclaims {abs(dur_diff):.1f} hours of transit time by completely bypassing HCV municipal restrictions. "
                f"For SLA-critical consignments, the van fleet yields a 28% higher customer satisfaction index. "
                f"Action Plan: {suggested_action}"
            )
        else:
            advice = (
                f"Simulation completed cleanly with zero regulatory infractions. Operational adjustments result in "
                f"a marginal cost delta of ₹{cost_diff:+.0f} and schedule impact of {dur_diff:+.1f} hours. "
                f"Action Plan: {suggested_action}"
            )

        return advice, "RouteOpt Rule-Based Advisor (Offline / Heuristic Engine)"
