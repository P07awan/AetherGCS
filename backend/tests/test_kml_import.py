"""Unit test for AetherGCS KML Parser."""

import unittest
from gcs.kml_parser import parse_kml_content


class TestAetherGCSKMLParser(unittest.TestCase):
    def test_parse_polygon_kml(self):
        kml_sample = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Test Survey Parcel</name>
    <Placemark>
      <name>Parcel 101 Boundary</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.500000,28.600000,25.0
              77.501000,28.601000,25.0
              77.502000,28.600000,25.0
              77.500000,28.600000,25.0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>"""
        mission = parse_kml_content(kml_sample)
        self.assertEqual(mission.name, "Test Survey Parcel")
        self.assertGreater(len(mission.waypoints), 3)
        self.assertEqual(mission.waypoints[0].action, "takeoff")
        self.assertEqual(mission.waypoints[-1].action, "rtl")
        self.assertAlmostEqual(mission.waypoints[0].latitude, 28.600000)
        self.assertAlmostEqual(mission.waypoints[0].longitude, 77.500000)

if __name__ == "__main__":
    unittest.main()
