import requests
import json
import math
import time
import sys


# ============================================================
# CONFIGURATION
# ============================================================

MCP_URL = "http://127.0.0.1:29292/mcp"

# ------------------------------------------------------------
# POINT B
# ------------------------------------------------------------

POINT_B = {
    "x": -822.21875,
    "y": -835.28070068359,
    "z": 119.6600189209
}

# ------------------------------------------------------------
# DRIVING SETTINGS
# ------------------------------------------------------------

# 80 mph -> m/s
MAX_SPEED_MPS = 80.0 * 0.44704

# Minimum A -> B straight-line distance
MIN_DISTANCE_M = 5000.0

# Consider destination reached inside this radius
ARRIVAL_DISTANCE_M = 12.0

# Position checking interval
CHECK_INTERVAL = 1.0


# ============================================================
# MCP REQUEST
# ============================================================

request_id = 0


def call_mcp(tool_name, arguments):
    """
    Calls BeamNG's MCP server.
    """

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
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        return data

    except requests.exceptions.ConnectionError:

        print()
        print("ERROR: Could not connect to BeamNG MCP.")
        print()
        print("Make sure:")
        print("1. BeamNG.drive is running")
        print("2. MCP server is enabled")
        print("3. MCP server is listening on:")
        print(MCP_URL)
        print()

        sys.exit(1)

    except Exception as e:

        print("MCP ERROR:", e)
        return None


# ============================================================
# EXTRACT MCP TEXT RESULT
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
# GET VEHICLE POSITION
# ============================================================

def get_position():

    response = call_mcp(
        "get_position",
        {}
    )

    text = extract_text(response)

    if text is None:

        print("Could not read vehicle position.")
        print(response)

        return None

    try:

        data = json.loads(text)

        return data["pos"]

    except Exception as e:

        print("Position parsing error:", e)
        print("Raw response:", text)

        return None


# ============================================================
# DISTANCE BETWEEN TWO POSITIONS
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
# GET CURRENT VEHICLE STATUS
# ============================================================

def get_status():

    response = call_mcp(
        "get_status",
        {}
    )

    text = extract_text(response)

    if text is None:
        return None

    try:
        return json.loads(text)

    except Exception:
        return None


# ============================================================
# CHECK FOR INSTABILITY
# ============================================================

def check_instability():

    response = call_mcp(
        "get_instability",
        {
            "clear": True
        }
    )

    text = extract_text(response)

    if text is None:
        return 0

    try:

        data = json.loads(text)

        return data.get("count", 0)

    except Exception:

        return 0


# ============================================================
# START DRIVING
# ============================================================

def start_drive():

    print()
    print("=" * 60)
    print("STARTING BEAMNG NAVIGATION")
    print("=" * 60)

    print()
    print("Driving mode:")
    print("  Navigation AI        : ON")
    print("  Lane following       : ON")
    print("  Traffic avoidance    : ON")
    print("  Aggression parameter  : NOT USED")
    print("  Maximum speed        : 80 mph")
    print("  Speed mode           : LIMIT")
    print()

    response = call_mcp(
        "drive_to",
        {
            "pos": POINT_B,

            # 80 mph maximum
            "routeSpeed": MAX_SPEED_MPS,

            # IMPORTANT:
            # This is a maximum, NOT a constant target speed.
            "routeSpeedMode": "limit",

            # Stay on the proper lane.
            "driveInLane": "on",

            # Avoid other vehicles.
            "avoidCars": "on"
        }
    )

    print("BeamNG response:")

    text = extract_text(response)

    if text:
        print(text)

    print()

    return response


# ============================================================
# MAIN EXPERIMENT
# ============================================================

def main():

    print()
    print("=" * 60)
    print("       BEAMNG HUMAN-LIKE DRIVE TEST")
    print("=" * 60)
    print()

    # --------------------------------------------------------
    # Get Point A
    # --------------------------------------------------------

    print("Getting current vehicle position...")

    point_a = get_position()

    if point_a is None:

        print("Could not obtain Point A.")
        return

    print()
    print("POINT A")
    print(
        f"X = {point_a['x']:.3f}\n"
        f"Y = {point_a['y']:.3f}\n"
        f"Z = {point_a['z']:.3f}"
    )

    print()
    print("POINT B")
    print(
        f"X = {POINT_B['x']:.3f}\n"
        f"Y = {POINT_B['y']:.3f}\n"
        f"Z = {POINT_B['z']:.3f}"
    )

    # --------------------------------------------------------
    # Calculate distance
    # --------------------------------------------------------

    start_distance = distance(
        point_a,
        POINT_B
    )

    print()
    print(
        f"Straight-line distance: "
        f"{start_distance:.2f} m"
    )

    print(
        f"Straight-line distance: "
        f"{start_distance / 1000:.2f} km"
    )

    # --------------------------------------------------------
    # Minimum 5 km requirement
    # --------------------------------------------------------

    if start_distance < MIN_DISTANCE_M:

        print()
        print("=" * 60)
        print("DISTANCE TOO SHORT")
        print("=" * 60)

        print(
            f"Required minimum : "
            f"{MIN_DISTANCE_M / 1000:.1f} km"
        )

        print(
            f"Current distance : "
            f"{start_distance / 1000:.2f} km"
        )

        print()
        print("Choose a farther Point B.")

        return

    print()
    print("5 km minimum requirement: PASS")

    # --------------------------------------------------------
    # Start AI
    # --------------------------------------------------------

    start_drive()

    print("=" * 60)
    print("VEHICLE IS NOW DRIVING")
    print("=" * 60)

    print()
    print("Press CTRL+C to stop manually.")
    print()

    # --------------------------------------------------------
    # Monitor vehicle
    # --------------------------------------------------------

    last_distance = start_distance

    total_progress = 0.0

    while True:

        try:

            time.sleep(CHECK_INTERVAL)

            # ------------------------------------------------
            # Position
            # ------------------------------------------------

            position = get_position()

            if position is None:

                print("Position unavailable.")
                continue

            current_distance = distance(
                position,
                POINT_B
            )

            # ------------------------------------------------
            # Progress
            # ------------------------------------------------

            progress = last_distance - current_distance

            if progress > 0:
                total_progress += progress

            last_distance = current_distance

            # ------------------------------------------------
            # Status
            # ------------------------------------------------

            status = get_status()

            speed = None

            if status:

                try:

                    speed = status.get(
                        "speed"
                    )

                except Exception:
                    speed = None

            # ------------------------------------------------
            # Print
            # ------------------------------------------------

            print(
                f"Distance: "
                f"{current_distance:8.2f} m"
                f" | Progress: "
                f"{total_progress:8.2f} m"
                + (
                    f" | Speed: {speed:.2f} m/s"
                    if isinstance(speed, (int, float))
                    else ""
                )
            )

            # ------------------------------------------------
            # Instability
            # ------------------------------------------------

            instability = check_instability()

            if instability > 0:

                print()
                print("WARNING!")
                print(
                    f"BeamNG reported "
                    f"{instability} instability event(s)."
                )
                print()

            # ------------------------------------------------
            # ARRIVAL
            # ------------------------------------------------

            if current_distance <= ARRIVAL_DISTANCE_M:

                print()
                print("=" * 60)
                print("           DESTINATION REACHED")
                print("=" * 60)

                print()
                print(
                    f"Final distance: "
                    f"{current_distance:.2f} m"
                )

                print(
                    f"Total progress: "
                    f"{total_progress:.2f} m"
                )

                print()

                # IMPORTANT:
                #
                # We DO NOT:
                # - inject parking brake
                # - remove parking brake
                # - inject throttle
                # - inject steering
                # - inject brake
                #
                # BeamNG AI owns the vehicle.
                #
                # This avoids the abnormal behavior we saw
                # at the previous destination.

                print(
                    "Leaving vehicle control to BeamNG "
                    "at destination."
                )

                print()
                break

        except KeyboardInterrupt:

            print()
            print("=" * 60)
            print("MANUAL STOP")
            print("=" * 60)

            print()
            print("Experiment interrupted by user.")

            # Do NOT mess with parking brake here.
            # Simply stop monitoring.

            break

        except Exception as e:

            print()
            print("Monitoring error:")
            print(e)
            print()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()