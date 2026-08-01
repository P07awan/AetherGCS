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
    "MANUAL", "STABILIZE", "GUIDED", "AUTO", "LOITER", "RTL", "LAND", "POSHOLD"
]
DroneStatus = Literal["disconnected", "connecting", "connected", "error"]


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
    battery_percent: float = 100.0
    battery_voltage: float = 16.8
    battery_current: float = 0.0
    gps_fix: int = 3            # 0=no fix, 3=3D
    satellites: int = 12
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_msl: float = 0.0
    altitude_relative: float = 0.0
    ground_speed: float = 0.0
    air_speed: float = 0.0
    heading: float = 0.0        # degrees 0-360
    flight_time: int = 0        # seconds
    heartbeat: bool = True
    heartbeat_ts: str = Field(default_factory=_now_iso)


class Drone(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    system_id: int
    component_id: int
    firmware: str = "ArduPilot 4.4.0 (SIM)"
    connection: ConnectionProfile
    status: DroneStatus = "disconnected"
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
