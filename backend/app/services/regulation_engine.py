"""
Regional Government Road Guidelines Engine
Loads structured municipal regulations from backend/app/data/regulations.json.
Maintains verified citations for Mumbai MMRDA, with other jurisdictions marked demo/assumption.
"""

import os
import json
from typing import Tuple, List, Dict, Any, Optional
import logging
from backend.app.models.fleet_v2 import CommercialVehicleSpec, VehicleClass

logger = logging.getLogger("routeopt.regulations")

DATA_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "regulations.json")

class RegionalRegulationEngine:
    _cached_data = None

    @classmethod
    def _load_data(cls) -> Dict[str, Any]:
        if cls._cached_data is None:
            if os.path.exists(DATA_FILE_PATH):
                try:
                    with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
                        cls._cached_data = json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load regulations.json: {e}")
                    cls._cached_data = {}
            else:
                cls._cached_data = {}
        return cls._cached_data

    def __init__(self, region: str = "MUMBAI_MMRDA"):
        self.region = (region or "MUMBAI_MMRDA").upper()
        data = self._load_data().get("regions", {})

        if "PUNE" in self.region:
            reg_info = data.get("PUNE_PMC", {})
            self.region_key = "PUNE_PMC"
        elif "NAGPUR" in self.region:
            reg_info = data.get("NAGPUR_NMC", {})
            self.region_key = "NAGPUR_NMC"
        else:
            reg_info = data.get("MUMBAI_MMRDA", {})
            self.region_key = "MUMBAI_MMRDA"

        self.name = reg_info.get("name", "Metropolitan Area")
        self.status = reg_info.get("status", "demo")
        self.citations = reg_info.get("citations", [])

        # Time restrictions
        time_restrictions = reg_info.get("time_restrictions", [])
        if len(time_restrictions) >= 2:
            self.morning_ban_start = time_restrictions[0]["start_sec"]
            self.morning_ban_end = time_restrictions[0]["end_sec"]
            self.morning_ban_label = time_restrictions[0]["name"]

            self.evening_ban_start = time_restrictions[1]["start_sec"]
            self.evening_ban_end = time_restrictions[1]["end_sec"]
            self.evening_ban_label = time_restrictions[1]["name"]
        else:
            # Verified Mumbai default fallback
            self.morning_ban_start = 28800
            self.morning_ban_end = 41400
            self.morning_ban_label = "Morning Peak HCV Ban (08:00 AM - 11:30 AM)"
            self.evening_ban_start = 61200
            self.evening_ban_end = 77400
            self.evening_ban_label = "Evening Peak Severe HCV Ban (05:00 PM - 09:30 PM)"

        # Infrastructure limits
        infra = reg_info.get("infrastructure_limits", {})
        self.flyover_height_limit_m = infra.get("flyover_height_limit_m", 2.5)
        self.bridge_gvw_limit_tonnes = infra.get("bridge_gvw_limit_tonnes", 7.5 if "MUMBAI" in self.region_key else 5.0)

        # Penalties
        penalties = reg_info.get("penalties", {})
        self.violation_fine_inr = penalties.get("violation_fine_inr", 20000.0)
        self.legal_basis = penalties.get("legal_basis", "Motor Vehicles Act, 1988")

    def check_time_in_no_entry_window(self, clock_seconds: int) -> Tuple[bool, str]:
        """
        Verifies if arrival time falls into Heavy Goods Vehicle (HGV/HCV) no-entry ban hours.
        """
        sec = clock_seconds % 86400
        if self.morning_ban_start <= sec <= self.morning_ban_end:
            return True, self.morning_ban_label
        elif self.evening_ban_start <= sec <= self.evening_ban_end:
            return True, self.evening_ban_label
        return False, "Unrestricted Entry"

    def check_vehicle_access(self, vehicle: CommercialVehicleSpec, is_flyover: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Verifies whether vehicle height and weight comply with structural barriers.
        """
        if is_flyover and vehicle.height_meters > self.flyover_height_limit_m:
            return False, f"Vehicle height ({vehicle.height_meters}m) exceeds {self.flyover_height_limit_m}m flyover clearance gantry"
        
        if vehicle.gross_vehicle_weight_tonnes > self.bridge_gvw_limit_tonnes:
            return False, f"Vehicle GVW ({vehicle.gross_vehicle_weight_tonnes}T) exceeds {self.bridge_gvw_limit_tonnes}T bridge load capacity"
            
        return True, None

    def get_guideline_summary(self) -> Dict[str, Any]:
        """
        Returns structured regulatory summary with explicit verification status and sources.
        """
        return {
            "region": self.region_key,
            "region_name": self.name,
            "status": self.status,
            "citations": self.citations,
            "rules": [
                {
                    "title": self.morning_ban_label,
                    "applies_to": "Heavy Freight Trucks (MCV/HCV > 3.5T GVW)",
                    "restricted_hours": [f"{self.morning_ban_start//3600:02d}:{(self.morning_ban_start%3600)//60:02d} - {self.morning_ban_end//3600:02d}:{(self.morning_ban_end%3600)//60:02d}"],
                    "exempt_vehicles": "Delivery Vans (LCVs like Tata Ace, GVW < 3.5T)",
                    "penalty": f"₹{self.violation_fine_inr:,.0f} fine ({self.legal_basis})",
                    "status": self.status
                },
                {
                    "title": self.evening_ban_label,
                    "applies_to": "Heavy Freight Trucks (MCV/HCV > 3.5T GVW)",
                    "restricted_hours": [f"{self.evening_ban_start//3600:02d}:{(self.evening_ban_start%3600)//60:02d} - {self.evening_ban_end//3600:02d}:{(self.evening_ban_end%3600)//60:02d}"],
                    "exempt_vehicles": "Delivery Vans (LCVs like Tata Ace, GVW < 3.5T)",
                    "penalty": f"₹{self.violation_fine_inr:,.0f} fine ({self.legal_basis})",
                    "status": self.status
                },
                {
                    "title": "Corridor Bridge & Flyover Structural Limits",
                    "applies_to": f"Vehicles > {self.bridge_gvw_limit_tonnes}T GVW or > {self.flyover_height_limit_m}m Height",
                    "impact": "Mandatory bypass via arterial surface corridors",
                    "status": self.status
                }
            ]
        }
