from beamng_client import BeamNGMCP
import time

# ============================================================
# POINT B
# ============================================================

POINT_B = {
    "x": -822.21875,
    "y": -835.28070068359,
    "z": 119.6600189209
}


# ============================================================
# DRIVING SETTINGS
# ============================================================

# 6 m/s ≈ 21.6 km/h
# Start slowly so we can verify the route is safe.
ROUTE_SPEED = 6.0

# Lower = more cautious
AGGRESSION = 0.1


# ============================================================
# CONNECT TO BEAMNG MCP
# ============================================================

print("==============================")
print(" BeamNG A -> B Test")
print("==============================")

bng = BeamNGMCP()


# ============================================================
# GET STARTING POSITION
# ============================================================

print("\nGetting starting position...")

start = bng.call(
    "get_position",
    {}
)

print("START:")
print(start)


# ============================================================
# CLEAR OLD INSTABILITY EVENTS
# ============================================================

print("\nClearing previous instability events...")

bng.call(
    "get_instability",
    {
        "clear": True
    }
)


# ============================================================
# DRIVE TO POINT B
# ============================================================

print("\n==============================")
print("Driving to Point B")
print("==============================")

print(f"Point B:")
print(f"X = {POINT_B['x']}")
print(f"Y = {POINT_B['y']}")
print(f"Z = {POINT_B['z']}")

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
# MONITOR VEHICLE
# ============================================================

print("\nVehicle is driving...")
print("Press CTRL+C to stop.\n")


try:

    while True:

        time.sleep(2)

        position = bng.call(
            "get_position",
            {}
        )

        print("\nPOSITION:")
        print(position)


        instability = bng.call(
            "get_instability",
            {
                "clear": True
            }
        )

        print("\nINSTABILITY:")
        print(instability)


except KeyboardInterrupt:

    print("\nStopping test...")

    # Stop throttle
    bng.call(
        "inject_input",
        {
            "event": "throttle",
            "value": 0
        }
    )

    # Apply brake
    bng.call(
        "inject_input",
        {
            "event": "brake",
            "value": 1
        }
    )

    # Center steering
    bng.call(
        "inject_input",
        {
            "event": "steering",
            "value": 0
        }
    )

    print("Vehicle stopped.")