import socket
import struct

HOST = "127.0.0.1"
PORT = 4445

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))

print("MotionSim decoder running...")
print("Drive the car in BeamNG...\n")

while True:
    data, address = sock.recvfrom(4096)

    if len(data) != 88:
        continue

    # 4 bytes = BNG1
    # 21 floats = remaining 84 bytes
    values = struct.unpack("<4s21f", data)

    marker = values[0].decode("ascii", errors="ignore")

    if marker != "BNG1":
        continue

    (
        _,
        pos_x, pos_y, pos_z,
        vel_x, vel_y, vel_z,
        acc_x, acc_y, acc_z,
        up_x, up_y, up_z,
        roll, pitch, yaw,
        roll_vel, pitch_vel, yaw_vel,
        roll_acc, pitch_acc, yaw_acc
    ) = values

    print(
        f"POS=({pos_x:.2f}, {pos_y:.2f}, {pos_z:.2f}) | "
        f"VEL=({vel_x:.2f}, {vel_y:.2f}, {vel_z:.2f}) | "
        f"ACC=({acc_x:.2f}, {acc_y:.2f}, {acc_z:.2f})"
    )