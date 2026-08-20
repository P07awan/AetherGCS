import { useEffect } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Copy, Trash2, FolderOpen, Download, Upload as UploadIcon } from "lucide-react";
import { missionsApi } from "@/services/api";
import { useGCS } from "@/store/gcsStore";
import GcsModal from "@/components/GcsModal";

export default function MissionLibraryDialog({ open, onOpenChange }) {
  const missions = useGCS((s) => s.missions);
  const setMissions = useGCS((s) => s.setMissions);
  const setDraft = useGCS((s) => s.setDraftMission);

  const refresh = async () => {
    try {
      const list = await missionsApi.list();
      setMissions(list);
    } catch {
      toast.error("Failed to load missions");
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (open) refresh(); }, [open]);

  const load = (m) => {
    setDraft({
      id: m.id, name: m.name, description: m.description,
      default_altitude: m.default_altitude, default_speed: m.default_speed,
      waypoints: m.waypoints,
    });
    toast.success(`Loaded: ${m.name}`);
    onOpenChange(false);
  };

  const del = async (id) => { await missionsApi.remove(id); await refresh(); toast.message("Mission deleted"); };
  const dup = async (id) => { await missionsApi.duplicate(id); await refresh(); toast.success("Duplicated"); };

  const exportMission = (m) => {
    const blob = new Blob([JSON.stringify(m, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${m.name.replace(/\s+/g, "_")}.mission.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const importMission = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      await missionsApi.create({
        name: data.name || file.name,
        description: data.description || "",
        default_altitude: data.default_altitude || 20,
        default_speed: data.default_speed || 5,
        waypoints: data.waypoints || [],
      });
      await refresh();
      toast.success("Mission imported");
    } catch {
      toast.error("Invalid mission file");
    }
    e.target.value = "";
  };

  return (
    <GcsModal
      open={open}
      onOpenChange={onOpenChange}
      testid="mission-library-dialog"
      title="MISSION LIBRARY"
      subtitle="Load · Duplicate · Export JSON · Delete"
      accent="#00F0FF"
      footer={
        <label className="text-[11px] font-mono uppercase text-[#00F0FF] cursor-pointer border border-[#00F0FF]/50 hover:bg-[#00F0FF]/10 px-3 py-1.5 rounded-sm flex items-center gap-1.5">
          <UploadIcon className="w-3.5 h-3.5" />
          Import JSON
          <input data-testid="input-import-mission" type="file" accept="application/json" className="hidden" onChange={importMission} />
        </label>
      }
    >
      <div className="max-h-[60vh] overflow-y-auto -mx-1">
        {missions.length === 0 && (
          <div className="text-center text-zinc-400 py-10 text-sm">
            No saved missions. Save one from the planner.
          </div>
        )}
        {missions.map((m) => (
          <div
            key={m.id}
            data-testid={`mission-row-${m.id}`}
            className="flex items-center gap-2 px-3 py-2 border border-zinc-800 hover:border-[#00F0FF]/40 hover:bg-zinc-900 mb-1 rounded-sm"
          >
            <div className="flex-1 min-w-0">
              <div className="font-display font-bold text-sm text-zinc-50 truncate">{m.name}</div>
              <div className="font-mono text-[10px] text-zinc-400">
                {m.waypoints.length} WP · ALT {m.default_altitude}m · SPD {m.default_speed} m/s ·{" "}
                {new Date(m.updated_at).toLocaleString()}
              </div>
            </div>
            <Button data-testid={`btn-mission-load-${m.id}`} variant="outline" onClick={() => load(m)}
                    className="h-7 border-[#00F0FF]/40 text-[#00F0FF] hover:bg-[#00F0FF]/10 rounded-sm px-2 text-[10px] bg-transparent">
              <FolderOpen className="w-3 h-3 mr-1" /> Load
            </Button>
            <Button data-testid={`btn-mission-dup-${m.id}`} variant="outline" onClick={() => dup(m.id)}
                    className="h-7 border-zinc-700 hover:bg-zinc-800 rounded-sm px-2 text-[10px] bg-transparent text-zinc-200">
              <Copy className="w-3 h-3" />
            </Button>
            <Button data-testid={`btn-mission-export-${m.id}`} variant="outline" onClick={() => exportMission(m)}
                    className="h-7 border-zinc-700 hover:bg-zinc-800 rounded-sm px-2 text-[10px] bg-transparent text-zinc-200">
              <Download className="w-3 h-3" />
            </Button>
            <Button data-testid={`btn-mission-del-${m.id}`} variant="outline" onClick={() => del(m.id)}
                    className="h-7 border-[#FF003C]/40 text-[#FF6685] hover:bg-[#FF003C]/10 rounded-sm px-2 text-[10px] bg-transparent">
              <Trash2 className="w-3 h-3" />
            </Button>
          </div>
        ))}
      </div>
    </GcsModal>
  );
}
