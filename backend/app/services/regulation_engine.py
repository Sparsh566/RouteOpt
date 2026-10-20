"""
Regional Government Road Guidelines Engine
Encodes Mumbai MMRDA, Pune PMC, and Indian Highway traffic regulations.
"""

from typing import Tuple, List, Dict, Any, Optional
from backend.app.models.fleet_v2 import CommercialVehicleSpec, VehicleClass, DeliveryStop

class RegionalRegulationEngine:
    def __init__(self, region: str = "MUMBAI_MMRDA"):
        self.region = (region or "MUMBAI_MMRDA").upper()
        
        if "PUNE" in self.region:
            # Pune Municipal Corporation (PMC) Regulations
            # Morning ban: 09:00 AM (32400s) to 12:00 PM (43200s)
            self.morning_ban_start = 32400
            self.morning_ban_end = 43200
            # Evening ban: 04:30 PM (59400s) to 08:30 PM (73800s)
            self.evening_ban_start = 59400
            self.evening_ban_end = 73800
            self.flyover_height_limit_m = 2.5
            self.bridge_gvw_limit_tonnes = 5.0
            self.violation_fine_inr = 15000.0
            self.morning_ban_label = "Pune PMC Morning Peak HCV Ban (09:00 AM - 12:00 PM)"
            self.evening_ban_label = "Pune PMC Evening Peak HCV Ban (04:30 PM - 08:30 PM)"
        else:
            # Mumbai MMRDA Regulations (Default)
            # Morning ban: 08:00 AM (28800s) to 11:30 AM (41400s)
            self.morning_ban_start = 28800
            self.morning_ban_end = 41400
            # Evening ban: 05:00 PM (61200s) to 09:30 PM (77400s)
            self.evening_ban_start = 61200
            self.evening_ban_end = 77400
            self.flyover_height_limit_m = 2.5
            self.bridge_gvw_limit_tonnes = 7.5
            self.violation_fine_inr = 20000.0
            self.morning_ban_label = "Morning Peak HCV Ban (08:00 AM - 11:30 AM)"
            self.evening_ban_label = "Evening Peak Severe HCV Ban (05:00 PM - 09:30 PM)"

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

    def check_vehicle_access(self, vehicle: CommercialVehicleSpec, is_flyover: bool) -> Tuple[bool, Optional[str]]:
        """
        Verifies whether vehicle height and weight comply with structural barriers.
        """
        if is_flyover and vehicle.height_meters > self.flyover_height_limit_m:
            return False, f"Vehicle height ({vehicle.height_meters}m) exceeds {self.flyover_height_limit_m}m flyover clearance gantry"
        
        if vehicle.gross_vehicle_weight_tonnes > self.bridge_gvw_limit_tonnes:
            return False, f"Vehicle GVW ({vehicle.gross_vehicle_weight_tonnes}T) exceeds {self.bridge_gvw_limit_tonnes}T bridge load capacity"
            
        return True, None

    def get_guideline_summary(self) -> Dict[str, Any]:
        if "PUNE" in self.region:
            return {
                "region": "PUNE_PMC",
                "rules": [
                    {
                        "title": "Pune PMC Peak-Hour Commercial Freight Prohibition",
                        "applies_to": "Heavy Goods Vehicles (HCV/MCV > 5.0T GVW)",
                        "restricted_hours": ["09:00 AM - 12:00 PM", "04:30 PM - 08:30 PM"],
                        "exempt_vehicles": "Delivery Vans (LCVs < 3.5T GVW like Tata Ace)",
                        "penalty": f"₹{self.violation_fine_inr:,.0f} fine + vehicle impound risk"
                    },
                    {
                        "title": "Heritage Bridge Axle Limits (Old Lakdi Pul & Shivaji Bridge)",
                        "applies_to": "Vehicles exceeding 5.0T Gross Vehicle Weight",
                        "impact": "Mandatory bypass via Katraj-Dehu Road Bypass or Swargate Outer Ring"
                    },
                    {
                        "title": "Swargate & Pune University Flyover Clearance",
                        "applies_to": "All Commercial Vehicles > 2.5m height",
                        "impact": "Tall freight trucks forced to ground-level choke points"
                    }
                ]
            }

        return {
            "region": "MUMBAI_MMRDA",
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
