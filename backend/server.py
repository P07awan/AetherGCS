"""GCS Backend – FastAPI + WebSocket entry point.

REST API:  /api/drones, /api/missions, /api/commands, /api/history
WebSocket: /api/ws/telemetry (broadcasts full drone state at ~5 Hz)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from gcs.command_log import CommandLogStore
from gcs.db import close_db
from gcs.drone_manager import DroneManager
from gcs.mission_manager import MissionManager
from gcs.kml_parser import parse_kml_content, parse_kmz_file
from gcs.models import (
    CommandLog,
    CommandRequest,
    ConnectionProfile,
    Drone,
    DroneCreate,
    Mission,
    MissionCreate,
    Waypoint,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("gcs")

app = FastAPI(title="Multi-Drone GCS")
api = APIRouter(prefix="/api")

drone_manager = DroneManager()
mission_manager = MissionManager()
command_log = CommandLogStore()


# ---------------------------------------------------------------------------
# WebSocket broadcaster
# ---------------------------------------------------------------------------
class Broadcaster:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self._queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=1000)
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="ws-broadcaster")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    def push(self, event: str, payload) -> None:
        try:
            self._queue.put_nowait({"event": event, "data": payload})
        except asyncio.QueueFull:
            pass

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)
        # send full snapshot on connect
        await ws.send_json({
            "event": "snapshot",
            "data": [d.model_dump() for d in drone_manager.list_drones()],
        })

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def _run(self) -> None:
        while True:
            msg = await self._queue.get()
            dead = []
            for ws in list(self.clients):
                try:
                    await ws.send_json(msg)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.disconnect(ws)


broadcaster = Broadcaster()


def _on_drone_update(drone: Drone) -> None:
    broadcaster.push("drone", drone.model_dump())


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def _startup() -> None:
    drone_manager.subscribe(_on_drone_update)
    await drone_manager.load_saved()
    await broadcaster.start()
    logger.info("GCS started with %d saved drone(s)", len(drone_manager.list_drones()))


@app.on_event("shutdown")
async def _shutdown() -> None:
    await broadcaster.stop()
    await drone_manager.shutdown()
    await close_db()


# ---------------------------------------------------------------------------
# REST – Drones
# ---------------------------------------------------------------------------
@api.get("/system/serial-ports")
async def get_system_serial_ports():
    """Detect and return available hardware COM/serial ports on host system."""
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        return [
            {
                "port": p.device,
                "description": p.description,
                "hwid": p.hwid,
                "manufacturer": getattr(p, "manufacturer", "") or "",
            }
            for p in ports
        ]
    except Exception as e:
        logger.warning("Failed to list serial ports: %s", e)
        return []


@api.get("/")
async def root():
    return {"service": "gcs", "drones": len(drone_manager.list_drones())}


@api.get("/drones", response_model=List[Drone])
async def list_drones():
    return drone_manager.list_drones()


@api.post("/drones", response_model=Drone)
async def create_drone(payload: DroneCreate):
    return await drone_manager.add_drone(payload)


@api.get("/drones/{drone_id}", response_model=Drone)
async def get_drone(drone_id: str):
    d = drone_manager.get_drone(drone_id)
    if not d:
        raise HTTPException(404, "Drone not found")
    return d


@api.delete("/drones/{drone_id}")
async def delete_drone(drone_id: str):
    await drone_manager.remove_drone(drone_id)
    broadcaster.push("drone_removed", {"id": drone_id})
    return {"ok": True}


@api.post("/drones/{drone_id}/connect", response_model=Drone)
async def connect_drone(drone_id: str):
    if not drone_manager.get_drone(drone_id):
        raise HTTPException(404, "Drone not found")
    drone = await drone_manager.connect(drone_id)
    if drone.status == "error" and drone.last_error:
        raise HTTPException(400, f"Connection failed: {drone.last_error}")
    return drone


@api.post("/drones/{drone_id}/disconnect", response_model=Drone)
async def disconnect_drone(drone_id: str):
    if not drone_manager.get_drone(drone_id):
        raise HTTPException(404, "Drone not found")
    return await drone_manager.disconnect(drone_id)


class HardwareFCConnectPayload(BaseModel):
    port: str = "COM3"
    baud_rate: int = 115200
    name: str = "Hardware FC Drone"


@api.post("/drones/connect-hardware-fc", response_model=Drone)
async def connect_hardware_fc(payload: HardwareFCConnectPayload):
    """Add and connect a physical Flight Controller connected via Serial/USB/Bluetooth."""
    drone_payload = DroneCreate(
        name=payload.name,
        connection=ConnectionProfile(
            connection_type="serial",
            address=payload.port,
            baud_rate=payload.baud_rate,
            auto_reconnect=True,
        )
    )
    drone = await drone_manager.add_drone(drone_payload)
    connected_drone = await drone_manager.connect(drone.id)
    return connected_drone


# ---------------------------------------------------------------------------
# REST – Commands
# ---------------------------------------------------------------------------
@api.post("/commands")
async def send_command(req: CommandRequest):
    ids = req.drone_ids
    if not ids:
        raise HTTPException(400, "drone_ids required")

    logs: list[CommandLog] = []
    for did in ids:
        d = drone_manager.get_drone(did)
        if not d:
            continue
        logs.append(CommandLog(
            drone_id=did, drone_name=d.name, command=req.command, params=req.params, status="sent"
        ))

    start = time.time()
    err_detail = None
    try:
        await drone_manager.send_command(ids, req.command, req.params)
        elapsed = int((time.time() - start) * 1000)
        for lg in logs:
            lg.status = "success"
            lg.response_ms = elapsed
    except Exception as e:  # noqa: BLE001
        err_detail = str(e)
        elapsed = int((time.time() - start) * 1000)
        for lg in logs:
            lg.status = "failed"
            lg.error = err_detail
            lg.response_ms = elapsed

    for lg in logs:
        await command_log.add(lg)
        broadcaster.push("command", lg.model_dump())

    if err_detail:
        raise HTTPException(400, detail=err_detail)

    return {"ok": True, "count": len(logs)}


@api.get("/history", response_model=List[CommandLog])
async def get_history(limit: int = 200):
    return await command_log.list(limit=limit)


@api.delete("/history")
async def clear_history():
    await command_log.clear()
    return {"ok": True}


# ---------------------------------------------------------------------------
# REST – Missions
# ---------------------------------------------------------------------------
@api.get("/missions", response_model=List[Mission])
async def list_missions():
    return await mission_manager.list()


@api.post("/missions", response_model=Mission)
async def create_mission(payload: MissionCreate):
    return await mission_manager.create(payload)


@api.get("/missions/{mid}", response_model=Mission)
async def get_mission(mid: str):
    m = await mission_manager.get(mid)
    if not m:
        raise HTTPException(404, "Mission not found")
    return m


@api.put("/missions/{mid}", response_model=Mission)
async def update_mission(mid: str, payload: MissionCreate):
    m = await mission_manager.update(mid, payload)
    if not m:
        raise HTTPException(404, "Mission not found")
    return m


@api.delete("/missions/{mid}")
async def delete_mission(mid: str):
    ok = await mission_manager.delete(mid)
    if not ok:
        raise HTTPException(404, "Mission not found")
    return {"ok": True}


@api.post("/missions/{mid}/duplicate", response_model=Mission)
async def duplicate_mission(mid: str):
    m = await mission_manager.duplicate(mid)
    if not m:
        raise HTTPException(404, "Mission not found")
    return m


@api.post("/missions/import-kml", response_model=Mission)
async def import_kml_mission(file: UploadFile = File(...)):
    """Import a .kml or .kmz file, parse waypoints, create and save mission."""
    filename = file.filename or "uploaded.kml"
    content = await file.read()
    try:
        if filename.lower().endswith(".kmz"):
            mission_create = parse_kmz_file(content)
        else:
            kml_text = content.decode("utf-8", errors="ignore")
            mission_create = parse_kml_content(kml_text)
        if not mission_create.name or mission_create.name == "Imported KML Mission":
            mission_create.name = Path(filename).stem.replace("_", " ").title()
        return await mission_manager.create(mission_create)
    except Exception as e:
        logger.error("KML import failed: %s", e)
        raise HTTPException(400, detail=f"Invalid KML file: {str(e)}")


@api.post("/missions/auto-load-kml")
async def auto_load_kml_from_folder(folder_path: str = r"C:\Users\ASUS\Desktop\AetherGCS"):
    """Scan folder for any .kml/.kmz files and automatically create missions in GCS."""
    target_dir = Path(folder_path)
    if not target_dir.exists():
        raise HTTPException(404, detail=f"Folder not found: {folder_path}")

    loaded_missions = []
    kml_files = list(target_dir.glob("*.kml")) + list(target_dir.glob("*.kmz"))
    
    for kml_file in kml_files:
        try:
            if kml_file.suffix.lower() == ".kmz":
                mission_create = parse_kmz_file(kml_file.read_bytes())
            else:
                mission_create = parse_kml_content(kml_file.read_text(encoding="utf-8", errors="ignore"))
            
            if not mission_create.name or mission_create.name == "Imported KML Mission":
                mission_create.name = kml_file.stem.replace("_", " ").title()
                
            m = await mission_manager.create(mission_create)
            loaded_missions.append(m)
        except Exception as e:
            logger.warning("Failed to parse %s: %s", kml_file.name, e)

    return {"ok": True, "count": len(loaded_missions), "missions": loaded_missions}


@api.post("/missions/{mid}/auto-execute")
async def auto_execute_mission(mid: str):
    """Automatically upload mission waypoints to connected FC or SITL simulator drone, arm, and start mission."""
    mission = await mission_manager.get(mid)
    if not mission:
        raise HTTPException(404, "Mission not found")

    drones = drone_manager.list_drones()
    target_drone = None
    for d in drones:
        if d.status == "connected":
            target_drone = d
            break

    if not target_drone:
        # Check if hardware FC serial port is available on host system
        try:
            import serial.tools.list_ports
            com_ports = [p.device for p in serial.tools.list_ports.comports()]
        except Exception:
            com_ports = []

        if com_ports:
            hw_port = com_ports[0]
            fc_drone_payload = DroneCreate(
                name=f"Hardware FC ({hw_port})",
                connection=ConnectionProfile(
                    connection_type="serial",
                    address=hw_port,
                    baud_rate=115200,
                    auto_reconnect=True,
                )
            )
            try:
                hw_drone = await drone_manager.add_drone(fc_drone_payload)
                hw_drone = await drone_manager.connect(hw_drone.id)
                # Wait up to 1.5s for heartbeat if hardware FC is live
                for _ in range(15):
                    latest_d = drone_manager.get_drone(hw_drone.id)
                    if latest_d and latest_d.status == "connected":
                        target_drone = latest_d
                        logger.info("Connected to Hardware Flight Controller on %s", hw_port)
                        break
                    await asyncio.sleep(0.1)
            except Exception as fc_err:
                logger.warning("Hardware FC connection on %s failed: %s", hw_port, fc_err)

        if not target_drone:
            # Fall back to active simulator drone
            first_lat = mission.waypoints[0].latitude if mission.waypoints else 28.6751
            first_lon = mission.waypoints[0].longitude if mission.waypoints else 77.5023
            new_drone_payload = DroneCreate(
                name="AeroForge Survey UAV-1",
                home_lat=first_lat,
                home_lon=first_lon,
                connection=ConnectionProfile(connection_type="simulator")
            )
            target_drone = await drone_manager.add_drone(new_drone_payload)
            target_drone = await drone_manager.connect(target_drone.id)

    did = target_drone.id
    cmd_status = "MISSION_STARTED"
    err_msg = None

    try:
        await drone_manager.send_command([did], "upload_mission", {"waypoints": [w.model_dump() for w in mission.waypoints]})
        await asyncio.sleep(0.3)
        await drone_manager.send_command([did], "arm", {})
        await asyncio.sleep(0.3)
        await drone_manager.send_command([did], "start_mission", {})
    except Exception as cmd_err:
        logger.warning("Command execution warning for drone %s: %s", did, cmd_err)
        cmd_status = "MISSION_LOADED_FC_WAITING"
        err_msg = str(cmd_err)

    return {
        "ok": True,
        "drone_id": did,
        "drone_name": target_drone.name,
        "mission_id": mid,
        "status": cmd_status,
        "waypoints_count": len(mission.waypoints),
        "note": err_msg or "Mission uploaded successfully."
    }


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
@api.websocket("/ws/telemetry")
async def ws_telemetry(ws: WebSocket):
    await broadcaster.connect(ws)
    try:
        while True:
            # keep-alive; client may send ping
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_json({"event": "pong", "data": time.time()})
    except WebSocketDisconnect:
        broadcaster.disconnect(ws)
    except Exception:
        broadcaster.disconnect(ws)



app.include_router(api)

_cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
_allow_credentials = _cors_origins != ["*"]  # credentials=True is invalid with wildcard origins
app.add_middleware(
    CORSMiddleware,
    allow_credentials=_allow_credentials,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)