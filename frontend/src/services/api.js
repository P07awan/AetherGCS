import axios from "axios";

const BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || "").trim().replace(/\/+$/, "");
export const API = BACKEND_URL ? `${BACKEND_URL}/api` : "/api";

const client = axios.create({ baseURL: API, timeout: 60000 });

// FastAPI 422 responses carry `detail` as an array of objects; flatten it so
// every `e.response?.data?.detail` toast shows text instead of "[object Object]".
client.interceptors.response.use(undefined, (error) => {
  const detail = error.response?.data?.detail;
  if (Array.isArray(detail)) {
    error.response.data.detail = detail
      .map((d) => {
        const loc = Array.isArray(d?.loc) ? d.loc.slice(1).join(".") : "";
        return loc ? `${loc}: ${d?.msg}` : d?.msg || JSON.stringify(d);
      })
      .join("; ");
  }
  return Promise.reject(error);
});

// POST /commands only returns an HTTP error when EVERY target fails; a partial
// failure comes back as 200 with per-drone `ok: false`. Surface those as errors.
const checkCommandResults = (data) => {
  const results = Array.isArray(data?.results) ? data.results : [];
  if (results.length === 0) throw new Error("Target drone(s) not found");
  const failed = results.filter((r) => !r.ok);
  if (failed.length) {
    const err = new Error(
      `${failed.length}/${results.length} drone(s) failed: ` +
        failed.map((f) => `${f.name || f.drone_id}: ${f.error}`).join("; ")
    );
    err.results = results;
    throw err;
  }
  return data;
};

export const dronesApi = {
  list: () => client.get("/drones").then((r) => r.data),
  create: (payload) => client.post("/drones", payload).then((r) => r.data),
  remove: (id) => client.delete(`/drones/${id}`).then((r) => r.data),
  connect: (id) => client.post(`/drones/${id}/connect`).then((r) => r.data),
  disconnect: (id) => client.post(`/drones/${id}/disconnect`).then((r) => r.data),
  getSerialPorts: () => client.get("/system/serial-ports").then((r) => r.data),
};

export const commandsApi = {
  send: (drone_ids, command, params = {}) =>
    client.post("/commands", { drone_ids, command, params }).then((r) => checkCommandResults(r.data)),
  history: (limit = 200) => client.get(`/history?limit=${limit}`).then((r) => r.data),
  clearHistory: () => client.delete("/history").then((r) => r.data),
};

export const missionsApi = {
  list: () => client.get("/missions").then((r) => r.data),
  create: (payload) => client.post("/missions", payload).then((r) => r.data),
  get: (id) => client.get(`/missions/${id}`).then((r) => r.data),
  update: (id, payload) => client.put(`/missions/${id}`, payload).then((r) => r.data),
  remove: (id) => client.delete(`/missions/${id}`).then((r) => r.data),
  duplicate: (id) => client.post(`/missions/${id}/duplicate`).then((r) => r.data),
};
