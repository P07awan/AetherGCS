import { useEffect } from "react";
import ReactDOM from "react-dom";
import { X } from "lucide-react";

/**
 * Simple, animation-free centered modal, portaled to document.body
 * to escape any ancestor `overflow: hidden`.
 */
export default function GcsModal({ open, onOpenChange, title, subtitle, accent = "#FFB000", testid, children, footer }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") onOpenChange(false); };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onOpenChange]);

  if (!open) return null;

  const modal = (
    <div
      className="fixed inset-0 z-[9999] flex items-start justify-center pt-10 pb-6 px-4"
      style={{ background: "rgba(0,0,0,0.72)" }}
      onClick={() => onOpenChange(false)}
    >
      <div
        data-testid={testid}
        onClick={(e) => e.stopPropagation()}
        style={{
          backgroundColor: "#1c1c22",
          borderColor: accent,
          boxShadow: `0 0 0 1px ${accent}55, 0 24px 60px rgba(0,0,0,0.85)`,
        }}
        className="relative border-2 rounded-sm w-full max-w-2xl max-h-[calc(100vh-80px)] overflow-y-auto text-zinc-100"
      >
        <button
          onClick={() => onOpenChange(false)}
          className="absolute right-3 top-3 text-zinc-400 hover:text-zinc-100 z-10"
          aria-label="Close"
        >
          <X className="w-4 h-4" />
        </button>
        <div className="px-5 pt-4 pb-3 border-b" style={{ borderColor: `${accent}33` }}>
          <div className="font-display font-black tracking-wider text-zinc-50 text-lg">{title}</div>
          {subtitle && (
            <div className="text-zinc-400 text-xs font-mono mt-0.5">{subtitle}</div>
          )}
        </div>
        <div className="p-5">{children}</div>
        {footer && (
          <div className="px-5 py-3 border-t flex justify-end gap-2 bg-zinc-900/60"
               style={{ borderColor: `${accent}33` }}>
            {footer}
          </div>
        )}
      </div>
    </div>
  );

  return ReactDOM.createPortal(modal, document.body);
}

