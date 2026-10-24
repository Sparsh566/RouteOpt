"""
AI Scenario Simulation and Advisory Engine
Uses Groq API with robust heuristic fallback.
Strictly avoids emojis, em dashes, and AI buzzwords.
Supports custom user situations and problems.
"""

import logging
import re
import time
from typing import Any, Literal

import httpx

from backend.app.config import settings
from backend.app.models.fleet_v2 import (
    CommercialVehicleSpec,
    DeliveryStop,
    VehicleClass,
)
from backend.app.models.simulation_v3 import (
    RuleViolationDetail,
    SimulationScenarioRequest,
    SimulationScenarioResponse,
)
from backend.app.services.cvrptw_solver import CVRPTWSolver
from backend.app.services.osrm_service import OSRMService
from backend.app.services.regulation_engine import RegionalRegulationEngine
from backend.app.services.validator import RouteValidator
from backend.app.utils import parse_departure_datetime

logger = logging.getLogger("routeopt.simulation")



class AISimulationEngine:
    SYSTEM_PROMPT = """
You are a senior fleet dispatch supervisor for Indian commercial transport (Tata Ace delivery vans and Tata 407 freight trucks).
You explain deterministically computed dispatch metrics, delays, and municipal traffic violations to drivers and dispatchers.

STRICT NUMERICAL AND DECISION BOUNDARIES:
1. Grounding: You must ONLY reference the exact numbers, costs, time variances, and feasibility status provided in the context. NEVER invent new cost figures, percentages, fines, or override the solver's feasibility decision.
2. Directness: Explain why the deterministic solver made this decision based strictly on the violations and metrics provided.
3. Formatting:
   - Do NOT use any emojis.
   - Do NOT use em dashes. Use simple hyphens, commas, or colons instead.
   - Keep the summary to exactly 3 short sentences:
     * What happened (the delay or rule breach).
     * The computed cost and time consequence (using only the provided metrics).
     * The recommended operational action.
"""

    @staticmethod
    def _calc_solution_metrics(solution: dict[str, Any], fleet: list[CommercialVehicleSpec]) -> tuple[float, float]:
        total_cost = 0.0
        total_dur_s = 0.0
        for r in solution.get("routes", []):
            if r.get("utilized", False):
                v = next((veh for veh in fleet if veh.vehicle_id == r["vehicle_id"]), None)
                if v:
                    total_cost += v.fixed_dispatch_cost + ((r["total_distance_m"] / 1000.0) * v.running_cost_per_km)
                total_dur_s += r["total_duration_s"]
        return total_cost, total_dur_s / 3600.0

    @classmethod
    async def run_scenario(cls, request: SimulationScenarioRequest) -> SimulationScenarioResponse:

        t0 = time.perf_counter()
        scenario = request.scenario_type
        params = request.parameters
        custom_problem_text = request.custom_situation_text
        region = params.get("region", "MUMBAI_MMRDA")
        reg_engine = RegionalRegulationEngine(region)

        # 1. Dynamically compute baseline route and metrics
        departure_dt, departure_sec = parse_departure_datetime(request.departure_time_iso)
        all_coords = [[request.depot.lat, request.depot.lon]] + [[s.lat, s.lon] for s in request.stops]
        dist_matrix, base_dur_matrix, _ = await OSRMService.get_matrices(all_coords)

        baseline_solver = CVRPTWSolver(
            distance_matrix=dist_matrix,
            duration_matrix=base_dur_matrix,
            depot=request.depot,
            stops=request.stops,
            fleet=request.fleet,
            enforce_guidelines=True,
            departure_time_sec=departure_sec,
            region=region
        )
        baseline_solution = baseline_solver.solve()

        if baseline_solution and baseline_solution.get("routes"):
            baseline_cost = 0.0
            baseline_duration_s = 0.0
            for r in baseline_solution["routes"]:
                if r.get("utilized", False):
                    v = next((veh for veh in request.fleet if veh.vehicle_id == r["vehicle_id"]), None)
                    if v:
                        baseline_cost += v.fixed_dispatch_cost + ((r["total_distance_m"] / 1000.0) * v.running_cost_per_km)
                    baseline_duration_s += r["total_duration_s"]
            baseline_duration = baseline_duration_s / 3600.0
        else:
            baseline_cost = 0.0
            baseline_duration = 0.0

        status: Literal["COMPLIANT", "VIOLATION_DETECTED", "REROUTED_SUCCESSFULLY", "INFEASIBLE"] = "COMPLIANT"
        violations: list[RuleViolationDetail] = []
        unserved_stops_count = 0
        missed_deadlines_count = 0
        fines_avoided_inr = 0.0

        if custom_problem_text and custom_problem_text.strip():
            # User provided a custom situation: evaluate deterministically with RouteValidator & RegionalRegulationEngine
            title = "Custom Situation Analysis: " + (custom_problem_text[:45] + "..." if len(custom_problem_text) > 45 else custom_problem_text)

            if not baseline_solution or not baseline_solution.get("routes"):
                status = "INFEASIBLE"
                sim_cost = baseline_cost
                sim_duration = baseline_duration
                unserved_stops_count = len(request.stops)
                action = f"Routing constraints infeasible in region {region} under operational bounds."
            else:
                validator = RouteValidator(
                    depot=request.depot,
                    stops=request.stops,
                    fleet=request.fleet,
                    distance_matrix=dist_matrix,
                    duration_matrix=base_dur_matrix,
                    departure_time_sec=departure_sec,
                    region=region,
                    enforce_guidelines=True
                )
                val_report = validator.validate(
                    routes=baseline_solution["routes"],
                    dropped_stops=baseline_solution.get("dropped_stops", [])
                )

                # Check for regional violations from route execution
                rule_errors = [e for e in val_report["errors"] if e.get("error_type") in [
                    "TRUCK_PEAK_BAN_VIOLATION", "FLYOVER_HEIGHT_VIOLATION", "BRIDGE_GVW_VIOLATION"
                ]]

                # Also check if heavy vehicle was barred from serving restricted stops during peak no-entry
                truck_present = any(v.vehicle_class == VehicleClass.FREIGHT_TRUCK for v in request.fleet)
                for s in request.stops:
                    if s.is_in_restricted_urban_core and truck_present:
                        norm_start, _ = s.get_normalized_window(departure_sec, request.depot.operating_hours_sec)
                        is_banned, window_name = reg_engine.check_time_in_no_entry_window(norm_start)
                        if is_banned:
                            rule_errors.append({
                                "vehicle_id": next((v.vehicle_id for v in request.fleet if v.vehicle_class == VehicleClass.FREIGHT_TRUCK), "TRUCK-01"),
                                "error_type": "TRUCK_PEAK_BAN_VIOLATION",
                                "stop_index": s.name,
                                "message": f"Stop {s.name} inside {window_name}"
                            })

                if rule_errors:
                    status = "VIOLATION_DETECTED"
                    sim_cost = baseline_cost + reg_engine.violation_fine_inr
                    sim_duration = baseline_duration + 2.0
                    action = f"Hold heavy truck outside restricted boundary or shift cargo to small delivery vans to avoid Rs {reg_engine.violation_fine_inr:,.0f} penalty."
                    for err in rule_errors:
                        violations.append(RuleViolationDetail(
                            vehicle_id=err.get("vehicle_id", "TRUCK-01"),
                            rule_breached=f"{region} Municipal Restriction: {err.get('error_type')}",
                            location=f"Stop {err.get('stop_index')}",
                            scheduled_arrival="Restricted Window",
                            legal_hours_window="Outside Peak No-Entry Windows",
                            penalty_fine_inr=reg_engine.violation_fine_inr,
                            delay_minutes=120.0
                        ))
                elif not val_report["is_valid"]:
                    status = "VIOLATION_DETECTED"
                    sim_cost = baseline_cost
                    sim_duration = baseline_duration
                    action = "Operational constraint breach detected: " + "; ".join(e.get("message", "") for e in val_report["errors"][:2])
                else:
                    status = "COMPLIANT"
                    sim_cost = baseline_cost
                    sim_duration = baseline_duration
                    action = f"Route confirmed compliant with {region} regional commercial vehicle guidelines."



        elif scenario == "VEHICLE_BREAKDOWN":
            breakdown_vid = params.get("breakdown_vehicle_id") or (request.fleet[0].vehicle_id if request.fleet else "VEH-01")
            disrupted_fleet = [v for v in request.fleet if v.vehicle_id != breakdown_vid]
            title = f"Vehicle Breakdown: {breakdown_vid}"

            if not disrupted_fleet:
                status = "INFEASIBLE"
                sim_cost = baseline_cost
                sim_duration = baseline_duration
                unserved_stops_count = len(request.stops)
                action = f"Vehicle {breakdown_vid} broke down. Fleet exhausted; urgent spare vehicle required."
            else:
                solver = CVRPTWSolver(
                    distance_matrix=dist_matrix,
                    duration_matrix=base_dur_matrix,
                    depot=request.depot,
                    stops=request.stops,
                    fleet=disrupted_fleet,
                    enforce_guidelines=True,
                    departure_time_sec=departure_sec,
                    region=region
                )
                disrupted_sol = solver.solve()
                if disrupted_sol:
                    sim_cost, sim_duration = cls._calc_solution_metrics(disrupted_sol, disrupted_fleet)
                    unserved_stops_count = len(disrupted_sol.get("dropped_stops", []))
                    if unserved_stops_count > 0:
                        status = "VIOLATION_DETECTED"
                        action = f"Vehicle {breakdown_vid} broke down. {unserved_stops_count} stops dropped due to remaining capacity limit."
                    else:
                        status = "REROUTED_SUCCESSFULLY"
                        action = f"Vehicle {breakdown_vid} broke down. Remaining fleet re-routed to absorb all stops."
                else:
                    status = "INFEASIBLE"
                    sim_cost = baseline_cost
                    sim_duration = baseline_duration
                    unserved_stops_count = len(request.stops)
                    action = f"Vehicle {breakdown_vid} broke down. Remaining vehicles cannot satisfy time windows or capacity."

        elif scenario == "ARC_CLOSURE":
            from_idx = params.get("from_node_index", 0)
            to_idx = params.get("to_node_index", 1)
            title = f"Road / Corridor Closure Between Nodes {from_idx} and {to_idx}"

            pert_dist = [row[:] for row in dist_matrix]
            pert_dur = [row[:] for row in base_dur_matrix]
            if 0 <= from_idx < len(pert_dist) and 0 <= to_idx < len(pert_dist):
                pert_dist[from_idx][to_idx] = 10_000_000.0
                pert_dur[from_idx][to_idx] = 100_000.0
                pert_dist[to_idx][from_idx] = 10_000_000.0
                pert_dur[to_idx][from_idx] = 100_000.0

            solver = CVRPTWSolver(
                distance_matrix=pert_dist,
                duration_matrix=pert_dur,
                depot=request.depot,
                stops=request.stops,
                fleet=request.fleet,
                enforce_guidelines=True,
                departure_time_sec=departure_sec,
                region=region
            )
            disrupted_sol = solver.solve()
            if disrupted_sol:
                sim_cost, sim_duration = cls._calc_solution_metrics(disrupted_sol, request.fleet)
                unserved_stops_count = len(disrupted_sol.get("dropped_stops", []))
                status = "REROUTED_SUCCESSFULLY" if sim_cost != baseline_cost else "COMPLIANT"
                action = f"Rerouted fleet around closed corridor between nodes {from_idx} and {to_idx}."
            else:
                status = "INFEASIBLE"
                sim_cost = baseline_cost
                sim_duration = baseline_duration
                unserved_stops_count = len(request.stops)
                action = f"Closure between nodes {from_idx} and {to_idx} isolates stops; access impossible."

        elif scenario == "LEG_DELAY":
            delay_mins = params.get("delay_minutes", 60)
            delay_sec = delay_mins * 60.0
            delay_node = params.get("delay_node_index", 1)
            title = f"Corridor Congestion / Leg Delay (+{delay_mins}m)"

            pert_dur = [row[:] for row in base_dur_matrix]
            if 0 <= delay_node < len(pert_dur):
                for i in range(len(pert_dur)):
                    pert_dur[i][delay_node] += delay_sec

            solver = CVRPTWSolver(
                distance_matrix=dist_matrix,
                duration_matrix=pert_dur,
                depot=request.depot,
                stops=request.stops,
                fleet=request.fleet,
                enforce_guidelines=True,
                departure_time_sec=departure_sec,
                region=region
            )
            disrupted_sol = solver.solve()
            if disrupted_sol:
                sim_cost, sim_duration = cls._calc_solution_metrics(disrupted_sol, request.fleet)
                unserved_stops_count = len(disrupted_sol.get("dropped_stops", []))
                status = "COMPLIANT"
                action = f"Fleet schedules adjusted to absorb {delay_mins} min delay on node {delay_node}."
            else:
                status = "VIOLATION_DETECTED"
                sim_cost = baseline_cost + (delay_mins * 12.0) + reg_engine.violation_fine_inr
                sim_duration = baseline_duration + (delay_mins / 60.0)
                missed_deadlines_count = 1
                action = "Delay pushes vehicle into municipal peak ban or misses delivery deadline. Reschedule or shift cargo."
                violations.append(RuleViolationDetail(
                    vehicle_id=request.fleet[0].vehicle_id if request.fleet else "VEH-01",
                    rule_breached=f"{region} Road Restriction Window Conflict",
                    location=f"Stop {delay_node}",
                    scheduled_arrival="Delayed Window",
                    legal_hours_window="Outside Peak Hours",
                    penalty_fine_inr=reg_engine.violation_fine_inr,
                    delay_minutes=float(delay_mins)
                ))

        elif scenario == "URGENT_STOP":
            urgent_data = params.get("urgent_stop", {})
            if urgent_data:
                new_stop = DeliveryStop(
                    stop_id=urgent_data.get("stop_id", "URGENT-01"),
                    name=urgent_data.get("name", "Urgent Drop"),
                    lat=urgent_data.get("lat", request.depot.lat + 0.05),
                    lon=urgent_data.get("lon", request.depot.lon + 0.05),
                    demand_kg=urgent_data.get("demand_kg", 150.0),
                    time_window_start_sec=urgent_data.get("time_window_start_sec", 28800),
                    time_window_end_sec=urgent_data.get("time_window_end_sec", 64800)
                )
            else:
                new_stop = DeliveryStop(
                    stop_id="URGENT-01",
                    name="Urgent Hospital Supply",
                    lat=request.depot.lat + 0.02,
                    lon=request.depot.lon + 0.02,
                    demand_kg=100.0,
                    time_window_start_sec=28800,
                    time_window_end_sec=64800
                )
            disrupted_stops = request.stops + [new_stop]
            new_coords = [[request.depot.lat, request.depot.lon]] + [[s.lat, s.lon] for s in disrupted_stops]
            new_dist, new_dur, _ = await OSRMService.get_matrices(new_coords)

            solver = CVRPTWSolver(
                distance_matrix=new_dist,
                duration_matrix=new_dur,
                depot=request.depot,
                stops=disrupted_stops,
                fleet=request.fleet,
                enforce_guidelines=True,
                departure_time_sec=departure_sec,
                region=region
            )
            disrupted_sol = solver.solve()
            title = "Urgent Delivery Added on Active Route"
            if disrupted_sol:
                sim_cost, sim_duration = cls._calc_solution_metrics(disrupted_sol, request.fleet)
                unserved_stops_count = len(disrupted_sol.get("dropped_stops", []))
                if unserved_stops_count == 0:
                    status = "COMPLIANT"
                    action = f"Successfully inserted urgent stop {new_stop.name} into active fleet itinerary."
                else:
                    status = "VIOLATION_DETECTED"
                    action = f"Urgent stop caused {unserved_stops_count} stops to be dropped due to time/capacity bounds."
            else:
                status = "INFEASIBLE"
                sim_cost = baseline_cost
                sim_duration = baseline_duration
                unserved_stops_count = len(disrupted_stops)
                action = f"Cannot accommodate urgent delivery {new_stop.name} within existing vehicle capacities and time windows."

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
            title = "Custom Delivery Scenario on Active Route"
            action = "Assign the new pickup stop to the nearest Tata Ace van that has remaining weight space."

        cost_diff = sim_cost - baseline_cost
        dur_diff = sim_duration - baseline_duration

        ai_recommendation, engine_name, is_ai = await cls._query_llm(
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
            unserved_stops_count=unserved_stops_count,
            missed_deadlines_count=missed_deadlines_count,
            fines_avoided_inr=fines_avoided_inr,
            violations=violations,
            ai_advisory_recommendation=ai_recommendation,
            ai_advisory_explanation=ai_recommendation,
            is_ai_generated=is_ai,
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
        violations: list[RuleViolationDetail],
        suggested_action: str,
        custom_problem: str | None = None
    ) -> tuple[str, str, bool]:
        if custom_problem and custom_problem.strip():
            user_prompt = (
                f"Custom Driver Problem: {custom_problem}\n"
                f"Evaluation Status: {status}\n"
                f"Cost Variance: Rs {cost_diff:+.2f}\n"
                f"Time Variance: {dur_diff:+.2f} hours\n"
                f"Violations: {[v.rule_breached for v in violations]}\n"
                f"Recommended Operational Action: {suggested_action}\n"
                f"Write the 3-sentence operational guidance referencing only the above computed values."
            )
        else:
            user_prompt = (
                f"Scenario: {scenario_title}\n"
                f"Status: {status}\n"
                f"Cost Difference: Rs {cost_diff:+.2f}\n"
                f"Time Difference: {dur_diff:+.2f} hours\n"
                f"Violations: {[v.rule_breached for v in violations]}\n"
                f"Recommended Action: {suggested_action}\n"
                f"Write the 3-sentence operational driver advice referencing only the above computed values."
            )

        groq_key = settings.GROQ_API_KEY
        if groq_key:
            for model_candidate in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
                try:
                    async with httpx.AsyncClient(timeout=4.0) as client:
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
                            return text, f"Groq Llama ({model_candidate})", True
                except Exception as e:
                    logger.warning(f"Groq API call failed on {model_candidate}: {e}")

        # Deterministic rule fallback cleanly handles missing GROQ_API_KEY, API rate limits, or timeouts
        if status == "VIOLATION_DETECTED":
            fine_str = f"Rs {violations[0].penalty_fine_inr:,.0f}" if violations else "a substantial"
            advice = (
                f"The vehicle faces a municipal peak-hour restriction or delay. "
                f"Continuing risks an immediate {fine_str} police penalty and {dur_diff:+.1f} hours of delay. "
                f"{suggested_action}"
            )
        elif status == "INFEASIBLE":
            advice = (
                f"Dispatch requirements cannot be satisfied under operational constraints. "
                f"Routing failed with unserved demand under time-window or vehicle limits. "
                f"{suggested_action}"
            )
        elif status == "REROUTED_SUCCESSFULLY":
            advice = (
                f"The route has been successfully recalculated around active corridor disruptions. "
                f"Expected cost change is Rs {cost_diff:+.0f} with a time shift of {dur_diff:+.1f} hours. "
                f"{suggested_action}"
            )
        else:
            advice = (
                f"The situation has been evaluated against regional road rules. "
                f"Expected cost change is Rs {cost_diff:+.0f} with a time shift of {dur_diff:+.1f} hours. "
                f"{suggested_action}"
            )

        return advice, "RouteOpt Deterministic Rules (Fallback)", False

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
