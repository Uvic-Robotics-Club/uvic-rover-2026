#!/usr/bin/env python3
"""
Joy Output Node
---------------
- Subscribes to /joy for raw joystick input
- Applies a deadzone filter to stick and trigger axes
- Republishes filtered joystick messages on /joy_processed
- Supports both joystick input and keyboard control modes

Run with:
    rosrun uvic_rover joy_output.py _input:=<input method>
"""

import sys
import tty
import termios

import rospy
from sensor_msgs.msg import Joy

# =============================================================================
# Configuration
# =============================================================================
DEADZONE_THRESHOLD = 0.5

def deadzone(value, threshold):
    if abs(value) < threshold:
        return 0.0
    return value


def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


class InputInterface:
    def start(self):
        raise NotImplementedError("start() must be implemented by subclasses")


class JoyInputInterface(InputInterface):
    def __init__(self, publisher):
        self.publisher = publisher
        self.subscriber = rospy.Subscriber("/joy", Joy, self.joy_raw)

    def joy_raw(self, msg):
        if len(msg.axes) < 6:
            rospy.logwarn("Received joystick message with fewer than 6 axes")
            return

        lx, ly, lt, rx, ry, rt = msg.axes[:6]
        buttons = list(msg.buttons)

        left_x = deadzone(lx, DEADZONE_THRESHOLD)
        left_y = deadzone(ly, DEADZONE_THRESHOLD)
        left_t = deadzone(lt, DEADZONE_THRESHOLD)
        right_x = deadzone(rx, DEADZONE_THRESHOLD)
        right_y = deadzone(ry, DEADZONE_THRESHOLD)
        right_t = deadzone(rt, DEADZONE_THRESHOLD)

        print("-----------------------------------------")
        print(f"Left Stick: X={left_x:.2f} Y={left_y:.2f}")
        print(f"Left Trigger: {left_t:.2f}")
        print(f"Right Stick: X={right_x:.2f} Y={right_y:.2f}")
        print(f"Right Trigger: {right_t:.2f}")
        print("-----------------------------------------")
        print("Buttons:")

        button_labels = [
            "A", "B", "X", "Y", "L Trigger", "R Trigger",
            "Back", "Start", None, "L Joystick", "R Joystick",
            "Left Arrow", "Right Arrow", "Up Arrow", "Down Arrow",
        ]

        for index, label in enumerate(button_labels):
            if label is None:
                continue
            value = buttons[index] if index < len(buttons) else 0
            print(f"{label}: {value}")

        new_msg = Joy()
        new_msg.header = msg.header
        new_msg.axes = [lx, ly, lt, rx, ry, rt]
        new_msg.buttons = buttons
        self.publisher.publish(new_msg)

    def start(self):
        rospy.loginfo("Joy input mode active. Listening on /joy.")
        rospy.spin()


class KeyboardInputInterface(InputInterface):
    def __init__(self, publisher):
        self.publisher = publisher

    def start(self):
        print("Robot Control - Use WASD keys to control the robot.")
        print("  W: MOVE_FORWARD")
        print("  S: MOVE_BACKWARD")
        print("Press Ctrl+C to exit.\n")

        try:
            while not rospy.is_shutdown():
                key = getch().lower()
                if key == "\x03":
                    raise KeyboardInterrupt

                joy_msg = self.key_to_joy(key)
                if joy_msg:
                    print(f"Sending command for key: {key}")
                    self.publisher.publish(joy_msg)
                else:
                    print(f"Unrecognized command: '{key}'")
        except KeyboardInterrupt:
            print("\nExiting robot control program.")

    def key_to_joy(self, key):
        msg = Joy()
        msg.header.stamp = rospy.Time.now()
        msg.axes = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        msg.buttons = [0] * 15

        if key == "w":
            msg.axes[1] = 1.0
            msg.axes[4] = 1.0
        elif key == "s":
            msg.axes[1] = -1.0
            msg.axes[4] = -1.0
        else:
            return None

        return msg


def main():
    rospy.init_node("joy_output", anonymous=False)
    joy_pub = rospy.Publisher("/joy_processed", Joy, queue_size=10)

    input_source = rospy.get_param("~input").lower()
    if input_source == "keyboard":
        handler = KeyboardInputInterface(joy_pub)
    else:
        handler = JoyInputInterface(joy_pub)

    rospy.loginfo(f"Starting joy_output with input_source='{input_source}'")
    handler.start()


# =============================================================================
# Entry point
# =============================================================================
if __name__ == '__main__':
    main()
