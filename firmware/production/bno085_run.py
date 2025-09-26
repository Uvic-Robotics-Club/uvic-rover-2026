"""
BNO085 → ROS bridge (quiet mode):
---------------------------------
This script runs on a Raspberry Pi Pico board (WH or non-W) with CircuitPython,
reads orientation + sensor data from a BNO085 IMU over I2C, and streams it over
USB serial in a format ready for imu.py to publish as a ROS sensor_msgs/Imu.

Output order (space-separated floats, one line per update):
    ax ay az   mx my mz   gx gy gz   qw qx qy qz

Where:
    a = linear acceleration (m/s^2)
    m = magnetic field (uT)
    g = angular velocity (rad/s)
    q = quaternion orientation (w,x,y,z)

Notes on try/except usage in this script:
- We use try/except when selecting the onboard LED pin because the Pico WH
  and the original Pico have different LED wiring and CircuitPython exposes
  them differently (board.LED vs board.GP25).
- We also use try/except when creating the I2C object so the same code works
  across multiple Pico versions and pin mappings without modification.
"""


import time, board, digitalio, busio
from adafruit_bno08x.i2c import BNO08X_I2C
from adafruit_bno08x import (
    BNO_REPORT_ACCELEROMETER,
    BNO_REPORT_GYROSCOPE,
    BNO_REPORT_MAGNETOMETER,
    BNO_REPORT_ROTATION_VECTOR,        # absolute orientation (uses mag)
)

# ----- LED: blink 3x, then stay off -----
_led = None
try:                        
    _pin = board.LED
except AttributeError:
    try:        
        _pin = board.GP25
    except AttributeError:
        _pin = None
if _pin:
    _led = digitalio.DigitalInOut(_pin)
    _led.switch_to_output(False)
    for _ in range(3):
        _led.value = True;  time.sleep(0.1)
        _led.value = False; time.sleep(0.1)

# ----- I2C bring-up (Pico defaults first; fallbacks included) -----
def make_i2c():
    try:
        return board.I2C()
    except AttributeError:
        pass
    try:
        return busio.I2C(board.SCL, board.SDA, frequency=400000)
    except Exception:
        pass
    return busio.I2C(board.GP1, board.GP0, frequency=400000)

i2c = make_i2c()

# ----- Connect BNO08X (try 0x4A then 0x4B) -----
bno = None
for addr in (0x4A, 0x4B):
    try:
        bno = BNO08X_I2C(i2c, address=addr)
        break
    except Exception:
        bno = None
if bno is None:
    # Stay silent; if wiring/addr is wrong this just won't stream
    while True:
        time.sleep(1)

# Enable needed reports (no prints)
bno.enable_feature(BNO_REPORT_ACCELEROMETER)
bno.enable_feature(BNO_REPORT_GYROSCOPE)
bno.enable_feature(BNO_REPORT_MAGNETOMETER)
bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)

# ----- Stream ONLY data lines (13 floats, space-separated) -----
# Units: accel m/s^2, gyro rad/s, mag uT, quat (w,x,y,z)
while True:
    # Read sensors
    ax, ay, az = bno.acceleration
    gx, gy, gz = bno.gyro
    mx, my, mz = bno.magnetic
    qx, qy, qz, qw = bno.quaternion   # (x,y,z,w) from library

    # Print EXACTLY what imu.py expects
    # ax ay az  mx my mz  gx gy gz  qw qx qy qz
    print(
        "{:.6f} {:.6f} {:.6f} {:.6f} {:.6f} {:.6f} "
        "{:.6f} {:.6f} {:.6f} {:.6f} {:.6f} {:.6f} {:.6f}".format(
            ax, ay, az, mx, my, mz, gx, gy, gz, qw, qx, qy, qz
        )
    )

    # Light delay to avoid overwhelming the USB serial reader
    time.sleep(0.01)