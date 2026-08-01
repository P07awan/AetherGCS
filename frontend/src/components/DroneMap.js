import { useEffect, useMemo, useRef } from "react";
import L from "leaflet";
import {
  MapContainer, TileLayer, Marker, Polyline, useMap, useMapEvents,
} from "react-leaflet";
import { useGCS, useDroneList, useActiveDrone } from "@/store/gcsStore";
import { Crosshair } from "lucide-react";
import { renderToStaticMarkup } from "react-dom/server";

// Custom drone icon with heading rotation
const droneIcon = (heading, selected) =>
  L.divIcon({
    className: "",
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    html: `<div class="drone-marker ${selected ? "selected" : ""}" style="transform: rotate(${heading}deg)">
      ${renderToStaticMarkup(
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
          <path
            d="M12 2 L15 12 L12 10 L9 12 Z"
            fill={selected ? "#FFB000" : "#00F0FF"}
            stroke="#000"
            strokeWidth="1"
          />
          <circle cx="12" cy="14" r="2" fill={selected ? "#FFB000" : "#00F0FF"} stroke="#000" strokeWidth="0.5" />
        </svg>
      )}
    </div>`,
  });

const homeIcon = L.divIcon({
  className: "",
  iconSize: [22, 22],
  iconAnchor: [11, 11],
  html: `<div class="home-marker"></div>`,
});

const waypointIcon = (seq) =>
  L.divIcon({
    className: "",
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    html: `<div class="waypoint-marker">${seq + 1}</div>`,
  });

function MapClickHandler({ onClick }) {
  useMapEvents({ click(e) { onClick && onClick(e); } });
  return null;
}

function FitBounds({ drones }) {
  const map = useMap();
  useEffect(() => {
    if (!drones.length) return;
    const bounds = L.latLngBounds(
      drones.map((d) => [d.telemetry.latitude, d.telemetry.longitude])
    );
    map.fitBounds(bounds.pad(0.2), { animate: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return null;
}

export default function DroneMap() {
  const drones = useDroneList();
  const activeDrone = useActiveDrone();
  const activeId = useGCS((s) => s.activeDroneId);
  const setActive = useGCS((s) => s.setActive);
  const draftWaypoints = useGCS((s) => s.draftMission.waypoints);
  const draftAlt = useGCS((s) => s.draftMission.default_altitude);
  const addWaypoint = useGCS((s) => s.addWaypoint);
  const updateWaypoint = useGCS((s) => s.updateWaypoint);
  const mapRef = useRef(null);

  const center = useMemo(() => {
    if (activeDrone) return [activeDrone.telemetry.latitude, activeDrone.telemetry.longitude];
    if (drones[0]) return [drones[0].telemetry.latitude, drones[0].telemetry.longitude];
    return [37.7749, -122.4194];
  }, [activeDrone, drones]);

  const handleMapClick = (e) => {
    addWaypoint({
      latitude: e.latlng.lat,
      longitude: e.latlng.lng,
      altitude: draftAlt,
      action: "waypoint",
      hold_seconds: 0,
    });
  };

  const centerActive = () => {
    if (!activeDrone || !mapRef.current) return;
    mapRef.current.flyTo(
      [activeDrone.telemetry.latitude, activeDrone.telemetry.longitude],
      Math.max(mapRef.current.getZoom(), 16)
    );
  };

  const fitAll = () => {
    if (!drones.length || !mapRef.current) return;
    const bounds = L.latLngBounds(
      drones.map((d) => [d.telemetry.latitude, d.telemetry.longitude])
    );
    mapRef.current.fitBounds(bounds.pad(0.3), { animate: true });
  };

  return (
    <div data-testid="map-container" className="flex-1 relative bg-[#0a0a0a]">
      <MapContainer
        center={center}
        zoom={17}
        className="w-full h-full"
        zoomControl={true}
        ref={mapRef}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        <MapClickHandler onClick={handleMapClick} />
        <FitBounds drones={drones} />

        {drones.map((d) => (
          <Marker
            key={`home-${d.id}`}
            position={[d.home_lat, d.home_lon]}
            icon={homeIcon}
            interactive={false}
          />
        ))}

        {drones.map((d) => (
          <Polyline
            key={`trail-${d.id}`}
            positions={d.trail || []}
            pathOptions={{
              color: d.id === activeId ? "#FFB000" : "#00F0FF",
              weight: 2,
              opacity: 0.75,
              dashArray: d.id === activeId ? undefined : "4 4",
            }}
          />
        ))}

        {drones.map((d) => (
          <Marker
            key={d.id}
            position={[d.telemetry.latitude, d.telemetry.longitude]}
            icon={droneIcon(d.telemetry.heading, d.id === activeId)}
            eventHandlers={{ click: () => setActive(d.id) }}
          />
        ))}

        {draftWaypoints.length > 1 && (
          <Polyline
            positions={draftWaypoints.map((w) => [w.latitude, w.longitude])}
            pathOptions={{ color: "#FFB000", weight: 2, opacity: 0.9 }}
          />
        )}

        {draftWaypoints.map((wp) => (
          <Marker
            key={wp.seq}
            position={[wp.latitude, wp.longitude]}
            icon={waypointIcon(wp.seq)}
            draggable
            eventHandlers={{
              dragend: (e) => {
                const { lat, lng } = e.target.getLatLng();
                updateWaypoint(wp.seq, { latitude: lat, longitude: lng });
              },
            }}
          />
        ))}
      </MapContainer>

      {/* Map overlays */}
      <div className="absolute top-3 left-3 z-[500] bg-zinc-900/90 backdrop-blur border border-zinc-800 px-3 py-1.5">
        <div className="font-mono text-[10px] text-zinc-500">
          CLICK MAP TO ADD WAYPOINT ({draftWaypoints.length})
        </div>
      </div>

      <div className="absolute top-3 right-3 z-[500] flex gap-1">
        <button
          data-testid="btn-map-fit-all"
          onClick={fitAll}
          className="bg-zinc-900/90 backdrop-blur border border-zinc-800 text-zinc-200 hover:bg-zinc-800 h-8 px-3 text-[11px] font-mono uppercase"
        >
          Fit All
        </button>
        <button
          data-testid="btn-map-center-active"
          onClick={centerActive}
          className="bg-zinc-900/90 backdrop-blur border border-zinc-800 text-zinc-200 hover:bg-zinc-800 h-8 w-8 flex items-center justify-center"
        >
          <Crosshair className="w-4 h-4 text-[#FFB000]" />
        </button>
      </div>

      {activeDrone && (
        <div className="absolute bottom-3 left-3 z-[500] bg-zinc-900/90 backdrop-blur border border-zinc-800 px-3 py-2 font-mono text-[10px] leading-relaxed">
          <div className="text-[#FFB000] font-bold">{activeDrone.name}</div>
          <div className="text-zinc-400">
            {activeDrone.telemetry.latitude.toFixed(6)}, {activeDrone.telemetry.longitude.toFixed(6)}
          </div>
          <div className="text-zinc-500">
            ALT {activeDrone.telemetry.altitude_relative.toFixed(1)}m · HDG {activeDrone.telemetry.heading.toFixed(0)}° · GS {activeDrone.telemetry.ground_speed.toFixed(1)} m/s
          </div>
        </div>
      )}
    </div>
  );
}
