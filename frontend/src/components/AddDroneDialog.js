import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { dronesApi } from "@/services/api";
import { Cable, Wifi, Radio, Zap, MapPin, RefreshCw, Cpu, AlertTriangle } from "lucide-react";
import GcsModal from "@/components/GcsModal";
import { useGCS } from "@/store/gcsStore";

const BAUD_RATES = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600, 1500000];
const COMMON_COM_PORTS = ["COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "/dev/ttyUSB0", "/dev/ttyACM0"];
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

const Field = ({ label, children, error }) => (
  <div>
    <label className="text-[10px] font-mono uppercase text-zinc-400">{label}</label>
    <div className="mt-1">{children}</div>
    {error && (
      <div className="flex items-center gap-1 mt-1">
        <AlertTriangle className="w-3 h-3 text-red-400 shrink-0" />
        <p className="text-[10px] text-red-400 font-mono">{error}</p>
      </div>
    )}
  </div>
);

const NATO_NAMES = [
  "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot",
  "Golf", "Hotel", "India", "Juliet", "Kilo", "Lima",
  "Mike", "November", "Oscar", "Papa", "Quebec", "Romeo",
  "Sierra", "Tango", "Uniform", "Victor", "Whiskey", "X-ray", "Yankee", "Zulu"
];

// ---- Helpers ---------------------------------------------------------------

/** Normalise local-loopback variants to a canonical token for comparison. */
function normaliseHost(addr) {
  const clean = (addr || "").trim().toLowerCase();
  return (clean === "" || clean === "0.0.0.0" || clean === "localhost") ? "127.0.0.1" : clean;
}

/** Case-insensitive serial port comparison. */
function normaliseSerial(path) {
  return (path || "").trim().toUpperCase();
}

/**
 * Find the lowest available system ID (1–255) not already assigned to a drone.
 * Never returns 0.
 */
function getNextAvailableSystemId(droneList) {
  const used = new Set(
    droneList.map((d) => Number(d.system_id)).filter((id) => Number.isInteger(id) && id >= 1)
  );
  let id = 1;
  while (used.has(id)) id++;
  return id;
}

// ---- Main component --------------------------------------------------------

export default function AddDroneDialog({ open, onOpenChange }) {
  const userLocation = useGCS((s) => s.userLocation);
  const dronesMap = useGCS((s) => s.drones);
  const droneList = Object.values(dronesMap);

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

  // Per-field inline validation errors
  const [fieldErrors, setFieldErrors] = useState({});

  // Real system serial port scanning
  const [detectedPorts, setDetectedPorts] = useState([]);
  const [scanningPorts, setScanningPorts] = useState(false);

  // Initialize unique name and system ID on open
  useEffect(() => {
    if (open) {
      const existingNames = new Set(droneList.map((d) => d.name));

      // Always recompute from the live drone list — not from stale dialog state
      const nextSysId = getNextAvailableSystemId(droneList);
      setSysId(nextSysId);

      const nextName = NATO_NAMES.map((n) => `Drone ${n}`).find((n) => !existingNames.has(n))
        || `Drone ${droneList.length + 1}`;
      setName(nextName);

      // Auto-increment UDP port to the first unused one
      if (type === "udp") {
        const usedPorts = new Set(
          droneList
            .filter((d) => d.connection?.connection_type === "udp")
            .map((d) => Number(d.connection.port))
        );
        let nextPort = 14550;
        while (usedPorts.has(nextPort)) nextPort++;
        setUdpPort(nextPort);
      }

      if (!homeTouched) {
        let baseLat = userLocation?.lat ?? 37.7749;
        let baseLon = userLocation?.lon ?? -122.4194;
        if (droneList.length > 0) {
          const cosLat = Math.cos((baseLat * Math.PI) / 180) || 1.0;
          const dlon = (20.0 * droneList.length) / (111139.0 * cosLat);
          baseLon += dlon;
        }
        setHomeLat(Number(baseLat.toFixed(6)));
        setHomeLon(Number(baseLon.toFixed(6)));
      }

      setFieldErrors({});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

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

  // Auto-fill home from user's live GPS while unchanged if single drone
  useEffect(() => {
    if (userLocation && !homeTouched && droneList.length === 0) {
      setHomeLat(Number(userLocation.lat.toFixed(6)));
      setHomeLon(Number(userLocation.lon.toFixed(6)));
    }
  }, [userLocation, homeTouched, droneList.length]);

  const useMyLocation = () => {
    if (!userLocation) return toast.error("GPS not available yet");
    let baseLon = userLocation.lon;
    if (droneList.length > 0) {
      const cosLat = Math.cos((userLocation.lat * Math.PI) / 180) || 1.0;
      baseLon += (20.0 * droneList.length) / (111139.0 * cosLat);
    }
    setHomeLat(Number(userLocation.lat.toFixed(6)));
    setHomeLon(Number(baseLon.toFixed(6)));
    setHomeTouched(true);
    toast.success("Home set to your current location (with fleet offset)");
  };

  const applyPreset = (p) => {
    const c = p.conf;
    setType(c.type);
    if (c.type === "serial") { setSerialPort(c.address); setBaud(c.baud); }
    if (c.type === "udp") { setUdpAddress(c.address); setUdpPort(c.port); }
    if (c.type === "tcp") { setTcpAddress(c.address); setTcpPort(c.port); }
    setFieldErrors({});
  };

  const buildConnection = () => {
    if (type === "serial") return { connection_type: "serial", address: serialPort, port: null, baud_rate: Number(baud), auto_reconnect: true };
    if (type === "udp")    return { connection_type: "udp",    address: udpAddress,  port: Number(udpPort), baud_rate: null, auto_reconnect: true };
    if (type === "tcp")    return { connection_type: "tcp",    address: tcpAddress,  port: Number(tcpPort), baud_rate: null, auto_reconnect: true };
    return { connection_type: "simulator", address: "sim://local", port: 0, baud_rate: null, auto_reconnect: true };
  };

  // ---- Client-side validation (mirrors backend rules) --------------------
  const validate = () => {
    const errors = {};

    // Read the latest drone list each time — dialog may stay open across adds
    const latestDrones = Object.values(dronesMap);
    const numSysId = Number(sysId);

    // Name
    if (!name.trim()) {
      errors.name = "Drone name is required.";
    }

    // System ID range (1–255 per MAVLink spec)
    if (!Number.isInteger(numSysId) || numSysId < 1 || numSysId > 255) {
      errors.sysId = "System ID must be an integer between 1 and 255.";
    } else {
      // Duplicate system ID check
      const conflict = latestDrones.find((d) => Number(d.system_id) === numSysId);
      if (conflict) {
        errors.sysId = `System ID ${numSysId} is already used by "${conflict.name}". Choose a different ID.`;
      }
    }

    if (type === "serial") {
      if (!serialPort.trim()) {
        errors.serialPort = "Serial port path is required (e.g. COM3 or /dev/ttyUSB0).";
      } else {
        // Duplicate serial port check
        const conflict = latestDrones.find(
          (d) =>
            d.connection?.connection_type === "serial" &&
            normaliseSerial(d.connection.address) === normaliseSerial(serialPort)
        );
        if (conflict) {
          errors.serialPort = `Port ${serialPort} is already in use by "${conflict.name}". Each drone needs a unique COM port.`;
        }
      }
    }

    if (type === "udp") {
      const normAddr = normaliseHost(udpAddress);
      const portNum = Number(udpPort);
      if (!portNum || portNum < 1 || portNum > 65535) {
        errors.udpPort = "UDP port must be between 1 and 65535.";
      } else {
        const conflict = latestDrones.find(
          (d) =>
            d.connection?.connection_type === "udp" &&
            normaliseHost(d.connection.address) === normAddr &&
            Number(d.connection.port) === portNum
        );
        if (conflict) {
          errors.udpPort = `UDP ${udpAddress}:${portNum} is already used by "${conflict.name}". Each SITL drone needs a unique port (e.g. 14550, 14551, 14552…).`;
        }
      }
    }

    if (type === "tcp") {
      const portNum = Number(tcpPort);
      if (!portNum || portNum < 1 || portNum > 65535) {
        errors.tcpPort = "TCP port must be between 1 and 65535.";
      } else {
        const conflict = latestDrones.find(
          (d) =>
            d.connection?.connection_type === "tcp" &&
            normaliseHost(d.connection.address) === normaliseHost(tcpAddress) &&
            Number(d.connection.port) === portNum
        );
        if (conflict) {
          errors.tcpPort = `TCP ${tcpAddress}:${portNum} is already used by "${conflict.name}". Choose a different port.`;
        }
      }
    }

    if (type !== "simulator" && !userLocation && !homeTouched) {
      errors.home = "GPS location is required before adding a real drone.";
    }

    return errors;
  };

  const submit = async () => {
    const errors = validate();
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      // Show the first error as a toast so it's impossible to miss
      toast.error(Object.values(errors)[0], { duration: 5000 });
      return;
    }
    setFieldErrors({});
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

  // Count how many drones already use each UDP port — for the hint panel
  const usedUdpPorts = new Set(
    droneList
      .filter((d) => d.connection?.connection_type === "udp")
      .map((d) => Number(d.connection.port))
  );

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
            <Field label="Drone Name" error={fieldErrors.name}>
              <Input data-testid="input-drone-name" value={name} onChange={(e) => setName(e.target.value)}
                     className={`bg-zinc-950 border-zinc-700 rounded-sm h-9 text-zinc-100 ${fieldErrors.name ? "border-red-500" : ""}`} />
            </Field>
          </div>
          <Field label="Sys ID (1–255)" error={fieldErrors.sysId}>
            <Input data-testid="input-drone-sysid" type="number" min="1" max="255" value={sysId}
                   onChange={(e) => setSysId(e.target.value)}
                   className={`bg-zinc-950 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono ${fieldErrors.sysId ? "border-red-500" : ""}`} />
          </Field>
          <Field label="Home Lat">
            <Input data-testid="input-home-lat" type="number" step="0.0001" value={homeLat}
                   onChange={(e) => { setHomeLat(e.target.value); setHomeTouched(true); }}
                   className="bg-zinc-950 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono text-xs" />
          </Field>
          <Field label="Home Lon" error={fieldErrors.home}>
            <Input data-testid="input-home-lon" type="number" step="0.0001" value={homeLon}
                   onChange={(e) => { setHomeLon(e.target.value); setHomeTouched(true); }}
                   className="bg-zinc-950 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono text-xs" />
          </Field>
        </div>

        {/* Use my GPS location */}
        <div className="flex items-center justify-between -mt-2">
          <span className="text-[10px] font-mono text-zinc-400">
            {userLocation
              ? <><span className="text-[#00F0FF]">{userLocation.lat.toFixed(5)}, {userLocation.lon.toFixed(5)}</span> · ±{userLocation.accuracy?.toFixed(0)}m</>
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
            <TabBtn testid="tab-conn-serial" active={type === "serial"}    onClick={() => setType("serial")}    icon={Cable} label="Serial (COM / USB)" />
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
                  <Field label="COM Port / Device Path" error={fieldErrors.serialPort}>
                    <Input
                      data-testid="input-serial-port"
                      value={serialPort}
                      onChange={(e) => setSerialPort(e.target.value)}
                      placeholder="e.g. COM3, COM4, COM18, or /dev/ttyUSB0"
                      className={`bg-zinc-900 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono text-xs font-bold text-[#FFB000] ${fieldErrors.serialPort ? "border-red-500" : ""}`}
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
                    <Cpu className="w-3 h-3 text-[#00F0FF]" /> Hardware Detected COM Ports
                  </span>
                  <button
                    type="button"
                    onClick={scanPorts}
                    disabled={scanningPorts}
                    className="text-[10px] font-mono text-[#00F0FF] hover:underline flex items-center gap-1"
                  >
                    <RefreshCw className={`w-3 h-3 ${scanningPorts ? "animate-spin" : ""}`} />
                    {scanningPorts ? "Scanning..." : "Rescan Hardware"}
                  </button>
                </div>

                {detectedPorts.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {detectedPorts.map((dp) => (
                      <button
                        key={dp.port}
                        type="button"
                        onClick={() => setSerialPort(dp.port)}
                        className={`text-[10px] font-mono px-2 py-1 rounded-sm border text-left transition-colors flex items-center gap-1.5 ${
                          serialPort === dp.port
                            ? "border-[#00FF41] bg-[#00FF41]/10 text-[#00FF41] font-bold"
                            : "border-zinc-700 bg-zinc-900 text-zinc-300 hover:border-zinc-500"
                        }`}
                        title={dp.description}
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-[#00FF41] animate-pulse" />
                        <span>{dp.port}</span>
                        <span className="text-zinc-400 text-[9px]">({(dp.description || "Active").slice(0, 24)})</span>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="text-[10px] font-mono text-zinc-500 bg-zinc-900/60 border border-zinc-800/80 p-1.5 rounded-sm mb-2 flex items-center justify-between">
                    <span>No USB/Telemetry hardware auto-detected yet. Select standard COM port below:</span>
                  </div>
                )}

                {/* Always-visible Quick Select COM Buttons */}
                <div className="space-y-1">
                  <div className="text-[10px] font-mono text-zinc-400 flex items-center justify-between">
                    <span className="font-semibold text-zinc-300">Quick Select COM Port:</span>
                    <span className="text-[10px] text-[#FFB000] font-mono font-bold">Active: {serialPort || "None"}</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {COMMON_COM_PORTS.map((p) => (
                      <button
                        key={p}
                        type="button"
                        onClick={() => setSerialPort(p)}
                        className={`text-[10px] font-mono px-2.5 py-1 rounded-sm border transition-colors ${
                          serialPort === p
                            ? "border-[#FFB000] bg-[#FFB000]/20 text-[#FFB000] font-bold shadow-sm"
                            : "border-zinc-800 bg-zinc-900 text-zinc-300 hover:border-zinc-600 hover:text-zinc-100"
                        }`}
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <p className="text-[10px] text-zinc-400 font-mono">
                Pixhawk/APM USB → 57600 · PX4 native USB → 115200 · SiK Telemetry Radio → 57600.
              </p>
            </div>
          )}

          {type === "udp" && (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <Field label="Host / Listen Address">
                    <Input data-testid="input-udp-address" value={udpAddress}
                           onChange={(e) => setUdpAddress(e.target.value)}
                           placeholder="0.0.0.0 or 127.0.0.1 or 192.168.4.1"
                           className="bg-zinc-900 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono text-xs" />
                  </Field>
                </div>
                <Field label="Port" error={fieldErrors.udpPort}>
                  <Input
                    data-testid="input-udp-port"
                    type="number"
                    value={udpPort}
                    onChange={(e) => setUdpPort(e.target.value)}
                    className={`bg-zinc-900 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono text-xs ${fieldErrors.udpPort ? "border-red-500" : ""}`}
                  />
                </Field>
                <div className="col-span-3 flex items-center gap-1.5 flex-wrap">
                  <span className="text-[10px] font-mono text-zinc-400">Common UDP Ports:</span>
                  {COMMON_UDP_PORTS.map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setUdpPort(p)}
                      className={`text-[9px] font-mono px-1.5 py-0.5 border rounded-xs transition-colors ${
                        usedUdpPorts.has(p)
                          ? "border-red-700/60 text-red-400 bg-red-900/10 cursor-not-allowed"
                          : "border-zinc-700 hover:border-[#FFB000] text-zinc-300"
                      }`}
                      title={usedUdpPorts.has(p) ? `Port ${p} is already used by another drone` : `Use port ${p}`}
                    >
                      :{p}{usedUdpPorts.has(p) ? " ✕" : ""}
                    </button>
                  ))}
                </div>
              </div>
              {/* SITL configuration guide */}
              <div className="bg-zinc-900 border border-zinc-700 rounded-sm p-2 text-[10px] font-mono text-zinc-400 space-y-0.5">
                <p className="text-zinc-300 font-semibold uppercase tracking-wider">UDP / SITL Configuration</p>
                <p>Worker listens on: <span className="text-[#00F0FF]">udpin:0.0.0.0:{udpPort}</span></p>
                <p>Configure SITL to send MAVLink to: <span className="text-[#FFB000]">127.0.0.1:{udpPort}</span></p>
                <p className="text-zinc-500 pt-0.5">Each SITL drone must use a unique UDP port. Example: Drone 1 → :14550 · Drone 2 → :14551</p>
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
              <Field label="Port" error={fieldErrors.tcpPort}>
                <Input
                  data-testid="input-tcp-port"
                  type="number"
                  value={tcpPort}
                  onChange={(e) => setTcpPort(e.target.value)}
                  className={`bg-zinc-900 border-zinc-700 rounded-sm h-9 text-zinc-100 font-mono text-xs ${fieldErrors.tcpPort ? "border-red-500" : ""}`}
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
