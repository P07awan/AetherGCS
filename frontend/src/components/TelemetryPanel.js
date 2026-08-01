import { useGCS, useActiveDrone } from "@/store/gcsStore";
import { fmt, fmtLat, fmtLon, fmtDuration, statusDot } from "@/utils/format";
import { Progress } from "@/components/ui/progress";
import { Activity, Navigation, Satellite, Gauge } from "lucide-react";

const Row = ({ label, value, unit, testid, accent }) => (
  <div className="flex items-baseline justify-between py-1 border-b border-zinc-800/60">
    <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-400">{label}</span>
    <span
      data-testid={testid}
      className={`font-mono text-sm ${accent || "text-zinc-50"} tabular-nums`}
    >
      {value}
      {unit && <span className="text-zinc-400 ml-0.5 text-[10px]">{unit}</span>}
    </span>
  </div>
);

const Section = ({ title, icon: Icon, children }) => (
  <div className="border-b border-zinc-700">
    <div className="h-8 px-3 flex items-center gap-2 bg-zinc-800 border-b border-zinc-700">
      {Icon && <Icon className="w-3.5 h-3.5 text-[#FFB000]" />}
      <span className="font-display font-black text-[11px] tracking-widest text-zinc-100">
        {title}
      </span>
    </div>
    <div className="px-3 py-1.5">{children}</div>
  </div>
);

export default function TelemetryPanel() {
  const d = useActiveDrone();

  if (!d) {
    return (
      <div className="w-80 shrink-0 border-l border-zinc-800 bg-zinc-950 flex items-center justify-center text-zinc-600 text-sm">
        <div className="text-center px-6">
          <Activity className="w-10 h-10 mx-auto mb-3 opacity-30" />
          Select a drone to view telemetry.
        </div>
      </div>
    );
  }

  const t = d.telemetry;
  const bat = t.battery_percent;
  const batColor = bat < 20 ? "text-[#FF5500]" : bat < 40 ? "text-[#FFB000]" : "text-[#00FF41]";

  return (
    <div
      data-testid="telemetry-panel"
      className="w-80 shrink-0 border-l border-zinc-700 bg-zinc-900 flex flex-col overflow-hidden"
    >
      <div className="h-10 px-3 flex items-center justify-between border-b border-zinc-700 bg-zinc-800/60">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${statusDot(d)}`} />
          <span className="font-display font-black text-sm text-zinc-100 truncate">
            {d.name}
          </span>
        </div>
        <span className="font-mono text-[10px] text-zinc-500">
          SYS {d.system_id}·{d.component_id}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto">
        <Section title="STATUS" icon={Activity}>
          <Row label="Connection" value={d.status.toUpperCase()} testid="tlm-status"
               accent={d.status === "connected" ? "text-[#00FF41]" : "text-[#FF003C]"} />
          <Row label="Mode" value={t.flight_mode} testid="tlm-mode" accent="text-[#00F0FF]" />
          <Row label="Armed" value={t.armed ? "YES" : "NO"} testid="tlm-armed"
               accent={t.armed ? "text-[#0088FF]" : "text-zinc-400"} />
          <Row label="Flight time" value={fmtDuration(t.flight_time)} testid="tlm-flight-time" />
          <Row label="Firmware" value={d.firmware} accent="text-zinc-400" />
        </Section>

        <Section title="POWER" icon={Gauge}>
          <div className="mb-2">
            <div className="flex items-baseline justify-between">
              <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                Battery
              </span>
              <span data-testid="tlm-battery-pct" className={`font-mono text-lg font-bold ${batColor}`}>
                {fmt(bat, 0)}%
              </span>
            </div>
            <Progress
              value={bat}
              className="h-1 mt-1 bg-zinc-900 rounded-none [&>div]:bg-current"
            />
          </div>
          <Row label="Voltage" value={fmt(t.battery_voltage)} unit="V" testid="tlm-voltage" />
          <Row label="Current" value={fmt(t.battery_current)} unit="A" testid="tlm-current" />
        </Section>

        <Section title="POSITION" icon={Navigation}>
          <Row label="Latitude" value={fmtLat(t.latitude)} testid="tlm-lat" />
          <Row label="Longitude" value={fmtLon(t.longitude)} testid="tlm-lon" />
          <Row label="Altitude (MSL)" value={fmt(t.altitude_msl, 1)} unit="m" testid="tlm-alt-msl" />
          <Row label="Altitude (rel)" value={fmt(t.altitude_relative, 1)} unit="m" testid="tlm-alt-rel" />
          <Row label="Heading" value={fmt(t.heading, 0) + "°"} testid="tlm-heading" />
        </Section>

        <Section title="MOTION" icon={Gauge}>
          <Row label="Ground speed" value={fmt(t.ground_speed, 1)} unit="m/s" testid="tlm-gs" />
          <Row label="Air speed" value={fmt(t.air_speed, 1)} unit="m/s" testid="tlm-as" />
        </Section>

        <Section title="GNSS" icon={Satellite}>
          <Row label="Fix type" value={t.gps_fix >= 3 ? "3D" : t.gps_fix >= 2 ? "2D" : "NO FIX"}
               testid="tlm-fix"
               accent={t.gps_fix >= 3 ? "text-[#00FF41]" : "text-[#FFB000]"} />
          <Row label="Satellites" value={t.satellites} testid="tlm-sats" />
          <Row label="Heartbeat" value={t.heartbeat ? "OK" : "LOST"} testid="tlm-heartbeat"
               accent={t.heartbeat ? "text-[#00FF41]" : "text-[#FF003C]"} />
        </Section>
      </div>
    </div>
  );
}
