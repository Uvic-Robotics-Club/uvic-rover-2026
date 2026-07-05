#!/usr/bin/env python3
"""
Arm Control Node
================
Subscribes to joint commands from the Jetson and relays them to the
robotic arm motors over CAN bus.

The Jetson handles all inverse kinematics and motion planning. This node
is purely a relay — it maps joint commands to motor CAN IDs and sends
the corresponding CANopen messages.

Topic:
    /arm/joint_commands (sensor_msgs/JointState)
        - name:     list of joint names (must match JOINT_TO_MOTOR_ID keys)
        - position: desired position for each joint (degrees)
        - velocity: unused
        - effort:   unused

CAN Interface:
    can0 — configured on the host and passed through to the container.
"""

import struct
import socket
import rospy
from sensor_msgs.msg import JointState


# ---------------------------------------------------------------------------
# Motor configuration
# ---------------------------------------------------------------------------

# Maps joint names (as sent by the Jetson) to their CAN IDs.
# Update CAN IDs to match the actual motor configuration once confirmed.
JOINT_TO_MOTOR_ID = {
    "base_rotation": 0x601,
    "shoulder":      0x602,
    "elbow":         None,
    "wrist_pitch":   0x604,
    "wrist_rotation":0x605,
    "end_effector":  0x606,
}

PULSES_PER_REV = 2654208

# Home position offsets
HOME_OFFSETS = {
    0x601:  65.0,
    0x602:   0.0,
    0x604: 212.0,   # -(-180 + 32) = 212
    0x605:  87.0,
    0x606: -17.0,
}

# Gear ratio scalars — matches Arduino processMotorCommand().
GEAR_SCALARS = {
    0x601: 1.2458,
    0x602: 1.0,
    0x604: 0.63,
    0x605: 0.63,
    0x606: 0.63,
}


# CAN interface name — must match what's configured on the host.
CAN_INTERFACE = "can0"


# ---------------------------------------------------------------------------
# CAN helpers
# ---------------------------------------------------------------------------
 
def open_can_socket(interface: str) -> socket.socket:
    """Open a raw CAN socket on the given interface."""
    sock = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
    sock.bind((interface,))
    return sock
 
 
def send_can_frame(sock: socket.socket, can_id: int, data: bytes) -> None:
    """
    Send a single CAN frame.
 
    Frame format (16 bytes):
        - 4 bytes: CAN ID (little-endian, with flags)
        - 1 byte:  DLC (data length)
        - 3 bytes: padding
        - 8 bytes: data payload (padded to 8 bytes)
    """
    can_id_with_flags = can_id & socket.CAN_EFF_MASK
    dlc = len(data)
    padded_data = data.ljust(8, b'\x00')
    frame = struct.pack("=IB3x8s", can_id_with_flags, dlc, padded_data)
    sock.send(frame)
 
 
def degrees_to_pulses(can_id: int, angle_deg: float) -> int:
    """
    Convert a target angle in degrees to motor pulses.
    Applies home position offsets and gear ratio scalars
    matching the Arduino processMotorCommand() logic.
 
    Args:
        can_id:    CANopen node ID of the motor.
        angle_deg: Target angle in degrees.
 
    Returns:
        Target position in pulses as a signed 32-bit integer.
    """
    # Apply direction inversion and home offset.
    if can_id == 0x601:
        angle_deg -= HOME_OFFSETS[can_id]
    elif can_id in (0x604, 0x605, 0x606):
        angle_deg = -angle_deg - HOME_OFFSETS[can_id]
 
    # Convert to pulses.
    pulses = (angle_deg / 360.0) * PULSES_PER_REV
 
    # Apply gear scalar.
    pulses *= GEAR_SCALARS.get(can_id, 1.0)
 
    return int(pulses)
 
 
def send_motor_position(sock: socket.socket, can_id: int, angle_deg: float) -> None:
    """
    Send a CANopen position command to a motor.
 
    Matches the Arduino processMotorCommand() logic:
        1. Set target position (SDO write to object 0x607A)
        2. Execute position command (controlword 0x3F = new setpoint)
 
    Args:
        sock:      Open CAN socket.
        can_id:    CANopen node ID of the motor.
        angle_deg: Target angle in degrees.
    """
    target_pulses = degrees_to_pulses(can_id, angle_deg)
 
    # Step 1: Set target position (CANopen SDO, object 0x607A subindex 0x00).
    # 0x23 = SDO download request, 4 bytes of data.
    position_bytes = struct.pack("<i", target_pulses)  # signed 32-bit little-endian
    set_position_cmd = bytes([0x23, 0x7A, 0x60, 0x00]) + position_bytes
    send_can_frame(sock, can_id, set_position_cmd)
 
    # Step 2: Execute position command (CANopen controlword 0x6040, value 0x3F).
    # 0x2B = SDO download request, 2 bytes of data.
    # 0x3F = enable operation + new setpoint + change set immediately.
    execute_cmd = bytes([0x2B, 0x40, 0x60, 0x00, 0x3F, 0x00, 0x00, 0x00])
    send_can_frame(sock, can_id, execute_cmd)
 
 
def setup_motor(sock: socket.socket, can_id: int) -> None:
    """
    Initialize a motor with position mode, speed, and acceleration.
    Matches the Arduino speedSetup() logic.
 
    Args:
        sock:   Open CAN socket.
        can_id: CANopen node ID of the motor.
    """
    # Enable operation and allow emergency stop.
    send_can_frame(sock, can_id, bytes([0x2B, 0x40, 0x60, 0x00, 0x0F, 0x00, 0x00, 0x00]))
 
    # Set working mode to position mode (0x01).
    send_can_frame(sock, can_id, bytes([0x2F, 0x60, 0x60, 0x00, 0x01, 0x00, 0x00, 0x00]))
 
    # Set speed and acceleration based on motor ID — matches Arduino speedSetup().
    if can_id == 0x601:
        speed = bytes([0x23, 0x81, 0x60, 0x00, 0x60, 0x01, 0x00, 0x00])
        accel = bytes([0x23, 0x83, 0x60, 0x00, 0x10, 0x16, 0x00, 0x00])
    elif can_id == 0x602:
        speed = bytes([0x23, 0x81, 0x60, 0x00, 0xF0, 0x00, 0x00, 0x00])
        accel = bytes([0x23, 0x83, 0x60, 0x00, 0x10, 0x16, 0x00, 0x00])
    elif can_id in (0x604, 0x605, 0x606):
        speed = bytes([0x23, 0x81, 0x60, 0x00, 0xF0, 0x00, 0x00, 0x00])
        accel = bytes([0x23, 0x83, 0x60, 0x00, 0x10, 0x16, 0x00, 0x00])
    else:
        # Default speed/accel for unknown motors.
        speed = bytes([0x23, 0x81, 0x60, 0x00, 0x54, 0x01, 0x00, 0x00])
        accel = bytes([0x23, 0x83, 0x60, 0x00, 0x10, 0x16, 0x00, 0x00])
 
    send_can_frame(sock, can_id, speed)
    send_can_frame(sock, can_id, accel)
 
    # Set electronic gear to 8192 pulses per revolution.
    send_can_frame(sock, can_id, bytes([0x23, 0x90, 0x60, 0x00, 0x00, 0x20, 0x00, 0x00]))

# ---------------------------------------------------------------------------
# ROS node
# ---------------------------------------------------------------------------

class ArmControlNode:
    def __init__(self):
        rospy.init_node("arm_control")
        rospy.loginfo("Arm control node starting...")
 
        # Open CAN socket.
        try:
            self.can_socket = open_can_socket(CAN_INTERFACE)
            rospy.loginfo(f"CAN socket opened on {CAN_INTERFACE}")
        except OSError as e:
            rospy.logerr(f"Failed to open CAN socket on {CAN_INTERFACE}: {e}")
            raise
 
        # Initialize all motors.
        self._setup_motors()
 
        # Subscribe to joint commands from the Jetson.
        rospy.Subscriber(
            "/arm/joint_commands",
            JointState,
            self.joint_command_callback,
            queue_size=10
        )
 
        rospy.loginfo("Arm control node ready, waiting for joint commands...")
 
    def _setup_motors(self) -> None:
        """Initialize all CAN motors on startup."""
        rospy.loginfo("Initializing motors...")
        for joint_name, can_id in JOINT_TO_MOTOR_ID.items():
            if can_id is None:
                continue  # Skip PWM-controlled motors.
            try:
                setup_motor(self.can_socket, can_id)
                rospy.loginfo(f"Initialized {joint_name} (CAN ID: 0x{can_id:03X})")
            except OSError as e:
                rospy.logwarn(f"Failed to initialize {joint_name} (CAN ID: 0x{can_id:03X}): {e}")
 
    def joint_command_callback(self, msg: JointState) -> None:
        """
        Callback for incoming joint commands.
 
        Maps each joint in the message to its motor CAN ID and sends
        the corresponding CANopen position command.
        """
        for i, joint_name in enumerate(msg.name):
            can_id = JOINT_TO_MOTOR_ID.get(joint_name)
 
            if can_id is None and joint_name == "elbow":
                rospy.logdebug("Elbow joint is PWM controlled, skipping CAN command.")
                continue
 
            if can_id is None:
                rospy.logwarn(f"Unknown joint name: '{joint_name}', skipping.")
                continue
 
            # Position is in degrees.
            angle_deg = msg.position[i] if i < len(msg.position) else 0.0
 
            try:
                send_motor_position(self.can_socket, can_id, angle_deg)
                rospy.logdebug(
                    f"Sent position command to {joint_name} "
                    f"(CAN ID: 0x{can_id:03X}) — {angle_deg:.2f} degrees"
                )
            except OSError as e:
                rospy.logerr(
                    f"Failed to send CAN message to {joint_name} "
                    f"(CAN ID: 0x{can_id:03X}): {e}"
                )
 
    def spin(self):
        rospy.spin()
 
    def shutdown(self):
        rospy.loginfo("Arm control node shutting down, closing CAN socket.")
        self.can_socket.close()
 
 
# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
 
if __name__ == "__main__":
    node = ArmControlNode()
    rospy.on_shutdown(node.shutdown)
    node.spin()

