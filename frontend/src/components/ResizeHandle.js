import React from "react";

export function ResizeHandle({ direction, ...props }) {
  const isVertical = direction === "vertical";

  return (
    <div
      {...props}
      className={`
        flex-shrink-0 bg-zinc-800 z-50 flex items-center justify-center
        transition-colors hover:bg-[#FFB000] active:bg-[#FFB000]
        ${isVertical ? "w-1 cursor-col-resize hover:w-1.5" : "h-1 cursor-row-resize hover:h-1.5"}
      `}
    />
  );
}
