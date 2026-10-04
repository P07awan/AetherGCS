"""
Unit tests for coordinate frame transformations and estimator health monitoring.
"""
import math
import unittest
from gcs.coordinate_frames import CoordinateFrames
from gcs.estimator import EstimatorHealthMonitor

class TestCoordinateFrames(unittest.TestCase):
    def test_body_to_local_forward_yaw_zero(self):
        # Yaw 0 -> Forward (+X_body) maps to North (+X_local)
        vn, ve = CoordinateFrames.body_velocity_to_local(1.0, 0.0, 0.0)
        self.assertAlmostEqual(vn, 1.0, places=5)
        self.assertAlmostEqual(ve, 0.0, places=5)

    def test_body_to_local_forward_yaw_90(self):
        # Yaw 90 deg (pi/2) -> Forward (+X_body) maps to East (+Y_local)
        vn, ve = CoordinateFrames.body_velocity_to_local(1.0, 0.0, math.pi / 2)
        self.assertAlmostEqual(vn, 0.0, places=5)
        self.assertAlmostEqual(ve, 1.0, places=5)

    def test_body_offset_forward_yaw_zero(self):
        tx, ty, tz = CoordinateFrames.body_offset_to_local_target(0.0, 0.0, -2.0, 0.0, "FORWARD", 5.0)
        self.assertAlmostEqual(tx, 5.0, places=5)
        self.assertAlmostEqual(ty, 0.0, places=5)
        self.assertAlmostEqual(tz, -2.0, places=5)

    def test_body_offset_up(self):
        tx, ty, tz = CoordinateFrames.body_offset_to_local_target(0.0, 0.0, -2.0, 0.0, "UP", 3.0)
        self.assertAlmostEqual(tx, 0.0, places=5)
        self.assertAlmostEqual(ty, 0.0, places=5)
        self.assertAlmostEqual(tz, -5.0, places=5)

    def test_estimator_health(self):
        monitor = EstimatorHealthMonitor(data_timeout_sec=1.0)
        self.assertEqual(monitor.evaluate(True, True, True, 0.1, "GOOD"), "GOOD")
        self.assertEqual(monitor.evaluate(True, True, True, 1.5, "GOOD"), "INVALID")
        self.assertEqual(monitor.evaluate(False, True, True, 0.1, "GOOD"), "INVALID")

if __name__ == "__main__":
    unittest.main()

