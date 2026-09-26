"""
Automated KML Loader Script for AetherGCS.
Scans the AetherGCS directory for .kml / .kmz files and loads them into AetherGCS backend.
"""

import os
import sys
import glob
import json
import requests
from pathlib import Path

# Base configuration
GCS_FOLDER = Path(r"C:\Users\ASUS\Desktop\AetherGCS")
API_URL = os.environ.get("GCS_API_URL", "http://localhost:8000/api")

def auto_load_kml_files():
    print(f"[*] Scanning for KML/KMZ files in: {GCS_FOLDER}")
    
    kml_files = list(GCS_FOLDER.glob("*.kml")) + list(GCS_FOLDER.glob("*.kmz"))
    
    if not kml_files:
        print("[-] No .kml or .kmz files found directly in AetherGCS folder.")
        print("[*] Creating sample KML file from SIH cadastral export...")
        sample_kml_path = create_sample_kml()
        kml_files = [sample_kml_path]

    for kml_path in kml_files:
        print(f"[+] Loading KML file: {kml_path.name}")
        try:
            with open(kml_path, "rb") as f:
                response = requests.post(
                    f"{API_URL}/missions/import-kml",
                    files={"file": (kml_path.name, f, "application/vnd.google-earth.kml+xml")}
                )
            if response.status_code == 200:
                data = response.json()
                print(f"  [SUCCESS] Created GCS Mission: '{data.get('name')}' (ID: {data.get('id')}) with {len(data.get('waypoints', []))} waypoints")
            else:
                print(f"  [ERROR] Server responded {response.status_code}: {response.text}")
        except requests.exceptions.ConnectionError:
            print("  [NOTE] GCS backend server is not currently running at http://localhost:8000.")
            print("  [ACTION] Parsing locally using standalone KML parser...")
            load_locally(kml_path)

def create_sample_kml() -> Path:
    """Create a sample KML file in AetherGCS directory for verification."""
    sample_file = GCS_FOLDER / "khasra_121_survey.kml"
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Khasra 121 Survey Boundary</name>
    <description>WGS84 EPSG:4326 Drone Boundary for GCS Import</description>
    <Placemark>
      <name>Khasra 121 Boundary Survey</name>
      <Polygon>
        <altitudeMode>clampToGround</altitudeMode>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.50230000,28.67510000,20.0
              77.50310000,28.67520000,20.0
              77.50320000,28.67440000,20.0
              77.50240000,28.67430000,20.0
              77.50230000,28.67510000,20.0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>"""
    sample_file.write_text(kml_content, encoding="utf-8")
    print(f"  [CREATED] Generated sample KML: {sample_file.name}")
    return sample_file

def load_locally(kml_path: Path):
    sys.path.insert(0, str(GCS_FOLDER / "backend"))
    try:
        from gcs.kml_parser import parse_kml_content
        kml_text = kml_path.read_text(encoding="utf-8", errors="ignore")
        mission_create = parse_kml_content(kml_text)
        print(f"  [PARSED] Local KML Mission: '{mission_create.name}'")
        for wp in mission_create.waypoints:
            print(f"    WP #{wp.seq + 1}: [{wp.action.upper()}] Lat: {wp.latitude:.6f}, Lon: {wp.longitude:.6f}, Alt: {wp.altitude}m")
    except Exception as e:
        print(f"  [ERROR] Local parse failed: {e}")

if __name__ == "__main__":
    auto_load_kml_files()
