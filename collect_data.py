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
#
# IMPORTANT:
# Set this to the actual mass of the vehicle you are using.
#
# This is NOT measured from OutGauge.
#
# Example:
# VEHICLE_MASS_KG = 1500.0
#
# If you don't know the exact mass yet, leave it as NaN.
#
# ============================================================

VEHICLE_MASS_KG = 2135.059


# ============================================================
# GLOBAL STATE
# ============================================================

running = True

motion_latest = None
outgauge_latest = None

data_lock = threading.Lock()

# Distance integration
distance_lock = threading.Lock()

odometer_m = 0.0
trip_m = 0.0

last_distance_time = None


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
# MOTIONSIM LISTENER
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

            data, _ = sock.recvfrom(
                4096
            )

        except socket.timeout:

            continue

        except Exception:

            continue

        # MotionSim packet:
        # 4 byte header + 21 floats
        # = 88 bytes

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

        # ----------------------------------------------------
        # Velocity
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Motion sample
        # ----------------------------------------------------

        sample = {

            "timestamp":
                time.perf_counter(),

            # Position
            "x_m": values[1],
            "y_m": values[2],
            "z_m": values[3],

            # Velocity
            "vx_mps": vx,
            "vy_mps": vy,
            "vz_mps": vz,

            # Speed
            "speed_mps": speed,

            # Acceleration
            "ax_mps2": values[7],
            "ay_mps2": values[8],
            "az_mps2": values[9],

            # Direction
            "dir_x": dir_x,
            "dir_y": dir_y,
            "dir_z": dir_z,

            # Orientation
            "roll": values[13],
            "pitch": values[14],
            "yaw": values[15],

            # Angular velocity
            "roll_vel": values[16],
            "pitch_vel": values[17],
            "yaw_vel": values[18],

            # Angular acceleration
            "roll_acc": values[19],
            "pitch_acc": values[20],
            "yaw_acc": values[21]
        }

        with data_lock:

            motion_latest = sample


# ============================================================
# OUTGAUGE LISTENER
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

            data, _ = sock.recvfrom(
                4096
            )

        except socket.timeout:

            continue

        except Exception:

            continue

        # BeamNG OutGauge packet
        # = 96 bytes

        if len(data) != 96:

            continue

        # ====================================================
        # CORRECT BEAMNG OUTGAUGE STRUCTURE
        # ====================================================
        #
        # uint32 time
        # char[4] car
        # uint16 flags
        # char gear
        # char playerID
        # float speed
        # float rpm
        # float turbo
        # float engine temperature
        # float fuel
        # float oil pressure
        # float oil temperature
        # uint32 dash lights
        # uint32 show lights
        # float throttle
        # float brake
        # float clutch
        # char display[32]
        # int id
        #
        # ====================================================

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

        # ----------------------------------------------------
        # IMPORTANT FIELD MAPPING
        # ----------------------------------------------------

        # values[3] = gear
        #
        # BeamNG:
        # Reverse = 0
        # Neutral = 1
        # First = 2
        # Second = 3
        # etc.
        #
        # Convert to more intuitive gear index:
        #
        # Reverse -> -1
        # Neutral -> 0
        # First   -> 1
        # Second  -> 2
        # etc.

        raw_gear = values[3]

        if raw_gear == 0:

            gear_index = -1

        else:

            gear_index = raw_gear - 1

        # ----------------------------------------------------
        # Dashboard flags
        # ----------------------------------------------------

        show_lights = values[13]

        # BeamNG OutGauge:
        #
        # DL_HANDBRAKE = 2^2 = 4

        parkingbrake = (
            1.0
            if (show_lights & 4)
            else 0.0
        )

        # ----------------------------------------------------
        # CORRECT FIELD INDICES
        # ----------------------------------------------------

        sample = {

            "timestamp":
                time.perf_counter(),

            "gear_index":
                gear_index,

            # Speed
            "speed_mps":
                values[5],

            # Engine RPM
            "rpm":
                values[6],

            # Engine coolant
            "coolant_c":
                values[8],

            # Fuel ratio
            "fuel":
                values[9],

            # Oil pressure
            "oil_pressure":
                values[10],

            # Oil temperature
            "oil_c":
                values[11],

            # CORRECT!
            "throttle":
                values[14],

            # CORRECT!
            "brake":
                values[15],

            # CORRECT!
            "clutch":
                values[16],

            # Parking brake from dashboard flag
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

    # Brake temperatures
    "brake_temp_fl",
    "brake_temp_fr",
    "brake_temp_rl",
    "brake_temp_rr",

    # Aerodynamics
    "downforce_fl",

    # Temperatures
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

    # Battery
    "battery_voltage_v",
    "battery_current_a",
    "battery_temperature_c",
    "battery_soc",

    # Additional
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
# DISTANCE INTEGRATION
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

        # Ignore abnormal time gaps
        if dt <= 0 or dt > 1.0:

            return

        # Distance = speed × time

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
    # VEHICLE MASS
    # ========================================================

    row["mass_kg"] = (
        VEHICLE_MASS_KG
    )

    # ========================================================
    # MOTION DATA
    # ========================================================

    if motion is not None:

        for key in [

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
        ]:

            if key in motion:

                row[key] = motion[key]

    # ========================================================
    # OUTGAUGE
    # ========================================================

    if gauge is not None:

        # ----------------------------------------------------
        # Gear
        # ----------------------------------------------------

        row["gear_index"] = (
            gauge["gear_index"]
        )

        # ----------------------------------------------------
        # RPM
        # ----------------------------------------------------

        row["rpm"] = (
            gauge["rpm"]
        )

        # ----------------------------------------------------
        # Speed
        # ----------------------------------------------------

        if math.isnan(
            row["speed_mps"]
        ):

            row["speed_mps"] = (
                gauge["speed_mps"]
            )

        # ----------------------------------------------------
        # Coolant
        # ----------------------------------------------------

        row["coolant_c"] = (
            gauge["coolant_c"]
        )

        # ----------------------------------------------------
        # Oil
        # ----------------------------------------------------

        row["oil_c"] = (
            gauge["oil_c"]
        )

        row["oil_pressure"] = (
            gauge["oil_pressure"]
        )

        # ----------------------------------------------------
        # Fuel
        # ----------------------------------------------------

        # OutGauge fuel is 0..1 ratio.
        #
        # We don't know actual tank capacity here,
        # so keep the ratio rather than pretending it is liters.

        row["fuel_volume_l"] = (
            gauge["fuel"]
        )

        # ----------------------------------------------------
        # DRIVER INPUTS
        # ----------------------------------------------------

        row["throttle"] = (
            gauge["throttle"]
        )

        row["brake"] = (
            gauge["brake"]
        )

        row["clutch_ratio"] = (
            gauge["clutch"]
        )

        # ----------------------------------------------------
        # PARKING BRAKE
        # ----------------------------------------------------

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
    #
    # This is a DERIVED approximation.
    #
    # It is NOT the actual BeamNG ignitionLevel.
    #
    # 0 = off
    # 2 = ignition/engine running
    #
    # We don't have accessory/starter state through OutGauge.
    #
    # ========================================================

    if not math.isnan(
        row["rpm"]
    ):

        if row["rpm"] > 100.0:

            row["ignition_level"] = 2.0

        else:

            row["ignition_level"] = 0.0

    # ========================================================
    # ODOMETER / TRIP
    # ========================================================
    #
    # These are distance-integrated values from MotionSim speed.
    #
    # They are NOT the vehicle's internal BeamNG odometer.
    #
    # ========================================================

    with distance_lock:

        row["odometer_m"] = (
            odometer_m
        )

        row["trip_m"] = (
            trip_m
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
                # COPY TELEMETRY
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
                # WAIT FOR BOTH SOURCES
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
                # CHECK DATA AGE
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
                # UPDATE DISTANCE
                # =================================================

                update_distance(
                    motion["speed_mps"]
                )

                # =================================================
                # BUILD ROW
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

                # Prevent burst after lag

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

    # --------------------------------------------------------
    # Start MotionSim
    # --------------------------------------------------------

    t1 = threading.Thread(
        target=motion_listener,
        daemon=True
    )

    # --------------------------------------------------------
    # Start OutGauge
    # --------------------------------------------------------

    t2 = threading.Thread(
        target=outgauge_listener,
        daemon=True
    )

    t1.start()
    t2.start()

    # --------------------------------------------------------
    # Start collector
    # --------------------------------------------------------

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