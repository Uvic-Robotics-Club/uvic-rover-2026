#!/usr/bin/env python3
# gps.py — ROS Noetic NavSatFix publisher for Adafruit GPS over UART (pyserial).
# - Publishes /sensors/gps/fix  (sensor_msgs/NavSatFix)
# - Publishes /sensors/gps/fix_common (gps_common/GPSFix) [optional debug]
# Key fixes:
#   * Fresh header.stamp each publish
#   * Realistic position_covariance (from HDOP when available)
#   * Correct NavSatStatus mapping (no hard-coded "1")
#   * Avoids function-scope imports (no UnboundLocalError)

import time
import serial
import serial.tools.list_ports

import rospy
from sensor_msgs.msg import NavSatFix, NavSatStatus
from gps_common.msg import GPSFix

import adafruit_gps  # Uses pyserial UART

# --------------------------------------------------------------------------- #
# Hardware: auto-detect a CP210x USB-UART (VID:PID 10c4:ea60). Adjust if needed.
# --------------------------------------------------------------------------- #
def find_gps_port(vid=0x10C4, pid=0xEA60, baudrate=9600, timeout=10.0):
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        # rospy.loginfo(f"DEBUG: {p.device} VID={p.vid} PID={p.pid} {p.description}")
        if p.vid == vid and p.pid == pid:
            rospy.loginfo(f"[gps] GPS device found on {p.device}")
            return serial.Serial(p.device, baudrate=baudrate, timeout=timeout)
    rospy.logfatal("[gps] GPS device not found (VID:PID %04x:%04x)!" % (vid, pid))
    rospy.signal_shutdown("GPS device not found")
    raise rospy.ROSInterruptException("GPS device not found")

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def navsat_status_from_fix_quality(has_fix, fix_quality):
    """
    Map NMEA fix_quality (if provided) to NavSatStatus.
    NMEA (typical): 0=Invalid, 1=GPS(SPS), 2=DGPS/SBAS, 4=RTK fixed, 5=RTK float, etc.
    """
    if not has_fix:
        return NavSatStatus.STATUS_NO_FIX

    if fix_quality is None:
        return NavSatStatus.STATUS_FIX

    try:
        fq = int(fix_quality)
    except Exception:
        return NavSatStatus.STATUS_FIX

    if fq <= 0:
        return NavSatStatus.STATUS_NO_FIX
    elif fq == 1:
        return NavSatStatus.STATUS_FIX
    elif fq == 2:
        return NavSatStatus.STATUS_SBAS_FIX
    elif fq in (4, 5):  # RTK fixed/float → treat as GBAS for lack of a better bucket
        return NavSatStatus.STATUS_GBAS_FIX
    else:
        return NavSatStatus.STATUS_FIX

def covariance_from_hdop(hdop):
    """
    Return (sx2, sy2, sz2) variances (m^2) using the simple σ ≈ HDOP * UERE model.
    If HDOP missing, fall back to ~5 m horiz (1σ) and ~10 m vert (1σ).
    """
    if hdop is None:
        sigma_h = 5.0
    else:
        try:
            hdop = float(hdop)
        except Exception:
            hdop = 0.0
        if hdop <= 0.0:
            sigma_h = 5.0
        else:
            # UERE ~ 5 m for standalone civilian GPS under decent sky.
            sigma_h = max(hdop * 5.0, 3.0)  # clamp a bit; don't claim sub-meter
    sx2 = sigma_h ** 2
    sy2 = sigma_h ** 2
    sz2 = (2.0 * sigma_h) ** 2  # vertical ~ 2x worse
    return sx2, sy2, sz2

# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main():
    rospy.init_node("gps_talker")
    rate = rospy.Rate(5)  # process faster than 1 Hz updates so we don't miss lines

    # Publishers
    navsatfix_pub = rospy.Publisher("/sensors/gps/fix", NavSatFix, queue_size=10)
    common_pub    = rospy.Publisher("/sensors/gps/fix_common", GPSFix, queue_size=10)

    # Open serial & init GPS
    uart = find_gps_port()
    gps = adafruit_gps.GPS(uart, debug=False)  # NMEA over pyserial

    # NMEA sentence & rate configuration (PMTK)
    # Enable RMC + GGA (common minimum for position/time/quality)
    gps.send_command(b"PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
    # 1 Hz update rate
    gps.send_command(b"PMTK220,1000")

    last_log = time.monotonic()

    while not rospy.is_shutdown():
        gps.update()  # read and parse incoming NMEA

        # Log status once per second
        if time.monotonic() - last_log >= 1.0:
            last_log = time.monotonic()

            if not gps.has_fix:
                rospy.loginfo("[gps] Waiting for fix…")
                continue

            # Build NavSatFix
            now = rospy.Time.now()
            fix_msg = NavSatFix()
            fix_msg.header.stamp = now
            fix_msg.header.frame_id = "gps_link"  # ensure a static TF base_link->gps_link exists

            # Coordinates
            fix_msg.latitude  = getattr(gps, "latitude",  float("nan"))
            fix_msg.longitude = getattr(gps, "longitude", float("nan"))
            alt_m = getattr(gps, "altitude_m", None)
            fix_msg.altitude  = alt_m if alt_m is not None else float("nan")

            # Status
            fix_quality = getattr(gps, "fix_quality", None)
            fix_msg.status.status  = navsat_status_from_fix_quality(gps.has_fix, fix_quality)
            fix_msg.status.service = NavSatStatus.SERVICE_GPS  # we at least know it's GPS

            # Covariance
            hdop = getattr(gps, "horizontal_dilution", None)
            sx2, sy2, sz2 = covariance_from_hdop(hdop)
            fix_msg.position_covariance = [sx2, 0.0, 0.0,
                                           0.0, sy2, 0.0,
                                           0.0, 0.0, sz2]
            fix_msg.position_covariance_type = NavSatFix.COVARIANCE_TYPE_DIAGONAL_KNOWN

            # Publish NavSatFix
            navsatfix_pub.publish(fix_msg)

            # Optional: publish GPSFix (handy for Mapviz / debugging)
            fix_dbg = GPSFix()
            fix_dbg.header.stamp = now
            fix_dbg.header.frame_id = "gps_link"
            fix_dbg.latitude  = fix_msg.latitude
            fix_dbg.longitude = fix_msg.longitude
            fix_dbg.altitude  = fix_msg.altitude
            # If adafruit_gps exposes these, copy them:
            spd   = getattr(gps, "speed_knots", None)
            track = getattr(gps, "track_angle_deg", None)
            if spd is not None:
                try:
                    # GPSFix has 'speed' in m/s; knots→m/s = 0.514444
                    fix_dbg.speed = float(spd) * 0.514444
                except Exception:
                    pass
            if track is not None:
                try:
                    # GPSFix expects track in radians; deg→rad
                    import math
                    fix_dbg.track = math.radians(float(track))
                except Exception:
                    pass
            common_pub.publish(fix_dbg)

            # Console log (optional)
            rospy.loginfo("=" * 40)
            ts = getattr(gps, "timestamp_utc", None)
            if ts:
                rospy.loginfo(
                    "UTC: {}/{}/{} {:02}:{:02}:{:02}".format(
                        ts.tm_mon, ts.tm_mday, ts.tm_year, ts.tm_hour, ts.tm_min, ts.tm_sec
                    )
                )
            rospy.loginfo("Lat: {:.6f}  Lon: {:.6f}".format(fix_msg.latitude, fix_msg.longitude))
            if hdop is not None:
                rospy.loginfo("HDOP: {}".format(hdop))
            rospy.loginfo("Cov diag (m^2): [{:.1f}, {:.1f}, {:.1f}]".format(sx2, sy2, sz2))

        rate.sleep()

if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
