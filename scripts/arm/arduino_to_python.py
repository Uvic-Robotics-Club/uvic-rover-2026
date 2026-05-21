# This is a conversion of the code found on the arduino for the arm into python.

import time
import sys
import os
from collections import deque

# =============================================================================
# CAN BUS INTERFACE - Replace with actual CAN library (e.g. python-can)
# =============================================================================
# import can
# bus = can.interface.Bus(channel='can0', bustype='socketcan')

def can_send(can_id, data):
    """
    Send a CAN message.
    Replace this with actual CAN bus send logic.
    
    Example with python-can:
        msg = can.Message(arbitration_id=can_id, data=data, is_extended_id=False)
        bus.send(msg)
    """
    print(f"[CAN STUB] ID=0x{can_id:03X}, Data={[f'0x{b:02X}' for b in data]}")

# =============================================================================
# ANSI color codes and styles
# =============================================================================
class Style:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    BG_BLACK = "\033[40m"

# =============================================================================
# Constants
# =============================================================================
CAN_BASE_ID      = 0x600
PULSES_PER_REV   = 2654208
FULL_TRAVEL_TIME = 2.750  # seconds (gripper full open/close)

# =============================================================================
# Motor state
# =============================================================================
motor_states  = {i: 0.0 for i in range(1, 7)}
gripper_state = "Open"
command_history = deque(maxlen=5)

# =============================================================================
# CAN helpers
# =============================================================================
def send_motor_command(can_id, data):
    """Send an 8-byte CANopen SDO command."""
    can_send(can_id, data)

def speed_setup():
    """
    Configure speed, acceleration, and working mode for all CAN motors.
    Mirrors Arduino speedSetup().
    """
    # Motor at 0x600 — Position mode + enable
    send_motor_command(0x600, [0x2B, 0x40, 0x60, 0x00, 0x0F, 0x00, 0x00, 0x00])
    send_motor_command(0x600, [0x2F, 0x60, 0x60, 0x00, 0x01, 0x00, 0x00, 0x00])
    send_motor_command(0x600, [0x23, 0x81, 0x60, 0x00, 0x54, 0x01, 0x00, 0x00])  # speed 500
    send_motor_command(0x600, [0x23, 0x83, 0x60, 0x00, 0x10, 0x16, 0x00, 0x00])  # accel
    send_motor_command(0x600, [0x23, 0x90, 0x60, 0x00, 0x00, 0x20, 0x00, 0x00])  # electronic gear

    # Motor 1 (0x601)
    send_motor_command(0x601, [0x23, 0x81, 0x60, 0x00, 0x60, 0x01, 0x00, 0x00])
    send_motor_command(0x601, [0x23, 0x83, 0x60, 0x00, 0x10, 0x16, 0x00, 0x00])

    # Motor 2 (0x602)
    send_motor_command(0x602, [0x23, 0x81, 0x60, 0x00, 0xF0, 0x00, 0x00, 0x00])
    send_motor_command(0x602, [0x23, 0x83, 0x60, 0x00, 0x10, 0x16, 0x00, 0x00])

    # Motor 4 (0x604)
    send_motor_command(0x604, [0x23, 0x81, 0x60, 0x00, 0xF0, 0x00, 0x00, 0x00])
    send_motor_command(0x604, [0x23, 0x83, 0x60, 0x00, 0x10, 0x16, 0x00, 0x00])

# =============================================================================
# Gripper control
# NOTE: Gripper was previously driven by a DC motor via H-bridge (in3/in4/enB).
# Now replaced with CAN. Fill in the correct CAN ID and commands below.
# =============================================================================
GRIPPER_CAN_ID = 0x6FF  # TODO: Replace with actual gripper CAN ID

def open_gripper():
    """Send CAN command to open gripper."""
    global gripper_state
    print("[GRIPPER] Opening...")
    # TODO: Replace with actual CAN open command for gripper
    send_motor_command(GRIPPER_CAN_ID, [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])  # STUB
    time.sleep(FULL_TRAVEL_TIME)
    gripper_state = "Open"
    print("[GRIPPER] Fully opened")

def close_gripper():
    """Send CAN command to close gripper."""
    global gripper_state
    print("[GRIPPER] Closing...")
    # TODO: Replace with actual CAN close command for gripper
    send_motor_command(GRIPPER_CAN_ID, [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])  # STUB
    time.sleep(FULL_TRAVEL_TIME)
    gripper_state = "Closed"
    print("[GRIPPER] Fully closed")

# =============================================================================
# Motor 3 (Elbow) — previously PWM, now CAN
# NOTE: The Arduino used open-loop timed PWM to estimate angle.
# On CAN this should use position mode like the other motors.
# Fill in the correct CAN ID and any elbow-specific scaling below.
# =============================================================================
ELBOW_CAN_ID = 0x603  # TODO: Confirm elbow motor CAN ID

elbow_current_angle = 0.0

def process_elbow_motor(angle):
    """
    Move elbow motor (motor 3) to an absolute angle via CAN.
    Previously used timed PWM; now uses CANopen position mode.
    """
    global elbow_current_angle
    angle = -angle  # Matches Arduino sign convention
    print(f"[ELBOW] Moving to angle: {angle}")

    target_position = int((angle / 360.0) * PULSES_PER_REV)
    # TODO: Apply elbow-specific pulse scaling if needed (check with hardware)

    data = [0x23, 0x7A, 0x60, 0x00] + list(target_position.to_bytes(4, byteorder='little', signed=True))
    send_motor_command(ELBOW_CAN_ID, data)
    send_motor_command(ELBOW_CAN_ID, [0x2B, 0x40, 0x60, 0x00, 0x3F, 0x00, 0x00, 0x00])

    elbow_current_angle = angle

# =============================================================================
# General CAN motor command (motors 1, 2, 4, 5, 6)
# =============================================================================
def process_motor_command(motor_id, angle):
    """
    Move a CAN motor to an absolute angle.
    Applies home position offsets matching the Arduino.
    motor_id is 1-6 (mapped internally to CAN IDs 0x601-0x606).
    """
    can_id = CAN_BASE_ID + motor_id

    # Home position offsets (from Arduino processMotorCommand)
    if can_id == 0x600:
        return  # Motor 0 forbidden
    elif can_id == 0x601:
        angle -= 65
    elif can_id == 0x602:
        pass  # No offset
    elif can_id == 0x604:
        angle = -angle
        angle -= (32 + 180)
    elif can_id == 0x605:
        angle = -angle
        angle -= 87
    elif can_id == 0x606:
        angle = -angle
        angle += 17

    target_position = int((angle / 360.0) * PULSES_PER_REV)

    # Per-motor pulse scaling
    if can_id == 0x601:
        target_position = int(target_position * 1.2458)
    elif can_id in (0x604, 0x605, 0x606):
        target_position = int(target_position * 0.63)

    data = [0x23, 0x7A, 0x60, 0x00] + list(target_position.to_bytes(4, byteorder='little', signed=True))
    send_motor_command(can_id, data)
    send_motor_command(can_id, [0x2B, 0x40, 0x60, 0x00, 0x3F, 0x00, 0x00, 0x00])

    motor_states[motor_id] = angle

# =============================================================================
# High-level commands
# =============================================================================
presets = {
    "reset":   ["1 0", "2 0", "3 0", "4 0", "5 0", "6 0"],
    "forward": ["2 60", "3 30", "6 90"],
    "lift":    ["2 0", "3 0"],
}

def send_command(command):
    """Parse and dispatch a command string."""
    command_history.append(command)
    parts = command.strip().split()

    if command.upper() == "GO":
        open_gripper()
    elif command.upper() == "GC":
        close_gripper()
    elif len(parts) == 2:
        motor_id = int(parts[0])
        angle    = float(parts[1])
        if motor_id == 3:
            process_elbow_motor(angle)
        else:
            process_motor_command(motor_id, angle)
        motor_states[motor_id] = angle

def execute_preset(preset_name):
    if preset_name in presets:
        for cmd in presets[preset_name]:
            send_command(cmd)
            time.sleep(0.3)

def reset_all():
    execute_preset("reset")
    close_gripper()

# =============================================================================
# Terminal UI  (unchanged from original Python script)
# =============================================================================
def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

def draw_interface():
    clear_console()
    width = 75
    print(f"{Style.BG_BLACK}{Style.CYAN}╔{'═' * (width-2)}╗{Style.RESET}")
    print(f"{Style.BG_BLACK}{Style.CYAN}║{Style.BOLD} Robot Arm Control Interface {' ' * (width-31)}║{Style.RESET}")
    print(f"{Style.BG_BLACK}{Style.CYAN}╠{'═' * (width-2)}╣{Style.RESET}")

    motor_colors = [Style.RED, Style.GREEN, Style.YELLOW, Style.BLUE, Style.MAGENTA, Style.CYAN]
    for motor, angle in motor_states.items():
        color = motor_colors[motor - 1]
        bar_length = int((angle + 120) / 8)
        bar = '█' * bar_length
        padding = ' ' * (30 - bar_length)
        left  = (padding + bar) if angle < 0 else ' ' * 15
        right = '' if angle < 0 else (bar + padding)
        print(f"{Style.BG_BLACK}{Style.CYAN}║ {color}Motor {motor}: {left}│{right} {angle:>6.2f}°{' ' * (width-66)}║{Style.RESET}")

    gripper_color = Style.RED if gripper_state == "Closed" else Style.GREEN
    print(f"{Style.BG_BLACK}{Style.CYAN}║ {gripper_color}Gripper: {gripper_state:<6}{' ' * (width-18)}║{Style.RESET}")

    print(f"{Style.BG_BLACK}{Style.CYAN}╠{'═' * (width-2)}╣{Style.RESET}")
    print(f"{Style.BG_BLACK}{Style.CYAN}║{Style.YELLOW} Commands: [motor] [angle], reset, forward, lift, GC, GO{' ' * (width-58)}║{Style.RESET}")
    print(f"{Style.BG_BLACK}{Style.CYAN}║{Style.YELLOW} Example: '3 45' sets motor 3 to 45° (Range: -120 to 120){' ' * (width-59)}║{Style.RESET}")
    print(f"{Style.BG_BLACK}{Style.CYAN}╠{'═' * (width-2)}╣{Style.RESET}")

    print(f"{Style.BG_BLACK}{Style.CYAN}║ {Style.MAGENTA}Command History:{' ' * (width-19)}║{Style.RESET}")
    for cmd in reversed(command_history):
        print(f"{Style.BG_BLACK}{Style.CYAN}║ {Style.CYAN}> {cmd:<{width-5}}║{Style.RESET}")
    for _ in range(5 - len(command_history)):
        print(f"{Style.BG_BLACK}{Style.CYAN}║{' ' * (width-2)}║{Style.RESET}")

    print(f"{Style.BG_BLACK}{Style.CYAN}╚{'═' * (width-2)}╝{Style.RESET}")

# =============================================================================
# Startup & main loop
# =============================================================================
def initialize_system():
    print(f"{Style.YELLOW}Initializing CAN bus and motors...{Style.RESET}")
    speed_setup()
    reset_all()
    open_gripper()
    print(f"{Style.GREEN}System initialized. Gripper open.{Style.RESET}")

def main():
    initialize_system()

    while True:
        draw_interface()
        user_input = input(f"{Style.GREEN}Enter command: {Style.RESET}").strip().lower()

        if user_input == 'exit':
            break
        elif user_input == 'reset':
            reset_all()
        elif user_input in presets:
            execute_preset(user_input)
        elif user_input in ['gc', 'go']:
            send_command(user_input.upper())
        elif len(user_input.split()) == 2:
            motor, angle = user_input.split()
            try:
                motor = int(motor)
                angle = float(angle)
                if 1 <= motor <= 6 and -120 <= angle <= 120:
                    send_command(f"{motor} {angle}")
                else:
                    raise ValueError
            except ValueError:
                print(f"{Style.RED}Invalid input. Motor 1-6, angle -120 to 120.{Style.RESET}")
                time.sleep(1)
        else:
            print(f"{Style.RED}Invalid input. Please try again.{Style.RESET}")
            time.sleep(1)

    print(f"{Style.YELLOW}Exiting.{Style.RESET}")

if __name__ == "__main__":
    main()