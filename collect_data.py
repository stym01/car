import socket
import struct
import threading
import csv
import time
import math


# ============================================================
# CONFIGURATION
# ============================================================

HOST = "127.0.0.1"

SAMPLE_RATE_HZ = 5
SAMPLE_INTERVAL = 1.0 / SAMPLE_RATE_HZ

MOTIONSIM_PORT = 4445
OUTGAUGE_PORT = 4444

OUTPUT_FILE = "telemetry.csv"

MAX_DATA_AGE = 0.5


# ============================================================
# VEHICLE CONFIGURATION
# ============================================================

# Put the actual mass of your BeamNG vehicle here.
# Example:
# VEHICLE_MASS_KG = 1500.0
#
# Keep NaN if you don't know it yet.

VEHICLE_MASS_KG = float("nan")


# ============================================================
# GLOBAL STATE
# ============================================================

running = True

motion_latest = None
outgauge_latest = None

data_lock = threading.Lock()

distance_lock = threading.Lock()

odometer_m = 0.0
trip_m = 0.0

last_distance_time = None


# ============================================================
# BATTERY STATE
# ============================================================
#
# IMPORTANT:
#
# These are intentionally NOT fake values.
#
# They will remain NaN until we connect a genuine battery
# telemetry source.
#
# This keeps your research dataset scientifically valid.
#
# ============================================================

battery_voltage_v = float("nan")
battery_current_a = float("nan")
battery_temperature_c = float("nan")
battery_soc = float("nan")

battery_energy_wh = float("nan")


# ============================================================
# HELPERS
# ============================================================

def calculate_speed(vx, vy, vz):

    return math.sqrt(
        vx * vx +
        vy * vy +
        vz * vz
    )


def calculate_direction(vx, vy, vz):

    speed = calculate_speed(
        vx,
        vy,
        vz
    )

    if speed < 0.1:

        return (
            0.0,
            0.0,
            0.0
        )

    return (
        vx / speed,
        vy / speed,
        vz / speed
    )


# ============================================================
# MOTIONSIM
# ============================================================

def motion_listener():

    global motion_latest

    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    )

    sock.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    sock.bind(
        (HOST, MOTIONSIM_PORT)
    )

    sock.settimeout(1.0)

    print(
        f"[MotionSim] Listening on "
        f"{MOTIONSIM_PORT}"
    )

    while running:

        try:

            data, _ = sock.recvfrom(4096)

        except socket.timeout:

            continue

        except Exception:

            continue

        # BNG1 + 21 floats = 88 bytes

        if len(data) != 88:

            continue

        try:

            values = struct.unpack(
                "<4s21f",
                data
            )

        except struct.error:

            continue

        if values[0] != b"BNG1":

            continue

        vx = values[4]
        vy = values[5]
        vz = values[6]

        speed = calculate_speed(
            vx,
            vy,
            vz
        )

        dir_x, dir_y, dir_z = (
            calculate_direction(
                vx,
                vy,
                vz
            )
        )

        sample = {

            "timestamp":
                time.perf_counter(),

            "x_m": values[1],
            "y_m": values[2],
            "z_m": values[3],

            "vx_mps": vx,
            "vy_mps": vy,
            "vz_mps": vz,

            "speed_mps": speed,

            "ax_mps2": values[7],
            "ay_mps2": values[8],
            "az_mps2": values[9],

            "dir_x": dir_x,
            "dir_y": dir_y,
            "dir_z": dir_z,

            "roll": values[13],
            "pitch": values[14],
            "yaw": values[15],

            "roll_vel": values[16],
            "pitch_vel": values[17],
            "yaw_vel": values[18],

            "roll_acc": values[19],
            "pitch_acc": values[20],
            "yaw_acc": values[21]
        }

        with data_lock:

            motion_latest = sample


# ============================================================
# OUTGAUGE
# ============================================================

def outgauge_listener():

    global outgauge_latest

    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    )

    sock.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    sock.bind(
        (HOST, OUTGAUGE_PORT)
    )

    sock.settimeout(1.0)

    print(
        f"[OutGauge] Listening on "
        f"{OUTGAUGE_PORT}"
    )

    while running:

        try:

            data, _ = sock.recvfrom(4096)

        except socket.timeout:

            continue

        except Exception:

            continue

        if len(data) != 96:

            continue

        try:

            values = struct.unpack(
                "<I4sHbb7f2I3f32si",
                data
            )

        except struct.error as e:

            print(
                "[OutGauge] Decode error:",
                e
            )

            continue

        # ====================================================
        # GEAR
        # ====================================================

        raw_gear = values[3]

        if raw_gear == 0:

            gear_index = -1

        else:

            gear_index = raw_gear - 1

        # ====================================================
        # DASHBOARD FLAGS
        # ====================================================

        show_lights = values[13]

        # Handbrake flag

        parkingbrake = (
            1.0
            if (show_lights & 4)
            else 0.0
        )

        # ====================================================
        # OUTGAUGE VALUES
        # ====================================================

        sample = {

            "timestamp":
                time.perf_counter(),

            "gear_index":
                gear_index,

            "speed_mps":
                values[5],

            "rpm":
                values[6],

            "coolant_c":
                values[8],

            "fuel":
                values[9],

            "oil_pressure":
                values[10],

            "oil_c":
                values[11],

            # IMPORTANT:
            # Correct OutGauge indices

            "throttle":
                values[14],

            "brake":
                values[15],

            "clutch":
                values[16],

            "parkingbrake":
                parkingbrake
        }

        with data_lock:

            outgauge_latest = sample


# ============================================================
# CSV FIELDS
# ============================================================

FIELDS = [

    "t_s",
    "seq",

    # Position
    "x_m",
    "y_m",
    "z_m",

    # Velocity
    "vx_mps",
    "vy_mps",
    "vz_mps",

    # Speed
    "speed_mps",

    # Acceleration
    "ax_mps2",
    "ay_mps2",
    "az_mps2",

    # Direction
    "dir_x",
    "dir_y",
    "dir_z",

    # Vehicle
    "mass_kg",

    # Engine
    "rpm",
    "engine_torque_nm",
    "engine_av_rads",
    "engine_load",
    "exhaust_flow",

    # Transmission
    "gear_index",
    "clutch_ratio",

    # Driver inputs
    "throttle",
    "brake",
    "steering",

    # Wheels
    "wheel_av_fl",
    "wheel_av_fr",
    "wheel_av_rl",
    "wheel_av_rr",

    # Brake temperature
    "brake_temp_fl",
    "brake_temp_fr",
    "brake_temp_rl",
    "brake_temp_rr",

    # Aerodynamics
    "downforce_fl",

    # Temperature
    "coolant_c",
    "oil_c",

    # Fuel
    "fuel_volume_l",

    # Distance
    "odometer_m",
    "trip_m",

    # Altitude
    "altitude_m",

    # Vehicle state
    "ignition_level",
    "parkingbrake",
    "avg_wheel_av",
    "engine_running",
    "damage",

    # ========================================================
    # BATTERY
    # ========================================================

    "battery_voltage_v",
    "battery_current_a",
    "battery_temperature_c",
    "battery_soc",

    "battery_power_w",
    "battery_energy_wh",

    # Oil
    "oil_pressure",

    # Orientation
    "roll",
    "pitch",
    "yaw",

    "roll_vel",
    "pitch_vel",
    "yaw_vel",

    "roll_acc",
    "pitch_acc",
    "yaw_acc"
]


# ============================================================
# DISTANCE
# ============================================================

def update_distance(speed_mps):

    global odometer_m
    global trip_m
    global last_distance_time

    now = time.perf_counter()

    with distance_lock:

        if last_distance_time is None:

            last_distance_time = now

            return

        dt = (
            now
            - last_distance_time
        )

        last_distance_time = now

        if dt <= 0 or dt > 1.0:

            return

        distance = (
            max(speed_mps, 0.0)
            * dt
        )

        odometer_m += distance

        trip_m += distance


# ============================================================
# BUILD ROW
# ============================================================

def build_row(
    motion,
    gauge,
    start_time,
    sequence
):

    row = {
        field: float("nan")
        for field in FIELDS
    }

    # ========================================================
    # TIME
    # ========================================================

    row["t_s"] = (
        time.perf_counter()
        - start_time
    )

    row["seq"] = sequence

    # ========================================================
    # MASS
    # ========================================================

    row["mass_kg"] = (
        VEHICLE_MASS_KG
    )

    # ========================================================
    # MOTION
    # ========================================================

    if motion is not None:

        motion_fields = [

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

            "roll",
            "pitch",
            "yaw",

            "roll_vel",
            "pitch_vel",
            "yaw_vel",

            "roll_acc",
            "pitch_acc",
            "yaw_acc"
        ]

        for key in motion_fields:

            if key in motion:

                row[key] = motion[key]

    # ========================================================
    # OUTGAUGE
    # ========================================================

    if gauge is not None:

        row["gear_index"] = (
            gauge["gear_index"]
        )

        row["rpm"] = (
            gauge["rpm"]
        )

        # MotionSim is primary speed source

        if math.isnan(
            row["speed_mps"]
        ):

            row["speed_mps"] = (
                gauge["speed_mps"]
            )

        row["coolant_c"] = (
            gauge["coolant_c"]
        )

        row["oil_c"] = (
            gauge["oil_c"]
        )

        row["oil_pressure"] = (
            gauge["oil_pressure"]
        )

        # Fuel is a normalized 0-1 value.
        # Do NOT label it liters.

        row["fuel_volume_l"] = (
            gauge["fuel"]
        )

        # Driver controls

        row["throttle"] = (
            gauge["throttle"]
        )

        row["brake"] = (
            gauge["brake"]
        )

        row["clutch_ratio"] = (
            gauge["clutch"]
        )

        row["parkingbrake"] = (
            gauge["parkingbrake"]
        )

    # ========================================================
    # ENGINE ANGULAR VELOCITY
    # ========================================================

    if not math.isnan(
        row["rpm"]
    ):

        row["engine_av_rads"] = (

            row["rpm"]
            * 2.0
            * math.pi
            / 60.0
        )

    # ========================================================
    # ENGINE RUNNING
    # ========================================================

    if not math.isnan(
        row["rpm"]
    ):

        row["engine_running"] = (

            1.0
            if row["rpm"] > 100.0
            else 0.0
        )

    # ========================================================
    # IGNITION LEVEL
    # ========================================================

    if not math.isnan(
        row["rpm"]
    ):

        row["ignition_level"] = (

            2.0
            if row["rpm"] > 100.0
            else 0.0
        )

    # ========================================================
    # DISTANCE
    # ========================================================

    with distance_lock:

        row["odometer_m"] = (
            odometer_m
        )

        row["trip_m"] = (
            trip_m
        )

    # ========================================================
    # BATTERY
    # ========================================================
    #
    # CURRENTLY:
    #
    # These values come from the battery state variables above.
    #
    # They remain NaN until a REAL battery telemetry source
    # is connected.
    #
    # ========================================================

    row["battery_voltage_v"] = (
        battery_voltage_v
    )

    row["battery_current_a"] = (
        battery_current_a
    )

    row["battery_temperature_c"] = (
        battery_temperature_c
    )

    row["battery_soc"] = (
        battery_soc
    )

    # ========================================================
    # BATTERY POWER
    # ========================================================

    if (
        not math.isnan(
            battery_voltage_v
        )
        and
        not math.isnan(
            battery_current_a
        )
    ):

        row["battery_power_w"] = (

            battery_voltage_v
            * battery_current_a
        )

    # ========================================================
    # BATTERY ENERGY
    # ========================================================
    #
    # Left NaN until actual battery current/voltage are available.
    #
    # We will integrate:
    #
    # E = integral(V * I * dt)
    #
    # in the battery phase.
    #
    # ========================================================

    row["battery_energy_wh"] = (
        battery_energy_wh
    )

    return row


# ============================================================
# CSV WRITER
# ============================================================

def csv_writer():

    print(
        f"[CSV] Recording at "
        f"{SAMPLE_RATE_HZ} Hz"
    )

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=FIELDS,
            extrasaction="ignore"
        )

        writer.writeheader()

        f.flush()

        sequence = 0

        start_time = (
            time.perf_counter()
        )

        next_sample = (
            time.monotonic()
        )

        while running:

            now = time.monotonic()

            if now >= next_sample:

                # =================================================
                # COPY CURRENT TELEMETRY
                # =================================================

                with data_lock:

                    motion = (

                        motion_latest.copy()

                        if motion_latest
                        is not None

                        else None
                    )

                    gauge = (

                        outgauge_latest.copy()

                        if outgauge_latest
                        is not None

                        else None
                    )

                # =================================================
                # WAIT FOR BOTH
                # =================================================

                if (
                    motion is None
                    or gauge is None
                ):

                    next_sample += (
                        SAMPLE_INTERVAL
                    )

                    time.sleep(0.002)

                    continue

                # =================================================
                # DATA AGE
                # =================================================

                current_time = (
                    time.perf_counter()
                )

                motion_age = (
                    current_time
                    - motion["timestamp"]
                )

                gauge_age = (
                    current_time
                    - gauge["timestamp"]
                )

                if (
                    motion_age
                    > MAX_DATA_AGE
                    or
                    gauge_age
                    > MAX_DATA_AGE
                ):

                    next_sample += (
                        SAMPLE_INTERVAL
                    )

                    time.sleep(0.002)

                    continue

                # =================================================
                # DISTANCE
                # =================================================

                update_distance(
                    motion["speed_mps"]
                )

                # =================================================
                # BUILD
                # =================================================

                row = build_row(
                    motion,
                    gauge,
                    start_time,
                    sequence
                )

                # =================================================
                # WRITE
                # =================================================

                writer.writerow(row)

                f.flush()

                sequence += 1

                # =================================================
                # NEXT SAMPLE
                # =================================================

                next_sample += (
                    SAMPLE_INTERVAL
                )

                # Prevent backlog

                if now > (
                    next_sample
                    + SAMPLE_INTERVAL * 10
                ):

                    next_sample = (
                        now
                        + SAMPLE_INTERVAL
                    )

            else:

                time.sleep(0.002)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print(
        "=============================="
    )

    print(
        " BeamNG Research Data Logger"
    )

    print(
        "=============================="
    )

    print()

    print(
        f"[CSV] Output: {OUTPUT_FILE}"
    )

    print(
        f"[CSV] Sampling: "
        f"{SAMPLE_RATE_HZ} Hz"
    )

    print()

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

        print()

        print(
            "Stopping data collection..."
        )

        running = False

        time.sleep(0.5)

    print()

    print(
        "Dataset saved:",
        OUTPUT_FILE
    )