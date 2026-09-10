import socket

HOST = "127.0.0.1"
PORT = 4445

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))

print(f"Listening on UDP {HOST}:{PORT}")
print("Now drive the car in BeamNG...\n")

while True:
    data, address = sock.recvfrom(4096)

    print(f"Received {len(data)} bytes from {address}")