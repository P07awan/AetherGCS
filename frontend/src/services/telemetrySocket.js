import { API } from "@/services/api";

/**
 * Real-time telemetry WebSocket handler with auto-reconnect.
 */
export function createTelemetrySocket({ onSnapshot, onDrone, onDroneRemoved, onCommand, onStatus }) {
  const wsUrl = API.replace(/^http/, "ws") + "/ws/telemetry";
  let ws = null;
  let closed = false;
  let reconnectDelay = 1000;
  let heartbeatInterval = null;

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
      reconnectDelay = 1000;
      onStatus && onStatus("open");
      heartbeatInterval = setInterval(() => {
        try {
          ws?.send("ping");
        } catch {}
      }, 15000);
    };

    ws.onmessage = (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch { return; }
      switch (msg.event) {
        case "snapshot": onSnapshot && onSnapshot(msg.data); break;
        case "drone": onDrone && onDrone(msg.data); break;
        case "drone_removed": onDroneRemoved && onDroneRemoved(msg.data); break;
        case "command": onCommand && onCommand(msg.data); break;
        default: break;
      }
    };

    ws.onerror = () => { /* handled by onclose */ };

    ws.onclose = () => {
      onStatus && onStatus("closed");
      if (heartbeatInterval) clearInterval(heartbeatInterval);
      heartbeatInterval = null;
      scheduleReconnect();
    };
  };

  const scheduleReconnect = () => {
    if (closed) return;
    setTimeout(connect, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 1.5, 10000);
  };

  connect();

  return {
    close: () => {
      closed = true;
      if (heartbeatInterval) clearInterval(heartbeatInterval);
      try { ws?.close(); } catch {}
    },
  };
}
