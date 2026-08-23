"""
Route Optimization Solver Service using Google OR-Tools.

Provides TSP route optimization logic for a single vehicle starting and ending at a depot.
"""

from ortools.constraint_solver import pywrapcp, routing_enums_pb2


def solve_route(distance_matrix: list[list[int]]) -> list[int]:
    """
    Solves the Traveling Salesperson Problem (TSP) using Google OR-Tools.

    Args:
        distance_matrix (list[list[int]]): NxN matrix where element [i][j] represents 
                                           the distance or cost from node i to node j.

    Returns:
        list[int]: Ordered list of node indices representing the optimal route,
                   starting and ending at the depot (node 0).

    Raises:
        ValueError: If distance_matrix is empty or not an NxN square matrix.
        RuntimeError: If OR-Tools fails to find a valid solution.
    """
    if not distance_matrix or not distance_matrix[0]:
        raise ValueError("Distance matrix must not be empty.")

    num_nodes = len(distance_matrix)

    # Validate that distance matrix is square (NxN)
    for row in distance_matrix:
        if len(row) != num_nodes:
            raise ValueError("Distance matrix must be an NxN square matrix.")

    # Configure single vehicle routing starting and ending at depot 0
    num_vehicles = 1
    depot = 0

    # Initialize OR-Tools Routing Index Manager and Routing Model
    manager = pywrapcp.RoutingIndexManager(num_nodes, num_vehicles, depot)
    routing = pywrapcp.RoutingModel(manager)

    # Define transit distance callback between internal routing nodes
    def distance_callback(from_index: int, to_index: int) -> int:
        """Returns travel distance between two solver nodes."""
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]

    # Register distance callback with solver
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)

    # Set transit callback as cost evaluator for all vehicle arcs
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Set first solution heuristic search strategy
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )

    # Execute OR-Tools routing solver
    solution = routing.SolveWithParameters(search_parameters)

    # Raise exception if solver could not find a solution
    if not solution:
        raise RuntimeError("No solution found for the given distance matrix.")

    # Traverse solution route from start depot to end depot
    index = routing.Start(depot)
    route = []
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        route.append(node)
        index = solution.Value(routing.NextVar(index))

    # Append return depot node to complete loop
    route.append(manager.IndexToNode(index))

    return route

