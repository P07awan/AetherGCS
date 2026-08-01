"""Per-drone async worker.

Runs an independent asyncio task that maintains connection state and generates
realistic telemetry (simulator mode). Real MAVSDK integration would replace the
`_simulator_tick` implementation without changing the public API.
"""
from __future__ import annotations

import asyncio
import logging
import math
import random
import time
from typing import Callable, Optional

from .models import Drone, Waypoint

logger = logging.getLogger(__name__)

R_EARTH = 6_371_000.0  # meters


def _meters_to_latlon(lat: float, lon: float, dn: float, de: float) -> tuple[float, float]:
    dlat = (dn / R_EARTH) * (180.0 / math.pi)
    dlon = (de / (R_EARTH * math.cos(math.radians(lat)))) * (180.0 / math.pi)
    return lat + dlat, lon + dlon


def _bearing_meters(lat1, lon1, lat2, lon2) -> tuple[float, float]:
    """Return (distance_meters, bearing_degrees)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    dist = 2 * R_EARTH * math.asin(math.sqrt(a))
    y = math.sin(dlmb) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlmb)
    brng = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
    return dist, brng


class DroneWorker:
    """Independent async worker for a single drone."""

    TICK_HZ = 5
    TICK_DT = 1.0 / TICK_HZ

    def __init__(self, drone: Drone, on_update: Callable[[Drone], None]):
        self.drone = drone
        self.on_update = on_update
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._velocity_body = [0.0, 0.0, 0.0]  # fwd, right, up (m/s)
        self._yaw_rate = 0.0  # deg/s
        self._mission: list[Waypoint] = []
        self._mission_index = 0
        self._mission_running = False
        self._mission_paused = False
        self._t_armed: float | None = None
        # simulator uses home as initial position
        d = self.drone
        d.telemetry.latitude = d.home_lat
        d.telemetry.longitude = d.home_lon
        d.telemetry.altitude_msl = d.home_alt
        d.telemetry.altitude_relative = 0.0

    # ---- lifecycle -----------------------------------------------------
    async def connect(self) -> None:
        if self._running:
            return
        self.drone.status = "connecting"
        self.on_update(self.drone)
        await asyncio.sleep(0.4)  # simulate handshake
        self.drone.status = "connected"
        self._running = True
        self._task = asyncio.create_task(self._run(), name=f"worker-{self.drone.id}")
        self.on_update(self.drone)

    async def disconnect(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        self.drone.status = "disconnected"
        self.drone.telemetry.heartbeat = False
        self.on_update(self.drone)

    # ---- flight commands -----------------------------------------------
    async def arm(self) -> None:
        if self.drone.status != "connected":
            raise RuntimeError("Drone not connected")
        self.drone.telemetry.armed = True
        self._t_armed = time.time()
        self.on_update(self.drone)

    async def disarm(self) -> None:
        self.drone.telemetry.armed = False
        self._velocity_body = [0.0, 0.0, 0.0]
        self._yaw_rate = 0.0
        self._mission_running = False
        self.on_update(self.drone)

    async def takeoff(self, altitude: float = 15.0) -> None:
        if not self.drone.telemetry.armed:
            await self.arm()
        self.drone.telemetry.flight_mode = "GUIDED"
        # climb to target
        self._velocity_body = [0.0, 0.0, 2.0]
        # store target altitude
        self._takeoff_target = altitude
        self.on_update(self.drone)

    async def land(self) -> None:
        self.drone.telemetry.flight_mode = "LAND"
        self._velocity_body = [0.0, 0.0, -1.5]
        self._yaw_rate = 0.0
        self.on_update(self.drone)

    async def hold(self) -> None:
        self.drone.telemetry.flight_mode = "LOITER"
        self._velocity_body = [0.0, 0.0, 0.0]
        self._yaw_rate = 0.0
        self.on_update(self.drone)

    async def rtl(self) -> None:
        self.drone.telemetry.flight_mode = "RTL"
        self._mission_running = False
        self._rtl_active = True
        self.on_update(self.drone)

    async def emergency_stop(self) -> None:
        self.drone.telemetry.armed = False
        self._velocity_body = [0.0, 0.0, 0.0]
        self._yaw_rate = 0.0
        self._mission_running = False
        self.drone.telemetry.flight_mode = "MANUAL"
        self.on_update(self.drone)

    async def set_velocity(self, forward: float, right: float, up: float, yaw_rate: float) -> None:
        self._velocity_body = [forward, right, up]
        self._yaw_rate = yaw_rate
        if self.drone.telemetry.flight_mode not in ("GUIDED", "LOITER"):
            self.drone.telemetry.flight_mode = "GUIDED"
        self.on_update(self.drone)

    # ---- missions ------------------------------------------------------
    async def upload_mission(self, waypoints: list[Waypoint]) -> None:
        self._mission = [Waypoint(**w.model_dump()) for w in waypoints]
        self._mission_index = 0
        self._mission_running = False
        self._mission_paused = False
        self.on_update(self.drone)

    async def start_mission(self) -> None:
        if not self._mission:
            raise RuntimeError("No mission uploaded")
        if not self.drone.telemetry.armed:
            await self.arm()
        self.drone.telemetry.flight_mode = "AUTO"
        self._mission_running = True
        self._mission_paused = False
        self.on_update(self.drone)

    async def pause_mission(self) -> None:
        self._mission_paused = True
        self._velocity_body = [0.0, 0.0, 0.0]
        self.on_update(self.drone)

    async def resume_mission(self) -> None:
        self._mission_paused = False
        self.on_update(self.drone)

    async def stop_mission(self) -> None:
        self._mission_running = False
        self._mission_paused = False
        self._velocity_body = [0.0, 0.0, 0.0]
        self.on_update(self.drone)

    async def clear_mission(self) -> None:
        self._mission = []
        self._mission_index = 0
        self._mission_running = False
        self.on_update(self.drone)

    # ---- main loop -----------------------------------------------------
    async def _run(self) -> None:
        try:
            while self._running:
                self._simulator_tick(self.TICK_DT)
                self.on_update(self.drone)
                await asyncio.sleep(self.TICK_DT)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Worker %s crashed", self.drone.id)
            self.drone.status = "error"
            self.on_update(self.drone)

    def _simulator_tick(self, dt: float) -> None:
        t = self.drone.telemetry
        d = self.drone
        t.heartbeat = True
        t.heartbeat_ts = f"{time.time():.3f}"

        # flight time
        if t.armed and self._t_armed is not None:
            t.flight_time = int(time.time() - self._t_armed)

        # mission autopilot – steer toward current waypoint
        if self._mission_running and not self._mission_paused and self._mission:
            if self._mission_index >= len(self._mission):
                self._mission_running = False
                t.flight_mode = "LOITER"
            else:
                wp = self._mission[self._mission_index]
                dist, brng = _bearing_meters(t.latitude, t.longitude, wp.latitude, wp.longitude)
                # face waypoint
                t.heading = brng
                cruise_speed = 8.0
                if dist < 3.0 and abs(t.altitude_relative - wp.altitude) < 1.5:
                    self._mission_index += 1
                else:
                    self._velocity_body = [
                        min(cruise_speed, max(dist * 0.5, 1.0)),
                        0.0,
                        max(-2.0, min(2.0, (wp.altitude - t.altitude_relative) * 0.8)),
                    ]

        # RTL autopilot
        if t.flight_mode == "RTL":
            dist, brng = _bearing_meters(t.latitude, t.longitude, d.home_lat, d.home_lon)
            t.heading = brng
            if dist < 2.0:
                t.flight_mode = "LAND"
                self._velocity_body = [0.0, 0.0, -1.5]
            else:
                self._velocity_body = [min(8.0, dist * 0.5), 0.0, 0.0]

        # takeoff auto-level
        if hasattr(self, "_takeoff_target") and t.altitude_relative >= getattr(self, "_takeoff_target", 0):
            self._velocity_body[2] = 0.0
            t.flight_mode = "LOITER" if t.flight_mode == "GUIDED" else t.flight_mode

        # apply yaw rate
        t.heading = (t.heading + self._yaw_rate * dt) % 360.0

        # translate body velocity to NE (dn/dt north, de/dt east)
        yaw_rad = math.radians(t.heading)
        fwd, right, up = self._velocity_body
        dn = (fwd * math.cos(yaw_rad) - right * math.sin(yaw_rad)) * dt
        de = (fwd * math.sin(yaw_rad) + right * math.cos(yaw_rad)) * dt

        if t.armed:
            t.latitude, t.longitude = _meters_to_latlon(t.latitude, t.longitude, dn, de)
            t.altitude_relative = max(0.0, t.altitude_relative + up * dt)
            t.altitude_msl = d.home_alt + t.altitude_relative
            t.ground_speed = math.hypot(fwd, right)
            t.air_speed = t.ground_speed + random.uniform(-0.2, 0.2)

            # touchdown – if landing and hit ground
            if t.flight_mode == "LAND" and t.altitude_relative <= 0.05:
                t.altitude_relative = 0.0
                t.armed = False
                self._velocity_body = [0.0, 0.0, 0.0]
                t.flight_mode = "STABILIZE"

            # trail
            if not d.trail or _bearing_meters(
                d.trail[-1][0], d.trail[-1][1], t.latitude, t.longitude
            )[0] > 1.0:
                d.trail.append([t.latitude, t.longitude])
                if len(d.trail) > 500:
                    d.trail.pop(0)

            # battery drain – proportional to throttle
            throttle = abs(fwd) + abs(right) + abs(up) + 0.4
            drain = 0.02 * throttle * dt
            t.battery_percent = max(0.0, t.battery_percent - drain)
            t.battery_voltage = 14.4 + (t.battery_percent / 100.0) * 2.4
            t.battery_current = 5.0 + throttle * 3.0
        else:
            t.ground_speed = 0.0
            t.air_speed = 0.0
            t.battery_current = 0.3

        # GPS noise
        t.satellites = max(6, min(20, t.satellites + random.choice([-1, 0, 0, 0, 1])))
        t.gps_fix = 3 if t.satellites >= 6 else 2
