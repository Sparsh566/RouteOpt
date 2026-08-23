import pytest
from app.services.solver import solve_route


def test_solve_route_5x5_valid():
    """Test solver with a valid 5x5 distance matrix."""
    matrix = [
        [0, 10, 15, 20, 25],
        [10, 0, 35, 25, 30],
        [15, 35, 0, 30, 20],
        [20, 25, 30, 0, 15],
        [25, 30, 20, 15, 0],
    ]
    route = solve_route(matrix)
    n = len(matrix)

    # Verify route starts and ends with depot (node 0)
    assert route[0] == 0
    assert route[-1] == 0

    # Verify route length (all n nodes + return to depot)
    assert len(route) == n + 1

    # Verify every node is visited exactly once before returning to depot
    assert sorted(route[:-1]) == list(range(n))


def test_solve_route_8x8_valid():
    """Test solver with a valid 8x8 distance matrix."""
    matrix = [
        [0, 12, 29, 22, 13, 24, 11, 27],
        [12, 0, 19, 14, 25, 18, 16, 21],
        [29, 19, 0, 17, 30, 15, 20, 10],
        [22, 14, 17, 0, 28, 12, 19, 16],
        [13, 25, 30, 28, 0, 26, 14, 32],
        [24, 18, 15, 12, 26, 0, 22, 13],
        [11, 16, 20, 19, 14, 22, 0, 25],
        [27, 21, 10, 16, 32, 13, 25, 0],
    ]
    route = solve_route(matrix)
    n = len(matrix)

    # Verify route starts and ends with depot (node 0)
    assert route[0] == 0
    assert route[-1] == 0

    # Verify route length
    assert len(route) == n + 1

    # Verify every node is visited exactly once before returning to depot
    assert sorted(route[:-1]) == list(range(n))


def test_solve_route_empty_matrix():
    """Test solver raises ValueError when distance matrix is empty."""
    with pytest.raises(ValueError, match="Distance matrix must not be empty."):
        solve_route([])

    with pytest.raises(ValueError, match="Distance matrix must not be empty."):
        solve_route([[]])


def test_solve_route_non_square_matrix():
    """Test solver raises ValueError when matrix is not square."""
    non_square_matrix = [
        [0, 10, 15],
        [10, 0, 35],
    ]
    with pytest.raises(ValueError, match="Distance matrix must be an NxN square matrix."):
        solve_route(non_square_matrix)
