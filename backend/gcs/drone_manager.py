"""DroneManager – orchestrates DroneWorkers and persists drone state."""
from __future__ import annotations

import asyncio
import logging
import math
from typing import Dict, Iterable, List, Optional

from fastapi import HTTPException

from .db import get_db
from .drone_worker import DroneWorker, SimulatorWorker, MavlinkWorker
from .models import Drone, DroneCreate, Waypoint

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Endpoint normalisation helpers
# ---------------------------------------------------------------------------

_LOCAL_ADDRS = {"", "0.0.0.0", "127.0.0.1", "localhost"}


def _norm_addr(addr: str) -> str:
    """Normalise local-loopback variants to a single canonical token."""
    cleaned = (addr or "").strip().lower()
    return "127.0.0.1" if cleaned in _LOCAL_ADDRS else cleaned


def _norm_serial(path: str) -> str:
    """Normalise serial port path for comparison (case-insensitive, stripped)."""
    return (path or "").strip().upper()


class DroneManager:
    def __init__(self) -> None:
        self.workers: Dict[str, DroneWorker] = {}
        self._listeners: list = []
        # One lock guards ALL state mutations (add / remove / connect).
        # The check-then-create section MUST stay inside the lock.
        self._lock = asyncio.Lock()

    # ---- events --------------------------------------------------------
    def subscribe(self, callback) -> None:
        self._listeners.append(callback)

    def unsubscribe(self, callback) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _emit(self, drone: Drone) -> None:
        for cb in list(self._listeners):
            try:
                cb(drone)
            except Exception:
                logger.exception("listener failed")

    # ---- persistence ---------------------------------------------------
    async def load_saved(self) -> None:
        """Restore drones from MongoDB. Applies simulator position spread on restore."""
        try:
            db = get_db()
            docs = await db.drones.find({}, {"_id": 0}).to_list(1000)
            sim_count = 0  # track simulator drones loaded so far for spread
            for doc in docs:
                try:
                    drone = Drone(**doc)
                    drone.status = "disconnected"
                    ct = drone.connection.connection_type

                    if ct == "simulator":
                        # Re-apply the 20-m east spread so saved simulators don't stack
                        if sim_count > 0:
                            cos_lat = math.cos(math.radians(drone.home_lat)) or 1.0
                            # Use the first drone's base position as the reference
                            # (home_lon already stored correctly in the DB per add_drone)
                            pass  # positions already stored correctly per drone in DB
                        worker: DroneWorker = SimulatorWorker(drone, on_update=self._emit)
                        sim_count += 1
                    else:
                        worker = MavlinkWorker(drone, on_update=self._emit)

                    self.workers[drone.id] = worker
                    logger.info(
                        "Loaded saved drone id=%s name=%s type=%s",
                        drone.id, drone.name, ct,
                    )
                except Exception:
                    logger.exception("failed to load drone %s", doc.get("id"))
        except Exception as e:
            logger.warning("MongoDB unavailable for loading saved drones: %s", e)

    async def _persist(self, drone: Drone) -> None:
        try:
            db = get_db()
            doc = drone.model_dump()
            doc["trail"] = doc["trail"][-200:]
            await db.drones.update_one({"id": drone.id}, {"$set": doc}, upsert=True)
        except Exception as e:
            logger.warning("MongoDB unavailable for persisting drone %s: %s", drone.id, e)

    # ---- duplicate detection -------------------------------------------
    def _check_duplicate_system_id(self, system_id: int, exclude_id: str | None = None) -> None:
        """Raise HTTP 409 if system_id is already taken by another worker."""
        for w in self.workers.values():
            if exclude_id and w.drone.id == exclude_id:
                continue
            if w.drone.system_id == system_id:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"System ID {system_id} is already assigned to drone "
                        f"'{w.drone.name}' (id={w.drone.id}). "
                        "Each drone must have a unique MAVLink system ID (1–255)."
                    ),
                )

    def _check_duplicate_endpoint(self, payload: DroneCreate, exclude_id: str | None = None) -> None:
        """Raise HTTP 409 if (connection_type, address, port) is already in use."""
        ct = payload.connection.connection_type
        if ct == "simulator":
            return  # simulators share no physical endpoint

        addr = _norm_addr(payload.connection.address)
        port = payload.connection.port

        for w in self.workers.values():
            if exclude_id and w.drone.id == exclude_id:
                continue
            wc = w.drone.connection
            if wc.connection_type != ct:
                continue

            if ct == "serial":
                if _norm_serial(wc.address) == _norm_serial(payload.connection.address):
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Serial port '{payload.connection.address}' is already used "
                            f"by drone '{w.drone.name}' (id={w.drone.id}). "
                            "Each serial drone must use a unique COM port / device path."
                        ),
                    )
            else:  # udp / tcp
                if _norm_addr(wc.address) == addr and wc.port == port:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"{ct.upper()} endpoint {addr}:{port} is already used "
                            f"by drone '{w.drone.name}' (id={w.drone.id}). "
                            "Each drone requires a unique connection endpoint. "
                            "For SITL, assign a different UDP port per drone "
                            "(e.g. 14550, 14551, 14552…)."
                        ),
                    )

    # ---- CRUD ----------------------------------------------------------
    async def add_drone(self, payload: DroneCreate) -> Drone:
        # The entire check + create block is atomic under the lock so that two
        # simultaneous requests cannot both pass validation and then both create
        # a duplicate endpoint.
        async with self._lock:
            # --- Duplicate validation (authoritative; frontend mirrors these) ---
            self._check_duplicate_system_id(payload.system_id)
            self._check_duplicate_endpoint(payload)

            lat = payload.home_lat
            lon = payload.home_lon
            if payload.connection.connection_type == "simulator":
                # Spread simulator drones ~20 m east of each other so they don't
                # stack on the map.  Only nudge if another sim is very close.
                sim_count = sum(
                    1 for w in self.workers.values()
                    if w.drone.connection.connection_type == "simulator"
                )
                if sim_count > 0:
                    for w in self.workers.values():
                        dist = math.hypot(
                            (lat - w.drone.home_lat) * 111139.0,
                            (lon - w.drone.home_lon) * 111139.0
                            * math.cos(math.radians(lat)),
                        )
                        if dist < 5.0:
                            cos_lat = math.cos(math.radians(lat)) or 1.0
                            dlon = (20.0 * sim_count) / (111139.0 * cos_lat)
                            lon = lon + dlon
                            break

            drone = Drone(
                name=payload.name,
                system_id=payload.system_id,
                component_id=payload.component_id,
                connection=payload.connection,
                home_lat=lat,
                home_lon=lon,
                home_alt=payload.home_alt,
            )

            if payload.connection.connection_type == "simulator":
                worker: DroneWorker = SimulatorWorker(drone, on_update=self._emit)
            else:
                worker = MavlinkWorker(drone, on_update=self._emit)

            self.workers[drone.id] = worker

            logger.info(
                "[Drone %s] created name=%s system_id=%s type=%s endpoint=%s:%s",
                drone.id, drone.name, drone.system_id,
                payload.connection.connection_type,
                payload.connection.address or "—",
                payload.connection.port or "—",
            )

        await self._persist(drone)
        self._emit(drone)
        return drone

    async def remove_drone(self, drone_id: str) -> None:
        async with self._lock:
            worker = self.workers.pop(drone_id, None)
        if worker:
            await worker.disconnect()
        try:
            db = get_db()
            await db.drones.delete_one({"id": drone_id})
        except Exception as e:
            logger.warning("MongoDB unavailable for remove_drone %s: %s", drone_id, e)

    def list_drones(self) -> List[Drone]:
        return [w.drone for w in self.workers.values()]

    def get_drone(self, drone_id: str) -> Optional[Drone]:
        w = self.workers.get(drone_id)
        return w.drone if w else None

    def get_worker(self, drone_id: str) -> Optional[DroneWorker]:
        return self.workers.get(drone_id)

    # ---- connection ---------------------------------------------------
    async def connect(self, drone_id: str) -> Drone:
        worker = self.workers[drone_id]
        await worker.connect()
        await self._persist(worker.drone)
        return worker.drone

    async def disconnect(self, drone_id: str) -> Drone:
        worker = self.workers[drone_id]
        await worker.disconnect()
        await self._persist(worker.drone)
        return worker.drone

    async def connect_all(self) -> None:
        await asyncio.gather(*[w.connect() for w in self.workers.values()])

    # ---- commands (broadcast) -----------------------------------------
    async def send_command(self, drone_ids: Iterable[str], command: str, params: dict) -> list[dict]:
        tasks = []
        for did in drone_ids:
            worker = self.workers.get(did)
            if not worker:
                continue
            tasks.append(self._dispatch_safe(worker, command, params))
        if not tasks:
            return []
        results = await asyncio.gather(*tasks)
        failures = [r for r in results if not r["ok"]]
        # If ALL targeted drones failed, raise the first error
        if len(failures) == len(results) and results:
            raise RuntimeError(failures[0]["error"])
        return results

    async def _dispatch_safe(self, worker: DroneWorker, command: str, params: dict) -> dict:
        cmd = command.lower()
        try:
            # Auto-connect simulator workers for convenience (testing / demo)
            if cmd not in ("connect", "disconnect") and worker.drone.status != "connected":
                if isinstance(worker, SimulatorWorker):
                    await worker.connect()
                else:
                    raise RuntimeError(
                        f"Drone '{worker.drone.name}' is disconnected. "
                        "Connect it first before sending commands."
                    )
            await self._dispatch(worker, command, params)
            return {"drone_id": worker.drone.id, "name": worker.drone.name, "ok": True}
        except Exception as exc:
            logger.warning("Command '%s' failed on drone %s: %s", command, worker.drone.name, exc)
            return {"drone_id": worker.drone.id, "name": worker.drone.name, "ok": False, "error": str(exc)}

    async def _dispatch(self, worker: DroneWorker, command: str, params: dict) -> None:
        cmd = command.lower()
        if cmd == "connect":
            await worker.connect()
        elif cmd == "disconnect":
            await worker.disconnect()
        elif cmd == "arm":
            await worker.arm()
        elif cmd == "disarm":
            await worker.disarm()
        elif cmd == "takeoff":
            await worker.takeoff(altitude=float(params.get("altitude", 15.0)))
        elif cmd == "land":
            await worker.land()
        elif cmd == "hold":
            await worker.hold()
        elif cmd == "rtl":
            await worker.rtl()
        elif cmd == "emergency_stop":
            await worker.emergency_stop()
        elif cmd == "level_horizon":
            await worker.level_horizon()
        elif cmd == "velocity":
            await worker.set_velocity(
                float(params.get("forward", 0)),
                float(params.get("right", 0)),
                float(params.get("up", 0)),
                float(params.get("yaw_rate", 0)),
            )
        elif cmd == "upload_mission":
            wps = [Waypoint(**w) for w in params.get("waypoints", [])]
            await worker.upload_mission(wps)
        elif cmd == "start_mission":
            await worker.start_mission()
        elif cmd == "pause_mission":
            await worker.pause_mission()
        elif cmd == "resume_mission":
            await worker.resume_mission()
        elif cmd == "stop_mission":
            await worker.stop_mission()
        elif cmd == "clear_mission":
            await worker.clear_mission()
        elif cmd == "set_mode":
            mode = params.get("mode", "").upper()
            if not mode:
                raise ValueError("set_mode requires a 'mode' parameter")
            await worker.set_flight_mode(mode)
        else:
            raise ValueError(f"Unknown command: {command}")

    async def shutdown(self) -> None:
        await asyncio.gather(*[w.disconnect() for w in self.workers.values()], return_exceptions=True)
