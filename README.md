<![CDATA[<div align="center">

# ✈️ AetherGCS

**Professional Ground Control Station for Autonomous Drone Fleets**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19.0-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![MAVLink](https://img.shields.io/badge/MAVLink-v2-FF6600?style=flat)](https://mavlink.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*Real-time telemetry · Multi-drone fleet management · Mission planning · Built-in simulator*

</div>

---

## Overview

AetherGCS is a full-stack Ground Control Station application for managing autonomous drone fleets. It supports real hardware connections via **MAVLink** (ArduPilot / PX4) over Serial, UDP, or TCP, as well as a **built-in physics-lite simulator** requiring no external hardware.

The UI is a premium dark-mode dashboard with live telemetry, an interactive map, a mission planner with waypoint editing, a Primary Flight Display (PFD/HUD), and a command log — all updating at **10 Hz** over WebSocket.

---

## Features

### Fleet Management
- Add unlimited drones (real or simulated) simultaneously
- Connection types: **Serial/USB**, **UDP**, **TCP**, **Built-in Simulator**
- Auto-reconnect on connection drop with configurable retry logic
- Per-drone status indicators: `connecting` / `connected` / `error` / `disconnected`
- Persistent drone registry via **MongoDB** (gracefully falls back to in-memory if unavailable)

### Live Telemetry (10 Hz)

| Category | Metrics |
|---|---|
| Flight State | Armed/Disarmed, Flight Mode, Firmware, Heartbeat |
| Position | Latitude, Longitude, Altitude MSL, Altitude Relative, Flight Trail |
| GNSS | GPS Fix Type, Satellite Count, HDOP |
| Attitude | Pitch, Roll, Heading/Yaw |
| Speed | Ground Speed, Air Speed |
| Battery | Voltage, Current, State of Charge % |
| Status | STATUSTEXT messages from flight controller |

### Flight Commands

| Command | Description |
|---|---|
| `arm` / `disarm` | Motor arm/disarm |
| `takeoff` | Set GUIDED mode → arm → NAV_TAKEOFF |
| `land` | MAV_CMD_NAV_LAND |
| `rtl` | Return to Launch |
| `hold` | LOITER mode |
| `emergency_stop` | Force-disarm in flight (safety override) |
| `set_mode` | Change flight mode |
| `goto` | Fly to GPS coordinate |
| `set_velocity` | Body-frame velocity (forward/right/up + yaw rate) |
| `upload_mission` | Upload waypoint list via MAVLink Mission Protocol |
| `start_mission` | Switch to AUTO + MAV_CMD_MISSION_START |
| `pause_mission` | Switch to LOITER |
| `resume_mission` | Switch back to AUTO |
| `stop_mission` | Switch to LOITER |
| `clear_mission` | MISSION_CLEAR_ALL |
| `level_horizon` | MAV_CMD_PREFLIGHT_CALIBRATION (accelerometer level) |

### Mission Planner
- Click-to-place waypoints on map
- Waypoint table with lat/lon/altitude/action/hold editing
- **Survey Grid Generator** — automatic lawnmower mapping grid with configurable area, lane spacing, and rotation angle
- Mission library with save / load / duplicate / delete / import / export JSON
- Upload mission to single or multiple drones simultaneously

### Map
- Leaflet-based interactive map with satellite and street tile layers
- Live drone position markers with real-time heading vectors
- Color-coded flight path trails (up to 500 points per drone)
- Waypoint markers with sequence numbers
- RTL home position marker
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
    │       ├── TopToolbar.js            # Command buttons (Arm, Takeoff, etc.)
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
| Yarn | 1.22+ | Package manager (`npm install -g yarn`) |
| MongoDB | 6.0+ | **Optional** — falls back to in-memory |

> **MongoDB is optional.** AetherGCS works fully without it; drones and missions will not persist across server restarts.

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
yarn install
```

Create `frontend/.env`:

```ini
REACT_APP_BACKEND_URL=http://localhost:8000
WDS_SOCKET_PORT=443
ENABLE_HEALTH_CHECK=false
```

Start the frontend dev server:

```bash
yarn start
# App opens at http://localhost:3000
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `DB_NAME` | `test_database` | MongoDB database name |
| `CORS_ORIGINS` | `*` | Allowed origins (comma-separated). Set to your frontend URL in production, e.g. `http://localhost:3000`. Wildcard `*` disables cookie/credential sharing per CORS spec. |

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
  "command": "takeoff",
  "params": { "altitude": 20.0 }
}
```

### Missions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/missions` | List all saved missions |
| `POST` | `/missions` | Create a new mission |
| `GET` | `/missions/{id}` | Get a mission by ID |
| `PUT` | `/missions/{id}` | Update a mission |
| `DELETE` | `/missions/{id}` | Delete a mission |
| `POST` | `/missions/{id}/duplicate` | Duplicate a mission |

### System

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/system/serial-ports` | List available serial/COM ports on the host |

### WebSocket

```
ws://localhost:8000/api/ws/telemetry
```

The server pushes JSON events at up to **10 Hz**:

| Event `type` | Payload | Description |
|------------|---------|-------------|
| `snapshot` | `Drone[]` | Full fleet state on initial connect |
| `drone` | `Drone` | Single drone state update (telemetry / status change) |
| `drone_removed` | `{ "id": "..." }` | Drone was deleted from fleet |
| `command_log` | `CommandLog` | A command was executed |

---

## Connecting a Real Drone

### Serial / USB (Pixhawk, APM, SiK Telemetry Radio)

1. Click **+ Add Drone** in the top toolbar
2. Select the **Serial (USB/Radio)** tab
3. Click **Scan Ports** — detected system COM ports are listed automatically
4. Select your port and baud rate:
   | Hardware | Baud Rate |
   |----------|-----------|
   | Pixhawk native USB | 115200 |
   | APM/Pixhawk USB | 57600 |
   | SiK Telemetry Radio | 57600 |
5. Set drone name and home position, then click **Connect Drone**

### UDP (SITL, Mission Planner forwarding)

```
Host: 127.0.0.1    Port: 14550
```

### TCP (SITL)

```
Host: 127.0.0.1    Port: 5760
```

### Built-in Simulator

Select the **Simulator** tab — no hardware required. The drone spawns at the configured home coordinates and responds to all flight commands with realistic physics.

---

## Mission Planner Usage

1. **Add waypoints** — click the map (in *Add WP* mode from toolbar) or press **+ WP** in the Mission Planner panel
2. **Edit waypoints** — modify latitude, longitude, altitude, action type, and hold time directly in the table
3. **Generate a survey grid** — click the grid icon and configure area dimensions (width × length), lane spacing, and grid rotation angle for automated mapping missions
4. **Upload** — click **Upload** to send the mission to selected drone(s) via the MAVLink Mission Protocol
5. **Execute** — click **Start** to switch the drone to AUTO mode
6. **Save/load** — missions are persisted to MongoDB and can be exported as `.mission.json` files

---

## MAVLink Messages Decoded

| MAVLink Message | Telemetry Fields Populated |
|----------------|---------------------------|
| `HEARTBEAT` | `armed`, `flight_mode`, `firmware`, `heartbeat` |
| `GLOBAL_POSITION_INT` | `latitude`, `longitude`, `altitude_msl`, `altitude_relative` ★ |
| `GPS_RAW_INT` | `gps_fix`, `satellites`, `hdop` |
| `GPS2_RAW` | `satellites` (fallback), `gps_fix` (fallback) |
| `VFR_HUD` | `ground_speed`, `air_speed`, `heading`, `altitude_msl` |
| `ATTITUDE` | `pitch`, `roll`, `heading` |
| `BATTERY_STATUS` | `battery_voltage`, `battery_current`, `battery_percent` |
| `SYS_STATUS` | `battery_voltage` (fallback) |
| `HOME_POSITION` | `home_lat`, `home_lon`, `home_alt` |
| `STATUSTEXT` | Status messages in command log |

> ★ **Altitude note:** `altitude_relative` comes exclusively from `GLOBAL_POSITION_INT.relative_alt` — the autopilot's own home-referenced altitude. It reads **0 m at the home/arm position**, increases as the drone ascends, and decreases on descent. It is never overridden by MSL calculations.

---

## Development

### Backend tests

```bash
cd backend
pytest
```

### Backend code quality

```bash
black .          # Format
isort .          # Import order
flake8 .         # Lint
mypy .           # Type check
```

### Production build (frontend)

```bash
cd frontend
yarn build
```

---

## Technology Stack

### Backend

| Library | Version | Purpose |
|---------|---------|---------|
| **FastAPI** | 0.110 | REST API + WebSocket server |
| **uvicorn** | 0.25 | ASGI runtime |
| **pymavlink** | ≥2.4.40 | MAVLink v2 protocol (Serial/UDP/TCP) |
| **pyserial** | ≥3.5 | Serial port enumeration |
| **motor** | 3.3 | Async MongoDB driver |
| **pydantic** | ≥2.6 | Data validation + models |
| **python-dotenv** | ≥1.0 | Environment config loading |

### Frontend

| Library | Version | Purpose |
|---------|---------|---------|
| **React** | 19.0 | UI framework |
| **Zustand** | ≥5.0 | Global state management |
| **Leaflet + react-leaflet** | 1.9 / 5.0 | Interactive drone map |
| **Axios** | 1.18 | REST API HTTP client |
| **Framer Motion** | 11.18 | UI animations |
| **Radix UI** | Various | Accessible UI primitives |
| **Tailwind CSS** | 3.4 | Utility-first styling |
| **Recharts** | 3.6 | Data visualization |
| **Sonner** | 2.0 | Toast notifications |
| **Lucide React** | 0.516 | Icon set |

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built for drone operators who need reliability, speed, and control.

</div>
]]>
