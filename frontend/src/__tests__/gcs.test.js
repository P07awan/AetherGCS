import { useGCS } from "../store/gcsStore";
import { API, dronesApi, commandsApi, missionsApi } from "../services/api";
import { fmt, fmtLat, fmtLon, fmtDuration, statusDot } from "../utils/format";
import { createTelemetrySocket } from "../services/telemetrySocket";

describe("AetherGCS Frontend Unit Tests", () => {
  beforeEach(() => {
    // Reset Zustand store state before each test
    useGCS.setState({
      drones: {},
      selectedDroneIds: [],
      activeDroneId: null,
      wsStatus: "closed",
      commandHistory: [],
      draftMissions: {},
      draftMission: { name: "New Mission", default_altitude: 20, default_speed: 5, waypoints: [] },
      missions: [],
      levelCardOpen: true,
      userLocation: null,
    });
  });

  describe("API Service Configuration", () => {
    test("API base URL is correctly resolved", () => {
      expect(API).toBeDefined();
      expect(API.endsWith("/api")).toBe(true);
    });

    test("API modules expose required endpoints", () => {
      expect(typeof dronesApi.list).toBe("function");
      expect(typeof dronesApi.create).toBe("function");
      expect(typeof dronesApi.remove).toBe("function");
      expect(typeof dronesApi.connect).toBe("function");
      expect(typeof dronesApi.disconnect).toBe("function");
      expect(typeof dronesApi.getSerialPorts).toBe("function");

      expect(typeof commandsApi.send).toBe("function");
      expect(typeof commandsApi.history).toBe("function");
      expect(typeof commandsApi.clearHistory).toBe("function");

      expect(typeof missionsApi.list).toBe("function");
      expect(typeof missionsApi.create).toBe("function");
      expect(typeof missionsApi.get).toBe("function");
      expect(typeof missionsApi.update).toBe("function");
      expect(typeof missionsApi.remove).toBe("function");
      expect(typeof missionsApi.duplicate).toBe("function");
    });
  });

  describe("Zustand Store - State Management & Resilience", () => {
    test("setSnapshot populates drone map and sets activeDroneId", () => {
      const droneA = {
        id: "drone-1",
        name: "Drone Alpha",
        status: "disconnected",
        home_lat: 37.77,
        home_lon: -122.41,
        telemetry: { armed: false, flight_mode: "STABILIZE" },
      };
      const droneB = {
        id: "drone-2",
        name: "Drone Bravo",
        status: "connected",
        home_lat: 37.78,
        home_lon: -122.42,
        telemetry: { armed: true, flight_mode: "GUIDED" },
      };

      useGCS.getState().setSnapshot([droneA, droneB]);

      const state = useGCS.getState();
      expect(Object.keys(state.drones).length).toBe(2);
      expect(state.drones["drone-1"].name).toBe("Drone Alpha");
      expect(state.activeDroneId).toBe("drone-1");
    });

    test("upsertDrone updates existing drone telemetry without losing selection", () => {
      const drone = {
        id: "drone-1",
        name: "Drone Alpha",
        status: "connected",
        home_lat: 37.77,
        home_lon: -122.41,
        telemetry: { armed: false, flight_mode: "STABILIZE" },
      };
      useGCS.getState().setSnapshot([drone]);
      useGCS.getState().setSelected(["drone-1"]);

      const updated = {
        ...drone,
        telemetry: { armed: true, flight_mode: "LOITER", altitude_relative: 15.2 },
      };
      useGCS.getState().upsertDrone(updated);

      const state = useGCS.getState();
      expect(state.drones["drone-1"].telemetry.armed).toBe(true);
      expect(state.drones["drone-1"].telemetry.flight_mode).toBe("LOITER");
      expect(state.selectedDroneIds).toEqual(["drone-1"]);
    });

    test("removeDrone clears drone and smoothly transitions activeDroneId", () => {
      const d1 = { id: "d1", name: "D1", status: "disconnected" };
      const d2 = { id: "d2", name: "D2", status: "connected" };
      useGCS.getState().setSnapshot([d1, d2]);
      useGCS.getState().setActive("d1");
      useGCS.getState().setSelected(["d1"]);

      useGCS.getState().removeDrone("d1");

      const state = useGCS.getState();
      expect(state.drones["d1"]).toBeUndefined();
      expect(state.drones["d2"]).toBeDefined();
      expect(state.activeDroneId).toBe("d2");
      expect(state.selectedDroneIds).toEqual([]);
    });

    test("waypoint CRUD operations maintain sequential seq indices", () => {
      useGCS.getState().addWaypoint({ latitude: 37.1, longitude: -122.1, altitude: 20 });
      useGCS.getState().addWaypoint({ latitude: 37.2, longitude: -122.2, altitude: 25 });
      useGCS.getState().addWaypoint({ latitude: 37.3, longitude: -122.3, altitude: 30 });

      let wps = useGCS.getState().draftMission.waypoints;
      expect(wps.length).toBe(3);
      expect(wps[0].seq).toBe(0);
      expect(wps[1].seq).toBe(1);
      expect(wps[2].seq).toBe(2);

      // Remove middle waypoint
      useGCS.getState().removeWaypoint(1);
      wps = useGCS.getState().draftMission.waypoints;
      expect(wps.length).toBe(2);
      expect(wps[0].seq).toBe(0);
      expect(wps[1].seq).toBe(1);
      expect(wps[1].latitude).toBe(37.3);

      // Clear
      useGCS.getState().clearWaypoints();
      expect(useGCS.getState().draftMission.waypoints.length).toBe(0);
    });

    test("handles empty or malformed snapshot without throwing", () => {
      expect(() => useGCS.getState().setSnapshot([])).not.toThrow();
      expect(useGCS.getState().drones).toEqual({});
      expect(useGCS.getState().activeDroneId).toBeNull();

      expect(() => useGCS.getState().setSnapshot(null)).not.toThrow();
    });
  });

  describe("Formatting & Utility Functions", () => {
    test("fmt correctly handles numbers, null, and custom decimals", () => {
      expect(fmt(12.3456, 2)).toBe("12.35");
      expect(fmt(12.3456, 0)).toBe("12");
      expect(fmt(null)).toBe("--");
      expect(fmt(undefined)).toBe("--");
      expect(fmt(NaN)).toBe("--");
    });

    test("fmtLat and fmtLon handle coordinate formatting", () => {
      expect(fmtLat(37.7749)).toBe("37.774900°");
      expect(fmtLat(-37.7749)).toBe("-37.774900°");
      expect(fmtLat(null)).toBe("--");
      expect(fmtLat(NaN)).toBe("--");

      expect(fmtLon(122.4194)).toBe("122.419400°");
      expect(fmtLon(-122.4194)).toBe("-122.419400°");
      expect(fmtLon(null)).toBe("--");
      expect(fmtLon(NaN)).toBe("--");
    });

    test("fmtDuration formats seconds into mm:ss and hh:mm:ss", () => {
      expect(fmtDuration(0)).toBe("00:00");
      expect(fmtDuration(65)).toBe("01:05");
      expect(fmtDuration(3665)).toBe("1:01:05");
      expect(fmtDuration(null)).toBe("--:--");
    });

    test("statusDot returns correct styling classes", () => {
      expect(statusDot({ status: "connected", telemetry: { armed: true } })).toContain("bg-[#0088FF]");
      expect(statusDot({ status: "connected", telemetry: { armed: false } })).toContain("bg-[#00FF41]");
      expect(statusDot({ status: "connecting" })).toContain("bg-[#FFB000]");
      expect(statusDot({ status: "disconnected" })).toContain("bg-[#FF003C]");
      expect(statusDot(null)).toContain("bg-zinc-600");
    });

    test("statusDot treats unknown (null) battery as not low", () => {
      expect(statusDot({ status: "connected", telemetry: { armed: true, battery_percent: null } })).toContain("bg-[#0088FF]");
      expect(statusDot({ status: "connected", telemetry: { armed: false, battery_percent: 10 } })).toContain("bg-[#FF5500]");
    });
  });

  describe("Store regressions", () => {
    test("setSnapshot drops selections of drones that no longer exist", () => {
      useGCS.setState({ selectedDroneIds: ["a", "gone"] });
      useGCS.getState().setSnapshot([{ id: "a", name: "A", telemetry: {} }]);
      expect(useGCS.getState().selectedDroneIds).toEqual(["a"]);
    });

    test("first upserted drone becomes active and the visible draft follows it", () => {
      useGCS.getState().upsertDrone({ id: "d1", name: "D1", telemetry: {} });
      expect(useGCS.getState().activeDroneId).toBe("d1");
      useGCS.getState().addWaypoint({ latitude: 1, longitude: 2, altitude: 20, action: "waypoint", hold_seconds: 0 });
      expect(useGCS.getState().draftMission.waypoints).toHaveLength(1);
      expect(useGCS.getState().draftMissions.d1.waypoints).toHaveLength(1);
    });
  });

  describe("WebSocket Client Handler", () => {
    let originalWebSocket;
    let mockWsInstance;

    beforeEach(() => {
      originalWebSocket = global.WebSocket;
      mockWsInstance = {
        send: jest.fn(),
        close: jest.fn(),
        readyState: 1, // OPEN
      };
      global.WebSocket = jest.fn(() => mockWsInstance);
    });

    afterEach(() => {
      global.WebSocket = originalWebSocket;
    });

    test("createTelemetrySocket instantiates WebSocket and dispatches snapshot", () => {
      const onSnapshot = jest.fn();
      const onStatus = jest.fn();

      const socket = createTelemetrySocket({
        onSnapshot,
        onStatus,
      });

      expect(global.WebSocket).toHaveBeenCalled();
      expect(onStatus).toHaveBeenCalledWith("connecting");

      // Simulate onopen
      mockWsInstance.onopen();
      expect(onStatus).toHaveBeenCalledWith("open");

      // Simulate snapshot message
      const snapshotPayload = {
        event: "snapshot",
        data: [{ id: "d1", name: "Alpha", status: "connected" }],
      };
      mockWsInstance.onmessage({ data: JSON.stringify(snapshotPayload) });
      expect(onSnapshot).toHaveBeenCalledWith(snapshotPayload.data);

      socket.close();
      expect(mockWsInstance.close).toHaveBeenCalled();
    });

    test("createTelemetrySocket cleanly closes and handles disconnects", () => {
      const onStatus = jest.fn();
      const socket = createTelemetrySocket({ onStatus });

      mockWsInstance.onopen();
      mockWsInstance.onclose();
      expect(onStatus).toHaveBeenCalledWith("closed");

      socket.close();
    });
  });
});
