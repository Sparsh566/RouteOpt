"""
Regional Government Road Guidelines Engine
Encodes Mumbai MMRDA, Pune PMC, and Indian Highway traffic regulations.
"""

from typing import Tuple, List, Dict, Any, Optional
from backend.app.models.fleet_v2 import CommercialVehicleSpec, VehicleClass, DeliveryStop

class RegionalRegulationEngine:
    def __init__(self, region: str = "MUMBAI_MMRDA"):
        self.region = region
        # No-entry hours in seconds from midnight (00:00)
        # Morning peak ban: 08:00 (28800) to 11:30 (41400)
        self.morning_ban_start = 28800
        self.morning_ban_end = 41400
        # Evening peak ban: 17:00 (61200) to 21:30 (77400)
        self.evening_ban_start = 61200
        self.evening_ban_end = 77400
        
        # Physical road barriers
        self.flyover_height_limit_m = 2.5
        self.bridge_gvw_limit_tonnes = 7.5
        self.violation_fine_inr = 20000.0

    def check_time_in_no_entry_window(self, clock_seconds: int) -> Tuple[bool, str]:
        """
        Verifies if arrival time falls into Heavy Goods Vehicle (HGV/HCV) no-entry ban hours.
        """
        sec = clock_seconds % 86400
        if self.morning_ban_start <= sec <= self.morning_ban_end:
            return True, "Morning Peak HCV Ban (08:00 AM - 11:30 AM)"
        elif self.evening_ban_start <= sec <= self.evening_ban_end:
            return True, "Evening Peak Severe HCV Ban (05:00 PM - 09:30 PM)"
        return False, "Unrestricted Entry"

    def check_vehicle_access(self, vehicle: CommercialVehicleSpec, is_flyover: bool) -> Tuple[bool, Optional[str]]:
        """
        Verifies whether vehicle height and weight comply with structural barriers.
        """
        if is_flyover and vehicle.height_meters > self.flyover_height_limit_m:
            return False, f"Vehicle height ({vehicle.height_meters}m) exceeds 2.5m flyover clearance gantry"
        
        if vehicle.gross_vehicle_weight_tonnes > self.bridge_gvw_limit_tonnes:
            return False, f"Vehicle GVW ({vehicle.gross_vehicle_weight_tonnes}T) exceeds 7.5T bridge load capacity"
            
        return True, None

    def get_guideline_summary(self) -> Dict[str, Any]:
        return {
            "region": self.region,
            "rules": [
                {
                    "title": "HCV Urban Entry Prohibition (Sec 115 Motor Vehicles Act)",
                    "applies_to": "Freight Trucks (MCV/HCV > 7.5T GVW)",
                    "restricted_hours": ["08:00 AM - 11:30 AM", "05:00 PM - 09:30 PM"],
                    "exempt_vehicles": "Delivery Vans (LCVs < 3.5T GVW like Tata Ace)",
                    "penalty": f"₹{self.violation_fine_inr:,.0f} fine + vehicle impound risk"
                },
                {
                    "title": "Flyover Overhead Height Gantries",
                    "applies_to": "All Commercial Vehicles > 2.5m height",
                    "impact": "Tall trucks forced onto ground-level arterial roads, incurring +35% urban travel time"
                },
                {
                    "title": "Arterial Bridge Weight Rating",
                    "applies_to": "Vehicles exceeding 7.5T Gross Vehicle Weight",
                    "impact": "Mandatory detour via peripheral bypass highways"
                }
            ]
        }
