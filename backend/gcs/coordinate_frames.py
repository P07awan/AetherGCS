"""
Coordinate Frames Manager for GPS-Denied AetherGCS.
Handles transformations between BODY_NED, LOCAL_NED, and HOME_RELATIVE frames.
"""
import math

class CoordinateFrames:
    @staticmethod
    def body_velocity_to_local(vx_body: float, vy_body: float, yaw_rad: float) -> tuple[float, float]:
        """
        Rotates body-frame velocity (forward vx, right vy) into local NED velocity (north vn, east ve).
        """
        vn = vx_body * math.cos(yaw_rad) - vy_body * math.sin(yaw_rad)
        ve = vx_body * math.sin(yaw_rad) + vy_body * math.cos(yaw_rad)
        return vn, ve

    @staticmethod
    def body_offset_to_local_target(
        current_x: float,
        current_y: float,
        current_z: float,
        yaw_rad: float,
        direction: str,
        distance_m: float
    ) -> tuple[float, float, float]:
        """
        Calculates local NED target position from a relative body-frame direction and distance.
        """
        dx_body = 0.0
        dy_body = 0.0
        dz_body = 0.0

        d = direction.upper()
        if d == "FORWARD":
            dx_body = distance_m
        elif d == "BACKWARD":
            dx_body = -distance_m
        elif d == "LEFT":
            dy_body = -distance_m
        elif d == "RIGHT":
            dy_body = distance_m
        elif d == "UP":
            dz_body = -distance_m  # NED: negative Z is UP
        elif d == "DOWN":
            dz_body = distance_m   # NED: positive Z is DOWN
        else:
            raise ValueError(f"Invalid direction: {direction}")

        # Rotate body XY offset into Local NED offset
        dx_local = dx_body * math.cos(yaw_rad) - dy_body * math.sin(yaw_rad)
        dy_local = dx_body * math.sin(yaw_rad) + dy_body * math.cos(yaw_rad)

        target_x = current_x + dx_local
        target_y = current_y + dy_local
        target_z = current_z + dz_body

        return target_x, target_y, target_z
