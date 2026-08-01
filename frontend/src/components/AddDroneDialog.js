import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { dronesApi } from "@/services/api";
import { Cable, Wifi, Radio, Zap } from "lucide-react";
import GcsModal from "@/components/GcsModal";

const SERIAL_PORTS = [
  "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8",
  "COM9", "COM10", "COM11", "COM12", "COM13", "COM14", "COM15", "COM16",
  "/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2",
  "/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyACM2",
  "/dev/ttyAMA0", "/dev/serial0",
];
const BAUD_RATES = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600, 1500000];
const UDP_PORTS = [14550, 14551, 14552, 14553, 14555, 14556];
const TCP_PORTS = [5760, 5761, 5762, 5763, 5770];

const PRESETS = [
  { key: "sitl-udp", label: "SITL UDP :14550", icon: Zap,
    conf: { type: "udp", address: "127.0.0.1", port: 14550 } },
  { key: "sitl-tcp", label: "SITL TCP :5760", icon: Zap,
    conf: { type: "tcp", address: "127.0.0.1", port: 5760 } },
  { key: "apm-usb", label: "APM/Pixhawk USB @57600", icon: Cable,
    conf: { type: "serial", address: "COM7", baud: 57600 } },
  { key: "px4-usb", label: "PX4 USB @115200", icon: Cable,
    conf: { type: "serial", address: "COM8", baud: 115200 } },
  { key: "telem-radio", label: "SiK Telemetry @57600", icon: Radio,
    conf: { type: "serial", address: "COM3", baud: 57600 } },
  { key: "wifi-udp", label: "Wi-Fi Drone UDP :14555", icon: Wifi,
    conf: { type: "udp", address: "192.168.4.1", port: 14555 } },
  { key: "simulator", label: "Built-in Simulator", icon: Zap,
    conf: { type: "simulator", address: "sim://local", port: 0 } },
];

const TabBtn = ({ active, onClick, icon: Icon, label, testid }) => (
  <button
    data-testid={testid}
    onClick={onClick}
    className={`flex-1 h-10 flex items-center justify-center gap-2 border-b-2 text-[11px] font-mono uppercase tracking-wider transition-colors ${
      active
        ? "border-[#FFB000] text-[#FFB000] bg-zinc-800"
        : "border-transparent text-zinc-300 hover:text-zinc-50 hover:bg-zinc-800/60"
    }`}
  >
    <Icon className="w-3.5 h-3.5" />
    {label}
  </button>
);

const Field = ({ label, children }) => (
  <div>
    <label className="text-[10px] font-mono uppercase text-zinc-400">{label}</label>
    <div className="mt-1">{children}</div>
  </div>
);

export default function AddDroneDialog({ open, onOpenChange }) {
  const [name, setName] = useState("Drone Alpha");
  const [sysId, setSysId] = useState(1);
  const [type, setType] = useState("serial");
  const [serialPort, setSerialPort] = useState("COM7");
  const [baud, setBaud] = useState(57600);
  const [udpAddress, setUdpAddress] = useState("127.0.0.1");
  const [udpPort, setUdpPort] = useState(14550);
  const [tcpAddress, setTcpAddress] = useState("127.0.0.1");
  const [tcpPort, setTcpPort] = useState(5760);
  const [homeLat, setHomeLat] = useState(37.7749);
  const [homeLon, setHomeLon] = useState(-122.4194);
  const [busy, setBusy] = useState(false);

  const applyPreset = (p) => {
    const c = p.conf;
    setType(c.type);
    if (c.type === "serial") { setSerialPort(c.address); setBaud(c.baud); }
    if (c.type === "udp") { setUdpAddress(c.address); setUdpPort(c.port); }
    if (c.type === "tcp") { setTcpAddress(c.address); setTcpPort(c.port); }
  };

  const buildConnection = () => {
    if (type === "serial") return { connection_type: "serial", address: serialPort, port: null, baud_rate: Number(baud), auto_reconnect: true };
    if (type === "udp")    return { connection_type: "udp",    address: udpAddress,  port: Number(udpPort), baud_rate: null, auto_reconnect: true };
    if (type === "tcp")    return { connection_type: "tcp",    address: tcpAddress,  port: Number(tcpPort), baud_rate: null, auto_reconnect: true };
    return { connection_type: "simulator", address: "sim://local", port: 0, baud_rate: null, auto_reconnect: true };
  };

  const submit = async () => {
    if (!name.trim()) return toast.error("Name required");
    setBusy(true);
    try {
      const drone = await dronesApi.create({
        name, system_id: Number(sysId), component_id: 1,
        connection: buildConnection(),
        home_lat: Number(homeLat), home_lon: Number(homeLon), home_alt: 0,
      });
      await dronesApi.connect(drone.id);
      toast.success(`${drone.name} added & connected`);
      onOpenChange(false);
    } catch (e) {
      toast.error("Failed: " + (e.response?.data?.detail || e.message));
    } finally {
      setBusy(false);
    }
  };

  return (
    <GcsModal
      open={open}
      onOpenChange={onOpenChange}
      testid="add-drone-dialog"
      title="CONNECT NEW DRONE"
      subtitle="Mission Planner / QGroundControl-style workflow"
      accent="#FFB000"
      footer={
        <>
          <Button
            data-testid="btn-add-drone-cancel"
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="border-zinc-700 hover:bg-zinc-800 rounded-sm text-zinc-100 bg-transparent"
          >
            Cancel
          </Button>
          <Button
            data-testid="btn-add-drone-submit"
            disabled={busy}
            onClick={submit}
            className="bg-[#FFB000] hover:bg-[#FFC033] text-black rounded-sm font-semibold"
          >
            {busy ? "Connecting..." : "Connect"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {/* Presets */}
        <div>
          <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-400 mb-2">
            Quick Presets
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-1.5">
            {PRESETS.map((p) => (
              <button
                key={p.key}
                data-testid={`preset-${p.key}`}
                onClick={() => applyPreset(p)}
                className="flex items-center gap-2 border border-zinc-700 hover:border-[#FFB000] hover:bg-zinc-800 h-9 px-2.5 text-[10px] font-mono text-zinc-100 text-left transition-colors"
              >
                <p.icon className="w-3.5 h-3.5 text-[#00F0FF] shrink-0" />
                <span className="truncate">{p.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Name / SysID / Home */}
        <div className="grid grid-cols-6 gap-2">
          <div className="col-span-3">
            <Field label="Drone Name">
              <Input data-testid="input-drone-name" value={name} onChange={(e) => setName(e.target.value)}
                     className="bg-zinc-950 border-zinc-700 rounded-sm h-9 text-zinc-100" />
            </Field>
          </div>
          <Field label="Sys ID">
            <Input data-testid="input-drone-sysid" type="number" value={sysId} onChange={(e) => setSysId(e.target.value)}
                   className="bg-zinc-950 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono" />
          </Field>
          <Field label="Home Lat">
            <Input data-testid="input-home-lat" type="number" step="0.0001" value={homeLat} onChange={(e) => setHomeLat(e.target.value)}
                   className="bg-zinc-950 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono text-xs" />
          </Field>
          <Field label="Home Lon">
            <Input data-testid="input-home-lon" type="number" step="0.0001" value={homeLon} onChange={(e) => setHomeLon(e.target.value)}
                   className="bg-zinc-950 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono text-xs" />
          </Field>
        </div>

        {/* Type tabs */}
        <div>
          <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-400 mb-2">
            Connection Type
          </div>
          <div className="flex border border-zinc-700 rounded-sm overflow-hidden bg-zinc-900">
            <TabBtn testid="tab-conn-serial" active={type === "serial"}    onClick={() => setType("serial")}    icon={Cable} label="Serial" />
            <TabBtn testid="tab-conn-udp"    active={type === "udp"}       onClick={() => setType("udp")}       icon={Wifi}  label="UDP" />
            <TabBtn testid="tab-conn-tcp"    active={type === "tcp"}       onClick={() => setType("tcp")}       icon={Radio} label="TCP" />
            <TabBtn testid="tab-conn-sim"    active={type === "simulator"} onClick={() => setType("simulator")} icon={Zap}   label="Simulator" />
          </div>
        </div>

        {/* Per-type controls */}
        <div className="bg-zinc-950 border border-zinc-800 p-3 rounded-sm">
          {type === "serial" && (
            <div className="grid grid-cols-2 gap-3">
              <Field label="Port (COMx / /dev/tty*)">
                <Select value={serialPort} onValueChange={setSerialPort}>
                  <SelectTrigger data-testid="select-serial-port"
                                 className="bg-zinc-900 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-700 text-zinc-100 max-h-72">
                    {SERIAL_PORTS.map((p) => (
                      <SelectItem key={p} value={p} className="font-mono text-xs">{p}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Baud Rate">
                <Select value={String(baud)} onValueChange={(v) => setBaud(Number(v))}>
                  <SelectTrigger data-testid="select-baud-rate"
                                 className="bg-zinc-900 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-700 text-zinc-100">
                    {BAUD_RATES.map((b) => (
                      <SelectItem key={b} value={String(b)} className="font-mono text-xs">{b}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <p className="col-span-2 text-[10px] text-zinc-400 font-mono">
                APM/Pixhawk USB → 57600 · PX4 native USB → 115200 · SiK radio → 57600.
              </p>
            </div>
          )}

          {type === "udp" && (
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <Field label="Bind / Host">
                  <Input data-testid="input-udp-address" value={udpAddress}
                         onChange={(e) => setUdpAddress(e.target.value)}
                         className="bg-zinc-900 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono" />
                </Field>
              </div>
              <Field label="Port">
                <Select value={String(udpPort)} onValueChange={(v) => setUdpPort(Number(v))}>
                  <SelectTrigger data-testid="select-udp-port"
                                 className="bg-zinc-900 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-700 text-zinc-100">
                    {UDP_PORTS.map((p) => (
                      <SelectItem key={p} value={String(p)} className="font-mono text-xs">{p}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <p className="col-span-3 text-[10px] text-zinc-400 font-mono">
                Default ArduPilot SITL forwards MAVLink to <span className="text-zinc-100">127.0.0.1:14550</span>.
              </p>
            </div>
          )}

          {type === "tcp" && (
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <Field label="Host">
                  <Input data-testid="input-tcp-address" value={tcpAddress}
                         onChange={(e) => setTcpAddress(e.target.value)}
                         className="bg-zinc-900 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono" />
                </Field>
              </div>
              <Field label="Port">
                <Select value={String(tcpPort)} onValueChange={(v) => setTcpPort(Number(v))}>
                  <SelectTrigger data-testid="select-tcp-port"
                                 className="bg-zinc-900 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-700 text-zinc-100">
                    {TCP_PORTS.map((p) => (
                      <SelectItem key={p} value={String(p)} className="font-mono text-xs">{p}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            </div>
          )}

          {type === "simulator" && (
            <p className="text-xs text-zinc-200 font-mono py-1 leading-relaxed">
              Uses the built-in physics-lite simulator. No configuration required –
              the drone spawns at the home coordinates and responds to every flight
              command (arm, takeoff, missions, RTL, land) in real time.
            </p>
          )}
        </div>
      </div>
    </GcsModal>
  );
}
