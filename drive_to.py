from beamng_client import BeamNGMCP
import time
import json
import math


# ============================================================
# POINT B
# ============================================================

POINT_B = {
    "x": -822.21875,
    "y": -835.28070068359,
    "z": 119.6600189209
}


# ============================================================
# DRIVER SETTINGS
# ============================================================

ROUTE_SPEED = 12.0       # 43.2 km/h
AGGRESSION = 0.2

CHECK_INTERVAL = 2.0

# Distance considered "reached"
TARGET_DISTANCE = 8.0

# If vehicle moves less than this for several checks,
# consider it stuck.
MIN_MOVEMENT = 0.5

MAX_STUCK_CHECKS = 5


# ============================================================
# HELPER
# ============================================================

def extract_position(response):

    try:

        data = json.loads(response)

        text = data["result"]["content"][0]["text"]

        vehicle = json.loads(text)

        return vehicle["pos"]

    except Exception as e:

        print("Position parsing error:", e)

        return None


def distance(p1, p2):

    return math.sqrt(
        (p1["x"] - p2["x"]) ** 2 +
        (p1["y"] - p2["y"]) ** 2 +
        (p1["z"] - p2["z"]) ** 2
    )


# ============================================================
# START
# ============================================================

print("==============================")
print(" BeamNG Realistic A -> B Test")
print("==============================")


bng = BeamNGMCP()


# ============================================================
# GET START POSITION
# ============================================================

response = bng.call(
    "get_position",
    {}
)

start_pos = extract_position(response)

print("\nSTART POSITION:")

if start_pos:
    print(
        f"X={start_pos['x']:.2f} "
        f"Y={start_pos['y']:.2f} "
        f"Z={start_pos['z']:.2f}"
    )


# ============================================================
# CLEAR INSTABILITY
# ============================================================

bng.call(
    "get_instability",
    {
        "clear": True
    }
)


# ============================================================
# START DRIVING
# ============================================================

print("\n==============================")
print("Starting AI driver")
print("==============================")

print(
    f"Target: "
    f"{POINT_B['x']:.2f}, "
    f"{POINT_B['y']:.2f}, "
    f"{POINT_B['z']:.2f}"
)

print(f"Speed: {ROUTE_SPEED} m/s")
print(f"Speed: {ROUTE_SPEED * 3.6:.1f} km/h")
print(f"Aggression: {AGGRESSION}")


result = bng.call(
    "drive_to",
    {
        "pos": POINT_B,

        "routeSpeed": ROUTE_SPEED,

        "routeSpeedMode": "set",

        "aggression": AGGRESSION,

        "avoidCars": "on",

        "driveInLane": "on"
    }
)

print("\nDrive command:")
print(result)


# ============================================================
# MONITOR
# ============================================================

previous_pos = start_pos

stuck_checks = 0

start_time = time.time()


try:

    while True:

        time.sleep(CHECK_INTERVAL)

        response = bng.call(
            "get_position",
            {}
        )

        current_pos = extract_position(response)

        if current_pos is None:
            continue


        # ----------------------------------------------------
        # DISTANCE TO TARGET
        # ----------------------------------------------------

        target_distance = distance(
            current_pos,
            POINT_B
        )


        # ----------------------------------------------------
        # MOVEMENT
        # ----------------------------------------------------

        movement = 0

        if previous_pos:

            movement = distance(
                current_pos,
                previous_pos
            )


        # ----------------------------------------------------
        # TIME
        # ----------------------------------------------------

        elapsed = time.time() - start_time


        print(
            f"\nTime: {elapsed:6.1f}s"
            f" | Distance to B: {target_distance:7.2f} m"
            f" | Movement: {movement:5.2f} m"
        )


        # ----------------------------------------------------
        # CHECK IF REACHED
        # ----------------------------------------------------

        if target_distance <= TARGET_DISTANCE:

            print("\n================================")
            print(" TARGET REACHED!")
            print("================================")

            break


        # ----------------------------------------------------
        # CHECK IF STUCK
        # ----------------------------------------------------

        if movement < MIN_MOVEMENT:

            stuck_checks += 1

            print(
                f"Vehicle may be stuck "
                f"({stuck_checks}/{MAX_STUCK_CHECKS})"
            )

        else:

            stuck_checks = 0


        if stuck_checks >= MAX_STUCK_CHECKS:

            print("\n================================")
            print(" VEHICLE APPEARS STUCK")
            print(" Stopping experiment")
            print("================================")

            break


        previous_pos = current_pos


except KeyboardInterrupt:

    print("\nExperiment manually stopped.")


# ============================================================
# STOP VEHICLE
# ============================================================

print("\nStopping vehicle...")

bng.call(
    "inject_input",
    {
        "event": "throttle",
        "value": 0
    }
)

bng.call(
    "inject_input",
    {
        "event": "brake",
        "value": 1
    }
)

bng.call(
    "inject_input",
    {
        "event": "steering",
        "value": 0
    }
)

print("Done.")