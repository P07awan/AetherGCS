import { useState } from "react";
import { toast } from "sonner";
import {
  Plane, Power, PowerOff, Plus, Trash2, ShieldAlert, ArrowUpFromDot,
  ArrowDownToDot, Home, Hand, Route as RouteIcon, Upload, Download, Radio,
} from "lucide-react";
import { useGCS, useSelectedDrones } from "@/store/gcsStore";
import { commandsApi, dronesApi } from "@/services/api";
import AddDroneDialog from "@/components/AddDroneDialog";
import MissionLibraryDialog from "@/components/MissionLibraryDialog";

const IconBtn = ({ label, onClick, testid, variant = "default", disabled, children }) => {
  const base =
    "h-9 px-3 flex items-center gap-2 text-xs font-medium tracking-wide uppercase rounded-sm border transition-colors disabled:opacity-40 disabled:cursor-not-allowed";
  const styles = {
    default: "bg-zinc-900 border-zinc-800 hover:bg-zinc-800 text-zinc-200",
    primary: "bg-[#FFB000] border-[#FFB000] text-black hover:bg-[#FFC033]",
    danger: "bg-transparent border-[#FF003C]/60 text-[#FF003C] hover:bg-[#FF003C]/10",
    ghost: "bg-transparent border-transparent text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900",
    cyan: "bg-transparent border-[#00F0FF]/50 text-[#00F0FF] hover:bg-[#00F0FF]/10",
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

export default function TopToolbar() {
  const selected = useSelectedDrones();
  const activeId = useGCS((s) => s.activeDroneId);
  const drones = useGCS((s) => s.drones);
  const [addOpen, setAddOpen] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);

  const targetIds = () => {
    if (selected.length > 0) return selected.map((d) => d.id);
    if (activeId) return [activeId];
    return [];
  };

  const run = async (cmd, params = {}, label = cmd, danger = false) => {
    const ids = targetIds();
    if (ids.length === 0) return toast.error("Select at least one drone");
    try {
      await commandsApi.send(ids, cmd, params);
      (danger ? toast.warning : toast.success)(`${label} → ${ids.length} drone(s)`);
    } catch (e) {
      toast.error(`${label} failed: ${e.message}`);
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
    await commandsApi.send(ids, "upload_mission", { waypoints: draftMission.waypoints });
    toast.success(`Mission uploaded to ${ids.length} drone(s)`);
  };

  const anyConnected = selected.some((d) => d.status === "connected") ||
    (activeId && drones[activeId]?.status === "connected");

  return (
    <div
      data-testid="top-toolbar"
      className="h-14 border-b border-zinc-800 bg-zinc-900/90 backdrop-blur-md flex items-center gap-2 px-3 z-40"
    >
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

      <div className="h-8 w-px bg-zinc-800 mx-1" />

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

      <div className="h-8 w-px bg-zinc-800 mx-1" />

      <IconBtn label="Arm" testid="btn-arm" onClick={() => run("arm", {}, "Arm")} disabled={!anyConnected}>
        <Radio className="w-4 h-4 text-[#0088FF]" />
      </IconBtn>
      <IconBtn label="Disarm" testid="btn-disarm" onClick={() => run("disarm", {}, "Disarm")}>
        <Radio className="w-4 h-4" />
      </IconBtn>
      <IconBtn
        label="Takeoff"
        testid="btn-takeoff"
        variant="primary"
        onClick={() => run("takeoff", { altitude: 20 }, "Takeoff")}
      >
        <ArrowUpFromDot className="w-4 h-4" />
      </IconBtn>
      <IconBtn label="Land" testid="btn-land" onClick={() => run("land", {}, "Land")}>
        <ArrowDownToDot className="w-4 h-4" />
      </IconBtn>
      <IconBtn label="Hold" testid="btn-hold" onClick={() => run("hold", {}, "Hold")}>
        <Hand className="w-4 h-4" />
      </IconBtn>
      <IconBtn label="RTL" testid="btn-rtl" onClick={() => run("rtl", {}, "RTL")}>
        <Home className="w-4 h-4" />
      </IconBtn>

      <div className="h-8 w-px bg-zinc-800 mx-1" />

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
    </div>
  );
}
