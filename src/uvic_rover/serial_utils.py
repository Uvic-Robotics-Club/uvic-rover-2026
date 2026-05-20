import os
import yaml
import rospkg
import rospy
import serial
import serial.tools.list_ports


def _sensor_key(config_ns):
    return config_ns.rstrip("/").split("/")[-1]


def _format_vidpid(port):
    if port.vid is None or port.pid is None:
        return "unknown"
    return f"{port.vid:04x}:{port.pid:04x}"


def _parse_vidpid(text):
    vid, pid = text.split(":")
    return int(vid, 16), int(pid, 16)


def _load_yaml_config(config_ns):
    sensor = _sensor_key(config_ns)

    package_path = rospkg.RosPack().get_path("uvic_rover")
    yaml_path = os.path.join(package_path, "config", "serial_ports.yaml")

    if not os.path.exists(yaml_path):
        return {}

    with open(yaml_path, "r") as file:
        data = yaml.safe_load(file) or {}

    return data.get("serial_ports", {}).get(sensor, {}) or {}


def open_serial_port(config_ns=None):
    """
    Open a serial device using this priority:

    1. Manual private override:
       rosrun uvic_rover imu.py _port:=/dev/ttyACM0

    2. ROS params loaded from serial_ports.yaml:
       /serial_ports/imu/port

    3. Directly read config/serial_ports.yaml if params were not loaded.

    4. Auto-detect by VID/PID from the config.

    5. If exactly one serial port exists and fallback is enabled, use it.

    6. Otherwise fail and print all detected ports.
    """

    config = {}

    if config_ns and rospy.has_param(config_ns):
        config = rospy.get_param(config_ns) or {}
    elif config_ns:
        config = _load_yaml_config(config_ns)

    name = config.get("name", _sensor_key(config_ns).upper() if config_ns else "Serial device")

    # Manual overrides always win.
    manual_port = str(rospy.get_param("~port", "")).strip()
    manual_baud = rospy.get_param("~baud", None)
    manual_timeout = rospy.get_param("~timeout", None)

    if manual_port:
        port = manual_port
        rospy.loginfo(f"{name}: using manual port override {port}")
    else:
        # Use configured port if present.
        configured_port = str(config.get("port", "")).strip()

        if configured_port:
            port = configured_port
            rospy.loginfo(f"{name}: using configured port {port}")
        else:
            ports = sorted(serial.tools.list_ports.comports(), key=lambda p: p.device)

            if not ports:
                rospy.logfatal(
                    f"{name}: no serial ports found.\n"
                    "Check that the USB device is attached into WSL/Docker."
                )
                rospy.signal_shutdown(f"{name} serial port not found")
                raise rospy.ROSInterruptException

            allowed_vidpids = {
                _parse_vidpid(text)
                for text in config.get("vidpids", [])
            }

            matches = [
                p for p in ports
                if p.vid is not None
                and p.pid is not None
                and (p.vid, p.pid) in allowed_vidpids
            ]

            if len(matches) == 1:
                port = matches[0].device
                rospy.loginfo(
                    f"{name}: auto-detected on {port} "
                    f"(VID:PID={_format_vidpid(matches[0])})"
                )
            elif bool(config.get("allow_single_port_fallback", True)) and len(ports) == 1:
                port = ports[0].device
                rospy.logwarn(
                    f"{name}: no configured port or exact VID/PID match, "
                    f"but only one serial port exists. Using {port}."
                )
            else:
                port_list = "\n".join(
                    f"  - {p.device} | {p.description} | VID:PID={_format_vidpid(p)}"
                    for p in ports
                )

                match_list = "\n".join(
                    f"  - {p.device} | {p.description} | VID:PID={_format_vidpid(p)}"
                    for p in matches
                ) or "  (none)"

                rosrun_hint = config.get(
                    "rosrun_hint",
                    "rosrun uvic_rover <node>.py _port:=/dev/ttyUSB0"
                )

                rospy.logfatal(
                    f"{name}: serial port is ambiguous.\n"
                    f"Config namespace: {config_ns}\n"
                    f"Ports seen:\n{port_list}\n"
                    f"VID/PID matches:\n{match_list}\n"
                    f"Fix: pass the port manually, e.g.:\n"
                    f"  {rosrun_hint}"
                )

                rospy.signal_shutdown(f"{name} serial port ambiguous")
                raise rospy.ROSInterruptException

    baud = int(manual_baud if manual_baud is not None else config.get("baud", 9600))
    timeout = float(
        manual_timeout if manual_timeout is not None else config.get("timeout", 1.0)
    )

    rospy.loginfo(f"{name}: opening {port} @ {baud} baud, timeout={timeout}")
    return serial.Serial(port, baudrate=baud, timeout=timeout)