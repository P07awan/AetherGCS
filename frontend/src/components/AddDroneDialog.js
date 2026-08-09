import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { dronesApi } from "@/services/api";
import { Cable, Wifi, Radio, Zap, MapPin, RefreshCw, Cpu } from "lucide-react";
import GcsModal from "@/components/GcsModal";
import { useGCS } from "@/store/gcsStore";

const BAUD_RATES = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600, 1500000];
const COMMON_UDP_PORTS = [14550, 14551, 14552, 14553, 14555, 14556];
const COMMON_TCP_PORTS = [5760, 5761, 5762, 5763, 5770];

const PRESETS = [
  { key: "sitl-udp", label: "SITL UDP :14550", icon: Zap,
    conf: { type: "udp", address: "127.0.0.1", port: 14550 } },
  { key: "sitl-tcp", label: "SITL TCP :5760", icon: Zap,
    conf: { type: "tcp", address: "127.0.0.1", port: 5760 } },
  { key: "apm-usb", label: "APM/Pixhawk USB @57600", icon: Cable,
    conf: { type: "serial", address: "COM3", baud: 57600 } },
  { key: "px4-usb", label: "PX4 USB @115200", icon: Cable,
    conf: { type: "serial", address: "COM4", baud: 115200 } },
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
  const userLocation = useGCS((s) => s.userLocation);
  const [name, setName] = useState("Drone Alpha");
  const [sysId, setSysId] = useState(1);
  const [type, setType] = useState("serial");
  const [serialPort, setSerialPort] = useState("COM3");
  const [baud, setBaud] = useState(57600);
  const [udpAddress, setUdpAddress] = useState("127.0.0.1");
  const [udpPort, setUdpPort] = useState(14550);
  const [tcpAddress, setTcpAddress] = useState("127.0.0.1");
  const [tcpPort, setTcpPort] = useState(5760);
  const [homeLat, setHomeLat] = useState(37.7749);
  const [homeLon, setHomeLon] = useState(-122.4194);
  const [busy, setBusy] = useState(false);
  const [homeTouched, setHomeTouched] = useState(false);
  
  // Real system serial port scanning
  const [detectedPorts, setDetectedPorts] = useState([]);
  const [scanningPorts, setScanningPorts] = useState(false);

  const scanPorts = useCallback(async () => {
    setScanningPorts(true);
    try {
      const list = await dronesApi.getSerialPorts();
      setDetectedPorts(list || []);
      if (list && list.length > 0 && !serialPort) {
        setSerialPort(list[0].port);
      }
    } catch (e) {
      console.warn("Failed to scan serial ports", e);
    } finally {
      setScanningPorts(false);
    }
  }, [serialPort]);

  useEffect(() => {
    if (open && type === "serial") {
      scanPorts();
    }
  }, [open, type, scanPorts]);

  // Auto-fill home from user's live GPS while unchanged
  useEffect(() => {
    if (userLocation && !homeTouched) {
      setHomeLat(Number(userLocation.lat.toFixed(6)));
      setHomeLon(Number(userLocation.lon.toFixed(6)));
    }
  }, [userLocation, homeTouched]);

  const useMyLocation = () => {
    if (!userLocation) return toast.error("GPS not available yet");
    setHomeLat(Number(userLocation.lat.toFixed(6)));
    setHomeLon(Number(userLocation.lon.toFixed(6)));
    setHomeTouched(false);
    toast.success("Home set to your current location");
  };

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
    if (type === "serial" && !serialPort.trim()) return toast.error("Serial port path required (e.g. COM3 or /dev/ttyUSB0)");
    
    setBusy(true);
    try {
      const drone = await dronesApi.create({
        name, system_id: Number(sysId), component_id: 1,
        connection: buildConnection(),
        home_lat: Number(homeLat), home_lon: Number(homeLon), home_alt: 0,
      });
      await dronesApi.connect(drone.id);
      toast.success(`${drone.name} added & connected successfully!`);
      onOpenChange(false);
    } catch (e) {
      const errDetail = e.response?.data?.detail || e.message;
      toast.error(`Connection Failed: ${errDetail}`, { duration: 7000 });
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
      subtitle="Connect Real Drone (Serial / USB / Telemetry Radio / UDP / TCP) or Simulator"
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
            {busy ? "Connecting..." : "Connect Drone"}
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
            <Input data-testid="input-home-lat" type="number" step="0.0001" value={homeLat}
                   onChange={(e) => { setHomeLat(e.target.value); setHomeTouched(true); }}
                   className="bg-zinc-950 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono text-xs" />
          </Field>
          <Field label="Home Lon">
            <Input data-testid="input-home-lon" type="number" step="0.0001" value={homeLon}
                   onChange={(e) => { setHomeLon(e.target.value); setHomeTouched(true); }}
                   className="bg-zinc-950 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono text-xs" />
          </Field>
        </div>

        {/* Use my GPS location */}
        <div className="flex items-center justify-between -mt-2">
          <span className="text-[10px] font-mono text-zinc-400">
            {userLocation
              ? <>Live GPS: <span className="text-[#00F0FF]">{userLocation.lat.toFixed(5)}, {userLocation.lon.toFixed(5)}</span> · ±{userLocation.accuracy?.toFixed(0)}m</>
              : "Acquiring GPS…"}
          </span>
          <button
            data-testid="btn-use-my-location"
            onClick={useMyLocation}
            disabled={!userLocation}
            className="text-[10px] font-mono uppercase text-[#00F0FF] border border-[#00F0FF]/50 hover:bg-[#00F0FF]/10 px-2 py-1 flex items-center gap-1.5 disabled:opacity-40"
          >
            <MapPin className="w-3 h-3" />
            Use My Location
          </button>
        </div>

        {/* Type tabs */}
        <div>
          <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-400 mb-2">
            Connection Type
          </div>
          <div className="flex border border-zinc-700 rounded-sm overflow-hidden bg-zinc-900">
            <TabBtn testid="tab-conn-serial" active={type === "serial"}    onClick={() => setType("serial")}    icon={Cable} label="Serial (USB/Radio)" />
            <TabBtn testid="tab-conn-udp"    active={type === "udp"}       onClick={() => setType("udp")}       icon={Wifi}  label="UDP" />
            <TabBtn testid="tab-conn-tcp"    active={type === "tcp"}       onClick={() => setType("tcp")}       icon={Radio} label="TCP" />
            <TabBtn testid="tab-conn-sim"    active={type === "simulator"} onClick={() => setType("simulator")} icon={Zap}   label="Simulator" />
          </div>
        </div>

        {/* Per-type controls */}
        <div className="bg-zinc-950 border border-zinc-800 p-3 rounded-sm">
          {type === "serial" && (
            <div className="space-y-3">
              <div className="grid grid-cols-6 gap-3">
                <div className="col-span-4">
                  <Field label="Serial Port / Device Path">
                    <Input
                      data-testid="input-serial-port"
                      value={serialPort}
                      onChange={(e) => setSerialPort(e.target.value)}
                      placeholder="e.g. COM3, COM18, or /dev/ttyUSB0"
                      className="bg-zinc-900 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono text-xs"
                    />
                  </Field>
                </div>
                <div className="col-span-2">
                  <Field label="Baud Rate">
                    <Select value={String(baud)} onValueChange={(v) => setBaud(Number(v))}>
                      <SelectTrigger data-testid="select-baud-rate"
                                     className="bg-zinc-900 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent position="popper" side="bottom" sideOffset={4} className="bg-zinc-900 border-zinc-700 text-zinc-100">
                        {BAUD_RATES.map((b) => (
                          <SelectItem key={b} value={String(b)} className="font-mono text-xs">{b}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </Field>
                </div>
              </div>

              {/* Detected Hardware COM Ports */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[10px] font-mono uppercase text-zinc-400 flex items-center gap-1">
                    <Cpu className="w-3 h-3 text-[#00F0FF]" /> Detected System Serial Ports
                  </span>
                  <button
                    type="button"
                    onClick={scanPorts}
                    disabled={scanningPorts}
                    className="text-[10px] font-mono text-[#00F0FF] hover:underline flex items-center gap-1"
                  >
                    <RefreshCw className={`w-3 h-3 ${scanningPorts ? "animate-spin" : ""}`} />
                    {scanningPorts ? "Scanning..." : "Scan Ports"}
                  </button>
                </div>

                {detectedPorts.length === 0 ? (
                  <div className="text-[11px] font-mono text-zinc-500 bg-zinc-900 border border-zinc-800 p-2 rounded-sm">
                    No physical COM ports detected on host. Plug in USB cable or Telemetry Radio module and click Scan.
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {detectedPorts.map((dp) => (
                      <button
                        key={dp.port}
                        type="button"
                        onClick={() => setSerialPort(dp.port)}
                        className={`text-[10px] font-mono px-2 py-1 rounded-sm border text-left transition-colors ${
                          serialPort === dp.port
                            ? "border-[#FFB000] bg-[#FFB000]/10 text-[#FFB000]"
                            : "border-zinc-700 bg-zinc-900 text-zinc-300 hover:border-zinc-500"
                        }`}
                        title={dp.description}
                      >
                        <span className="font-bold">{dp.port}</span>
                        <span className="text-zinc-400 ml-1 text-[9px]">({dp.description.slice(0, 30)})</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <p className="text-[10px] text-zinc-400 font-mono">
                Pixhawk/APM USB → 57600 · PX4 native USB → 115200 · SiK Telemetry Radio → 57600.
              </p>
            </div>
          )}

          {type === "udp" && (
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <Field label="Host / Listen Address">
                  <Input data-testid="input-udp-address" value={udpAddress}
                         onChange={(e) => setUdpAddress(e.target.value)}
                         placeholder="0.0.0.0 or 127.0.0.1 or 192.168.4.1"
                         className="bg-zinc-900 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono text-xs" />
                </Field>
              </div>
              <Field label="Port">
                <Input
                  data-testid="input-udp-port"
                  type="number"
                  value={udpPort}
                  onChange={(e) => setUdpPort(e.target.value)}
                  className="bg-zinc-900 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono text-xs"
                />
              </Field>
              <div className="col-span-3 flex items-center gap-1.5 flex-wrap">
                <span className="text-[10px] font-mono text-zinc-400">Common UDP Ports:</span>
                {COMMON_UDP_PORTS.map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setUdpPort(p)}
                    className="text-[9px] font-mono px-1.5 py-0.5 border border-zinc-700 hover:border-[#FFB000] text-zinc-300 rounded-xs"
                  >
                    :{p}
                  </button>
                ))}
              </div>
            </div>
          )}

          {type === "tcp" && (
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <Field label="Host / Drone IP">
                  <Input data-testid="input-tcp-address" value={tcpAddress}
                         onChange={(e) => setTcpAddress(e.target.value)}
                         placeholder="127.0.0.1 or 192.168.1.50"
                         className="bg-zinc-900 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono text-xs" />
                </Field>
              </div>
              <Field label="Port">
                <Input
                  data-testid="input-tcp-port"
                  type="number"
                  value={tcpPort}
                  onChange={(e) => setTcpPort(e.target.value)}
                  className="bg-zinc-900 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono text-xs"
                />
              </Field>
              <div className="col-span-3 flex items-center gap-1.5 flex-wrap">
                <span className="text-[10px] font-mono text-zinc-400">Common TCP Ports:</span>
                {COMMON_TCP_PORTS.map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setTcpPort(p)}
                    className="text-[9px] font-mono px-1.5 py-0.5 border border-zinc-700 hover:border-[#FFB000] text-zinc-300 rounded-xs"
                  >
                    :{p}
                  </button>
                ))}
              </div>
            </div>
          )}

          {type === "simulator" && (
            <p className="text-xs text-zinc-200 font-mono py-1 leading-relaxed">
              Uses the built-in physics-lite simulator. No hardware required –
              the drone spawns at the home coordinates and responds to all flight
              commands in real time.
            </p>
          )}
        </div>
      </div>
    </GcsModal>
  );
}
