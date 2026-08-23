"""
Performance Benchmark Script for RouteOpt Solver Service.

Measures OR-Tools TSP solve execution times across different matrix sizes (5, 8, and 10 nodes).
"""

import os
import random
import sys
import time

# Add parent directory to sys.path for standalone script execution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.solver import solve_route


def generate_symmetric_matrix(num_nodes: int, max_distance: int = 100) -> list[list[int]]:
    """
    Generates a random symmetric NxN distance matrix with zero diagonal.
    
    Args:
        num_nodes (int): Number of nodes (matrix dimension N).
        max_distance (int): Upper bound for random edge distances.

    Returns:
        list[list[int]]: Symmetric NxN distance matrix.
    """
    matrix = [[0] * num_nodes for _ in range(num_nodes)]
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            dist = random.randint(10, max_distance)
            matrix[i][j] = dist
            matrix[j][i] = dist
    return matrix


def run_benchmarks():
    """
    Executes solver benchmarks for 5, 8, and 10 node distance matrices.
    """
    node_counts = [5, 8, 10]

    # Seed random number generator for reproducible benchmark output
    random.seed(42)

    print("=" * 60)
    print("RouteOpt v1 - OR-Tools Solver Performance Benchmark")
    print("=" * 60)

    for num_nodes in node_counts:
        distance_matrix = generate_symmetric_matrix(num_nodes)

        # High-resolution timing before solver call
        start_time = time.perf_counter()
        route = solve_route(distance_matrix)
        end_time = time.perf_counter()

        # Calculate solve duration in milliseconds
        solve_time_ms = (end_time - start_time) * 1000

        print(f"Nodes           : {num_nodes}")
        print(f"Solve Time      : {solve_time_ms:.3f} ms")
        print(f"Optimized Route : {route}")
        print("-" * 60)


if __name__ == "__main__":
    run_benchmarks()

