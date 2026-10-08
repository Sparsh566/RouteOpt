from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from enum import Enum

class VehicleClass(str, Enum):
    DELIVERY_VAN = "van"       # Light Commercial Vehicle (LCV: e.g. Tata Ace, Bolero Maxi Truck)
    FREIGHT_TRUCK = "truck"    # Medium/Heavy Commercial Vehicle (MCV/HCV: e.g. Tata 407, BharatBenz)

class CommercialVehicleSpec(BaseModel):
    vehicle_id: str = Field(..., description="Unique vehicle ID or registration")
    name: str = Field(default="Commercial Vehicle")
    vehicle_class: VehicleClass = Field(default=VehicleClass.DELIVERY_VAN)
    gross_vehicle_weight_tonnes: float = Field(default=2.5, description="GVW rating in metric tonnes")
    height_meters: float = Field(default=1.9, description="Vehicle height (checks flyover gantry clearance)")
    payload_capacity_kg: float = Field(..., gt=0, description="Max cargo weight limit")
    fixed_dispatch_cost: float = Field(default=250.0, description="Driver + daily fixed vehicle charge")
    running_cost_per_km: float = Field(default=12.0, description="Fuel + maintenance cost per km")
    color_hex: Optional[str] = Field(default="#06b6d4", description="Hex color for map display")

class DeliveryStop(BaseModel):
    stop_id: str
    name: str
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    demand_kg: float = Field(default=50.0, ge=0)
    time_window_start_sec: int = Field(default=0, description="Earliest delivery time in shift seconds")
    time_window_end_sec: int = Field(default=43200, description="Latest cutoff time in shift seconds (12h default)")
    service_duration_sec: int = Field(default=300, description="Unloading dock dwell time (default 5m)")
    is_in_restricted_urban_core: bool = Field(default=False, description="Inside municipal truck no-entry zone")

class DepotLocation(BaseModel):
    depot_id: str = Field(default="DEPOT-01")
    name: str = Field(default="Central Distribution Hub")
    lat: float
    lon: float
    operating_hours_sec: int = Field(default=43200)

class OptimizeV2Request(BaseModel):
    depot: DepotLocation
    stops: List[DeliveryStop] = Field(..., min_length=1)
    fleet: List[CommercialVehicleSpec] = Field(..., min_length=1)
    departure_time_iso: Optional[str] = Field(default="2026-10-09T08:30:00+05:30")
    region: str = Field(default="MUMBAI_MMRDA")
    apply_traffic_congestion: bool = Field(default=True)
    enforce_government_guidelines: bool = Field(default=True)

class StopVisit(BaseModel):
    stop_id: str
    name: str
    lat: float
    lon: float
    arrival_time_sec: int
    departure_time_sec: int
    waiting_time_sec: int
    current_load_kg: float
    clock_time_str: str

class VehicleRouteResult(BaseModel):
    vehicle_id: str
    vehicle_name: str
    vehicle_class: VehicleClass
    color_hex: str
    stops_visited: List[StopVisit]
    total_distance_m: float
    total_duration_s: float
    total_load_kg: float
    total_wait_s: float
    estimated_cost_inr: float
    route_geometry: Dict[str, Any]

class OptimizeV2Response(BaseModel):
    status: Literal["SUCCESS", "PARTIAL", "INFEASIBLE"]
    routes: List[VehicleRouteResult]
    dropped_stops: List[str] = Field(default_factory=list)
    total_fleet_distance_km: float
    total_fleet_duration_hours: float
    total_fleet_cost_inr: float
    traffic_factor_applied: float
    regulatory_compliance_notes: List[str]
    solve_duration_ms: float
