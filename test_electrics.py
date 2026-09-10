from beamng_client import BeamNGMCP

bng = BeamNGMCP()

result = bng.call(
    "get_electrics",
    {
        "keys": [
            "rpm",
            "gear",
            "throttle",
            "brake",
            "steering",
            "wheelspeed",
            "coolantTemperature",
            "oilTemperature"
        ]
    }
)

print("\nVehicle electrics:")
print(result)