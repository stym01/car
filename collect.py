import socket
import struct
import threading
import time
import csv
import os

HOST = "127.0.0.1"

MOTIONSIM_PORT = 4445
OUTGAUGE_PORT = 4444

output_file = "telemetry.csv"

latest_motion = {}
latest_outgauge = {}

lock = threading.Lock()


# -----------------------------
# MotionSim
# -----------------------------

def motion_listener():

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, MOTIONSIM_PORT))

    print(f"[MotionSim] Listening on {MOTIONSIM_PORT}")

    while True:

        data, _ = sock.recvfrom(4096)

        if len(data) != 88:
            continue

        values = struct.unpack("<4s21f", data)

        if values[0] != b"BNG1":
            continue

        with lock:
            latest_motion.update({

                "pos_x": values[1],
                "pos_y": values[2],
                "pos_z": values[3],

                "vel_x": values[4],
                "vel_y": values[5],
                "vel_z": values[6],

                "acc_x": values[7],
                "acc_y": values[8],
                "acc_z": values[9],

                "up_x": values[10],
                "up_y": values[11],
                "up_z": values[12],

                "roll": values[13],
                "pitch": values[14],
                "yaw": values[15],

                "roll_vel": values[16],
                "pitch_vel": values[17],
                "yaw_vel": values[18],

                "roll_acc": values[19],
                "pitch_acc": values[20],
                "yaw_acc": values[21],
            })


# -----------------------------
# OutGauge
# -----------------------------

def outgauge_listener():

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, OUTGAUGE_PORT))

    print(f"[OutGauge] Listening on {OUTGAUGE_PORT}")

    while True:

        data, _ = sock.recvfrom(4096)

        if len(data) != 96:
            continue

        values = struct.unpack("<I4sHbb7f2I3f32si", data)

        with lock:

            latest_outgauge.update({

                "game_time": values[0],

                "speed": values[5],
                "rpm": values[6],
                "turbo": values[7],
                "engine_temp": values[8],
                "fuel": values[9],
                "oil_pressure": values[10],
                "oil_temp": values[11],

                "throttle": values[18],
                "brake": values[19],
                "clutch": values[20],

                "gear": values[3],
            })


# -----------------------------
# CSV writer
# -----------------------------

def csv_writer():

    fields = [
        "timestamp",

        # MotionSim
        "pos_x", "pos_y", "pos_z",
        "vel_x", "vel_y", "vel_z",
        "acc_x", "acc_y", "acc_z",
        "roll", "pitch", "yaw",
        "roll_vel", "pitch_vel", "yaw_vel",
        "roll_acc", "pitch_acc", "yaw_acc",

        # OutGauge
        "game_time",
        "speed",
        "rpm",
        "turbo",
        "engine_temp",
        "fuel",
        "oil_pressure",
        "oil_temp",
        "throttle",
        "brake",
        "clutch",
        "gear"
    ]

    with open(output_file, "w", newline="") as f:

        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        print(f"[CSV] Recording to {output_file}")

        while True:

            time.sleep(0.01)  # 100 Hz

            with lock:

                if not latest_motion or not latest_outgauge:
                    continue

                row = {
                    "timestamp": time.time()
                }

                row.update(latest_motion)
                row.update(latest_outgauge)

            writer.writerow(row)
            f.flush()


# -----------------------------
# Start everything
# -----------------------------

if __name__ == "__main__":

    print("==============================")
    print(" BeamNG Research Data Logger")
    print("==============================")

    threading.Thread(
        target=motion_listener,
        daemon=True
    ).start()

    threading.Thread(
        target=outgauge_listener,
        daemon=True
    ).start()

    csv_writer()