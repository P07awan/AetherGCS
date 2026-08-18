# Survey Grid Generator Guide

## What is a Survey Grid?
A survey grid is an automated flight path (often referred to as a "lawnmower pattern") used by drones to systematically cover a specific area of land. 

Instead of manually flying a drone back and forth, the Survey Grid Generator calculates precise GPS waypoints to ensure the drone flies in perfectly parallel lanes. This guarantees uniform coverage of the target area.

## Purpose and Use Cases
The primary purpose of a survey grid is to capture overlapping data across a large area. This data is typically processed later to create 2D maps or 3D models.

Common use cases include:
*   **Photogrammetry & 3D Mapping:** Capturing hundreds of overlapping top-down photos to stitch together into high-resolution 2D orthomosaics or 3D point clouds.
*   **LiDAR Scanning:** Flying a precise grid with a laser scanner to penetrate foliage and map the bare earth terrain beneath.
*   **Precision Agriculture:** Using multispectral cameras to monitor crop health over large fields.
*   **Search and Rescue:** Systematically searching an area of interest with thermal or RGB cameras without missing any spots.
*   **Construction & Inspection:** Monitoring site progress and calculating earthwork volumes over time.

## How it Works
The generator takes a few simple inputs and mathematically converts them into a sequence of actionable MAVLink waypoints:

1.  **Center Point:** The grid is generated centered around the drone's current active GPS position (Home or current telemetry coordinate).
2.  **Area Dimensions (Width & Length):** Defines the total rectangular boundary (in meters) that needs to be surveyed.
3.  **Lane Spacing:** The distance between each parallel flight line. This is a critical setting for **overlap**. For photogrammetry, you typically want high side-overlap (e.g., 70%), so your lane spacing must be smaller than the camera's ground footprint.
4.  **Altitude:** The height at which the drone flies. Altitude determines the Ground Sampling Distance (GSD)—how many centimeters per pixel your final map will have. Flying lower gives higher resolution but requires more lanes and photos to cover the same area.
5.  **Grid Angle:** Allows you to rotate the entire grid. This is useful for aligning the flight lanes with the longest edge of a field (to minimize the number of turns and save battery) or to fly perpendicular to the wind.

### The Generated Mission
Once you click "Generate Grid", the system creates a mission containing:
1.  **TAKEOFF:** An initial command to automatically ascend to the survey altitude.
2.  **WAYPOINTS:** A zig-zag series of coordinates. The drone will fly to the start of lane 1, fly to the end, shift over by the "Lane Spacing" distance, and fly back down lane 2, repeating until the width is covered.
3.  **RTL (Return To Launch):** After the final waypoint is reached, the drone will automatically return to its home point and land.
