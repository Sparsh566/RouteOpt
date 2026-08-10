# Student Name: Aditya khiratkar
# PRN: 24070521071
# Role: Member 2 (Optimization Engine / OR-Tools Solver)

import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import solve_cvrp

def test_cvrp_solver():
    print("Testing OR-Tools CVRP solver execution...")
    
    # 4 nodes: 0 (depot), 1, 2, 3
    # Distance matrix (symmetric)
    distance_matrix = [
        [0, 10, 20, 15],
        [10, 0, 12, 25],
        [20, 12, 0, 8],
        [15, 25, 8, 0]
    ]
    
    # Simple duration matrix (e.g. travel speed 1 unit/sec)
    duration_matrix = [[val for val in row] for row in distance_matrix]
    
    # Demands at nodes: Depot has 0. Nodes 1, 2, 3 have demand 5, 8, 3.
    demands = [0, 5, 8, 3]
    
    # Vehicles: 2 vehicles, each with capacity 10
    vehicle_capacities = [10, 10]
    num_vehicles = 2
    
    solution = solve_cvrp(
        distance_matrix=distance_matrix,
        duration_matrix=duration_matrix,
        demands=demands,
        vehicle_capacities=vehicle_capacities,
        num_vehicles=num_vehicles,
        depot_index=0
    )
    
    if solution is None:
        print("Test FAILED: No solution found!")
        sys.exit(1)
        
    print("Test PASSED! Solution found:")
    print(f"Total distance: {solution['total_distance_meters']} meters")
    print(f"Total duration: {solution['total_duration_seconds']} seconds")
    for route in solution['routes']:
        print(f"Vehicle {route['vehicle_id']} route: {route['node_sequence']} with load {route['load']}/{route['capacity']}")
        
    # Basic assertions
    assert solution['total_distance_meters'] > 0
    assert len(solution['routes']) == 2
    print("All assertions passed successfully!")
    
if __name__ == "__main__":
    test_cvrp_solver()
