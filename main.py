import osmnx as ox
import math
import matplotlib.pyplot as plt

# Optional: configure logging & cache
# ox.config(log_console=True, use_cache=True)

# 1. Download a bikeable-street network and project it to meters
G = ox.graph_from_place("San Luis Obispo, California, USA", network_type="bike")
G = ox.project_graph(G)

# 2. (Elevation is skipped because no API key; grades will default to 0)
#    If you later add elevation data, you can uncomment:
# G = ox.elevation.add_node_elevations_google(G, api_key="YOUR_KEY_HERE", pause=1)
# G = ox.elevation.add_edge_grades(G, add_absolute=True)

# 3. Add edge speeds and travel times
G = ox.routing.add_edge_speeds(G)
G = ox.routing.add_edge_travel_times(G)

# 4. Define custom cost weights (tweak as needed)
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
    """Compute custom cost for edge (u->v) based on length, cycleway, grade, speed, surface, and controls."""
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

    # grade penalty (will be zero since no grades added)
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

    return length * (c_pen + g_pen + s_pen + surf_pen) + ctrl_pen

# 5. Geocode origin and destination, convert to GeoDataFrames
orig_address = "790 Foothill Blvd, San Luis Obispo, CA 93405"
dest_address = "1210 Higuera St, San Luis Obispo, CA 93401"
orig_gdf = ox.geocode_to_gdf(orig_address)
dest_gdf = ox.geocode_to_gdf(dest_address)

# Project those GeoDataFrames to the same CRS as G
orig_proj = ox.projection.project_gdf(orig_gdf, to_crs=G.graph["crs"])
dest_proj = ox.projection.project_gdf(dest_gdf, to_crs=G.graph["crs"])

# If the geometry is a polygon, use its centroid; otherwise, use the point directly
orig_geom = orig_proj.geometry.iloc[0]
orig_centroid = orig_geom.centroid if orig_geom.geom_type != "Point" else orig_geom
ox_x, ox_y = orig_centroid.x, orig_centroid.y

dest_geom = dest_proj.geometry.iloc[0]
dest_centroid = dest_geom.centroid if dest_geom.geom_type != "Point" else dest_geom
dx_x, dx_y = dest_centroid.x, dest_centroid.y

# Find nearest nodes
orig_node = ox.distance.nearest_nodes(G, ox_x, ox_y)
dest_node = ox.distance.nearest_nodes(G, dx_x, dx_y)

# --------------------
# CHOOSE what the router should minimize
#   "length"       → shortest physical distance (metres)
#   "travel_time"  → fastest route using OSMnx‑calculated travel_time (seconds)
#   "speed"        → minimise time by (length / speed_kph) when travel_time absent
# --------------------
WEIGHT_MODE = "length"        # change to "travel_time" or "speed" as needed


def routing_weight(u: int, v: int, k: int, data: dict) -> float:
    """Return the edge cost used by NetworkX shortest_path
    depending on the global WEIGHT_MODE."""
    if WEIGHT_MODE == "length":
        # Already stored by OSMnx for every edge (metres)
        return data.get("length", 0.0)

    elif WEIGHT_MODE == "travel_time":
        # Added above via ox.routing.add_edge_travel_times(G) (seconds)
        return data.get("travel_time", data.get("length", 0.0))

    elif WEIGHT_MODE == "speed":
        # Approximate time = length / speed (length in m, speed in km/h)
        speed_kph = data.get("speed_kph", 30.0)
        # Convert km/h → m/s to avoid divide‑by‑zero
        speed_mps = max(speed_kph * (1000 / 3600), 0.1)
        return data.get("length", 0.0) / speed_mps

    # default fallback
    return data.get("length", 0.0)

route = ox.shortest_path(G, orig_node, dest_node, weight=routing_weight)

# 7. Plot the custom A* bike route and zoom to bounding box
fig, ax = ox.plot_graph_route(
    G, route,
    route_linewidth=4, node_size=0, bgcolor="white",
    show=True  # draw later after setting limits
)

# Plot origin and destination points
ax.scatter([ox_x], [ox_y], c="red", s=100, label="Origin")
ax.scatter([dx_x], [dx_y], c="blue", s=100, label="Destination")
ax.legend()

# Compute bounding box around route nodes, with a 50-meter buffer
xs = [G.nodes[n]["x"] for n in route]
ys = [G.nodes[n]["y"] for n in route]
buffer = 50
xmin, xmax = min(xs) - buffer, max(xs) + buffer
ymin, ymax = min(ys) - buffer, max(ys) + buffer

ax.set_xlim(xmin, xmax)
ax.set_ylim(ymin, ymax)

plt.show()
