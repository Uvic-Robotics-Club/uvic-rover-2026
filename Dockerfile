# Base image: Ubuntu 20.04
FROM ubuntu:20.04

# Avoid interactive prompts during apt installs
ARG DEBIAN_FRONTEND=noninteractive

# Set locale + timezone (For proper Ubuntu behavior)
RUN apt-get update && apt-get install -y locales tzdata \
    && locale-gen en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 \
    && ln -fs /usr/share/zoneinfo/UTC /etc/localtime \
    && dpkg-reconfigure --frontend noninteractive tzdata \
    && rm -rf /var/lib/apt/lists/*

# Install text editors
RUN apt-get update && apt-get install -y \
    nano \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
ARG USERNAME=ros
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd -s /bin/bash --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && mkdir /home/$USERNAME/.config && chown $USER_UID:$USER_GID /home/$USERNAME/.config

# Set up sudo
RUN apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL >> /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME \
    && rm -rf /var/lib/apt/lists/*

# Install basic tools
RUN apt-get update && apt-get install -y \
    curl git git-lfs python3-pip build-essential lsb-release gnupg2 \
    && rm -rf /var/lib/apt/lists/*

# Add the ROS Noetic package repository and key
RUN sh -c 'echo "deb http://packages.ros.org/ros/ubuntu $(lsb_release -sc) main" > /etc/apt/sources.list.d/ros-latest.list' \
    && curl -s https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc | apt-key add -

# Install ROS Noetic and catkin tools
RUN apt-get update && apt-get install -y \
    ros-noetic-desktop python3-catkin-tools python3-rosdep \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y \
    x11-apps mesa-utils libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Initialize rosdep
RUN rosdep init && rosdep update

# Set up environment variables for ROS
RUN echo "source /opt/ros/noetic/setup.bash" >> /root/.bashrc \
    && echo "source /opt/ros/noetic/setup.bash" >> /home/$USERNAME/.bashrc

# Switch to non-root user and setup workspace
USER $USERNAME
WORKDIR /catkin_ws
RUN mkdir -p src

# Default command
CMD ["/bin/bash"]