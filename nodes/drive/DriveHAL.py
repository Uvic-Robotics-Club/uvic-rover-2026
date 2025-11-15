#!/usr/bin/env python3

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
        # Publish to simulation
        print(f"Simulated left speed {left}, right speed {right}")

class PWMDriveInterface:
    def send_motor_commands(self, left, right):
        # Publish to PWM
        print(f"PWM left speed {left}, right speed {right}")

class CANDriveInterface:
    def send_motor_commands(self, left, right):
        # Publish to CAN
        print(f"CAN left speed {left}, right speed {right}")