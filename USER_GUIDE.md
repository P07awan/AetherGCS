# AETHER GCS - User Guide & Operations Manual

Welcome to **AETHER GCS**, your advanced multi-drone Ground Control Station. This guide explains how to navigate the user interface, manage your fleet, execute basic flight commands, switch flight modes, and plan automated missions.

---

## 1. Interface Layout Overview

The AETHER GCS interface is built entirely around maximizing situational awareness and giving you absolute control over your fleet. The layout is highly customizable.

- **Top Toolbar**: Your primary command center for executing actions like Connect, Arm, Takeoff, Flight Mode Selection (LOITER, GUIDED, AUTO, STABILIZE, LAND, RTL), Land, Hold, RTL, and uploading missions.
- **Left Panel (Fleet Status)**: Lists all your configured drones. Shows connection status, active modes, level horizon toggle, and allows you to select single or multiple drones. 
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

### Selecting Drones: Individual vs Swarm Operations
AETHER GCS supports both **individual drone control** and **multi-drone swarm operations**:

#### 1. Individual Drone Mode (Separate Waypoints per Drone)
When you want **Drone 1** and **Drone 2** to fly different waypoint paths:
1. Click **`NONE`** in the top right of the Fleet panel to ensure no swarm checkboxes are selected.
2. Click on **Drone 1** in the Fleet list. Notice the Mission Planner header shows **`DRONE: Drone 1`**.
3. Draw waypoints on the map for Drone 1 and click **`Upload`** (transmits mission to Drone 1).
4. Click **`Clear`** in the Mission Planner tab.
5. Click on **Drone 2** in the Fleet list. Notice the Mission Planner header updates to **`DRONE: Drone 2`**.
6. Draw the unique waypoints for Drone 2 and click **`Upload`** (transmits mission to Drone 2).

#### 2. Swarm Batch Mode (Same Mission to Multiple Drones)
When you want multiple drones to execute the same flight path simultaneously:
1. Check the checkboxes next to the drones (or click **`ALL`** in the Fleet panel header).
2. Notice the Mission Planner header displays **`SWARM: X DRONES`**.
3. Click **`Upload`** → transmits the mission to all selected drones in a single batch.

---

## 3. Basic Flight Controls

> [!IMPORTANT]
> **Normal Flight Workflow — Each step is independent and must be explicitly user-triggered:**
> ```
> CONNECT → ARM → TAKEOFF → MODE SELECT / HOLD / MISSION → LAND → DISARM
> ```

Once your drones are connected and have a valid GPS lock, command them using the Top Toolbar buttons in order:

### Step 1 — ARM

Click **Arm (Green Radio Icon)** to arm the motors.

- The GCS sends a `MAV_CMD_COMPONENT_ARM_DISARM` command and waits for the flight controller's `COMMAND_ACK`.
- If the flight controller **accepts** the command, the heartbeat armed flag is verified and the UI shows `ARMED`.
- If the flight controller **rejects** the command (e.g. GPS/EKF/pre-arm check failure), the exact reason is shown:
  ```
  ARM FAILED: Command 400 rejected — PreArm: Need 3D Fix
  ```
- The ARM button is automatically disabled once the drone is armed.

> [!WARNING]
> **Propellers will spin immediately when armed.** Keep clear of the drone.

### Step 2 — Set Takeoff Altitude

Before clicking Takeoff, set your target altitude using the **altitude picker** (the `± / number input` widget next to the Takeoff button).

- Range: **1m – 120m** (GCS safety maximum).
- Default: **10m**.

### Step 3 — TAKEOFF

Click **Takeoff (Yellow Up Arrow)** to climb to the selected altitude.

- The drone **must be armed** before clicking Takeoff. If not, you will see:
  ```
  TAKEOFF BLOCKED — Drone is not armed. Click ARM first.
  ```
- The GCS sends `MAV_CMD_NAV_TAKEOFF` with your selected altitude and waits for `COMMAND_ACK`.
- After the command is accepted, the UI state shows `TAKING OFF`.
- When the drone reaches the target altitude, it automatically transitions to `AIRBORNE` state in `LOITER` mode.
- **The drone will never automatically land after reaching the target altitude.**

### Step 4 — Flight Mode Selector & Hold

- **Flight Mode Dropdown**: Click the mode pill (e.g. `● LOITER`) in the Top Toolbar to pick any flight mode directly:
  - **Manual**: `STABILIZE`, `ALT_HOLD`, `POSHOLD`
  - **GCS Commanded**: `GUIDED`, `LOITER`
  - **Autonomous**: `AUTO`
  - **Navigation**: `LAND`, `RTL`
- **Hold (Hand Icon)**: Instantly switches the drone to `LOITER` mode to hover in place.
- **Manual Control**: Select the Manual Control tab at the bottom to fly using virtual joysticks.
- **Mission**: Upload and start an autonomous waypoint mission (see Section 5).

### Step 5 — LAND

Click **Land (Down Arrow)** to descend and land at the current GPS location.

- The LAND button is enabled whenever the drone is armed and airborne.
- LAND is completely independent — it is **never called automatically** by any other button.
- The drone descends to the ground and disarms automatically per flight controller settings (`LANDING` → `DISARMED`).

### Step 6 — DISARM

Click **Disarm (White Radio Icon)** after landing to confirm the motors are disarmed.

- The GCS verifies the heartbeat armed flag is `false` after sending the command.
- If the drone auto-disarms upon touchdown, the GCS automatically catches the update and shows `DISARMED`.

> [!WARNING]
> **Disarming in the air will cause the drone to fall.** Always land first, then disarm.

> [!NOTE]
> **Mission Note:** Uploading a mission does NOT automatically arm or start flight. After uploading, you must:
> 1. Click **ARM** → drone arms
> 2. Click **Start Mission** → mission begins (switches to `AUTO`)

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
> You can toggle the artificial horizon card directly in the Left Sidebar (Fleet status header) to visualize the drone's physical tilt in real-time.

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

> **Looking to test before flying real hardware?** See the complete **[Manual Testing Guide](MANUAL_TESTING_GUIDE.md)** for a 12-step verification walkthrough using the built-in simulator.

*Fly safely and always adhere to local aviation regulations when using AETHER GCS outdoors.*
