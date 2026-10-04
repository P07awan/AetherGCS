"""
Estimator Health Monitor for GPS-Denied AetherGCS.
Tracks VIO / Optical Flow / Odometry state and validity flags.
"""
from typing import Literal

EstimatorState = Literal["UNKNOWN", "INITIALIZING", "GOOD", "DEGRADED", "INVALID"]

class EstimatorHealthMonitor:
    def __init__(self, data_timeout_sec: float = 1.0):
        self.data_timeout_sec = data_timeout_sec

    def evaluate(
        self,
        position_valid: bool,
        velocity_valid: bool,
        altitude_valid: bool,
        age_sec: float,
        quality: str = "GOOD"
    ) -> EstimatorState:
        if age_sec > self.data_timeout_sec:
            return "INVALID"

        if not position_valid or not velocity_valid or not altitude_valid:
            return "INVALID"

        if quality == "DEGRADED":
            return "DEGRADED"

        return "GOOD"
