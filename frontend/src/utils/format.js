export const fmt = (n, d = 2) => (n == null || isNaN(n) ? "--" : Number(n).toFixed(d));
export const fmtLat = (n) => (n == null || isNaN(n) ? "--" : Number(n).toFixed(6) + "°");
export const fmtLon = (n) => (n == null || isNaN(n) ? "--" : Number(n).toFixed(6) + "°");
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
// battery_percent is null when the autopilot hasn't reported it; null < 20 is true in JS.
const isLowBattery = (drone) => {
  const b = drone.telemetry?.battery_percent;
  return b != null && b < 20;
};
export const statusColor = (drone) => {
  if (!drone) return "text-zinc-500";
  if (drone.status !== "connected") return "text-[#FF003C]";
  if (isLowBattery(drone)) return "text-[#FF5500]";
  if (drone.telemetry?.armed) return "text-[#0088FF]";
  return "text-[#00FF41]";
};
export const statusDot = (drone) => {
  if (!drone) return "bg-zinc-600";
  if (drone.status === "connecting") return "bg-[#FFB000] animate-pulse-glow";
  if (drone.status !== "connected") return "bg-[#FF003C]";
  if (isLowBattery(drone)) return "bg-[#FF5500]";
  if (drone.telemetry?.armed) return "bg-[#0088FF] animate-pulse-glow";
  return "bg-[#00FF41]";
};

/**
 * Link health of a drone as an operator should read it. When `ok` is false the
 * telemetry on screen is NOT live (stale values from the last packet).
 *   tone: "ok" | "warn" | "bad" | "off"
 */
export const linkState = (drone) => {
  if (!drone) return { ok: false, label: "NO DRONE", tone: "off" };
  const err = drone.last_error || "";
  switch (drone.status) {
    case "connected":
      return drone.telemetry?.heartbeat === false
        ? { ok: false, label: "LINK LOST", tone: "bad" }
        : { ok: true, label: "LIVE", tone: "ok" };
    case "connecting":
      return err
        ? { ok: false, label: "RECONNECTING", tone: "warn" }
        : { ok: false, label: "CONNECTING", tone: "warn" };
    case "error":
      return /link lost/i.test(err)
        ? { ok: false, label: "LINK LOST", tone: "bad" }
        : { ok: false, label: "ERROR", tone: "bad" };
    default:
      return { ok: false, label: "OFFLINE", tone: "off" };
  }
};

export const LINK_TONE_CLASS = {
  ok: "text-[#00FF41]",
  warn: "text-[#FFB000]",
  bad: "text-[#FF003C]",
  off: "text-zinc-500",
};

/** Escape text for insertion into HTML strings (Leaflet divIcon markup). */
export const escapeHtml = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
