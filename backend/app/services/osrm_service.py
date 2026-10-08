"""
OSRM Routing and Matrix Service with Haversine Road-Winding Fallback
"""

import httpx
import math
from typing import List, Tuple, Dict, Any
import logging
from backend.app.config import settings

logger = logging.getLogger("routeopt.osrm")

class OSRMService:
    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371000.0  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return R * c

    @classmethod
    async def get_matrices(cls, coordinates: List[List[float]]) -> Tuple[List[List[float]], List[List[float]], bool]:
        """
        Coordinates in [[lat, lon], ...]
        Returns: (distance_matrix_meters, duration_matrix_seconds, is_real_osrm)
        """
        n = len(coordinates)
        if n < 2:
            return [[0.0]], [[0.0]], False

        # Attempt OSRM Table query
        # OSRM expects lon,lat format: /table/v1/driving/{lon1},{lat1};{lon2},{lat2}...
        coords_str = ";".join([f"{lon},{lat}" for lat, lon in coordinates])
        url = f"{settings.OSRM_URL}/table/v1/driving/{coords_str}?annotations=distance,duration"

        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    if "distances" in data and "durations" in data:
                        return data["distances"], data["durations"], True
        except Exception as e:
            logger.info(f"OSRM service unavailable ({e}); utilizing high-fidelity road winding fallback.")

        # High-Fidelity Fallback: Haversine multiplied by urban detour winding coefficient (1.35x)
        # Urban average commercial vehicle speed: 30 km/h = 8.33 m/s
        WINDING_FACTOR = 1.35
        URBAN_SPEED_MPS = 8.33

        dist_matrix = [[0.0] * n for _ in range(n)]
        dur_matrix = [[0.0] * n for _ in range(n)]

        for i in range(n):
            for j in range(n):
                if i != j:
                    crow_fly = cls._haversine(coordinates[i][0], coordinates[i][1], coordinates[j][0], coordinates[j][1])
                    road_dist = crow_fly * WINDING_FACTOR
                    dist_matrix[i][j] = round(road_dist, 1)
                    dur_matrix[i][j] = round(road_dist / URBAN_SPEED_MPS, 1)

        return dist_matrix, dur_matrix, False

    @classmethod
    async def get_route_geometry(cls, coordinates: List[List[float]]) -> Dict[str, Any]:
        """
        Fetches route geometry GeoJSON from OSRM Route service, or creates straight-line GeoJSON.
        """
        if len(coordinates) < 2:
            return {"type": "LineString", "coordinates": []}

        coords_str = ";".join([f"{lon},{lat}" for lat, lon in coordinates])
        url = f"{settings.OSRM_URL}/route/v1/driving/{coords_str}?overview=full&geometries=geojson"

        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    if "routes" in data and len(data["routes"]) > 0:
                        return data["routes"][0]["geometry"]
        except Exception:
            pass

        # Fallback GeoJSON: list of [lon, lat] pairs
        return {
            "type": "LineString",
            "coordinates": [[lon, lat] for lat, lon in coordinates]
        }
