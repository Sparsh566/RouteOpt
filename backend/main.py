# Student Name: Aditya khiratkar
# PRN: 24070521071
# Role: Member 2 (Optimization Engine / OR-Tools Solver)

import math
import logging
from typing import List, Dict, Any, Optional
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RouteOpt")

app = FastAPI(
    title="RouteOpt API",
    description="Multi-Stop Delivery Route Optimization using Google OR-Tools and OpenStreetMap Data",
    version="1.0.0"
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class Location(BaseModel):
    lat: float
    lng: float
    demand: int
    name: str

class OptimizeRequest(BaseModel):
    locations: List[Location]
    num_vehicles: int
    vehicle_capacities: List[int]

# Helper: Haversine distance between two coordinates (fallback in meters)
def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    R = 6371000  # Radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return int(R * c)

# Fetch Distance and Duration matrix from OSRM
def fetch_osrm_matrices(locations: List[Location]) -> tuple[List[List[int]], List[List[int]], bool]:
    """
    Queries the public OSRM table API to retrieve distance and duration matrices.
    Returns (distance_matrix, duration_matrix, success_flag).
    Coordinates in OSRM must be formatted as: lon,lat;lon,lat;...
    """
    coords_str = ";".join([f"{loc.lng},{loc.lat}" for loc in locations])
    url = f"http://router.project-osrm.org/table/v1/driving/{coords_str}"
    params = {"annotations": "distance,duration"}

    try:
        logger.info(f"Querying OSRM Table API for {len(locations)} points...")
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "distances" in data and "durations" in data:
                # OSRM distances are in meters (float), convert to ints
                # OSRM durations are in seconds (float), convert to ints
                distances = [[int(val) if val is not None else 0 for val in row] for row in data["distances"]]
                durations = [[int(val) if val is not None else 0 for val in row] for row in data["durations"]]
                logger.info("OSRM matrices successfully retrieved.")
                return distances, durations, True
            
        logger.warning(f"OSRM returned unexpected status or structure: {response.status_code}")
    except Exception as e:
        logger.error(f"Error querying OSRM Table API: {e}")

    # Fallback: compute straight-line (Haversine) matrices
    logger.info("Falling back to Haversine distance calculations.")
    n = len(locations)
    distances = [[0] * n for _ in range(n)]
    durations = [[0] * n for _ in range(n)] # Assume constant speed of 10 m/s (36 km/h) for duration
    for i in range(n):
        for j in range(n):
            if i == j:
                distances[i][j] = 0
                durations[i][j] = 0
            else:
                dist = calculate_haversine_distance(
                    locations[i].lat, locations[i].lng,
                    locations[j].lat, locations[j].lng
                )
                distances[i][j] = dist
                durations[i][j] = int(dist / 10.0) # 10 meters per second

    return distances, durations, False

# Fetch detailed road routing geometry between list of coordinates from OSRM
def fetch_osrm_route_geometry(coords: List[Location]) -> Dict[str, Any]:
    """
    Gets detailed geometry (GeoJSON) from OSRM for a specific sequence of coordinates.
    """
    if len(coords) < 2:
        return {"type": "LineString", "coordinates": []}

    coords_str = ";".join([f"{loc.lng},{loc.lat}" for loc in coords])
    url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false"
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "routes" in data and len(data["routes"]) > 0:
                return data["routes"][0]["geometry"]
    except Exception as e:
        logger.error(f"Error fetching OSRM route geometry: {e}")

    # Fallback: simple line segments connecting the stops in order (geojson format expects [lon, lat])
    return {
        "type": "LineString",
        "coordinates": [[loc.lng, loc.lat] for loc in coords]
    }

# OR-Tools Solver
def solve_cvrp(
    distance_matrix: List[List[int]],
    duration_matrix: List[List[int]],
    demands: List[int],
    vehicle_capacities: List[int],
    num_vehicles: int,
    depot_index: int = 0
) -> Optional[Dict[str, Any]]:
    """
    Solves the Capacitated Vehicle Routing Problem (CVRP).
    """
    num_nodes = len(distance_matrix)
    manager = pywrapcp.RoutingIndexManager(num_nodes, num_vehicles, depot_index)
    routing = pywrapcp.RoutingModel(manager)

    # 1. Define Transit Callbacks (Distance & Duration)
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    def duration_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return duration_matrix[from_node][to_node]

    duration_callback_index = routing.RegisterTransitCallback(duration_callback)

    # 2. Add Capacity Constraints
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return demands[from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # null capacity slack
        vehicle_capacities,
        True,  # start cumulative to zero
        "Capacity"
    )

    # 3. Add Distance and Time Dimensions (to calculate cumulative distance/time per vehicle)
    routing.AddDimension(
        transit_callback_index,
        0,  # no slack
        1_000_000,  # max distance in meters (1000km)
        True,
        "Distance"
    )
    routing.AddDimension(
        duration_callback_index,
        3600,  # slack max 1 hour at each stop
        86400,  # max time in seconds (24 hours)
        True,
        "Time"
    )

    # 4. Set Search Parameters
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    # Guided Local Search is highly effective for CVRP
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = 3  # short timeout for responsive UI

    # Solve
    solution = routing.SolveWithParameters(search_parameters)

    if not solution:
        return None

    # 5. Extract Solution
    routes = []
    total_distance_m = 0
    total_duration_s = 0
    
    distance_dimension = routing.GetDimensionOrDie("Distance")
    time_dimension = routing.GetDimensionOrDie("Time")
    capacity_dimension = routing.GetDimensionOrDie("Capacity")

    for vehicle_id in range(num_vehicles):
        index = routing.Start(vehicle_id)
        route_nodes = []
        
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            route_nodes.append(node)
            index = solution.Value(routing.NextVar(index))
            
        # Add the ending depot node
        route_nodes.append(manager.IndexToNode(index))

        # Get stats for this route
        end_index = routing.End(vehicle_id)
        route_distance = solution.Value(distance_dimension.CumulVar(end_index))
        route_duration = solution.Value(time_dimension.CumulVar(end_index))
        route_load = solution.Value(capacity_dimension.CumulVar(end_index))

        total_distance_m += route_distance
        total_duration_s += route_duration

        # Only add the route if it actually services at least one customer (i.e. more than just Depot -> Depot)
        if len(route_nodes) > 2:
            routes.append({
                "vehicle_id": vehicle_id,
                "node_sequence": route_nodes,
                "distance_meters": route_distance,
                "duration_seconds": route_duration,
                "load": route_load,
                "capacity": vehicle_capacities[vehicle_id]
            })
        else:
            # Empty route
            routes.append({
                "vehicle_id": vehicle_id,
                "node_sequence": [],
                "distance_meters": 0,
                "duration_seconds": 0,
                "load": 0,
                "capacity": vehicle_capacities[vehicle_id]
            })

    return {
        "routes": routes,
        "total_distance_meters": total_distance_m,
        "total_duration_seconds": total_duration_s
    }

# API Endpoints
@app.post("/api/optimize")
def optimize_routes(payload: OptimizeRequest):
    if not payload.locations or len(payload.locations) < 2:
        raise HTTPException(status_code=400, detail="At least 2 locations (1 depot and 1 stop) are required.")
    
    if payload.num_vehicles <= 0:
        raise HTTPException(status_code=400, detail="Number of vehicles must be at least 1.")
    
    if len(payload.vehicle_capacities) != payload.num_vehicles:
        raise HTTPException(status_code=400, detail="Vehicle capacities list size must match the number of vehicles.")

    # 1. Fetch distance and duration matrices
    distance_matrix, duration_matrix, is_real_road = fetch_osrm_matrices(payload.locations)

    # Extract demands
    demands = [loc.demand for loc in payload.locations]
    
    # Check if any single stop's demand exceeds the maximum vehicle capacity
    max_capacity = max(payload.vehicle_capacities)
    for idx, demand in enumerate(demands):
        if demand > max_capacity:
            raise HTTPException(
                status_code=400, 
                detail=f"Location '{payload.locations[idx].name}' demand ({demand}) exceeds the maximum vehicle capacity ({max_capacity}). Please increase capacity or reduce demand."
            )

    # 2. Solve CVRP
    solution = solve_cvrp(
        distance_matrix=distance_matrix,
        duration_matrix=duration_matrix,
        demands=demands,
        vehicle_capacities=payload.vehicle_capacities,
        num_vehicles=payload.num_vehicles,
        depot_index=0
    )

    if not solution:
        raise HTTPException(
            status_code=400, 
            detail="Could not find a feasible solution. Make sure the total vehicle capacity is sufficient for all delivery demands, or try adding more vehicles."
        )

    # 3. For each solved route, query the detailed OSRM road geometry
    for route in solution["routes"]:
        if len(route["node_sequence"]) > 2:
            # Map node index to coordinate list
            route_coords = [payload.locations[node_idx] for node_idx in route["node_sequence"]]
            route["geometry"] = fetch_osrm_route_geometry(route_coords)
        else:
            route["geometry"] = {"type": "LineString", "coordinates": []}

    # Add routing type flag to response
    solution["using_real_roads"] = is_real_road

    return solution

@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "RouteOpt service is running"}

# Serve frontend static files
# In production / full-stack deployment, we mount the frontend static directory.
try:
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
except Exception as e:
    # If frontend folder doesn't exist yet, we don't crash startup during code construction
    logger.warning(f"Could not mount static frontend folder: {e}")
