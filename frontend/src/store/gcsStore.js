import { create } from "zustand";
import { useShallow } from "zustand/react/shallow";

/**
 * Central GCS state store.
 * - drones:            id -> drone
 * - selectedDroneIds:  Set of currently-selected drones
 * - activeDroneId:     drone whose telemetry is displayed on right panel
 * - wsStatus:          websocket status
 * - commandHistory:    latest command log entries (append-front)
 * - draftWaypoints:    waypoints being edited in the mission planner
 */
export const useGCS = create((set, get) => ({
  drones: {},
  selectedDroneIds: [],
  activeDroneId: null,
  wsStatus: "connecting",
  commandHistory: [],
  draftMission: { name: "New Mission", default_altitude: 20, default_speed: 5, waypoints: [] },
  missions: [],

  setSnapshot: (list) => {
    const map = {};
    list.forEach((d) => (map[d.id] = d));
    set({
      drones: map,
      activeDroneId: get().activeDroneId || (list[0]?.id ?? null),
    });
  },

  upsertDrone: (d) =>
    set((s) => ({
      drones: { ...s.drones, [d.id]: d },
      activeDroneId: s.activeDroneId || d.id,
    })),

  removeDrone: (id) =>
    set((s) => {
      const { [id]: _, ...rest } = s.drones;
      return {
        drones: rest,
        selectedDroneIds: s.selectedDroneIds.filter((x) => x !== id),
        activeDroneId: s.activeDroneId === id ? Object.keys(rest)[0] || null : s.activeDroneId,
      };
    }),

  setSelected: (ids) => set({ selectedDroneIds: ids }),
  toggleSelected: (id) =>
    set((s) => {
      const has = s.selectedDroneIds.includes(id);
      return {
        selectedDroneIds: has
          ? s.selectedDroneIds.filter((x) => x !== id)
          : [...s.selectedDroneIds, id],
      };
    }),
  selectAll: () => set((s) => ({ selectedDroneIds: Object.keys(s.drones) })),
  deselectAll: () => set({ selectedDroneIds: [] }),
  setActive: (id) => set({ activeDroneId: id }),

  setWsStatus: (s) => set({ wsStatus: s }),

  addCommandLog: (log) =>
    set((s) => ({ commandHistory: [log, ...s.commandHistory].slice(0, 300) })),
  setCommandHistory: (list) => set({ commandHistory: list }),

  setDraftMission: (m) => set({ draftMission: m }),
  addWaypoint: (wp) =>
    set((s) => ({
      draftMission: {
        ...s.draftMission,
        waypoints: [...s.draftMission.waypoints, { ...wp, seq: s.draftMission.waypoints.length }],
      },
    })),
  updateWaypoint: (seq, patch) =>
    set((s) => ({
      draftMission: {
        ...s.draftMission,
        waypoints: s.draftMission.waypoints.map((w) => (w.seq === seq ? { ...w, ...patch } : w)),
      },
    })),
  removeWaypoint: (seq) =>
    set((s) => ({
      draftMission: {
        ...s.draftMission,
        waypoints: s.draftMission.waypoints
          .filter((w) => w.seq !== seq)
          .map((w, i) => ({ ...w, seq: i })),
      },
    })),
  clearWaypoints: () =>
    set((s) => ({ draftMission: { ...s.draftMission, waypoints: [] } })),
  reorderWaypoints: (list) =>
    set((s) => ({
      draftMission: { ...s.draftMission, waypoints: list.map((w, i) => ({ ...w, seq: i })) },
    })),

  setMissions: (list) => set({ missions: list }),

  userLocation: null,   // {lat, lon, accuracy} from browser geolocation
  setUserLocation: (loc) => set({ userLocation: loc }),
}));

// Selectors — arrays wrapped in useShallow to prevent infinite re-renders
export const useDroneList = () =>
  useGCS(useShallow((s) => Object.values(s.drones)));
export const useSelectedDrones = () =>
  useGCS(useShallow((s) => s.selectedDroneIds.map((id) => s.drones[id]).filter(Boolean)));
export const useActiveDrone = () =>
  useGCS((s) => (s.activeDroneId ? s.drones[s.activeDroneId] : null));
