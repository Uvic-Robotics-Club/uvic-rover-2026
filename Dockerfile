# Use the official ROS Noetic base image (Ubuntu 20.04)
FROM ros:noetic-ros-base

LABEL maintainer="UVicRobotics <uvic.robotics@gmail.com>"

# Prevent interactive prompts during apt installations
ENV DEBIAN_FRONTEND=noninteractive

# Install essential tools and ROS dependencies listed in package.xml and CMakeLists.txt
# git is needed for rosdep to potentially fetch sources
# python3-pip might be needed for Python script dependencies not handled by rosdep
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    python3-pip \
    ros-noetic-gps-common \
    ros-noetic-robot-localization \
    # Clean up apt cache to reduce image size
    && rm -rf /var/lib/apt/lists/*

# Create the catkin workspace directory
RUN mkdir -p /catkin_ws/src
WORKDIR /catkin_ws

# Copy the entire ROS package source code into the workspace's src directory
# Assumes the Dockerfile is located at the root of your uvic_rover package directory
COPY . src/uvic_rover/

RUN rosdep update

# Install dependencies listed in package.xml for all packages in the src directory
# --from-paths specifies where to find package.xml files
# --ignore-src prevents reinstalling packages already present in the src directory
# -r continues even if some dependencies fail (useful in CI, but check logs)
# -y confirms installations automatically
RUN rosdep install --from-paths src --ignore-src -r -y

# Build the catkin workspace
# Source the main ROS setup file before running catkin_make
RUN /bin/bash -c "source /opt/ros/noetic/setup.bash && catkin_make"

CMD ["/bin/bash", "-c", "source /catkin_ws/devel/setup.bash && bash"]

