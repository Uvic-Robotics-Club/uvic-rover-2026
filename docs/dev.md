# Docker instructions

1.  Build the Docker image using a command like:
    ```bash
    docker build -t uvic_rover_image .
    ```

2.  Run the container interactively:

    ```bash
    docker run -v $(pwd):/catkin_ws/src/ ... my_image
    ```

    run this at the top of the repo. Mount the uvic_repo (pwd) into a catkin_ws/src (ros package)

3. Build packages

    Inside catkin_ws

    ```bash
    catkin_make
    source devel/setup.bash
    ```
