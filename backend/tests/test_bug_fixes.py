"""Regression tests for simulator mission/mode handling, MAVLink decoding and WS throttling."""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from gcs.drone_worker import (
    MavlinkWorker,
    SimulatorWorker,
    _is_autopilot_heartbeat,
    _px4_mode_str,
)
from gcs.models import ConnectionProfile, Drone, Waypoint


def _sim_drone():
    return Drone(
        name="Sim", system_id=1, component_id=1,
        connection=ConnectionProfile(connection_type="simulator"),
        home_lat=37.7749, home_lon=-122.4194, home_alt=0.0,
    )


def _airborne_sim(alt=20.0):
    w = SimulatorWorker(_sim_drone(), on_update=lambda d: None)
    w.drone.telemetry.armed = True
    w.drone.telemetry.altitude_relative = alt
    return w


def test_saved_drone_with_unlisted_mode_reloads():
    d = _sim_drone()
    d.telemetry.flight_mode = "SMART_RTL"
    assert Drone(**d.model_dump()).telemetry.flight_mode == "SMART_RTL"


def test_px4_mode_decoding_uses_auto_sub_modes():
    def cm(main, sub=0):
        return (sub << 24) | (main << 16)
    assert _px4_mode_str(cm(4, 4)) == "AUTO"
    assert _px4_mode_str(cm(4, 5)) == "RTL"
    assert _px4_mode_str(cm(4, 6)) == "LAND"
    assert _px4_mode_str(cm(4, 3)) == "LOITER"
    assert _px4_mode_str(cm(2)) == "ALT_HOLD"
    assert _px4_mode_str(cm(6)) == "GUIDED"
    assert _px4_mode_str(cm(7)) == "STABILIZE"


def test_non_autopilot_heartbeat_ignored():
    gimbal = SimpleNamespace(autopilot=8, type=26)
    gcs = SimpleNamespace(autopilot=8, type=6)
    copter = SimpleNamespace(autopilot=3, type=2)
    assert not _is_autopilot_heartbeat(gimbal)
    assert not _is_autopilot_heartbeat(gcs)
    assert _is_autopilot_heartbeat(copter)


def test_gimbal_heartbeat_does_not_clear_armed():
    drone = Drone(
        name="Real", system_id=1, component_id=1,
        connection=ConnectionProfile(connection_type="udp", port=14550),
        home_lat=0, home_lon=0, home_alt=0,
    )
    w = MavlinkWorker(drone, on_update=lambda d: None)
    w.drone.telemetry.armed = True
    hb = MagicMock()
    hb.get_srcSystem.return_value = 1
    hb.get_type.return_value = "HEARTBEAT"
    hb.autopilot = 8
    hb.type = 26
    hb.base_mode = 0
    w._handle_message(hb)
    assert w.drone.telemetry.armed is True


def test_sim_mission_complete_stops_moving():
    async def _run():
        w = _airborne_sim()
        t = w.drone.telemetry
        await w.upload_mission([Waypoint(seq=0, latitude=t.latitude, longitude=t.longitude, altitude=20.0)])
        await w.start_mission()
        for _ in range(5):
            w._simulator_tick(0.2)
        assert t.flight_mode == "LOITER"
        assert t.flight_state == "AIRBORNE"
        lat, lon = t.latitude, t.longitude
        for _ in range(10):
            w._simulator_tick(0.2)
        assert (t.latitude, t.longitude) == (lat, lon)
    asyncio.run(_run())


def test_sim_hold_suspends_mission():
    async def _run():
        w = _airborne_sim()
        t = w.drone.telemetry
        await w.upload_mission([Waypoint(seq=0, latitude=t.latitude + 0.01, longitude=t.longitude, altitude=20.0)])
        await w.start_mission()
        w._simulator_tick(0.2)
        await w.hold()
        lat = t.latitude
        for _ in range(5):
            w._simulator_tick(0.2)
        assert t.latitude == lat
        assert t.flight_mode == "LOITER"
    asyncio.run(_run())


def test_sim_mission_takeoff_climbs_past_manual_target():
    async def _run():
        w = _airborne_sim(alt=0.0)
        t = w.drone.telemetry
        w._takeoff_target = 15.0
        await w.upload_mission([Waypoint(seq=0, latitude=t.latitude, longitude=t.longitude,
                                         altitude=30.0, action="takeoff")])
        await w.start_mission()
        for _ in range(150):
            w._simulator_tick(0.2)
        assert t.altitude_relative >= 29.0
    asyncio.run(_run())


def test_sim_yaw_rate_is_rad_per_second():
    async def _run():
        w = _airborne_sim()
        await w.set_velocity(0, 0, 0, 1.0)  # 1 rad/s
        h0 = w.drone.telemetry.heading
        w._simulator_tick(1.0)
        assert abs(((w.drone.telemetry.heading - h0) % 360) - 57.2958) < 0.01
    asyncio.run(_run())


def test_throttled_status_change_is_still_broadcast():
    import server

    async def _run():
        d = _sim_drone()
        server.drone_manager.workers[d.id] = SimpleNamespace(drone=d)
        pushed = []
        orig_push = server.broadcaster.push
        server.broadcaster.push = lambda ev, payload: pushed.append(payload["status"])
        try:
            d.status = "connected"
            server._on_drone_update(d)
            d.status = "disconnected"  # arrives inside the throttle window
            server._on_drone_update(d)
            assert pushed == ["connected"]
            await asyncio.sleep(server._BROADCAST_INTERVAL + 0.05)
            assert pushed == ["connected", "disconnected"]
        finally:
            server.broadcaster.push = orig_push
            server.drone_manager.workers.pop(d.id, None)
    asyncio.run(_run())
