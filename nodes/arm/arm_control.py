#!/usr/bin/env python3
"""
Arm Control Node
================
Subscribes to joint commands from the Jetson and relays them to the
robotic arm motors over CAN bus.

The Jetson handles all inverse kinematics and motion planning. This node
is purely a relay — it maps joint commands to motor CAN IDs and sends
the corresponding CAN messages.

Topic:
    /arm/joint_commands (sensor_msgs/JointState)
        - name:     list of joint names (must match JOINT_TO_MOTOR_ID keys)
        - position: desired position for each joint (radians)
        - velocity: desired velocity for each joint (rad/s)
        - effort:   desired torque for each joint (Nm)

CAN Interface:
    can0 — configured on the host and passed through to the container.
"""

import os
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
    "base_rotation": 0x01,
    "shoulder":      0x02,
    "elbow":         0x03,
    "wrist_pitch":   0x04,
    "wrist_rotation":0x05,
    "end_effector":  0x06,
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


def send_can_message(sock: socket.socket, can_id: int, data: bytes) -> None:
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


def build_can_payload(position: float, velocity: float, effort: float) -> bytes:
    """
    Build a CAN payload for the AK series motors.

    TODO: Replace with the actual AK Series CAN message format from the
    manual once confirmed. Currently sends placeholder zeros.

    Args:
        position: Desired joint position in radians.
        velocity: Desired joint velocity in rad/s.
        effort:   Desired joint torque in Nm.

    Returns:
        8-byte CAN payload.
    """
    # Placeholder — replace with actual AK series message packing.
    return b'\x00' * 8


# ---------------------------------------------------------------------------
# ROS node
# ---------------------------------------------------------------------------

class ArmControlNode:
    def __init__(self):
        rospy.init_node("arm_control_node")
        rospy.loginfo("Arm control node starting...")

        # Open CAN socket.
        try:
            self.can_socket = open_can_socket(CAN_INTERFACE)
            rospy.loginfo(f"CAN socket opened on {CAN_INTERFACE}")
        except OSError as e:
            rospy.logerr(f"Failed to open CAN socket on {CAN_INTERFACE}: {e}")
            raise

        # Subscribe to joint commands from the Jetson.
        rospy.Subscriber(
            "/arm/joint_commands",
            JointState,
            self.joint_command_callback,
            queue_size=10
        )

        rospy.loginfo("Arm control node ready, waiting for joint commands...")

    def joint_command_callback(self, msg: JointState) -> None:
        """
        Callback for incoming joint commands.

        Maps each joint in the message to its motor CAN ID and sends
        the corresponding CAN message.
        """
        for i, joint_name in enumerate(msg.name):
            can_id = JOINT_TO_MOTOR_ID.get(joint_name)

            if can_id is None:
                rospy.logwarn(f"Unknown joint name: '{joint_name}', skipping.")
                continue

            # Safely extract values — default to 0 if not provided.
            position = msg.position[i] if i < len(msg.position) else 0.0
            velocity = msg.velocity[i] if i < len(msg.velocity) else 0.0
            effort   = msg.effort[i]   if i < len(msg.effort)   else 0.0

            payload = build_can_payload(position, velocity, effort)

            try:
                send_can_message(self.can_socket, can_id, payload)
                rospy.logdebug(
                    f"Sent CAN message to {joint_name} "
                    f"(ID: 0x{can_id:02X}) — "
                    f"pos={position:.3f} vel={velocity:.3f} eff={effort:.3f}"
                )
            except OSError as e:
                rospy.logerr(f"Failed to send CAN message to {joint_name}: {e}")

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
