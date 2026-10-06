"""Unit tests for multi-drone operations, independent flight, and swarm control."""
import asyncio
from gcs.drone_manager import DroneManager
from gcs.models import DroneCreate, ConnectionProfile


def test_add_multiple_drones_placement():
    """Verify adding multiple simulated drones assigns distinct positions."""
    async def _run():
        dm = DroneManager()

        d1 = await dm.add_drone(DroneCreate(
            name="Drone Alpha",
            system_id=1,
            component_id=1,
            connection=ConnectionProfile(connection_type="simulator", address="sim://local", port=0),
            home_lat=37.7749,
            home_lon=-122.4194,
            home_alt=0.0,
        ))

        d2 = await dm.add_drone(DroneCreate(
            name="Drone Bravo",
            system_id=2,
            component_id=1,
            connection=ConnectionProfile(connection_type="simulator", address="sim://local", port=0),
            home_lat=37.7749,
            home_lon=-122.4194,
            home_alt=0.0,
        ))

        assert d1.id != d2.id
        assert d1.name == "Drone Alpha"
        assert d2.name == "Drone Bravo"
        # Verify d2 has a distinct home_lon offset so they don't overlap on the map
        assert d2.home_lon > d1.home_lon
        await dm.shutdown()

    asyncio.run(_run())


def test_independent_drone_operations():
    """Verify each drone can be armed, flown, and landed independently."""
    async def _run():
        dm = DroneManager()

        d1 = await dm.add_drone(DroneCreate(
            name="Drone Alpha",
            system_id=1,
            component_id=1,
            connection=ConnectionProfile(connection_type="simulator", address="sim://local", port=0),
            home_lat=37.7749,
            home_lon=-122.4194,
            home_alt=0.0,
        ))

        d2 = await dm.add_drone(DroneCreate(
            name="Drone Bravo",
            system_id=2,
            component_id=1,
            connection=ConnectionProfile(connection_type="simulator", address="sim://local", port=0),
            home_lat=37.7749,
            home_lon=-122.4194,
            home_alt=0.0,
        ))

        # Connect both
        await dm.connect(d1.id)
        await dm.connect(d2.id)

        # Arm Drone 1 only
        await dm.send_command([d1.id], "arm", {})
        assert d1.telemetry.armed is True
        assert d2.telemetry.armed is False

        # Takeoff Drone 1 to 10m
        await dm.send_command([d1.id], "takeoff", {"altitude": 10.0})
        assert d1.telemetry.flight_mode == "GUIDED"

        # Now Arm and Takeoff Drone 2 to 15m
        await dm.send_command([d2.id], "arm", {})
        await dm.send_command([d2.id], "takeoff", {"altitude": 15.0})
        assert d2.telemetry.armed is True
        assert d2.telemetry.flight_mode == "GUIDED"

        # Operate Drone 1 with manual velocity (forward)
        await dm.send_command([d1.id], "velocity", {"forward": 3.0, "right": 0.0, "up": 0.0, "yaw_rate": 0.0})
        w1 = dm.get_worker(d1.id)
        assert w1._velocity_body[0] == 3.0

        # Operate Drone 2 with manual velocity (right)
        await dm.send_command([d2.id], "velocity", {"forward": 0.0, "right": 2.5, "up": 0.0, "yaw_rate": 0.0})
        w2 = dm.get_worker(d2.id)
        assert w2._velocity_body[1] == 2.5
        # Drone 1 should still have forward = 3.0
        assert w1._velocity_body[0] == 3.0

        # Land Drone 1 only
        await dm.send_command([d1.id], "land", {})
        assert d1.telemetry.flight_mode == "LAND"
        # Drone 2 is still in GUIDED mode flying
        assert d2.telemetry.flight_mode == "GUIDED"

        await dm.shutdown()

    asyncio.run(_run())


def test_simultaneous_swarm_command():
    """Verify commanding multiple drones simultaneously in a swarm."""
    async def _run():
        dm = DroneManager()

        d1 = await dm.add_drone(DroneCreate(
            name="Drone 1",
            system_id=1,
            component_id=1,
            connection=ConnectionProfile(connection_type="simulator", address="sim://local", port=0),
            home_lat=37.7749,
            home_lon=-122.4194,
            home_alt=0.0,
        ))

        d2 = await dm.add_drone(DroneCreate(
            name="Drone 2",
            system_id=2,
            component_id=1,
            connection=ConnectionProfile(connection_type="simulator", address="sim://local", port=0),
            home_lat=37.7749,
            home_lon=-122.4194,
            home_alt=0.0,
        ))

        # Connect both
        await dm.connect(d1.id)
        await dm.connect(d2.id)

        # Arm both simultaneously
        results = await dm.send_command([d1.id, d2.id], "arm", {})
        assert len(results) == 2
        assert all(r["ok"] for r in results)
        assert d1.telemetry.armed is True
        assert d2.telemetry.armed is True

        # Arm again (idempotent test)
        results2 = await dm.send_command([d1.id, d2.id], "arm", {})
        assert len(results2) == 2
        assert all(r["ok"] for r in results2)

        # Takeoff both
        results_takeoff = await dm.send_command([d1.id, d2.id], "takeoff", {"altitude": 12.0})
        assert all(r["ok"] for r in results_takeoff)

        # Hold both
        results_hold = await dm.send_command([d1.id, d2.id], "hold", {})
        assert all(r["ok"] for r in results_hold)
        assert d1.telemetry.flight_mode == "LOITER"
        assert d2.telemetry.flight_mode == "LOITER"

        await dm.shutdown()

    asyncio.run(_run())


def test_mavlink_worker_system_id_isolation():
    """Verify MavlinkWorker rejects telemetry from mismatching system IDs."""
    from unittest.mock import MagicMock
    from gcs.drone_worker import MavlinkWorker
    from gcs.models import Drone, ConnectionProfile

    drone = Drone(
        name="Drone 1",
        system_id=1,
        component_id=1,
        connection=ConnectionProfile(connection_type="udp", address="127.0.0.1", port=14550),
        home_lat=37.7749,
        home_lon=-122.4194,
        home_alt=0.0,
    )
    worker = MavlinkWorker(drone, on_update=lambda d: None)

    # Mock message from system_id 2
    msg_other = MagicMock()
    msg_other.get_type.return_value = "GLOBAL_POSITION_INT"
    msg_other.get_srcSystem.return_value = 2
    msg_other.lat = int(40.0 * 1e7)
    msg_other.lon = int(-120.0 * 1e7)
    msg_other.alt = 50000
    msg_other.relative_alt = 20000

    worker._handle_message(msg_other)
    # Latitude should NOT be updated because srcSystem is 2 and drone is 1
    assert worker.drone.telemetry.latitude == 0.0

    # Mock message from system_id 1
    msg_self = MagicMock()
    msg_self.get_type.return_value = "GLOBAL_POSITION_INT"
    msg_self.get_srcSystem.return_value = 1
    msg_self.lat = int(40.0 * 1e7)
    msg_self.lon = int(-120.0 * 1e7)
    msg_self.alt = 50000
    msg_self.relative_alt = 20000

    worker._handle_message(msg_self)
    # Latitude should be updated because srcSystem is 1
    assert worker.drone.telemetry.latitude == 40.0
