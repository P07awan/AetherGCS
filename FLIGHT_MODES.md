# AetherGCS — Flight Mode Switching Guide

This guide explains how to switch between the key ArduCopter/ArduPilot flight modes using **AetherGCS**: STABILIZE, ALT_HOLD, POSHOLD, GUIDED, LOITER, AUTO, LAND, and RTL.

---

## Quick Reference

| Mode | What it does | When to use |
|------|-------------|-------------|
| **STABILIZE** | Self-levelling manual control — throttle/pitch/roll via joystick | First flights, manual flying, troubleshooting |
| **ALT_HOLD** | Maintains altitude automatically; manual pitch/roll | Controlled altitude flying without GPS |
| **POSHOLD** | Holds position and altitude; manual override when joystick moved | Intuitive manual flight with GPS braking |
| **GUIDED** | FC accepts waypoint / velocity commands from GCS | Takeoff, programmatic positioning, custom paths |
| **LOITER** | Holds GPS position and altitude automatically | Pause in place, inspect surroundings, standby |
| **AUTO** | Flies a pre-uploaded waypoint mission autonomously | Automated survey, delivery, inspection routes |
| **LAND** | Descends and lands vertically at current GPS position | End of flight, emergency set-down |
| **RTL** | Returns to launch point and lands | Low battery, lost link recovery |

---

## Method 1 — Top Toolbar Mode Selector Dropdown (Recommended)

The top toolbar features an integrated **Flight Mode Selector** dropdown pill button (positioned right next to the `STATE` badge).

```
┌─────────────────────────────────────────────────────────────┐
│  AETHER GCS   [+ ADD] [CONNECT] ... STATE: ARMED  [● LOITER ▾]│
└─────────────────────────────────────────────────────────────┘
                                                       │
                                   ┌───────────────────┴───────────────────┐
                                   │ ─ Manual ───────────────────────────  │
                                   │   ● STABILIZE                         │
                                   │   ● ALT_HOLD                          │
                                   │   ● POSHOLD                           │
                                   │ ─ GCS Commanded ────────────────────  │
                                   │   ● GUIDED                            │
                                   │   ● LOITER                 [ACTIVE]   │
                                   │ ─ Autonomous ───────────────────────  │
                                   │   ● AUTO                              │
                                   │ ─ Navigation ───────────────────────  │
                                   │   ● LAND                              │
                                   │   ● RTL                               │
                                   └───────────────────────────────────────┘
```

### Steps:
1. Ensure your drone is connected.
2. Click the **Flight Mode Selector** button (e.g. `● LOITER ▾`) in the Top Toolbar.
3. Select any flight mode from the grouped list:
   - **Manual**: `STABILIZE`, `ALT_HOLD`, `POSHOLD`
   - **GCS Commanded**: `GUIDED`, `LOITER`
   - **Autonomous**: `AUTO`
   - **Navigation**: `LAND`, `RTL`
4. AetherGCS immediately sends the `set_mode` command to all selected drones and displays a confirmation toast notification.

---

## Method 2 — Toolbar Flight Action Buttons

The Top Toolbar also has dedicated action buttons that execute automatic mode transitions as part of a flight flow:

| Button | Mode it switches to | Notes |
|--------|---------------------|-------|
| **Takeoff** | `GUIDED` (auto) | Always switches to GUIDED before takeoff command |
| **Hold** (Hand icon) | `LOITER` | Stops movement and holds position |
| **RTL** (Home icon) | `RTL` | Returns to home and lands |
| **Land** (Arrow Down) | `LAND` | Descends at current position |
| **Start Mission** (Cyan Play) | `AUTO` | Switches to AUTO and begins the uploaded mission |

### Example — Switch to LOITER (Hold) via toolbar button:
```
1. Drone is AIRBORNE in any mode
2. Click the Hold button (hand icon) in the top toolbar
3. Drone switches to LOITER → holds GPS position and altitude
4. Flight Mode Selector pill updates to: ● LOITER
```

---

## Method 3 — Browser Developer Console (Direct API Call)

You can switch to any mode programmatically using the AetherGCS REST API directly from the browser console.

### Open the Console
Press `F12` → **Console** tab.

### Paste this helper function once per session:
```javascript
async function setMode(droneId, mode) {
  const res = await fetch('/api/commands', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      drone_ids: [droneId],
      command: 'set_mode',
      params: { mode: mode }
    })
  });
  const data = await res.json().catch(() => res.text());
  console.log(`Mode → ${mode}:`, res.status, data);
}
```

### Switch modes (replace `"YOUR_DRONE_ID"` with your drone ID):
```javascript
// STABILIZE — manual self-levelling
await setMode("YOUR_DRONE_ID", "STABILIZE")

// GUIDED — GCS-commanded flight
await setMode("YOUR_DRONE_ID", "GUIDED")

// LOITER — GPS position hold
await setMode("YOUR_DRONE_ID", "LOITER")

// AUTO — fly uploaded mission
await setMode("YOUR_DRONE_ID", "AUTO")

// LAND — descend and land now
await setMode("YOUR_DRONE_ID", "LAND")
```

---

## Method 4 — cURL / External Script

If calling from a terminal or script outside the browser:

```bash
DRONE_ID="sim-1"
SERVER="http://localhost:8000"

# STABILIZE
curl -s -X POST "$SERVER/api/commands" \
  -H "Content-Type: application/json" \
  -d "{\"drone_ids\":[\"$DRONE_ID\"],\"command\":\"set_mode\",\"params\":{\"mode\":\"STABILIZE\"}}"

# GUIDED
curl -s -X POST "$SERVER/api/commands" \
  -H "Content-Type: application/json" \
  -d "{\"drone_ids\":[\"$DRONE_ID\"],\"command\":\"set_mode\",\"params\":{\"mode\":\"GUIDED\"}}"

# LOITER
curl -s -X POST "$SERVER/api/commands" \
  -H "Content-Type: application/json" \
  -d "{\"drone_ids\":[\"$DRONE_ID\"],\"command\":\"set_mode\",\"params\":{\"mode\":\"LOITER\"}}"

# AUTO
curl -s -X POST "$SERVER/api/commands" \
  -H "Content-Type: application/json" \
  -d "{\"drone_ids\":[\"$DRONE_ID\"],\"command\":\"set_mode\",\"params\":{\"mode\":\"AUTO\"}}"

# LAND
curl -s -X POST "$SERVER/api/commands" \
  -H "Content-Type: application/json" \
  -d "{\"drone_ids\":[\"$DRONE_ID\"],\"command\":\"set_mode\",\"params\":{\"mode\":\"LAND\"}}"
```

---

## Mode-by-Mode Instructions

---

### STABILIZE

**What it does:**
The flight controller self-levels the drone (prevents flipping) but you control
throttle, roll, pitch, and yaw manually via the joystick. There is no altitude hold
or GPS position lock. The drone drifts with the wind.

**When to use:**
- First time flying a new drone
- Testing motor/ESC response
- Manual aerobatic flying
- When GPS is unavailable

**How to switch:**
1. Click the **Flight Mode Selector** pill in the Top Toolbar.
2. Under **Manual**, click `STABILIZE`.

---

### GUIDED

**What it does:**
The flight controller accepts external position, velocity, and altitude commands
from the GCS. AetherGCS switches to GUIDED automatically when you click **Takeoff**
or send velocity commands via the joystick tab.

**When to use:**
- Before takeoff (AetherGCS does this automatically)
- Sending velocity commands via the Manual Control joystick
- Programmatic waypoint navigation via API

**How to switch:**
1. Click the **Flight Mode Selector** pill in the Top Toolbar.
2. Under **GCS Commanded**, click `GUIDED`.

---

### LOITER (GPS Position Hold)

**What it does:**
The drone uses GPS and barometer to hold its current position and altitude
precisely. No joystick input required. The drone fights wind drift automatically.

**When to use:**
- Pausing during a flight to take photos
- Holding position while you plan the next move
- Waiting for a human to clear the landing zone
- After aborting a mission

**How to switch:**
1. Click the **Flight Mode Selector** pill in the Top Toolbar.
2. Under **GCS Commanded**, click `LOITER` (or click the **Hold** button).

---

### AUTO (Autonomous Mission)

**What it does:**
The drone follows a pre-uploaded sequence of GPS waypoints automatically.
Speed, altitude, and hold time at each waypoint is defined in the mission plan.

**Prerequisites before switching to AUTO:**
1. A mission must be uploaded (click **Upload** in the toolbar first)
2. The drone must be **armed**
3. GPS fix must be valid (>= 6 satellites, HDOP < 2.0)

**How to switch:**
1. Click **Upload** to transmit the mission to the drone.
2. Click **ARM** to arm the motors.
3. Click **Start Mission** in the Top Toolbar (or select `AUTO` from the Flight Mode Selector).

---

### LAND

**What it does:**
The drone descends vertically at its current GPS position until it touches down,
then the flight controller disarms the motors automatically.

**When to use:**
- End of flight
- When RTL is not desirable (e.g. drone is already at the right place)
- Emergency set-down

**How to switch:**
1. Click **Land** button in the Top Toolbar (or select `LAND` from the Flight Mode Selector).
2. The UI state updates to `LANDING` and transitions to `DISARMED` upon touchdown.

---

## Supported Mode Name Strings

| String | ArduCopter Mode | Category | Notes |
|--------|----------------|----------|-------|
| `STABILIZE` | Stabilize | Manual | Self-levelling, manual throttle |
| `ALT_HOLD` | AltHold | Manual | Altitude hold, manual pitch/roll |
| `POSHOLD` | PosHold | Manual | Position hold with manual joystick override |
| `GUIDED` | Guided | GCS Commanded | GCS positioning & velocity control |
| `LOITER` | Loiter | GCS Commanded | GPS position + altitude hold |
| `AUTO` | Auto | Autonomous | Autonomous waypoint mission |
| `LAND` | Land | Navigation | Vertical descent & landing |
| `RTL` | Return to Launch | Navigation | Return to home & land |

> [!TIP]
> Mode names are **case-insensitive** in AetherGCS — `"loiter"`, `"LOITER"`, and `"Loiter"` all work.

---

*For general GCS operation, see [USER_GUIDE.md](./USER_GUIDE.md).*
