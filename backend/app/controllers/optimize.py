from fastapi import APIRouter, HTTPException
from backend.app.models.optimize import OptimizeRequest, OptimizeResponse
from backend.app.services.mock_services import MockOSRMService, MockSolverService

router = APIRouter()

@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_route(payload: OptimizeRequest):
    # Complete coordinate list starting with the depot and then stops
    all_waypoints = [payload.depot] + payload.stops
    
    try:
        # 1. Fetch duration matrix
        matrix = await MockOSRMService.get_duration_matrix(all_waypoints)
        
        # 2. Compute sequence order using the solver
        order = MockSolverService.solve_route(matrix)
        
        # 3. Retrieve final route polyline for the ordered waypoints
        ordered_waypoints = [all_waypoints[i] for i in order]
        polyline = await MockOSRMService.get_route_polyline(ordered_waypoints)
        
        # 4. Calculate total travel duration and a simulated distance
        # Total duration is the sum of times along the solved route sequence
        total_duration = 0.0
        for idx in range(len(order) - 1):
            u, v = order[idx], order[idx + 1]
            total_duration += matrix[u][v]
            
        # Simulate distance (e.g. durations * speed multiplier, say 12.5 meters/sec)
        total_distance = round(total_duration * 12.5, 1)
        
        return OptimizeResponse(
            order=order,
            distance_m=total_distance,
            duration_s=total_duration,
            polyline=polyline
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization process failed: {str(e)}")
