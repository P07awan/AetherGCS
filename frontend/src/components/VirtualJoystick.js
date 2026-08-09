import React, { useRef, useState, useCallback, useEffect } from "react";

/**
 * VirtualJoystick
 * 
 * @param {number} size - The diameter of the joystick base (default 150)
 * @param {function} onChange - Callback receiving (x, y) coordinates from -1.0 to 1.0
 * @param {function} onRelease - Callback triggered when the joystick is released
 */
export default function VirtualJoystick({ size = 150, onChange, onRelease }) {
  const baseRef = useRef(null);
  const knobRef = useRef(null);
  const dragState = useRef({ isDragging: false, cx: 0, cy: 0, r: 0 });
  const rafRef = useRef(null);
  
  // Normalized x, y (-1 to 1)
  const lastVal = useRef({ x: 0, y: 0 });

  const applyLive = useCallback((px, py) => {
    if (knobRef.current) {
      knobRef.current.style.transform = `translate3d(${px}px, ${py}px, 0)`;
    }
  }, []);

  const setTransition = (active) => {
    if (knobRef.current) {
      knobRef.current.style.transition = active ? "transform 0.15s ease-out" : "none";
    }
  };

  const handlePointerDown = (e) => {
    if (!baseRef.current) return;
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);

    const rect = baseRef.current.getBoundingClientRect();
    // Center of the joystick
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const r = rect.width / 2;

    dragState.current = { isDragging: true, cx, cy, r };
    setTransition(false); // Disable transition for instant drag
    processMove(e.clientX, e.clientY);
  };

  const processMove = (clientX, clientY) => {
    const { cx, cy, r } = dragState.current;
    
    // Calculate raw offset from center
    let dx = clientX - cx;
    let dy = clientY - cy;

    // Constrain to circle radius
    const distance = Math.sqrt(dx * dx + dy * dy);
    if (distance > r) {
      dx = (dx / distance) * r;
      dy = (dy / distance) * r;
    }

    // Apply visual position
    applyLive(dx, dy);

    // Normalize coordinates to -1.0 ... 1.0
    // Note: typical joystick Y is positive UP. Screen Y is positive DOWN.
    // So we invert Y: -dy / r
    const nx = dx / r;
    const ny = -dy / r;

    // Only fire onChange if values changed significantly to save CPU
    if (Math.abs(nx - lastVal.current.x) > 0.01 || Math.abs(ny - lastVal.current.y) > 0.01) {
      lastVal.current = { x: nx, y: ny };
      if (onChange) onChange(nx, ny);
    }
  };

  const handlePointerMove = (e) => {
    if (!dragState.current.isDragging) return;
    
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    
    rafRef.current = requestAnimationFrame(() => {
      processMove(e.clientX, e.clientY);
    });
  };

  const handlePointerUp = (e) => {
    if (!dragState.current.isDragging) return;
    
    e.currentTarget.releasePointerCapture(e.pointerId);
    dragState.current.isDragging = false;
    
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    
    setTransition(true); // Enable transition for snapping back
    
    // Snap back to center
    applyLive(0, 0);
    lastVal.current = { x: 0, y: 0 };
    if (onChange) onChange(0, 0);
    if (onRelease) onRelease();
  };

  useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return (
    <div 
      ref={baseRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      className="relative rounded-full border-2 border-zinc-700 bg-zinc-800/50 shadow-inner flex items-center justify-center cursor-crosshair touch-none"
      style={{ width: size, height: size }}
    >
      {/* Target Crosshairs */}
      <div className="absolute w-full h-px bg-zinc-700/50 pointer-events-none" />
      <div className="absolute h-full w-px bg-zinc-700/50 pointer-events-none" />
      <div className="absolute w-1/2 h-1/2 rounded-full border border-zinc-700/30 pointer-events-none" />

      {/* Draggable Knob */}
      <div 
        ref={knobRef}
        className="absolute rounded-full bg-zinc-400 shadow-md shadow-black/50 border border-zinc-300 pointer-events-none"
        style={{ 
          width: size * 0.35, 
          height: size * 0.35,
          transition: "transform 0.15s ease-out"
        }}
      />
    </div>
  );
}
