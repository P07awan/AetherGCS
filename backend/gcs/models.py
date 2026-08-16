"""Pydantic models for the GCS (drones, telemetry, missions, commands)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict
import uuid


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


ConnectionType = Literal["udp", "tcp", "serial", "simulator"]
FlightMode = Literal[
    "MANUAL", "STABILIZE", "GUIDED", "AUTO", "LOITER", "RTL", "LAND", "POSHOLD",
    "ALT_HOLD", "MODE_0", "MODE_1", "MODE_2", "MODE_3", "MODE_4", "MODE_5",
    "MODE_6", "MODE_7", "MODE_8", "MODE_9", "MODE_10", "MODE_11", "MODE_12",
]
DroneStatus = Literal["disconnected", "connecting", "connected", "error"]

# Explicit flight state machine — updated by drone workers, consumed by frontend
FlightState = Literal[
    "DISCONNECTED",      # no MAVLink link
    "CONNECTED",         # link up, waiting for heartbeat / pre-arm
    "DISARMED",          # heartbeat received, armed=False
    "ARMING",            # ARM command sent, waiting for ACK + heartbeat confirmation
    "ARMED",             # heartbeat confirms armed=True, on ground
    "TAKEOFF_REQUESTED", # TAKEOFF command sent, waiting for ACK
    "TAKING_OFF",        # climbing toward target altitude
    "AIRBORNE",          # at or above target altitude, holding
    "LANDING",           # LAND command sent / descending
    "LANDED",            # on ground after landing (may still be armed briefly)
    "MISSION_READY",     # mission uploaded, armed, ready to start
    "MISSION_ACTIVE",    # AUTO mode, mission running
]


class ConnectionProfile(BaseModel):
    connection_type: ConnectionType = "simulator"
    address: str = ""          # e.g. "127.0.0.1"
    port: Optional[int] = None
    baud_rate: Optional[int] = None
    auto_reconnect: bool = True


class DroneCreate(BaseModel):
    name: str
    system_id: int = 1
    component_id: int = 1
    connection: ConnectionProfile = Field(default_factory=ConnectionProfile)
    home_lat: float = 37.7749
    home_lon: float = -122.4194
    home_alt: float = 0.0


class Telemetry(BaseModel):
    armed: bool = False
    flight_mode: FlightMode = "STABILIZE"
    flight_state: FlightState = "DISCONNECTED"  # explicit state machine
    # Optional for real drones — None means MAVLink hasn't sent data yet
    battery_percent: Optional[float] = None   # 0-100 or None (unknown)
    battery_voltage: Optional[float] = None   # V or None
    battery_current: Optional[float] = None   # A or None
    gps_fix: Optional[int] = None             # 0=no fix, 2=2D, 3=3D, None=unknown
    ekf_ok: Optional[bool] = None             # True if EKF is healthy
    satellites: Optional[int] = None          # count or None
    hdop: Optional[float] = None              # horizontal dilution of precision (e.g. 1.2)
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_msl: float = 0.0
    altitude_relative: float = 0.0
    ground_speed: float = 0.0
    air_speed: float = 0.0
    heading: float = 0.0        # degrees 0-360
    pitch: float = 0.0          # degrees -90 to +90
    roll: float = 0.0           # degrees -180 to +180
    flight_time: int = 0        # seconds
    heartbeat: bool = True
    heartbeat_ts: str = Field(default_factory=_now_iso)


class Drone(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    system_id: int
    component_id: int
    firmware: str = ""  # populated from heartbeat for real drones
    connection: ConnectionProfile
    status: DroneStatus = "disconnected"
    last_error: Optional[str] = None
    home_lat: float
    home_lon: float
    home_alt: float
    telemetry: Telemetry = Field(default_factory=Telemetry)
    trail: List[List[float]] = Field(default_factory=list)  # [[lat,lon], ...]
    created_at: str = Field(default_factory=_now_iso)


class Waypoint(BaseModel):
    seq: int
    latitude: float
    longitude: float
    altitude: float = 20.0
    hold_seconds: float = 0.0
    action: Literal["waypoint", "takeoff", "land", "rtl"] = "waypoint"


class Mission(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    default_altitude: float = 20.0
    default_speed: float = 5.0
    waypoints: List[Waypoint] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class MissionCreate(BaseModel):
    name: str
    description: str = ""
    default_altitude: float = 20.0
    default_speed: float = 5.0
    waypoints: List[Waypoint] = Field(default_factory=list)


class CommandRequest(BaseModel):
    drone_ids: List[str]
    command: str
    params: dict = Field(default_factory=dict)


class CommandLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    drone_id: str
    drone_name: str = ""
    command: str
    params: dict = Field(default_factory=dict)
    status: Literal["queued", "sent", "ack", "success", "failed", "timeout"] = "queued"
    response_ms: Optional[int] = None
    error: Optional[str] = None
    ts: str = Field(default_factory=_now_iso)
