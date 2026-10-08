from pydantic import BaseModel, Field
from typing import List

class OptimizeRequest(BaseModel):
    depot: List[float] = Field(
        ..., 
        description="Depot coordinates [latitude, longitude]. Must contain exactly 2 floats.",
        min_length=2,
        max_length=2
    )
    stops: List[List[float]] = Field(
        ..., 
        description="List of delivery stop coordinates [[lat1, lon1], [lat2, lon2], ...].",
        min_length=1,
        max_length=10
    )

class OptimizeResponse(BaseModel):
    order: List[int] = Field(
        ..., 
        description="Optimal route order of stops, represented by their 0-indexed indices (where 0 is depot, 1+ are stops)."
    )
    distance_m: float = Field(
        ..., 
        description="Total route travel distance in meters."
    )
    duration_s: float = Field(
        ..., 
        description="Total route duration in seconds."
    )
    polyline: str = Field(
        ..., 
        description="Encoded polyline string representing the optimal route geometry."
    )
