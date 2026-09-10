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

running = True

# Latest packets
motion_latest = None
outgauge_latest = None

# IMPORTANT:
# Both UDP listener threads and the CSV writer use this lock.
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

    speed = calculate_speed(
        vx,
        vy,
        vz
    )

    if speed < 0.1:

        return (
            float("nan"),
            float("nan"),
            float("nan")
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

    # Timeout allows the thread to notice
    # when running becomes False.
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

        # Expected packet:
        #
        # 4 byte header
        # +
        # 21 floats
        #
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

            # ------------------------------------------------
            # Position
            # ------------------------------------------------

            "x_m":
                values[1],

            "y_m":
                values[2],

            "z_m":
                values[3],

            # ------------------------------------------------
            # Velocity
            # ------------------------------------------------

            "vx_mps":
                vx,

            "vy_mps":
                vy,

            "vz_mps":
                vz,

            "speed_mps":
                speed,

            # ------------------------------------------------
            # Acceleration
            # ------------------------------------------------

            "ax_mps2":
                values[7],

            "ay_mps2":
                values[8],

            "az_mps2":
                values[9],

            # ------------------------------------------------
            # Direction
            # ------------------------------------------------

            "dir_x":
                dir_x,

            "dir_y":
                dir_y,

            "dir_z":
                dir_z,

            # ------------------------------------------------
            # Orientation
            # ------------------------------------------------

            "roll":
                values[13],

            "pitch":
                values[14],

            "yaw":
                values[15],

            # ------------------------------------------------
            # Angular velocity
            # ------------------------------------------------

            "roll_vel":
                values[16],

            "pitch_vel":
                values[17],

            "yaw_vel":
                values[18],

            # ------------------------------------------------
            # Angular acceleration
            # ------------------------------------------------

            "roll_acc":
                values[19],

            "pitch_acc":
                values[20],

            "yaw_acc":
                values[21],
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

        # Expected OutGauge packet
        # is 96 bytes.

        if len(data) != 96:

            continue

        try:

            values = struct.unpack(
                "<I4sHbb7f2I3f32si",
                data
            )

        except struct.error:

            continue

        sample = {

            "timestamp":
                time.perf_counter(),

            # ------------------------------------------------
            # Driver / engine
            # ------------------------------------------------

            "gear_index":
                values[3],

            "speed_mps":
                values[5],

            "rpm":
                values[6],

            # ------------------------------------------------
            # Temperatures
            # ------------------------------------------------

            "coolant_c":
                values[8],

            "fuel":
                values[9],

            "oil_pressure":
                values[10],

            "oil_c":
                values[11],

            # ------------------------------------------------
            # Controls
            # ------------------------------------------------

            "throttle":
                values[16],

            "brake":
                values[17],

            "clutch":
                values[18],
        }

        with data_lock:

            outgauge_latest = sample


# ============================================================
# CSV FIELD NAMES
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
    # Vehicle / engine
    # --------------------------------------------------------

    "mass_kg",

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

    # --------------------------------------------------------
    # Wheels
    # --------------------------------------------------------

    "wheel_av_fl",
    "wheel_av_fr",
    "wheel_av_rl",
    "wheel_av_rr",

    # --------------------------------------------------------
    # Brakes
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
    # Temperatures
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
    # BATTERY
    #
    # These are deliberately blank because the current
    # UDP packets don't provide them.
    # --------------------------------------------------------

    "battery_voltage_v",

    "battery_current_a",

    "battery_temperature_c",

    "battery_soc"
]


# ============================================================
# CREATE CSV ROW
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

    # --------------------------------------------------------
    # Time
    # --------------------------------------------------------

    row["t_s"] = (
        time.perf_counter()
        - start_time
    )

    row["seq"] = sequence

    # --------------------------------------------------------
    # Motion data
    # --------------------------------------------------------

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
            "dir_z"
        ]:

            if key in motion:

                row[key] = motion[key]

    # --------------------------------------------------------
    # OutGauge data
    # --------------------------------------------------------

    if gauge is not None:

        for key in [

            "gear_index",
            "rpm",
            "speed_mps",
            "coolant_c",
            "fuel",
            "oil_pressure",
            "oil_c",
            "throttle",
            "brake",
            "clutch"
        ]:

            if key in gauge:

                if key == "fuel":

                    row[
                        "fuel_volume_l"
                    ] = gauge[key]

                else:

                    row[key] = gauge[key]

    # --------------------------------------------------------
    # Engine angular velocity
    #
    # rpm → rad/s
    # --------------------------------------------------------

    if not math.isnan(
        row["rpm"]
    ):

        row[
            "engine_av_rads"
        ] = (
            row["rpm"]
            * 2.0
            * math.pi
            / 60.0
        )

    # --------------------------------------------------------
    # Clutch
    # --------------------------------------------------------

    if not math.isnan(
        row["clutch"]
    ):

        row[
            "clutch_ratio"
        ] = row["clutch"]

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

                # --------------------------------------------
                # IMPORTANT:
                # Copy both telemetry packets while holding
                # the same lock used by listener threads.
                # --------------------------------------------

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

                # --------------------------------------------
                # Build combined row
                # --------------------------------------------

                row = build_row(
                    motion,
                    gauge,
                    start_time,
                    sequence
                )

                writer.writerow(
                    row
                )

                f.flush()

                sequence += 1

                # --------------------------------------------
                # Schedule next sample
                # --------------------------------------------

                next_sample += (
                    SAMPLE_INTERVAL
                )

                # Prevent runaway if the computer
                # was paused for a while.
                if now > (
                    next_sample
                    + SAMPLE_INTERVAL * 10
                ):

                    next_sample = (
                        now
                        + SAMPLE_INTERVAL
                    )

            else:

                time.sleep(
                    0.002
                )


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
        f"[CSV] Output: "
        f"{OUTPUT_FILE}"
    )

    print(
        f"[CSV] Sampling: "
        f"{SAMPLE_RATE_HZ} Hz"
    )

    # --------------------------------------------------------
    # Start listeners
    # --------------------------------------------------------

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

    print()
    print(
        "Dataset saved:",
        OUTPUT_FILE
    )