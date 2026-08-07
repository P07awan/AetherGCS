"""GCS backend API + WebSocket tests."""
import asyncio
import json
import os
import time

import pytest
import requests
import websockets

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"
WS_URL = API.replace("http", "ws") + "/ws/telemetry"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    yield s


def _create_drone(session, name="TEST_Alpha"):
    payload = {
        "name": name,
        "system_id": 1,
        "component_id": 1,
        "connection": {"connection_type": "simulator", "address": "sim://local", "port": 0},
        "home_lat": 37.7749,
        "home_lon": -122.4194,
        "home_alt": 0.0,
    }
    r = session.post(f"{API}/drones", json=payload, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()


# --- Drone CRUD & lifecycle ------------------------------------------------
class TestDrones:
    def test_list_drones_initial(self, session):
        r = session.get(f"{API}/drones", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_drone(self, session):
        d = _create_drone(session, "TEST_Create")
        assert "id" in d and len(d["id"]) > 10
        assert d["name"] == "TEST_Create"
        assert d["status"] == "disconnected"
        assert d["home_lat"] == 37.7749
        assert d["telemetry"]["armed"] is False
        # verify via GET
        r = session.get(f"{API}/drones/{d['id']}", timeout=10)
        assert r.status_code == 200
        assert r.json()["id"] == d["id"]
        session.delete(f"{API}/drones/{d['id']}", timeout=10)

    def test_connect_disconnect(self, session):
        d = _create_drone(session, "TEST_Conn")
        r = session.post(f"{API}/drones/{d['id']}/connect", timeout=10)
        assert r.status_code == 200
        # wait for telemetry ticks
        time.sleep(1.5)
        r = session.get(f"{API}/drones/{d['id']}", timeout=10)
        assert r.json()["status"] == "connected"
        r = session.post(f"{API}/drones/{d['id']}/disconnect", timeout=10)
        assert r.status_code == 200
        assert r.json()["status"] == "disconnected"
        session.delete(f"{API}/drones/{d['id']}", timeout=10)


# --- Commands ---------------------------------------------------------------
class TestCommands:
    def test_arm_takeoff_land(self, session):
        d = _create_drone(session, "TEST_Cmd")
        session.post(f"{API}/drones/{d['id']}/connect", timeout=10)
        time.sleep(0.8)

        # ARM
        r = session.post(f"{API}/commands", json={"drone_ids": [d["id"]], "command": "arm"}, timeout=10)
        assert r.status_code == 200
        time.sleep(0.5)
        t = session.get(f"{API}/drones/{d['id']}", timeout=10).json()["telemetry"]
        assert t["armed"] is True

        # TAKEOFF
        session.post(f"{API}/commands", json={"drone_ids": [d["id"]], "command": "takeoff", "params": {"altitude": 10}}, timeout=10)
        time.sleep(4)
        t = session.get(f"{API}/drones/{d['id']}", timeout=10).json()["telemetry"]
        assert t["altitude_relative"] > 1.0, f"altitude did not climb: {t['altitude_relative']}"

        # LAND
        session.post(f"{API}/commands", json={"drone_ids": [d["id"]], "command": "land"}, timeout=10)
        time.sleep(10)
        t = session.get(f"{API}/drones/{d['id']}", timeout=10).json()["telemetry"]
        assert t["altitude_relative"] <= 0.1
        assert t["armed"] is False

        session.delete(f"{API}/drones/{d['id']}", timeout=10)

    def test_emergency_stop(self, session):
        d = _create_drone(session, "TEST_ES")
        session.post(f"{API}/drones/{d['id']}/connect", timeout=10)
        time.sleep(0.8)
        session.post(f"{API}/commands", json={"drone_ids": [d["id"]], "command": "arm"}, timeout=10)
        time.sleep(0.3)
        session.post(f"{API}/commands", json={"drone_ids": [d["id"]], "command": "emergency_stop"}, timeout=10)
        time.sleep(0.5)
        t = session.get(f"{API}/drones/{d['id']}", timeout=10).json()["telemetry"]
        assert t["armed"] is False
        assert t["ground_speed"] == 0.0
        session.delete(f"{API}/drones/{d['id']}", timeout=10)

    def test_multi_drone_command(self, session):
        d1 = _create_drone(session, "TEST_M1")
        d2 = _create_drone(session, "TEST_M2")
        session.post(f"{API}/drones/{d1['id']}/connect", timeout=10)
        session.post(f"{API}/drones/{d2['id']}/connect", timeout=10)
        time.sleep(0.8)
        r = session.post(f"{API}/commands", json={"drone_ids": [d1["id"], d2["id"]], "command": "arm"}, timeout=10)
        assert r.status_code == 200
        assert r.json()["count"] == 2
        time.sleep(0.5)
        for did in (d1["id"], d2["id"]):
            t = session.get(f"{API}/drones/{did}", timeout=10).json()["telemetry"]
            assert t["armed"] is True
        session.delete(f"{API}/drones/{d1['id']}", timeout=10)
        session.delete(f"{API}/drones/{d2['id']}", timeout=10)


# --- Missions ---------------------------------------------------------------
class TestMissions:
    def test_mission_crud(self, session):
        payload = {
            "name": "TEST_Mission1",
            "description": "test",
            "default_altitude": 25.0,
            "default_speed": 6.0,
            "waypoints": [
                {"seq": 0, "latitude": 37.7749, "longitude": -122.4194, "altitude": 20, "action": "waypoint"},
                {"seq": 1, "latitude": 37.7750, "longitude": -122.4195, "altitude": 20, "action": "waypoint"},
            ],
        }
        r = session.post(f"{API}/missions", json=payload, timeout=10)
        assert r.status_code == 200
        m = r.json()
        assert len(m["waypoints"]) == 2
        mid = m["id"]

        # list
        r = session.get(f"{API}/missions", timeout=10)
        assert any(mm["id"] == mid for mm in r.json())

        # update
        payload["name"] = "TEST_Mission1_upd"
        r = session.put(f"{API}/missions/{mid}", json=payload, timeout=10)
        assert r.status_code == 200
        assert r.json()["name"] == "TEST_Mission1_upd"

        # duplicate
        r = session.post(f"{API}/missions/{mid}/duplicate", timeout=10)
        assert r.status_code == 200
        dup_id = r.json()["id"]
        assert dup_id != mid

        # delete
        r = session.delete(f"{API}/missions/{mid}", timeout=10)
        assert r.status_code == 200
        r = session.get(f"{API}/missions/{mid}", timeout=10)
        assert r.status_code == 404

        session.delete(f"{API}/missions/{dup_id}", timeout=10)


# --- History ---------------------------------------------------------------
class TestHistory:
    def test_history(self, session):
        r = session.get(f"{API}/history", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        if r.json():
            entry = r.json()[0]
            for key in ("ts", "drone_id", "command", "status"):
                assert key in entry


# --- WebSocket ------------------------------------------------------------
class TestWebSocket:
    def test_ws_snapshot_and_updates(self, session):
        d = _create_drone(session, "TEST_WS")
        session.post(f"{API}/drones/{d['id']}/connect", timeout=10)

        async def run():
            events = []
            async with websockets.connect(WS_URL) as ws:
                # snapshot
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                events.append(msg["event"])
                # drone updates
                deadline = time.time() + 5
                drone_updates = 0
                while time.time() < deadline and drone_updates < 5:
                    m = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                    events.append(m["event"])
                    if m["event"] == "drone":
                        drone_updates += 1
            return events, drone_updates

        events, drone_updates = asyncio.run(run())
        assert events[0] == "snapshot"
        assert drone_updates >= 3, f"expected >=3 drone updates, got {drone_updates}"
        session.delete(f"{API}/drones/{d['id']}", timeout=10)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
