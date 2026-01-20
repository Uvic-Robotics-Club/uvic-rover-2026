import serial
import time
import sys
import os
from collections import deque

# ANSI color codes and styles
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BG_BLACK = "\033[40m"

# Open serial connection
try:
    ser = serial.Serial('/dev/ttyACM1', 115200, timeout=1)
    time.sleep(2)  # Wait for the connection to initialize
except serial.SerialException as e:
    print(f"{Style.RED}Error opening port COM9: {e}{Style.RESET}")
    print("Please ensure no other program is using the port and you have the necessary permissions.")
    sys.exit(1)

# Presets (adjusted for -120 to 120 range)
presets = {
    "reset": ["1 0", "2 0", "3 0", "4 0", "5 0", "6 0"],
    "forward": ["2 60", "3 30", "6 90"],
    "lift": ["2 0", "3 0"]
}

# Motor states
motor_states = {i: 0 for i in range(1, 7)}

# Gripper state
gripper_state = "Open"

# Command history
command_history = deque(maxlen=5)

def send_command(command):
    global gripper_state
    ser.write(f"{command}\n".encode())
    command_history.append(command)
    
    parts = command.split()
    if len(parts) == 2 and parts[0].isdigit():
        motor = int(parts[0])
        angle = float(parts[1])
        if 1 <= motor <= 6 and -120 <= angle <= 120:
            motor_states[motor] = angle
    elif command == "GC":
        gripper_state = "Closed"
    elif command == "GO":
        gripper_state = "Open"

def execute_preset(preset_name):
    if preset_name in presets:
        for command in presets[preset_name]:
            send_command(command)
            time.sleep(0.3)

def reset_all():
    execute_preset("reset")

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

def draw_interface():
    clear_console()
    width = 75
    print(f"{Style.BG_BLACK}{Style.CYAN}╔{'═' * (width-2)}╗{Style.RESET}")
    print(f"{Style.BG_BLACK}{Style.CYAN}║{Style.BOLD} Robot Control Interface {' ' * (width-27)}║{Style.RESET}")
    print(f"{Style.BG_BLACK}{Style.CYAN}╠{'═' * (width-2)}╣{Style.RESET}")
    
    motor_colors = [Style.RED, Style.GREEN, Style.YELLOW, Style.BLUE, Style.MAGENTA, Style.CYAN]
    for motor, angle in motor_states.items():
        color = motor_colors[motor - 1]
        bar_length = int((angle + 120) / 8)  # Scale -120 to 120 to 0-30 for display
        bar = '█' * bar_length
        padding = ' ' * (30 - bar_length)
        if angle < 0:
            left = padding + bar
            right = ''
        else:
            left = ' ' * 15
            right = bar + padding
        print(f"{Style.BG_BLACK}{Style.CYAN}║ {color}Motor {motor}: {left}│{right} {angle:>6.2f}°{' ' * (width-66)}║{Style.RESET}")
    
    gripper_color = Style.RED if gripper_state == "Closed" else Style.GREEN
    print(f"{Style.BG_BLACK}{Style.CYAN}║ {gripper_color}Gripper: {gripper_state:<6}{' ' * (width-18)}║{Style.RESET}")
    
    print(f"{Style.BG_BLACK}{Style.CYAN}╠{'═' * (width-2)}╣{Style.RESET}")
    print(f"{Style.BG_BLACK}{Style.CYAN}║{Style.YELLOW} Commands: [motor] [angle], reset, forward, lift, GC, GO{' ' * (width - 58)}║{Style.RESET}")
    print(f"{Style.BG_BLACK}{Style.CYAN}║{Style.YELLOW} Example: '3 45' sets motor 3 to 45° (Range: -120 to 120){' ' * (width - 59)}║{Style.RESET}")
    print(f"{Style.BG_BLACK}{Style.CYAN}╠{'═' * (width-2)}╣{Style.RESET}")
    
    print(f"{Style.BG_BLACK}{Style.CYAN}║ {Style.MAGENTA}Command History:{' ' * (width-19)}║{Style.RESET}")
    for cmd in reversed(command_history):
        print(f"{Style.BG_BLACK}{Style.CYAN}║ {Style.CYAN}> {cmd:<{width-5}}║{Style.RESET}")
    
    remaining_lines = 5 - len(command_history)
    for _ in range(remaining_lines):
        print(f"{Style.BG_BLACK}{Style.CYAN}║{' ' * (width-2)}║{Style.RESET}")
    
    print(f"{Style.BG_BLACK}{Style.CYAN}╚{'═' * (width-2)}╝{Style.RESET}")
def initialize_system():
    print(f"{Style.YELLOW}Initializing system...{Style.RESET}")
    reset_all()
    # time.sleep(1)
    send_command("GO")
    # time.sleep(1)
    print(f"{Style.GREEN}System initialized. Gripper open.{Style.RESET}")
    # time.sleep(2)

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
                    send_command(user_input)
                else:
                    raise ValueError
            except ValueError:
                print(f"{Style.RED}Invalid input. Motor should be 1-6 and angle should be between -120 and 120.{Style.RESET}")
                time.sleep(1)
        else:
            print(f"{Style.RED}Invalid input. Please try again.{Style.RESET}")
            time.sleep(1)

    ser.close()
    print(f"{Style.YELLOW}Serial connection closed. Exiting.{Style.RESET}")

if __name__ == "__main__":
    main()