import React, { useState } from "react";
import { toast } from "sonner";
import {
  Plane, Power, PowerOff, Plus, Trash2, ShieldAlert, ArrowUpFromDot,
  ArrowDownToDot, Home, Hand, Route as RouteIcon, Upload, Download, Radio,
  Grid, ChevronUp, ChevronDown
} from "lucide-react";
import { useGCS, useSelectedDrones } from "@/store/gcsStore";
import { commandsApi, dronesApi } from "@/services/api";
import AddDroneDialog from "@/components/AddDroneDialog";
import MissionLibraryDialog from "@/components/MissionLibraryDialog";
import SurveyGridDialog from "@/components/SurveyGridDialog";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Derive a canonical flight state from drone telemetry.
 * Falls back to flight_state if present, otherwise infers from armed + mode.
 */
function getFlightState(drone) {
  if (!drone) return "DISCONNECTED";
  if (drone.status !== "connected") return "DISCONNECTED";
  const t = drone.telemetry;
  // Prefer the explicit state machine field from the backend
  if (t?.flight_state && t.flight_state !== "DISCONNECTED") {
    return t.flight_state;
  }
  // Fallback inference for older backend compatibility
  if (!t?.armed) return "DISARMED";
  const mode = t?.flight_mode || "";
  if (mode === "AUTO") return "MISSION_ACTIVE";
  if (mode === "LAND") return "LANDING";
  if ((t?.altitude_relative ?? 0) > 1.0) return "AIRBORNE";
  return "ARMED";
}

function isAirborne(state) {
  return ["TAKING_OFF", "TAKEOFF_REQUESTED", "AIRBORNE", "LANDING", "MISSION_ACTIVE"].includes(state);
}

// ---------------------------------------------------------------------------
// Styled button component
// ---------------------------------------------------------------------------

const IconBtn = ({ label, onClick, testid, variant = "default", disabled, children }) => {
  const base =
    "h-9 px-3 flex items-center gap-2 text-xs font-medium tracking-wide uppercase rounded-sm border transition-colors disabled:opacity-40 disabled:cursor-not-allowed";
  const styles = {
    default: "bg-zinc-800 border-zinc-600 hover:bg-zinc-700 text-zinc-100",
    primary: "bg-[#FFB000] border-[#FFB000] text-black hover:bg-[#FFC033]",
    danger: "bg-transparent border-[#FF003C] text-[#FF6685] hover:bg-[#FF003C]/20",
    ghost: "bg-transparent border-transparent text-zinc-300 hover:text-zinc-50 hover:bg-zinc-800",
    cyan: "bg-transparent border-[#00F0FF] text-[#00F0FF] hover:bg-[#00F0FF]/15",
    green: "bg-transparent border-[#00FF41] text-[#00FF41] hover:bg-[#00FF41]/15",
  }[variant];
  return (
    <button
      data-testid={testid}
      onClick={onClick}
      disabled={disabled}
      title={label}
      className={`${base} ${styles}`}
    >
      {children}
      <span className="hidden md:inline">{label}</span>
    </button>
  );
};

// ---------------------------------------------------------------------------
// Takeoff altitude picker (inline compact widget)
// ---------------------------------------------------------------------------

const TAKEOFF_MIN = 1;
const TAKEOFF_MAX = 120;
const TAKEOFF_DEFAULT = 10;

function TakeoffControl({ armed, onTakeoff, disabled }) {
  const [altitude, setAltitude] = useState(TAKEOFF_DEFAULT);

  const clamp = (v) => Math.max(TAKEOFF_MIN, Math.min(TAKEOFF_MAX, Number(v)));

  const handleTakeoff = () => {
    if (!armed) {
      toast.error("TAKEOFF BLOCKED — Drone is not armed. Click ARM first.");
      return;
    }
    onTakeoff(altitude);
  };

  return (
    <div className="flex items-center gap-1 h-9">
      {/* Altitude stepper */}
      <div className="flex flex-col border border-zinc-600 rounded-sm overflow-hidden">
        <button
          className="w-5 h-4 bg-zinc-700 hover:bg-zinc-600 text-zinc-300 flex items-center justify-center disabled:opacity-40"
          onClick={() => setAltitude((v) => clamp(v + 1))}
          disabled={disabled || altitude >= TAKEOFF_MAX}
          title="Increase altitude"
        >
          <ChevronUp className="w-3 h-3" />
        </button>
        <button
          className="w-5 h-4 bg-zinc-700 hover:bg-zinc-600 text-zinc-300 flex items-center justify-center disabled:opacity-40"
          onClick={() => setAltitude((v) => clamp(v - 1))}
          disabled={disabled || altitude <= TAKEOFF_MIN}
          title="Decrease altitude"
        >
          <ChevronDown className="w-3 h-3" />
        </button>
      </div>

      {/* Altitude input */}
      <div className="relative flex items-center">
        <input
          type="number"
          min={TAKEOFF_MIN}
          max={TAKEOFF_MAX}
          value={altitude}
          onChange={(e) => setAltitude(clamp(e.target.value))}
          disabled={disabled}
          className="w-14 h-9 bg-zinc-800 border border-zinc-600 rounded-sm text-zinc-100 text-xs font-mono text-center pr-5 disabled:opacity-40 focus:outline-none focus:border-[#FFB000]"
          data-testid="takeoff-altitude-input"
          title="Takeoff altitude in metres"
        />
        <span className="absolute right-1.5 text-[9px] text-zinc-400 font-mono pointer-events-none">m</span>
      </div>

      {/* Takeoff button */}
      <IconBtn
        label="Takeoff"
        testid="btn-takeoff"
        variant="primary"
        onClick={handleTakeoff}
        disabled={disabled}
      >
        <ArrowUpFromDot className="w-4 h-4" />
      </IconBtn>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Flight Mode Selector dropdown
// ---------------------------------------------------------------------------

const FLIGHT_MODES = [
  { group: "Manual",         modes: ["STABILIZE", "ALT_HOLD", "POSHOLD"] },
  { group: "GCS Commanded",  modes: ["GUIDED", "LOITER"] },
  { group: "Autonomous",     modes: ["AUTO"] },
  { group: "Navigation",     modes: ["LAND", "RTL"] },
];

const MODE_COLORS = {
  STABILIZE: "text-zinc-400",
  ALT_HOLD:  "text-zinc-400",
  POSHOLD:   "text-zinc-400",
  GUIDED:    "text-[#FFB000]",
  LOITER:    "text-[#00FF41]",
  AUTO:      "text-[#00F0FF]",
  LAND:      "text-orange-400",
  RTL:       "text-orange-400",
};

function FlightModeSelector({ currentMode, onSetMode, disabled }) {
  const [open, setOpen] = useState(false);
  const ref = React.useRef(null);

  // Close on outside click
  React.useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const modeColor = MODE_COLORS[currentMode] || "text-zinc-300";

  return (
    <div ref={ref} className="relative flex items-center shrink-0 z-[9999]">
      <button
        data-testid="btn-flight-mode-selector"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        title="Switch flight mode"
        className={
          `h-9 px-2.5 flex items-center gap-1.5 rounded-sm border text-xs font-mono font-semibold
           uppercase tracking-wider transition-colors
           disabled:opacity-40 disabled:cursor-not-allowed
           ${
             open
               ? "bg-zinc-700 border-zinc-500 " + modeColor
               : "bg-zinc-800 border-zinc-600 hover:border-zinc-400 " + modeColor
           }`
        }
      >
        <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80 flex-shrink-0" />
        <span>{currentMode || "MODE"}</span>
        <svg className={`w-3 h-3 opacity-60 transition-transform ${open ? "rotate-180" : ""}`}
          viewBox="0 0 10 6" fill="none">
          <path d="M1 1l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 z-[99999] min-w-[170px] bg-zinc-900 border border-zinc-600
                        rounded shadow-2xl shadow-black/80 py-1">
          {FLIGHT_MODES.map(({ group, modes }) => (
            <div key={group}>
              <div className="px-3 py-1 text-[9px] font-bold uppercase tracking-widest text-zinc-500 select-none">
                {group}
              </div>
              {modes.map((m) => {
                const active = m === currentMode;
                return (
                  <button
                    key={m}
                    data-testid={`mode-option-${m.toLowerCase()}`}
                    onClick={() => { onSetMode(m); setOpen(false); }}
                    className={
                      `w-full text-left px-4 py-1.5 text-xs font-mono font-semibold uppercase
                       tracking-wider transition-colors flex items-center gap-2
                       ${
                         active
                           ? `${MODE_COLORS[m] || "text-zinc-200"} bg-zinc-800`
                           : "text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
                       }`
                    }
                  >
                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                      active ? "bg-current" : "bg-zinc-600"
                    }`} />
                    {m}
                    {active && <span className="ml-auto text-[9px] opacity-60">ACTIVE</span>}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main toolbar
// ---------------------------------------------------------------------------

export default function TopToolbar() {
  const selected = useSelectedDrones();
  const activeId = useGCS((s) => s.activeDroneId);
  const drones = useGCS((s) => s.drones);
  const [addOpen, setAddOpen] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [surveyOpen, setSurveyOpen] = useState(false);

  // Determine target drone IDs
  const targetIds = () => {
    if (selected.length > 0) return selected.map((d) => d.id);
    if (activeId) return [activeId];
    return [];
  };

  // Get the primary drone's state for button gating
  const primaryDrone = selected.length > 0
    ? selected[0]
    : activeId ? drones[activeId] : null;

  const flightState = getFlightState(primaryDrone);
  const isConnected = primaryDrone?.status === "connected";
  const isArmed = primaryDrone?.telemetry?.armed === true;
  const isDroneAirborne = isAirborne(flightState);
  const currentMode = primaryDrone?.telemetry?.flight_mode || "";
  // Allow LAND whenever armed and drone has left the ground (or is trying to)
  const canLand = isConnected && isArmed && isDroneAirborne;
  // Allow TAKEOFF when connected, armed, and NOT already airborne
  const canTakeoff = isConnected && isArmed && !isDroneAirborne;

  // Generic command runner
  const run = async (cmd, params = {}, label = cmd, danger = false) => {
    const ids = targetIds();
    if (ids.length === 0) return toast.error("Select at least one drone");
    try {
      await commandsApi.send(ids, cmd, params);
      (danger ? toast.warning : toast.success)(`${label} → ${ids.length} drone(s)`);
    } catch (e) {
      // Show the actual backend error message (pre-arm failures, etc.)
      const detail = e.response?.data?.detail || e.message || String(e);
      toast.error(`${label} failed: ${detail}`);
    }
  };

  // ---- ARM — only arms, never takes off
  const handleArm = async () => {
    const ids = targetIds();
    if (ids.length === 0) return toast.error("Select at least one drone");
    try {
      await commandsApi.send(ids, "arm", {});
      toast.success(`ARMED — ${ids.length} drone(s)`);
    } catch (e) {
      const detail = e.response?.data?.detail || e.message || String(e);
      toast.error(`ARM FAILED: ${detail}`);
    }
  };

  // ---- DISARM — only disarms
  const handleDisarm = async () => {
    const ids = targetIds();
    if (ids.length === 0) return toast.error("Select at least one drone");
    try {
      await commandsApi.send(ids, "disarm", {});
      toast.success(`DISARMED — ${ids.length} drone(s)`);
    } catch (e) {
      const detail = e.response?.data?.detail || e.message || String(e);
      toast.error(`DISARM FAILED: ${detail}`);
    }
  };

  // ---- TAKEOFF — requires armed + user-selected altitude
  const handleTakeoff = async (altitude) => {
    const ids = targetIds();
    if (ids.length === 0) return toast.error("Select at least one drone");
    if (!isArmed) {
      toast.error("TAKEOFF BLOCKED — Drone is not armed. Click ARM first.");
      return;
    }
    try {
      await commandsApi.send(ids, "takeoff", { altitude });
      toast.success(`TAKEOFF → ${altitude}m — ${ids.length} drone(s)`);
    } catch (e) {
      const detail = e.response?.data?.detail || e.message || String(e);
      toast.error(`TAKEOFF FAILED: ${detail}`);
    }
  };

  // ---- LAND — separate command, never called by takeoff
  const handleLand = async () => {
    const ids = targetIds();
    if (ids.length === 0) return toast.error("Select at least one drone");
    try {
      await commandsApi.send(ids, "land", {});
      toast.success(`LAND command sent — ${ids.length} drone(s)`);
    } catch (e) {
      const detail = e.response?.data?.detail || e.message || String(e);
      toast.error(`LAND FAILED: ${detail}`);
    }
  };

  const removeSelected = async () => {
    const ids = selected.length ? selected.map((d) => d.id) : activeId ? [activeId] : [];
    if (!ids.length) return toast.error("Select a drone to remove");
    for (const id of ids) await dronesApi.remove(id);
    toast.success(`Removed ${ids.length} drone(s)`);
  };

  const uploadMission = async () => {
    const { draftMission } = useGCS.getState();
    if (!draftMission.waypoints.length) return toast.error("No waypoints in draft mission");
    const ids = targetIds();
    if (!ids.length) return toast.error("Select drones to upload mission");
    try {
      await commandsApi.send(ids, "upload_mission", { waypoints: draftMission.waypoints });
      toast.success(`Mission uploaded to ${ids.length} drone(s)`);
    } catch (e) {
      toast.error(`Mission upload failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  // ---- SET MODE — switch to any named flight mode
  const handleSetMode = async (mode) => {
    const ids = targetIds();
    if (ids.length === 0) return toast.error("Select at least one drone");
    try {
      await commandsApi.send(ids, "set_mode", { mode });
      toast.success(`Mode → ${mode}`);
    } catch (e) {
      const detail = e.response?.data?.detail || e.message || String(e);
      toast.error(`Mode change failed: ${detail}`);
    }
  };

  // Flight state display label
  const stateColors = {
    DISCONNECTED: "text-zinc-500",
    CONNECTED: "text-zinc-400",
    DISARMED: "text-zinc-300",
    ARMING: "text-yellow-400 animate-pulse",
    ARMED: "text-[#00FF41]",
    TAKEOFF_REQUESTED: "text-[#FFB000] animate-pulse",
    TAKING_OFF: "text-[#FFB000] animate-pulse",
    AIRBORNE: "text-[#00F0FF]",
    LANDING: "text-orange-400 animate-pulse",
    LANDED: "text-zinc-300",
    MISSION_READY: "text-[#00FF41]",
    MISSION_ACTIVE: "text-[#00F0FF] animate-pulse",
  };

  return (
    <div
      data-testid="top-toolbar"
      className="h-14 border-b border-zinc-700 bg-zinc-900 flex items-center gap-2 px-3 z-[9999] relative"
    >
      {/* Brand */}
      <div className="flex items-center gap-2 mr-3">
        <Plane className="w-5 h-5 text-[#FFB000]" />
        <div className="flex flex-col">
          <span className="font-display font-black text-sm text-zinc-100 leading-none tracking-wider">
            AETHER GCS
          </span>
          <span className="font-mono text-[10px] text-zinc-500 leading-none mt-0.5">
            MULTI-DRONE CTRL // v1.0
          </span>
        </div>
      </div>

      <div className="h-8 w-px bg-zinc-700 mx-1" />

      {/* Drone management */}
      <IconBtn label="Add" testid="btn-add-drone" onClick={() => setAddOpen(true)} variant="cyan">
        <Plus className="w-4 h-4" />
      </IconBtn>
      <IconBtn label="Remove" testid="btn-remove-drone" onClick={removeSelected}>
        <Trash2 className="w-4 h-4" />
      </IconBtn>
      <IconBtn
        label="Connect"
        testid="btn-connect"
        onClick={() => run("connect", {}, "Connect")}
      >
        <Power className="w-4 h-4 text-[#00FF41]" />
      </IconBtn>
      <IconBtn
        label="Disconnect"
        testid="btn-disconnect"
        onClick={() => run("disconnect", {}, "Disconnect")}
      >
        <PowerOff className="w-4 h-4" />
      </IconBtn>

      <div className="h-8 w-px bg-zinc-700 mx-1" />

      {/* Flight state indicator */}
      {isConnected && (
        <div className="flex flex-col items-center px-2 min-w-[64px]">
          <span className="font-mono text-[9px] text-zinc-500 uppercase leading-none">STATE</span>
          <span className={`font-mono text-[10px] font-bold leading-tight ${stateColors[flightState] || "text-zinc-300"}`}>
            {flightState.replace(/_/g, " ")}
          </span>
        </div>
      )}

      {/* Flight Mode Selector — always visible in toolbar */}
      <FlightModeSelector
        currentMode={currentMode}
        onSetMode={handleSetMode}
        disabled={!isConnected}
      />

      <div className="h-8 w-px bg-zinc-700 mx-1" />

      {/* ARM / DISARM — mutually exclusive based on armed state */}
      <IconBtn
        label="Arm"
        testid="btn-arm"
        onClick={handleArm}
        variant="green"
        disabled={!isConnected || isArmed || flightState === "ARMING"}
        title={isArmed ? "Already armed" : "ARM the drone"}
      >
        <Radio className="w-4 h-4" />
      </IconBtn>
      <IconBtn
        label="Disarm"
        testid="btn-disarm"
        onClick={handleDisarm}
        variant="default"
        disabled={!isConnected || !isArmed}
        title={!isArmed ? "Already disarmed" : "DISARM the drone"}
      >
        <Radio className="w-4 h-4" />
      </IconBtn>

      <div className="h-8 w-px bg-zinc-700 mx-1" />

      {/* TAKEOFF with altitude picker — disabled when not armed or already airborne */}
      <TakeoffControl
        armed={isArmed}
        onTakeoff={handleTakeoff}
        disabled={!canTakeoff}
      />

      {/* LAND — enabled whenever drone is armed and in the air */}
      <IconBtn
        label="Land"
        testid="btn-land"
        onClick={handleLand}
        disabled={!canLand}
        title={canLand ? "Land at current position" : isArmed ? "Drone not airborne" : "Drone not armed"}
      >
        <ArrowDownToDot className="w-4 h-4" />
      </IconBtn>

      {/* HOLD / RTL — only useful when armed */}
      <IconBtn
        label="Hold"
        testid="btn-hold"
        onClick={() => run("hold", {}, "Hold")}
        disabled={!isConnected || !isArmed}
        title={!isArmed ? "Arm the drone first" : "Hold current GPS position (LOITER)"}
      >
        <Hand className="w-4 h-4" />
      </IconBtn>
      <IconBtn
        label="RTL"
        testid="btn-rtl"
        onClick={() => run("rtl", {}, "RTL")}
        disabled={!isConnected || !isArmed}
        title={!isArmed ? "Arm the drone first" : "Return to launch point and land"}
      >
        <Home className="w-4 h-4" />
      </IconBtn>

      <div className="h-8 w-px bg-zinc-700 mx-1" />

      <IconBtn label="Survey Grid" testid="btn-survey-grid" onClick={() => setSurveyOpen(true)} variant="cyan">
        <Grid className="w-4 h-4" />
      </IconBtn>

      <IconBtn
        label="Library"
        testid="btn-mission-library"
        onClick={() => setLibraryOpen(true)}
      >
        <RouteIcon className="w-4 h-4" />
      </IconBtn>
      <IconBtn label="Upload" testid="btn-mission-upload" onClick={uploadMission}>
        <Upload className="w-4 h-4" />
      </IconBtn>
      <IconBtn
        label="Start"
        testid="btn-mission-start"
        variant="cyan"
        onClick={() => run("start_mission", {}, "Mission Start")}
        disabled={!isConnected || !isArmed}
        title={!isArmed ? "ARM the drone before starting a mission" : "Start uploaded mission"}
      >
        <Download className="w-4 h-4 rotate-180" />
      </IconBtn>

      <div className="flex-1" />

      <IconBtn
        label="E-STOP"
        testid="btn-emergency-stop"
        variant="danger"
        onClick={() => run("emergency_stop", {}, "EMERGENCY STOP", true)}
      >
        <ShieldAlert className="w-4 h-4" />
      </IconBtn>

      <AddDroneDialog open={addOpen} onOpenChange={setAddOpen} />
      <MissionLibraryDialog open={libraryOpen} onOpenChange={setLibraryOpen} />
      <SurveyGridDialog open={surveyOpen} onOpenChange={setSurveyOpen} />
    </div>
  );
}
