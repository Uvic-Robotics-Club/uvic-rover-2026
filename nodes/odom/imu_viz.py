#!/usr/bin/env python3
# imu_viz: Lightweight ROS node to visualize IMU orientation.
# - Subscribes: /sensors/imu/data (sensor_msgs/Imu)
# - Publishes:  /imu/pose (geometry_msgs/PoseStamped) for RViz pose display
# - Broadcasts: TF from <fixed_frame> → <child_frame> using IMU quaternion
# - Params: ~fixed_frame (default: "world"), ~child_frame (default: "imu_link")
# Use this to see live IMU axes and orientation in RViz without affecting the localization stack.

import rospy
from sensor_msgs.msg import Imu
from geometry_msgs.msg import PoseStamped, TransformStamped
import tf2_ros

def main():
    rospy.init_node("imu_viz")

    fixed_frame = rospy.get_param("~fixed_frame", "world")  # set to map/odom if you prefer
    child_frame = rospy.get_param("~child_frame", "imu_link")
    pose_pub = rospy.Publisher("/imu/pose", PoseStamped, queue_size=10)
    tf_broadcaster = tf2_ros.TransformBroadcaster()

    def cb(msg: Imu):
        # 1) Pose view
        pose = PoseStamped()
        pose.header.stamp = rospy.Time.now()
        pose.header.frame_id = fixed_frame
        pose.pose.position.x = 0.0
        pose.pose.position.y = 0.0
        pose.pose.position.z = 0.0
        pose.pose.orientation = msg.orientation  # (w,x,y,z) already
        pose_pub.publish(pose)

        # 2) TF axes
        tfm = TransformStamped()
        tfm.header.stamp = pose.header.stamp
        tfm.header.frame_id = fixed_frame
        tfm.child_frame_id = child_frame
        tfm.transform.translation.x = 0.0
        tfm.transform.translation.y = 0.0
        tfm.transform.translation.z = 0.0
        tfm.transform.rotation = msg.orientation
        tf_broadcaster.sendTransform(tfm)

    rospy.Subscriber("/sensors/imu/data", Imu, cb, queue_size=10)
    rospy.loginfo("imu_viz: publishing /imu/pose and TF (world->imu_link)")
    rospy.spin()

if __name__ == "__main__":
    main()
