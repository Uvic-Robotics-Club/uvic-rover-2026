# ===========================================================================================================================================
# Section Guide:
# Section 1 (Basic Project Setup): Defines the project, sets required CMake and C++ standards, and includes global compiler options.
# Section 2 (ROS Dependencies): Lists all ROS dependencies needed by this package. Adjust these lists to include only what’s necessary.
# Section 3 (Setup Catkin): Finds catkin and sets up Python support (if there exists any Python scripts).
# Section 4 (Message Generation): Configures the generation of custom messages, if used.
# Section 5 (Declare Catkin Package): Exports this package’s dependency information so that other packages can depend on it.
# Section 6 (Include Directories): Defines include paths necessary for compiling ROS nodes.
# Section 7 (Executable or Library Targets): Optionally defines any C++ executables or libraries for any nodes not in Python.
# Section 8 (Installation): Sets up installation rules for Python scripts, launch files, etc.
# Section 9 (Additional Macros and Tests): Provides a placeholder for additional functionality that may be added in the future.
# ===========================================================================================================================================

# ------------------------------------------------------------------------------
# 1. Basic Project Setup
# ------------------------------------------------------------------------------
# Specify the minimum required version of CMake to use.
cmake_minimum_required(VERSION 3.16)
# Define the project name, version, and programming languages used.
project(uvic_rover VERSION 1.0.0 LANGUAGES CXX)
# Set the C++ standard to C++17 and enforce its usage.
# ------------------------------------------------------------------------------
# 1. Specify C++ standard and optional compiler warnings.
# ------------------------------------------------------------------------------
# Set the C++ standard to C++17 and enforce its usage.
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# Define compiler options that you may want applied to C++ compilations.
set(ROVER_CPP_COMPILE_OPTIONS -Wall -Wextra -Werror -pedantic)
# ------------------------------------------------------------------------------
# 2. ROS Dependencies and Package Settings
# ------------------------------------------------------------------------------
# List the ROS packages that THIS project depends on.
set(ROVER_PACKAGES
    roscpp                # For writing C++ nodes.
    rospy                 # For writing Python nodes if needed.
    std_msgs              # Provides standard message types.
    sensor_msgs           # Provides sensor message types (e.g., for IMU/GPS data).
    message_generation    # Needed only if you create custom messages.
)
# If you are using custom messages in your package, list the message files here.
set(ROVER_MESSAGE_FILES
    # Arm.msg
    # Speed.msg
)
# List the ROS packages that this package will export to OTHERS.
# This is used by catkin for dependency resolution. 
# (Other packages need these packages to use this package)
set(ROVER_CATKIN_PACKAGES
    roscpp
    rospy
    std_msgs
    message_runtime      # Required if using custom messages.
)
# ------------------------------------------------------------------------------
# 3. Find and Setup Catkin
# ------------------------------------------------------------------------------
# Find the catkin package along with the packages listed in ROVER_PACKAGES.
find_package(catkin REQUIRED COMPONENTS
    ${ROVER_PACKAGES}
)
# Ucomment only if you're writing Python code that should be imported like a library, e.g.: from uvic_rover.nav import gps_utils
# Note: requires a setup.py file to be preset.
# catkin_python_setup()
# ------------------------------------------------------------------------------
# 4. Message Generation (Optional)
# ------------------------------------------------------------------------------
# Add custom message files, if any.
# If you are not using custom messages, you can comment this section out.
add_message_files(
    FILES
    ${ROVER_MESSAGE_FILES}
)
# Generate the custom messages (if any) so that they can be used at runtime.
# List any dependencies that your messages have, typically standard messages.
generate_messages(
    DEPENDENCIES
    std_msgs
    sensor_msgs
)
# ------------------------------------------------------------------------------
# 5. Declare Catkin Package
# ------------------------------------------------------------------------------
# Export package information to other ROS packages.
# List catkin dependencies here so that downstream packages have access.
catkin_package(
    CATKIN_DEPENDS ${ROVER_CATKIN_PACKAGES}
)
# ------------------------------------------------------------------------------
# 6. Include Directories
# ------------------------------------------------------------------------------
# Specify include directories, typically those provided by catkin.
include_directories(
    ${catkin_INCLUDE_DIRS}
)
# ------------------------------------------------------------------------------
# 7. Executable or Library Targets (Optional)
# ------------------------------------------------------------------------------
# If you have C++ nodes, add them here.
# For example, if there was an IMU node implemented in C++:
# add_executable(imu_node src/nav/imu_node.cpp)
# target_link_libraries(imu_node ${catkin_LIBRARIES})
# add_dependencies(imu_node ${${PROJECT_NAME}_EXPORTED_TARGETS} ${catkin_EXPORTED_TARGETS})
# For now, IF YOUR NODES ARE PYTHON SCRIPTS, you do not need to define them here.
# ------------------------------------------------------------------------------
# 8. Installation
# ------------------------------------------------------------------------------
# Install any Python scripts.
# This makes them available as executable files when the package is built.
catkin_install_python(PROGRAMS
     nodes/odom/gps.py
     nodes/odom/imu.py
     DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
# Optionally, install your launch files so they can be run via roslaunch.
install(DIRECTORY launch/
        DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/launch
)
# ------------------------------------------------------------------------------
# 9. Additional Macros and Tests (Optional)
# ------------------------------------------------------------------------------
# Any additional macros (like for Gazebo plugins or tests) can be added here.
# These sections are not needed for basic sensor functionalities.
# For example, if you need to add tests later:
# if (COMMAND add_tests_macro)
#     add_tests_macro()
# endif ()
