#!/usr/bin/env python3

import rospy
from std_msgs.msg import String
from std_msgs.msg import Bool
from sensor_msgs.msg import Joy 

left_y_out = ""
right_y_out = ""

watchdogFlag = False
estopFlag = False

MAX_SPEED = 10
MIN_SPEED = -10



def MotorCommand():
    """
        Converts /joy_processed messages from joysticks to /drive/cmd_vel messages for motors

        Exponential curve applied to left_y_out, right_y_out in joyCallback,
        Manual E-Stop and watchdog timeout applied in joyCallback,
        Speed scaling applied within joyCallback,
        Sends to HAL using sendCommand 
    """
    rospy.init_node("MotorCommand")

    cmdVelPublisher = rospy.Publisher("/drive/cmd_vel", String, queue_size=10)
    rospy.Subscriber("/joy_processed", Joy, joyCallback)
    rospy.Subscriber("/drive/watchdogResets", Bool, watchDogCallback)
    rate = rospy.Rate(10)

    while not rospy.is_shutdown():
        # Send command to HAL
        sendCommand(left_y_out, right_y_out)
        # Publish/log final drive commands with response curves:
        cmd_vel_msg = "Left speed: %s, Right speed: %s" % (left_y_out, right_y_out)
        cmdVelPublisher.publish(cmd_vel_msg)
        rate.sleep()


def watchDogCallback(msg):
    # Check for watchdog timeout
    global watchdogFlag
    watchdogFlag = msg


def joyCallback(msg):
    global estopFlag, left_y_out, right_y_out
    if msg.button[0]: # A button triggers manual estop
        estopFlag = True
        return
    
    left_y_in = msg.axes[1] # left joysticks y axis
    right_y_in = msg.axes[4] # right joysticks y axis

    # Apply exponential response curve
    left_y_out = 1.2*(1.043**left_y_in) - 1.2 + 0.2*left_y_in
    right_y_out = 1.2*(1.043**right_y_in) - 1.2 + 0.2*right_y_in

    # Apply safety check
    left_y_out = checkSafety(left_y_out)
    right_y_out = checkSafety(right_y_out)


def sendCommand(left_y_out, right_y_out):
    # Send processed speeds to HAL
    if estopFlag or watchdogFlag:
        hal.stop_motors()
    else:
        hal.set_motor_speeds(left_y_out, right_y_out) 

def checkSafety(speed):
    # Implement speed scaling
    return max(MIN_SPEED, min(int(speed) if speed else 0, MAX_SPEED))

if __name__ == "__main__":
    try:
        MotorCommand()
    except rospy.ROSInterruptionException:
        pass

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
        print(f"Simulated left speed {left}, right speed {right}")

class PWMDriveInterface:
    def send_motor_commands(self, left, right):
        # STUB: Publish to PWM
        print(f"PWM left speed {left}, right speed {right}")

class CANDriveInterface:
    def send_motor_commands(self, left, right):
        # STUB: Publish to CAN
        print(f"CAN left speed {left}, right speed {right}")

hal = DriveHAL("simulation")