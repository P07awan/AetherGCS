#!/usr/bin/env python3
"""Focused API setup/cleanup for GCS add-drone bug verification."""

import json
import os
import sys
from pathlib import Path

import requests


def load_backend_url() -> str:
    env_path = Path("/app/frontend/.env")
    backend = "https://drone-swarm-control-1.preview.emergentagent.com"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                backend = line.split("=", 1)[1].strip()
    return backend.rstrip("/") + "/api"


API = load_backend_url()
SESSION = requests.Session()
SESSION.timeout = 15


def request(method: str, path: str, **kwargs):
    resp = SESSION.request(method, f"{API}{path}", timeout=15, **kwargs)
    resp.raise_for_status()
    if resp.text:
        return resp.json()
    return None


def cleanup_drones():
    deleted = []
    for drone in request("GET", "/drones"):
        request("DELETE", f"/drones/{drone['id']}")
        deleted.append(drone["id"])
    return deleted


def ensure_mission():
    missions = request("GET", "/missions")
    for mission in missions:
        if mission.get("name") == "QA Visibility Mission":
            return mission
    payload = {
        "name": "QA Visibility Mission",
        "description": "Seed mission for modal visibility verification",
        "default_altitude": 20,
        "default_speed": 5,
        "waypoints": [
            {
                "seq": 0,
                "latitude": 37.7751,
                "longitude": -122.4196,
                "altitude": 20,
                "action": "waypoint",
                "hold_seconds": 0,
            }
        ],
    }
    return request("POST", "/missions", json=payload)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "setup"
    out = {"api": API, "mode": mode}
    if mode in {"setup", "cleanup"}:
        out["deleted_drones"] = cleanup_drones()
    if mode == "setup":
        out["mission"] = ensure_mission()
        out["drones_after_cleanup"] = request("GET", "/drones")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()