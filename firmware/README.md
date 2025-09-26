# firmware/

This folder contains all embedded‐firmware code for microcontrollers (Arduino sketches and related headers), organized by subsystem and purpose.

## Contents

- **`production/`**  
  Contains the stable, “flashable” Arduino sketch(s) you use in normal operation.  
- **`calibration/`**  
  Contains one‐off or occasional tools—e.g. calibration routines—that you run to generate parameters (biases, scales), but don’t deploy in production.

> **Tip:** Once you’ve completed calibration and recorded your offset values, you should be able to archive or remove the entire `calibration/` folder without affecting runtime firmware.  