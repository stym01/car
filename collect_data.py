import socket
import struct
import threading
import csv
import time
import math

HOST = "127.0.0.1"

SAMPLE_RATE_HZ = 5
SAMPLE_INTERVAL = 1.0 / SAMPLE_RATE_HZ

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

def clean_number(value):
    """
    Convert BeamNG telemetry values into normal Python numbers.
    """

    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", errors="ignore")
        except:
            return 0.0

    if isinstance(value, str):

        value = value.strip()

        # Remove byte-string representation if present
        if value.startswith("b'") or value.startswith('b"'):
            try:
                value = eval(value)
            except:
                pass

    try:
        return float(value)
    except:
        return 0.0


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
    print(f"[CSV] Recording at {SAMPLE_RATE_HZ} Hz")

    fieldnames = [
        "t_s", "seq",
        "x_m", "y_m", "z_m",
        "vx_mps", "vy_mps", "vz_mps",
        "speed_mps",
        "ax_mps2", "ay_mps2", "az_mps2",
        "dir_x", "dir_y", "dir_z",

        "rpm",
        "engine_torque_nm",
        "engine_av_rads",
        "engine_load",
        "exhaust_flow",

        "gear_index",
        "clutch_ratio",
        "throttle",
        "brake",
        "steering",

        "wheel_av_fl",
        "wheel_av_fr",
        "wheel_av_rl",
        "wheel_av_rr",

        "brake_temp_fl",
        "brake_temp_fr",
        "brake_temp_rl",
        "brake_temp_rr",

        "downforce_fl",
        "coolant_c",
        "oil_c",
        "fuel_volume_l",
        "odometer_m",
        "trip_m",
        "altitude_m",

        "ignition_level",
        "parkingbrake",
        "avg_wheel_av",
        "engine_running",
        "damage"
    ]

    with open("telemetry.csv", "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            extrasaction="ignore"
        )

        writer.writeheader()

        next_sample = time.monotonic()

        while True:
            now = time.monotonic()

            if now >= next_sample:

                with data_lock:
                    row = latest_data.copy()

                if row:
                    writer.writerow(row)
                    f.flush()

                next_sample += SAMPLE_INTERVAL

            else:
                time.sleep(0.005)

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