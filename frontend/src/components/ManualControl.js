import React, { useRef, useEffect, useState } from "react";
import { toast } from "sonner";
import { useGCS, useSelectedDrones } from "@/store/gcsStore";
import { commandsApi } from "@/services/api";
import VirtualJoystick from "./VirtualJoystick";

export default function ManualControl() {
  const selected = useSelectedDrones();
  const activeId = useGCS((s) => s.activeDroneId);
  const getTargetIds = () => (selected.length > 0 ? selected.map((d) => d.id) : activeId ? [activeId] : []);

  const [maxSpeed, setMaxSpeed] = useState(5.0); // m/s
  const [maxZSpeed, setMaxZSpeed] = useState(2.0); // m/s
  const [maxYaw, setMaxYaw] = useState(1.0); // rad/s

  // State of the joysticks
  const sticks = useRef({
    forward: 0,
    right: 0,
    up: 0,
    yaw_rate: 0,
  });

  const sendIntervalRef = useRef(null);

  const startLoop = () => {
    if (!sendIntervalRef.current) {
      sendIntervalRef.current = setInterval(async () => {
        const { forward, right, up, yaw_rate } = sticks.current;
        // Optimization: don't send if all 0 and we haven't just snapped to zero
        // Actually, it's safer to always send while the loop is active.
        
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
          // silently fail continuous commands to avoid log spam, 
          // but could add a subtle indicator if needed
        }
      }, 250); // 4Hz
    }
  };

  const stopLoop = () => {
    if (sendIntervalRef.current) {
      clearInterval(sendIntervalRef.current);
      sendIntervalRef.current = null;
    }
  };

  const stopDrone = async () => {
    sticks.current = { forward: 0, right: 0, up: 0, yaw_rate: 0 };
    const ids = getTargetIds();
    if (ids.length === 0) return;
    try {
      await commandsApi.send(ids, "velocity", { forward: 0, right: 0, up: 0, yaw_rate: 0 });
    } catch (e) {
      toast.error("Failed to stop drone");
    }
  };

  const checkLoopState = () => {
    const { forward, right, up, yaw_rate } = sticks.current;
    const isZero = forward === 0 && right === 0 && up === 0 && yaw_rate === 0;
    
    if (!isZero) {
      startLoop();
    } else {
      stopLoop();
      stopDrone(); // Send a final zero-velocity packet
    }
  };

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
    // Check loop state will catch the 0s and stop the drone
    checkLoopState();
  };

  useEffect(() => {
    return () => {
      stopLoop();
    };
  }, []);

  return (
    <div className="flex flex-col h-full bg-zinc-900 p-4 relative text-zinc-300">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-display font-bold text-zinc-100">MANUAL RC CONTROL</h2>
          <p className="text-xs text-zinc-500 max-w-sm">
            Drag the joysticks to manually fly the selected drone(s). 
            Left stick controls Altitude and Yaw. Right stick controls Pitch and Roll.
          </p>
        </div>
        
        {/* Speed settings */}
        <div className="flex gap-4">
          <div className="flex flex-col text-xs font-mono">
            <span className="text-zinc-500 mb-1">XY MAX (m/s)</span>
            <input 
              type="number" min="0" step="0.5" value={maxSpeed} 
              onChange={(e) => setMaxSpeed(Number(e.target.value))}
              className="bg-zinc-800 border border-zinc-700 px-2 py-1 rounded w-20 outline-none"
            />
          </div>
          <div className="flex flex-col text-xs font-mono">
            <span className="text-zinc-500 mb-1">Z MAX (m/s)</span>
            <input 
              type="number" min="0" step="0.5" value={maxZSpeed} 
              onChange={(e) => setMaxZSpeed(Number(e.target.value))}
              className="bg-zinc-800 border border-zinc-700 px-2 py-1 rounded w-20 outline-none"
            />
          </div>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-around">
        
        {/* Left Stick Area */}
        <div className="flex flex-col items-center">
          <VirtualJoystick size={160} onChange={onLeftStick} onRelease={onRelease} />
          <div className="mt-4 grid grid-cols-2 gap-x-8 gap-y-1 text-center font-mono text-xs text-zinc-500">
            <span>&larr; YAW &rarr;</span>
            <span>&uarr; UP &darr;</span>
          </div>
        </div>

        {/* Right Stick Area */}
        <div className="flex flex-col items-center">
          <VirtualJoystick size={160} onChange={onRightStick} onRelease={onRelease} />
          <div className="mt-4 grid grid-cols-2 gap-x-8 gap-y-1 text-center font-mono text-xs text-zinc-500">
            <span>&larr; ROLL &rarr;</span>
            <span>&uarr; PITCH &darr;</span>
          </div>
        </div>

      </div>
    </div>
  );
}
