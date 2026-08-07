import { useGCS, useDroneList } from "@/store/gcsStore";

export default function StatusBar() {
  const wsStatus = useGCS((s) => s.wsStatus);
  const drones = useDroneList();
  const connected = drones.filter((d) => d.status === "connected").length;
  const armed = drones.filter((d) => d.telemetry?.armed).length;
  const low = drones.filter((d) => d.telemetry?.battery_percent != null && d.telemetry.battery_percent < 20 && d.status === "connected");

  return (
    <div
      data-testid="status-bar"
      className="h-8 border-t border-zinc-700 bg-zinc-950 flex items-center px-4 text-xs font-mono text-zinc-300 justify-between"
    >
      <div className="flex items-center gap-4">
        <span className="flex items-center gap-1.5">
          <span
            data-testid="status-ws-indicator"
            className={`w-2 h-2 rounded-full ${wsStatus === "open"
              ? "bg-[#00FF41]"
              : wsStatus === "connecting"
                ? "bg-[#FFB000] animate-pulse-glow"
                : "bg-[#FF003C]"
              }`}
          />
          <span>WS: {wsStatus.toUpperCase()}</span>
        </span>
        <span>FLEET: {drones.length}</span>
        <span className="text-[#00FF41]">CONN: {connected}</span>
        <span className="text-[#0088FF]">ARM: {armed}</span>
        {low.length > 0 && (
          <span className="text-[#FF5500]" data-testid="status-low-battery">
            LOW-BAT: {low.length}
          </span>
        )}
      </div>
      <div className="flex items-center gap-4">
        <span>{new Date().toISOString().replace("T", " ").slice(0, 19)}Z</span>
        <span className="text-[#FFB000]">AETHER GCS</span>
      </div>
    </div>
  );
}
