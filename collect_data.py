import socket
import struct
import threading
import csv
import time
import math

HOST = "127.0.0.1"

MOTIONSIM_PORT = 4445
OUTGAUGE_PORT = 4444

OUTPUT_FILE = "research_dataset.csv"

running = True

motion_latest = None
outgauge_latest = None

lock = threading.Lock()


# ============================================================
# MOTIONSIM
# ============================================================

def motion_listener():

    global motion_latest

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, MOTIONSIM_PORT))

    print(f"[MotionSim] Listening on {MOTIONSIM_PORT}")

    while running:

        try:
            data, _ = sock.recvfrom(4096)
        except Exception:
            continue

        if len(data) != 88:
            continue

        try:
            values = struct.unpack("<4s21f", data)
        except struct.error:
            continue

        if values[0] != b"BNG1":
            continue

        sample = {
            "timestamp": time.perf_counter(),

            "x_m": values[1],
            "y_m": values[2],
            "z_m": values[3],

            "vx_mps": values[4],
            "vy_mps": values[5],
            "vz_mps": values[6],

            "ax_mps2": values[7],
            "ay_mps2": values[8],
            "az_mps2": values[9],

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
        }

        with lock:
            motion_latest = sample


# ============================================================
# OUTGAUGE
# ============================================================

def outgauge_listener():

    global outgauge_latest

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, OUTGAUGE_PORT))

    print(f"[OutGauge] Listening on {OUTGAUGE_PORT}")

    while running:

        try:
            data, _ = sock.recvfrom(4096)
        except Exception:
            continue

        if len(data) != 96:
            continue

        try:
            values = struct.unpack("<I4sHbb7f2I3f32si", data)
        except struct.error:
            continue

        sample = {
            "timestamp": time.perf_counter(),

            "gear_index": values[3],

            "speed_mps": values[5],
            "rpm": values[6],

            "coolant_c": values[8],
            "fuel": values[9],

            "oil_pressure": values[10],
            "oil_c": values[11],

            "throttle": values[16],
            "brake": values[17],
            "clutch": values[18],
        }

        with lock:
            outgauge_latest = sample


# ============================================================
# CSV
# ============================================================

FIELDS = [
    "t_s",
    "seq",

    "x_m",
    "y_m",
    "z_m",

    "vx_mps",
    "vy_mps",
    "vz_mps",

    "speed_mps",

    "ax_mps2",
    "ay_mps2",
    "az_mps2",

    "dir_x",
    "dir_y",
    "dir_z",

    "rpm",
    "engine_av_rads",

    "gear_index",

    "throttle",
    "brake",
    "clutch",

    "coolant_c",
    "oil_c",
    "fuel",

    "roll",
    "pitch",
    "yaw",

    "roll_vel",
    "pitch_vel",
    "yaw_vel",

    "roll_acc",
    "pitch_acc",
    "yaw_acc",
]


def calculate_speed(vx, vy, vz):

    return math.sqrt(
        vx * vx +
        vy * vy +
        vz * vz
    )


def calculate_direction(vx, vy, vz):

    speed = calculate_speed(vx, vy, vz)

    if speed < 0.1:
        return float("nan"), float("nan"), float("nan")

    return (
        vx / speed,
        vy / speed,
        vz / speed
    )


def csv_writer():

    global running

    seq = 0
    start_time = None

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=FIELDS
        )

        writer.writeheader()

        print(f"[CSV] Recording to {OUTPUT_FILE}")

        while running:

            time.sleep(0.01)

            with lock:

                motion = motion_latest
                gauge = outgauge_latest

            if motion is None:
                continue

            if gauge is None:
                continue

            if start_time is None:
                start_time = motion["timestamp"]

            vx = motion["vx_mps"]
            vy = motion["vy_mps"]
            vz = motion["vz_mps"]

            speed = calculate_speed(vx, vy, vz)

            dx, dy, dz = calculate_direction(
                vx,
                vy,
                vz
            )

            rpm = gauge["rpm"]

            row = {

                "t_s":
                    motion["timestamp"] - start_time,

                "seq":
                    seq,

                "x_m":
                    motion["x_m"],

                "y_m":
                    motion["y_m"],

                "z_m":
                    motion["z_m"],

                "vx_mps":
                    vx,

                "vy_mps":
                    vy,

                "vz_mps":
                    vz,

                "speed_mps":
                    speed,

                "ax_mps2":
                    motion["ax_mps2"],

                "ay_mps2":
                    motion["ay_mps2"],

                "az_mps2":
                    motion["az_mps2"],

                "dir_x":
                    dx,

                "dir_y":
                    dy,

                "dir_z":
                    dz,

                "rpm":
                    rpm,

                "engine_av_rads":
                    rpm * 2 * math.pi / 60,

                "gear_index":
                    gauge["gear_index"],

                "throttle":
                    gauge["throttle"],

                "brake":
                    gauge["brake"],

                "clutch":
                    gauge["clutch"],

                "coolant_c":
                    gauge["coolant_c"],

                "oil_c":
                    gauge["oil_c"],

                "fuel":
                    gauge["fuel"],

                "roll":
                    motion["roll"],

                "pitch":
                    motion["pitch"],

                "yaw":
                    motion["yaw"],

                "roll_vel":
                    motion["roll_vel"],

                "pitch_vel":
                    motion["pitch_vel"],

                "yaw_vel":
                    motion["yaw_vel"],

                "roll_acc":
                    motion["roll_acc"],

                "pitch_acc":
                    motion["pitch_acc"],

                "yaw_acc":
                    motion["yaw_acc"],
            }

            writer.writerow(row)

            seq += 1

            if seq % 100 == 0:

                print(
                    f"Samples={seq:6d} | "
                    f"Speed={speed:6.2f} m/s | "
                    f"RPM={rpm:6.0f}"
                )

            file.flush()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print("==============================")
    print(" BeamNG Research Data Logger")
    print("==============================")

    t1 = threading.Thread(
        target=motion_listener,
        daemon=True
    )

    t2 = threading.Thread(
        target=outgauge_listener,
        daemon=True
    )

    t1.start()
    t2.start()

    try:

        csv_writer()

    except KeyboardInterrupt:

        print("\nStopping...")

        running = False

    print("Dataset saved:", OUTPUT_FILE)