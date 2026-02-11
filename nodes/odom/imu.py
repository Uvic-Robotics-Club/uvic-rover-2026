#!/usr/bin/env python3
"""
ROS node: /imu_talker
Publishes : sensor_msgs/Imu on /imu/data
"""

import math
import numpy as np
import serial
import serial.tools.list_ports
from typing import Tuple
from tf.transformations import euler_from_quaternion

import rospy
from sensor_msgs.msg import Imu

# ───────── constants ─────────
ARDUINO_VID   = 0x2341
ARDUINO_PID   = 0x0043
SERIAL_BAUD   = 115_200
EXPECTED_FIELDS = 13
DEFAULT_RATE_HZ = 50

# ───────── helper functions ─────────
def _set_diag(matrix, var_xyz):
    """Fill a 3×3 covariance array (row-major) with variances on the diagonal."""
    matrix[:] = [var_xyz[0], 0.0,          0.0,
                 0.0,        var_xyz[1],   0.0,
                 0.0,        0.0,          var_xyz[2]]

# ───────── lightweight data struct ─────────
class ImuData:
    """
    Fixed-layout container for one IMU sample.
    Using __slots__ saves ~50 B per instance versus __dict__.
    """
    __slots__ = ("accel", "mag", "gyro", "quat")

    def __init__(
        self,
        accel: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        mag:   Tuple[float, float, float] = (0.0, 0.0, 0.0),
        gyro:  Tuple[float, float, float] = (0.0, 0.0, 0.0),
        quat:  Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
    ):
        self.accel = accel
        self.mag   = mag
        self.gyro  = gyro
        self.quat  = quat

# ───────── node class ─────────
class ImuNode:
    def __init__(self, rate_hz: int = DEFAULT_RATE_HZ) -> None:
        self._serial = self._open_port()
        self._pub    = rospy.Publisher("/imu/data", Imu, queue_size=10)
        self._rate   = rospy.Rate(rate_hz)
        self._data   = ImuData()
        rospy.on_shutdown(self._shutdown)
        rospy.loginfo("IMU node initialised")

    # ----- main loop -----
    def spin(self) -> None:
        while not rospy.is_shutdown():
            try:
                raw = self._read_raw_sample()
                if raw:
                    self._update_data(raw)
                    self._pub.publish(self._build_msg())
                #self._rate.sleep()
            except serial.SerialException as err:
                rospy.logerr_throttle(1.0, f"Serial error: {err}")

    # ----- serial helpers -----
    def _open_port(self):
        forced = rospy.get_param("~port", "").strip()
        baud = int(rospy.get_param("~baud", SERIAL_BAUD))
        timeout = float(rospy.get_param("~timeout", 0.1))

        # 1) Explicit override (best / most deterministic)
        if forced:
            rospy.loginfo(f"Opening IMU on forced port: {forced} @ {baud}")
            return serial.Serial(forced, baud, timeout=timeout)

        ports = list(serial.tools.list_ports.comports())
        if not ports:
            rospy.logfatal(
                "No serial ports found in this environment.\n"
                "If you're on Windows + Docker Desktop, ensure the USB device is attached into WSL/docker."
            )
            rospy.signal_shutdown("No serial ports found")
            raise rospy.ROSInterruptException

        # 2) Filter by known VID/PID allowlist
        matches = [p for p in ports if (p.vid, p.pid) in ALLOWED_VIDPID]

        # Deterministic ordering
        matches.sort(key=lambda p: p.device)
        ports_sorted = sorted(ports, key=lambda p: p.device)

        if len(matches) == 1:
            p = matches[0]
            rospy.loginfo(f"IMU detected on {p.device} (VID:PID={p.vid:04x}:{p.pid:04x})")
            return serial.Serial(p.device, baud, timeout=timeout)

        # 3) If only one port exists total, use it (common on dev machines)
        if len(ports_sorted) == 1:
            p = ports_sorted[0]
            rospy.logwarn(f"No VID/PID match; using only available port: {p.device} ({p.description})")
            return serial.Serial(p.device, baud, timeout=timeout)

        # 4) Otherwise: ambiguous — force user to specify port
        port_list = "\n".join(
            [f"  - {p.device} | {p.description} | VID:PID={p.vid}:{p.pid}" for p in ports_sorted]
        )
        match_list = "\n".join(
            [f"  - {p.device} | VID:PID={p.vid:04x}:{p.pid:04x}" for p in matches]
        ) or "  (none)"

        rospy.logfatal(
            "IMU port is ambiguous.\n"
            f"Ports seen:\n{port_list}\n"
            f"VID/PID allowlist matches:\n{match_list}\n"
            "Fix: pass the port explicitly, e.g.:\n"
            "  rosrun uvic_rover imu.py _port:=/dev/ttyACM0"
        )
        rospy.signal_shutdown("Ambiguous serial ports")
        raise rospy.ROSInterruptException

    def _read_raw_sample(self):
        line = self._serial.readline().decode(errors="ignore").strip()
        if not line:
            return None
        parts = line.split()
        if len(parts) != EXPECTED_FIELDS:
            rospy.logwarn_throttle(5.0,
                                   f"Unexpected field count: {len(parts)} != {EXPECTED_FIELDS}")
            return None
        try:
            return tuple(map(float, parts))
        except ValueError:
            rospy.logwarn_throttle(5.0, "Non-numeric data encountered")
            return None

    # ----- conversion -----
    def _update_data(self, raw):
        ax, ay, az, mx, my, mz, gx, gy, gz, qw, qx, qy, qz = raw
        self._data = ImuData(
            accel=(ax, ay, az),
            mag=(mx, my, mz),
            gyro=(gx, gy, gz),
            quat=(qw, qx, qy, qz),
        )

    def _build_msg(self) -> Imu:
        msg = Imu()
        msg.header.stamp = rospy.Time.now()
        msg.header.frame_id = "imu_link"
        # orientation
        msg.orientation.w, msg.orientation.x, msg.orientation.y, msg.orientation.z = self._data.quat
        # linear accel
        msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z = self._data.accel
        # angular vel
        msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z = self._data.gyro

        #TEMP
        yaw = euler_from_quaternion([msg.orientation.x,
            msg.orientation.y,
            msg.orientation.z,
            msg.orientation.w])[2]
        print(f"yaw (deg): {math.degrees(yaw):.1f}")

                # ====== covariance values (variance, not std-dev) ======
        gyro_var   = [1.5e-6] * 3                      # rad²/s²
        accel_var  = [8e-4]  * 3                      # (m/s²)²
        ori_var    = [math.radians(2)**2,              # roll
                    math.radians(2)**2,              # pitch
                    math.radians(5)**2]              # yaw

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
    ImuNode().spin()

if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass