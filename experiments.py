import requests
import json
import math
import random
import time
import heapq
import sys


# ============================================================
# CONFIGURATION
# ============================================================

MCP_URL = "http://127.0.0.1:29292/mcp"

# Minimum ACTUAL ROAD distance
MIN_ROUTE_DISTANCE_M = 2000.0
# Maximum driving speed = 80 mph
MAX_SPEED_MPS = 80.0 * 0.44704

# Destination arrival radius
ARRIVAL_DISTANCE_M = 15.0

# Time between position checks
CHECK_INTERVAL = 1.0

# Number of trips
NUMBER_OF_TRIPS = 1

# Maximum navgraph nodes
MAX_NAV_NODES = 100000

# Only use reasonably drivable roads
MIN_DRIVABILITY = 0.3

# How many attempts to find Point A
MAX_A_ATTEMPTS = 100

# ============================================================
# MCP
# ============================================================

request_id = 0


def call_mcp(tool_name, arguments):

    global request_id

    request_id += 1

    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }

    try:

        response = requests.post(
            MCP_URL,
            json=payload,
            timeout=60
        )

        response.raise_for_status()

        return response.json()

    except requests.exceptions.ConnectionError:

        print()
        print("=" * 60)
        print("ERROR: MCP SERVER NOT REACHABLE")
        print("=" * 60)
        print()
        print(MCP_URL)
        print()

        sys.exit(1)

    except Exception as e:

        print(
            f"MCP error [{tool_name}]: {e}"
        )

        return None


# ============================================================
# EXTRACT MCP TEXT
# ============================================================

def extract_text(response):

    if response is None:
        return None

    try:

        content = response["result"]["content"]

        for item in content:

            if item.get("type") == "text":

                return item["text"]

    except Exception:
        pass

    return None


# ============================================================
# PARSE JSON
# ============================================================

def extract_json(response):

    text = extract_text(response)

    if text is None:
        return None

    try:

        return json.loads(text)

    except Exception:

        try:

            start = text.find("{")
            end = text.rfind("}")

            if start >= 0 and end > start:

                return json.loads(
                    text[start:end + 1]
                )

        except Exception:
            pass

    return None


# ============================================================
# GET NAVGRAPH
# ============================================================

def get_navgraph():

    print()
    print("=" * 60)
    print("LOADING COMPLETE BEAMNG NAVGRAPH")
    print("=" * 60)
    print()

    response = call_mcp(
        "get_navgraph",
        {
            "all": True,
            "maxNodes": MAX_NAV_NODES
        }
    )

    data = extract_json(response)

    if data is None:

        print("Could not parse navgraph.")
        print(response)

        sys.exit(1)

    return data


# ============================================================
# EXTRACT NODES
# ============================================================

def extract_nodes(navgraph):

    if not isinstance(navgraph, dict):
        return []

    nodes = navgraph.get("nodes")

    if isinstance(nodes, list):
        return nodes

    graph = navgraph.get("graph")

    if isinstance(graph, dict):

        nodes = graph.get("nodes")

        if isinstance(nodes, list):
            return nodes

    result = navgraph.get("result")

    if isinstance(result, dict):

        nodes = result.get("nodes")

        if isinstance(nodes, list):
            return nodes

    return []


# ============================================================
# CONVERT NODE
# ============================================================

def convert_node(node):

    if not isinstance(node, dict):
        return None

    name = node.get("name")

    if name is None:
        return None

    pos = node.get("pos")

    if not isinstance(pos, dict):
        return None

    try:

        x = float(pos["x"])
        y = float(pos["y"])
        z = float(pos["z"])

    except Exception:

        return None

    drivability = node.get(
        "drivability",
        1.0
    )

    try:

        drivability = float(
            drivability
        )

    except Exception:

        drivability = 1.0

    return {
        "name": name,
        "pos": {
            "x": x,
            "y": y,
            "z": z
        },
        "drivability": drivability,
        "links": node.get(
            "links",
            []
        )
    }


# ============================================================
# BUILD NODE DICTIONARY
# ============================================================

def build_nodes(raw_nodes):

    nodes = {}

    for raw in raw_nodes:

        node = convert_node(raw)

        if node is None:
            continue

        if (
            node["drivability"]
            < MIN_DRIVABILITY
        ):
            continue

        nodes[node["name"]] = node

    return nodes


# ============================================================
# BUILD ROAD GRAPH
# ============================================================

def build_graph(nodes):

    graph = {}

    for name, node in nodes.items():

        graph[name] = []

        links = node.get(
            "links",
            []
        )

        if not isinstance(
            links,
            list
        ):
            continue

        for link in links:

            if not isinstance(
                link,
                dict
            ):
                continue

            target = link.get(
                "to"
            )

            if target not in nodes:
                continue

            try:

                length = float(
                    link.get(
                        "len",
                        0
                    )
                )

            except Exception:

                continue

            if length <= 0:
                continue

            try:

                drivability = float(
                    link.get(
                        "drivability",
                        1.0
                    )
                )

            except Exception:

                drivability = 1.0

            if (
                drivability
                < MIN_DRIVABILITY
            ):
                continue

            graph[name].append(
                (
                    target,
                    length
                )
            )

    return graph


# ============================================================
# DIJKSTRA
# ============================================================

def dijkstra(
    graph,
    start,
    minimum_distance=5000.0
):

    """
    Calculate shortest road distance from start.

    We stop exploring once nodes are more than
    minimum_distance away.

    Returns:
        distances
    """

    distances = {
        start: 0.0
    }

    heap = [
        (0.0, start)
    ]

    while heap:

        current_distance, current = (
            heapq.heappop(heap)
        )

        if (
            current_distance
            != distances.get(
                current,
                float("inf")
            )
        ):
            continue

        for neighbor, edge_length in graph.get(
            current,
            []
        ):

            new_distance = (
                current_distance
                + edge_length
            )

            if (
                new_distance
                > minimum_distance
            ):
                continue

            old_distance = distances.get(
                neighbor,
                float("inf")
            )

            if new_distance < old_distance:

                distances[neighbor] = (
                    new_distance
                )

                heapq.heappush(
                    heap,
                    (
                        new_distance,
                        neighbor
                    )
                )

    return distances


# ============================================================
# FIND POINT A AND B
# ============================================================

def choose_a_b(
    nodes,
    graph
):

    node_names = list(
        graph.keys()
    )

    if len(node_names) < 2:

        print(
            "Not enough connected nodes."
        )

        return None, None, None

    print()
    print(
        "Searching for A → B with "
        "actual road distance >= 5 km..."
    )

    for attempt in range(
        1,
        MAX_A_ATTEMPTS + 1
    ):

        a_name = random.choice(
            node_names
        )

        distances = dijkstra(
            graph,
            a_name,
            MIN_ROUTE_DISTANCE_M
        )

        # Nodes that can actually be reached
        # by at least 5 km of road.

        candidates = [
            (
                name,
                dist
            )

            for name, dist
            in distances.items()

            if (
                dist >=
                MIN_ROUTE_DISTANCE_M
            )
        ]

        if not candidates:
            continue

        b_name, route_distance = (
            random.choice(
                candidates
            )
        )

        return (
            nodes[a_name],
            nodes[b_name],
            route_distance
        )

    return None, None, None


# ============================================================
# TELEPORT
# ============================================================

def teleport_to(position):

    print()
    print("=" * 60)
    print("TELEPORTING TO POINT A")
    print("=" * 60)

    print()

    print(
        f"X = {position['x']:.3f}"
    )

    print(
        f"Y = {position['y']:.3f}"
    )

    print(
        f"Z = {position['z']:.3f}"
    )

    response = call_mcp(
        "set_position",
        {
            "pos": position
        }
    )

    text = extract_text(
        response
    )

    if text:
        print()
        print(
            "Teleport response:",
            text
        )

    # Give physics time to settle.
    time.sleep(3)


# ============================================================
# START DRIVING
# ============================================================

def drive_to(position):

    print()
    print("=" * 60)
    print("STARTING A → B DRIVE")
    print("=" * 60)

    print()

    print(
        "Maximum speed : 80 mph"
    )

    print(
        "Speed mode    : LIMIT"
    )

    print(
        "Lane keeping  : ON"
    )

    print(
        "Avoid cars    : ON"
    )

    print(
        "Aggression    : NOT USED"
    )

    print()

    response = call_mcp(
        "drive_to",
        {
            "pos": position,

            "routeSpeed":
                MAX_SPEED_MPS,

            "routeSpeedMode":
                "limit",

            "driveInLane":
                "on",

            "avoidCars":
                "on"
        }
    )

    text = extract_text(
        response
    )

    if text:
        print(
            "Drive response:",
            text
        )

    return response


# ============================================================
# GET POSITION
# ============================================================

def get_position():

    response = call_mcp(
        "get_position",
        {}
    )

    data = extract_json(
        response
    )

    if not data:
        return None

    return data.get(
        "pos"
    )


# ============================================================
# GET INSTABILITY
# ============================================================

def get_instability():

    response = call_mcp(
        "get_instability",
        {
            "clear": True
        }
    )

    data = extract_json(
        response
    )

    if not data:
        return 0

    try:

        return int(
            data.get(
                "count",
                0
            )
        )

    except Exception:

        return 0


# ============================================================
# DISTANCE
# ============================================================

def euclidean_distance(a, b):

    dx = (
        a["x"]
        - b["x"]
    )

    dy = (
        a["y"]
        - b["y"]
    )

    dz = (
        a["z"]
        - b["z"]
    )

    return math.sqrt(
        dx * dx
        + dy * dy
        + dz * dz
    )


# ============================================================
# MONITOR
# ============================================================

def monitor_drive(
    point_b,
    route_distance
):

    print()
    print("=" * 60)
    print("MONITORING DRIVE")
    print("=" * 60)

    print()

    print(
        f"Planned road distance: "
        f"{route_distance / 1000:.2f} km"
    )

    print()

    while True:

        time.sleep(
            CHECK_INTERVAL
        )

        position = get_position()

        if position is None:

            print(
                "Position unavailable."
            )

            continue

        remaining = (
            euclidean_distance(
                position,
                point_b
            )
        )

        instability = (
            get_instability()
        )

        line = (
            f"Distance to B: "
            f"{remaining:8.1f} m"
        )

        if instability > 0:

            line += (
                f" | INSTABILITY: "
                f"{instability}"
            )

        print(line)

        # ----------------------------------------------------
        # Instability
        # ----------------------------------------------------

        if instability > 0:

            print()
            print(
                "=" * 60
            )

            print(
                "INSTABILITY DETECTED"
            )

            print(
                "=" * 60
            )

            return False

        # ----------------------------------------------------
        # Arrival
        # ----------------------------------------------------

        if (
            remaining
            <= ARRIVAL_DISTANCE_M
        ):

            print()
            print(
                "=" * 60
            )

            print(
                "DESTINATION REACHED"
            )

            print(
                "=" * 60
            )

            print()

            print(
                f"Final distance: "
                f"{remaining:.2f} m"
            )

            return True


# ============================================================
# SAVE METADATA
# ============================================================

def save_metadata(
    trip_number,
    point_a,
    point_b,
    route_distance,
    success
):

    filename = (
        f"trip_{trip_number:03d}_metadata.json"
    )

    data = {

        "trip":
            trip_number,

        "point_a":
            point_a,

        "point_b":
            point_b,

        "planned_route_distance_m":
            route_distance,

        "planned_route_distance_km":
            route_distance / 1000.0,

        "minimum_route_distance_m":
            MIN_ROUTE_DISTANCE_M,

        "maximum_speed_mph":
            80.0,

        "success":
            success,

        "timestamp":
            time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
    }

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2
        )

    print()
    print(
        f"Metadata saved: {filename}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 60)
    print(
        "       BEAMNG AUTOMATIC DATA COLLECTION"
    )
    print("=" * 60)

    print()

    print(
        "Minimum ROAD distance : "
        "5.0 km"
    )

    print(
        "Maximum speed          : "
        "80 mph"
    )

    print(
        "Aggression             : "
        "NOT USED"
    )

    print()

    # --------------------------------------------------------
    # NAVGRAPH
    # --------------------------------------------------------

    navgraph = get_navgraph()

    raw_nodes = extract_nodes(
        navgraph
    )

    print(
        f"Raw navgraph nodes: "
        f"{len(raw_nodes)}"
    )

    if not raw_nodes:

        print(
            "No navgraph nodes found."
        )

        return

    # --------------------------------------------------------
    # NODES
    # --------------------------------------------------------

    nodes = build_nodes(
        raw_nodes
    )

    print(
        f"Usable road nodes: "
        f"{len(nodes)}"
    )

    # --------------------------------------------------------
    # GRAPH
    # --------------------------------------------------------

    graph = build_graph(
        nodes
    )

    edge_count = sum(
        len(v)
        for v in graph.values()
    )

    print(
        f"Usable road links: "
        f"{edge_count}"
    )

    if edge_count == 0:

        print(
            "No usable road links found."
        )

        return

    print()

    # --------------------------------------------------------
    # TRIPS
    # --------------------------------------------------------

    successful = 0
    failed = 0

    for trip in range(
        1,
        NUMBER_OF_TRIPS + 1
    ):

        print()
        print(
            "#" * 60
        )

        print(
            f"                     TRIP {trip}"
        )

        print(
            "#" * 60
        )

        # ----------------------------------------------------
        # SELECT A/B
        # ----------------------------------------------------

        point_a_node, point_b_node, route_distance = (
            choose_a_b(
                nodes,
                graph
            )
        )

        if point_a_node is None:

            print()
            print(
                "Could not find an A → B pair "
                "with >= 5 km road distance."
            )

            print()

            print(
                "This means the currently loaded "
                "road network may have no connected "
                "route longer than 5 km."
            )

            failed += 1

            continue

        point_a = point_a_node["pos"]
        point_b = point_b_node["pos"]

        # ----------------------------------------------------
        # PRINT A
        # ----------------------------------------------------

        print()
        print("POINT A")

        print(
            f"Node: {point_a_node['name']}"
        )

        print(
            f"X = {point_a['x']:.3f}"
        )

        print(
            f"Y = {point_a['y']:.3f}"
        )

        print(
            f"Z = {point_a['z']:.3f}"
        )

        # ----------------------------------------------------
        # PRINT B
        # ----------------------------------------------------

        print()
        print("POINT B")

        print(
            f"Node: {point_b_node['name']}"
        )

        print(
            f"X = {point_b['x']:.3f}"
        )

        print(
            f"Y = {point_b['y']:.3f}"
        )

        print(
            f"Z = {point_b['z']:.3f}"
        )

        print()

        print(
            "ACTUAL ROAD DISTANCE:"
        )

        print(
            f"{route_distance:.2f} m"
        )

        print(
            f"{route_distance / 1000:.2f} km"
        )

        # ----------------------------------------------------
        # TELEPORT
        # ----------------------------------------------------

        teleport_to(
            point_a
        )

        # ----------------------------------------------------
        # DRIVE
        # ----------------------------------------------------

        drive_to(
            point_b
        )

        # ----------------------------------------------------
        # MONITOR
        # ----------------------------------------------------

        success = monitor_drive(
            point_b,
            route_distance
        )

        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------

        save_metadata(
            trip,
            point_a,
            point_b,
            route_distance,
            success
        )

        if success:
            successful += 1
        else:
            failed += 1

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("EXPERIMENT COMPLETE")
    print("=" * 60)

    print()

    print(
        f"Successful trips: "
        f"{successful}"
    )

    print(
        f"Failed trips: "
        f"{failed}"
    )

    print()

    print(
        "Remember:"
    )

    print(
        "Run collect_data.py separately "
        "to record telemetry."
    )

    print()


# ============================================================
# RUN
# ============================================================

def diagnose_graph(nodes, graph):

    print()
    print("=" * 60)
    print("NAVGRAPH DIAGNOSTIC")
    print("=" * 60)

    print("Nodes:", len(nodes))

    edge_count = sum(
        len(v) for v in graph.values()
    )

    print("Edges:", edge_count)

    if edge_count == 0:
        print()
        print("PROBLEM: ZERO EDGES")
        print("Our link parser is wrong.")
        return

    # Pick a node that actually has outgoing links
    starts = [
        n for n in graph
        if len(graph[n]) > 0
    ]

    print(
        "Nodes with outgoing links:",
        len(starts)
    )

    start = random.choice(starts)

    print()
    print("Testing node:")
    print(start)

    distances = dijkstra(
        graph,
        start,
        10000.0
    )

    print()
    print(
        "Reachable nodes within 10 km:",
        len(distances)
    )

    if distances:

        maximum = max(
            distances.values()
        )

        print(
            "Maximum explored road distance:",
            maximum,
            "m"
        )

        farthest = max(
            distances,
            key=distances.get
        )

        print(
            "Farthest node:",
            farthest
        )

        print()

        for threshold in [
            100,
            500,
            1000,
            1500,
            2000,
            3000,
            5000
        ]:

            count = sum(
                1
                for d in distances.values()
                if d >= threshold
            )

            print(
                f">= {threshold:4} m:",
                count,
                "nodes"
            )

if __name__ == "__main__":

    if __name__ == "__main__":

    navgraph = get_navgraph()

    raw_nodes = extract_nodes(
        navgraph
    )

    nodes = build_nodes(
        raw_nodes
    )

    graph = build_graph(
        nodes
    )

    diagnose_graph(
        nodes,
        graph
    )

    main()