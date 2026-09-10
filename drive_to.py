from beamng_client import BeamNGMCP
import time


# ============================================================
# DESTINATION
# ============================================================

# CHANGE THIS TO YOUR POINT B

POINT_B = {
    "x": 800.0,
    "y": -350.0,
    "z": 160.0
}


# ============================================================
# SETTINGS
# ============================================================

ROUTE_SPEED = 8.0       # m/s ≈ 29 km/h
AGGRESSION = 0.3        # calm driving
AVOID_CARS = "on"
DRIVE_IN_LANE = "on"


# ============================================================
# START
# ============================================================

bng = BeamNGMCP()

print("==============================")
print(" BeamNG A → B Test")
print("==============================")


# Get current position

print("\nCurrent vehicle:")

position = bng.call(
    "get_position",
    {}
)

print(position)


# Clear previous instability events

bng.call(
    "get_instability",
    {
        "clear": True
    }
)


# ============================================================
# SEND A → B COMMAND
# ============================================================

print("\nSending vehicle to Point B...")

result = bng.call(
    "drive_to",
    {
        "pos": POINT_B,

        "routeSpeed": ROUTE_SPEED,

        "routeSpeedMode": "set",

        "aggression": AGGRESSION,

        "avoidCars": AVOID_CARS,

        "driveInLane": DRIVE_IN_LANE
    }
)

print("\nDrive command result:")
print(result)


print("\nBeamNG AI is now driving.")

print("Press Ctrl+C to stop monitoring.")


# ============================================================
# MONITOR
# ============================================================

try:

    while True:

        time.sleep(2)

        position = bng.call(
            "get_position",
            {}
        )

        print(
            "\nPOSITION:"
        )

        print(position)


        instability = bng.call(
            "get_instability",
            {
                "clear": True
            }
        )

        print(
            "INSTABILITY:"
        )

        print(instability)


except KeyboardInterrupt:

    print("\nStopping vehicle...")

    # Full brake

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

    print("Vehicle stopped.")