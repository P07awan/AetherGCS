import { API } from "./api";

/**
 * Real-time telemetry WebSocket handler with auto-reconnect.
 */
export function createTelemetrySocket({ onSnapshot, onDrone, onDroneRemoved, onCommand, onStatus }) {
  const getWsUrl = () => {
    const cleanApi = API.trim().replace(/\/+$/, "");
    if (cleanApi.startsWith("https://")) {
      return cleanApi.replace(/^https:\/\//, "wss://") + "/ws/telemetry";
    }
    if (cleanApi.startsWith("http://")) {
      return cleanApi.replace(/^http:\/\//, "ws://") + "/ws/telemetry";
    }
    const protocol = typeof window !== "undefined" && window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = typeof window !== "undefined" ? window.location.host : "localhost:8000";
    return `${protocol}//${host}${cleanApi.startsWith("/") ? cleanApi : `/${cleanApi}`}/ws/telemetry`;
  };
  const wsUrl = getWsUrl();
  let ws = null;
  let closed = false;
  let reconnectDelay = 1000;
  let heartbeatInterval = null;
  let reconnectTimer = null;
  let rafId = null;
  let flushTimer = null;

  const connect = () => {
    if (closed) return;
    try {
      ws = new WebSocket(wsUrl);
    } catch (e) {
      scheduleReconnect();
      return;
    }
    onStatus && onStatus("connecting");

    ws.onopen = () => {
      if (closed) {
        try { ws.close(); } catch {}
        return;
      }
      reconnectDelay = 1000;
      onStatus && onStatus("open");
      heartbeatInterval = setInterval(() => {
        try {
          if (ws?.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        } catch {}
      }, 15000);
    };

    let pendingDroneMap = {};
    let rafScheduled = false;

    const flushDrones = () => {
      if (!rafScheduled) return; // already flushed by the other trigger
      rafScheduled = false;
      if (rafId) cancelAnimationFrame(rafId);
      if (flushTimer) clearTimeout(flushTimer);
      rafId = null;
      flushTimer = null;
      if (closed) return;
      const dronesToUpdate = Object.values(pendingDroneMap);
      pendingDroneMap = {};
      dronesToUpdate.forEach((d) => onDrone && onDrone(d));
    };

    ws.onmessage = (ev) => {
      if (closed) return;
      let msg;
      try { msg = JSON.parse(ev.data); } catch { return; }
      switch (msg.event) {
        case "snapshot": onSnapshot && onSnapshot(msg.data); break;
        case "drone":
          if (msg.data && msg.data.id) {
            pendingDroneMap[msg.data.id] = msg.data;
            if (!rafScheduled) {
              rafScheduled = true;
              rafId = requestAnimationFrame(flushDrones);
              // rAF is paused while the tab is hidden/minimized/occluded; the
              // timer keeps the store live so telemetry doesn't freeze.
              flushTimer = setTimeout(flushDrones, 250);
            }
          }
          break;
        case "drone_removed":
          if (msg.data && msg.data.id) delete pendingDroneMap[msg.data.id];
          onDroneRemoved && onDroneRemoved(msg.data);
          break;
        case "command": onCommand && onCommand(msg.data); break;
        default: break;
      }
    };

    ws.onerror = () => { /* handled by onclose */ };

    ws.onclose = () => {
      if (heartbeatInterval) clearInterval(heartbeatInterval);
      heartbeatInterval = null;
      if (!closed) {
        onStatus && onStatus("closed");
        scheduleReconnect();
      }
    };
  };

  const scheduleReconnect = () => {
    if (closed) return;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 1.5, 10000);
  };

  connect();

  return {
    close: () => {
      closed = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
        heartbeatInterval = null;
      }
      if (rafId) {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
      if (flushTimer) {
        clearTimeout(flushTimer);
        flushTimer = null;
      }
      try { ws?.close(); } catch {}
    },
  };
}
