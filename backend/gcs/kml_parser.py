"""KML Parser for AetherGCS – Parses KML / KMZ files into AetherGCS Missions and Waypoints."""
from __future__ import annotations

import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO
from typing import List, Tuple, Dict, Any
from .models import MissionCreate, Waypoint


def parse_kml_content(kml_text: str, default_alt: float = 20.0, default_speed: float = 5.0) -> MissionCreate:
    """
    Parse KML XML content and convert Placemarks, Polygons, LineStrings, or Points into a GCS Mission.
    Handles standard KML 2.2, Google Earth KML, and QGroundControl / SIH exported KMLs.
    """
    root = ET.fromstring(kml_text.strip())
    
    # Strip namespace handling
    def strip_ns(tag: str) -> str:
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    # Find Document or Placemark elements
    placemarks = []
    for elem in root.iter():
        if strip_ns(elem.tag) == "Placemark":
            placemarks.append(elem)

    document_name = "Imported KML Mission"
    for elem in root.iter():
        if strip_ns(elem.tag) in ("Document", "kml"):
            for child in elem:
                if strip_ns(child.tag) == "name" and child.text and child.text.strip():
                    document_name = child.text.strip()
                    break
            if document_name != "Imported KML Mission":
                break

    raw_coords: List[Tuple[float, float, float]] = []

    for pm in placemarks:
        pm_name = ""
        name_node = pm.find("name")
        if name_node is not None and name_node.text:
            pm_name = name_node.text.strip()

        # Check for coordinates inside Point, LineString, or Polygon
        for child in pm.iter():
            tag = strip_ns(child.tag)
            if tag == "coordinates" and child.text:
                coord_tokens = child.text.strip().split()
                for token in coord_tokens:
                    parts = token.strip().split(",")
                    if len(parts) >= 2:
                        try:
                            lon = float(parts[0])
                            lat = float(parts[1])
                            alt = float(parts[2]) if len(parts) >= 3 else default_alt
                            if alt <= 0:
                                alt = default_alt
                            raw_coords.append((lat, lon, alt))
                        except ValueError:
                            continue

    if not raw_coords:
        raise ValueError("No valid coordinates found in KML file.")

    # Deduplicate consecutive identical coordinates (such as closed polygon start/end points)
    clean_coords: List[Tuple[float, float, float]] = []
    for pt in raw_coords:
        if not clean_coords:
            clean_coords.append(pt)
        else:
            prev = clean_coords[-1]
            if abs(prev[0] - pt[0]) > 1e-7 or abs(prev[1] - pt[1]) > 1e-7:
                clean_coords.append(pt)

    waypoints: List[Waypoint] = []
    
    # Generate waypoints: 0 is Takeoff, middle are Waypoints, final is RTL
    for idx, (lat, lon, alt) in enumerate(clean_coords):
        action = "waypoint"
        if idx == 0:
            action = "takeoff"
        
        waypoints.append(
            Waypoint(
                seq=idx,
                latitude=lat,
                longitude=lon,
                altitude=alt,
                hold_seconds=0.0,
                action=action,
            )
        )

    # Add final RTL waypoint if there are multiple waypoints
    if len(waypoints) > 1:
        last_wp = waypoints[-1]
        waypoints.append(
            Waypoint(
                seq=len(waypoints),
                latitude=last_wp.latitude,
                longitude=last_wp.longitude,
                altitude=last_wp.altitude,
                hold_seconds=0.0,
                action="rtl",
            )
        )

    return MissionCreate(
        name=document_name,
        description=f"Auto-converted from KML ({len(waypoints)} waypoints)",
        default_altitude=default_alt,
        default_speed=default_speed,
        waypoints=waypoints,
    )


def parse_kmz_file(kmz_bytes: bytes, default_alt: float = 20.0, default_speed: float = 5.0) -> MissionCreate:
    """Extract and parse doc.kml inside a KMZ zip file."""
    with zipfile.ZipFile(BytesIO(kmz_bytes)) as z:
        kml_filename = None
        for filename in z.namelist():
            if filename.lower().endswith(".kml"):
                kml_filename = filename
                break
        if not kml_filename:
            raise ValueError("No .kml file found inside KMZ archive.")
        
        kml_content = z.read(kml_filename).decode("utf-8", errors="ignore")
        return parse_kml_content(kml_content, default_alt, default_speed)
