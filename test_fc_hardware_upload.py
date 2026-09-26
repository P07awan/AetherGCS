"""
Hardware Flight Controller (FC) MAVLink Mission Upload Tester for AetherGCS.
Scans available COM ports, connects to physical Flight Controller, parses KML, and uploads waypoints.
"""

import sys
import time
import logging
from pathlib import Path
import serial.tools.list_ports

logging.basicConfig(level=logging.INFO, format="[FC-TEST %(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("fc_test")

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from gcs.kml_parser import parse_kml_content
from gcs.models import Waypoint

def scan_com_ports():
    ports = list(serial.tools.list_ports.comports())
    logger.info("Scanning host system serial ports...")
    if not ports:
        logger.warning("No active serial COM ports detected on host system.")
        return []
    
    available = []
    for p in ports:
        logger.info("  Found Port: %s | Description: %s | HWID: %s", p.device, p.description, p.hwid)
        available.append(p.device)
    return available

def test_fc_connection_and_upload(port_name: str, baud_rate: int = 115200, kml_path: Path = None):
    logger.info("==========================================================")
    logger.info("CONNECTING TO HARDWARE FLIGHT CONTROLLER ON %s (%d BAUD)", port_name, baud_rate)
    logger.info("==========================================================")

    try:
        from pymavlink import mavutil
    except ImportError:
        logger.error("pymavlink is required for hardware FC communication. Install with: pip install pymavlink")
        return False

    # 1. Parse KML File into Waypoints
    if not kml_path or not kml_path.exists():
        kml_path = ROOT_DIR / "khasra_121_survey.kml"
    
    if not kml_path.exists():
        logger.error("No KML file found at %s. Please generate a KML file first.", kml_path)
        return False

    kml_text = kml_path.read_text(encoding="utf-8", errors="ignore")
    mission_create = parse_kml_content(kml_text)
    logger.info("Parsed KML Mission: '%s' with %d waypoints", mission_create.name, len(mission_create.waypoints))

    # 2. Establish MAVLink Serial Connection
    logger.info("Connecting MAVLink serial transport to %s...", port_name)
    try:
        mav = mavutil.mavlink_connection(port_name, baud=baud_rate, timeout=5.0)
    except Exception as e:
        logger.error("Failed to open serial port %s: %s", port_name, e)
        return False

    # 3. Wait for Heartbeat from Physical FC
    logger.info("Waiting for MAVLink Heartbeat from Flight Controller (5s timeout)...")
    hb = mav.wait_heartbeat(timeout=5.0)
    if not hb:
        logger.warning("No MAVLink heartbeat received on %s at %d baud.", port_name, baud_rate)
        logger.warning("If testing Bluetooth/virtual serial port, ensure FC is powered and sending MAVLink.")
        mav.close()
        return False

    logger.info("SUCCESS: MAVLink Heartbeat received from FC System ID %d (Type: %d, Autopilot: %d)",
                mav.target_system, hb.type, hb.autopilot)

    # 4. Mission Protocol Upload (MISSION_COUNT -> MISSION_ITEM_INT -> MISSION_ACK)
    waypoints = mission_create.waypoints
    count = len(waypoints)
    logger.info("Uploading %d waypoints to Flight Controller (System ID: %d)...", count, mav.target_system)

    mav.mav.mission_count_send(mav.target_system, mav.target_component, count, mavutil.mavlink.MAV_MISSION_TYPE_MISSION)
    
    start_time = time.time()
    uploaded_count = 0

    while time.time() - start_time < 15.0 and uploaded_count < count:
        msg = mav.recv_match(type=['MISSION_REQUEST_INT', 'MISSION_REQUEST', 'MISSION_ACK'], blocking=True, timeout=2.0)
        if not msg:
            logger.warning("Timeout waiting for mission request from FC.")
            break

        msg_type = msg.get_type()
        if msg_type in ('MISSION_REQUEST_INT', 'MISSION_REQUEST'):
            seq = msg.seq
            if seq >= count:
                logger.warning("FC requested invalid waypoint index %d (max: %d)", seq, count - 1)
                break
            
            wp = waypoints[seq]
            # Command mapping: 16 = MAV_CMD_NAV_WAYPOINT, 22 = TAKEOFF, 20 = RTL
            cmd_code = 16
            if wp.action == "takeoff":
                cmd_code = 22
            elif wp.action == "rtl":
                cmd_code = 20

            mav.mav.mission_item_int_send(
                mav.target_system,
                mav.target_component,
                seq,
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                cmd_code,
                1 if seq == 0 else 0, # current
                1, # autocontinue
                wp.hold_seconds, # param1 (hold time)
                0, 0, 0, # params 2-4
                int(wp.latitude * 1e7),
                int(wp.longitude * 1e7),
                float(wp.altitude),
                mavutil.mavlink.MAV_MISSION_TYPE_MISSION
            )
            uploaded_count += 1
            logger.info("  Uploaded Waypoint #%d [%s] -> Lat: %.6f, Lon: %.6f, Alt: %.1fm",
                        seq + 1, wp.action.upper(), wp.latitude, wp.longitude, wp.altitude)

        elif msg_type == 'MISSION_ACK':
            ack_type = getattr(msg, 'type', 0)
            if ack_type == 0:
                logger.info("SUCCESS: Mission upload ACK ACCEPTED by Hardware Flight Controller!")
                mav.close()
                return True
            else:
                logger.error("FC Rejected Mission with ACK error code: %d", ack_type)
                mav.close()
                return False

    mav.close()
    return uploaded_count == count


if __name__ == "__main__":
    com_ports = scan_com_ports()
    
    if not com_ports:
        logger.info("No active COM ports detected. Plug in your Flight Controller USB cable or Bluetooth link and re-run.")
    else:
        logger.info("Attempting MAVLink test connection on available ports...")
        for port in com_ports:
            # Try 115200 and 57600 baud rates
            for baud in [115200, 57600, 921600]:
                logger.info("Testing Port: %s at %d Baud...", port, baud)
                success = test_fc_connection_and_upload(port, baud)
                if success:
                    logger.info("Hardware FC test PASSED on %s at %d baud!", port, baud)
                    break
