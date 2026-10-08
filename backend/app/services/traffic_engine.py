"""
Indian Peak-Hour Traffic Congestion Matrix Multiplier
"""

from datetime import datetime
from typing import List, Union

class TrafficEngine:
    @staticmethod
    def get_congestion_factor(departure_time: Union[datetime, str, float, int] = None) -> float:
        """
        Calculates empirical traffic degradation factor for Indian urban corridors.
        Supports datetime object, ISO string, or float hour (e.g. 8.5 for 8:30 AM).
        """
        if departure_time is None:
            departure_time = datetime.now()

        if isinstance(departure_time, (int, float)):
            hour = float(departure_time)
        elif isinstance(departure_time, str):
            try:
                dt = datetime.fromisoformat(departure_time)
                hour = dt.hour + (dt.minute / 60.0)
            except Exception:
                hour = 8.5
        elif isinstance(departure_time, datetime):
            hour = departure_time.hour + (departure_time.minute / 60.0)
        else:
            hour = 8.5

        if 8.5 <= hour <= 11.5:
            return 1.65  # Morning peak traffic
        elif 17.5 <= hour <= 21.0:
            return 1.85  # Severe evening peak traffic
        elif 12.0 <= hour <= 16.5:
            return 1.20  # Afternoon normal traffic
        else:
            return 1.00  # Free-flow nighttime

    @classmethod
    def apply_traffic(cls, duration_matrix: List[List[float]], departure_iso: str = None) -> List[List[float]]:
        factor = cls.get_congestion_factor(departure_iso)
        n = len(duration_matrix)
        return [
            [0.0 if i == j else round(duration_matrix[i][j] * factor, 1) for j in range(n)]
            for i in range(n)
        ]
