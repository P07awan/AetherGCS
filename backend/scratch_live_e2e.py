import asyncio
import json
import time
import requests
import websockets

BASE = "http://127.0.0.1:8000"
API = f"{BASE}/api"
WS_URL = "ws://127.0.0.1:8000/api/ws/telemetry"

async def test_live_e2e():
    print("--- 1. Testing Health Endpoints ---")
    r = requests.get(f"{BASE}/health")
    assert r.status_code == 200, f"/health returned {r.status_code}"
    print("  GET /health:", r.json())
    r = requests.get(f"{API}/health")
    assert r.status_code == 200, f"/api/health returned {r.status_code}"
    print("  GET /api/health:", r.json())

    print("\n--- 2. Connecting to WebSocket ---")
    async with websockets.connect(WS_URL) as ws:
        # Initial snapshot
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        msg = json.loads(raw)
        assert msg["event"] == "snapshot", f"Expected snapshot, got {msg['event']}"
        print("  WebSocket snapshot received! Current drones:", len(msg["data"]))

        # Send keep-alive ping
        await ws.send("ping")
        pong_raw = await asyncio.wait_for(ws.recv(), timeout=5)
        pong = json.loads(pong_raw)
        assert pong["event"] == "pong"
        print("  WebSocket ping/pong verified:", pong)

        print("\n--- 3. Creating Simulator Drone via REST ---")
        drone_payload = {
            "name": "E2E_Sim_Drone",
            "system_id": 99,
            "component_id": 1,
            "connection": {"connection_type": "simulator", "address": "sim://local", "port": 0},
            "home_lat": 37.7749,
            "home_lon": -122.4194,
            "home_alt": 10.0,
        }
        res = requests.post(f"{API}/drones", json=drone_payload)
        assert res.status_code == 200, f"Create drone failed: {res.text}"
        drone = res.json()
        drone_id = drone["id"]
        print(f"  Drone created: id={drone_id}, name={drone['name']}")

        # Expect drone broadcast on WebSocket
        drone_ws_msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert drone_ws_msg["event"] == "drone"
        assert drone_ws_msg["data"]["id"] == drone_id
        print("  Drone event received on WebSocket!")

        print("\n--- 4. Connecting Drone ---")
        res = requests.post(f"{API}/drones/{drone_id}/connect")
        assert res.status_code == 200
        print("  Connected drone via REST")

        # Wait for telemetry updates
        print("\n--- 5. Streaming Live Telemetry via WebSocket ---")
        updates_received = 0
        for _ in range(5):
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if m["event"] == "drone" and m["data"]["id"] == drone_id:
                t = m["data"]["telemetry"]
                updates_received += 1
                print(f"  Telemetry #{updates_received}: armed={t['armed']}, mode={t['flight_mode']}, alt={t['altitude_relative']:.2f}m, bat={t['battery_percent']:.1f}%")
        assert updates_received >= 3

        print("\n--- 6. Arming Drone ---")
        res = requests.post(f"{API}/commands", json={"drone_ids": [drone_id], "command": "arm"})
        assert res.status_code == 200
        await asyncio.sleep(0.5)
        drone_state = requests.get(f"{API}/drones/{drone_id}").json()
        assert drone_state["telemetry"]["armed"] is True
        print("  Armed successfully! State:", drone_state["telemetry"]["flight_state"])

        print("\n--- 7. Takeoff to 10m ---")
        res = requests.post(f"{API}/commands", json={"drone_ids": [drone_id], "command": "takeoff", "params": {"altitude": 10}})
        assert res.status_code == 200
        print("  Takeoff command accepted, climbing...")
        # Monitor climb
        start = time.time()
        while time.time() - start < 10:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if m["event"] == "drone" and m["data"]["id"] == drone_id:
                alt = m["data"]["telemetry"]["altitude_relative"]
                if alt > 2.0:
                    print(f"  Climbing: altitude = {alt:.2f}m, state = {m['data']['telemetry']['flight_state']}")
                    break

        print("\n--- 8. Landing Drone ---")
        res = requests.post(f"{API}/commands", json={"drone_ids": [drone_id], "command": "land"})
        assert res.status_code == 200
        print("  Landing command accepted")

        print("\n--- 9. Cleaning up test drone ---")
        res = requests.delete(f"{API}/drones/{drone_id}")
        assert res.status_code == 200
        # Wait for drone_removed event (may have in-flight drone telemetry right before it)
        removed_found = False
        for _ in range(10):
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if msg["event"] == "drone_removed":
                assert msg["data"]["id"] == drone_id
                removed_found = True
                print("  drone_removed event received on WebSocket!")
                break
        assert removed_found, "drone_removed event was not received"

    print("\n--- 10. WebSocket Disconnect Verification ---")
    # Verify server is still alive and responsive after WebSocket disconnect
    r = requests.get(f"{BASE}/health")
    assert r.status_code == 200
    print("  Server is healthy and responsive after client disconnect!")
    print("\n==========================================")
    print("ALL LIVE END-TO-END VERIFICATION CHECKS PASSED!")
    print("==========================================")

if __name__ == "__main__":
    asyncio.run(test_live_e2e())
