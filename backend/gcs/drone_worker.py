"""Per-drone async worker.

Two concrete implementations share the same public API:
  - SimulatorWorker: built-in physics-lite simulator (no real link)
  - MavlinkWorker:   pymavlink connection to a real/SITL drone via serial, UDP or TCP
"""
from __future__ import annotations

import asyncio
import logging
import math
import random
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional

from .models import Drone, Waypoint

logger = logging.getLogger(__name__)

R_EARTH = 6_371_000.0  # meters
MAX_TAKEOFF_ALTITUDE = 120.0  # metres — GCS safety hard limit

# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# MAVLink flight-mode mapping (ArduCopter / PX4)
# ---------------------------------------------------------------------------
_ARDUPILOT_MODE_MAP: dict[int, str] = {
    0: "STABILIZE",
    2: "ALT_HOLD",
    3: "AUTO",
    4: "GUIDED",
    5: "LOITER",
    6: "RTL",
    9: "LAND",
    16: "POSHOLD",
    19: "MANUAL",
}

_PX4_MODE_MAP: dict[int, str] = {
    # main_mode (byte 1 of custom_mode uint32)
    1: "MANUAL",
    2: "STABILIZE",
    3: "POSHOLD",
    4: "AUTO",
    6: "LOITER",
    7: "RTL",
    8: "AUTO",  # MISSION
}


def _ardupilot_mode_str(custom_mode: int) -> str:
    return _ARDUPILOT_MODE_MAP.get(custom_mode, f"MODE_{custom_mode}")


def _px4_mode_str(custom_mode: int) -> str:
    main = (custom_mode >> 16) & 0xFF
    return _PX4_MODE_MAP.get(main, f"MODE_{main}")


def _update_flight_state_from_telemetry(t) -> None:
    """
    Derive flight_state from real telemetry (armed flag, flight mode, altitude).

    This is called on every HEARTBEAT and GLOBAL_POSITION_INT so that transient
    command states (ARMING, TAKING_OFF, LANDING) are resolved as soon as the
    flight controller confirms the actual state.

    State transitions:
      not armed                     → DISARMED
      armed + AUTO mode             → MISSION_ACTIVE
      armed + LAND/RTL mode         → LANDING  (or DISARMED if on ground)
      armed + altitude > 1.5 m AGL → AIRBORNE
      armed + altitude ≤ 1.5 m AGL → ARMED (on ground)
    """
    if not t.armed:
        t.flight_state = "DISARMED"
        return

    mode = t.flight_mode or ""
    alt = t.altitude_relative or 0.0

    if mode == "AUTO":
        t.flight_state = "MISSION_ACTIVE"
    elif mode in ("LAND", "RTL"):
        # Detect touch-down: altitude essentially zero
        if alt <= 0.2:
            t.flight_state = "DISARMED"   # FC will auto-disarm; pre-empt the display
        else:
            t.flight_state = "LANDING"
    elif alt > 1.5:
        t.flight_state = "AIRBORNE"
    else:
        # On ground, armed (covers ARMING transient \u2014 once armed is True it shows ARMED)
        t.flight_state = "ARMED"


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class DroneWorker(ABC):
    """Public API shared by SimulatorWorker and MavlinkWorker."""

    TICK_HZ = 5
    TICK_DT = 1.0 / TICK_HZ

    def __init__(self, drone: Drone, on_update: Callable[[Drone], None]) -> None:
        self.drone = drone
        self.on_update = on_update
        self._running = False
        self._task: Optional[asyncio.Task] = None

    # ---- lifecycle ---------------------------------------------------------
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    # ---- commands ----------------------------------------------------------
    @abstractmethod
    async def arm(self) -> None: ...

    @abstractmethod
    async def disarm(self) -> None: ...

    @abstractmethod
    async def takeoff(self, altitude: float = 15.0) -> None: ...

    @abstractmethod
    async def land(self) -> None: ...

    @abstractmethod
    async def hold(self) -> None: ...

    @abstractmethod
    async def rtl(self) -> None: ...

    @abstractmethod
    async def emergency_stop(self) -> None: ...

    @abstractmethod
    async def set_velocity(self, forward: float, right: float, up: float, yaw_rate: float) -> None: ...

    @abstractmethod
    async def upload_mission(self, waypoints: list[Waypoint]) -> None: ...

    @abstractmethod
    async def start_mission(self) -> None: ...

    @abstractmethod
    async def pause_mission(self) -> None: ...

    @abstractmethod
    async def resume_mission(self) -> None: ...

    @abstractmethod
    async def stop_mission(self) -> None: ...

    @abstractmethod
    async def clear_mission(self) -> None: ...

    @abstractmethod
    async def level_horizon(self) -> None: ...

    @abstractmethod
    async def set_flight_mode(self, mode: str) -> None: ...


# ---------------------------------------------------------------------------
# SimulatorWorker  (original physics-lite implementation)
# ---------------------------------------------------------------------------

class SimulatorWorker(DroneWorker):
    """Independent async worker for a single simulated drone."""

    def __init__(self, drone: Drone, on_update: Callable[[Drone], None]) -> None:
        super().__init__(drone, on_update)
        self._velocity_body = [0.0, 0.0, 0.0]  # fwd, right, up (m/s)
        self._yaw_rate = 0.0  # deg/s
        self._mission: list[Waypoint] = []
        self._mission_index = 0
        self._mission_running = False
        self._mission_paused = False
        self._t_armed: float | None = None
        self._rtl_active = False
        self._takeoff_target: float = 15.0

        d = self.drone
        d.telemetry.latitude = d.home_lat
        d.telemetry.longitude = d.home_lon
        d.telemetry.altitude_msl = d.home_alt
        d.telemetry.altitude_relative = 0.0
        # Simulator initial values
        d.telemetry.battery_percent = 100.0
        d.telemetry.battery_voltage = 16.8
        d.telemetry.battery_current = 0.0
        d.telemetry.gps_fix = 3
        d.telemetry.satellites = 14
        d.telemetry.hdop = 1.2

    # ---- lifecycle ---------------------------------------------------------
    async def connect(self) -> None:
        if self._running:
            return
        self.drone.status = "connected"
        self.drone.firmware = "ArduPilot 4.4.0 (SIM)"
        self._running = True
        self._task = asyncio.create_task(self._run(), name=f"sim-{self.drone.id}")
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

    # ---- flight commands ---------------------------------------------------
    async def arm(self) -> None:
        if self.drone.status != "connected":
            await self.connect()
        if self.drone.telemetry.armed:
            raise RuntimeError("Drone is already armed.")
        self.drone.telemetry.flight_state = "ARMING"
        self.on_update(self.drone)
        # Simulate a brief arming delay (like waiting for ACK)
        await asyncio.sleep(0.2)
        self.drone.telemetry.armed = True
        self._t_armed = time.time()
        self.drone.telemetry.flight_state = "ARMED"
        self.on_update(self.drone)

    async def disarm(self) -> None:
        alt = self.drone.telemetry.altitude_relative or 0.0
        if alt > 0.5:
            raise RuntimeError(
                f"Cannot disarm: drone is airborne at {alt:.1f}m AGL. "
                "LAND the drone first."
            )
        self.drone.telemetry.armed = False
        self._velocity_body = [0.0, 0.0, 0.0]
        self._yaw_rate = 0.0
        self._mission_running = False
        self.drone.telemetry.flight_state = "DISARMED"
        self.on_update(self.drone)

    async def takeoff(self, altitude: float = 10.0) -> None:
        if not self.drone.telemetry.armed:
            raise RuntimeError(
                "Drone is not armed. Click ARM first, then TAKEOFF."
            )
        if altitude <= 0 or altitude > MAX_TAKEOFF_ALTITUDE:
            raise RuntimeError(
                f"Requested altitude {altitude:.1f}m exceeds safety limit of {MAX_TAKEOFF_ALTITUDE}m."
            )
        self.drone.telemetry.flight_state = "TAKEOFF_REQUESTED"
        self.drone.telemetry.flight_mode = "GUIDED"
        self._velocity_body = [0.0, 0.0, 2.0]
        self._takeoff_target = altitude
        self.drone.telemetry.flight_state = "TAKING_OFF"
        self.on_update(self.drone)

    async def land(self) -> None:
        self.drone.telemetry.flight_mode = "LAND"
        self._velocity_body = [0.0, 0.0, -1.5]
        self._yaw_rate = 0.0
        self.drone.telemetry.flight_state = "LANDING"
        self.on_update(self.drone)

    async def hold(self) -> None:
        self.drone.telemetry.flight_mode = "LOITER"
        self._velocity_body = [0.0, 0.0, 0.0]
        self._yaw_rate = 0.0
        # Only update to AIRBORNE if we're actually in the air
        if self.drone.telemetry.altitude_relative > 0.5:
            self.drone.telemetry.flight_state = "AIRBORNE"
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
        self.drone.telemetry.flight_state = "DISARMED"
        self.on_update(self.drone)

    async def level_horizon(self) -> None:
        logger.info("Level horizon executed on simulator %s", self.drone.name)
        self.on_update(self.drone)

    async def set_velocity(self, forward: float, right: float, up: float, yaw_rate: float) -> None:
        self._velocity_body = [forward, right, up]
        self._yaw_rate = yaw_rate
        if self.drone.telemetry.flight_mode not in ("GUIDED", "LOITER"):
            self.drone.telemetry.flight_mode = "GUIDED"
        self.on_update(self.drone)

    # ---- missions ----------------------------------------------------------
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
            raise RuntimeError(
                "Drone is not armed. ARM the drone before starting a mission."
            )
        self.drone.telemetry.flight_mode = "AUTO"
        self._mission_running = True
        self._mission_paused = False
        self.drone.telemetry.flight_state = "MISSION_ACTIVE"
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

    async def set_flight_mode(self, mode: str) -> None:
        """Switch to a named flight mode on the simulator."""
        VALID = {"STABILIZE", "ALT_HOLD", "POSHOLD", "GUIDED", "LOITER", "AUTO", "LAND", "RTL", "MANUAL"}
        m = mode.upper()
        if m not in VALID:
            raise ValueError(f"Simulator: unknown mode '{mode}'. Valid: {', '.join(sorted(VALID))}")
        self.drone.telemetry.flight_mode = m
        # Stop velocity so the mode change takes effect visually
        if m in ("LOITER", "STABILIZE", "ALT_HOLD", "POSHOLD", "GUIDED"):
            self._velocity_body = [0.0, 0.0, 0.0]
            self._yaw_rate = 0.0
        if m == "LAND":
            self._velocity_body = [0.0, 0.0, -1.5]
            self._yaw_rate = 0.0
            self.drone.telemetry.flight_state = "LANDING"
        self.on_update(self.drone)
        logger.info("Simulator %s mode → %s", self.drone.id, m)

    # ---- main loop ---------------------------------------------------------
    async def _run(self) -> None:
        try:
            while self._running:
                self._simulator_tick(self.TICK_DT)
                self.on_update(self.drone)
                await asyncio.sleep(self.TICK_DT)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("SimulatorWorker %s crashed", self.drone.id)
            self.drone.status = "error"
            self.on_update(self.drone)

    def _simulator_tick(self, dt: float) -> None:
        t = self.drone.telemetry
        d = self.drone
        t.heartbeat = True
        t.heartbeat_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if t.armed and self._t_armed is not None:
            t.flight_time = int(time.time() - self._t_armed)

        # mission autopilot
        if self._mission_running and not self._mission_paused and self._mission:
            if self._mission_index >= len(self._mission):
                self._mission_running = False
                t.flight_mode = "LOITER"
            else:
                wp = self._mission[self._mission_index]
                dist, brng = _bearing_meters(t.latitude, t.longitude, wp.latitude, wp.longitude)
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

        # takeoff auto-level: stop climbing and transition to AIRBORNE
        if t.altitude_relative >= self._takeoff_target and t.flight_mode == "GUIDED":
            self._velocity_body[2] = 0.0
            t.flight_mode = "LOITER"
            if t.flight_state == "TAKING_OFF":
                t.flight_state = "AIRBORNE"

        t.heading = (t.heading + self._yaw_rate * dt) % 360.0

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

            if t.flight_mode == "LAND" and t.altitude_relative <= 0.05:
                t.altitude_relative = 0.0
                t.armed = False
                self._velocity_body = [0.0, 0.0, 0.0]
                t.flight_mode = "STABILIZE"
                _update_flight_state_from_telemetry(t)  # → DISARMED

            if not d.trail or _bearing_meters(
                d.trail[-1][0], d.trail[-1][1], t.latitude, t.longitude
            )[0] > 1.0:
                d.trail.append([t.latitude, t.longitude])
                if len(d.trail) > 500:
                    d.trail.pop(0)

            throttle = abs(fwd) + abs(right) + abs(up) + 0.4
            drain = 0.02 * throttle * dt
            if t.battery_percent is None:
                t.battery_percent = 100.0
            t.battery_percent = max(0.0, t.battery_percent - drain)
            t.battery_voltage = 14.4 + (t.battery_percent / 100.0) * 2.4
            t.battery_current = 5.0 + throttle * 3.0
        else:
            t.ground_speed = 0.0
            t.air_speed = 0.0
            t.battery_current = 0.3

        curr_sats = t.satellites if t.satellites is not None else 14
        t.satellites = max(6, min(20, curr_sats + random.choice([-1, 0, 0, 0, 1])))
        t.gps_fix = 3 if t.satellites >= 6 else 2
        curr_hdop = t.hdop if t.hdop is not None else 1.2
        t.hdop = round(max(0.7, min(2.5, curr_hdop + random.uniform(-0.04, 0.04))), 2)


# ---------------------------------------------------------------------------
# MavlinkWorker  (real drone via pymavlink)
# ---------------------------------------------------------------------------

class MavlinkWorker(DroneWorker):
    """Connects to a real (or SITL) drone via MAVLink using pymavlink.

    Supports serial (COMx / /dev/tty*), UDP (udpin), and TCP connections.
    Runs a blocking pymavlink receive loop in a thread executor so asyncio
    is never blocked.
    """

    HEARTBEAT_INTERVAL = 1.0       # send GCS heartbeat every second
    CONNECT_TIMEOUT    = 15.0      # seconds to wait for first heartbeat
    RECONNECT_DELAY    = 5.0       # seconds before reconnect attempt
    TELEMETRY_STREAM_RATE = 10     # Hz — requested from autopilot

    def __init__(self, drone: Drone, on_update: Callable[[Drone], None]) -> None:
        super().__init__(drone, on_update)
        self._mav = None            # mavutil.mavlink_connection instance
        self._hb_task: Optional[asyncio.Task] = None
        self._rx_task: Optional[asyncio.Task] = None
        self._mission_buffer: list[Waypoint] = []
        self._pending_mission_ack = False
        self._mission_msg_queue: asyncio.Queue = asyncio.Queue()
        # ACK queue: COMMAND_ACK messages routed here for command confirmation
        self._ack_queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        # Last STATUSTEXT lines (ring buffer) — captures pre-arm check failures
        self._recent_statustext: list[str] = []

        d = self.drone
        d.telemetry.latitude = d.home_lat
        d.telemetry.longitude = d.home_lon

    # ---- connection string -------------------------------------------------
    def _connection_string(self) -> str:
        c = self.drone.connection
        ct = c.connection_type
        addr = c.address.strip() if c.address else ""
        port = c.port or (14550 if ct == "udp" else 5760)

        # Explicit full connection string provided
        if any(addr.startswith(prefix) for prefix in ("udpin:", "udpout:", "udp:", "tcp:", "tcpin:", "serial:")):
            return addr

        if ct == "serial":
            return addr if addr else "COM3"
        elif ct == "udp":
            if addr in ("", "0.0.0.0", "127.0.0.1", "localhost"):
                bind_addr = addr if addr else "0.0.0.0"
                return f"udpin:{bind_addr}:{port}"
            else:
                return f"udp:{addr}:{port}"
        elif ct == "tcp":
            if addr in ("", "0.0.0.0"):
                return f"tcpin:0.0.0.0:{port}"
            else:
                host_addr = addr if addr else "127.0.0.1"
                return f"tcp:{host_addr}:{port}"
        raise ValueError(f"Unsupported connection_type: {ct}")

    # ---- lifecycle ---------------------------------------------------------
    async def connect(self) -> None:
        if self._running:
            return
        self.drone.status = "connecting"
        self.drone.last_error = None
        self.on_update(self.drone)
        try:
            await self._open_link()
        except Exception as exc:
            err_msg = str(exc)
            if "No module named 'serial'" in err_msg:
                err_msg = "pyserial package is not installed in backend python environment"
            elif "PermissionError" in err_msg or "Access is denied" in err_msg:
                err_msg = f"Serial port {self.drone.connection.address} is locked by another program (e.g. Mission Planner or QGroundControl)"
            elif "FileNotFoundError" in err_msg or "cannot find" in err_msg.lower():
                err_msg = f"Serial port '{self.drone.connection.address}' was not found on this system"
            elif isinstance(exc, TimeoutError) or "No heartbeat" in err_msg:
                err_msg = f"No MAVLink heartbeat received within {self.CONNECT_TIMEOUT}s (Check drone power, telemetry baud rate, or cable/radio)"
            
            logger.error("MavlinkWorker %s connect failed: %s", self.drone.id, err_msg)
            self.drone.status = "error"
            self.drone.last_error = err_msg
            self.on_update(self.drone)
            if self.drone.connection.auto_reconnect:
                self._task = asyncio.create_task(
                    self._reconnect_loop(), name=f"mav-reconnect-{self.drone.id}"
                )
            return

        self._running = True
        self.drone.status = "connected"
        self.drone.last_error = None
        self.on_update(self.drone)
        self._hb_task = asyncio.create_task(self._heartbeat_loop(), name=f"mav-hb-{self.drone.id}")
        self._rx_task  = asyncio.create_task(self._receive_loop(),   name=f"mav-rx-{self.drone.id}")

    async def disconnect(self) -> None:
        self._running = False
        for t in (self._task, self._hb_task, self._rx_task):
            if t:
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
        self._task = self._hb_task = self._rx_task = None

        loop = asyncio.get_running_loop()
        if self._mav:
            try:
                await loop.run_in_executor(None, self._mav.close)
            except Exception:
                pass
            self._mav = None

        self.drone.status = "disconnected"
        self.drone.telemetry.heartbeat = False
        self.on_update(self.drone)

    # ---- internal link setup -----------------------------------------------
    async def _open_link(self) -> None:
        from pymavlink import mavutil

        conn_str  = self._connection_string()
        baud      = self.drone.connection.baud_rate or 57600
        loop      = asyncio.get_running_loop()
        ct        = self.drone.connection.connection_type

        logger.info("MavlinkWorker %s opening %s (baud=%s)", self.drone.id, conn_str, baud)

        # mavlink_connection is blocking — run in thread executor
        def _open():
            if ct == "serial":
                return mavutil.mavlink_connection(conn_str, baud=baud, autoreconnect=True)
            else:
                return mavutil.mavlink_connection(conn_str, autoreconnect=True)

        try:
            mav = await asyncio.wait_for(
                loop.run_in_executor(None, _open),
                timeout=self.CONNECT_TIMEOUT,
            )
        except Exception as exc:
            err_msg = str(exc)
            if "Permission denied" in err_msg or "Errno 13" in err_msg:
                port_name = self.drone.connection.address or conn_str
                clean_err = f"Port {port_name} is locked by another program (e.g. Mission Planner or QGroundControl). Please disconnect Mission Planner or close software using {port_name}."
                self.drone.last_error = clean_err
                raise RuntimeError(clean_err) from exc
            self.drone.last_error = err_msg
            raise

        # wait for first heartbeat
        def _wait_hb():
            return mav.wait_heartbeat(timeout=self.CONNECT_TIMEOUT)

        hb = await asyncio.wait_for(
            loop.run_in_executor(None, _wait_hb),
            timeout=self.CONNECT_TIMEOUT + 2,
        )
        if hb is None:
            mav.close()
            raise TimeoutError("No heartbeat received within timeout")

        self._mav = mav
        # populate firmware / autopilot info from heartbeat
        autopilot = getattr(hb, "autopilot", 3)
        fw_names  = {3: "ArduPilot", 12: "PX4", 8: "SLUGS", 0: "Generic"}
        fw_label  = fw_names.get(autopilot, f"AP_{autopilot}")
        self.drone.firmware = f"{fw_label} (live)"
        logger.info(
            "MavlinkWorker %s connected — autopilot=%s sysid=%s",
            self.drone.id, fw_label, mav.target_system,
        )

        # request all standard data streams at TELEMETRY_STREAM_RATE Hz
        await loop.run_in_executor(None, self._request_data_streams)

    def _request_data_streams(self) -> None:
        """Request MAVLink data streams from autopilot (MAV_DATA_STREAM)."""
        from pymavlink import mavutil as _mu
        if self._mav is None:
            return
        hz = self.TELEMETRY_STREAM_RATE
        # Request individual message intervals using MAV_CMD_SET_MESSAGE_INTERVAL
        msg_ids = [
            33,   # GLOBAL_POSITION_INT
            74,   # VFR_HUD
            1,    # SYS_STATUS
            30,   # ATTITUDE
            24,   # GPS_RAW_INT
            124,  # GPS2_RAW (secondary GPS)
            62,   # NAV_CONTROLLER_OUTPUT
            42,   # MISSION_CURRENT
            147,  # BATTERY_STATUS
            242,  # HOME_POSITION
        ]
        for msg_id in msg_ids:
            try:
                self._mav.mav.command_long_send(
                    self._mav.target_system,
                    self._mav.target_component,
                    511,  # MAV_CMD_SET_MESSAGE_INTERVAL
                    0,
                    float(msg_id),
                    int(1_000_000 / hz),  # interval in microseconds
                    0, 0, 0, 0, 0,
                )
            except Exception:
                pass
        # Also use the legacy MAV_DATA_STREAM_ALL for older firmwares
        try:
            self._mav.mav.request_data_stream_send(
                self._mav.target_system,
                self._mav.target_component,
                _mu.mavlink.MAV_DATA_STREAM_ALL,
                hz, 1,
            )
        except Exception:
            pass

    # ---- receive loop ------------------------------------------------------
    async def _receive_loop(self) -> None:
        """Non-blocking receive loop — runs message callbacks at TICK_HZ."""
        loop = asyncio.get_running_loop()
        while self._running:
            try:
                msg = await loop.run_in_executor(
                    None, lambda: self._mav.recv_match(blocking=True, timeout=0.2)
                )
                if msg is None:
                    continue
                self._handle_message(msg)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._running:
                    logger.warning("MavlinkWorker %s receive error: %s", self.drone.id, exc)
                    await asyncio.sleep(0.5)
                    if self.drone.connection.auto_reconnect:
                        self._running = False
                        if not self._task or self._task.done():
                            self._task = asyncio.create_task(
                                self._reconnect_loop(), name=f"mav-reconnect-{self.drone.id}"
                            )
                    break

    def _calc_battery_percent(self, voltage: float | None, reported_pct: float | None) -> float | None:
        """Calculate battery percent cleanly.
        If reported_pct is between 1 and 100, use reported_pct.
        If reported_pct <= 0 or None (e.g. ArduPilot BATT_CAPACITY parameter is 0),
        estimate percentage from battery voltage curve if voltage is valid (>6V).
        """
        if reported_pct is not None and 1 <= reported_pct <= 100:
            return float(reported_pct)
        if voltage is None or voltage < 6.0:
            return None
        # Auto-detect cell count (2S, 3S, 4S, 6S)
        if 13.0 <= voltage <= 17.2:
            cell_v = voltage / 4.0   # 4S pack (14.0V - 16.8V)
        elif 9.5 <= voltage <= 13.0:
            cell_v = voltage / 3.0   # 3S pack (10.5V - 12.6V)
        elif 19.0 <= voltage <= 25.8:
            cell_v = voltage / 6.0   # 6S pack (21.0V - 25.2V)
        elif 6.5 <= voltage <= 8.6:
            cell_v = voltage / 2.0   # 2S pack (7.0V - 8.4V)
        else:
            cell_v = voltage / 4.0   # fallback 4S

        pct = (cell_v - 3.5) / (4.2 - 3.5) * 100.0
        return max(0.0, min(100.0, round(pct, 0)))

    def _handle_message(self, msg) -> None:
        """Map incoming MAVLink messages to Telemetry fields."""
        t   = self.drone.telemetry
        typ = msg.get_type()

        if typ == "HEARTBEAT":
            t.heartbeat    = True
            t.heartbeat_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            t.armed        = bool(msg.base_mode & 0x80)  # MAV_MODE_FLAG_SAFETY_ARMED
            # Decode flight mode
            try:
                fw = self.drone.firmware.lower()
                if "px4" in fw:
                    t.flight_mode = _px4_mode_str(msg.custom_mode)
                else:
                    t.flight_mode = _ardupilot_mode_str(msg.custom_mode)  # type: ignore[assignment]
            except Exception:
                pass

            # Derive flight_state entirely from telemetry — authoritative source.
            # Transient command states (ARMING, TAKING_OFF, LANDING) are overridden here
            # as soon as the FC confirms the real state via heartbeat.
            _update_flight_state_from_telemetry(t)
            self.on_update(self.drone)

        elif typ == "GLOBAL_POSITION_INT":
            t.latitude          = msg.lat  / 1e7
            t.longitude         = msg.lon  / 1e7
            t.altitude_msl      = msg.alt  / 1000.0
            t.altitude_relative = msg.relative_alt / 1000.0
            # Update flight_state based on altitude change —
            # catches TAKING_OFF → AIRBORNE as the drone climbs
            _update_flight_state_from_telemetry(t)
            # trail point
            d = self.drone
            if not d.trail or _bearing_meters(
                d.trail[-1][0], d.trail[-1][1], t.latitude, t.longitude
            )[0] > 1.0:
                d.trail.append([t.latitude, t.longitude])
                if len(d.trail) > 500:
                    d.trail.pop(0)
            self.on_update(self.drone)

        elif typ == "GPS_RAW_INT":
            t.gps_fix = msg.fix_type
            # satellites_visible: 255 = unknown in MAVLink spec
            sats = getattr(msg, "satellites_visible", 255)
            t.satellites = None if sats == 255 else int(sats)
            # eph (HDOP * 100): 65535 or >= 9900 = invalid/no 3D lock
            raw_eph = getattr(msg, "eph", 65535)
            if raw_eph is not None and 0 < raw_eph < 9900:
                t.hdop = round(raw_eph / 100.0, 2)
            else:
                t.hdop = None
            if t.latitude == 0.0:
                t.latitude  = msg.lat / 1e7
                t.longitude = msg.lon / 1e7
                t.altitude_msl = msg.alt / 1000.0
            self.on_update(self.drone)

        elif typ == "GPS2_RAW":
            sats2 = getattr(msg, "satellites_visible", 255)
            if sats2 != 255 and (t.satellites is None or t.satellites == 0):
                t.satellites = int(sats2)
            fix2 = getattr(msg, "fix_type", None)
            if fix2 is not None and (t.gps_fix is None or t.gps_fix < fix2):
                t.gps_fix = fix2
            raw_eph2 = getattr(msg, "eph", 65535)
            if raw_eph2 is not None and 0 < raw_eph2 < 9900 and t.hdop is None:
                t.hdop = round(raw_eph2 / 100.0, 2)
            self.on_update(self.drone)

        elif typ == "VFR_HUD":
            t.ground_speed = msg.groundspeed
            t.air_speed    = msg.airspeed
            t.heading      = float(msg.heading)
            t.altitude_msl = float(msg.alt)   # MSL in metres for ArduPilot
            # NOTE: Do NOT derive altitude_relative here from (MSL - home_alt).
            # GLOBAL_POSITION_INT.relative_alt is the authoritative source for relative altitude
            # because the autopilot computes it from its own armed home position (always 0 at
            # takeoff point, positive going up). Recomputing from (MSL - user_home_alt) breaks
            # when user_home_alt (default 0.0) doesn't match the actual MSL elevation of home.
            # Fallback: if GLOBAL_POSITION_INT has never arrived (lat == 0), estimate from MSL.
            if t.latitude == 0.0:
                home_alt = self.drone.home_alt or 0.0
                t.altitude_relative = t.altitude_msl - home_alt
            self.on_update(self.drone)

        elif typ == "HOME_POSITION":
            self.drone.home_lat = msg.latitude / 1e7
            self.drone.home_lon = msg.longitude / 1e7
            self.drone.home_alt = msg.altitude / 1000.0
            self.on_update(self.drone)

        elif typ == "ATTITUDE":
            t.pitch = math.degrees(msg.pitch)
            t.roll  = math.degrees(msg.roll)
            t.heading = (math.degrees(msg.yaw) + 360.0) % 360.0
            self.on_update(self.drone)

        elif typ == "SYS_STATUS":
            batt_mv = msg.voltage_battery          # millivolts
            if batt_mv > 0:
                t.battery_voltage = round(batt_mv / 1000.0, 2)
            batt_ma = msg.current_battery          # centiamperes (or -1 if unknown)
            if batt_ma > 0:
                t.battery_current = round(batt_ma / 100.0, 2)
            elif batt_ma == 0:
                t.battery_current = 0.0
            else:
                t.battery_current = None           # -1 = sensor not installed/unsupported
            batt_pct = msg.battery_remaining       # 0-100 or -1
            rep_pct = float(batt_pct) if 0 <= batt_pct <= 100 else None
            t.battery_percent = self._calc_battery_percent(t.battery_voltage, rep_pct)
            
            # Check EKF health via MAV_SYS_STATUS_AHRS (0x10000)
            sensors_health = getattr(msg, "onboard_control_sensors_health", 0)
            if sensors_health > 0:
                t.ekf_ok = bool(sensors_health & 0x10000)
                
            self.on_update(self.drone)

        elif typ == "BATTERY_STATUS":
            voltages = getattr(msg, "voltages", []) or []
            valid_mv = [v for v in voltages if v != 65535 and v > 0]
            if valid_mv:
                t.battery_voltage = round(sum(valid_mv) / 1000.0, 2)
            current_ca = getattr(msg, "current_battery", -1)
            if current_ca > 0:
                t.battery_current = round(current_ca / 100.0, 2)
            elif current_ca == 0:
                t.battery_current = 0.0
            else:
                t.battery_current = None           # -1 = sensor not installed/unsupported
            batt_remaining = getattr(msg, "battery_remaining", -1)
            rep_pct = float(batt_remaining) if 0 <= batt_remaining <= 100 else None
            t.battery_percent = self._calc_battery_percent(t.battery_voltage, rep_pct)
            self.on_update(self.drone)

        elif typ == "MISSION_CURRENT":
            # Track active waypoint index (update drone firmware info if needed)
            pass

        elif typ in ("MISSION_REQUEST", "MISSION_REQUEST_INT", "MISSION_ACK"):
            try:
                self._mission_msg_queue.put_nowait(msg)
            except Exception:
                pass

        elif typ == "COMMAND_ACK":
            # Route to the ACK queue so waiting commands can read their result
            try:
                self._ack_queue.put_nowait(msg)
            except Exception:
                pass

        elif typ == "STATUSTEXT":
            text = msg.text.rstrip("\x00")
            # Buffer recent statustext for rejection reason retrieval
            self._recent_statustext.append(text)
            if len(self._recent_statustext) > 10:
                self._recent_statustext.pop(0)
            if text.startswith("PreArm:") or text.startswith("Arm:"):
                logger.warning("DRONE %s PRE-ARM: %s", self.drone.name, text)
            else:
                logger.info(
                    "DRONE %s STATUS: [%s] %s",
                    self.drone.name,
                    getattr(msg, "severity", "?"),
                    text,
                )

    # ---- GCS heartbeat loop ------------------------------------------------
    async def _heartbeat_loop(self) -> None:
        """Send GCS heartbeat every second to keep autopilot happy."""
        from pymavlink import mavutil as _mu
        while self._running:
            try:
                if self._mav:
                    self._mav.mav.heartbeat_send(
                        _mu.mavlink.MAV_TYPE_GCS,
                        _mu.mavlink.MAV_AUTOPILOT_INVALID,
                        0, 0, 0,
                    )
            except Exception:
                pass
            await asyncio.sleep(self.HEARTBEAT_INTERVAL)

    # ---- reconnect loop ----------------------------------------------------
    async def _reconnect_loop(self) -> None:
        """Attempt to reconnect if connection drops."""
        # Loop while we are NOT running (i.e. disconnected/error state)
        while not self._running:
            if self.drone.last_error and "locked by another program" in self.drone.last_error:
                break
            logger.info("MavlinkWorker %s reconnecting in %.0fs…", self.drone.id, self.RECONNECT_DELAY)
            self.drone.status = "connecting"
            self.on_update(self.drone)
            await asyncio.sleep(self.RECONNECT_DELAY)
            try:
                await self._open_link()
                self._running = True
                self.drone.status = "connected"
                self.drone.last_error = None
                self.on_update(self.drone)
                self._hb_task = asyncio.create_task(self._heartbeat_loop(), name=f"mav-hb-{self.drone.id}")
                self._rx_task  = asyncio.create_task(self._receive_loop(),   name=f"mav-rx-{self.drone.id}")
                logger.info("MavlinkWorker %s reconnected", self.drone.id)
                return
            except Exception as exc:
                logger.warning("MavlinkWorker %s reconnect failed: %s", self.drone.id, exc)
                self.drone.status = "error"
                if not self.drone.last_error:
                    self.drone.last_error = str(exc)
                self.on_update(self.drone)

    # ---- MAVLink command helpers --------------------------------------------
    def _send_command_long(
        self, command: int, *params, confirmation: int = 0
    ) -> None:
        """Send MAV_CMD as COMMAND_LONG (7 float params)."""
        p = list(params) + [0.0] * (7 - len(params))
        self._mav.mav.command_long_send(
            self._mav.target_system,
            self._mav.target_component,
            command, confirmation,
            *p[:7],
        )

    def _require_mav(self) -> None:
        if self._mav is None or not self._running or self.drone.status != "connected":
            err = f"Drone '{self.drone.name}' is not connected (status: {self.drone.status})"
            if self.drone.last_error:
                err += f" - {self.drone.last_error}"
            raise RuntimeError(err)

    async def _wait_for_ack(self, command_id: int, timeout: float = 5.0) -> None:
        """
        Wait for COMMAND_ACK matching command_id.
        Raises RuntimeError with the actual rejection reason if the FC rejects the command.
        MAV_RESULT values: 0=ACCEPTED, 1=TEMPORARILY_REJECTED, 2=DENIED, 3=UNSUPPORTED, 4=FAILED
        """
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                # Gather any recent statustext for context
                recent = "; ".join(self._recent_statustext[-3:]) if self._recent_statustext else ""
                hint = f" ({recent})" if recent else ""
                raise TimeoutError(
                    f"No COMMAND_ACK received for command {command_id} within {timeout}s{hint}"
                )
            try:
                msg = await asyncio.wait_for(self._ack_queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                recent = "; ".join(self._recent_statustext[-3:]) if self._recent_statustext else ""
                hint = f" ({recent})" if recent else ""
                raise TimeoutError(
                    f"No COMMAND_ACK received for command {command_id} within {timeout}s{hint}"
                )

            # Match the command we sent (older FW may not include command field)
            ack_cmd = getattr(msg, "command", None)
            if ack_cmd is not None and ack_cmd != command_id:
                # Stale ACK from a different command — discard and keep waiting.
                # (Do NOT put it back — that causes an infinite loop.)
                await asyncio.sleep(0.02)
                continue

            result = getattr(msg, "result", -1)
            if result == 0:  # MAV_RESULT_ACCEPTED
                return

            # Build rejection message with any statustext context
            result_names = {
                1: "TEMPORARILY_REJECTED",
                2: "DENIED",
                3: "UNSUPPORTED",
                4: "FAILED",
                5: "IN_PROGRESS",
            }
            result_str = result_names.get(result, f"RESULT_{result}")
            # Find most relevant statustext (PreArm: / Arm: lines)
            prearm_msgs = [
                s for s in self._recent_statustext
                if s.startswith("PreArm:") or s.startswith("Arm:")
            ]
            detail = prearm_msgs[-1] if prearm_msgs else (
                self._recent_statustext[-1] if self._recent_statustext else ""
            )
            raise RuntimeError(
                f"Command {command_id} rejected: {result_str}"
                + (f" — {detail}" if detail else "")
            )

    # ---- flight commands ---------------------------------------------------
    async def arm(self) -> None:
        """ARM the drone. Waits for COMMAND_ACK and verifies heartbeat confirms armed==True."""
        self._require_mav()
        loop = asyncio.get_running_loop()
        # Clear stale ACKs
        while not self._ack_queue.empty():
            try:
                self._ack_queue.get_nowait()
            except Exception:
                break
        self._recent_statustext.clear()

        self.drone.telemetry.flight_state = "ARMING"
        self.on_update(self.drone)

        await loop.run_in_executor(
            None,
            lambda: self._send_command_long(
                400,  # MAV_CMD_COMPONENT_ARM_DISARM
                1.0,  # param1: 1=arm
                0.0,  # param2: 0=normal arm (not force)
            ),
        )
        logger.info("ARM command sent to %s", self.drone.name)

        # Wait for COMMAND_ACK — raises RuntimeError with actual reason if rejected
        await self._wait_for_ack(400, timeout=5.0)

        # Verify heartbeat confirms armed == True (up to 3 seconds)
        for _ in range(15):
            if self.drone.telemetry.armed:
                break
            await asyncio.sleep(0.2)
        if not self.drone.telemetry.armed:
            raise RuntimeError(
                "ARM command was accepted but heartbeat never confirmed armed state"
            )

        self.drone.telemetry.flight_state = "ARMED"
        self.on_update(self.drone)
        logger.info("ARMED confirmed on %s", self.drone.name)

    async def disarm(self) -> None:
        """DISARM the drone. Sends DISARM command, verifies heartbeat confirms armed==False."""
        self._require_mav()

        # If already disarmed, consider it success immediately
        if not self.drone.telemetry.armed:
            self.drone.telemetry.flight_state = "DISARMED"
            self.on_update(self.drone)
            logger.info("Drone %s already disarmed", self.drone.name)
            return

        loop = asyncio.get_running_loop()
        # Clear stale ACKs before sending
        while not self._ack_queue.empty():
            try:
                self._ack_queue.get_nowait()
            except Exception:
                break

        await loop.run_in_executor(
            None,
            lambda: self._send_command_long(400, 0.0, 0.0),
        )
        logger.info("DISARM command sent to %s", self.drone.name)

        # Wait for ACK — handle DENIED gracefully (may already be disarmed)
        try:
            await self._wait_for_ack(400, timeout=5.0)
        except RuntimeError as exc:
            # If FC says DENIED/TEMPORARILY_REJECTED but drone is already disarmed
            # (e.g. FC auto-disarmed after landing), treat as success
            if not self.drone.telemetry.armed:
                logger.info("DISARM ACK non-zero but drone already disarmed: %s", exc)
            else:
                raise

        # Verify heartbeat confirms armed == False (up to 3 seconds)
        for _ in range(15):
            if not self.drone.telemetry.armed:
                break
            await asyncio.sleep(0.2)

        self.drone.telemetry.flight_state = "DISARMED"
        self.on_update(self.drone)
        logger.info("DISARMED confirmed on %s", self.drone.name)

    async def takeoff(self, altitude: float = 10.0) -> None:
        """
        Command the drone to take off to the specified altitude.

        Preconditions (raises RuntimeError if violated):
          - Drone must be connected.
          - Drone must already be armed (call arm() first).
          - Altitude must be > 0 and <= MAX_TAKEOFF_ALTITUDE.

        Does NOT auto-arm, does NOT land after reaching altitude.
        """
        self._require_mav()
        t = self.drone.telemetry

        if not t.armed:
            raise RuntimeError(
                "Drone is not armed. Click ARM first, then click TAKEOFF."
            )
        if altitude <= 0:
            raise RuntimeError("Takeoff altitude must be greater than 0 metres.")
        if altitude > MAX_TAKEOFF_ALTITUDE:
            raise RuntimeError(
                f"Requested altitude {altitude:.1f}m exceeds safety limit of "
                f"{MAX_TAKEOFF_ALTITUDE:.0f}m. Reduce the takeoff altitude."
            )

        loop = asyncio.get_running_loop()

        # Clear stale ACKs
        while not self._ack_queue.empty():
            try:
                self._ack_queue.get_nowait()
            except Exception:
                break

        # Switch to GUIDED mode (required for MAV_CMD_NAV_TAKEOFF on ArduCopter)
        await loop.run_in_executor(None, lambda: self._set_mode("GUIDED"))
        await asyncio.sleep(0.3)

        self.drone.telemetry.flight_state = "TAKEOFF_REQUESTED"
        self.on_update(self.drone)

        # MAV_CMD_NAV_TAKEOFF (22)
        # param1: min pitch (deg) — 0 for copter
        # param2: empty
        # param3: empty
        # param4: yaw angle — NaN to keep current
        # param5: lat — 0 means use current position
        # param6: lon — 0 means use current position
        # param7: altitude (metres, relative to home)
        #
        # BUG FIX: Previous code incorrectly passed home_lat/home_lon into params 5&6.
        # This caused ArduPilot to navigate to home as a waypoint then land.
        # Correct: pass 0 (or NaN) so the FC uses the current position.
        await loop.run_in_executor(
            None,
            lambda: self._send_command_long(
                22,        # MAV_CMD_NAV_TAKEOFF
                0.0,       # param1: min pitch
                0.0,       # param2: empty
                0.0,       # param3: empty
                float("nan"),  # param4: yaw (NaN = keep current)
                0.0,       # param5: lat (0 = current position)
                0.0,       # param6: lon (0 = current position)
                float(altitude),  # param7: target altitude in metres AGL
            ),
        )
        logger.info("MAV_CMD_NAV_TAKEOFF sent to %s (target: %.1fm)", self.drone.name, altitude)

        # Wait for COMMAND_ACK
        await self._wait_for_ack(22, timeout=5.0)

        self.drone.telemetry.flight_state = "TAKING_OFF"
        self.on_update(self.drone)
        logger.info("TAKEOFF accepted by %s — climbing to %.1fm", self.drone.name, altitude)

    async def land(self) -> None:
        """Command the drone to land at current position."""
        self._require_mav()
        loop = asyncio.get_running_loop()

        self.drone.telemetry.flight_state = "LANDING"
        self.on_update(self.drone)

        # Prefer set_mode("LAND") — more reliable on ArduCopter than MAV_CMD_NAV_LAND.
        # Fall back to COMMAND_LONG if mode mapping is unavailable.
        try:
            await loop.run_in_executor(None, lambda: self._set_mode("LAND"))
            logger.info("LAND mode set on %s", self.drone.name)
        except Exception as mode_err:
            logger.warning(
                "set_mode(LAND) failed on %s (%s), trying MAV_CMD_NAV_LAND",
                self.drone.name, mode_err,
            )
            await loop.run_in_executor(
                None,
                lambda: self._send_command_long(21),  # MAV_CMD_NAV_LAND
            )
            logger.info("MAV_CMD_NAV_LAND sent to %s", self.drone.name)

    async def hold(self) -> None:
        self._require_mav()
        await asyncio.get_running_loop().run_in_executor(
            None, lambda: self._set_mode("LOITER")
        )

    async def rtl(self) -> None:
        self._require_mav()
        await asyncio.get_running_loop().run_in_executor(
            None, lambda: self._set_mode("RTL")
        )
        logger.info("RTL sent to %s", self.drone.name)

    async def emergency_stop(self) -> None:
        self._require_mav()
        # Force disarm even in air (param2=21196 = magic safety override)
        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: self._send_command_long(400, 0.0, 21196.0),
        )
        logger.warning("EMERGENCY STOP sent to %s", self.drone.name)

    async def level_horizon(self) -> None:
        """Send MAV_CMD_PREFLIGHT_CALIBRATION (param5=1) to level accelerometers / horizon."""
        self._require_mav()
        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: self._send_command_long(
                241,  # MAV_CMD_PREFLIGHT_CALIBRATION
                0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0
            ),
        )
        logger.info("LEVEL HORIZON sent to %s", self.drone.name)

    async def set_velocity(self, forward: float, right: float, up: float, yaw_rate: float) -> None:
        """Send SET_POSITION_TARGET_LOCAL_NED velocity command."""
        self._require_mav()
        from pymavlink import mavutil as _mu
        # type_mask: bits 0-2 ignore position, bits 3-5 use velocity, bits 6-8 ignore accel,
        # bit 10 use yaw_rate. Value 0b110000111000 = 0x0FC7 (ignore pos+accel, use vel+yaw_rate)
        type_mask = 0x0FC7  # ignore pos (bits 0-2) + accel (bits 6-8), use vx/vy/vz + yaw_rate

        # Convert body-frame to NED by using current heading
        hdg = math.radians(self.drone.telemetry.heading)
        vx = forward * math.cos(hdg) - right * math.sin(hdg)  # North
        vy = forward * math.sin(hdg) + right * math.cos(hdg)  # East
        vz = -up  # NED: down is positive

        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: self._mav.mav.set_position_target_local_ned_send(
                0,  # time_boot_ms (ignored)
                self._mav.target_system,
                self._mav.target_component,
                _mu.mavlink.MAV_FRAME_LOCAL_NED,
                int(type_mask),
                0, 0, 0,        # position (ignored)
                vx, vy, vz,     # velocity m/s
                0, 0, 0,        # acceleration (ignored)
                0, math.radians(yaw_rate),  # yaw, yaw_rate
            ),
        )

    def _set_mode(self, mode_str: str) -> None:
        """Set flight mode by name (ArduPilot or PX4)."""
        if self._mav is None:
            return
        mode_id = self._mav.mode_mapping().get(mode_str)
        if mode_id is None:
            # Try case-insensitive fallback
            mapping = {k.upper(): v for k, v in self._mav.mode_mapping().items()}
            mode_id = mapping.get(mode_str.upper())
        if mode_id is None:
            raise ValueError(f"Unknown flight mode: {mode_str}")
        self._mav.set_mode(mode_id)

    # ---- mission upload ----------------------------------------------------
    async def upload_mission(self, waypoints: list[Waypoint]) -> None:
        self._require_mav()
        self._mission_buffer = waypoints
        loop = asyncio.get_running_loop()
        from pymavlink import mavutil as _mu

        count = len(waypoints)
        logger.info("Mission upload started")
        logger.info(f"Mission contains {count} waypoints")
        logger.info("Sending mission to vehicle")

        # Clear the queue of any stale messages
        while not self._mission_msg_queue.empty():
            try:
                self._mission_msg_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        try:
            # Send mission count
            await loop.run_in_executor(
                None,
                lambda: self._mav.mav.mission_count_send(
                    self._mav.target_system, self._mav.target_component, count, 0
                )
            )

            while True:
                try:
                    msg = await asyncio.wait_for(self._mission_msg_queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    raise TimeoutError("Mission upload timed out waiting for drone response")

                if msg.get_type() in ("MISSION_REQUEST", "MISSION_REQUEST_INT"):
                    seq = msg.seq
                    if seq >= len(waypoints):
                        raise RuntimeError(f"Drone requested invalid waypoint index {seq}")
                    wp = waypoints[seq]
                    await loop.run_in_executor(
                        None,
                        lambda seq=seq, wp=wp: self._mav.mav.mission_item_int_send(
                            self._mav.target_system,
                            self._mav.target_component,
                            seq,                                    # seq
                            _mu.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                            _mu.mavlink.MAV_CMD_NAV_WAYPOINT,
                            0,                                    # current
                            1,                                    # auto-continue
                            wp.hold_seconds,                      # param1 hold time
                            0, 0,                                 # param2 accept radius, param3 pass radius
                            float("nan"),                         # param4 yaw
                            int(wp.latitude  * 1e7),              # x = lat
                            int(wp.longitude * 1e7),              # y = lon
                            wp.altitude,                          # z = altitude (relative)
                            0,                                    # mission_type
                        )
                    )
                elif msg.get_type() == "MISSION_ACK":
                    if msg.type != 0:
                        raise RuntimeError(f"Mission upload rejected: type={msg.type}")
                    logger.info("Mission upload completed")
                    break
        except Exception:
            logger.exception("Mission upload failed")
            raise

    async def start_mission(self) -> None:
        """Start the uploaded mission. Drone must already be armed."""
        self._require_mav()
        loop = asyncio.get_running_loop()
        t = self.drone.telemetry

        logger.info(
            "Start Mission: Mode=%s, Armed=%s, GPS Fix=%s, EKF OK=%s",
            t.flight_mode, t.armed, t.gps_fix, t.ekf_ok,
        )

        if not t.armed:
            raise RuntimeError(
                "Drone is not armed. ARM the drone before starting a mission."
            )

        # Switch to AUTO
        await loop.run_in_executor(None, lambda: self._set_mode("AUTO"))

        # Send MISSION_START
        await loop.run_in_executor(
            None,
            lambda: self._send_command_long(
                300,   # MAV_CMD_MISSION_START
                0, 0,
            ),
        )
        self.drone.telemetry.flight_state = "MISSION_ACTIVE"
        self.on_update(self.drone)
        logger.info("MISSION START sent to %s", self.drone.name)

    async def pause_mission(self) -> None:
        self._require_mav()
        await asyncio.get_running_loop().run_in_executor(
            None, lambda: self._set_mode("LOITER")
        )

    async def resume_mission(self) -> None:
        self._require_mav()
        await asyncio.get_running_loop().run_in_executor(
            None, lambda: self._set_mode("AUTO")
        )

    async def stop_mission(self) -> None:
        self._require_mav()
        await asyncio.get_running_loop().run_in_executor(
            None, lambda: self._set_mode("LOITER")
        )

    async def clear_mission(self) -> None:
        self._require_mav()
        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: self._mav.mav.mission_clear_all_send(
                self._mav.target_system, self._mav.target_component
            ),
        )
        logger.info("MISSION CLEAR sent to %s", self.drone.name)

    async def set_flight_mode(self, mode: str) -> None:
        """Switch flight mode by name (ArduCopter or PX4)."""
        self._require_mav()
        await asyncio.get_running_loop().run_in_executor(
            None, lambda: self._set_mode(mode.upper())
        )
        logger.info("Mode → %s sent to %s", mode.upper(), self.drone.name)
