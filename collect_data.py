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

# Maximum age allowed for UDP telemetry
MAX_DATA_AGE = 0.5

running = True

motion_latest = None
outgauge_latest = None

# IMPORTANT:
# One lock shared by all threads
data_lock = threading.Lock()


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

    speed = calculate_speed(vx, vy, vz)

    if speed < 0.1:
        return 0.0, 0.0, 0.0

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
        f"[MotionSim] Listening on {MOTIONSIM_PORT}"
    )

    while running:

        try:
            data, _ = sock.recvfrom(4096)

        except socket.timeout:
            continue

        except Exception:
            continue

        # Expected MotionSim packet
        # 4 bytes header + 21 floats = 88 bytes

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

        dir_x, dir_y, dir_z = calculate_direction(
            vx,
            vy,
            vz
        )

        # ----------------------------------------------------
        # Create MotionSim sample
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
            "yaw_acc": values[21],
        }

        # ----------------------------------------------------
        # Update shared telemetry
        # ----------------------------------------------------

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
        f"[OutGauge] Listening on {OUTGAUGE_PORT}"
    )

    while running:

        try:
            data, _ = sock.recvfrom(4096)

        except socket.timeout:
            continue

        except Exception:
            continue

        # Your BeamNG setup sends 96-byte packets

        if len(data) != 96:
            continue

        # ----------------------------------------------------
        # IMPORTANT
        #
        # This is the packet format that was already working
        # with your BeamNG setup.
        # ----------------------------------------------------

        try:

            values = struct.unpack(
                "<I4sHbb7f2I3f32si",
                data
            )

        except struct.error as e:

            print(
                "[OutGauge] Packet decode error:",
                e
            )

            continue

        # ----------------------------------------------------
        # Extract values
        # ----------------------------------------------------

        sample = {

            "timestamp":
                time.perf_counter(),

            "gear_index":
                values[3],

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

            "throttle":
                values[16],

            "brake":
                values[17],

            "clutch":
                values[18],
        }

        # ----------------------------------------------------
        # Update shared telemetry
        # ----------------------------------------------------

        with data_lock:
            outgauge_latest = sample


# ============================================================
# CSV FIELDS
# ============================================================

FIELDS = [

    # --------------------------------------------------------
    # Time
    # --------------------------------------------------------

    "t_s",
    "seq",

    # --------------------------------------------------------
    # Position
    # --------------------------------------------------------

    "x_m",
    "y_m",
    "z_m",

    # --------------------------------------------------------
    # Velocity
    # --------------------------------------------------------

    "vx_mps",
    "vy_mps",
    "vz_mps",

    "speed_mps",

    # --------------------------------------------------------
    # Acceleration
    # --------------------------------------------------------

    "ax_mps2",
    "ay_mps2",
    "az_mps2",

    # --------------------------------------------------------
    # Direction
    # --------------------------------------------------------

    "dir_x",
    "dir_y",
    "dir_z",

    # --------------------------------------------------------
    # Vehicle
    # --------------------------------------------------------

    "mass_kg",

    # --------------------------------------------------------
    # Engine
    # --------------------------------------------------------

    "rpm",
    "engine_torque_nm",
    "engine_av_rads",
    "engine_load",
    "exhaust_flow",

    # --------------------------------------------------------
    # Transmission
    # --------------------------------------------------------

    "gear_index",
    "clutch_ratio",

    # --------------------------------------------------------
    # Driver inputs
    # --------------------------------------------------------

    "throttle",
    "brake",
    "steering",

    # --------------------------------------------------------
    # Wheels
    # --------------------------------------------------------

    "wheel_av_fl",
    "wheel_av_fr",
    "wheel_av_rl",
    "wheel_av_rr",

    # --------------------------------------------------------
    # Brake temperatures
    # --------------------------------------------------------

    "brake_temp_fl",
    "brake_temp_fr",
    "brake_temp_rl",
    "brake_temp_rr",

    # --------------------------------------------------------
    # Aerodynamics
    # --------------------------------------------------------

    "downforce_fl",

    # --------------------------------------------------------
    # Temperature
    # --------------------------------------------------------

    "coolant_c",
    "oil_c",

    # --------------------------------------------------------
    # Fuel / distance
    # --------------------------------------------------------

    "fuel_volume_l",
    "odometer_m",
    "trip_m",
    "altitude_m",

    # --------------------------------------------------------
    # Vehicle state
    # --------------------------------------------------------

    "ignition_level",
    "parkingbrake",
    "avg_wheel_av",
    "engine_running",
    "damage",

    # --------------------------------------------------------
    # Battery
    # --------------------------------------------------------

    "battery_voltage_v",
    "battery_current_a",
    "battery_temperature_c",
    "battery_soc",

    # --------------------------------------------------------
    # Additional
    # --------------------------------------------------------

    "oil_pressure",

    # --------------------------------------------------------
    # Orientation
    # --------------------------------------------------------

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


# ============================================================
# BUILD DATA ROW
# ============================================================

def build_row(
    motion,
    gauge,
    start_time,
    sequence
):

    # Start every field as NaN.
    # We NEVER invent unavailable measurements.

    row = {
        field: float("nan")
        for field in FIELDS
    }

    # --------------------------------------------------------
    # Time
    # --------------------------------------------------------

    row["t_s"] = (
        time.perf_counter()
        - start_time
    )

    row["seq"] = sequence

    # --------------------------------------------------------
    # MotionSim
    # --------------------------------------------------------

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
            "yaw_acc",
        ]

        for key in motion_fields:

            if key in motion:

                row[key] = motion[key]

    # --------------------------------------------------------
    # OutGauge
    # --------------------------------------------------------

    if gauge is not None:

        if "gear_index" in gauge:

            row["gear_index"] = (
                gauge["gear_index"]
            )

        if "rpm" in gauge:

            row["rpm"] = (
                gauge["rpm"]
            )

        # ----------------------------------------------------
        # Speed
        # ----------------------------------------------------

        if "speed_mps" in gauge:

            # MotionSim is preferred.

            if math.isnan(
                row["speed_mps"]
            ):

                row["speed_mps"] = (
                    gauge["speed_mps"]
                )

        # ----------------------------------------------------
        # Temperatures
        # ----------------------------------------------------

        if "coolant_c" in gauge:

            row["coolant_c"] = (
                gauge["coolant_c"]
            )

        if "oil_c" in gauge:

            row["oil_c"] = (
                gauge["oil_c"]
            )

        # ----------------------------------------------------
        # Oil pressure
        # ----------------------------------------------------

        if "oil_pressure" in gauge:

            row["oil_pressure"] = (
                gauge["oil_pressure"]
            )

        # ----------------------------------------------------
        # Fuel
        # ----------------------------------------------------

        if "fuel" in gauge:

            row["fuel_volume_l"] = (
                gauge["fuel"]
            )

        # ----------------------------------------------------
        # Driver controls
        # ----------------------------------------------------

        if "throttle" in gauge:

            row["throttle"] = (
                gauge["throttle"]
            )

        if "brake" in gauge:

            row["brake"] = (
                gauge["brake"]
            )

        if "clutch" in gauge:

            row["clutch_ratio"] = (
                gauge["clutch"]
            )

    # ========================================================
    # DERIVED ENGINE VALUES
    # ========================================================

    # RPM → rad/s

    if not math.isnan(
        row["rpm"]
    ):

        row["engine_av_rads"] = (

            row["rpm"]
            * 2.0
            * math.pi
            / 60.0
        )

        # Engine running state

        row["engine_running"] = (

            1
            if row["rpm"] > 100
            else 0
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

            # =================================================
            # TIME TO TAKE SAMPLE
            # =================================================

            if now >= next_sample:

                # -------------------------------------------------
                # Safely copy latest telemetry
                # -------------------------------------------------

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

                # -------------------------------------------------
                # Do not record until BOTH sources exist
                # -------------------------------------------------

                if motion is None or gauge is None:

                    next_sample += (
                        SAMPLE_INTERVAL
                    )

                    time.sleep(0.002)

                    continue

                # -------------------------------------------------
                # Check freshness
                # -------------------------------------------------

                current_perf = (
                    time.perf_counter()
                )

                motion_age = (
                    current_perf
                    - motion["timestamp"]
                )

                gauge_age = (
                    current_perf
                    - gauge["timestamp"]
                )

                # -------------------------------------------------
                # Do not record stale packets
                # -------------------------------------------------

                if (
                    motion_age > MAX_DATA_AGE
                    or
                    gauge_age > MAX_DATA_AGE
                ):

                    next_sample += (
                        SAMPLE_INTERVAL
                    )

                    time.sleep(0.002)

                    continue

                # -------------------------------------------------
                # Build row
                # -------------------------------------------------

                row = build_row(

                    motion,
                    gauge,

                    start_time,
                    sequence
                )

                # -------------------------------------------------
                # Write row
                # -------------------------------------------------

                writer.writerow(row)

                f.flush()

                sequence += 1

                # -------------------------------------------------
                # Next sample
                # -------------------------------------------------

                next_sample += (
                    SAMPLE_INTERVAL
                )

                # -------------------------------------------------
                # Prevent burst after lag
                # -------------------------------------------------

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
    # MotionSim thread
    # --------------------------------------------------------

    t1 = threading.Thread(
        target=motion_listener,
        daemon=True
    )

    # --------------------------------------------------------
    # OutGauge thread
    # --------------------------------------------------------

    t2 = threading.Thread(
        target=outgauge_listener,
        daemon=True
    )

    t1.start()
    t2.start()

    # --------------------------------------------------------
    # Start CSV collection
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