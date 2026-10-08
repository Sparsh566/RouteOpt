"""
Commercial Fleet CVRPTW Solver Service
Formulates Capacitated Vehicle Routing Problem with Time Windows & Road Guidelines using Google OR-Tools.
"""

try:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    ORTOOLS_AVAILABLE = True
except (ImportError, Exception):
    pywrapcp = None
    routing_enums_pb2 = None
    ORTOOLS_AVAILABLE = False

from typing import List, Dict, Any, Optional
import logging
from backend.app.models.fleet_v2 import CommercialVehicleSpec, VehicleClass, DeliveryStop, DepotLocation

logger = logging.getLogger("routeopt.cvrptw")

class CVRPTWSolver:
    def __init__(
        self,
        distance_matrix: List[List[float]],
        duration_matrix: List[List[float]],
        depot: DepotLocation,
        stops: List[DeliveryStop],
        fleet: List[CommercialVehicleSpec],
        enforce_guidelines: bool = True
    ):
        self.distance_matrix = distance_matrix
        self.duration_matrix = duration_matrix
        self.depot = depot
        self.stops = stops
        self.fleet = fleet
        self.enforce_guidelines = enforce_guidelines
        
        # Node 0 is Depot, Nodes 1..N are stops
        self.all_nodes = [depot] + stops
        self.num_nodes = len(self.all_nodes)
        self.num_vehicles = len(fleet)
        self.depot_index = 0

    def solve(self) -> Optional[Dict[str, Any]]:
        if not ORTOOLS_AVAILABLE:
            logger.info("OR-Tools not available in environment. Running greedy CVRPTW solver fallback.")
            return self._solve_greedy_fallback()

        try:
            return self._solve_ortools()
        except Exception as e:
            logger.warning(f"OR-Tools solver execution failed: {e}. Falling back to greedy CVRPTW.")
            return self._solve_greedy_fallback()

    def _solve_ortools(self) -> Optional[Dict[str, Any]]:
        manager = pywrapcp.RoutingIndexManager(
            self.num_nodes,
            self.num_vehicles,
            self.depot_index
        )
        routing = pywrapcp.RoutingModel(manager)

        # 1. Register Transit Duration Callbacks per vehicle class
        transit_callback_indices = []
        for v in self.fleet:
            # Trucks face ~1.30x transit duration in tight Indian urban streets
            vehicle_speed_penalty = 1.30 if v.vehicle_class == VehicleClass.FREIGHT_TRUCK else 1.0

            def create_duration_callback(penalty):
                def callback(from_index: int, to_index: int) -> int:
                    u = manager.IndexToNode(from_index)
                    v_node = manager.IndexToNode(to_index)
                    base_dur = self.duration_matrix[u][v_node]
                    # Add dwell/unloading time at origin (0 for depot)
                    dwell = self.stops[u - 1].service_duration_sec if u > 0 else 0
                    return int((base_dur * penalty) + dwell)
                return callback

            cb = routing.RegisterTransitCallback(create_duration_callback(vehicle_speed_penalty))
            transit_callback_indices.append(cb)

        # 2. Distance Callback for Arc Cost Evaluator
        def distance_callback(from_index: int, to_index: int) -> int:
            u = manager.IndexToNode(from_index)
            v_node = manager.IndexToNode(to_index)
            return int(self.distance_matrix[u][v_node])

        dist_cb_index = routing.RegisterTransitCallback(distance_callback)

        for v_idx in range(self.num_vehicles):
            routing.SetArcCostEvaluatorOfVehicle(dist_cb_index, v_idx)
            # Fixed vehicle dispatch cost
            fixed_cost = int(self.fleet[v_idx].fixed_dispatch_cost * 100)
            routing.SetFixedCostOfVehicle(fixed_cost, v_idx)

        # 3. Capacity Dimension (Payload kg)
        def demand_callback(from_index: int) -> int:
            u = manager.IndexToNode(from_index)
            if u == 0:
                return 0
            return int(self.stops[u - 1].demand_kg)

        demand_cb_index = routing.RegisterUnaryTransitCallback(demand_callback)
        capacities = [int(v.payload_capacity_kg) for v in self.fleet]

        routing.AddDimensionWithVehicleCapacity(
            demand_cb_index,
            0,            # Null capacity slack
            capacities,   # Vehicle max capacities
            True,         # Start load at 0
            "Capacity"
        )

        # 4. Time Dimension (Time Windows + Shift Operating Limits)
        max_shift_sec = self.depot.operating_hours_sec
        routing.AddDimension(
            transit_callback_indices[0],
            7200,          # 2 hours slack waiting time allowed if driver arrives early
            max_shift_sec, # Max route duration
            False,         # Don't force start to zero
            "Time"
        )
        time_dimension = routing.GetDimensionOrDie("Time")

        # Apply Time Windows for each Delivery Stop
        for i, stop in enumerate(self.stops):
            node_idx = i + 1
            idx = manager.NodeToIndex(node_idx)
            time_dimension.CumulVar(idx).SetRange(
                stop.time_window_start_sec,
                stop.time_window_end_sec
            )

        # 5. Municipal Government Guidelines: Restrict Trucks from Urban Core during Peak Bans
        if self.enforce_guidelines:
            # Morning peak ban: 28800s - 41400s (08:00 - 11:30 AM)
            # Evening peak ban: 61200s - 77400s (17:00 - 21:30 PM)
            for i, stop in enumerate(self.stops):
                if stop.is_in_restricted_urban_core:
                    node_idx = i + 1
                    idx = manager.NodeToIndex(node_idx)
                    for v_idx, v in enumerate(self.fleet):
                        if v.vehicle_class == VehicleClass.FREIGHT_TRUCK:
                            # Trucks cannot service restricted urban nodes during no-entry hours
                            try:
                                time_dimension.CumulVar(idx).RemoveInterval(28800, 41400)
                                time_dimension.CumulVar(idx).RemoveInterval(61200, 77400)
                            except Exception:
                                pass

        # 6. Disjunctions (Drop penalties so solver stays feasible)
        penalty = 500_000
        for i in range(len(self.stops)):
            node_idx = i + 1
            routing.AddDisjunction([manager.NodeToIndex(node_idx)], penalty)

        # 7. Search Strategy
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
        )
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_parameters.time_limit.seconds = 3

        solution = routing.SolveWithParameters(search_parameters)
        if not solution:
            return None

        # 8. Extract Solution
        capacity_dim = routing.GetDimensionOrDie("Capacity")
        routes = []
        dropped_stops = []

        # Find dropped stops
        for i, stop in enumerate(self.stops):
            node_idx = i + 1
            idx = manager.NodeToIndex(node_idx)
            if solution.Value(routing.NextVar(idx)) == idx:
                dropped_stops.append(stop.stop_id)

        for v_idx in range(self.num_vehicles):
            vehicle = self.fleet[v_idx]
            idx = routing.Start(v_idx)
            schedule = []
            route_dist = 0.0
            route_dur = 0.0

            while not routing.IsEnd(idx):
                node = manager.IndexToNode(idx)
                time_val = solution.Min(time_dimension.CumulVar(idx))
                load_val = solution.Value(capacity_dim.CumulVar(idx))

                schedule.append({
                    "node_index": node,
                    "arrival_time_sec": time_val,
                    "load_kg": load_val
                })
                next_idx = solution.Value(routing.NextVar(idx))
                next_node = manager.IndexToNode(next_idx)
                route_dist += self.distance_matrix[node][next_node]
                route_dur += self.duration_matrix[node][next_node]
                idx = next_idx

            # Final depot arrival
            node = manager.IndexToNode(idx)
            time_val = solution.Min(time_dimension.CumulVar(idx))
            schedule.append({
                "node_index": node,
                "arrival_time_sec": time_val,
                "load_kg": 0
            })

            routes.append({
                "vehicle_id": vehicle.vehicle_id,
                "vehicle_name": vehicle.name,
                "vehicle_class": vehicle.vehicle_class,
                "color_hex": vehicle.color_hex,
                "schedule": schedule,
                "total_distance_m": route_dist,
                "total_duration_s": route_dur,
                "utilized": len(schedule) > 2
            })

        return {
            "routes": routes,
            "dropped_stops": dropped_stops
        }

    def _solve_greedy_fallback(self) -> Dict[str, Any]:
        """
        Greedy CVRPTW solver fallback if OR-Tools is unavailable on serverless environments.
        Assigns stops to vehicles based on capacity constraints and nearest available drop.
        """
        unassigned = list(range(1, self.num_nodes))
        routes = []
        dropped_stops = []

        for vehicle in self.fleet:
            if not unassigned:
                # Idle vehicle
                routes.append({
                    "vehicle_id": vehicle.vehicle_id,
                    "vehicle_name": vehicle.name,
                    "vehicle_class": vehicle.vehicle_class,
                    "color_hex": vehicle.color_hex,
                    "schedule": [
                        {"node_index": 0, "arrival_time_sec": 0.0, "load_kg": 0.0},
                        {"node_index": 0, "arrival_time_sec": 0.0, "load_kg": 0.0}
                    ],
                    "total_distance_m": 0.0,
                    "total_duration_s": 0.0,
                    "utilized": False
                })
                continue

            current_node = 0
            current_time = 0.0
            current_load = 0.0
            schedule = [{"node_index": 0, "arrival_time_sec": 0.0, "load_kg": 0.0}]
            total_dist = 0.0
            total_dur = 0.0
            speed_penalty = 1.30 if vehicle.vehicle_class == VehicleClass.FREIGHT_TRUCK else 1.0

            while unassigned:
                # Find nearest feasible unassigned stop
                best_stop_idx = None
                best_dist = float("inf")

                for candidate_node in unassigned:
                    stop_data = self.stops[candidate_node - 1]
                    # Check capacity
                    if current_load + stop_data.demand_kg > vehicle.payload_capacity_kg:
                        continue
                    # Check truck ban
                    if (
                        self.enforce_guidelines
                        and vehicle.vehicle_class == VehicleClass.FREIGHT_TRUCK
                        and stop_data.is_in_restricted_urban_core
                    ):
                        continue

                    d = self.distance_matrix[current_node][candidate_node]
                    if d < best_dist:
                        best_dist = d
                        best_stop_idx = candidate_node

                if best_stop_idx is None:
                    # No more stops fit this vehicle's capacity or restrictions
                    break

                # Service best_stop_idx
                unassigned.remove(best_stop_idx)
                stop_data = self.stops[best_stop_idx - 1]
                leg_dist = self.distance_matrix[current_node][best_stop_idx]
                leg_dur = (self.duration_matrix[current_node][best_stop_idx] * speed_penalty)
                current_time += leg_dur

                # Apply time window wait if arriving early
                if current_time < stop_data.time_window_start_sec:
                    current_time = float(stop_data.time_window_start_sec)

                current_load += stop_data.demand_kg
                schedule.append({
                    "node_index": best_stop_idx,
                    "arrival_time_sec": current_time,
                    "load_kg": current_load
                })

                current_time += float(stop_data.service_duration_sec)
                total_dist += leg_dist
                total_dur += leg_dur + float(stop_data.service_duration_sec)
                current_node = best_stop_idx

            # Return to depot
            return_dist = self.distance_matrix[current_node][0]
            return_dur = self.duration_matrix[current_node][0] * speed_penalty
            current_time += return_dur
            total_dist += return_dist
            total_dur += return_dur

            schedule.append({
                "node_index": 0,
                "arrival_time_sec": current_time,
                "load_kg": 0.0
            })

            routes.append({
                "vehicle_id": vehicle.vehicle_id,
                "vehicle_name": vehicle.name,
                "vehicle_class": vehicle.vehicle_class,
                "color_hex": vehicle.color_hex,
                "schedule": schedule,
                "total_distance_m": total_dist,
                "total_duration_s": total_dur,
                "utilized": len(schedule) > 2
            })

        for remaining_node in unassigned:
            dropped_stops.append(self.stops[remaining_node - 1].stop_id)

        return {
            "routes": routes,
            "dropped_stops": dropped_stops
        }
