import { buildSwarmMissions, MIN_SEP_M, ALT_STAGGER_M } from "../utils/swarm";

const drone = (id, lat, lon) => ({ id, telemetry: { latitude: lat, longitude: lon }, home_lat: lat, home_lon: lon });
const wps = [
  { seq: 0, latitude: 37.7760, longitude: -122.4180, altitude: 20, action: "waypoint" },
  { seq: 1, latitude: 37.7770, longitude: -122.4170, altitude: 25, action: "waypoint" },
];
const metersBetween = (a, b) => {
  const n = (a.latitude - b.latitude) * 111139;
  const e = (a.longitude - b.longitude) * 111139 * Math.cos((a.latitude * Math.PI) / 180);
  return Math.hypot(n, e);
};

describe("buildSwarmMissions", () => {
  test("single drone gets the plan unchanged", () => {
    const [p] = buildSwarmMissions([drone("a", 37.7749, -122.4194)], wps);
    expect(p.waypoints).toBe(wps);
  });

  test("swarm keeps formation instead of converging on the same points", () => {
    // three drones 20 m apart east-west
    const d20 = 20 / (111139 * Math.cos((37.7749 * Math.PI) / 180));
    const ds = [drone("a", 37.7749, -122.4194), drone("b", 37.7749, -122.4194 + d20), drone("c", 37.7749, -122.4194 + 2 * d20)];
    const plans = buildSwarmMissions(ds, wps, "a");
    expect(plans.map((p) => p.droneId)).toEqual(["a", "b", "c"]);
    expect(plans[0].waypoints[0]).toMatchObject({ latitude: 37.776, longitude: -122.418 }); // lead flies the plan
    for (let k = 0; k < wps.length; k++) {
      expect(metersBetween(plans[0].waypoints[k], plans[1].waypoints[k])).toBeCloseTo(20, 0);
      expect(metersBetween(plans[0].waypoints[k], plans[2].waypoints[k])).toBeCloseTo(40, 0);
    }
    expect(plans.every((p) => p.altOffset === 0)).toBe(true);
  });

  test("co-located drones are separated by altitude", () => {
    const ds = [drone("a", 37.7749, -122.4194), drone("b", 37.7749, -122.4194), drone("c", 37.77490001, -122.4194)];
    const plans = buildSwarmMissions(ds, wps, "a");
    expect(plans.map((p) => p.altOffset)).toEqual([0, ALT_STAGGER_M, 2 * ALT_STAGGER_M]);
    expect(plans[2].waypoints[1].altitude).toBe(25 + 2 * ALT_STAGGER_M);
    expect(MIN_SEP_M).toBeGreaterThan(0);
  });

  test("lead defaults to the first drone; missing drones are skipped", () => {
    const plans = buildSwarmMissions([drone("x", 37.7749, -122.4194), undefined], wps);
    expect(plans).toHaveLength(1);
    expect(plans[0].droneId).toBe("x");
  });
});

describe("mergeTrail (live updates carry only the newest trail points)", () => {
  const { mergeTrail } = require("../store/gcsStore");
  test("appends only unseen points and keeps other fields", () => {
    const prev = { id: "a", trail: [[1, 1], [2, 2], [3, 3]] };
    const out = mergeTrail(prev, { id: "a", status: "connected", trail_tail: [[2, 2], [3, 3], [4, 4], [5, 5]] });
    expect(out.trail).toEqual([[1, 1], [2, 2], [3, 3], [4, 4], [5, 5]]);
    expect(out.status).toBe("connected");
    expect("trail_tail" in out).toBe(false);
  });
  test("unchanged tail keeps the same trail array", () => {
    const prev = { id: "a", trail: [[1, 1], [2, 2]] };
    expect(mergeTrail(prev, { id: "a", trail_tail: [[1, 1], [2, 2]] }).trail).toBe(prev.trail);
  });
  test("first update starts the trail from the tail; full payloads pass through", () => {
    expect(mergeTrail(undefined, { id: "a", trail_tail: [[9, 9]] }).trail).toEqual([[9, 9]]);
    const full = { id: "a", trail: [[7, 7]] };
    expect(mergeTrail({ trail: [[1, 1]] }, full)).toBe(full);
  });
});
