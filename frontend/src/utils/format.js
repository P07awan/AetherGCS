export const fmt = (n, d = 2) => (n == null ? "--" : Number(n).toFixed(d));
export const fmtLat = (n) => (n == null ? "--" : n.toFixed(6) + "°");
export const fmtLon = (n) => (n == null ? "--" : n.toFixed(6) + "°");
export const fmtDuration = (sec) => {
  if (!sec && sec !== 0) return "--:--";
  const s = Math.max(0, Math.floor(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`
    : `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
};
export const statusColor = (drone) => {
  if (!drone) return "text-zinc-500";
  if (drone.status !== "connected") return "text-[#FF003C]";
  if (drone.telemetry?.battery_percent < 20) return "text-[#FF5500]";
  if (drone.telemetry?.armed) return "text-[#0088FF]";
  return "text-[#00FF41]";
};
export const statusDot = (drone) => {
  if (!drone) return "bg-zinc-600";
  if (drone.status === "connecting") return "bg-[#FFB000] animate-pulse-glow";
  if (drone.status !== "connected") return "bg-[#FF003C]";
  if (drone.telemetry?.battery_percent < 20) return "bg-[#FF5500]";
  if (drone.telemetry?.armed) return "bg-[#0088FF] animate-pulse-glow";
  return "bg-[#00FF41]";
};
