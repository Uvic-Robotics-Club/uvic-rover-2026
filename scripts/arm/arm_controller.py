#!/usr/bin/env python3
"""
Arm Controller Node
-------------------
- On startup, sends all joints to home position (0 radians)
- Continuously republishes current target positions at 50hz to prevent drift
- Listens on /arm/joint_command for individual joint commands
- Listens on /arm/preset_command for preset moves

Command format on /arm/joint_command (std_msgs/String):
    "joint0 1.57"   -> moves joint0 to 1.57 radians
    "joint2 -0.5"   -> moves joint2 to -0.5 radians

Command format on /arm/preset_command (std_msgs/String):
    "home"          -> all joints to 0
    "reset"         -> alias for home
"""

import rospy
from std_msgs.msg import Float64, String

# =============================================================================
# Joint configuration
# =============================================================================
JOINTS = [
    "joint0",
    "joint1",
    "joint2",
    "joint3",
    "joint4",
    "end_effector_joint",
]

# Home position for each joint in radians
HOME_POSITION = {
    "joint0":             0.0,
    "joint1":             0.0,
    "joint2":             0.0,
    "joint3":             0.0,
    "joint4":             0.0,
    "end_effector_joint": 0.0,
}

# Joint limits in radians (matching URDF)
JOINT_LIMITS = {
    "joint0":             (-3.14159, 3.14159),
    "joint1":             (0.0,      3.14),
    "joint2":             (-2.094,   2.094),
    "joint3":             (-2.094,   2.094),
    "joint4":             (-2.094,   2.094),
    "end_effector_joint": (-2.094,   2.094),
}

# Presets — add more as needed
PRESETS = {
    "home":  {j: 0.0 for j in JOINTS},
    "reset": {j: 0.0 for j in JOINTS},
}

# =============================================================================
# Controller class
# =============================================================================
class ArmController:
    def __init__(self):
        rospy.init_node("arm_controller", anonymous=False)
        rospy.loginfo("Arm controller node starting...")

        # Current joint positions
        self.current_positions = dict(HOME_POSITION)

        # Create a publisher for each joint controller
        self.publishers = {}
        for joint in JOINTS:
            topic = f"/{joint}_position_controller/command"
            self.publishers[joint] = rospy.Publisher(topic, Float64, queue_size=10)
            rospy.loginfo(f"Publishing to {topic}")

        # Subscribers
        rospy.Subscriber("/arm/joint_command",  String, self.joint_command_callback)
        rospy.Subscriber("/arm/preset_command", String, self.preset_command_callback)

        # Publish rate — 50hz keeps joints locked without flooding the bus
        self.rate = rospy.Rate(50)

        # Wait for publishers to connect to Gazebo
        rospy.sleep(2.0)

        # Send home position on startup
        rospy.loginfo("Sending arm to home position...")
        self.go_to_preset("home")
        rospy.loginfo("Arm controller ready. Continuously holding position at 50hz.")

    def send_joint(self, joint_name, angle_rad):
        """Update target angle for a joint. Will be published on next loop tick."""
        if joint_name not in self.publishers:
            rospy.logwarn(f"Unknown joint: {joint_name}")
            return

        # Clamp to limits
        lo, hi = JOINT_LIMITS[joint_name]
        clamped = max(lo, min(hi, angle_rad))
        if clamped != angle_rad:
            rospy.logwarn(f"{joint_name}: {angle_rad:.3f} clamped to {clamped:.3f}")

        self.current_positions[joint_name] = clamped
        rospy.loginfo(f"{joint_name} -> {clamped:.3f} rad")

    def go_to_preset(self, preset_name):
        """Set all joints to a named preset position."""
        if preset_name not in PRESETS:
            rospy.logwarn(f"Unknown preset: {preset_name}")
            return
        rospy.loginfo(f"Moving to preset: {preset_name}")
        for joint, angle in PRESETS[preset_name].items():
            self.send_joint(joint, angle)

    def joint_command_callback(self, msg):
        """
        Handle individual joint commands.
        Expected format: "joint_name angle_in_radians"
        Example: "joint1 1.57"
        """
        parts = msg.data.strip().split()
        if len(parts) != 2:
            rospy.logwarn(f"Invalid joint command: '{msg.data}'. Use 'joint_name angle'")
            return
        joint_name = parts[0]
        try:
            angle = float(parts[1])
        except ValueError:
            rospy.logwarn(f"Invalid angle: '{parts[1]}'")
            return
        self.send_joint(joint_name, angle)

    def preset_command_callback(self, msg):
        """
        Handle preset commands.
        Expected format: "preset_name"
        Example: "home"
        """
        self.go_to_preset(msg.data.strip().lower())

    def publish_positions(self):
        """Continuously publish current target positions to all joint controllers."""
        for joint, angle in self.current_positions.items():
            self.publishers[joint].publish(Float64(angle))

    def run(self):
        """Main loop — republish target positions at 50hz to prevent drift."""
        while not rospy.is_shutdown():
            self.publish_positions()
            self.rate.sleep()


# =============================================================================
# Entry point
# =============================================================================
if __name__ == "__main__":
    try:
        controller = ArmController()
        controller.run()
    except rospy.ROSInterruptException:
        pass