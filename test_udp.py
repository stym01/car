import socket

HOST = "127.0.0.1"
PORT = 4445

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))

print("Listening on 4445...")

while True:
    data, addr = sock.recvfrom(4096)

    print(
        "Bytes:", len(data),
        "| First 20 bytes:",
        data[:20].hex(" ")
    )