from beamng_client import BeamNGMCP

bng = BeamNGMCP()

result = bng.call(
    "get_position",
    {}
)

print("\nVehicle position:")
print(result)