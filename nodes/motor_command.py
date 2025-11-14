#!/usr/bin/env python3

import rospy
from std_msgs.msg import String
from sensor_msgs.msg import Joy 
from DriveHAL.py import DriveHAL

left_y_out = ""
right_y_out = ""

watchdogFlag = False
estopFlag = False

MAX_SPEED = 10
MIN_SPEED = -10

hal = DriveHAL("simulation")

#
# Assuming deadzone is applied in Joy
# Exponential curve applied to left_y_out, right_y_out in joyCallback,
# Manual E-Stop and watchdog timeout applied in joyCallback,
# Speed scaling applied within cmdVelCallback
#

def MotorCommand():
    rospy.init_node("MotorCommand")

    rospy.Subscriber("/drive/cmd_vel", String, cmdVelCallback)
    rospy.Subscriber("/joy", Joy, joyCallback)
    rospy.Subscriber("/robot/watchdogResets", bool, watchDogCallback)
    rate = rospy.Rate(10)

    while not rospy.is_shutdown():
        # log final drive commands with response curves:
        rospy.loginfo("Left speed: %s, Right speed: %s", left_y_out, right_y_out) 
        rospy.spin()


def watchDogCallback(msg):
    # Check for watchdog timeout
    watchdogFlag = msg


def joyCallback(msg):
    # Ignore x-axis for tank steering
    if msg.button[0]: # assuming button[0] is manual estop
        estopFlag = True
        return
    
    left_y_in = msg.axes[1] # assuming axes[1] is left joysticks y axis
    right_y_in = msg.axes[4] # assuming axes[4] is right joysticks y axis

    # TODO: Handle stale input

    # Apply exponential response curve
    left_y_out = (1.2*1.043)**(left_y_in) - (1.2*1.043)**(left_y_in)
    right_y_out = (1.2*1.043)**(right_y_in) - (1.2*1.043)**(right_y_in)


def cmdVelCallback(data):
    # Publish speeds to /drive/cmd_vel
    if estopFlag or watchdogFlag:
        hal.stop_motors()
    else:
        # Apply safety check, send to HAL
        hal.set_motor_speeds(checkSafety(left_y_out), checkSafety(right_y_out)) 

def checkSafety(speed):
    # Implement speed scaling
    return max(MIN_SPEED, min(speed, MAX_SPEED))

if __name__ == "__main__":
    try:
        MotorCommand()
    except rospy.ROSInterruptionException:
        pass