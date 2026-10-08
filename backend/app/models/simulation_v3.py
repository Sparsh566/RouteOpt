from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from backend.app.models.fleet_v2 import CommercialVehicleSpec, DeliveryStop, DepotLocation

class SimulationScenarioRequest(BaseModel):
    scenario_type: str = Field(default="CUSTOM_SITUATION", description="Selected preset or CUSTOM_SITUATION")
    custom_situation_text: Optional[str] = Field(default=None, description="Free-text custom situation described by the user")
    scenario_title: Optional[str] = None
    depot: DepotLocation
    fleet: List[CommercialVehicleSpec]
    stops: List[DeliveryStop]
    departure_time_iso: str = Field(default="2026-10-09T08:30:00+05:30")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Scenario inputs (e.g. delay_minutes, new_order, low_bridge_location)"
    )

class RuleViolationDetail(BaseModel):
    vehicle_id: str
    rule_breached: str
    location: str
    scheduled_arrival: str
    legal_hours_window: str
    penalty_fine_inr: float
    delay_minutes: float

class SimulationScenarioResponse(BaseModel):
    scenario_type: str
    scenario_title: str
    feasibility_status: Literal["COMPLIANT", "VIOLATION_DETECTED", "REROUTED_SUCCESSFULLY"]
    baseline_cost_inr: float
    simulated_cost_inr: float
    cost_difference_inr: float
    baseline_duration_hours: float
    simulated_duration_hours: float
    violations: List[RuleViolationDetail]
    ai_advisory_recommendation: str
    suggested_action: str
    llm_engine_used: str
    simulation_duration_ms: float
