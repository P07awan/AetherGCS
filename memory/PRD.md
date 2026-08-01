# Multi-Drone Ground Control Station (GCS) — PRD

## Problem Statement
Build a production-quality, modular Multi-Drone GCS to connect, monitor, control and plan missions for multiple drones simultaneously. Clean Architecture with per-drone async workers, WebSocket telemetry, Leaflet map, waypoint planner, mission library. Future: swarm, AI, video, ROS2 (architecture-ready).

## Architecture
UI (React + Zustand + Leaflet) → REST/WS (FastAPI) → DroneManager → DroneWorker (1 per drone) → simulator/MAVSDK backend

## Backend (`/app/backend`)
- `server.py` — FastAPI app, REST + WebSocket broadcaster
- `gcs/models.py` — Drone, Telemetry, Waypoint, Mission, CommandLog
- `gcs/drone_manager.py` — orchestrator, persistence, command routing
- `gcs/drone_worker.py` — per-drone async worker (5 Hz simulator loop, physics-lite)
- `gcs/mission_manager.py` — mission CRUD (Mongo)
- `gcs/command_log.py` — append-only history

## Frontend (`/app/frontend`)
- `pages/GCSPage.js` — main layout
- `components/{TopToolbar,DroneListSidebar,DroneMap,TelemetryPanel,MissionPlanner,CommandHistory,StatusBar,AddDroneDialog,MissionLibraryDialog}.js`
- `store/gcsStore.js` — Zustand global state
- `services/{api,telemetrySocket}.js`

## Features implemented (2026-02-01)
- Multi-drone add/remove/connect/disconnect (UDP/TCP/Serial/Simulator profiles)
- Independent DroneWorker per drone with 5 Hz simulated telemetry
- Live WebSocket broadcast to any number of clients
- Commands: arm, disarm, takeoff, land, hold, RTL, emergency_stop, velocity, mission ops
- Multi-select drone control (checkbox / select all / deselect all)
- Interactive Leaflet map (dark CARTO tiles) with drone marker + heading, home diamond, flight trail
- Click-to-add / drag / delete / reorder / edit waypoints
- Mission library (create/load/save/duplicate/delete/export/import JSON, MongoDB persistence)
- Command history log with status pills, response time, timestamps
- Live telemetry panel (battery %, voltage, current, GPS fix, lat/lon, altitude, speed, heading, satellites, flight time, heartbeat)
- Status bar (WS status, fleet counts, low-battery warning, UTC time)
- Auto-reconnect WebSocket, safety color coding (green/blue/amber/red/orange)

## Deferred (P1/P2)
- Real MAVSDK/MAVLink connectivity (architecture stub in place)
- Live camera streaming, AI object detection, swarm control
- Tauri desktop packaging
- Geofence editor, plugin marketplace, cloud sync
