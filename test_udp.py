import socket
import struct

HOST = "127.0.0.1"
PORT = 4445

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))

print("MotionSim decoder running...")
print("Drive the car.\n")

while True:
    data, address = sock.recvfrom(4096)

    if len(data) != 76:
        continue

    values = struct.unpack("<4s18f", data)

    print(
        f"Position: {values[1]:.2f}, {values[2]:.2f}, {values[3]:.2f} | "
        f"Velocity: {values[4]:.2f}, {values[5]:.2f}, {values[6]:.2f} | "
        f"Acceleration: {values[7]:.2f}, {values[8]:.2f}, {values[9]:.2f}"
    )