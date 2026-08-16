# AetherGCS — Complete Manual Testing Guide

This guide provides a step-by-step walkthrough to test **every feature** of AetherGCS using the **Built-in Simulator** and **ArduPilot SITL** before flying real drone hardware.

---

## Testing Overview

You do **not** need a physical drone or radio telemetry to test AetherGCS. The software includes a physics-lite simulator that runs directly in the backend and allows you to test:
- Telemetry streaming & Primary Flight Display (HUD)
- Flight state transitions (`DISARMED` → `ARMING` → `ARMED` → `TAKING OFF` → `AIRBORNE` → `LANDING` → `DISARMED`)
- All flight modes (`STABILIZE`, `ALT_HOLD`, `POSHOLD`, `GUIDED`, `LOITER`, `AUTO`, `LAND`, `RTL`)
- Manual virtual joystick controls
- Waypoint mission planning, survey grid generation, upload, and autonomous mission flight
- Multi-drone fleet swarming
- Emergency safety overrides (`E-STOP`)

---

## Phase 1 — Built-In Simulator Testing (Zero Hardware Required)

### Step 1: Launch AetherGCS
1. Ensure the backend server is running (`uvicorn server:app --reload` at `http://localhost:8000`).
2. Ensure the frontend server is running (`npm start` at `http://localhost:3000`).
3. Open your browser to `http://localhost:3000`.

---

### Step 2: Add & Connect a Simulated Drone
1. In the top toolbar, click the cyan **+ Add** button.
2. In the dialog, select the **SIMULATOR** tab.
3. Configure the test parameters:
   - **Name:** `SIM-ALPHA`
   - **Home Latitude:** `37.7749` (or click on the map to set location)
   - **Home Longitude:** `-122.4194`
4. Click **Add Drone**.
5. In the left **Fleet Panel**, click on `SIM-ALPHA` to select it.
6. Click **Connect (Power Icon)** in the top toolbar.

**Expected Result:**
- The status dot turns **green** (`CONNECTED`).
- The **STATE** badge in the toolbar displays `DISARMED`.
- The map centers on the drone location with a cyan drone marker.
- The right Telemetry Panel populates with live 10 Hz telemetry:
  - Satellite Count: `14+` (Fix: `3D`)
  - Battery: `100%` (16.8 V)
  - Altitude: `0.0 m`
  - Groundspeed: `0.0 m/s`

---

### Step 3: Test Telemetry Panel & HUD
1. Look at the right **Telemetry Panel**:
   - Verify Roll, Pitch, Heading numbers update.
   - Verify GPS HDOP is around `1.2`.
2. Look at the **Left Fleet Panel**:
   - Click the **Level (Sliders Icon)** button in the header to open the Artificial Horizon card.
   - Observe the horizon pitch ladder and roll indicator matching drone telemetry.

---

### Step 4: Test Motor Arming (`ARM`)
1. Click the **ARM (Green Radio Icon)** button in the top toolbar.
2. Observe the state transition sequence:
   - Button turns yellow/pulsing: `ARMING`
   - Command acknowledged by flight controller backend
   - State turns solid green: `ARMED`
3. Look at the top toolbar:
   - The **ARM** button is now disabled (greyed out).
   - The **DISARM** button is now enabled.
   - The **Takeoff** control becomes enabled.

---

### Step 5: Test Takeoff & Altitude Selection
1. Locate the **altitude stepper** input next to the Takeoff button in the top toolbar.
2. Set target altitude to **15 meters** (use `+` / `-` buttons or type `15`).
3. Click the **Takeoff (Yellow Up Arrow)** button.
4. Observe the flight behavior:
   - Toolbar state updates to `TAKING OFF` (pulsing yellow).
   - In the right Telemetry Panel, watch **Relative Altitude** climb steadily (`1.0 m` → `5.0 m` → `12.0 m` → `15.0 m`).
   - Groundspeed remains near `0.0 m/s` (vertical climb only).
   - When `15.0 m` is reached, state automatically updates to **`AIRBORNE`** in cyan.
   - Mode automatically updates to **`LOITER`** (green dot).
   - The drone **holds altitude** at 15 meters and does not land automatically.

---

### Step 6: Test Flight Mode Selector
1. In the top toolbar, click the **Flight Mode Selector** pill button (currently showing `● LOITER ▾`).
2. Test switching to different modes:
   - Click **STABILIZE** (under Manual) → mode pill changes to `● STABILIZE` (grey dot).
   - Click **POSHOLD** (under Manual) → mode pill changes to `● POSHOLD`.
   - Click **GUIDED** (under GCS Commanded) → mode pill changes to `● GUIDED` (amber dot).
   - Click **LOITER** (under GCS Commanded) → mode pill changes to `● LOITER` (green dot).
3. Test toolbar action buttons:
   - Click the **Hold (Hand Icon)** button → mode instantly switches to `LOITER`.

---

### Step 7: Test Manual Joystick Control
1. In the bottom panel, click the **Manual Control** tab.
2. Set speed limits:
   - **XY MAX:** `5.0 m/s`
   - **Z MAX:** `2.0 m/s`
3. Click and drag the **Right Joystick** (Pitch / Roll):
   - Push forward → drone moves North on the map.
   - Watch groundspeed increase on the right Telemetry Panel (`0.0` → `4.5 m/s`).
   - Watch the flight trail line follow the drone movement on the map.
4. Release the joystick:
   - The joystick snaps back to center.
   - Groundspeed drops back to `0.0 m/s`.
   - Drone holds GPS position in place.

---

### Step 8: Test Mission Planner & Survey Grid

#### Part A — Manual Waypoint Flight
1. In the bottom panel, click the **Mission Planner** tab.
2. Click anywhere on the map to add **Waypoint 1** (e.g. 50 meters north of drone).
3. Click another location to add **Waypoint 2** and **Waypoint 3**.
4. In the waypoint table:
   - Set Altitude to `20 m` for all waypoints.
   - Set Speed to `5 m/s`.
5. Click **Upload (Up Arrow Icon)** in the Mission Planner panel.
   - Observe toast: `Mission uploaded to 1 drone(s)`.
6. Click **Start (Cyan Play Icon)**:
   - Flight mode changes to **`AUTO`** (cyan dot).
   - State badge changes to **`MISSION ACTIVE`** (pulsing cyan).
   - Drone begins moving along the mission path from Waypoint 1 → 2 → 3.
7. Click **Pause (Pause Icon)**:
   - Drone stops moving immediately.
   - Mode changes to `LOITER`.
8. Click **Start** again to resume the mission.
9. When the last waypoint is reached, the drone automatically switches to `LOITER` and holds position.

#### Part B — Automated Survey Grid (Lawnmower Pattern)
1. Click **Clear** in the Mission Planner tab to reset waypoints.
2. Click **Survey Grid (Grid Icon)** in the top toolbar.
3. Set grid parameters:
   - Lane Spacing: `10 m`
   - Flight Altitude: `25 m`
   - Speed: `6 m/s`
4. Click **Generate Grid**.
5. Observe the automated lawnmower search grid generated on the map.
6. Click **Upload** → **Start** to test autonomous survey execution.

---

### Step 9: Test Landing & Auto-Disarm (`LAND`)
1. With the drone airborne, click **Land (Arrow Down Icon)** in the top toolbar.
2. Observe the landing sequence:
   - Toolbar state updates to **`LANDING`** (pulsing orange).
   - Mode pill updates to `● LAND`.
   - In the Telemetry Panel, watch **Relative Altitude** decrease (`15.0 m` → `8.0 m` → `2.0 m` → `0.0 m`).
3. Upon touchdown (`0.0 m`):
   - Motor disarms automatically.
   - Toolbar state updates to **`DISARMED`**.
   - Mode pill updates to `● STABILIZE`.
   - **Takeoff** button is disabled until re-armed.

---

### Step 10: Test Multi-Drone Operations & Individual Waypoints
1. Click **+ Add** → add a second simulated drone (`SIM-BRAVO`) at home location `37.7755, -122.4180`.
2. Connect `SIM-BRAVO`.
3. **Test Individual Waypoint Assignment:**
   - Click **`NONE`** in the top right of the Fleet panel to uncheck all swarm checkboxes.
   - Click on `SIM-ALPHA` row in the Fleet list. Notice the Mission Planner target badge shows **`DRONE: SIM-ALPHA`**.
   - Drop 2 waypoints on the map → click **`Upload`** → observe mission uploaded **only to SIM-ALPHA**.
   - Click **`Clear`** in Mission Planner.
   - Click on `SIM-BRAVO` row in the Fleet list. Notice Mission Planner target badge updates to **`DRONE: SIM-BRAVO`**.
   - Drop 2 different waypoints for `SIM-BRAVO` → click **`Upload`** → observe mission uploaded **only to SIM-BRAVO**.
4. **Test Swarm Fleet Commands & Batch Upload:**
   - Click **`ALL`** in the Fleet panel header so both `SIM-ALPHA` and `SIM-BRAVO` checkboxes are selected. Notice target badge displays **`SWARM: 2 DRONES`**.
   - Issue fleet commands from the top toolbar: click **ARM** → both drones arm simultaneously → set Altitude `20 m` → click **Takeoff** → both drones climb in parallel to 20 meters → click **Land** → both drones descend and land together.

---

### Step 11: Test Emergency Safety Override (`E-STOP`)
1. Arm a drone and click **Takeoff** so it is airborne at `15 m`.
2. Click the red **E-STOP (Shield Icon)** button in the top toolbar.
3. Confirm emergency stop.
4. **Expected Result:** Motors force-disarm instantly (`armed: false`), demonstrating emergency safety override capability.

---

## Phase 2 — ArduPilot SITL Testing (Optional Advanced MAVLink Protocol Validation)

If you want to test exact MAVLink protocol packet handling with the real ArduPilot flight controller stack running in simulation:

### Prerequisites
- Install [ArduPilot SITL](https://ardupilot.org/dev/docs/sitl-simulator-software-in-the-loop.html) or Mission Planner SITL.

### Running SITL
Run ArduCopter SITL in your terminal:
```bash
sim_vehicle.py -v ArduCopter --console --map
```
SITL forwards MAVLink packets on UDP port `14550` or TCP port `5760`.

### Connecting in AetherGCS
1. In AetherGCS, click **+ Add** → select **UDP** tab.
2. Address: `127.0.0.1`, Port: `14550`.
3. Click **Add Drone** → select drone → click **Connect**.
4. Test ARM, TAKEOFF, MODE SELECT, MISSION UPLOAD, LAND on the real ArduPilot firmware simulation.
5. Test pre-arm checks: Try arming SITL before GPS 3D fix is acquired — verify AetherGCS displays the exact pre-arm rejection message (e.g. `ARM FAILED: PreArm: Need 3D Fix`).

---

## Manual Verification Checklist

| Test Item | Feature | Pass Criteria | Status |
|:---|:---|:---|:---:|
| **1** | Add Simulator Drone | Drone appears in fleet list with correct home lat/lon | [ ] |
| **2** | Connect & Telemetry | Status turns green, 10 Hz telemetry fields populate | [ ] |
| **3** | PFD / Horizon Card | Horizon ladder tilts with attitude updates | [ ] |
| **4** | Motor Arming | State turns `ARMED`, ARM button disables, DISARM enables | [ ] |
| **5** | Takeoff Execution | Climbs to selected altitude (e.g. 15m), state turns `AIRBORNE`, holds position | [ ] |
| **6** | Mode Selector | Dropdown switches mode between STABILIZE, GUIDED, LOITER, AUTO, LAND, RTL | [ ] |
| **7** | Virtual Joysticks | Manual pitch/roll/yaw/altitude response, instant zero-throttle stop on release | [ ] |
| **8** | Mission Planner | Drop waypoints, edit alt/speed, upload mission, execute AUTO flight | [ ] |
| **9** | Survey Grid | Lawnmower pattern generates cleanly, uploads and executes | [ ] |
| **10** | Landing Sequence | `LAND` descends vertically to `0.0m` and auto-disarms | [ ] |
| **11** | Multi-Drone Fleet | Swarm selection executes multi-drone ARM/TAKEOFF/LAND simultaneously | [ ] |
| **12** | Emergency Stop | `E-STOP` forces instant motor disarm | [ ] |

---

*Once all items in this checklist pass using the simulator, your GCS setup is fully verified and ready for real drone operations.*
