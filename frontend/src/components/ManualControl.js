import React, { useRef, useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { useGCS, useDroneList } from "@/store/gcsStore";
import { commandsApi } from "@/services/api";
import VirtualJoystick from "./VirtualJoystick";
import { Plane, Keyboard, Zap, Radio } from "lucide-react";

export default function ManualControl() {
  const droneList = useDroneList();
  const selectedIds = useGCS((s) => s.selectedDroneIds);
  const activeId = useGCS((s) => s.activeDroneId);
  const setActive = useGCS((s) => s.setActive);
  const setSelected = useGCS((s) => s.setSelected);

  // Target drones calculation
  const isSwarm = selectedIds.length > 1;
  const getTargetIds = useCallback(() => {
    if (selectedIds.length > 0) return selectedIds;
    if (activeId) return [activeId];
    return [];
  }, [selectedIds, activeId]);

  const [maxSpeed, setMaxSpeed] = useState(5.0); // m/s
  const [maxZSpeed, setMaxZSpeed] = useState(2.0); // m/s
  const [maxYaw, setMaxYaw] = useState(1.0); // rad/s
  const [keyboardEnabled, setKeyboardEnabled] = useState(true);
  const [currentVels, setCurrentVels] = useState({ forward: 0, right: 0, up: 0, yaw_rate: 0 });

  // State of the sticks / keys
  const sticks = useRef({
    forward: 0,
    right: 0,
    up: 0,
    yaw_rate: 0,
  });

  const sendIntervalRef = useRef(null);

  const startLoop = useCallback(() => {
    if (!sendIntervalRef.current) {
      sendIntervalRef.current = setInterval(async () => {
        const { forward, right, up, yaw_rate } = sticks.current;
        setCurrentVels({
          forward: Number((forward * maxSpeed).toFixed(1)),
          right: Number((right * maxSpeed).toFixed(1)),
          up: Number((up * maxZSpeed).toFixed(1)),
          yaw_rate: Number((yaw_rate * maxYaw).toFixed(1)),
        });

        const ids = getTargetIds();
        if (ids.length === 0) return;

        try {
          await commandsApi.send(ids, "velocity", {
            forward: forward * maxSpeed,
            right: right * maxSpeed,
            up: up * maxZSpeed,
            yaw_rate: yaw_rate * maxYaw,
          });
        } catch (e) {
          // silently fail continuous velocity packets
        }
      }, 50); // 20Hz
    }
  }, [getTargetIds, maxSpeed, maxZSpeed, maxYaw]);

  const stopLoop = useCallback(() => {
    if (sendIntervalRef.current) {
      clearInterval(sendIntervalRef.current);
      sendIntervalRef.current = null;
    }
  }, []);

  const stopDrone = useCallback(async () => {
    sticks.current = { forward: 0, right: 0, up: 0, yaw_rate: 0 };
    setCurrentVels({ forward: 0, right: 0, up: 0, yaw_rate: 0 });
    const ids = getTargetIds();
    if (ids.length === 0) return;
    try {
      await commandsApi.send(ids, "velocity", { forward: 0, right: 0, up: 0, yaw_rate: 0 });
    } catch (e) {
      toast.error("Failed to stop drone");
    }
  }, [getTargetIds]);

  const checkLoopState = useCallback(() => {
    const { forward, right, up, yaw_rate } = sticks.current;
    const isZero = forward === 0 && right === 0 && up === 0 && yaw_rate === 0;

    if (!isZero) {
      startLoop();
    } else {
      stopLoop();
      stopDrone();
    }
  }, [startLoop, stopLoop, stopDrone]);

  const onLeftStick = (x, y) => {
    sticks.current.yaw_rate = x;
    sticks.current.up = y;
    checkLoopState();
  };

  const onRightStick = (x, y) => {
    sticks.current.right = x;
    sticks.current.forward = y;
    checkLoopState();
  };

  const onRelease = () => {
    checkLoopState();
  };

  // Keyboard navigation listener (W/A/S/D + Arrow keys + Space)
  useEffect(() => {
    if (!keyboardEnabled) return;

    const pressed = new Set();

    const handleKeyDown = (e) => {
      // Don't intercept if user is typing in an input or textarea
      if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;

      const key = e.key.toLowerCase();
      if (["w", "s", "a", "d", "arrowup", "arrowdown", "arrowleft", "arrowright", " "].includes(key)) {
        e.preventDefault();
        pressed.add(key);

        if (key === " ") {
          sticks.current = { forward: 0, right: 0, up: 0, yaw_rate: 0 };
          checkLoopState();
          return;
        }

        // Pitch & Roll (W/S & A/D)
        sticks.current.forward = pressed.has("w") ? 1 : pressed.has("s") ? -1 : 0;
        sticks.current.right = pressed.has("d") ? 1 : pressed.has("a") ? -1 : 0;

        // Altitude & Yaw (Arrows)
        sticks.current.up = pressed.has("arrowup") ? 1 : pressed.has("arrowdown") ? -1 : 0;
        sticks.current.yaw_rate = pressed.has("arrowright") ? 1 : pressed.has("arrowleft") ? -1 : 0;

        checkLoopState();
      }
    };

    const handleKeyUp = (e) => {
      if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;

      const key = e.key.toLowerCase();
      if (pressed.has(key)) {
        pressed.delete(key);

        sticks.current.forward = pressed.has("w") ? 1 : pressed.has("s") ? -1 : 0;
        sticks.current.right = pressed.has("d") ? 1 : pressed.has("a") ? -1 : 0;
        sticks.current.up = pressed.has("arrowup") ? 1 : pressed.has("arrowdown") ? -1 : 0;
        sticks.current.yaw_rate = pressed.has("arrowright") ? 1 : pressed.has("arrowleft") ? -1 : 0;

        checkLoopState();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
      stopLoop();
    };
  }, [keyboardEnabled, checkLoopState, stopLoop]);

  return (
    <div className="flex flex-col h-full bg-zinc-950 p-3 relative text-zinc-300 overflow-y-auto">
      {/* Top Header & Drone Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 border-b border-zinc-800">
        <div>
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-[#00FF41]" />
            <h2 className="text-sm font-display font-black text-zinc-100 uppercase tracking-wider">
              MANUAL FLIGHT CONTROLS
            </h2>
            <button
              onClick={() => setKeyboardEnabled(!keyboardEnabled)}
              className={`flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded border transition-colors ${
                keyboardEnabled
                  ? "bg-emerald-950/80 border-emerald-500 text-emerald-300"
                  : "bg-zinc-800 border-zinc-700 text-zinc-400 hover:text-zinc-200"
              }`}
              title="Toggle WASD & Arrow keyboard flight keys"
            >
              <Keyboard className="w-3 h-3" />
              KEYBOARD {keyboardEnabled ? "ON" : "OFF"}
            </button>
          </div>
          <p className="text-[11px] text-zinc-400 mt-0.5 font-mono">
            Drag joysticks or use WASD (Pitch/Roll) + Arrow Keys (Altitude/Yaw). Spacebar to stop.
          </p>
        </div>

        {/* Speed parameters */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs font-mono bg-zinc-900 border border-zinc-800 px-2 py-1 rounded">
            <span className="text-zinc-500 text-[10px]">XY SPEED:</span>
            <input
              type="number"
              min="0.5"
              step="0.5"
              max="20"
              value={maxSpeed}
              onChange={(e) => setMaxSpeed(Number(e.target.value))}
              className="bg-transparent text-zinc-100 font-bold w-12 text-center focus:outline-none"
            />
            <span className="text-zinc-500 text-[10px]">m/s</span>
          </div>

          <div className="flex items-center gap-1.5 text-xs font-mono bg-zinc-900 border border-zinc-800 px-2 py-1 rounded">
            <span className="text-zinc-500 text-[10px]">CLIMB:</span>
            <input
              type="number"
              min="0.5"
              step="0.5"
              max="5"
              value={maxZSpeed}
              onChange={(e) => setMaxZSpeed(Number(e.target.value))}
              className="bg-transparent text-zinc-100 font-bold w-10 text-center focus:outline-none"
            />
            <span className="text-zinc-500 text-[10px]">m/s</span>
          </div>

          <button
            onClick={stopDrone}
            className="h-7 px-3 bg-red-950/80 hover:bg-red-900 border border-red-700 text-red-300 font-mono text-[10px] font-bold uppercase rounded tracking-wider"
          >
            STOP / HOVER
          </button>
        </div>
      </div>

      {/* Fleet Target Selection Pills */}
      <div className="py-2.5 flex items-center gap-2 border-b border-zinc-800/80 flex-wrap">
        <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 shrink-0">
          PILOTING TARGET:
        </span>

        {droneList.length > 1 && (
          <button
            data-testid="target-pill-all"
            onClick={() => {
              setSelected(droneList.map((d) => d.id));
            }}
            className={`px-2.5 py-1 text-xs font-mono font-bold uppercase tracking-wider rounded border flex items-center gap-1.5 transition-colors ${
              isSwarm
                ? "bg-amber-950 border-amber-500 text-amber-300 shadow-sm"
                : "bg-zinc-900 border-zinc-700 text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            SWARM // ALL ({droneList.length})
          </button>
        )}

        {droneList.map((d) => {
          const isTarget = (!isSwarm && (selectedIds.includes(d.id) || (selectedIds.length === 0 && activeId === d.id)));
          const alt = d.telemetry?.altitude_relative != null ? `${d.telemetry.altitude_relative.toFixed(1)}m` : "--";
          const armed = d.telemetry?.armed;

          return (
            <button
              key={d.id}
              data-testid={`target-pill-${d.id}`}
              onClick={() => {
                setActive(d.id);
                setSelected([d.id]);
              }}
              className={`px-2.5 py-1 text-xs font-mono font-semibold rounded border flex items-center gap-2 transition-colors ${
                isTarget
                  ? "bg-[#00F0FF]/10 border-[#00F0FF] text-[#00F0FF] shadow-sm"
                  : "bg-zinc-900 border-zinc-800 text-zinc-300 hover:border-zinc-700 hover:text-zinc-100"
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${armed ? "bg-emerald-400 animate-pulse" : "bg-zinc-600"}`} />
              <span className="font-bold">{d.name}</span>
              <span className="text-[10px] opacity-75 font-normal">
                [{d.telemetry?.flight_mode || "DISCONNECTED"} · {alt}]
              </span>
            </button>
          );
        })}

        {droneList.length === 0 && (
          <span className="text-xs font-mono text-zinc-500 italic">No drones registered.</span>
        )}
      </div>

      {/* Live Velocity Readout */}
      <div className="py-2 flex items-center justify-between text-[11px] font-mono bg-zinc-900/60 px-3 rounded mt-2 border border-zinc-800">
        <div className="flex gap-4">
          <span className={currentVels.forward !== 0 ? "text-amber-400 font-bold" : "text-zinc-500"}>
            PITCH/FWD: {currentVels.forward > 0 ? `+${currentVels.forward}` : currentVels.forward} m/s
          </span>
          <span className={currentVels.right !== 0 ? "text-amber-400 font-bold" : "text-zinc-500"}>
            ROLL/RIGHT: {currentVels.right > 0 ? `+${currentVels.right}` : currentVels.right} m/s
          </span>
          <span className={currentVels.up !== 0 ? "text-emerald-400 font-bold" : "text-zinc-500"}>
            ALT/CLIMB: {currentVels.up > 0 ? `+${currentVels.up}` : currentVels.up} m/s
          </span>
          <span className={currentVels.yaw_rate !== 0 ? "text-cyan-400 font-bold" : "text-zinc-500"}>
            YAW: {currentVels.yaw_rate > 0 ? `+${currentVels.yaw_rate}` : currentVels.yaw_rate} rad/s
          </span>
        </div>
        <div className="text-zinc-500 text-[10px]">
          CONTROLLING: <span className="text-[#00F0FF] font-bold">{isSwarm ? `SWARM (${selectedIds.length} DRONES)` : droneList.find(d => d.id === (selectedIds[0] || activeId))?.name || "NONE"}</span>
        </div>
      </div>

      {/* Joysticks Area */}
      <div className="flex-1 flex items-center justify-around py-4">
        {/* Left Stick Area */}
        <div className="flex flex-col items-center">
          <VirtualJoystick size={160} onChange={onLeftStick} onRelease={onRelease} />
          <div className="mt-3 grid grid-cols-2 gap-x-8 gap-y-0.5 text-center font-mono text-[11px] text-zinc-400">
            <span>&larr; YAW &rarr;</span>
            <span>&uarr; CLIMB &darr;</span>
          </div>
          <span className="text-[10px] text-zinc-600 font-mono mt-0.5">Arrow Left/Right / Up/Down</span>
        </div>

        {/* Right Stick Area */}
        <div className="flex flex-col items-center">
          <VirtualJoystick size={160} onChange={onRightStick} onRelease={onRelease} />
          <div className="mt-3 grid grid-cols-2 gap-x-8 gap-y-0.5 text-center font-mono text-[11px] text-zinc-400">
            <span>&larr; ROLL &rarr;</span>
            <span>&uarr; PITCH &darr;</span>
          </div>
          <span className="text-[10px] text-zinc-600 font-mono mt-0.5">A/D Keys / W/S Keys</span>
        </div>
      </div>
    </div>
  );
}
