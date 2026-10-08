"""
AI Scenario Simulation and Advisory Engine
Uses Groq API with robust heuristic fallback.
Strictly avoids emojis, em dashes, and AI buzzwords.
Supports custom user situations and problems.
"""

import time
import httpx
import re
from typing import Dict, Any, List, Optional
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
You are a senior fleet dispatch supervisor for Indian commercial transport (Tata Ace delivery vans and Tata 407 freight trucks).
You evaluate delays, traffic rules, and custom road problems in plain, practical terms for drivers and dispatchers.

CRITICAL FORMATTING RULES:
1. Do NOT use any emojis.
2. Do NOT use em dashes. Use simple hyphens, commas, or colons instead.
3. Write in direct, simple, professional language.
4. Keep the summary to 3 short sentences:
   - What happened (the delay or rule breach).
   - Cost and time consequence.
   - What the driver or supervisor must do right now.
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
        custom_problem_text = request.custom_situation_text

        if custom_problem_text and custom_problem_text.strip():
            # User provided a custom situation
            custom_lower = custom_problem_text.lower()
            title = "Custom Situation Analysis: " + (custom_problem_text[:45] + "..." if len(custom_problem_text) > 45 else custom_problem_text)
            
            # Detect rule impact keywords
            has_ban = any(w in custom_lower for w in ["ban", "no-entry", "no entry", "police", "fine", "5 pm", "5:00", "8 am", "peak", "late", "delay", "traffic"])
            has_barrier = any(w in custom_lower for w in ["height", "flyover", "bridge", "barrier", "clearance", "gantry", "water", "flood", "low"])

            if has_ban:
                status = "VIOLATION_DETECTED"
                sim_cost = baseline_cost + 20600.0
                sim_duration = baseline_duration + 3.5
                action = "Hold heavy truck at outer hub until 9:30 PM, or transfer delivery boxes into two Tata Ace vans."
                violations.append(RuleViolationDetail(
                    vehicle_id="TRUCK-01 (Tata 407)",
                    rule_breached="Municipal Commercial Vehicle Restriction Risk",
                    location="City Road Corridor",
                    scheduled_arrival="Peak Window",
                    legal_hours_window="11:30 AM to 5:00 PM, or after 9:30 PM",
                    penalty_fine_inr=reg_engine.violation_fine_inr,
                    delay_minutes=210.0
                ))
            elif has_barrier:
                status = "REROUTED_SUCCESSFULLY"
                sim_cost = baseline_cost + 450.0
                sim_duration = baseline_duration + 1.2
                action = "Direct heavy trucks via ground-level bypass roads; small Tata Ace vans can proceed on standard route."
            else:
                status = "COMPLIANT"
                sim_cost = baseline_cost + 280.0
                sim_duration = baseline_duration + 0.7
                action = "Update delivery sequence and notify destination supervisor of adjusted arrival window."

        elif scenario == "BORDER_ENTRY_DELAY":
            delay_mins = params.get("delay_minutes", 60)
            sim_cost = baseline_cost + (delay_mins * 12.0) + reg_engine.violation_fine_inr
            sim_duration = baseline_duration + (delay_mins / 60.0) + 4.0
            status = "VIOLATION_DETECTED"
            title = "Highway Toll Delay Leading to Evening Peak No-Entry Breach"
            action = "Park truck at Bhiwandi or Kalamboli transport hub until 9:30 PM, or transfer critical boxes into two Tata Ace vans."

            violations.append(RuleViolationDetail(
                vehicle_id=params.get("vehicle_id", "TRUCK-01 (Tata 407)"),
                rule_breached="Mumbai Traffic Police Notice: Heavy Goods Vehicle No-Entry Ban",
                location="Thane - Mulund Checkpost",
                scheduled_arrival="17:20 PM",
                legal_hours_window="11:30 AM to 5:00 PM, or after 9:30 PM",
                penalty_fine_inr=reg_engine.violation_fine_inr,
                delay_minutes=delay_mins + 240.0
            ))

        elif scenario == "FLEET_SWAP_TRUCK_TO_VANS":
            sim_cost = baseline_cost + 720.0
            sim_duration = baseline_duration - 1.6
            status = "COMPLIANT"
            title = "Fleet Change: Replacing 1 Big Truck with 3 Tata Ace Vans"
            action = "Dispatch 3 Tata Ace vans. Driver and toll cost increases by Rs 720, but delivery finishes 1.6 hours faster without any police fine risk."

        elif scenario == "FLYOVER_HEIGHT_CLOSURE":
            sim_cost = baseline_cost + 480.0
            sim_duration = baseline_duration + 1.2
            status = "REROUTED_SUCCESSFULLY"
            title = "Flyover Closed: Height Barrier Detour"
            action = "Direct heavy trucks to use surface roads via Eastern Freeway corridor; send small vans through regular city roads."

        else:
            sim_cost = baseline_cost + 350.0
            sim_duration = baseline_duration + 0.9
            status = "COMPLIANT"
            title = "Urgent Delivery Added on Active Route"
            action = "Assign the new pickup stop to the nearest Tata Ace van that has remaining weight space."

        cost_diff = sim_cost - baseline_cost
        dur_diff = sim_duration - baseline_duration

        ai_recommendation, engine_name = await cls._query_llm(
            scenario_title=title,
            status=status,
            cost_diff=cost_diff,
            dur_diff=dur_diff,
            violations=violations,
            suggested_action=action,
            custom_problem=custom_problem_text
        )

        ai_recommendation = cls._clean_text(ai_recommendation)
        title = cls._clean_text(title)
        action = cls._clean_text(action)

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
        suggested_action: str,
        custom_problem: Optional[str] = None
    ) -> tuple[str, str]:
        if custom_problem and custom_problem.strip():
            user_prompt = (
                f"Custom Driver Problem: {custom_problem}\n"
                f"Evaluation Status: {status}\n"
                f"Cost Variance: Rs {cost_diff:+.2f}\n"
                f"Time Variance: {dur_diff:+.2f} hours\n"
                f"Violations: {[v.rule_breached for v in violations]}\n"
                f"Recommended Operational Action: {suggested_action}\n"
                f"Write the 3-sentence operational guidance for the driver and supervisor."
            )
        else:
            user_prompt = (
                f"Scenario: {scenario_title}\n"
                f"Status: {status}\n"
                f"Cost Difference: Rs {cost_diff:+.2f}\n"
                f"Time Difference: {dur_diff:+.2f} hours\n"
                f"Violations: {[v.rule_breached for v in violations]}\n"
                f"Recommended Action: {suggested_action}\n"
                f"Write the 3-sentence operational driver advice."
            )

        groq_key = settings.GROQ_API_KEY
        if groq_key:
            for model_candidate in ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]:
                try:
                    async with httpx.AsyncClient(timeout=6.0) as client:
                        res = await client.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers={"Authorization": f"Bearer {groq_key}"},
                            json={
                                "model": model_candidate,
                                "messages": [
                                    {"role": "system", "content": cls.SYSTEM_PROMPT},
                                    {"role": "user", "content": user_prompt}
                                ],
                                "temperature": 0.1
                            }
                        )
                        if res.status_code == 200:
                            text = res.json()["choices"][0]["message"]["content"].strip()
                            return text, f"Groq Llama ({model_candidate.split('/')[-1]})"
                except Exception as e:
                    logger.warning(f"Groq API call failed on {model_candidate}: {e}")

        # Fallback text
        if status == "VIOLATION_DETECTED":
            advice = (
                f"The vehicle faces a municipal peak-hour restriction or delay. "
                f"Continuing risks an immediate Rs 20,000 police penalty and over 3 hours of delay. "
                f"Driver should halt at an outer transport bay or shift packages to Tata Ace delivery vans."
            )
        else:
            advice = (
                f"The situation has been evaluated against regional road rules. "
                f"Expected cost change is Rs {cost_diff:+.0f} with a time shift of {dur_diff:+.1f} hours. "
                f"Proceed according to the suggested action."
            )

        return advice, "RouteOpt Standard Dispatch Rules"

    @staticmethod
    def _clean_text(text: str) -> str:
        for char in ["\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\u2212"]:
            text = text.replace(char, "-")
        text = text.replace("—", " - ").replace("–", "-")
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FA6F"
            "\U0001FA70-\U0001FAFF"
            "\U00002600-\U000026FF"
            "]+", flags=re.UNICODE
        )
        return emoji_pattern.sub("", text).strip()
