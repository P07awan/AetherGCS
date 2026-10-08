"""
Tests for multi-drone connection reliability fixes.

Covers:
  - duplicate system_id rejection
  - duplicate UDP endpoint rejection
  - duplicate serial port rejection
  - system_id=0 Pydantic rejection
  - system_id out of range rejection
  - heartbeat system_id exact-match filter
  - heartbeat wrong sysid is ignored (no cross-talk)
  - auto_detect_system_id discovery path
  - simulator position spread on add
  - _norm_addr / _norm_serial normalisation helpers
"""
import asyncio
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from gcs.drone_manager import DroneManager, _norm_addr, _norm_serial
from gcs.drone_worker import MavlinkWorker
from gcs.models import ConnectionProfile, Drone, DroneCreate


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _sim_payload(name="Drone", sysid=1, lat=37.7749, lon=-122.4194):
    return DroneCreate(
        name=name,
        system_id=sysid,
        component_id=1,
        connection=ConnectionProfile(connection_type="simulator", address="sim://local", port=0),
        home_lat=lat,
        home_lon=lon,
        home_alt=0.0,
    )


def _udp_payload(name="Drone", sysid=1, address="127.0.0.1", port=14550):
    return DroneCreate(
        name=name,
        system_id=sysid,
        component_id=1,
        connection=ConnectionProfile(connection_type="udp", address=address, port=port),
        home_lat=37.7749,
        home_lon=-122.4194,
        home_alt=0.0,
    )


def _serial_payload(name="Drone", sysid=1, address="COM3", baud=57600):
    return DroneCreate(
        name=name,
        system_id=sysid,
        component_id=1,
        connection=ConnectionProfile(connection_type="serial", address=address, baud_rate=baud),
        home_lat=37.7749,
        home_lon=-122.4194,
        home_alt=0.0,
    )


def _mavlink_worker(sysid=1, address="127.0.0.1", port=14550):
    drone = Drone(
        name=f"Drone sysid={sysid}",
        system_id=sysid,
        component_id=1,
        connection=ConnectionProfile(connection_type="udp", address=address, port=port),
        home_lat=37.7749,
        home_lon=-122.4194,
        home_alt=0.0,
    )
    return MavlinkWorker(drone, on_update=lambda d: None)


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def test_norm_addr_local_variants():
    """All local-loopback representations normalise to the same token."""
    assert _norm_addr("") == "127.0.0.1"
    assert _norm_addr("0.0.0.0") == "127.0.0.1"
    assert _norm_addr("localhost") == "127.0.0.1"
    assert _norm_addr("127.0.0.1") == "127.0.0.1"
    assert _norm_addr("192.168.1.50") == "192.168.1.50"


def test_norm_serial_case_insensitive():
    assert _norm_serial("com3") == "COM3"
    assert _norm_serial("COM3") == "COM3"
    assert _norm_serial("/dev/ttyUSB0") == "/DEV/TTYUSB0"


# ---------------------------------------------------------------------------
# Model validation — system_id range
# ---------------------------------------------------------------------------

def test_system_id_zero_rejected_by_model():
    """system_id=0 is invalid per MAVLink and must be rejected at model level."""
    with pytest.raises(Exception):  # Pydantic ValidationError
        DroneCreate(name="X", system_id=0, component_id=1,
                    connection=ConnectionProfile(connection_type="simulator"),
                    home_lat=0, home_lon=0, home_alt=0)


def test_system_id_negative_rejected():
    with pytest.raises(Exception):
        DroneCreate(name="X", system_id=-1, component_id=1,
                    connection=ConnectionProfile(connection_type="simulator"),
                    home_lat=0, home_lon=0, home_alt=0)


def test_system_id_256_rejected():
    with pytest.raises(Exception):
        DroneCreate(name="X", system_id=256, component_id=1,
                    connection=ConnectionProfile(connection_type="simulator"),
                    home_lat=0, home_lon=0, home_alt=0)


def test_system_id_255_accepted():
    d = DroneCreate(name="X", system_id=255, component_id=1,
                    connection=ConnectionProfile(connection_type="simulator"),
                    home_lat=0, home_lon=0, home_alt=0)
    assert d.system_id == 255


# ---------------------------------------------------------------------------
# DroneManager — duplicate system ID
# ---------------------------------------------------------------------------

def test_duplicate_system_id_rejected():
    """Adding a second drone with the same system_id must raise HTTP 409."""
    async def _run():
        dm = DroneManager()
        await dm.add_drone(_sim_payload(name="Drone Alpha", sysid=1))
        with pytest.raises(HTTPException) as exc_info:
            await dm.add_drone(_sim_payload(name="Drone Bravo", sysid=1))
        assert exc_info.value.status_code == 409
        assert "System ID 1" in exc_info.value.detail
        await dm.shutdown()

    asyncio.run(_run())


def test_unique_system_ids_accepted():
    """Different system IDs should be accepted without error."""
    async def _run():
        dm = DroneManager()
        d1 = await dm.add_drone(_sim_payload(name="Alpha", sysid=1))
        d2 = await dm.add_drone(_sim_payload(name="Bravo", sysid=2))
        d3 = await dm.add_drone(_sim_payload(name="Charlie", sysid=3))
        assert d1.system_id == 1
        assert d2.system_id == 2
        assert d3.system_id == 3
        await dm.shutdown()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# DroneManager — duplicate UDP endpoint
# ---------------------------------------------------------------------------

def test_duplicate_udp_endpoint_rejected():
    """Two drones on the same UDP address:port must be rejected with HTTP 409."""
    async def _run():
        dm = DroneManager()
        await dm.add_drone(_udp_payload(name="D1", sysid=1, address="127.0.0.1", port=14550))
        with pytest.raises(HTTPException) as exc_info:
            await dm.add_drone(_udp_payload(name="D2", sysid=2, address="127.0.0.1", port=14550))
        assert exc_info.value.status_code == 409
        assert "14550" in exc_info.value.detail

    asyncio.run(_run())


def test_duplicate_udp_loopback_normalised():
    """localhost:14550 and 127.0.0.1:14550 must be treated as the same endpoint."""
    async def _run():
        dm = DroneManager()
        await dm.add_drone(_udp_payload(name="D1", sysid=1, address="127.0.0.1", port=14550))
        with pytest.raises(HTTPException) as exc_info:
            await dm.add_drone(_udp_payload(name="D2", sysid=2, address="localhost", port=14550))
        assert exc_info.value.status_code == 409

    asyncio.run(_run())


def test_different_udp_ports_accepted():
    """Two drones on different UDP ports must be accepted."""
    async def _run():
        dm = DroneManager()
        d1 = await dm.add_drone(_udp_payload(name="D1", sysid=1, port=14550))
        d2 = await dm.add_drone(_udp_payload(name="D2", sysid=2, port=14551))
        assert d1.connection.port == 14550
        assert d2.connection.port == 14551

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# DroneManager — duplicate serial port
# ---------------------------------------------------------------------------

def test_duplicate_serial_port_rejected():
    """Two drones on the same serial port must raise HTTP 409."""
    async def _run():
        dm = DroneManager()
        await dm.add_drone(_serial_payload(name="D1", sysid=1, address="COM3"))
        with pytest.raises(HTTPException) as exc_info:
            await dm.add_drone(_serial_payload(name="D2", sysid=2, address="COM3"))
        assert exc_info.value.status_code == 409
        assert "COM3" in exc_info.value.detail

    asyncio.run(_run())


def test_serial_case_insensitive_duplicate_rejected():
    """COM3 and com3 must be treated as the same port."""
    async def _run():
        dm = DroneManager()
        await dm.add_drone(_serial_payload(name="D1", sysid=1, address="COM3"))
        with pytest.raises(HTTPException) as exc_info:
            await dm.add_drone(_serial_payload(name="D2", sysid=2, address="com3"))
        assert exc_info.value.status_code == 409

    asyncio.run(_run())


def test_different_serial_ports_accepted():
    async def _run():
        dm = DroneManager()
        d1 = await dm.add_drone(_serial_payload(name="D1", sysid=1, address="COM3"))
        d2 = await dm.add_drone(_serial_payload(name="D2", sysid=2, address="COM4"))
        assert d1.connection.address == "COM3"
        assert d2.connection.address == "COM4"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# DroneManager — simulator position spread
# ---------------------------------------------------------------------------

def test_simulator_position_spread():
    """Second simulator drone must be offset east so drones don't overlap."""
    async def _run():
        dm = DroneManager()
        d1 = await dm.add_drone(_sim_payload(name="Alpha", sysid=1, lat=37.7749, lon=-122.4194))
        d2 = await dm.add_drone(_sim_payload(name="Bravo", sysid=2, lat=37.7749, lon=-122.4194))
        assert d2.home_lon > d1.home_lon, "Drone 2 must be offset east from Drone 1"
        await dm.shutdown()

    asyncio.run(_run())


def test_three_simulator_drones_distinct_positions():
    """Three simulator drones at the same initial coords must all have distinct positions."""
    async def _run():
        dm = DroneManager()
        d1 = await dm.add_drone(_sim_payload(name="A", sysid=1))
        d2 = await dm.add_drone(_sim_payload(name="B", sysid=2))
        d3 = await dm.add_drone(_sim_payload(name="C", sysid=3))
        lons = [d1.home_lon, d2.home_lon, d3.home_lon]
        assert len(set(round(l, 8) for l in lons)) == 3, "All three must have distinct longitudes"
        await dm.shutdown()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# MavlinkWorker — heartbeat system_id filtering
# ---------------------------------------------------------------------------

def test_heartbeat_correct_sysid_accepted():
    """Message from the configured system_id must update telemetry."""
    worker = _mavlink_worker(sysid=1)

    msg = MagicMock()
    msg.get_type.return_value = "GLOBAL_POSITION_INT"
    msg.get_srcSystem.return_value = 1
    msg.lat = int(40.0 * 1e7)
    msg.lon = int(-120.0 * 1e7)
    msg.alt = 50000
    msg.relative_alt = 20000

    worker._handle_message(msg)
    assert worker.drone.telemetry.latitude == 40.0


def test_heartbeat_wrong_sysid_ignored():
    """Message from a different system_id must NOT update telemetry (no cross-talk)."""
    worker = _mavlink_worker(sysid=1)

    msg = MagicMock()
    msg.get_type.return_value = "GLOBAL_POSITION_INT"
    msg.get_srcSystem.return_value = 2  # wrong
    msg.lat = int(99.0 * 1e7)
    msg.lon = int(99.0 * 1e7)
    msg.alt = 50000
    msg.relative_alt = 20000

    worker._handle_message(msg)
    assert worker.drone.telemetry.latitude == 0.0, "Latitude must not be updated by cross-talk"


def test_heartbeat_sysid_zero_source_ignored():
    """Source system_id=0 (ground control station) should not update drone telemetry."""
    worker = _mavlink_worker(sysid=1)

    msg = MagicMock()
    msg.get_type.return_value = "GLOBAL_POSITION_INT"
    msg.get_srcSystem.return_value = 0
    msg.lat = int(50.0 * 1e7)
    msg.lon = int(10.0 * 1e7)
    msg.alt = 1000
    msg.relative_alt = 500

    worker._handle_message(msg)
    # sysid=0 != drone.system_id=1, so must be ignored
    assert worker.drone.telemetry.latitude == 0.0


def test_two_workers_no_cross_talk():
    """Two workers with different system IDs must not accept each other's messages."""
    w1 = _mavlink_worker(sysid=1, port=14550)
    w2 = _mavlink_worker(sysid=2, port=14551)

    def _pos_msg(sysid, lat, lon):
        m = MagicMock()
        m.get_type.return_value = "GLOBAL_POSITION_INT"
        m.get_srcSystem.return_value = sysid
        m.lat = int(lat * 1e7)
        m.lon = int(lon * 1e7)
        m.alt = 1000
        m.relative_alt = 500
        return m

    # w1 receives message from sysid=2 (should be ignored by w1)
    w1._handle_message(_pos_msg(2, 50.0, 10.0))
    assert w1.drone.telemetry.latitude == 0.0

    # w2 receives message from sysid=1 (should be ignored by w2)
    w2._handle_message(_pos_msg(1, 55.0, 15.0))
    assert w2.drone.telemetry.latitude == 0.0

    # w1 receives its own message
    w1._handle_message(_pos_msg(1, 37.0, -122.0))
    assert w1.drone.telemetry.latitude == 37.0

    # w2 receives its own message
    w2._handle_message(_pos_msg(2, 48.0, 11.0))
    assert w2.drone.telemetry.latitude == 48.0


# ---------------------------------------------------------------------------
# auto_detect_system_id flag
# ---------------------------------------------------------------------------

def test_auto_detect_system_id_flag_default_false():
    """auto_detect_system_id must default to False."""
    cp = ConnectionProfile(connection_type="udp", address="127.0.0.1", port=14550)
    assert cp.auto_detect_system_id is False


def test_auto_detect_system_id_can_be_enabled():
    cp = ConnectionProfile(
        connection_type="udp", address="127.0.0.1", port=14550,
        auto_detect_system_id=True,
    )
    assert cp.auto_detect_system_id is True


# ---------------------------------------------------------------------------
# Race-condition: rapid concurrent creation
# ---------------------------------------------------------------------------

def test_rapid_drone_creation_unique_sysids():
    """Creating drones rapidly without closing the dialog must not produce duplicate system IDs."""
    async def _run():
        dm = DroneManager()
        # Simulate rapid creation of 5 drones all requesting sysid=1
        # The manager must reject 4 of them.
        results = []
        for i in range(5):
            try:
                d = await dm.add_drone(_sim_payload(name=f"Rapid-{i}", sysid=1))
                results.append(("ok", d.system_id))
            except HTTPException as exc:
                results.append(("conflict", exc.status_code))

        ok_count = sum(1 for r in results if r[0] == "ok")
        conflict_count = sum(1 for r in results if r[0] == "conflict")
        assert ok_count == 1, f"Only one should succeed, got {ok_count}"
        assert conflict_count == 4
        await dm.shutdown()

    asyncio.run(_run())
