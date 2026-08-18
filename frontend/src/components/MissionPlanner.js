import { useState } from "react";
import { toast } from "sonner";
import { commandsApi, missionsApi } from "@/services/api";
import { useGCS, useSelectedDrones } from "@/store/gcsStore";
import { Trash2, Save, Play, Pause, Square, Upload, Route as RouteIcon, PlusCircle, ArrowUp, ArrowDown } from "lucide-react";

const Btn = ({ children, onClick, testid, variant = "default", disabled }) => {
  const styles = {
    default: "bg-zinc-900 border-zinc-800 hover:bg-zinc-800 text-zinc-200",
    primary: "bg-[#FFB000] border-[#FFB000] text-black hover:bg-[#FFC033]",
    danger: "bg-transparent border-[#FF003C]/50 text-[#FF003C] hover:bg-[#FF003C]/10",
    cyan: "bg-transparent border-[#00F0FF]/50 text-[#00F0FF] hover:bg-[#00F0FF]/10",
  }[variant];
  return (
    <button
      data-testid={testid}
      disabled={disabled}
      onClick={onClick}
      className={`${styles} h-8 px-3 text-[10px] font-mono uppercase tracking-wider border flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed`}
    >
      {children}
    </button>
  );
};

export default function MissionPlanner() {
  const draft = useGCS((s) => s.draftMission);
  const setDraft = useGCS((s) => s.setDraftMission);
  const updateWaypoint = useGCS((s) => s.updateWaypoint);
  const removeWaypoint = useGCS((s) => s.removeWaypoint);
  const clearWaypoints = useGCS((s) => s.clearWaypoints);
  const reorderWaypoints = useGCS((s) => s.reorderWaypoints);
  const selected = useSelectedDrones();
  const activeId = useGCS((s) => s.activeDroneId);
  const setMissions = useGCS((s) => s.setMissions);

  const [saving, setSaving] = useState(false);

  const targetIds = () => (selected.length ? selected.map((d) => d.id) : activeId ? [activeId] : []);

  const upload = async () => {
    if (!draft.waypoints.length) return toast.error("Add waypoints first");
    const ids = targetIds();
    if (!ids.length) return toast.error("Select a drone");
    try {
      await commandsApi.send(ids, "upload_mission", { waypoints: draft.waypoints });
      toast.success(`Mission uploaded to ${ids.length} drone(s)`);
    } catch (e) {
      toast.error(`Upload failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  const startMission = async () => {
    const ids = targetIds();
    if (!ids.length) return toast.error("Select a drone");
    try {
      await commandsApi.send(ids, "start_mission", {});
      toast.success("Mission started");
    } catch (e) {
      toast.error(`Start failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  const pauseMission = async () => {
    const ids = targetIds();
    if (!ids.length) return;
    await commandsApi.send(ids, "pause_mission", {});
    toast.message("Mission paused");
  };

  const stopMission = async () => {
    const ids = targetIds();
    if (!ids.length) return;
    await commandsApi.send(ids, "stop_mission", {});
    toast.warning("Mission stopped");
  };

  const saveToLibrary = async () => {
    if (!draft.name.trim()) return toast.error("Mission name required");
    setSaving(true);
    try {
      await missionsApi.create({
        name: draft.name,
        description: draft.description || "",
        default_altitude: draft.default_altitude,
        default_speed: draft.default_speed,
        waypoints: draft.waypoints,
      });
      const list = await missionsApi.list();
      setMissions(list);
      toast.success("Mission saved to library");
    } catch (e) {
      toast.error("Save failed: " + e.message);
    } finally {
      setSaving(false);
    }
  };

  const move = (seq, dir) => {
    const list = [...draft.waypoints];
    const idx = list.findIndex((w) => w.seq === seq);
    const to = idx + dir;
    if (to < 0 || to >= list.length) return;
    [list[idx], list[to]] = [list[to], list[idx]];
    reorderWaypoints(list);
  };

  const drones = useGCS((s) => s.drones);
  const primaryDrone = selected.length === 0 && activeId ? drones[activeId] : null;
  const targetText = selected.length > 1
    ? `SWARM: ${selected.length} DRONES`
    : selected.length === 1
      ? `DRONE: ${selected[0].name}`
      : primaryDrone
        ? `DRONE: ${primaryDrone.name}`
        : "NO DRONE SELECTED";

  return (
    <div data-testid="mission-planner" className="h-full flex flex-col bg-zinc-950">
      <div className="h-10 px-3 border-b border-zinc-700 bg-zinc-900 flex items-center gap-2">
        <RouteIcon className="w-3.5 h-3.5 text-[#FFB000]" />
        <span className="font-display font-black text-[11px] tracking-widest text-zinc-100">
          MISSION PLANNER
        </span>
        <span className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold tracking-wider uppercase border ${selected.length > 1
            ? "bg-amber-950/60 border-amber-500 text-amber-300"
            : (selected.length === 1 || primaryDrone)
              ? "bg-cyan-950/60 border-cyan-500 text-cyan-300"
              : "bg-zinc-800 border-zinc-700 text-zinc-500"
          }`}>
          {targetText}
        </span>
        <input
          data-testid="input-mission-name"
          className="ml-2 bg-zinc-900 border border-zinc-800 h-6 px-2 text-xs w-44 focus:outline-none focus:border-[#FFB000] rounded-sm text-zinc-100"
          value={draft.name}
          onChange={(e) => setDraft({ ...draft, name: e.target.value })}
        />
        <label className="ml-2 text-[10px] font-mono text-zinc-500">ALT</label>
        <input
          data-testid="input-mission-alt"
          type="number"
          className="bg-zinc-900 border border-zinc-800 h-6 px-2 text-xs w-16 focus:outline-none focus:border-[#FFB000] rounded-sm text-zinc-100"
          value={draft.default_altitude}
          onChange={(e) => setDraft({ ...draft, default_altitude: Number(e.target.value) })}
        />
        <label className="ml-2 text-[10px] font-mono text-zinc-500">SPD</label>
        <input
          data-testid="input-mission-speed"
          type="number"
          className="bg-zinc-900 border border-zinc-800 h-6 px-2 text-xs w-16 focus:outline-none focus:border-[#FFB000] rounded-sm text-zinc-100"
          value={draft.default_speed}
          onChange={(e) => setDraft({ ...draft, default_speed: Number(e.target.value) })}
        />

        <div className="flex-1" />
        <Btn testid="btn-mp-upload" onClick={upload}><Upload className="w-3.5 h-3.5" /> Upload</Btn>
        <Btn testid="btn-mp-start" variant="primary" onClick={startMission}><Play className="w-3.5 h-3.5" /> Start</Btn>
        <Btn testid="btn-mp-pause" onClick={pauseMission}><Pause className="w-3.5 h-3.5" /> Pause</Btn>
        <Btn testid="btn-mp-stop" variant="danger" onClick={stopMission}><Square className="w-3.5 h-3.5" /> Stop</Btn>
        <Btn testid="btn-mp-save" variant="cyan" onClick={saveToLibrary} disabled={saving}><Save className="w-3.5 h-3.5" /> Save</Btn>
        <Btn testid="btn-mp-clear" onClick={clearWaypoints}><Trash2 className="w-3.5 h-3.5" /> Clear</Btn>
      </div>

      <div className="flex-1 overflow-auto">
        {draft.waypoints.length === 0 ? (
          <div className="p-8 text-center text-zinc-500 text-sm">
            <PlusCircle className="w-8 h-8 mx-auto mb-2 opacity-40" />
            Click the map to add waypoints.
          </div>
        ) : (
          <table className="w-full text-xs font-mono">
            <thead className="text-[10px] uppercase tracking-wider text-zinc-300 bg-zinc-800 sticky top-0">
              <tr className="border-b border-zinc-700">
                <th className="text-left px-3 py-2 w-8">#</th>
                <th className="text-left px-3 py-2">Action</th>
                <th className="text-right px-3 py-2">Latitude</th>
                <th className="text-right px-3 py-2">Longitude</th>
                <th className="text-right px-3 py-2 w-24">Altitude</th>
                <th className="text-right px-3 py-2 w-16">Hold</th>
                <th className="text-right px-3 py-2 w-24">Actions</th>
              </tr>
            </thead>
            <tbody>
              {draft.waypoints.map((wp) => (
                <tr key={wp.seq} className="border-b border-zinc-800 hover:bg-zinc-900 text-zinc-200" data-testid={`wp-row-${wp.seq}`}>
                  <td className="px-3 py-1.5 text-[#FFB000] font-bold">{wp.seq + 1}</td>
                  <td className="px-3 py-1.5">
                    <select
                      data-testid={`wp-action-${wp.seq}`}
                      value={wp.action}
                      onChange={(e) => updateWaypoint(wp.seq, { action: e.target.value })}
                      className="bg-transparent border border-zinc-800 text-zinc-200 text-xs rounded-none focus:outline-none focus:border-[#FFB000]"
                    >
                      <option value="waypoint">Waypoint</option>
                      <option value="takeoff">Takeoff</option>
                      <option value="land">Land</option>
                      <option value="rtl">RTL</option>
                    </select>
                  </td>
                  <td className="px-3 py-1.5 text-right text-zinc-300">{wp.latitude.toFixed(6)}</td>
                  <td className="px-3 py-1.5 text-right text-zinc-300">{wp.longitude.toFixed(6)}</td>
                  <td className="px-3 py-1.5 text-right">
                    <input
                      data-testid={`wp-alt-${wp.seq}`}
                      type="number"
                      className="w-16 bg-zinc-900 border border-zinc-800 h-6 px-1 text-right text-zinc-100 focus:outline-none focus:border-[#FFB000] rounded-sm"
                      value={wp.altitude}
                      onChange={(e) => updateWaypoint(wp.seq, { altitude: Number(e.target.value) })}
                    />
                  </td>
                  <td className="px-3 py-1.5 text-right">
                    <input
                      data-testid={`wp-hold-${wp.seq}`}
                      type="number"
                      className="w-12 bg-zinc-900 border border-zinc-800 h-6 px-1 text-right text-zinc-100 focus:outline-none focus:border-[#FFB000] rounded-sm"
                      value={wp.hold_seconds}
                      onChange={(e) => updateWaypoint(wp.seq, { hold_seconds: Number(e.target.value) })}
                    />
                  </td>
                  <td className="px-3 py-1.5 text-right">
                    <div className="inline-flex gap-1">
                      <button
                        data-testid={`wp-up-${wp.seq}`}
                        onClick={() => move(wp.seq, -1)}
                        className="w-6 h-6 border border-zinc-800 hover:bg-zinc-800 flex items-center justify-center"
                      >
                        <ArrowUp className="w-3 h-3" />
                      </button>
                      <button
                        data-testid={`wp-down-${wp.seq}`}
                        onClick={() => move(wp.seq, 1)}
                        className="w-6 h-6 border border-zinc-800 hover:bg-zinc-800 flex items-center justify-center"
                      >
                        <ArrowDown className="w-3 h-3" />
                      </button>
                      <button
                        data-testid={`wp-del-${wp.seq}`}
                        onClick={() => removeWaypoint(wp.seq)}
                        className="w-6 h-6 border border-[#FF003C]/40 text-[#FF003C] hover:bg-[#FF003C]/10 flex items-center justify-center"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
