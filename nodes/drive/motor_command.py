#!/usr/bin/env python3
"""
Motor Command Node
------------------
- Subscribes to /joy_processed for joystick inputs
- Subscribes to /drive/watchdogResets for watchdog status
- Publishes current drive outputs to /drive/cmd_vel at 10hz

Joystick mapping:
    axes[1] -> left motor input
    axes[4] -> right motor input
    buttons[0] -> manual e-stop

Run with:
    rosrun uvic_rover motor_command.py _interface:=<interface name>
"""

import rospy
from std_msgs.msg import String, Bool
from sensor_msgs.msg import Joy

MAX_SPEED = 10
MIN_SPEED = -10
PUBLISH_RATE_HZ = 10


# =============================================================================
# Hardware Abstraction Layer (HAL)
# =============================================================================
class DriveHAL:
    def __init__(self, backend):
        if backend == "simulation":
            self.interface = SimulatedDriveInterface()
        elif backend == "PWM":
            self.interface = PWMDriveInterface()
        elif backend == "CAN":
            self.interface = CANDriveInterface()
        else:
            raise ValueError("Unsupported backend")

    def set_motor_speeds(self, left_speed, right_speed):
        self.interface.send_motor_commands(left_speed, right_speed)

    def stop_motors(self):
        self.interface.send_motor_commands(0, 0)


class SimulatedDriveInterface:
    def send_motor_commands(self, left, right):
        # STUB: Publish to simulation
        print(f"Left speed {left}, Right speed {right}")


class PWMDriveInterface:
    def send_motor_commands(self, left, right):
        # STUB: Publish to PWM
        print(f"Left speed {left}, Right speed {right}")


class CANDriveInterface:
    def send_motor_commands(self, left, right):
        # STUB: Publish to CAN
        print(f"Left speed {left}, Right speed {right}")


# =============================================================================
# Motor Command Node
# =============================================================================
class MotorCommandNode:
    def __init__(self):
        rospy.init_node("motor_command", anonymous=False)
        self.interface_name = rospy.get_param('~interface')
        rospy.loginfo(f"Motor command node starting on interface: {self.interface_name}")

        self.left_out = 0.0
        self.right_out = 0.0
        self.estop_flag = False
        self.watchdog_flag = False
        self.hal = DriveHAL(self.interface_name)

        self.cmd_vel_pub = rospy.Publisher("/drive/cmd_vel", String, queue_size=10)
        rospy.Subscriber("/joy_processed", Joy, self.joy_callback)
        rospy.Subscriber("/drive/watchdogResets", Bool, self.watchdog_callback)

        self.rate = rospy.Rate(PUBLISH_RATE_HZ)
        rospy.loginfo("Motor command node ready")

    def watchdog_callback(self, msg):
        self.watchdog_flag = msg.data

    def get_exponential_response(self, raw_input):
        sign = 1 if raw_input >= 0 else -1
        percentage = abs(raw_input) * 100

        output = (1.2 * (1.043 ** percentage) - 1.2 + 0.2 * percentage) / 100
        return round(sign * output, 2)

    def joy_callback(self, msg):
        if msg.buttons[0]:  # A button triggers manual e-stop
            self.estop_flag = True
            return

        left_out, right_out = self.get_exponential_response(msg.axes[1]), self.get_exponential_response(msg.axes[4])
        self.left_out = self.check_safety(left_out)
        self.right_out = self.check_safety(right_out)

    def check_safety(self, speed):
        return max(MIN_SPEED, min(speed if speed else 0, MAX_SPEED))

    def send_command(self):
        if self.estop_flag or self.watchdog_flag:
            self.hal.stop_motors()
        else:
            self.hal.set_motor_speeds(self.left_out, self.right_out)

    def publish_drive_status(self):
        cmd_vel_msg = f"Left speed: {self.left_out}, Right speed: {self.right_out}"
        self.cmd_vel_pub.publish(String(data=cmd_vel_msg))

    def run(self):
        while not rospy.is_shutdown():
            self.send_command()
            self.publish_drive_status()
            self.rate.sleep()


# =============================================================================
# Entry point
# =============================================================================
if __name__ == "__main__":
    try:
        node = MotorCommandNode()
        node.run()
    except rospy.ROSInterruptException:
        pass
