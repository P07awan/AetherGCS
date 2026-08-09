# AETHER GCS - User Guide & Operations Manual

Welcome to **AETHER GCS**, your advanced multi-drone Ground Control Station. This guide explains how to navigate the user interface, manage your fleet, execute basic flight commands, and plan automated missions.

---

## 1. Interface Layout Overview

The AETHER GCS interface is built entirely around maximizing situational awareness and giving you absolute control over your fleet. The layout is highly customizable.

- **Top Toolbar**: Your primary command center for executing actions like Connect, Arm, Takeoff, RTL, and uploading missions.
- **Left Panel (Fleet Status)**: Lists all your configured drones. Shows connection status, active modes, and allows you to select single or multiple drones. 
- **Center Panel (Map & Mission Planner)**: 
  - **The Map** tracks real-time GPS locations of all connected drones and displays your drawn mission paths.
  - **Mission Planner (Bottom)** allows you to draw paths, create survey grids, and inspect the command log.
- **Right Panel (Telemetry)**: Displays highly detailed real-time sensor data for the currently active drone (Battery, GPS count, Altitude, Heading, Groundspeed).

> [!TIP]
> **Customizing Your Layout:** 
> The layout features a **VS Code-style resizable panel system**. Simply click and drag the dark divider lines between panels to resize them. You can minimize the sidebars down to an ultra-thin strip or expand the mission planner up to your preference. Double-click any drag handle to instantly reset that panel to its default size.

---

## 2. Managing Your Fleet

### Adding & Connecting Drones
1. Click the cyan **Add (+)** button in the Top Toolbar.
2. Select your connection type (Serial, UDP, TCP, Simulator).
3. If connecting a physical flight controller (like Pixhawk, MiniPix, or a Telemetry Radio) via USB:
   - Go to the **SERIAL (USB/RADIO)** tab.
   - Click **Scan Ports**.
   - Your device should appear as a clickable button below (e.g., `COM9` or `ttyUSB0`). Click it to auto-fill the path.
4. Select the drone in the Fleet List (Left Panel).
5. Click **Connect (Power Icon)** in the Top Toolbar. The status indicator will turn green once a heartbeat is established.

### Selecting Drones for Commands
AETHER GCS supports swarming and multi-drone commands. 
- Click on any drone in the left panel to select it.
- Hold `Ctrl` (or `Cmd`) while clicking to select multiple drones.
- Click the **[ ]** (Select All) button to issue commands to the entire fleet simultaneously.
- Any flight command issued from the Top Toolbar will be sent to **ALL** currently selected drones.

---

## 3. Basic Flight Controls

Once your drones are connected and have a valid GPS lock, you can command them using the Top Toolbar.

1. **Arm (Blue Radio Icon)**: Arms the motors. *Warning: Propellers will spin.*
2. **Takeoff (Yellow Up Arrow)**: Commands the drone to takeoff to a default altitude (20m). 
3. **Hold (Hand Icon)**: Instantly pauses the drone's current movement and commands it to loiter/hover in place.
4. **Land (Down Arrow)**: Commands the drone to descend and land at its current GPS location.
5. **RTL (Home Icon)**: Return To Launch. The drone will ascend to a safe altitude and return to its original takeoff location.
6. **Disarm (White Radio Icon)**: Disarms the motors. *Only use this when the drone is safely on the ground, or in an extreme emergency.*

> [!WARNING]
> **Emergency Kills:** Disarming while a drone is in the air will cause it to drop out of the sky. Always use **Hold** or **RTL** for mid-air aborts.

---

## 4. Telemetry and Flight Status

To view detailed telemetry, click on a single drone in the Left Panel to make it the "Active" drone.

The **Right Panel** will populate with real-time data streams:
- **Battery & GPS**: Monitor voltage levels and satellite lock count.
- **Attitude**: Roll, Pitch, and Yaw degrees.
- **Velocity**: Groundspeed (m/s) and Vertical Speed (m/s).
- **Altitude**: Relative altitude (from takeoff) and Absolute ASL.

> [!NOTE]
> **Artificial Horizon (Level Card):**
> You can click the **Level (Yellow Sliders)** button in the Top Toolbar to pop open an artificial horizon card directly in the Left Sidebar to visualize the drone's physical tilt in real-time.

---

## 5. Mission Planning (Automated Flights)

You can program automated GPS waypoint missions using the bottom **Mission Planner** panel.

### Creating a Mission
1. In the bottom panel, navigate to the **Mission** tab.
2. Click anywhere on the center map to drop a new waypoint. 
3. Adjust the altitude and parameters for each waypoint in the Mission tab list.

### Survey Grids
1. Click the **Grid (Survey)** button in the Top Toolbar.
2. Draw a polygon on the map outlining the area you want to map or scan.
3. The software will automatically generate a back-and-forth "lawnmower" flight path to cover the area.

### Executing the Mission
1. With your mission drawn, select the target drones in the Fleet List.
2. Click **Upload (Arrow Up)** in the Top Toolbar to transmit the mission to the drone's autopilot hardware.
3. Click **Start Mission (Play Button)** to switch the drone into AUTO mode and begin the flight path.
4. You can monitor the progress in the **Command Log** tab.

---

## 6. Manual Control (Virtual Joysticks)

If you prefer to fly the drone manually (similar to a Mode 2 RC Transmitter), AETHER GCS provides a high-performance virtual joystick interface.

1. Ensure your drone is **Armed** and in the air (using Takeoff or manually flying).
2. Look at the **Bottom Panel** and click the **Manual Control** tab.
3. You will see two virtual joysticks:
   - **Left Stick:** Controls Altitude (Up/Down) and Yaw rotation (Left/Right).
   - **Right Stick:** Controls Pitch (Forward/Backward) and Roll (Left/Right).
4. **Custom Speeds:** You can adjust the maximum velocity limits (`XY MAX` and `Z MAX`) at the top of the panel. The values are in meters per second (m/s).
5. Click and drag the sticks. The moment you release your mouse, the sticks snap back to the center and the drone is commanded to immediately stop and hold position.

---

*Fly safely and always adhere to local aviation regulations when using AETHER GCS outdoors.*
