import requests
import json
import math
import random
import time
import csv
import os
import sys


# ============================================================
# CONFIGURATION
# ============================================================

MCP_URL = "http://127.0.0.1:29292/mcp"

# ------------------------------------------------------------
# EXPERIMENT
# ------------------------------------------------------------

MIN_DISTANCE_M = 5000.0

# 80 mph
MAX_SPEED_MPS = 80.0 * 0.44704

# Consider B reached within this distance
ARRIVAL_DISTANCE_M = 15.0

# How long to wait after teleporting
TELEPORT_SETTLE_TIME = 2.0

# How often to check vehicle
MONITOR_INTERVAL = 1.0

# Number of trips
NUMBER_OF_TRIPS = 1

# ------------------------------------------------------------
# NAVGRAPH
# ------------------------------------------------------------

# Maximum number of nodes requested from MCP
MAX_NAV_NODES = 100000

# Don't select tiny/unusable roads
MIN_NODE_DRIVABILITY = 0.3

# Random seed
# Set to None for different experiments every run.
RANDOM_SEED = None


# ============================================================
# RANDOM
# ============================================================

if RANDOM_SEED is not None:
    random.seed(RANDOM_SEED)


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
            timeout=30
        )

        response.raise_for_status()

        return response.json()

    except requests.exceptions.ConnectionError:

        print()
        print("=" * 60)
        print("ERROR: MCP SERVER NOT REACHABLE")
        print("=" * 60)
        print()
        print("Expected:")
        print(MCP_URL)
        print()
        print("Check BeamNG + MCP server.")
        print()

        sys.exit(1)

    except Exception as e:

        print(
            f"MCP error while calling "
            f"{tool_name}: {e}"
        )

        return None


# ============================================================
# MCP TEXT EXTRACTION
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

        # Sometimes MCP output may contain
        # extra text around JSON.

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
# GET VEHICLE POSITION
# ============================================================

def get_position():

    response = call_mcp(
        "get_position",
        {}
    )

    data = extract_json(response)

    if not data:
        return None

    return data.get("pos")


# ============================================================
# GET VEHICLE STATUS
# ============================================================

def get_status():

    response = call_mcp(
        "get_status",
        {}
    )

    return extract_json(response)


# ============================================================
# GET NAVGRAPH
# ============================================================

def get_navgraph():

    print()
    print("=" * 60)
    print("LOADING BEAMNG NAVGRAPH")
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

    if not data:

        print(
            "Could not parse navgraph."
        )

        print(response)

        return None

    return data


# ============================================================
# EXTRACT NODES
# ============================================================

def extract_nodes(navgraph):

    """
    MCP versions may return the graph using
    slightly different JSON wrappers.

    Try common structures.
    """

    if not isinstance(navgraph, dict):
        return []

    # Direct nodes
    if isinstance(
        navgraph.get("nodes"),
        list
    ):
        return navgraph["nodes"]

    # graph.nodes
    graph = navgraph.get("graph")

    if isinstance(graph, dict):

        if isinstance(
            graph.get("nodes"),
            list
        ):
            return graph["nodes"]

    # result.nodes
    result = navgraph.get("result")

    if isinstance(result, dict):

        if isinstance(
            result.get("nodes"),
            list
        ):
            return result["nodes"]

    return []


# ============================================================
# NODE POSITION
# ============================================================

def node_position(node):

    if not isinstance(node, dict):
        return None

    # Most likely:
    # {"pos":{"x":...,"y":...,"z":...}}

    pos = node.get("pos")

    if isinstance(pos, dict):

        if all(
            k in pos
            for k in ("x", "y", "z")
        ):
            return {
                "x": float(pos["x"]),
                "y": float(pos["y"]),
                "z": float(pos["z"])
            }

    # Some representations may use
    # x/y/z directly.

    if all(
        k in node
        for k in ("x", "y", "z")
    ):

        return {
            "x": float(node["x"]),
            "y": float(node["y"]),
            "z": float(node["z"])
        }

    return None


# ============================================================
# NODE ID
# ============================================================

def node_id(node):

    if not isinstance(node, dict):
        return None

    for key in (
        "id",
        "name",
        "node",
        "nodeId"
    ):

        if key in node:

            return node[key]

    return None


# ============================================================
# DISTANCE
# ============================================================

def distance(a, b):

    dx = a["x"] - b["x"]
    dy = a["y"] - b["y"]
    dz = a["z"] - b["z"]

    return math.sqrt(
        dx * dx +
        dy * dy +
        dz * dz
    )


# ============================================================
# FILTER ROAD NODES
# ============================================================

def valid_nodes(nodes):

    valid = []

    for node in nodes:

        pos = node_position(node)

        if pos is None:
            continue

        # ----------------------------------------------------
        # Drivability
        # ----------------------------------------------------

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

        if (
            drivability <
            MIN_NODE_DRIVABILITY
        ):
            continue

        # ----------------------------------------------------
        # Need an ID
        # ----------------------------------------------------

        nid = node_id(node)

        if nid is None:
            continue

        valid.append(
            {
                "id": nid,
                "pos": pos,
                "raw": node
            }
        )

    return valid


# ============================================================
# RANDOM POINT A
# ============================================================

def choose_point_a(nodes):

    return random.choice(nodes)


# ============================================================
# RANDOM POINT B
# ============================================================

def choose_point_b(nodes, point_a):

    """
    Pick a random road node at least 5 km
    from Point A.
    """

    # Try many random candidates first.

    for _ in range(1000):

        candidate = random.choice(
            nodes
        )

        d = distance(
            point_a["pos"],
            candidate["pos"]
        )

        if d >= MIN_DISTANCE_M:

            return candidate

    # --------------------------------------------------------
    # Fallback:
    # Search all nodes.
    # --------------------------------------------------------

    print(
        "Random search unsuccessful."
    )

    print(
        "Searching entire navgraph..."
    )

    candidates = []

    for candidate in nodes:

        d = distance(
            point_a["pos"],
            candidate["pos"]
        )

        if d >= MIN_DISTANCE_M:

            candidates.append(
                candidate
            )

    if not candidates:

        return None

    return random.choice(
        candidates
    )


# ============================================================
# TELEPORT
# ============================================================

def teleport_to(point):

    print()
    print("Teleporting vehicle to:")
    print(
        f"X = {point['x']:.2f}"
    )
    print(
        f"Y = {point['y']:.2f}"
    )
    print(
        f"Z = {point['z']:.2f}"
    )

    response = call_mcp(
        "set_position",
        {
            "pos": point
        }
    )

    text = extract_text(response)

    if text:
        print(
            "Teleport response:",
            text
        )

    time.sleep(
        TELEPORT_SETTLE_TIME
    )


# ============================================================
# START DRIVE
# ============================================================

def start_drive(point_b):

    print()
    print("=" * 60)
    print("STARTING DRIVE")
    print("=" * 60)

    print()
    print(
        "Maximum speed: "
        f"{MAX_SPEED_MPS:.2f} m/s "
        "(80 mph)"
    )

    print(
        "Aggression: NOT USED"
    )

    print(
        "Lane following: ON"
    )

    print(
        "Traffic avoidance: ON"
    )

    print()

    response = call_mcp(
        "drive_to",
        {
            "pos": point_b,

            # 80 mph is a LIMIT.
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

    text = extract_text(response)

    if text:
        print(
            "Drive command:",
            text
        )

    return response


# ============================================================
# CHECK INSTABILITY
# ============================================================

def check_instability():

    response = call_mcp(
        "get_instability",
        {
            "clear": True
        }
    )

    data = extract_json(response)

    if not data:
        return 0

    return int(
        data.get(
            "count",
            0
        )
    )


# ============================================================
# MONITOR DRIVE
# ============================================================

def monitor_drive(point_b):

    print()
    print("=" * 60)
    print("MONITORING DRIVE")
    print("=" * 60)
    print()

    previous_distance = None

    while True:

        time.sleep(
            MONITOR_INTERVAL
        )

        # ----------------------------------------------------
        # Position
        # ----------------------------------------------------

        position = get_position()

        if position is None:

            print(
                "Could not read position."
            )

            continue

        current_distance = distance(
            position,
            point_b
        )

        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        status = get_status()

        speed = None

        if isinstance(status, dict):

            # Try several possible locations.

            speed = status.get(
                "speed"
            )

            if speed is None:

                vehicle = status.get(
                    "vehicle"
                )

                if isinstance(
                    vehicle,
                    dict
                ):

                    speed = vehicle.get(
                        "speed"
                    )

        # ----------------------------------------------------
        # Instability
        # ----------------------------------------------------

        instability = (
            check_instability()
        )

        # ----------------------------------------------------
        # Print
        # ----------------------------------------------------

        output = (
            f"Distance to B: "
            f"{current_distance:8.1f} m"
        )

        if isinstance(
            speed,
            (int, float)
        ):

            output += (
                f" | Speed: "
                f"{speed * 2.23694:5.1f} mph"
            )

        if instability > 0:

            output += (
                f" | INSTABILITY: "
                f"{instability}"
            )

        print(output)

        # ----------------------------------------------------
        # Crash / instability
        # ----------------------------------------------------

        if instability > 0:

            print()
            print("=" * 60)
            print("INSTABILITY DETECTED")
            print("=" * 60)

            return False

        # ----------------------------------------------------
        # Destination
        # ----------------------------------------------------

        if current_distance <= ARRIVAL_DISTANCE_M:

            print()
            print("=" * 60)
            print("DESTINATION REACHED")
            print("=" * 60)

            print()
            print(
                f"Final distance: "
                f"{current_distance:.2f} m"
            )

            return True

        previous_distance = (
            current_distance
        )


# ============================================================
# SAVE EXPERIMENT INFORMATION
# ============================================================

def save_trip_metadata(
    trip_number,
    point_a,
    point_b,
    success
):

    filename = (
        f"trip_{trip_number:03d}_metadata.json"
    )

    data = {

        "trip": trip_number,

        "point_a": point_a,

        "point_b": point_b,

        "straight_line_distance_m":
            distance(
                point_a,
                point_b
            ),

        "max_speed_mps":
            MAX_SPEED_MPS,

        "max_speed_mph":
            80.0,

        "minimum_distance_m":
            MIN_DISTANCE_M,

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

    print(
        f"Metadata saved: {filename}"
    )


# ============================================================
# ONE TRIP
# ============================================================

def run_trip(
    trip_number,
    nodes
):

    print()
    print()
    print("#" * 60)
    print(
        f"                 TRIP {trip_number}"
    )
    print("#" * 60)

    # --------------------------------------------------------
    # A
    # --------------------------------------------------------

    point_a_node = choose_point_a(
        nodes
    )

    point_a = point_a_node["pos"]

    print()
    print("POINT A")
    print(
        f"X = {point_a['x']:.2f}"
    )
    print(
        f"Y = {point_a['y']:.2f}"
    )
    print(
        f"Z = {point_a['z']:.2f}"
    )

    # --------------------------------------------------------
    # B
    # --------------------------------------------------------

    point_b_node = choose_point_b(
        nodes,
        point_a_node
    )

    if point_b_node is None:

        print(
            "Could not find Point B "
            "at least 5 km away."
        )

        return False

    point_b = point_b_node["pos"]

    # --------------------------------------------------------
    # Distance
    # --------------------------------------------------------

    d = distance(
        point_a,
        point_b
    )

    print()
    print("POINT B")
    print(
        f"X = {point_b['x']:.2f}"
    )
    print(
        f"Y = {point_b['y']:.2f}"
    )
    print(
        f"Z = {point_b['z']:.2f}"
    )

    print()
    print(
        f"A → B straight distance: "
        f"{d / 1000:.2f} km"
    )

    # Safety check

    if d < MIN_DISTANCE_M:

        print(
            "ERROR: distance requirement failed."
        )

        return False

    # --------------------------------------------------------
    # Teleport
    # --------------------------------------------------------

    teleport_to(
        point_a
    )

    # --------------------------------------------------------
    # Start drive
    # --------------------------------------------------------

    start_drive(
        point_b
    )

    # --------------------------------------------------------
    # Monitor
    # --------------------------------------------------------

    success = monitor_drive(
        point_b
    )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    save_trip_metadata(
        trip_number,
        point_a,
        point_b,
        success
    )

    return success


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 60)
    print("       BEAMNG AUTOMATIC DATA COLLECTION")
    print("=" * 60)

    print()
    print("Configuration:")
    print(
        f"Minimum distance : "
        f"{MIN_DISTANCE_M / 1000:.1f} km"
    )

    print(
        f"Maximum speed    : "
        f"80 mph"
    )

    print(
        f"Trips            : "
        f"{NUMBER_OF_TRIPS}"
    )

    print(
        "Aggression       : "
        "NOT USED"
    )

    # --------------------------------------------------------
    # Get navgraph
    # --------------------------------------------------------

    navgraph = get_navgraph()

    if navgraph is None:

        print(
            "Failed to get navgraph."
        )

        return

    nodes_raw = extract_nodes(
        navgraph
    )

    print()
    print(
        f"Raw navgraph nodes: "
        f"{len(nodes_raw)}"
    )

    if not nodes_raw:

        print()
        print(
            "No nodes were returned."
        )

        print(
            "Try running get_navgraph "
            "manually and inspect its output."
        )

        return

    # --------------------------------------------------------
    # Valid nodes
    # --------------------------------------------------------

    nodes = valid_nodes(
        nodes_raw
    )

    print(
        f"Usable road nodes: "
        f"{len(nodes)}"
    )

    if len(nodes) < 2:

        print(
            "Not enough usable road nodes."
        )

        return

    print()

    # --------------------------------------------------------
    # Trips
    # --------------------------------------------------------

    successful = 0
    failed = 0

    for trip in range(
        1,
        NUMBER_OF_TRIPS + 1
    ):

        try:

            success = run_trip(
                trip,
                nodes
            )

            if success:
                successful += 1
            else:
                failed += 1

        except KeyboardInterrupt:

            print()
            print(
                "Experiment interrupted."
            )

            break

        except Exception as e:

            print()
            print(
                f"Trip {trip} failed:"
            )

            print(e)

            failed += 1

    # --------------------------------------------------------
    # Summary
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
        "Telemetry should be available "
        "in telemetry.csv."
    )

    print()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()