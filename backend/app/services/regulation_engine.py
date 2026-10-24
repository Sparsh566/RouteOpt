"""
Regional Government Road Guidelines Engine
Loads structured municipal regulations from backend/app/data/regulations.json (all regions marked demo/assumption).
"""

import json
import logging
import os
import threading
from datetime import date, datetime, timezone
from typing import Any

from backend.app.models.fleet_v2 import CommercialVehicleSpec

logger = logging.getLogger("routeopt.regulations")

DATA_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "regulations.json")

def _is_point_in_polygon(lat: float, lon: float, polygon: list[list[float]]) -> bool:
    """Ray casting point-in-polygon algorithm to check if (lat, lon) is within polygon boundary."""
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    p1_lat, p1_lon = polygon[0]
    for i in range(1, n + 1):
        p2_lat, p2_lon = polygon[i % n]
        if (p1_lat > lat) != (p2_lat > lat):
            x_cross = (lat - p1_lat) * (p2_lon - p1_lon) / (p2_lat - p1_lat) + p1_lon
            if lon < x_cross:
                inside = not inside
        p1_lat, p1_lon = p2_lat, p2_lon
    return inside

class RegionalRegulationEngine:
    _cached_data: dict[str, Any] | None = None
    _lock = threading.Lock()

    @classmethod
    def _load_data(cls) -> dict[str, Any]:
        with cls._lock:
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

    def __init__(self, region: str = "MUMBAI_MMRDA", as_of_date: date | str | None = None):
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
        self.heavy_definition = reg_info.get("heavy_definition", "unspecified in sources")
        self.vans_exempt_note = reg_info.get("vans_exempt_note", "labeled demo assumption")

        # Determine reference date for validity check (Requirement 9)
        if isinstance(as_of_date, str):
            try:
                self.reference_date = datetime.fromisoformat(as_of_date.replace("Z", "+00:00")).date()
            except Exception:
                try:
                    self.reference_date = datetime.strptime(as_of_date[:10], "%Y-%m-%d").date()
                except Exception:
                    self.reference_date = datetime.now(timezone.utc).date()
        elif isinstance(as_of_date, date):
            self.reference_date = as_of_date
        else:
            self.reference_date = datetime.now(timezone.utc).date()

        # Parse time restrictions and evaluate validity check
        raw_restrictions = reg_info.get("time_restrictions", [])
        self.all_time_restrictions: list[dict[str, Any]] = []
        self.active_time_restrictions: list[dict[str, Any]] = []
        self.expired_time_restrictions: list[dict[str, Any]] = []

        today_str = self.reference_date.strftime("%Y-%m-%d")

        for item in raw_restrictions:
            rule = dict(item)
            is_expired = False
            valid_until_str = rule.get("valid_until")

            # Validity check: any rule whose valid_until is before today is ignored by the engine
            if valid_until_str:
                if valid_until_str < today_str:
                    is_expired = True

            if rule.get("status") == "expired":
                is_expired = True

            rule["is_expired"] = is_expired
            if is_expired:
                rule["ui_status"] = "expired, verify with traffic police"
                self.expired_time_restrictions.append(rule)
                # Expired rule is IGNORED by the engine for routing enforcement
            else:
                rule["ui_status"] = rule.get("status", "active")
                self.active_time_restrictions.append(rule)

            self.all_time_restrictions.append(rule)

        # Primary window bounds for backward-compatibility and solver integration
        citywide_active = [r for r in self.active_time_restrictions if r.get("scope") in ["citywide", "listed_city_roads"]]
        if not citywide_active:
            citywide_active = self.active_time_restrictions

        if len(citywide_active) >= 2:
            self.morning_ban_start = citywide_active[0]["start_sec"]
            self.morning_ban_end = citywide_active[0]["end_sec"]
            self.morning_ban_label = citywide_active[0]["name"]

            self.evening_ban_start = citywide_active[1]["start_sec"]
            self.evening_ban_end = citywide_active[1]["end_sec"]
            self.evening_ban_label = citywide_active[1]["name"]
        elif len(citywide_active) == 1:
            self.morning_ban_start = citywide_active[0]["start_sec"]
            self.morning_ban_end = citywide_active[0]["end_sec"]
            self.morning_ban_label = citywide_active[0]["name"]

            self.evening_ban_start = -1
            self.evening_ban_end = -1
            self.evening_ban_label = ""
        else:
            self.morning_ban_start = -1
            self.morning_ban_end = -1
            self.morning_ban_label = "Expired Restriction (verify with traffic police)"
            self.evening_ban_start = -1
            self.evening_ban_end = -1
            self.evening_ban_label = ""

        # Restricted zones
        self.restricted_zones: list[dict[str, Any]] = reg_info.get("restricted_zones", [])

        # Infrastructure limits
        infra = reg_info.get("infrastructure_limits", {})
        self.flyover_height_limit_m = infra.get("flyover_height_limit_m", 2.5)
        self.bridge_gvw_limit_tonnes = infra.get("bridge_gvw_limit_tonnes", 7.5 if "MUMBAI" in self.region_key else 5.0)

        # Penalties
        penalties = reg_info.get("penalties", {})
        self.violation_fine_inr = penalties.get("violation_fine_inr", 20000.0)
        self.legal_basis = penalties.get("legal_basis", "Motor Vehicles Act, 1988")

    def is_coordinate_in_restricted_zone(self, lat: float, lon: float) -> bool:
        """
        Derives restricted urban core status by evaluating if (lat, lon) coordinates
        fall inside any municipal restricted zone boundary polygon using ray casting.
        Rules with no polygon boundary return False.
        """
        for zone in self.restricted_zones:
            polygon = zone.get("polygon", [])
            if polygon and _is_point_in_polygon(lat, lon, polygon):
                return True
        return False

    def is_peak_ban_active(self, arrival_time_sec: float) -> bool:
        """
        Unified peak-hour truck ban rule.
        Returns True if arrival timestamp falls within any ACTIVE citywide restriction window.
        Rules with specific scopes (e.g. SOUTH_MUMBAI, EASTERN_FREEWAY with no polygon)
        are corridor/zone rules and not evaluated as citywide peak bans.
        Expired rules (valid_until < reference_date) are ignored.
        """
        sec = int(arrival_time_sec) % 86400
        for rule in self.active_time_restrictions:
            if rule.get("scope") not in ["citywide", "listed_city_roads"]:
                continue
            start_s = rule.get("start_sec", 0)
            end_s = rule.get("end_sec", 0)
            if start_s <= sec <= end_s:
                return True
        return False

    def check_time_in_no_entry_window(self, clock_seconds: int) -> tuple[bool, str]:
        """
        Verifies if arrival time falls into active heavy commercial vehicle no-entry ban hours.
        Returns (is_banned, rule_name_or_expired_notice).
        """
        sec = clock_seconds % 86400
        for rule in self.active_time_restrictions:
            if rule.get("scope") not in ["citywide", "listed_city_roads"]:
                continue
            start_s = rule.get("start_sec", 0)
            end_s = rule.get("end_sec", 0)
            if start_s <= sec <= end_s:
                return True, rule.get("name", "Active Restriction Window")

        # Check if an expired rule covered this window to notify UI/dispatcher
        for rule in self.expired_time_restrictions:
            if rule.get("scope") not in ["citywide", "listed_city_roads"]:
                continue
            start_s = rule.get("start_sec", 0)
            end_s = rule.get("end_sec", 0)
            if start_s <= sec <= end_s:
                return False, f"{rule.get('name')}: expired, verify with traffic police"

        return False, "Unrestricted Entry"

    def check_vehicle_access(self, vehicle: CommercialVehicleSpec, is_flyover: bool = False) -> tuple[bool, str | None]:
        """
        Verifies whether vehicle height and weight comply with structural barriers.
        """
        if is_flyover and vehicle.height_meters > self.flyover_height_limit_m:
            return False, f"Vehicle height ({vehicle.height_meters}m) exceeds {self.flyover_height_limit_m}m flyover clearance gantry"

        if vehicle.gross_vehicle_weight_tonnes > self.bridge_gvw_limit_tonnes:
            return False, f"Vehicle GVW ({vehicle.gross_vehicle_weight_tonnes}T) exceeds {self.bridge_gvw_limit_tonnes}T bridge load capacity"

        return True, None

    def get_guideline_summary(self) -> dict[str, Any]:
        """
        Returns structured regulatory summary with explicit verification status,
        heavy definition, exemptions, and validity check ('expired, verify with traffic police').
        """
        formatted_rules = []
        for r in self.all_time_restrictions:
            is_exp = r.get("is_expired", False)
            status_text = "expired, verify with traffic police" if is_exp else r.get("status", "active")

            start_s = r.get("start_sec", 0)
            end_s = r.get("end_sec", 0)
            time_display = f"{start_s // 3600:02d}:{(start_s % 3600) // 60:02d} - {end_s // 3600:02d}:{(end_s % 3600) // 60:02d}"

            formatted_rules.append({
                "title": r.get("name", "Restriction Rule"),
                "scope": r.get("scope", "citywide"),
                "applies_to": f"Heavy Freight Trucks (definition: {self.heavy_definition})",
                "restricted_hours": [time_display],
                "exempt_vehicles": "Delivery Vans (exempt only as labeled demo assumption)" if "van" in r.get("exempt", []) else "None",
                "exemptions": r.get("exemptions", ["essential_goods", "emergency"]),
                "heavy_definition": self.heavy_definition,
                "status": status_text,
                "is_expired": is_exp,
                "valid_until": r.get("valid_until"),
                "effective": r.get("effective"),
                "source_type": r.get("source_type"),
                "source_reference": r.get("source_reference", "")
            })

        # Corridor structural limits
        formatted_rules.append({
            "title": "Corridor Bridge & Flyover Structural Limits",
            "scope": "bridges_and_flyovers",
            "applies_to": f"Vehicles > {self.bridge_gvw_limit_tonnes}T GVW or > {self.flyover_height_limit_m}m Height",
            "impact": "Mandatory bypass via arterial surface corridors",
            "status": self.status,
            "is_expired": False
        })

        return {
            "region": self.region_key,
            "region_name": self.name,
            "status": self.status,
            "citations": self.citations,
            "heavy_definition": self.heavy_definition,
            "vans_exempt_note": self.vans_exempt_note,
            "reference_date": self.reference_date.isoformat(),
            "rules": formatted_rules
        }
