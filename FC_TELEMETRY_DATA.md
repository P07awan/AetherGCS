# Flight Controller Telemetry Data Reference (Aether GCS)

This document lists all **19 telemetry data metrics** received across **9 MAVLink message types** from the Flight Controller (ArduPilot / PX4) into Aether GCS.

---

## Telemetry Summary Count

- **Total MAVLink Message Types Received:** 9
- **Total Mapped Telemetry Fields:** 19
- **Update Rate:** 10 Hz (10 times per second)

---

## Complete List of Data Coming from the Flight Controller

### 1. System & Flight State (MAVLink: `HEARTBEAT`)
| Field | Type | Description / Units | Example |
| :--- | :--- | :--- | :--- |
| `armed` | `Boolean` | Motors armed or disarmed state | `true` / `false` |
| `flight_mode` | `String` | Current flight mode | `"LOITER"`, `"STABILIZE"`, `"RTL"`, `"AUTO"` |
| `firmware` | `String` | Autopilot type detected | `"ArduPilot (live)"` / `"PX4 (live)"` |
| `heartbeat` | `Boolean` | Active link indicator | `true` |
| `heartbeat_ts` | `String` | ISO timestamp of last packet | `"2026-08-05T09:40:00Z"` |

### 2. Position & Altitude (MAVLink: `GLOBAL_POSITION_INT`)
| Field | Type | Description / Units | Example |
| :--- | :--- | :--- | :--- |
| `latitude` | `Float` | WGS84 latitude in degrees | `12.971598` |
| `longitude` | `Float` | WGS84 longitude in degrees | `77.594562` |
| `altitude_msl` | `Float` | Altitude above Mean Sea Level (meters) | `920.5m` |
| `altitude_relative` | `Float` | Height above Home / Takeoff point (meters) | `15.2m` |
| `trail` | `Array` | Historical coordinates for flight path line | `[[lat1, lon1], [lat2, lon2]]` |

### 3. GNSS / Satellite Quality (MAVLink: `GPS_RAW_INT` & `GPS2_RAW`)
| Field | Type | Description / Units | Example |
| :--- | :--- | :--- | :--- |
| `gps_fix` | `Integer / null` | Fix type (0=No Fix, 2=2D, 3=3D Fix, 4=DGPS, 5=RTK Float, 6=RTK Fixed) | `3` (3D Fix) |
| `satellites` | `Integer / null` | Count of visible satellites | `14` |
| `hdop` | `Float / null` | Horizontal Dilution of Precision (lower is better) | `0.9` |

### 4. Attitude & Orientation (MAVLink: `ATTITUDE`)
| Field | Type | Description / Units | Example |
| :--- | :--- | :--- | :--- |
| `pitch` | `Float` | Pitch angle in degrees (-90° to +90°) | `-2.5°` |
| `roll` | `Float` | Roll angle in degrees (-180° to +180°) | `1.2°` |
| `heading` | `Float` | Compass heading / Yaw in degrees (0° to 360°) | `184.5°` |

### 5. Speed & Air Dynamics (MAVLink: `VFR_HUD`)
| Field | Type | Description / Units | Example |
| :--- | :--- | :--- | :--- |
| `ground_speed` | `Float` | Speed over ground in meters/second (m/s) | `4.2 m/s` |
| `air_speed` | `Float` | Airspeed in meters/second (m/s) | `4.5 m/s` |

### 6. Power & Battery Health (MAVLink: `BATTERY_STATUS` & `SYS_STATUS`)
| Field | Type | Description / Units | Example |
| :--- | :--- | :--- | :--- |
| `battery_voltage` | `Float / null` | Total battery pack voltage in Volts (V) | `16.54 V` |
| `battery_current` | `Float / null` | Current draw in Amperes (A) | `8.2 A` |
| `battery_percent` | `Float / null` | Remaining battery level (0% – 100%) | `85%` |

### 7. Reference Home Position (MAVLink: `HOME_POSITION`)
| Field | Type | Description / Units | Example |
| :--- | :--- | :--- | :--- |
| `home_lat` | `Float` | Home location latitude | `12.971500` |
| `home_lon` | `Float` | Home location longitude | `77.594500` |
| `home_alt` | `Float` | Home altitude MSL (meters) | `905.3m` |

### 8. Autopilot Status Text (MAVLink: `STATUSTEXT`)
| Field | Type | Description / Units | Example |
| :--- | :--- | :--- | :--- |
| `severity` | `Integer` | Log severity (0=Emergency to 6=Info) | `6` |
| `text` | `String` | System message from flight controller | `"EKF3 IMU0 is using GPS"` |

---

## Pipeline Flow

```
Flight Controller (FC)
       │
       ▼ (Serial COM / UDP)
pymavlink (drone_worker.py)
       │
       ▼ (MAVLink Handlers)
Telemetry Pydantic Model (models.py)
       │
       ▼ (WebSocket JSON Broadcast)
gcsStore.js (React Frontend)
       │
       ▼
UI Components (TelemetryPanel, DroneMap, HUD, DroneListSidebar)
```
