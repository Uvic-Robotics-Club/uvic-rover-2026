#########################################################
# Development Image
#########################################################

# Base image: Ubuntu 20.04
FROM osrf/ros:noetic-desktop-full AS dev

LABEL maintainer="UVic Robotics <uvic.robotics@gmail.com>"
# Avoid interactive prompts during apt installs
ARG DEBIAN_FRONTEND=noninteractive

# Basic dev tools
RUN apt-get update && apt-get install -y \
    nano vim curl git git-lfs python3-pip build-essential \
    lsb-release gnupg2 sudo \
    x11-apps mesa-utils libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies for ROS nodes (pip requirements)
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements.txt


# Create a non-root user
ARG USERNAME=ros
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd -s /bin/bash --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && mkdir /home/$USERNAME/.config && chown $USER_UID:$USER_GID /home/$USERNAME/.config \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL >> /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Allow non-root user to access serial devices like /dev/ttyACM0
RUN usermod -aG dialout,plugdev $USERNAME

# Set up environment variables for ROS
RUN echo "source /opt/ros/noetic/setup.bash" >> /root/.bashrc \
    && echo "source /opt/ros/noetic/setup.bash" >> /home/$USERNAME/.bashrc

# Switch to non-root user and setup workspace
USER $USERNAME
WORKDIR /catkin_ws
RUN mkdir -p src

# Default command
CMD ["/bin/bash"]

#########################################################
# CI/CD Image
#########################################################
FROM ros:noetic-ros-base AS ci

LABEL maintainer="UVicRobotics <uvic.robotics@gmail.com>"
# Prevent interactive prompts during apt installations
ENV DEBIAN_FRONTEND=noninteractive

# Install minimal tools + runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git python3-pip \
    ros-noetic-gps-common \
    ros-noetic-robot-localization \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies for ROS nodes (pip requirements)
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements.txt

# Create the catkin workspace directory
RUN mkdir -p /catkin_ws/src
WORKDIR /catkin_ws

# Copy source code
COPY . src/uvic_rover/

# Install dependencies listed in package.xml for all packages in the src 
RUN rosdep update && \
    rosdep install --from-paths src --ignore-src -r -y

# Build the catkin workspace
RUN /bin/bash -c "source /opt/ros/noetic/setup.bash && catkin_make"

CMD ["/bin/bash", "-c", "source /catkin_ws/devel/setup.bash && bash"]