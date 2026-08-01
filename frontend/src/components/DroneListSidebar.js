import { useGCS, useDroneList } from "@/store/gcsStore";
import { statusDot } from "@/utils/format";
import { Plane, Battery, Wifi, WifiOff } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function DroneListSidebar() {
  const drones = useDroneList();
  const selectedIds = useGCS((s) => s.selectedDroneIds);
  const activeId = useGCS((s) => s.activeDroneId);
  const toggleSelected = useGCS((s) => s.toggleSelected);
  const selectAll = useGCS((s) => s.selectAll);
  const deselectAll = useGCS((s) => s.deselectAll);
  const setActive = useGCS((s) => s.setActive);

  return (
    <div
      data-testid="drone-list-sidebar"
      className="w-72 shrink-0 border-r border-zinc-800 bg-zinc-950 flex flex-col"
    >
      <div className="h-10 px-3 flex items-center justify-between border-b border-zinc-800">
        <span className="font-display font-black text-[11px] tracking-widest text-zinc-400">
          FLEET // {drones.length}
        </span>
        <div className="flex gap-1">
          <Button
            data-testid="btn-select-all"
            variant="ghost"
            className="h-6 px-2 rounded-none text-[10px] font-mono text-zinc-400 hover:text-[#00F0FF] hover:bg-transparent"
            onClick={selectAll}
          >
            ALL
          </Button>
          <Button
            data-testid="btn-deselect-all"
            variant="ghost"
            className="h-6 px-2 rounded-none text-[10px] font-mono text-zinc-400 hover:text-zinc-100 hover:bg-transparent"
            onClick={deselectAll}
          >
            NONE
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {drones.length === 0 && (
          <div className="p-6 text-center text-zinc-500 text-sm">
            <Plane className="w-10 h-10 mx-auto mb-3 opacity-30" />
            No drones added. <br />
            Click <span className="text-[#00F0FF]">Add</span> to register a drone.
          </div>
        )}
        {drones.map((d) => {
          const selected = selectedIds.includes(d.id);
          const active = d.id === activeId;
          return (
            <div
              key={d.id}
              data-testid={`drone-row-${d.id}`}
              onClick={() => setActive(d.id)}
              className={`px-3 py-2.5 border-b border-zinc-900 cursor-pointer group ${
                active ? "bg-zinc-900" : "hover:bg-zinc-900/60"
              }`}
            >
              <div className="flex items-center gap-2">
                <input
                  data-testid={`checkbox-drone-${d.id}`}
                  type="checkbox"
                  className="accent-[#FFB000] w-3.5 h-3.5"
                  checked={selected}
                  onChange={(e) => {
                    e.stopPropagation();
                    toggleSelected(d.id);
                  }}
                  onClick={(e) => e.stopPropagation()}
                />
                <span className={`w-2 h-2 rounded-full ${statusDot(d)}`} />
                <span className="font-display font-bold text-sm text-zinc-100 truncate flex-1">
                  {d.name}
                </span>
                {d.status === "connected" ? (
                  <Wifi className="w-3.5 h-3.5 text-[#00FF41]" />
                ) : (
                  <WifiOff className="w-3.5 h-3.5 text-zinc-600" />
                )}
              </div>
              <div className="mt-1 pl-6 grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono text-[10px]">
                <div className="flex items-center gap-1 text-zinc-400">
                  <Battery
                    className={`w-3 h-3 ${
                      d.telemetry.battery_percent < 20 ? "text-[#FF5500]" : "text-zinc-500"
                    }`}
                  />
                  <span
                    className={
                      d.telemetry.battery_percent < 20
                        ? "text-[#FF5500]"
                        : "text-zinc-300"
                    }
                  >
                    {d.telemetry.battery_percent.toFixed(0)}%
                  </span>
                </div>
                <div className="text-zinc-500 text-right">
                  ALT{" "}
                  <span className="text-zinc-200">
                    {d.telemetry.altitude_relative.toFixed(1)}m
                  </span>
                </div>
                <div className="text-zinc-500">
                  MODE <span className="text-[#00F0FF]">{d.telemetry.flight_mode}</span>
                </div>
                <div className="text-zinc-500 text-right">
                  {d.telemetry.armed ? (
                    <span className="text-[#0088FF]">ARMED</span>
                  ) : (
                    <span className="text-zinc-500">DISARMED</span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="h-8 px-3 border-t border-zinc-800 flex items-center justify-between font-mono text-[10px] text-zinc-500">
        <span data-testid="fleet-selected-count">SEL {selectedIds.length}</span>
        <span>ACT {activeId ? activeId.slice(0, 6) : "--"}</span>
      </div>
    </div>
  );
}
