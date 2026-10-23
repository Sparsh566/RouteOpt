"""
Synthetic Indian Urban Logistics Instance Generator (Mumbai & Pune)

Generates reproducible benchmark instances with configurable stop counts,
fleet mixes, time window tightness, and municipal restriction densities.
"""

import os
import sys
import json
import random
import argparse
from typing import Dict, Any, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.models.fleet_v2 import CommercialVehicleSpec, VehicleClass, DeliveryStop, DepotLocation

REGIONAL_CENTERS: dict[str, Any] = {
    "MUMBAI_MMRDA": {
        "depot": {"name": "Bhiwandi Central Hub", "lat": 19.2967, "lon": 73.0631},
        "lat_min": 18.92,
        "lat_max": 19.30,
        "lon_min": 72.80,
        "lon_max": 73.05,
        "urban_core_lat": (18.93, 19.10),
        "urban_core_lon": (72.81, 72.88)
    },
    "PUNE_PMC": {
        "depot": {"name": "Swargate Logistics Hub", "lat": 18.5018, "lon": 73.8586},
        "lat_min": 18.45,
        "lat_max": 18.62,
        "lon_min": 73.78,
        "lon_max": 73.95,
        "urban_core_lat": (18.51, 18.54),
        "urban_core_lon": (73.83, 73.87)
    }
}

WINDOW_DURATIONS = {
    "tight": 3600,     # 1 hour
    "moderate": 9000,  # 2.5 hours
    "wide": 18000      # 5 hours
}


def build_fleet(fleet_mix: str, total_demand_kg: float) -> List[Dict[str, Any]]:
    fleet = []
    if fleet_mix == "all_vans":
        num_vans = max(2, int((total_demand_kg / 800.0) + 1))
        for i in range(num_vans):
            fleet.append({
                "vehicle_id": f"VAN-{i+1:02d}",
                "name": f"Tata Ace Van {i+1}",
                "vehicle_class": "van",
                "payload_capacity_kg": 1200.0,
                "gross_vehicle_weight_tonnes": 2.2,
                "height_meters": 1.9,
                "fixed_dispatch_cost": 500.0,
                "running_cost_per_km": 14.0
            })
    elif fleet_mix == "all_trucks":
        num_trucks = max(1, int((total_demand_kg / 2800.0) + 1))
        for i in range(num_trucks):
            fleet.append({
                "vehicle_id": f"TRUCK-{i+1:02d}",
                "name": f"Tata 407 Truck {i+1}",
                "vehicle_class": "truck",
                "payload_capacity_kg": 4000.0,
                "gross_vehicle_weight_tonnes": 7.5,
                "height_meters": 3.1,
                "fixed_dispatch_cost": 1200.0,
                "running_cost_per_km": 24.0
            })
    else:  # "mixed"
        num_trucks = max(1, int((total_demand_kg * 0.5 / 2500.0) + 1))
        num_vans = max(2, int((total_demand_kg * 0.5 / 750.0) + 1))
        for i in range(num_trucks):
            fleet.append({
                "vehicle_id": f"TRUCK-{i+1:02d}",
                "name": f"Tata 407 Truck {i+1}",
                "vehicle_class": "truck",
                "payload_capacity_kg": 4000.0,
                "gross_vehicle_weight_tonnes": 7.5,
                "height_meters": 3.1,
                "fixed_dispatch_cost": 1200.0,
                "running_cost_per_km": 24.0
            })
        for i in range(num_vans):
            fleet.append({
                "vehicle_id": f"VAN-{i+1:02d}",
                "name": f"Tata Ace Van {i+1}",
                "vehicle_class": "van",
                "payload_capacity_kg": 1200.0,
                "gross_vehicle_weight_tonnes": 2.2,
                "height_meters": 1.9,
                "fixed_dispatch_cost": 500.0,
                "running_cost_per_km": 14.0
            })
    return fleet


def generate_instance(
    seed: int = 42,
    stop_count: int = 25,
    region: str = "MUMBAI_MMRDA",
    fleet_mix: str = "mixed",
    window_tightness: str = "moderate",
    restriction_density: float = 0.4
) -> Dict[str, Any]:
    """
    Deterministically generates a benchmark logistics scenario.
    """
    rng = random.Random(seed)
    reg_cfg = REGIONAL_CENTERS.get(region, REGIONAL_CENTERS["MUMBAI_MMRDA"])
    w_dur = WINDOW_DURATIONS.get(window_tightness, 9000)

    depot_data = {
        "depot_id": f"DEPOT-{region[:3]}",
        "name": reg_cfg["depot"]["name"],
        "lat": reg_cfg["depot"]["lat"],
        "lon": reg_cfg["depot"]["lon"],
        "operating_hours_sec": 43200
    }

    stops = []
    total_demand = 0.0

    shift_start_sec = 30600  # 08:30 AM
    shift_end_sec = shift_start_sec + 43200

    u_lat_min: float = float(reg_cfg["urban_core_lat"][0])
    u_lat_max: float = float(reg_cfg["urban_core_lat"][1])
    u_lon_min: float = float(reg_cfg["urban_core_lon"][0])
    u_lon_max: float = float(reg_cfg["urban_core_lon"][1])
    lat_min: float = float(reg_cfg["lat_min"])
    lat_max: float = float(reg_cfg["lat_max"])
    lon_min: float = float(reg_cfg["lon_min"])
    lon_max: float = float(reg_cfg["lon_max"])

    for idx in range(1, stop_count + 1):
        is_restricted = rng.random() < restriction_density
        if is_restricted:
            lat = rng.uniform(u_lat_min, u_lat_max)
            lon = rng.uniform(u_lon_min, u_lon_max)
        else:
            lat = rng.uniform(lat_min, lat_max)
            lon = rng.uniform(lon_min, lon_max)

        demand = round(rng.uniform(80.0, 450.0), 1)
        total_demand += demand

        # Window generation within shift
        earliest_start = shift_start_sec + int(rng.uniform(0, 21600))
        latest_end = min(shift_end_sec, earliest_start + w_dur)

        stops.append({
            "stop_id": f"S{idx:03d}",
            "name": f"Customer Delivery {idx:03d}",
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "demand_kg": demand,
            "time_window_start_sec": earliest_start,
            "time_window_end_sec": latest_end,
            "service_duration_sec": 600,
            "is_in_restricted_urban_core": is_restricted
        })

    fleet = build_fleet(fleet_mix, total_demand)

    instance = {
        "instance_id": f"{region.lower()}_{stop_count}_{fleet_mix}_s{seed}",
        "metadata": {
            "seed": seed,
            "stop_count": stop_count,
            "region": region,
            "fleet_mix": fleet_mix,
            "window_tightness": window_tightness,
            "restriction_density": restriction_density,
            "total_demand_kg": round(total_demand, 2)
        },
        "depot": depot_data,
        "fleet": fleet,
        "stops": stops
    }
    return instance


def save_instance_to_file(instance: Dict[str, Any], output_dir: Optional[str] = None) -> str:
    if output_dir is None:
        output_dir = os.path.join(PROJECT_ROOT, "benchmarks", "instances")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"{instance['instance_id']}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(instance, f, indent=2)

    return filepath


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic Indian logistics benchmark instances")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--stops", type=int, default=25, choices=[10, 25, 50], help="Stop count")
    parser.add_argument("--region", type=str, default="MUMBAI_MMRDA", choices=["MUMBAI_MMRDA", "PUNE_PMC"])
    parser.add_argument("--fleet-mix", type=str, default="mixed", choices=["all_vans", "all_trucks", "mixed"])
    parser.add_argument("--tightness", type=str, default="moderate", choices=["tight", "moderate", "wide"])
    parser.add_argument("--restriction-density", type=float, default=0.4)
    parser.add_argument("--out", type=str, default=None, help="Output directory")

    args = parser.parse_args()
    inst = generate_instance(
        seed=args.seed,
        stop_count=args.stops,
        region=args.region,
        fleet_mix=args.fleet_mix,
        window_tightness=args.tightness,
        restriction_density=args.restriction_density
    )
    saved_path = save_instance_to_file(inst, args.out)
    print(f"Generated benchmark instance saved to: {saved_path}")
