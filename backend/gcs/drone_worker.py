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
        self._velocity_body = [0.0, 0.0, 2.0]
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

        # takeoff auto-level
        if t.altitude_relative >= self._takeoff_target and t.flight_mode == "GUIDED":
            self._velocity_body[2] = 0.0
            t.flight_mode = "LOITER"

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
            self.on_update(self.drone)

        elif typ == "GLOBAL_POSITION_INT":
            t.latitude          = msg.lat  / 1e7
            t.longitude         = msg.lon  / 1e7
            t.altitude_msl      = msg.alt  / 1000.0
            t.altitude_relative = msg.relative_alt / 1000.0
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

        elif typ == "STATUSTEXT":
            logger.info(
                "DRONE %s STATUS: [%s] %s",
                self.drone.name,
                getattr(msg, "severity", "?"),
                msg.text.rstrip("\x00"),
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

    # ---- flight commands ---------------------------------------------------
    async def arm(self) -> None:
        self._require_mav()
        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: self._send_command_long(
                400,  # MAV_CMD_COMPONENT_ARM_DISARM
                1.0,  # arm
            ),
        )
        logger.info("ARM sent to %s", self.drone.name)

    async def disarm(self) -> None:
        self._require_mav()
        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: self._send_command_long(400, 0.0),
        )
        logger.info("DISARM sent to %s", self.drone.name)

    async def takeoff(self, altitude: float = 15.0) -> None:
        self._require_mav()
        loop = asyncio.get_running_loop()
        # Set GUIDED mode first
        await loop.run_in_executor(None, lambda: self._set_mode("GUIDED"))
        await asyncio.sleep(0.3)
        # ARM
        await self.arm()
        await asyncio.sleep(0.5)
        # NAV_TAKEOFF
        await loop.run_in_executor(
            None,
            lambda: self._send_command_long(
                22,   # MAV_CMD_NAV_TAKEOFF
                0, 0, 0, 0,
                self.drone.home_lat,
                self.drone.home_lon,
                altitude,
            ),
        )
        logger.info("TAKEOFF to %.1fm sent to %s", altitude, self.drone.name)

    async def land(self) -> None:
        self._require_mav()
        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: self._send_command_long(21),  # MAV_CMD_NAV_LAND
        )
        logger.info("LAND sent to %s", self.drone.name)

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

        count = len(waypoints)
        logger.info("Uploading %d waypoints to %s", count, self.drone.name)

        await loop.run_in_executor(
            None,
            lambda: self._do_upload_mission(waypoints),
        )

    def _do_upload_mission(self, waypoints: list[Waypoint]) -> None:
        """Blocking mission upload using MAVLink mission protocol."""
        from pymavlink import mavutil as _mu

        mav = self._mav
        count = len(waypoints)

        # Send mission count
        mav.mav.mission_count_send(mav.target_system, mav.target_component, count, 0)

        for i, wp in enumerate(waypoints):
            # Wait for MISSION_REQUEST_INT
            req = mav.recv_match(type=["MISSION_REQUEST", "MISSION_REQUEST_INT"], blocking=True, timeout=5)
            if req is None:
                raise TimeoutError(f"No MISSION_REQUEST for item {i}")

            # Build MAVLink MISSION_ITEM_INT
            mav.mav.mission_item_int_send(
                mav.target_system,
                mav.target_component,
                i,                                    # seq
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

        # Wait for MISSION_ACK
        ack = mav.recv_match(type="MISSION_ACK", blocking=True, timeout=5)
        if ack is None:
            raise TimeoutError("No MISSION_ACK after upload")
        if ack.type != 0:  # MAV_MISSION_ACCEPTED = 0
            raise RuntimeError(f"Mission upload rejected: type={ack.type}")
        logger.info("Mission upload acknowledged by %s", self.drone.name)

    async def start_mission(self) -> None:
        self._require_mav()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: self._set_mode("AUTO"))
        await loop.run_in_executor(
            None,
            lambda: self._send_command_long(
                300,   # MAV_CMD_MISSION_START
                0, 0,
            ),
        )
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
