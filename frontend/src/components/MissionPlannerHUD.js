import React, { useMemo } from "react";
import { useActiveDrone } from "@/store/gcsStore";
import { commandsApi } from "@/services/api";
import { toast } from "sonner";
import { SlidersHorizontal } from "lucide-react";

export default function MissionPlannerHUD({ className = "" }) {
  const drone = useActiveDrone();

  const handleLevelHorizon = async () => {
    if (!drone) return;
    try {
      await commandsApi.send([drone.id], "level_horizon");
      toast.success(`Level Horizon calibration command sent to ${drone.name}`);
    } catch (e) {
      toast.error("Failed to send Level Horizon command: " + e.message);
    }
  };

  const pitch = drone?.telemetry?.pitch ?? 0; // degrees
  const roll = drone?.telemetry?.roll ?? 0;   // degrees
  const heading = drone?.telemetry?.heading ?? 0;
  const armed = drone?.telemetry?.armed ?? false;
  const flightMode = drone?.telemetry?.flight_mode ?? "STABILIZE";
  const groundSpeed = drone?.telemetry?.ground_speed ?? 0;
  const airSpeed = drone?.telemetry?.air_speed ?? 0;
  const altRel = drone?.telemetry?.altitude_relative ?? 0;
  const battVoltage = drone?.telemetry?.battery_voltage;
  const battCurrent = drone?.telemetry?.battery_current;
  const battPct = drone?.telemetry?.battery_percent;
  const gpsFix = drone?.telemetry?.gps_fix;
  const sats = drone?.telemetry?.satellites;

  // Compass tape heading ticks
  const compassTape = useMemo(() => {
    const ticks = [];
    const step = 15; // every 15 deg
    for (let deg = -180; deg <= 540; deg += step) {
      const normalized = (deg + 360) % 360;
      let label = `${normalized}`;
      if (normalized === 0) label = "N";
      else if (normalized === 45) label = "NE";
      else if (normalized === 90) label = "E";
      else if (normalized === 135) label = "SE";
      else if (normalized === 180) label = "S";
      else if (normalized === 225) label = "SW";
      else if (normalized === 270) label = "W";
      else if (normalized === 315) label = "NW";
      ticks.push({ deg, label, isCardinal: normalized % 45 === 0 });
    }
    return ticks;
  }, []);

  return (
    <div
      data-testid="mission-planner-hud"
      className={`relative w-full h-64 bg-black border border-zinc-700 font-mono select-none overflow-hidden rounded-xs ${className}`}
    >
      {/* Background Horizon (Sky vs Ground) */}
      <div
        className="absolute inset-0 transition-transform duration-75 ease-linear origin-center"
        style={{
          transform: `rotate(${-roll}deg) translateY(${pitch * 2.5}px)`,
        }}
      >
        {/* Sky */}
        <div className="absolute -top-[100%] -left-[100%] w-[300%] h-[150%] bg-gradient-to-b from-[#0066CC] to-[#3399FF]" />
        {/* Ground */}
        <div className="absolute top-[50%] -left-[100%] w-[300%] h-[150%] bg-gradient-to-b from-[#8B5A2B] to-[#5C3A1A]" />
        {/* Horizon Line */}
        <div className="absolute top-[50%] -left-[100%] w-[300%] h-[2px] bg-white opacity-90" />

        {/* Pitch Ladder Lines (-30 to +30) */}
        <div className="absolute top-[50%] left-[50%] -translate-x-1/2 -translate-y-1/2 w-44 pointer-events-none">
          {[-30, -20, -10, 10, 20, 30].map((deg) => (
            <div
              key={deg}
              className="absolute left-1/2 -translate-x-1/2 flex items-center gap-1.5 text-[10px] font-bold text-white drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]"
              style={{ transform: `translateY(${-deg * 2.5}px)` }}
            >
              <span className="w-4 text-right">{deg}</span>
              <div className="w-8 h-[1.5px] bg-white border-t border-b border-black" />
              <div className="w-4" />
              <div className="w-8 h-[1.5px] bg-white border-t border-b border-black" />
              <span className="w-4 text-left">{deg}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Center Aircraft Crosshair Marker */}
      <div className="absolute top-[50%] left-[50%] -translate-x-1/2 -translate-y-1/2 z-20 pointer-events-none">
        <div className="relative w-24 h-1 flex items-center justify-between">
          {/* Left Wing */}
          <div className="w-8 h-1 bg-[#FF003C] border border-black" />
          {/* Center Box */}
          <div className="w-3 h-3 border-2 border-[#FF003C] bg-black/40 rounded-full" />
          {/* Right Wing */}
          <div className="w-8 h-1 bg-[#FF003C] border border-black" />
        </div>
      </div>

      {/* Top Compass Ribbon */}
      <div className="absolute top-0 left-0 right-0 h-7 z-30 bg-black/60 border-b border-zinc-700/80 overflow-hidden flex items-center justify-center">
        <div
          className="flex items-center gap-6 whitespace-nowrap transition-transform duration-100"
          style={{ transform: `translateX(${-((heading % 360) * 2)}px)` }}
        >
          {compassTape.map((t, idx) => (
            <div key={idx} className="flex flex-col items-center min-w-[20px]">
              <span className={`text-[10px] font-bold ${t.isCardinal ? "text-[#FFB000]" : "text-white"}`}>
                {t.label}
              </span>
              <div className={`w-[1px] ${t.isCardinal ? "h-2 bg-[#FFB000]" : "h-1 bg-white/70"}`} />
            </div>
          ))}
        </div>
        {/* Pointer Triangle */}
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-0 h-0 border-x-4 border-x-transparent border-b-6 border-b-[#FFB000]" />
      </div>

      {/* Left Speed Tape (Groundspeed / Airspeed) */}
      <div className="absolute top-8 left-0 bottom-8 w-11 z-30 bg-black/50 border-r border-zinc-700 flex flex-col justify-between p-1 text-white text-[10px]">
        <div className="text-[#00F0FF] font-bold text-center">AS</div>
        <div className="text-center font-bold text-[11px] text-white">
          {airSpeed.toFixed(1)} <span className="text-[8px]">m/s</span>
        </div>
        <div className="border-t border-zinc-700 pt-1">
          <div className="text-[#FFB000] font-bold text-center">GS</div>
          <div className="text-center font-bold text-[11px] text-white">
            {groundSpeed.toFixed(1)} <span className="text-[8px]">m/s</span>
          </div>
        </div>
      </div>

      {/* Right Altitude Tape */}
      <div className="absolute top-8 right-0 bottom-8 w-11 z-30 bg-black/50 border-l border-zinc-700 flex flex-col justify-between p-1 text-white text-[10px]">
        <div className="text-[#00FF41] font-bold text-center">ALT</div>
        <div className="text-center font-bold text-sm text-[#00FF41]">
          {altRel.toFixed(1)} <span className="text-[9px]">m</span>
        </div>
        <div className="text-center text-[9px] text-zinc-400">
          Rel Home
        </div>
      </div>

      {/* Center Mission Planner Status Overlay Text */}
      <div className="absolute top-10 left-12 right-12 z-20 pointer-events-none text-center space-y-0.5">
        {/* ARM STATUS BOLD BANNER */}
        <div className="inline-block px-2 py-0.5 rounded-xs text-xs font-black tracking-widest text-shadow-md">
          {armed ? (
            <span className="bg-[#00FF41] text-black px-2 py-0.5">ARMED</span>
          ) : (
            <div className="space-y-0.5">
              <span className="bg-[#FF003C] text-white px-2 py-0.5">DISARMED</span>
              <div className="text-[#FF003C] font-bold text-[11px] tracking-wide drop-shadow-[0_1px_2px_rgba(0,0,0,0.9)]">
                FAILSAFE
              </div>
            </div>
          )}
        </div>

        {/* Mode / PreArm warning lines */}
        <div className="text-[#FFB000] font-bold text-xs drop-shadow-[0_1px_2px_rgba(0,0,0,0.9)]">
          {flightMode}
        </div>
        {!armed && (
          <div className="text-amber-300 text-[9px] drop-shadow-[0_1px_2px_rgba(0,0,0,0.9)] font-semibold">
            PreArm: Ready to Arm
          </div>
        )}
      </div>

      {/* Bottom Telemetry Overlay Bar */}
      <div className="absolute bottom-0 left-0 right-0 h-7 z-30 bg-black/80 border-t border-zinc-700 px-2 flex items-center justify-between text-[10px]">
        <div className="flex items-center gap-2 text-zinc-300">
          <span className="text-red-400 font-bold">Bat {battVoltage != null ? battVoltage.toFixed(1) : "--"}v</span>
          <span className="text-yellow-400 font-bold">{battCurrent != null ? battCurrent.toFixed(1) : "--"}A</span>
          <span className="text-green-400 font-bold">{battPct != null ? `${battPct.toFixed(0)}%` : "--"}</span>
        </div>
        <div className="flex items-center gap-2 text-zinc-300">
          <span className="text-[#00F0FF]">
            GPS: {gpsFix == null ? "UNKNOWN" : gpsFix >= 3 ? "3D Fix" : "2D"}
            {" "}({sats != null ? `${sats}sats` : "?"})
          </span>
          <button
            type="button"
            onClick={handleLevelHorizon}
            title="Level Horizon / Accel Calibration"
            className="bg-zinc-800 hover:bg-[#FFB000] hover:text-black border border-zinc-600 px-1.5 py-0.5 text-[9px] text-zinc-200 font-bold uppercase transition-colors flex items-center gap-1"
          >
            <SlidersHorizontal className="w-3 h-3" />
            Level
          </button>
        </div>
      </div>
    </div>
  );
}
