import osmnx as ox
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import os
from shapely.geometry import Point
import geopandas as gpd
import networkx as nx

GRAPH_FILE = "slo_bike_graph.graphml"
_cached_graph = None


def load_graph():
    global _cached_graph
    if _cached_graph is not None:
        return _cached_graph

    if os.path.exists(GRAPH_FILE):
        print("Loading cached graph...")
        G = ox.load_graphml(GRAPH_FILE)
    else:
        print("Downloading and building graph...")
        G = ox.graph_from_place("San Luis Obispo, California, USA", network_type="bike")
        G = ox.project_graph(G)
        ox.save_graphml(G, GRAPH_FILE)
    # G = ox.routing.add_edge_speeds(G)
    # G = ox.routing.add_edge_travel_times(G)
    # Set realistic bike travel times manually
    BIKE_SPEED_M_S = 15 / 3.6  # 15 km/h in m/s ≈ 4.17

    for u, v, k, data in G.edges(keys=True, data=True):
        length = data.get("length", 0)
        if length > 0:
            data["travel_time"] = length / BIKE_SPEED_M_S
    _cached_graph = G
    return G

def normalize_priorities(priority_map):
    inverse = {k: 1 / v for k, v in priority_map.items() if v is not None and v > 0}
    if not inverse:
        # Provide default: prioritize time
        inverse = {"Time": 1}
    total = sum(inverse.values())
    return {k: v / total for k, v in inverse.items()}


def edge_cost(u, v, data, weights, G):
    length = data.get("length", 0)
    ctype = data.get("cycleway") or data.get("cycleway:right") or data.get("highway", "")
    has_lane = ctype in ["lane", "shared_lane", "opposite_lane"]
    has_track = ctype == "track"
    if ctype == "track":
        c_pen = 0.1
    elif ctype == "lane":
        c_pen = 0.3
    elif ctype == "cycleway":
        c_pen = 0.5
    else:
        c_pen = 1.0

    try:
        speed = float(data.get("maxspeed", 30))
    except:
        speed = 30.0
    speed_penalty = speed / 50.0

    surface = data.get("surface", "").lower()
    unpaved_penalty = 1 if surface not in ("asphalt", "paved", "") else 0

    sigs = int(G.nodes[u].get("highway") == "traffic_signals") + int(G.nodes[v].get("highway") == "traffic_signals")
    stops = int(G.nodes[u].get("highway") == "stop") + int(G.nodes[v].get("highway") == "stop")

    travel_time = data.get("travel_time", length / 5)

    cost = 0
    cost += weights.get("Distance", 0) * length
    cost += weights.get("Time", 0) * travel_time
    cost += weights.get("Find Bike Lane", 0) * (1.0 - int(has_lane)) * length  # Reward lanes
    cost += weights.get("Find Protected Bike Lane", 0) * (1.0 - int(has_track)) * length  # Reward tracks
    cost += weights.get("Road Priority", 0) * (speed_penalty + unpaved_penalty + 0.5 * sigs + 0.2 * stops)

    return cost

def get_route_directions(G, route):
    directions = []
    prev_street = None

    for u, v in zip(route[:-1], route[1:]):
        edges = G.get_edge_data(u, v)
        if not edges:
            street = 'Unnamed Road'
        else:
            edge_key = next(iter(edges))
            edge_data = edges[edge_key]
            street = edge_data.get('name', 'Unnamed Road')

        if street != prev_street:
            directions.append(f"Continue on {street}")
            prev_street = street

    return directions

def run_routing(from_address, to_address, priority_map):
    print(f"Routing from: {from_address} to {to_address}")
    weights = normalize_priorities(priority_map)
    print("Normalized weights:", weights)

    G = load_graph()  # Load or build graph once per run

    try:
        orig_coords = ox.geocode(from_address)
        dest_coords = ox.geocode(to_address)
        print(f"Origin coords: {orig_coords}")
        print(f"Destination coords: {dest_coords}")
    except Exception as e:
        raise ValueError(f"Geocoding failed: {e}")

    if orig_coords is None or dest_coords is None:
        raise ValueError("Could not geocode one or both addresses.")

    # Build GeoDataFrames and project to graph CRS
    try:
        orig_point = Point(orig_coords[1], orig_coords[0])
        dest_point = Point(dest_coords[1], dest_coords[0])

        orig_gdf = gpd.GeoDataFrame(geometry=[Point(orig_point)], crs='EPSG:4326').to_crs(G.graph['crs'])
        dest_gdf = gpd.GeoDataFrame(geometry=[Point(dest_point)], crs='EPSG:4326').to_crs(G.graph['crs'])
    except Exception as e:
        raise ValueError(f"Error during coordinate projection: {e}")

    orig_pt = orig_gdf.geometry.iloc[0]
    dest_pt = dest_gdf.geometry.iloc[0]

    if not orig_pt.is_valid or not dest_pt.is_valid:
        raise ValueError("Invalid geometry returned from geocoding.")

    if not all(map(lambda v: v == v and v != float("inf") and v != float("-inf"),
                   [orig_pt.x, orig_pt.y, dest_pt.x, dest_pt.y])):
        raise ValueError("One or more coordinates are NaN or infinite.")

    if orig_pt.geom_type != "Point":
        orig_pt = orig_pt.centroid
    if dest_pt.geom_type != "Point":
        dest_pt = dest_pt.centroid

    orig_node = ox.distance.nearest_nodes(G, orig_pt.x, orig_pt.y)
    dest_node = ox.distance.nearest_nodes(G, dest_pt.x, dest_pt.y)

    def weight_fn(u: int, v: int, k: int, data: dict) -> float:
        return edge_cost(u, v, data, weights, G)

    route = nx.shortest_path(G, orig_node, dest_node, weight=lambda u, v, data: edge_cost(u, v, data, weights, G))
    #route = ox.shortest_path(G, orig_node, dest_node, weight=weight_fn)

    # Compute route summary
    total_distance = 0
    total_time = 0
    bike_lane_segments = 0
    protected_segments = 0

    for u, v in zip(route[:-1], route[1:]):
        edges = G.get_edge_data(u, v)
        if not edges:
            continue
        edge_key = next(iter(edges))
        data = edges[edge_key]

        total_distance += data.get("length", 0)
        total_time += data.get("travel_time", 0)

        cycleway_tags = [
            data.get("cycleway"),
            data.get("cycleway:right"),
            data.get("cycleway:left"),
            data.get("cycleway:both")
        ]
        highway = data.get("highway", "")
        bicycle = data.get("bicycle", "")

        cycleway = next((v for v in cycleway_tags if v), None)

        is_bike_lane = False
        is_protected = False

        if cycleway in ["lane", "track", "shared_lane", "opposite_lane"] or highway == "cycleway":
            is_bike_lane = True
        if cycleway == "track" or highway == "cycleway":
            is_protected = True

        if is_bike_lane:
            bike_lane_segments += 1
        if is_protected:
            protected_segments += 1

    # # Build color list for visualization
    # edge_colors = []
    # for u, v in zip(route[:-1], route[1:]):
    #     edges = G.get_edge_data(u, v)
    #     if not edges:
    #         color = "gray"
    #         continue
    #     edge_key = next(iter(edges))
    #     edge_data = edges[edge_key]
    #
    #     cycleway_tags = [
    #         edge_data.get("cycleway"),
    #         edge_data.get("cycleway:right"),
    #         edge_data.get("cycleway:left"),
    #         edge_data.get("cycleway:both")
    #     ]
    #     cycleway = next((tag for tag in cycleway_tags if tag), None)
    #     if cycleway == "track":
    #         color = "darkgreen"
    #     elif cycleway in ["lane", "shared_lane", "opposite_lane"]:
    #         color = "lightgreen"
    #     else:
    #         color = "gray"
    #     edge_colors.append(color)

    directions = get_route_directions(G, route)

    # Calculate bounding box of route nodes (min/max x and y)
    x_coords = [G.nodes[n]['x'] for n in route]
    y_coords = [G.nodes[n]['y'] for n in route]

    margin = 250  # margin to add around the route (in graph units, usually meters)

    xmin, xmax = min(x_coords) - margin, max(x_coords) + margin
    ymin, ymax = min(y_coords) - margin, max(y_coords) + margin

    fig, ax = ox.plot_graph_route(
        G, route, route_linewidth=4, node_size=0,
        bgcolor="white", show=False, close=False
    )

    # Set the axis limits to zoom tightly around the route + margin
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)

    ax.scatter([orig_pt.x], [orig_pt.y], c="red", s=100, label="Origin")
    ax.scatter([dest_pt.x], [dest_pt.y], c="blue", s=100, label="Destination")
    ax.legend()
    plt.show()

    return {
        "distance_m": round(total_distance, 2),
        "time_min": round(total_time / 60, 2),
        "bike_lane_segments": bike_lane_segments,
        "protected_segments": protected_segments,
        "directions" : directions
    }
