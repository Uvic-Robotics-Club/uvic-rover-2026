#! /usr/bin/env python3
import rospy
from sensor_msgs.msg import Joy

dz = 0.5
joy_pub = None

def deadzone(val, dz):
	if abs(val) < dz:
		return 0.0
	return val

def joy_raw(msg):
	
	lx = msg.axes[0]
	ly = msg.axes[1]
	lt = msg.axes[2]
	rx = msg.axes[3]
	ry = msg.axes[4]
	rt = msg.axes[5]

	left_x = deadzone(lx, dz)
	left_y = deadzone(ly, dz)
	left_t = deadzone(lt, dz)
	
	right_x = deadzone(rx, dz)
	right_y = deadzone(ry, dz)
	right_t = deadzone(rt, dz)

	buttons = msg.buttons

	
	print(f"-----------------------------------------")
	print(f"Left Stick: X={left_x:.2f} Y={left_y:.2f}")
	print(f"Left Trigger: {left_t:.2f}")
	print(f"Right Stick: X={right_x:.2f} Y={right_y:.2f}")
	print(f"Right Trigger: {right_t:.2f}")
	print(f"-----------------------------------------")
	print(f"Buttons:")
	print(f"A: {buttons[0]}")
	print(f"B: {buttons[1]}")
	print(f"X: {buttons[2]}")
	print(f"Y: {buttons[3]}")
	print(f"L Trigger: {buttons[4]}")
	print(f"R Trigger: {buttons[5]}")
	print(f"Back: {buttons[6]}")
	print(f"Start: {buttons[7]}")
	print(f"L Joystick: {buttons[9]}")
	print(f"R Joystick: {buttons[10]}")
	print(f"Left Arrow: {buttons[11]}")
	print(f"Right Arrow: {buttons[12]}")
	print(f"Up Arrow: {buttons[13]}")
	print(f"Down Arrow: {buttons[14]}")
	
	new_msg = Joy()
	new_msg.header = msg.header
	new_msg.axes = [lx, ly, lt, rx, ry, rt]
	new_msg.buttons = buttons
	
	joy_pub.publish(new_msg)


def main():
	global joy_pub
	
	rospy.init_node("joy_output")
	joy_pub = rospy.Publisher("/joy_processed", Joy, queue_size=10)
	rospy.Subscriber("/joy", Joy, joy_raw)
	rospy.spin()

if __name__ == '__main__':
	main()
