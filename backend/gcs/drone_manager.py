"""DroneManager – orchestrates DroneWorkers and persists drone state."""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, Iterable, List, Optional

from .db import get_db
from .drone_worker import DroneWorker, SimulatorWorker, MavlinkWorker
from .models import Drone, DroneCreate, Waypoint

logger = logging.getLogger(__name__)


class DroneManager:
    def __init__(self) -> None:
        self.workers: Dict[str, DroneWorker] = {}
        self._listeners: list = []
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
        try:
            db = get_db()
            docs = await db.drones.find({}, {"_id": 0}).to_list(1000)
            for doc in docs:
                try:
                    drone = Drone(**doc)
                    drone.status = "disconnected"
                    ct = drone.connection.connection_type
                    if ct == "simulator":
                        worker: DroneWorker = SimulatorWorker(drone, on_update=self._emit)
                    else:
                        worker = MavlinkWorker(drone, on_update=self._emit)
                    self.workers[drone.id] = worker
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


    # ---- CRUD ----------------------------------------------------------
    async def add_drone(self, payload: DroneCreate) -> Drone:
        async with self._lock:
            drone = Drone(
                name=payload.name,
                system_id=payload.system_id,
                component_id=payload.component_id,
                connection=payload.connection,
                home_lat=payload.home_lat,
                home_lon=payload.home_lon,
                home_alt=payload.home_alt,
            )
            if payload.connection.connection_type == "simulator":
                worker: DroneWorker = SimulatorWorker(drone, on_update=self._emit)
            else:
                worker = MavlinkWorker(drone, on_update=self._emit)
            self.workers[drone.id] = worker
            await self._persist(drone)
            self._emit(drone)
            return drone

    async def remove_drone(self, drone_id: str) -> None:
        worker = self.workers.get(drone_id)
        if not worker:
            return
        await worker.disconnect()
        del self.workers[drone_id]
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
    async def send_command(self, drone_ids: Iterable[str], command: str, params: dict) -> None:
        tasks = []
        for did in drone_ids:
            worker = self.workers.get(did)
            if not worker:
                continue
            # Auto-connect simulator worker if not connected
            if worker.drone.status != "connected" and isinstance(worker, SimulatorWorker):
                await worker.connect()
            tasks.append(self._dispatch(worker, command, params))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        errors = [r for r in results if isinstance(r, Exception)]
        if errors:
            raise errors[0]

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
        else:
            raise ValueError(f"Unknown command: {command}")

    async def shutdown(self) -> None:
        await asyncio.gather(*[w.disconnect() for w in self.workers.values()], return_exceptions=True)
