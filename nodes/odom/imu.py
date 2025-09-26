#!/usr/bin/env python3
"""
ROS node: /imu_talker
Publishes: sensor_msgs/Imu on /imu/data

Reads lines from a Raspberry Pi Pico WH (CircuitPython) streaming:
ax ay az  mx my mz  gx gy gz  qw qx qy qz
"""

import math
import serial
import serial.tools.list_ports
from typing import Tuple, Optional

import rospy
from sensor_msgs.msg import Imu

# ───────── constants / defaults ─────────
# Pico WH with CircuitPython usually reports Adafruit VID (0x239A) or Raspberry Pi VID (0x2E8A).
ADAfruit_VID = 0x239A
RASPI_VID    = 0x2E8A

SERIAL_BAUD        = 115_200         # USB CDC ignores baud but we keep it configurable
EXPECTED_FIELDS    = 13
DEFAULT_RATE_HZ    = 100             # publish loop cap; reading is event-driven

# ───────── helpers ─────────
def _set_diag(matrix, var_xyz):
    """Fill a 3×3 covariance array (row-major) with variances on the diagonal."""
    matrix[:] = [
        var_xyz[0], 0.0,        0.0,
        0.0,        var_xyz[1], 0.0,
        0.0,        0.0,        var_xyz[2],
    ]

def _pick_pico_port() -> Optional[str]:
    """
    Choose the serial port most likely to be the Pico running CircuitPython.
    Heuristics:
      - VID in {Adafruit(0x239A), Raspberry Pi(0x2E8A)}
      - and any of 'Pico', 'CircuitPython', 'Adafruit' in product/description/manufacturer
    Returns device path (e.g. /dev/ttyACM0) or None.
    """
    candidates = []
    keys = ("product", "manufacturer", "description")
    needles = ("pico", "circuitpython", "adafruit")
    for p in serial.tools.list_ports.comports():
        vid = (p.vid or 0)
        text = " ".join(
            str(getattr(p, k) or "").lower() for k in keys
        )
        if vid in (ADAfruit_VID, RASPI_VID) and any(n in text for n in needles):
            candidates.append(p.device)
    # Prefer stable order (ttyACM before ttyUSB if both show up)
    candidates.sort()
    return candidates[0] if candidates else None

# ───────── lightweight sample struct ─────────
class ImuData:
    __slots__ = ("accel", "mag", "gyro", "quat")
    def __init__(
        self,
        accel=(0.0, 0.0, 0.0),
        mag=(0.0, 0.0, 0.0),
        gyro=(0.0, 0.0, 0.0),
        quat=(0.0, 0.0, 0.0, 0.0),
    ):
        self.accel = accel
        self.mag   = mag
        self.gyro  = gyro
        self.quat  = quat

# ───────── node ─────────
class ImuNode:
    def __init__(self, rate_hz: int = DEFAULT_RATE_HZ) -> None:
        # Allow manual override
        desired_port = rospy.get_param("~port", "").strip()
        if not desired_port:
            desired_port = _pick_pico_port()
        if not desired_port:
            rospy.logfatal("No Raspberry Pi Pico (CircuitPython) serial device found. "
                           "You can set ~port to override.")
            rospy.signal_shutdown("IMU device not found")
            raise rospy.ROSInterruptException

        baud = int(rospy.get_param("~baud", SERIAL_BAUD))
        timeout = float(rospy.get_param("~timeout", 0.1))
        self._serial = serial.Serial(desired_port, baud, timeout=timeout)
        rospy.loginfo(f"IMU serial open on {desired_port}")

        self._pub  = rospy.Publisher("/sensors/imu/data", Imu, queue_size=10)
        self._rate = rospy.Rate(rate_hz)
        self._data = ImuData()

        self._frame_id = rospy.get_param("~frame_id", "imu_link")

        rospy.on_shutdown(self._shutdown)

    def spin(self) -> None:
        while not rospy.is_shutdown():
            try:
                raw = self._read_raw_sample()
                if raw:
                    self._update_data(raw)
                    self._pub.publish(self._build_msg())
                # self._rate.sleep()  # optional throttle; leave commented for lowest latency
            except serial.SerialException as err:
                rospy.logerr_throttle(1.0, f"Serial error: {err}")

    # ----- serial ingest -----
    def _read_raw_sample(self):
        line = self._serial.readline().decode(errors="ignore").strip()
        if not line:
            return None
        parts = line.split()
        if len(parts) != EXPECTED_FIELDS:
            # Silently ignore junk or debug lines; keep logs sparse
            rospy.logwarn_throttle(5.0, f"Bad field count: {len(parts)} != {EXPECTED_FIELDS}")
            return None
        try:
            return tuple(map(float, parts))
        except ValueError:
            rospy.logwarn_throttle(5.0, "Non-numeric data encountered")
            return None

    # ----- unpack -----
    def _update_data(self, raw):
        # Order from Pico (BNO085): ax ay az mx my mz gx gy gz qw qx qy qz
        ax, ay, az, mx, my, mz, gx, gy, gz, qw, qx, qy, qz = raw
        self._data = ImuData(
            accel=(ax, ay, az),
            mag=(mx, my, mz),
            gyro=(gx, gy, gz),
            quat=(qw, qx, qy, qz),
        )

    # ----- ROS message -----
    def _build_msg(self) -> Imu:
        msg = Imu()
        msg.header.stamp = rospy.Time.now()
        msg.header.frame_id = self._frame_id

        # Orientation (unit quaternion w,x,y,z)
        msg.orientation.w, msg.orientation.x, msg.orientation.y, msg.orientation.z = self._data.quat

        # Angular velocity (rad/s)
        msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z = self._data.gyro

        # Linear acceleration (m/s^2)
        msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z = self._data.accel

        # Covariances (variance, not std-dev)
        gyro_var  = [1.5e-6] * 3                     # rad²/s²  (tune to taste)
        accel_var = [8e-4]  * 3                      # (m/s²)²
        ori_var   = [math.radians(2)**2,             # roll
                     math.radians(2)**2,             # pitch
                     math.radians(5)**2]             # yaw (often worse due to mag)

        _set_diag(msg.angular_velocity_covariance,    gyro_var)
        _set_diag(msg.linear_acceleration_covariance, accel_var)
        _set_diag(msg.orientation_covariance,         ori_var)

        return msg

    # ----- shutdown -----
    def _shutdown(self):
        rospy.loginfo("Closing IMU serial port")
        try:
            self._serial.close()
        except Exception:
            pass

# ───────── entry point ─────────
def main():
    rospy.init_node("imu_talker")
    ImuNode(rate_hz=int(rospy.get_param("~rate_hz", DEFAULT_RATE_HZ))).spin()

if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
