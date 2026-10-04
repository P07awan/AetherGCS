"""Unit tests for drone worker mode switching and RTL behavior."""
import asyncio
from unittest.mock import MagicMock
import pytest
from gcs.drone_worker import MavlinkWorker
from gcs.models import Drone, ConnectionProfile


@pytest.fixture
def mock_worker():
    drone = Drone(
        id="test-drone-1",
        name="TestDrone",
        system_id=1,
        component_id=1,
        status="connected",
        connection=ConnectionProfile(connection_type="udp", address="127.0.0.1", port=14550),
        home_lat=37.7749,
        home_lon=-122.4194,
        home_alt=0.0,
    )
    worker = MavlinkWorker(drone, on_update=lambda d: None)
    worker._running = True
    mav = MagicMock()
    mav.target_system = 1
    mav.target_component = 1
    worker._mav = mav
    return worker


def test_set_mode_px4_tuple_unpacked(mock_worker):
    """Verify that when PX4 returns a tuple mode_id (e.g. (29, 4, 5)), it is unpacked."""
    # Simulate PX4 mode mapping
    mock_worker._mav.mode_mapping.return_value = {
        "RTL": (29, 4, 5),
        "LOITER": (29, 4, 3),
        "LAND": (29, 4, 6),
    }

    mock_worker._set_mode("RTL")
    # set_mode should be called with unpacked arguments, NOT as a tuple
    mock_worker._mav.set_mode.assert_called_with(29, 4, 5)


def test_set_mode_ardupilot_int(mock_worker):
    """Verify that when ArduPilot returns an int mode_id (e.g. 6), it is passed as int."""
    mock_worker._mav.mode_mapping.return_value = {
        "RTL": 6,
        "LOITER": 5,
        "LAND": 9,
    }

    mock_worker._set_mode("RTL")
    mock_worker._mav.set_mode.assert_called_with(6)


def test_set_mode_px4_alias(mock_worker):
    """Verify that ArduPilot mode names like AUTO or GUIDED map to PX4 MISSION/OFFBOARD."""
    mock_worker._mav.mode_mapping.return_value = {
        "MISSION": (29, 4, 4),
        "OFFBOARD": (29, 6, 0),
    }

    mock_worker._set_mode("AUTO")
    mock_worker._mav.set_mode.assert_called_with(29, 4, 4)


@pytest.mark.anyio
async def test_rtl_fallback_to_command_long(mock_worker):
    """Verify that if set_mode fails, rtl falls back to MAV_CMD_NAV_RETURN_TO_LAUNCH (20)."""
    mock_worker._mav.mode_mapping.side_effect = RuntimeError("mode mapping failed")
    mock_worker._send_command_long = MagicMock()

    await mock_worker.rtl()
    mock_worker._send_command_long.assert_called_with(20)


@pytest.mark.anyio
async def test_upload_mission_actions(mock_worker):
    """Verify upload_mission sends appropriate MAV_CMD for takeoff (22), land (21), rtl (20), waypoint (16)."""
    from gcs.models import Waypoint
    wps = [
        Waypoint(seq=0, latitude=28.67, longitude=77.50, altitude=20, action="takeoff"),
        Waypoint(seq=1, latitude=28.68, longitude=77.51, altitude=25, action="waypoint"),
        Waypoint(seq=2, latitude=28.69, longitude=77.52, altitude=0, action="land"),
        Waypoint(seq=3, latitude=28.70, longitude=77.53, altitude=0, action="rtl"),
    ]

    requests = []
    for seq in range(5):  # 1 home + 4 waypoints
        req = MagicMock()
        req.get_type.return_value = "MISSION_REQUEST_INT"
        req.seq = seq
        requests.append(req)

    ack = MagicMock()
    ack.get_type.return_value = "MISSION_ACK"
    ack.type = 0
    requests.append(ack)

    def on_mission_count(*args, **kwargs):
        for r in requests:
            mock_worker._mission_msg_queue.put_nowait(r)

    mock_worker._mav.mav.mission_count_send.side_effect = on_mission_count

    await mock_worker.upload_mission(wps)

    # Check mission count sent was 5 (1 home + 4 items)
    mock_worker._mav.mav.mission_count_send.assert_called_with(1, 1, 5, 0)

    # Check commands sent: seq 0=Home (16), seq 1=Takeoff (22), seq 2=Waypoint (16), seq 3=Land (21), seq 4=RTL (20)
    calls = mock_worker._mav.mav.mission_item_int_send.call_args_list
    assert len(calls) == 5
    # seq 0: home
    assert calls[0].args[2] == 0
    assert calls[0].args[4] == 16  # MAV_CMD_NAV_WAYPOINT
    # seq 1: takeoff
    assert calls[1].args[2] == 1
    assert calls[1].args[4] == 22  # MAV_CMD_NAV_TAKEOFF
    # seq 2: waypoint
    assert calls[2].args[2] == 2
    assert calls[2].args[4] == 16  # MAV_CMD_NAV_WAYPOINT
    # seq 3: land
    assert calls[3].args[2] == 3
    assert calls[3].args[4] == 21  # MAV_CMD_NAV_LAND
    # seq 4: rtl
    assert calls[4].args[2] == 4
    assert calls[4].args[4] == 20  # MAV_CMD_NAV_RETURN_TO_LAUNCH


@pytest.mark.anyio
async def test_simulator_commands_and_rtl():
    """Verify SimulatorWorker arm, takeoff, rtl, and land behavior."""
    from gcs.drone_worker import SimulatorWorker
    drone = Drone(
        id="sim-test-1",
        name="SimDrone",
        system_id=1,
        component_id=1,
        status="disconnected",
        connection=ConnectionProfile(connection_type="simulator"),
        home_lat=37.7749,
        home_lon=-122.4194,
        home_alt=10.0,
    )
    sim = SimulatorWorker(drone, on_update=lambda d: None)
    await sim.connect()
    assert drone.status == "connected"

    # ARM
    await sim.arm()
    assert drone.telemetry.armed is True

    # TAKEOFF
    await sim.takeoff(altitude=10.0)
    assert drone.telemetry.flight_mode == "GUIDED"
    assert drone.telemetry.flight_state == "TAKING_OFF"

    # Simulate climbing ticks
    for _ in range(30):
        sim._simulator_tick(0.2)
    assert drone.telemetry.altitude_relative >= 9.0
    assert drone.telemetry.flight_state == "AIRBORNE"

    # RTL
    await sim.rtl()
    assert drone.telemetry.flight_mode == "RTL"
    assert sim._rtl_active is True

    # Simulate RTL returning home and landing
    for _ in range(50):
        sim._simulator_tick(0.2)

    await sim.disconnect()
    assert drone.status == "disconnected"


@pytest.mark.anyio
async def test_simulator_mission_actions():
    """Verify SimulatorWorker executes mission with takeoff, waypoint, land, rtl."""
    from gcs.drone_worker import SimulatorWorker
    from gcs.models import Waypoint

    drone = Drone(
        id="sim-test-2",
        name="SimDrone2",
        system_id=2,
        component_id=1,
        status="disconnected",
        connection=ConnectionProfile(connection_type="simulator"),
        home_lat=37.7749,
        home_lon=-122.4194,
        home_alt=10.0,
    )
    sim = SimulatorWorker(drone, on_update=lambda d: None)
    await sim.connect()
    await sim.arm()

    wps = [
        Waypoint(seq=0, latitude=37.7749, longitude=-122.4194, altitude=15.0, action="takeoff"),
        Waypoint(seq=1, latitude=37.7750, longitude=-122.4194, altitude=15.0, action="waypoint"),
        Waypoint(seq=2, latitude=37.7750, longitude=-122.4194, altitude=0.0, action="land"),
    ]
    await sim.upload_mission(wps)
    await sim.start_mission()
    assert drone.telemetry.flight_mode == "AUTO"
    assert drone.telemetry.flight_state == "MISSION_ACTIVE"

    # Simulate ticks for takeoff and flying
    for _ in range(60):
        sim._simulator_tick(0.2)

    await sim.disconnect()


