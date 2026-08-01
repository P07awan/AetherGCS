import { useGCS } from "@/store/gcsStore";
import { Terminal, XCircle } from "lucide-react";
import { commandsApi } from "@/services/api";
import { toast } from "sonner";

const StatusPill = ({ status }) => {
  const map = {
    success: "text-[#00FF41] border-[#00FF41]/40",
    sent: "text-[#00F0FF] border-[#00F0FF]/40",
    failed: "text-[#FF003C] border-[#FF003C]/40",
    timeout: "text-[#FF5500] border-[#FF5500]/40",
    ack: "text-[#FFB000] border-[#FFB000]/40",
  };
  return (
    <span
      className={`text-[9px] font-mono px-1.5 py-0.5 border rounded-none uppercase ${
        map[status] || "text-zinc-400 border-zinc-700"
      }`}
    >
      {status}
    </span>
  );
};

export default function CommandHistory() {
  const history = useGCS((s) => s.commandHistory);
  const setHistory = useGCS((s) => s.setCommandHistory);

  const clear = async () => {
    await commandsApi.clearHistory();
    setHistory([]);
    toast.message("Command history cleared");
  };

  return (
    <div data-testid="command-history" className="h-full flex flex-col bg-zinc-950">
      <div className="h-10 px-3 border-b border-zinc-700 bg-zinc-900 flex items-center gap-2">
        <Terminal className="w-3.5 h-3.5 text-[#00F0FF]" />
        <span className="font-display font-black text-[11px] tracking-widest text-zinc-100">
          COMMAND LOG // {history.length}
        </span>
        <div className="flex-1" />
        <button
          data-testid="btn-clear-history"
          onClick={clear}
          className="text-[10px] font-mono uppercase text-zinc-500 hover:text-[#FF003C] flex items-center gap-1"
        >
          <XCircle className="w-3 h-3" /> Clear
        </button>
      </div>
      <div className="flex-1 overflow-y-auto font-mono text-[11px]">
        {history.length === 0 && (
          <div className="p-6 text-zinc-600 text-center text-xs">No commands issued yet.</div>
        )}
        {history.map((c) => (
          <div
            key={c.id}
            data-testid={`cmd-log-${c.id}`}
            className="grid grid-cols-[90px_1fr_100px_60px_70px] gap-2 px-3 py-1 border-b border-zinc-800 hover:bg-zinc-900 items-center text-zinc-200"
          >
            <span className="text-zinc-400">
              {new Date(c.ts).toLocaleTimeString(undefined, { hour12: false })}
            </span>
            <span className="truncate">
              <span className="text-[#FFB000]">{c.command}</span>{" "}
              <span className="text-zinc-500">→</span>{" "}
              <span className="text-zinc-300">{c.drone_name || c.drone_id.slice(0, 6)}</span>
            </span>
            <span className="text-zinc-400 truncate" title={JSON.stringify(c.params)}>
              {Object.keys(c.params || {}).length
                ? JSON.stringify(c.params).slice(0, 24)
                : "—"}
            </span>
            <span className="text-zinc-400 text-right">
              {c.response_ms != null ? `${c.response_ms}ms` : "—"}
            </span>
            <span className="text-right"><StatusPill status={c.status} /></span>
          </div>
        ))}
      </div>
    </div>
  );
}
