<div align="center">

# ✈️ AetherGCS

**Professional Ground Control Station for Autonomous Drone Fleets**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19.0-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![MAVLink](https://img.shields.io/badge/MAVLink-v2-FF6600?style=flat)](https://mavlink.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*Real-time telemetry · Multi-drone fleet management · Mission planning · Flight mode selector · Built-in simulator*

</div>

---

## Overview

AetherGCS is a full-stack Ground Control Station application for managing autonomous drone fleets. It supports real hardware connections via **MAVLink** (ArduPilot / PX4) over Serial, UDP, or TCP, as well as a **built-in physics-lite simulator** requiring no external hardware.

The UI is a premium dark-mode dashboard with live telemetry, an interactive map, a mission planner with waypoint editing, an integrated Flight Mode Selector dropdown, a Primary Flight Display (PFD/HUD), and a command log — all updating at **10 Hz** over WebSocket.

---

## Features

### Fleet Management
- Add unlimited drones (real or simulated) simultaneously
- Connection types: **Serial/USB**, **UDP**, **TCP**, **Built-in Simulator**
- Auto-reconnect on connection drop with configurable retry logic
- Per-drone status indicators: `connecting` / `connected` / `error` / `disconnected`
- Canonical telemetry state machine (`DISARMED`, `ARMING`, `ARMED`, `TAKING_OFF`, `AIRBORNE`, `LANDING`, `MISSION_ACTIVE`)
- Persistent drone registry via **MongoDB** (gracefully falls back to in-memory if unavailable)

### Live Telemetry (10 Hz)

| Category | Metrics |
|---|---|
| Flight State | Armed/Disarmed, Flight State, Flight Mode, Firmware, Heartbeat |
| Position | Latitude, Longitude, Altitude MSL, Altitude Relative, Flight Trail |
| GNSS | GPS Fix Type, Satellite Count, HDOP |
| Attitude | Pitch, Roll, Heading/Yaw |
| Speed | Ground Speed, Air Speed |
| Battery | Voltage, Current, State of Charge % |
| Status | STATUSTEXT messages from flight controller |

### Flight Commands & Mode Selector

| Command | Description |
|---|---|
| `arm` / `disarm` | Motor arm/disarm (with COMMAND_ACK verification & reason display) |
| `takeoff` | GUIDED takeoff with altitude picker (1m – 120m) |
| `land` | Descend & land vertically at current position |
| `rtl` | Return to Launch & land |
| `hold` | Switch to LOITER mode to hover in place |
| `set_mode` | Switch flight mode (`STABILIZE`, `ALT_HOLD`, `POSHOLD`, `GUIDED`, `LOITER`, `AUTO`, `LAND`, `RTL`) |
| `emergency_stop` | Force-disarm in flight (safety override) |
| `set_velocity` | Body-frame velocity (forward/right/up + yaw rate) |
| `upload_mission` | Upload waypoint list via MAVLink Mission Protocol |
| `start_mission` | Switch to AUTO + MAV_CMD_MISSION_START |
| `pause_mission` | Switch to LOITER |
| `resume_mission` | Switch back to AUTO |
| `stop_mission` | Switch to LOITER |
| `clear_mission` | MISSION_CLEAR_ALL |
| `level_horizon` | MAV_CMD_PREFLIGHT_CALIBRATION (accelerometer level) |

### Manual Control (Virtual Joysticks)
AETHER GCS features a built-in virtual joystick interface for manual flight control, allowing you to fly the drone directly from the dashboard:
- Dual on-screen joysticks mimicking a Mode 2 RC transmitter.
- **Left Stick:** Controls Altitude (Up/Down) and Yaw rotation (Left/Right).
- **Right Stick:** Controls Pitch (Forward/Backward) and Roll (Left/Right).
- Configurable maximum velocity limits for XY (horizontal) and Z (vertical) speeds in m/s.
- Instant stop and hold position when sticks are released.

### Mission Planner
- Click-to-place waypoints on map
- Waypoint table with lat/lon/altitude/action/hold editing
- **Survey Grid Generator** — automatic lawnmower mapping grid with configurable area, lane spacing, and rotation angle
- Mission library with save / load / duplicate / delete / import / export JSON
- Upload mission to single or multiple drones simultaneously

### Map & Deep Zoom
- **Mission Planner Aerial Maps** — Google Hybrid, Google Satellite, Esri World Imagery (HD), Google Streets, CartoDB Dark, and OpenStreetMap
- **Ultra-Deep Zooming (Level 23)** — enables sub-meter resolution for precise waypoint placement and alignment around buildings, fields, and structures
- **Quick Precision Zoom (21x)** — 1-click shortcut button to instantly zoom right in to 21x magnification on active drone or mission
- Live drone position markers with real-time heading vectors & target direction vectors
- Color-coded flight path trails (up to 500 points per drone)
- Draggable waypoint markers with sequence numbers
- Real-time zoom level indicator (`ZOOM: 21x (PRECISE)`) and map status readout
- One-click "fly here" by clicking the map

### Primary Flight Display (HUD)
- Artificial horizon with pitch ladder (±30°)
- Compass tape ribbon with cardinal directions
- Speed tape (airspeed + groundspeed)
- Altitude tape (relative to home — 0 m at takeoff, positive going up)
- ARM/DISARM status banner
- Battery, GPS, and Level Horizon quick-action

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          AetherGCS                              │
│                                                                 │
│  Frontend (React 19 + Tailwind + Leaflet)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │DroneList │  │ DroneMap │  │ Mission  │  │ TelemetryPanel│  │
│  │ Sidebar  │  │ (Leaflet)│  │ Planner  │  │ (19 live fields│  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────┘  │
│        │              │              │               │          │
│        └──────────────┴──────────────┴───────────────┘         │
│                          Zustand (gcsStore)                     │
│                                │                                │
│               WebSocket /api/ws/telemetry (10 Hz)               │
│                                │                                │
│  Backend (FastAPI + uvicorn)   │                                │
│  ┌─────────────────────────────┴────────────────────────┐      │
│  │                      Broadcaster                      │      │
│  │     (asyncio Queue → all connected WS clients)        │      │
│  └─────────────────────────────┬────────────────────────┘      │
│                                │                                │
│  ┌─────────────────────────────┴────────────────────────┐      │
│  │                    DroneManager                       │      │
│  │     (dict of DroneWorker instances + MongoDB)         │      │
│  └──────────┬─────────────────────────────┬─────────────┘      │
│             │                             │                     │
│  ┌──────────┴──────────┐       ┌──────────┴──────────┐         │
│  │  SimulatorWorker    │       │   MavlinkWorker      │         │
│  │  (physics-lite)     │       │   (pymavlink)        │         │
│  └─────────────────────┘       └──────────┬──────────┘         │
│                                           │ Serial / UDP / TCP  │
│                               ┌───────────┴──────────┐         │
│                               │  ArduPilot / PX4 FC  │         │
│                               │  (Real or SITL)      │         │
│                               └──────────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

### Key Files

```
AetherGCS/
├── FLIGHT_MODES.md             # Complete Flight Mode switching guide
├── USER_GUIDE.md               # Operational User Guide
├── backend/
│   ├── server.py               # FastAPI app — REST API + WebSocket broadcaster
│   ├── requirements.txt        # Python dependencies
│   ├── .env                    # Backend environment variables
│   └── gcs/
│       ├── drone_worker.py     # SimulatorWorker + MavlinkWorker (core flight logic)
│       ├── drone_manager.py    # Fleet orchestration + MongoDB persistence
│       ├── mission_manager.py  # Mission CRUD (MongoDB-backed)
│       ├── models.py           # Pydantic data models
│       └── db.py               # MongoDB async client (motor)
└── frontend/
    ├── src/
    │   ├── pages/GCSPage.js          # Root layout + WebSocket setup
    │   ├── store/gcsStore.js         # Zustand global state
    │   ├── services/
    │   │   ├── api.js                # Axios REST client
    │   │   └── telemetrySocket.js    # WebSocket lifecycle + reconnect
    │   ├── hooks/
    │   │   └── useUserGeolocation.js # Browser GPS → store
    │   └── components/
    │       ├── DroneListSidebar.js      # Fleet panel + level select
    │       ├── TopToolbar.js            # Command buttons + Flight Mode Selector
    │       ├── DroneMap.js              # Leaflet map + markers + trails
    │       ├── MissionPlanner.js        # Waypoint table + upload/start/pause
    │       ├── MissionPlannerHUD.js     # Primary Flight Display (HUD)
    │       ├── TelemetryPanel.js        # 19-field live telemetry readout
    │       ├── MissionLibraryDialog.js  # Save/load/import/export missions
    │       ├── SurveyGridDialog.js      # Lawnmower mapping grid generator
    │       ├── AddDroneDialog.js        # Connect drone wizard
    │       ├── CommandHistory.js        # Command audit log
    │       └── StatusBar.js             # Bottom connection status
    ├── package.json
    └── .env
```

---

## Prerequisites

| Tool | Minimum Version | Notes |
|------|----------------|-------|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend build |
| Yarn / NPM | 1.22+ / 9+ | Package manager |
| MongoDB | 6.0+ | **Optional** — falls back to in-memory |

---

## Quick Start

### 1 — Clone the repository

```bash
git clone https://github.com/your-username/AetherGCS.git
cd AetherGCS
```

### 2 — Backend setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

Create `backend/.env`:

```ini
MONGO_URL="mongodb://localhost:27017"
DB_NAME="aethergcs"
CORS_ORIGINS="*"
```

Start the backend server:

```bash
uvicorn server:app --reload
```

- API: `http://localhost:8000`
- Interactive API docs: `http://localhost:8000/docs`

### 3 — Frontend setup

```bash
cd frontend
npm install
```

Create `frontend/.env`:

```ini
REACT_APP_BACKEND_URL=http://localhost:8000
WDS_SOCKET_PORT=443
ENABLE_HEALTH_CHECK=false
```

Start the frontend dev server:

```bash
npm start
# App opens at http://localhost:3000
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `DB_NAME` | `aethergcs` | MongoDB database name |
| `CORS_ORIGINS` | `*` | Allowed origins (comma-separated). Set to your frontend URL in production, e.g. `http://localhost:3000`. |

### Frontend (`frontend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `REACT_APP_BACKEND_URL` | `http://localhost:8000` | Backend API base URL |
| `WDS_SOCKET_PORT` | `443` | Webpack dev server WS port |
| `ENABLE_HEALTH_CHECK` | `false` | Enable periodic backend health pings |

---

## REST API Reference

Base URL: `http://localhost:8000/api`

Full interactive docs: `http://localhost:8000/docs`

### Drones

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/drones` | List all registered drones |
| `POST` | `/drones` | Register a new drone |
| `DELETE` | `/drones/{id}` | Remove a drone |
| `POST` | `/drones/{id}/connect` | Connect to a drone |
| `POST` | `/drones/{id}/disconnect` | Disconnect from a drone |

### Commands

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/commands` | Send a command to one or more drones |
| `GET` | `/history` | Retrieve command history |
| `DELETE` | `/history` | Clear command history |

**Command payload example:**
```json
{
  "drone_ids": ["<uuid>"],
  "command": "set_mode",
  "params": { "mode": "LOITER" }
}
```

---

## Documentation Links

- **[Operational User Guide](USER_GUIDE.md)**: Detailed step-by-step instructions for operating the GCS.
- **[Flight Modes Guide](FLIGHT_MODES.md)**: Comprehensive reference for STABILIZE, GUIDED, LOITER, AUTO, LAND, and RTL flight modes.
- **[Manual Testing Guide](MANUAL_TESTING_GUIDE.md)**: Complete step-by-step testing guide using the simulator and SITL before flying real hardware.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
