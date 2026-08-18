import React, { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import GcsModal from "@/components/GcsModal";
import { useGCS, useActiveDrone } from "@/store/gcsStore";
import { Grid, Send } from "lucide-react";
import { commandsApi } from "@/services/api";

export default function SurveyGridDialog({ open, onOpenChange }) {
  const activeDrone = useActiveDrone();
  const setDraftWaypoints = useGCS((s) => s.setDraftWaypoints);

  const [altitude, setAltitude] = useState(25);
  const [widthMeters, setWidthMeters] = useState(100);
  const [lengthMeters, setLengthMeters] = useState(100);
  const [spacingMeters, setSpacingMeters] = useState(20);
  const [angleDeg, setAngleDeg] = useState(0);
  const [speed, setSpeed] = useState(5.0);

  const generateGrid = () => {
    if (!activeDrone) {
      toast.error("No active drone selected to center survey grid");
      return;
    }

    const homeLat = activeDrone.telemetry.latitude || activeDrone.home_lat;
    const homeLon = activeDrone.telemetry.longitude || activeDrone.home_lon;

    // Convert meters to lat/lon degrees (approx)
    const latMeters = 111139;
    const lonMeters = 111139 * Math.cos((homeLat * Math.PI) / 180);

    const halfW = widthMeters / 2;
    const halfL = lengthMeters / 2;
    const numLanes = Math.max(2, Math.floor(lengthMeters / spacingMeters) + 1);
    const laneStep = lengthMeters / (numLanes - 1);

    const rad = (angleDeg * Math.PI) / 180;
    const cosA = Math.cos(rad);
    const sinA = Math.sin(rad);

    const waypoints = [];
    let seq = 0;

    // Takeoff WP
    waypoints.push({
      seq: seq++,
      latitude: Number(homeLat.toFixed(7)),
      longitude: Number(homeLon.toFixed(7)),
      altitude: Number(altitude),
      hold_seconds: 0,
      action: "takeoff",
    });

    for (let i = 0; i < numLanes; i++) {
      const y = -halfL + i * laneStep;
      const xStart = i % 2 === 0 ? -halfW : halfW;
      const xEnd = i % 2 === 0 ? halfW : -halfW;

      // Rotate start point
      const rxStart = xStart * cosA - y * sinA;
      const ryStart = xStart * sinA + y * cosA;

      // Rotate end point
      const rxEnd = xEnd * cosA - y * sinA;
      const ryEnd = xEnd * sinA + y * cosA;

      waypoints.push({
        seq: seq++,
        latitude: Number((homeLat + ryStart / latMeters).toFixed(7)),
        longitude: Number((homeLon + rxStart / lonMeters).toFixed(7)),
        altitude: Number(altitude),
        hold_seconds: 0,
        action: "waypoint",
      });

      waypoints.push({
        seq: seq++,
        latitude: Number((homeLat + ryEnd / latMeters).toFixed(7)),
        longitude: Number((homeLon + rxEnd / lonMeters).toFixed(7)),
        altitude: Number(altitude),
        hold_seconds: 0,
        action: "waypoint",
      });
    }

    // RTL WP
    waypoints.push({
      seq: seq++,
      latitude: Number(homeLat.toFixed(7)),
      longitude: Number(homeLon.toFixed(7)),
      altitude: Number(altitude),
      hold_seconds: 0,
      action: "rtl",
    });

    setDraftWaypoints(waypoints);
    toast.success(`Generated ${waypoints.length} survey grid waypoints!`);
    onOpenChange(false);
  };

  const uploadAndStart = async () => {
    if (!activeDrone) return toast.error("No active drone selected");
    generateGrid();
    try {
      const wps = useGCS.getState().draftMission.waypoints;
      await commandsApi.send([activeDrone.id], "upload_mission", { waypoints: wps });
      toast.success(`Survey grid mission uploaded to ${activeDrone.name}`);
    } catch (e) {
      toast.error("Failed to upload mission: " + e.message);
    }
  };

  return (
    <GcsModal
      open={open}
      onOpenChange={onOpenChange}
      testid="survey-grid-dialog"
      title="SURVEY / MAPPING GRID GENERATOR"
      subtitle="Generate Mission Planner-style lawnmower photo/LiDAR mapping mission grid"
      accent="#FFB000"
      footer={
        <>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="border-zinc-700 hover:bg-zinc-800 text-zinc-100 bg-transparent"
          >
            Cancel
          </Button>
          <Button
            onClick={generateGrid}
            className="bg-[#00F0FF] hover:bg-[#33F3FF] text-black font-semibold"
          >
            <Grid className="w-4 h-4 mr-1.5" />
            Generate Grid
          </Button>
          <Button
            onClick={uploadAndStart}
            className="bg-[#FFB000] hover:bg-[#FFC033] text-black font-semibold"
          >
            <Send className="w-4 h-4 mr-1.5" />
            Upload to Drone
          </Button>
        </>
      }
    >
      <div className="space-y-3 font-mono text-xs">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] uppercase text-zinc-400">Area Width (m)</label>
            <Input
              type="number"
              value={widthMeters}
              onChange={(e) => setWidthMeters(Number(e.target.value))}
              className="bg-zinc-950 border-zinc-700 text-zinc-100 mt-1"
            />
          </div>
          <div>
            <label className="text-[10px] uppercase text-zinc-400">Area Length (m)</label>
            <Input
              type="number"
              value={lengthMeters}
              onChange={(e) => setLengthMeters(Number(e.target.value))}
              className="bg-zinc-950 border-zinc-700 text-zinc-100 mt-1"
            />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-[10px] uppercase text-zinc-400">Altitude (m)</label>
            <Input
              type="number"
              value={altitude}
              onChange={(e) => setAltitude(Number(e.target.value))}
              className="bg-zinc-950 border-zinc-700 text-zinc-100 mt-1"
            />
          </div>
          <div>
            <label className="text-[10px] uppercase text-zinc-400">Lane Spacing (m)</label>
            <Input
              type="number"
              value={spacingMeters}
              onChange={(e) => setSpacingMeters(Number(e.target.value))}
              className="bg-zinc-950 border-zinc-700 text-zinc-100 mt-1"
            />
          </div>
          <div>
            <label className="text-[10px] uppercase text-zinc-400">Grid Angle (°)</label>
            <Input
              type="number"
              value={angleDeg}
              onChange={(e) => setAngleDeg(Number(e.target.value))}
              className="bg-zinc-950 border-zinc-700 text-zinc-100 mt-1"
            />
          </div>
        </div>

        <p className="text-[10px] text-zinc-400 pt-1">
          Grid will be centered around the current position of{" "}
          <span className="text-[#FFB000] font-bold">{activeDrone ? activeDrone.name : "Active Drone"}</span>.
        </p>
      </div>
    </GcsModal>
  );
}
