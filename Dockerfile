#########################################################
# Development Image
#########################################################

# Full ROS Noetic desktop image on Ubuntu 20.04.
# Used for local development, including GUI tools like RViz/rqt.
FROM osrf/ros:noetic-desktop-full AS dev

LABEL maintainer="UVic Robotics <uvic.robotics@gmail.com>"

# Avoid interactive prompts during apt installs.
ARG DEBIAN_FRONTEND=noninteractive

# Basic dev tools + ROS development dependencies
#
# nano: simple terminal text editor.
# vim: more powerful terminal text editor.
# curl: downloads files/data from URLs.
# git: version control for the repo.
# git-lfs: handles large files tracked through Git LFS.
# python3-pip: installs Python packages from requirements.txt.
# build-essential: provides compilers and build tools like gcc, g++, and make.
# lsb-release: lets scripts check Ubuntu/Linux distribution info.
# gnupg2: manages package signing keys for apt repositories.
# sudo: allows the non-root dev user to run admin commands.
# iproute2: provides `ip`, useful for debugging WSL/Docker networking and display routing.
# x11-apps: provides GUI test tools like `xeyes`.
# mesa-utils: provides OpenGL test/debug tools like `glxinfo` and `glxgears`.
# libgl1-mesa-glx: provides OpenGL libraries needed by GUI tools such as RViz.
# iputils-ping: provides `ping` for checking container-to-container and host network reachability.
# netcat-openbsd: provides `nc` for TCP/UDP port connectivity tests and basic container networking debugging.
# ros-noetic-gps-common: provides GPS-related ROS message types/utilities.
# ros-noetic-robot-localization: provides EKF/UKF localization and navsat_transform_node.
RUN apt-get update && apt-get install -y \
    nano \
    vim \
    curl \
    git \
    git-lfs \
    python3-pip \
    build-essential \
    lsb-release \
    gnupg2 \
    sudo \
    iproute2 \
    x11-apps \
    mesa-utils \
    libgl1-mesa-glx \
    iputils-ping \
    netcat-openbsd \
    ros-noetic-gps-common \
    ros-noetic-robot-localization \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies used by ROS Python nodes.
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements.txt

# Create a non-root user for normal development.
# This avoids editing/building everything as root inside the container.
ARG USERNAME=ros
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd -s /bin/bash --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && mkdir /home/$USERNAME/.config \
    && chown $USER_UID:$USER_GID /home/$USERNAME/.config \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL >> /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Add the dev user to hardware-access groups.
# dialout: allows access to serial devices like /dev/ttyUSB0 and /dev/ttyACM0.
# plugdev: commonly used for removable/plugged-in device permissions.
RUN usermod -aG dialout,plugdev $USERNAME

# Configure every new terminal for ROS development.
# This sources ROS Noetic, sources the Catkin workspace when it exists,
# sets safe localhost defaults for ROS networking, and wraps catkin_make
# so a successful build is immediately sourced in the current terminal.
RUN echo "source /opt/ros/noetic/setup.bash" >> /root/.bashrc \
    && { \
        echo ""; \
        echo "# ROS auto-setup"; \
        echo "if [ -f /opt/ros/noetic/setup.bash ]; then"; \
        echo "  source /opt/ros/noetic/setup.bash"; \
        echo "fi"; \
        echo ""; \
        echo "if [ -f /catkin_ws/devel/setup.bash ]; then"; \
        echo "  source /catkin_ws/devel/setup.bash"; \
        echo "fi"; \
        echo ""; \
        echo "export ROS_MASTER_URI=\"\${ROS_MASTER_URI:-http://localhost:11311}\""; \
        echo "export ROS_HOSTNAME=\"\${ROS_HOSTNAME:-localhost}\""; \
        echo ""; \
        echo "# Wrapper: after catkin_make succeeds, source the workspace in this terminal"; \
        echo "catkin_make() {"; \
        echo "  command catkin_make \"\$@\""; \
        echo "  local status=\$?"; \
        echo "  if [ \$status -eq 0 ] && [ -f /catkin_ws/devel/setup.bash ]; then"; \
        echo "    source /catkin_ws/devel/setup.bash"; \
        echo "  fi"; \
        echo "  return \$status"; \
        echo "}"; \
    } >> /home/$USERNAME/.bashrc

# Switch to the non-root development user and create the Catkin workspace.
RUN mkdir -p /catkin_ws/src \
    && chown -R $USERNAME:$USERNAME /catkin_ws

USER $USERNAME
WORKDIR /catkin_ws

# Start an interactive shell by default.
CMD ["/bin/bash"]

#########################################################
# CI/CD Image
#########################################################

# Smaller ROS base image used for automated builds.
# This stage intentionally excludes GUI/editor/debug tools from the dev image.
FROM ros:noetic-ros-base AS ci

LABEL maintainer="UVic Robotics <uvic.robotics@gmail.com>"

# Avoid interactive prompts during apt installs.
ENV DEBIAN_FRONTEND=noninteractive

# Install only the tools and ROS dependencies needed to build/test in CI.
# --no-install-recommends keeps the CI image smaller by avoiding optional packages.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    python3-pip \
    ros-noetic-gps-common \
    ros-noetic-robot-localization \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies used by ROS Python nodes.
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements.txt

# Create the Catkin workspace directory.
RUN mkdir -p /catkin_ws/src
WORKDIR /catkin_ws

# Copy the repository into the CI workspace.
COPY . src/uvic_rover/

# Install ROS package dependencies declared in package.xml files.
RUN rosdep update && \
    rosdep install --from-paths src --ignore-src -r -y

# Build the Catkin workspace.
RUN /bin/bash -c "source /opt/ros/noetic/setup.bash && catkin_make"

CMD ["/bin/bash", "-c", "source /catkin_ws/devel/setup.bash && bash"]

#########################################################
# Pi Image
#########################################################

# Minimal ROS Noetic base image for Raspberry Pi 4B (arm64).
# Used exclusively for CAN/arm control on the rover.
# No GUI tools — this runs headless.
FROM ros:noetic-ros-base AS pi

LABEL maintainer="UVic Robotics <uvic.robotics@gmail.com>"

ENV DEBIAN_FRONTEND=noninteractive

# Install only what's needed for CAN communication and arm control.
#
# can-utils: provides candump, cansend, cangen for CAN bus interaction.
# python3-pip: installs Python packages from requirements.txt.
# build-essential: compilers and build tools for catkin_make.
# iproute2: provides `ip` for CAN interface management (ip link set can0 up).
# iputils-ping: provides `ping` for debugging network connectivity to Jetson.
# netcat-openbsd: provides `nc` for checking ROS master reachability.
# ros-noetic-rospy: Python ROS client library for writing nodes.
# ros-noetic-std-msgs: standard ROS message types.
# ros-noetic-sensor-msgs: sensor-related ROS message types.
RUN apt-get update && apt-get install -y --no-install-recommends \
    can-utils \
    python3-pip \
    build-essential \
    iproute2 \
    iputils-ping \
    netcat-openbsd \
    ros-noetic-rospy \
    ros-noetic-std-msgs \
    ros-noetic-sensor-msgs \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies.
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements.txt

# Create the Catkin workspace.
RUN mkdir -p /catkin_ws/src
WORKDIR /catkin_ws

# Copy the package into the workspace.
COPY . src/uvic_rover/

# Install ROS package dependencies from package.xml.
RUN rosdep update && \
    rosdep install --from-paths src --ignore-src -r -y

# Build the workspace.
RUN /bin/bash -c "source /opt/ros/noetic/setup.bash && catkin_make"

# Source ROS and the workspace on every terminal session.
RUN echo "source /opt/ros/noetic/setup.bash" >> /root/.bashrc \
    && echo "source /catkin_ws/devel/setup.bash" >> /root/.bashrc

# Start a shell with the workspace sourced.
# Make sure to start roscore and the pi.launch file
CMD ["/bin/bash", "-c", "source /catkin_ws/devel/setup.bash && roslaunch uvic_rover arm_control.launch"]
