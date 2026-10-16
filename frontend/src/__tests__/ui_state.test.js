import { linkState, escapeHtml } from "../utils/format";

describe("linkState", () => {
  const d = (status, extra = {}) => ({ status, last_error: null, telemetry: { heartbeat: true }, ...extra });

  test("live only when connected with heartbeat", () => {
    expect(linkState(d("connected"))).toMatchObject({ ok: true, label: "LIVE" });
    expect(linkState(d("connected", { telemetry: { heartbeat: false } }))).toMatchObject({ ok: false, label: "LINK LOST" });
  });

  test("watchdog link loss vs other errors", () => {
    expect(linkState(d("error", { last_error: "Link lost: no heartbeat for 3s" }))).toMatchObject({ ok: false, label: "LINK LOST", tone: "bad" });
    expect(linkState(d("error", { last_error: "Port COM3 is locked" }))).toMatchObject({ ok: false, label: "ERROR" });
  });

  test("connecting vs reconnecting vs offline vs no drone", () => {
    expect(linkState(d("connecting")).label).toBe("CONNECTING");
    expect(linkState(d("connecting", { last_error: "No heartbeat" })).label).toBe("RECONNECTING");
    expect(linkState(d("disconnected"))).toMatchObject({ ok: false, label: "OFFLINE", tone: "off" });
    expect(linkState(null)).toMatchObject({ ok: false, label: "NO DRONE" });
  });
});

test("escapeHtml neutralises markup in drone names", () => {
  expect(escapeHtml(`<img src=x onerror="alert(1)">&'`)).toBe("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;&amp;&#39;");
  expect(escapeHtml(null)).toBe("");
});
