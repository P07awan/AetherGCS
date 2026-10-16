import { commandsApi } from "@/services/api";
import { useGCS } from "@/store/gcsStore";

// Swarm mission planning helpers.
//
// Uploading one mission to several drones used to send identical absolute
// waypoints to each of them, so the whole swarm converged on the same points
// at the same altitude. Instead the plan is treated as the lead drone's path
// and every other drone flies the same shape shifted by its offset from the
// lead (formation preserved). Drones sitting on top of each other (< MIN_SEP_M)
// get an altitude stagger instead.

const M_PER_DEG_LAT = 111139;
export const MIN_SEP_M = 5;
export const ALT_STAGGER_M = 5;

const isValid = (lat, lon) =>
  Number.isFinite(lat) && Number.isFinite(lon) && (Math.abs(lat) > 1e-4 || Math.abs(lon) > 1e-4);

/** Best known position of a drone: live GPS, else its home. */
export function dronePosition(d) {
  const t = d?.telemetry || {};
  if (isValid(t.latitude, t.longitude)) return { lat: t.latitude, lon: t.longitude };
  if (isValid(d?.home_lat, d?.home_lon)) return { lat: d.home_lat, lon: d.home_lon };
  return null;
}

/**
 * @param {object[]} drones  target drones (first = lead unless leadId given)
 * @param {object[]} waypoints  the planned mission (lead drone's path)
 * @param {string} [leadId]
 * @returns {{droneId: string, waypoints: object[], offsetM: {north: number, east: number}, altOffset: number}[]}
 */
export function buildSwarmMissions(drones, waypoints, leadId) {
  const list = drones.filter(Boolean);
  if (list.length <= 1) {
    return list.map((d) => ({ droneId: d.id, waypoints, offsetM: { north: 0, east: 0 }, altOffset: 0 }));
  }
  const lead = list.find((d) => d.id === leadId) || list[0];
  const leadPos = dronePosition(lead);
  const placed = []; // {north, east} of drones already assigned, for separation checks
  let stagger = 0;

  return list.map((d) => {
    const pos = dronePosition(d);
    let north = 0;
    let east = 0;
    if (leadPos && pos) {
      north = (pos.lat - leadPos.lat) * M_PER_DEG_LAT;
      east = (pos.lon - leadPos.lon) * M_PER_DEG_LAT * Math.cos((leadPos.lat * Math.PI) / 180);
    }
    const crowded = placed.some((p) => Math.hypot(p.north - north, p.east - east) < MIN_SEP_M);
    const altOffset = crowded ? (stagger += ALT_STAGGER_M) : 0;
    placed.push({ north, east });

    const dLat = north / M_PER_DEG_LAT;
    const shifted = waypoints.map((w) => {
      const cosLat = Math.cos((w.latitude * Math.PI) / 180) || 1;
      return {
        ...w,
        latitude: Number((w.latitude + dLat).toFixed(7)),
        longitude: Number((w.longitude + east / (M_PER_DEG_LAT * cosLat)).toFixed(7)),
        altitude: Number(w.altitude) + altOffset,
      };
    });
    return { droneId: d.id, waypoints: shifted, offsetM: { north, east }, altOffset };
  });
}

/**
 * Upload `waypoints` to every drone in `ids`, preserving formation (see above).
 * Lead = the active drone if targeted, else the first id. Resolves to the
 * per-drone plans; rejects with a combined message if any upload fails.
 */
export async function uploadMissionToTargets(ids, waypoints) {
  const { drones, activeDroneId } = useGCS.getState();
  const leadId = ids.includes(activeDroneId) ? activeDroneId : ids[0];
  const plans = buildSwarmMissions(ids.map((id) => drones[id]).filter(Boolean), waypoints, leadId);
  const settled = await Promise.allSettled(
    plans.map((p) => commandsApi.send([p.droneId], "upload_mission", { waypoints: p.waypoints }))
  );
  const failed = settled
    .map((r, i) => ({ r, p: plans[i] }))
    .filter(({ r }) => r.status === "rejected");
  if (failed.length) {
    throw new Error(
      `${failed.length}/${plans.length} upload(s) failed: ` +
        failed
          .map(({ r, p }) => `${drones[p.droneId]?.name || p.droneId}: ${r.reason?.response?.data?.detail || r.reason?.message}`)
          .join("; ")
    );
  }
  return { plans, lead: drones[leadId] };
}
