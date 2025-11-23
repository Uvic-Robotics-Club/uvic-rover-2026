#!/usr/bin/env python3

import rospy
from std_msgs.msg import String
from std_msgs.msg import Bool
import time

class Watchdog:
    def __init__(self, timeout=0.5, check_interval=0.1):
        self.timeout = timeout
        self.last_msg_time = time.time()
        self.triggered = False

        # Publish to "drive/watchdogResets"
        self.watchdog_pub = rospy.Publisher("drive/watchdogResets", Bool, queue_size=1)

        # Subscribe to "/drive/cmd_vel"
        self.watchdog_sub = rospy.Subscriber("/drive/cmd_vel", String, self.cmdVelCallback)

        # Timer to check watchdog periodically
        rospy.Timer(rospy.Duration(check_interval), self.check_watchdog)

    def cmdVelCallback(self, data):
        """Reset the watchdog timer."""
        self.last_msg_time = time.time()
        if self.triggered:
            self.triggered = False
            self.watchdog_pub.publish(False)

    def check_watchdog(self, event):
        """Check if the watchdog has timed out."""
        if time.time() - self.last_reset_time > self.timeout:
            if not self.triggered:
                rospy.logerr("No /drive/cmd_vel messages received")
                self.triggered = True
                self.watchdog_pub.publish(True)

if __name__ == "__main__":
    rospy.init_node("cmd_vel_watchdog")
    watchdog = Watchdog(timeout=0.5, check_interval=0.1)
    rospy.spin()