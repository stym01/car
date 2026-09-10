import socket
import struct

HOST = "127.0.0.1"
PORT = 4444

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))

print("Listening for OutGauge on 127.0.0.1:4444...")
print("Drive the car in BeamNG...\n")

while True:
    data, address = sock.recvfrom(4096)

    print(f"Received {len(data)} bytes")