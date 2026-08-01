import { useState } from "react";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { dronesApi } from "@/services/api";

const defaults = {
  simulator: { address: "sim://local", port: 0 },
  udp: { address: "127.0.0.1", port: 14550 },
  tcp: { address: "127.0.0.1", port: 5760 },
  serial: { address: "/dev/ttyUSB0", baud_rate: 57600 },
};

export default function AddDroneDialog({ open, onOpenChange }) {
  const [name, setName] = useState("Drone Alpha");
  const [sysId, setSysId] = useState(1);
  const [type, setType] = useState("simulator");
  const [address, setAddress] = useState(defaults.simulator.address);
  const [port, setPort] = useState(defaults.simulator.port);
  const [baud, setBaud] = useState(57600);
  const [homeLat, setHomeLat] = useState(37.7749);
  const [homeLon, setHomeLon] = useState(-122.4194);
  const [busy, setBusy] = useState(false);

  const onTypeChange = (t) => {
    setType(t);
    const d = defaults[t];
    setAddress(d.address);
    setPort(d.port || 0);
    if (d.baud_rate) setBaud(d.baud_rate);
  };

  const submit = async () => {
    if (!name.trim()) return toast.error("Name required");
    setBusy(true);
    try {
      const drone = await dronesApi.create({
        name,
        system_id: Number(sysId),
        component_id: 1,
        connection: {
          connection_type: type,
          address,
          port: type === "serial" ? null : Number(port),
          baud_rate: type === "serial" ? Number(baud) : null,
          auto_reconnect: true,
        },
        home_lat: Number(homeLat),
        home_lon: Number(homeLon),
        home_alt: 0,
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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid="add-drone-dialog"
        className="bg-zinc-950 border border-zinc-800 rounded-sm max-w-md text-zinc-100"
      >
        <DialogHeader>
          <DialogTitle className="font-display tracking-wider">ADD DRONE</DialogTitle>
        </DialogHeader>

        <div className="space-y-3 py-2">
          <div>
            <label className="text-[10px] font-mono uppercase text-zinc-500">Name</label>
            <Input
              data-testid="input-drone-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="bg-zinc-900 border-zinc-800 rounded-sm mt-1"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-mono uppercase text-zinc-500">System ID</label>
              <Input
                data-testid="input-drone-sysid"
                type="number"
                value={sysId}
                onChange={(e) => setSysId(e.target.value)}
                className="bg-zinc-900 border-zinc-800 rounded-sm mt-1"
              />
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase text-zinc-500">Connection</label>
              <Select value={type} onValueChange={onTypeChange}>
                <SelectTrigger
                  data-testid="select-connection-type"
                  className="bg-zinc-900 border-zinc-800 rounded-sm mt-1"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-zinc-950 border-zinc-800 text-zinc-100">
                  <SelectItem value="simulator">Simulator</SelectItem>
                  <SelectItem value="udp">UDP</SelectItem>
                  <SelectItem value="tcp">TCP</SelectItem>
                  <SelectItem value="serial">Serial</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="text-[10px] font-mono uppercase text-zinc-500">
                {type === "serial" ? "Device" : "Address"}
              </label>
              <Input
                data-testid="input-drone-address"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className="bg-zinc-900 border-zinc-800 rounded-sm mt-1 font-mono"
              />
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase text-zinc-500">
                {type === "serial" ? "Baud" : "Port"}
              </label>
              <Input
                data-testid="input-drone-port"
                type="number"
                value={type === "serial" ? baud : port}
                onChange={(e) =>
                  type === "serial" ? setBaud(e.target.value) : setPort(e.target.value)
                }
                className="bg-zinc-900 border-zinc-800 rounded-sm mt-1 font-mono"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-mono uppercase text-zinc-500">Home Lat</label>
              <Input
                data-testid="input-home-lat"
                type="number"
                step="0.0001"
                value={homeLat}
                onChange={(e) => setHomeLat(e.target.value)}
                className="bg-zinc-900 border-zinc-800 rounded-sm mt-1 font-mono"
              />
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase text-zinc-500">Home Lon</label>
              <Input
                data-testid="input-home-lon"
                type="number"
                step="0.0001"
                value={homeLon}
                onChange={(e) => setHomeLon(e.target.value)}
                className="bg-zinc-900 border-zinc-800 rounded-sm mt-1 font-mono"
              />
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button
            data-testid="btn-add-drone-cancel"
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="border-zinc-800 hover:bg-zinc-900 rounded-sm"
          >
            Cancel
          </Button>
          <Button
            data-testid="btn-add-drone-submit"
            disabled={busy}
            onClick={submit}
            className="bg-[#FFB000] hover:bg-[#FFC033] text-black rounded-sm"
          >
            {busy ? "Adding..." : "Add & Connect"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
