from typing import List

class MockOSRMService:
    @staticmethod
    async def get_duration_matrix(stops: List[List[float]]) -> List[List[float]]:
        # Simulates a mock travel time matrix between coordinates.
        # It creates a simple grid duration matrix (e.g. durations based on coordinate distances)
        n = len(stops)
        matrix = []
        for i in range(n):
            row = []
            for j in range(n):
                if i == j:
                    row.append(0.0)
                else:
                    # Approximation: Euclidean distance scaled to travel time in seconds
                    lat1, lon1 = stops[i]
                    lat2, lon2 = stops[j]
                    dist = ((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) ** 0.5
                    row.append(round(dist * 100000.0, 1))  # Dummy calculation
            matrix.append(row)
        return matrix

    @staticmethod
    async def get_route_polyline(coords: List[List[float]]) -> str:
        # Returns a mock encoded polyline for routing presentation.
        # This is a sample valid polyline string.
        return "_p~iF~ps|U_ulLnnqC_mqNvxq@"

class MockSolverService:
    @staticmethod
    def solve_route(duration_matrix: List[List[float]]) -> List[int]:
        # Simple greedy TSP solver mockup for testing
        # Starts at 0 (depot) and visits the nearest unvisited node.
        n = len(duration_matrix)
        visited = {0}
        order = [0]
        curr = 0
        while len(visited) < n:
            next_node = -1
            min_dist = float('inf')
            for j in range(n):
                if j not in visited and duration_matrix[curr][j] < min_dist:
                    min_dist = duration_matrix[curr][j]
                    next_node = j
            if next_node == -1:
                break
            visited.add(next_node)
            order.append(next_node)
            curr = next_node
        order.append(0)  # Return to depot
        return order
