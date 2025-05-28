import osmnx as ox
import networkx as nx
import math
import matplotlib.pyplot as plt

# Optional: configure logging & cache
# ox.config(log_console=True, use_cache=True)

# 1. Download a bikeable-street network for a place by name and project it to meters
G = ox.graph_from_place("San Luis Obispo, California, USA", network_type="bike")
G = ox.project_graph(G)

# 2. Add elevation data and calculate grades
# You can switch to add_node_elevations_raster if you have local DEM files.
G = ox.elevation.add_node_elevations_google(G, api_key=None, pause=1)
G = ox.elevation.add_edge_grades(G, add_absolute=True)

# 3. Add edge speeds and travel times
G = ox.routing.add_edge_speeds(G)
G = ox.routing.add_edge_travel_times(G)

# 4. Define custom cost weights (tweak these)
W = {
    "protected_track": 0.5,
    "lane":            0.8,
    "cycleway":        1.0,
    "no_cycleway":     2.0,
    "grade":           5.0,
    "speed":           2.0,
    "unpaved":         3.0,
    "signal":          1.0,
    "stop":            0.5,
}

def edge_cost(u, v, data):
    """Compute custom cost for edge_u->v based on length, cycleway, grade, speed, surface, and controls."""
    length = data.get("length", 0)

    # cycleway type penalty
    ctype = data.get("cycleway") or data.get("cycleway:right") or data.get("highway")
    if ctype == "track":
        c_pen = W["protected_track"]
    elif ctype == "lane":
        c_pen = W["lane"]
    elif ctype == "cycleway":
        c_pen = W["cycleway"]
    else:
        c_pen = W["no_cycleway"]

    # grade penalty (positive only)
    grade = max(data.get("grade", 0), 0)
    g_pen = W["grade"] * grade

    # speed limit penalty
    maxspeed = data.get("maxspeed")
    try:
        speed = float(maxspeed)
    except:
        speed = 30.0
    s_pen = W["speed"] * (speed / 50.0)

    # surface penalty
    surface = data.get("surface", "").lower()
    surf_pen = W["unpaved"] if surface not in ("asphalt", "paved", "") else 0

    # control penalties at nodes
    sigs = int(G.nodes[u].get("highway") == "traffic_signals") + int(G.nodes[v].get("highway") == "traffic_signals")
    stops = int(G.nodes[u].get("highway") == "stop") + int(G.nodes[v].get("highway") == "stop")
    ctrl_pen = W["signal"] * sigs + W["stop"] * stops

    # total cost
    return length * (c_pen + g_pen + s_pen + surf_pen) + ctrl_pen

def euclidean_heuristic(u, v):
    """Straight-line distance heuristic in projected CRS."""
    x1, y1 = G.nodes[u]["x"], G.nodes[u]["y"]
    x2, y2 = G.nodes[v]["x"], G.nodes[v]["y"]
    return math.hypot(x2 - x1, y2 - y1)

# 5. Geocode origin and destination, find nearest nodes
orig_point = ox.geocode("790 Foothill Blvd, San Luis Obispo, CA 93405")
dest_point = ox.geocode("1210 Higuera St, San Luis Obispo, CA 93401")
orig_node = ox.nearest_nodes(G, orig_point[1], orig_point[0])
dest_node = ox.nearest_nodes(G, dest_point[1], dest_point[0])

# 6. Compute A* route
route = nx.astar_path(G, orig_node, dest_node, heuristic=euclidean_heuristic, weight=edge_cost)

# 7. Plot the custom A* bike route
fig, ax = ox.plot_graph_route(G, route, route_linewidth=4, node_size=0, bgcolor='white')
plt.show()