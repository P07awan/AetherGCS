import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "aether-gcs-layout";

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function loadLayout() {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    return data ? JSON.parse(data) : {};
  } catch (e) {
    return {};
  }
}

function saveLayout(newLayout) {
  try {
    const data = loadLayout();
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...data, ...newLayout }));
  } catch (e) {
    // Ignore
  }
}

export function useResizable({ id, initialSize, minSize, maxSize, direction, invert = false }) {
  const [size, setSize] = useState(() => {
    const saved = loadLayout()[id];
    return saved != null ? clamp(saved, minSize, maxSize) : initialSize;
  });

  const ref = useRef(null);
  const dragState = useRef({ isDragging: false, startSize: 0, startPos: 0 });
  const rafRef = useRef(null);

  const applyLive = useCallback((newSize) => {
    if (ref.current) {
      if (direction === "vertical") {
        ref.current.style.width = `${newSize}px`;
        ref.current.style.minWidth = `${newSize}px`;
        ref.current.style.maxWidth = `${newSize}px`;
      } else {
        ref.current.style.height = `${newSize}px`;
        ref.current.style.minHeight = `${newSize}px`;
        ref.current.style.maxHeight = `${newSize}px`;
      }
    }
  }, [direction]);

  const onPointerDown = useCallback((e) => {
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    dragState.current = {
      isDragging: true,
      startSize: size,
      startPos: direction === "vertical" ? e.clientX : e.clientY,
    };
    document.body.style.cursor = direction === "vertical" ? "col-resize" : "row-resize";
    document.body.style.userSelect = "none"; // Prevent text selection
  }, [direction, size]);

  const onPointerMove = useCallback((e) => {
    if (!dragState.current.isDragging) return;

    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    
    rafRef.current = requestAnimationFrame(() => {
      const state = dragState.current;
      const currentPos = direction === "vertical" ? e.clientX : e.clientY;
      const delta = currentPos - state.startPos;
      
      const newSize = clamp(state.startSize + (invert ? -delta : delta), minSize, maxSize);
      
      applyLive(newSize);
    });
  }, [direction, invert, maxSize, minSize, applyLive]);

  const onPointerUp = useCallback((e) => {
    if (!dragState.current.isDragging) return;
    
    e.currentTarget.releasePointerCapture(e.pointerId);
    dragState.current.isDragging = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    
    const currentPos = direction === "vertical" ? e.clientX : e.clientY;
    const delta = currentPos - dragState.current.startPos;
    const finalSize = clamp(dragState.current.startSize + (invert ? -delta : delta), minSize, maxSize);
    
    setSize(finalSize);
    saveLayout({ [id]: finalSize });
  }, [direction, id, invert, maxSize, minSize]);

  const onDoubleClick = useCallback(() => {
    setSize(initialSize);
    saveLayout({ [id]: initialSize });
  }, [id, initialSize]);

  // Ensure DOM is in sync with state after a re-render or reset
  useEffect(() => {
    applyLive(size);
  }, [size, applyLive]);

  return {
    ref,
    size,
    handleProps: {
      onPointerDown,
      onPointerMove,
      onPointerUp,
      onPointerCancel: onPointerUp,
      onDoubleClick,
    }
  };
}
