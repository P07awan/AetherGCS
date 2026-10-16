import { create } from "zustand";
import { useShallow } from "zustand/react/shallow";

const DEFAULT_MISSION = { name: "New Mission", default_altitude: 20, default_speed: 5, waypoints: [] };

const _getTargetKey = (s) => {
  if (s.selectedDroneIds && s.selectedDroneIds.length > 1) return "swarm";
  if (s.selectedDroneIds && s.selectedDroneIds.length === 1) return s.selectedDroneIds[0];
  return s.activeDroneId || "default";
};

const _syncDraft = (s, updatedMissions = null) => {
  const missions = updatedMissions || s.draftMissions || {};
  const key = _getTargetKey(s);
  const current = missions[key] || { ...DEFAULT_MISSION };
  return {
    draftMissions: missions,
    draftMission: current,
  };
};

const MAX_TRAIL = 500;

/**
 * Live "drone" events carry only `trail_tail` (newest points) instead of the
 * whole trail; append the points we don't have yet to the trail we already
 * hold (full trail comes with the snapshot).
 */
export const mergeTrail = (prev, incoming) => {
  if (!incoming || !("trail_tail" in incoming)) return incoming;
  const { trail_tail: tail = [], ...rest } = incoming;
  const old = prev?.trail || [];
  let trail;
  if (!old.length) {
    trail = tail.slice();
  } else {
    const last = old[old.length - 1];
    let idx = -1;
    for (let i = tail.length - 1; i >= 0; i--) {
      if (tail[i][0] === last[0] && tail[i][1] === last[1]) { idx = i; break; }
    }
    const fresh = tail.slice(idx + 1);
    trail = fresh.length ? old.concat(fresh) : old; // keep the same array when nothing changed
  }
  if (trail.length > MAX_TRAIL) trail = trail.slice(-MAX_TRAIL);
  return { ...rest, trail };
};

/**
 * Central GCS state store with per-drone draft mission isolation.
 */
export const useGCS = create((set, get) => ({
  drones: {},
  selectedDroneIds: [],
  activeDroneId: null,
  wsStatus: "connecting",
  commandHistory: [],

  // Per-drone mission isolation
  draftMissions: {},
  draftMission: { ...DEFAULT_MISSION },

  missions: [],
  levelCardOpen: true,
  toggleLevelCard: () => set((s) => ({ levelCardOpen: !s.levelCardOpen })),

  setSnapshot: (list) => {
    const safeList = Array.isArray(list) ? list : [];
    const map = {};
    safeList.forEach((d) => {
      if (d && d.id) map[d.id] = d;
    });
    const currentActive = get().activeDroneId;
    const nextActive = (currentActive && map[currentActive]) ? currentActive : (safeList[0]?.id ?? null);
    set((s) => {
      // Drop selections of drones that disappeared (e.g. deleted while the WS was down).
      const selectedDroneIds = (s.selectedDroneIds || []).filter((id) => map[id]);
      const next = { ...s, drones: map, activeDroneId: nextActive, selectedDroneIds };
      return { ...next, ..._syncDraft(next) };
    });
  },

  upsertDrone: (d) => {
    if (!d || !d.id) return;
    set((s) => {
      const drones = { ...s.drones, [d.id]: mergeTrail(s.drones[d.id], d) };
      if (s.activeDroneId) return { drones };
      // First drone becomes active: switch the visible draft to its key too,
      // otherwise edits go to the drone's draft while the old one is displayed.
      const next = { ...s, drones, activeDroneId: d.id };
      return { drones, activeDroneId: d.id, ..._syncDraft(next) };
    });
  },

  removeDrone: (id) =>
    set((s) => {
      const { [id]: _, ...rest } = s.drones || {};
      const { [id]: __, ...restMissions } = s.draftMissions || {};
      const nextActive = s.activeDroneId === id ? Object.keys(rest)[0] || null : s.activeDroneId;
      const nextSelected = (s.selectedDroneIds || []).filter((x) => x !== id);
      const next = { ...s, drones: rest, selectedDroneIds: nextSelected, activeDroneId: nextActive };
      return { ...next, ..._syncDraft(next, restMissions) };
    }),

  setSelected: (ids) =>
    set((s) => {
      const next = { ...s, selectedDroneIds: ids };
      return { ...next, ..._syncDraft(next) };
    }),

  toggleSelected: (id) =>
    set((s) => {
      const has = s.selectedDroneIds.includes(id);
      const nextIds = has
        ? s.selectedDroneIds.filter((x) => x !== id)
        : [...s.selectedDroneIds, id];
      const next = { ...s, selectedDroneIds: nextIds };
      return { ...next, ..._syncDraft(next) };
    }),

  selectAll: () =>
    set((s) => {
      const next = { ...s, selectedDroneIds: Object.keys(s.drones) };
      return { ...next, ..._syncDraft(next) };
    }),

  deselectAll: () =>
    set((s) => {
      const next = { ...s, selectedDroneIds: [] };
      return { ...next, ..._syncDraft(next) };
    }),

  setActive: (id) =>
    set((s) => {
      const next = { ...s, activeDroneId: id };
      return { ...next, ..._syncDraft(next) };
    }),

  setWsStatus: (s) => set({ wsStatus: s }),

  addCommandLog: (log) =>
    set((s) => ({ commandHistory: [log, ...s.commandHistory].slice(0, 300) })),
  setCommandHistory: (list) => set({ commandHistory: list }),

  setDraftMission: (m) =>
    set((s) => {
      const key = _getTargetKey(s);
      const updatedMissions = { ...s.draftMissions, [key]: m };
      return _syncDraft(s, updatedMissions);
    }),

  addWaypoint: (wp) =>
    set((s) => {
      const key = _getTargetKey(s);
      const current = s.draftMissions[key] || s.draftMission || { ...DEFAULT_MISSION };
      const nextWps = [...current.waypoints, { ...wp, seq: current.waypoints.length }];
      const updatedMission = { ...current, waypoints: nextWps };
      const updatedMissions = { ...s.draftMissions, [key]: updatedMission };
      return _syncDraft(s, updatedMissions);
    }),

  updateWaypoint: (seq, patch) =>
    set((s) => {
      const key = _getTargetKey(s);
      const current = s.draftMissions[key] || s.draftMission || { ...DEFAULT_MISSION };
      const nextWps = current.waypoints.map((w) => (w.seq === seq ? { ...w, ...patch } : w));
      const updatedMission = { ...current, waypoints: nextWps };
      const updatedMissions = { ...s.draftMissions, [key]: updatedMission };
      return _syncDraft(s, updatedMissions);
    }),

  removeWaypoint: (seq) =>
    set((s) => {
      const key = _getTargetKey(s);
      const current = s.draftMissions[key] || s.draftMission || { ...DEFAULT_MISSION };
      const nextWps = current.waypoints.filter((w) => w.seq !== seq).map((w, i) => ({ ...w, seq: i }));
      const updatedMission = { ...current, waypoints: nextWps };
      const updatedMissions = { ...s.draftMissions, [key]: updatedMission };
      return _syncDraft(s, updatedMissions);
    }),

  clearWaypoints: () =>
    set((s) => {
      const key = _getTargetKey(s);
      const current = s.draftMissions[key] || s.draftMission || { ...DEFAULT_MISSION };
      const updatedMission = { ...current, waypoints: [] };
      const updatedMissions = { ...s.draftMissions, [key]: updatedMission };
      return _syncDraft(s, updatedMissions);
    }),

  setDraftWaypoints: (list) =>
    set((s) => {
      const key = _getTargetKey(s);
      const current = s.draftMissions[key] || s.draftMission || { ...DEFAULT_MISSION };
      const updatedMission = { ...current, waypoints: list };
      const updatedMissions = { ...s.draftMissions, [key]: updatedMission };
      return _syncDraft(s, updatedMissions);
    }),

  reorderWaypoints: (list) =>
    set((s) => {
      const key = _getTargetKey(s);
      const current = s.draftMissions[key] || s.draftMission || { ...DEFAULT_MISSION };
      const updatedMission = { ...current, waypoints: list.map((w, i) => ({ ...w, seq: i })) };
      const updatedMissions = { ...s.draftMissions, [key]: updatedMission };
      return _syncDraft(s, updatedMissions);
    }),

  setMissions: (list) => set({ missions: list }),

  userLocation: null,
  setUserLocation: (loc) => set({ userLocation: loc }),
}));

// Selectors
export const useDroneList = () =>
  useGCS(useShallow((s) => Object.values(s.drones)));
export const useSelectedDrones = () =>
  useGCS(useShallow((s) => s.selectedDroneIds.map((id) => s.drones[id]).filter(Boolean)));
export const useActiveDrone = () =>
  useGCS((s) => (s.activeDroneId ? s.drones[s.activeDroneId] : null));
