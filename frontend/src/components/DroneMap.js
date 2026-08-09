import React, { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import { MapContainer, TileLayer, Marker, Polyline, Circle, useMap, useMapEvents } from "react-leaflet";
import { useGCS, useDroneList, useActiveDrone } from "@/store/gcsStore";
import { Crosshair, Navigation as NavIcon, Layers, Lock, Unlock } from "lucide-react";
import { renderToStaticMarkup } from "react-dom/server";

const MAP_PROVIDERS = {
  satellite: {
    name: "Google Satellite",
    url: "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    maxZoom: 20,
    subdomains: ["mt0", "mt1", "mt2", "mt3"],
  },
  hybrid: {
    name: "Google Hybrid",
    url: "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
    maxZoom: 20,
    subdomains: ["mt0", "mt1", "mt2", "mt3"],
  },
  dark: {
    name: "CartoDB Dark",
    url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    maxZoom: 19,
    subdomains: ["a", "b", "c", "d"],
  },
  osm: {
    name: "OpenStreetMap",
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    maxZoom: 19,
    subdomains: ["a", "b", "c"],
  },
};

// Quadcopter Drone Icon with rotors and directional heading
const quadcopterIcon = (heading, selected, armed) =>
  L.divIcon({
    className: "",
    iconSize: [36, 36],
    iconAnchor: [18, 18],
    html: `<div class="relative w-9 h-9 flex items-center justify-center transition-transform duration-75" style="transform: rotate(${heading}deg)">
      ${renderToStaticMarkup(
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
        {/* Quadcopter X Frame */}
        <line x1="6" y1="6" x2="26" y2="26" stroke={selected ? "#FFB000" : "#00F0FF"} strokeWidth="2.5" />
        <line x1="26" y1="6" x2="6" y2="26" stroke={selected ? "#FFB000" : "#00F0FF"} strokeWidth="2.5" />

        {/* 4 Rotors */}
        <circle cx="6" cy="6" r="3.5" fill={armed ? "#00FF41" : "#FF003C"} stroke="#000" strokeWidth="1" />
        <circle cx="26" cy="6" r="3.5" fill={armed ? "#00FF41" : "#FF003C"} stroke="#000" strokeWidth="1" />
        <circle cx="6" cy="26" r="3.5" fill={armed ? "#00FF41" : "#FF003C"} stroke="#000" strokeWidth="1" />
        <circle cx="26" cy="26" r="3.5" fill={armed ? "#00FF41" : "#FF003C"} stroke="#000" strokeWidth="1" />

        {/* Forward Nose Direction Arrow */}
        <path d="M16 2 L21 14 L16 11 L11 14 Z" fill={selected ? "#FFB000" : "#00F0FF"} stroke="#000" strokeWidth="1" />

        {/* Center Body Core */}
        <circle cx="16" cy="16" r="4.5" fill="#111" stroke={selected ? "#FFB000" : "#00F0FF"} strokeWidth="1.5" />
        <circle cx="16" cy="16" r="1.5" fill={selected ? "#FFB000" : "#00F0FF"} />
      </svg>
    )}
    </div>`,
  });

const homeIcon = L.divIcon({
  className: "",
  iconSize: [24, 24],
  iconAnchor: [12, 12],
  html: `<div class="w-6 h-6 rounded-full bg-[#FFB000] border-2 border-black flex items-center justify-center font-mono font-bold text-[10px] text-black shadow-md">H</div>`,
});

const userIcon = L.divIcon({
  className: "",
  iconSize: [24, 24],
  iconAnchor: [12, 12],
  html: `<div class="user-marker"><div class="user-marker-dot"></div></div>`,
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

const isValidCoord = (lat, lon) =>
  lat != null &&
  lon != null &&
  !isNaN(lat) &&
  !isNaN(lon) &&
  (Math.abs(lat) > 0.0001 || Math.abs(lon) > 0.0001);

function AutoPanHandler({ activeDrone, autoPan }) {
  const map = useMap();
  useEffect(() => {
    if (!autoPan || !activeDrone) return;
    const lat = activeDrone.telemetry?.latitude;
    const lon = activeDrone.telemetry?.longitude;
    const hLat = activeDrone.home_lat;
    const hLon = activeDrone.home_lon;

    if (isValidCoord(lat, lon)) {
      map.panTo([lat, lon], { animate: true, duration: 0.5 });
    } else if (isValidCoord(hLat, hLon)) {
      map.panTo([hLat, hLon], { animate: true, duration: 0.5 });
    }
  }, [
    activeDrone?.telemetry?.latitude,
    activeDrone?.telemetry?.longitude,
    activeDrone?.home_lat,
    activeDrone?.home_lon,
    autoPan,
    map,
    activeDrone,
  ]);
  return null;
}

function UserInteractionHandler({ onUserDrag }) {
  useMapEvents({
    dragstart() {
      onUserDrag && onUserDrag();
    },
  });
  return null;
}

function MapResizeInvalidator() {
  const map = useMap();
  useEffect(() => {
    const observer = new ResizeObserver(() => {
      map.invalidateSize();
    });
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);
  return null;
}

import MissionPlannerHUD from "@/components/MissionPlannerHUD";

export default function DroneMap() {
  const drones = useDroneList();
  const activeDrone = useActiveDrone();
  const activeId = useGCS((s) => s.activeDroneId);
  const setActive = useGCS((s) => s.setActive);
  const draftWaypoints = useGCS((s) => s.draftMission.waypoints);
  const draftAlt = useGCS((s) => s.draftMission.default_altitude);
  const addWaypoint = useGCS((s) => s.addWaypoint);
  const updateWaypoint = useGCS((s) => s.updateWaypoint);
  const userLocation = useGCS((s) => s.userLocation);
  const mapRef = useRef(null);
  const centeredOnUserRef = useRef(false);

  const [providerKey, setProviderKey] = useState("satellite"); // Default to Satellite map like Mission Planner!
  const [autoPan, setAutoPan] = useState(true);
  const [showHud, setShowHud] = useState(true);

  const provider = MAP_PROVIDERS[providerKey] || MAP_PROVIDERS.satellite;

  const center = useMemo(() => {
    if (activeDrone && isValidCoord(activeDrone.telemetry?.latitude, activeDrone.telemetry?.longitude)) {
      return [activeDrone.telemetry.latitude, activeDrone.telemetry.longitude];
    }
    if (activeDrone && isValidCoord(activeDrone.home_lat, activeDrone.home_lon)) {
      return [activeDrone.home_lat, activeDrone.home_lon];
    }
    if (drones[0] && isValidCoord(drones[0].telemetry?.latitude, drones[0].telemetry?.longitude)) {
      return [drones[0].telemetry.latitude, drones[0].telemetry.longitude];
    }
    if (drones[0] && isValidCoord(drones[0].home_lat, drones[0].home_lon)) {
      return [drones[0].home_lat, drones[0].home_lon];
    }
    if (userLocation && isValidCoord(userLocation.lat, userLocation.lon)) {
      return [userLocation.lat, userLocation.lon];
    }
    return [28.6769, 77.5020];
  }, [activeDrone, drones, userLocation]);

  useEffect(() => {
    if (!userLocation || centeredOnUserRef.current || !mapRef.current) return;
    if (isValidCoord(userLocation.lat, userLocation.lon)) {
      mapRef.current.flyTo([userLocation.lat, userLocation.lon], 17, { animate: true, duration: 1.2 });
      centeredOnUserRef.current = true;
    }
  }, [userLocation]);

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
    const lat = isValidCoord(activeDrone.telemetry?.latitude, activeDrone.telemetry?.longitude)
      ? activeDrone.telemetry.latitude
      : activeDrone.home_lat;
    const lon = isValidCoord(activeDrone.telemetry?.latitude, activeDrone.telemetry?.longitude)
      ? activeDrone.telemetry.longitude
      : activeDrone.home_lon;
    if (isValidCoord(lat, lon)) {
      mapRef.current.flyTo([lat, lon], Math.max(mapRef.current.getZoom(), 17));
    }
  };

  const centerOnUser = () => {
    if (!userLocation || !mapRef.current) return;
    if (isValidCoord(userLocation.lat, userLocation.lon)) {
      mapRef.current.flyTo([userLocation.lat, userLocation.lon], 17, { animate: true });
    }
  };

  const fitAll = () => {
    if (!drones.length || !mapRef.current) return;
    const validDrones = drones.filter((d) =>
      isValidCoord(d.telemetry?.latitude, d.telemetry?.longitude) || isValidCoord(d.home_lat, d.home_lon)
    );
    if (!validDrones.length) return;
    const bounds = L.latLngBounds(
      validDrones.map((d) =>
        isValidCoord(d.telemetry?.latitude, d.telemetry?.longitude)
          ? [d.telemetry.latitude, d.telemetry.longitude]
          : [d.home_lat, d.home_lon]
      )
    );
    mapRef.current.fitBounds(bounds.pad(0.3), { animate: true });
  };

  // Calculate Mission Planner Target Heading Line (Red Line)
  const targetHeadingLine = useMemo(() => {
    if (!activeDrone) return null;
    const lat = activeDrone.telemetry.latitude;
    const lon = activeDrone.telemetry.longitude;
    const hdgRad = (activeDrone.telemetry.heading * Math.PI) / 180;

    // Project 150 meters ahead
    const distMeters = 150;
    const latDist = (distMeters / 111139) * Math.cos(hdgRad);
    const lonDist = (distMeters / (111139 * Math.cos((lat * Math.PI) / 180))) * Math.sin(hdgRad);

    return [
      [lat, lon],
      [lat + latDist, lon + lonDist],
    ];
  }, [activeDrone]);

  // Direct Line to Current Waypoint (Orange Line)
  const directWpLine = useMemo(() => {
    if (!activeDrone || !draftWaypoints.length) return null;
    const targetWp = draftWaypoints[0];
    return [
      [activeDrone.telemetry.latitude, activeDrone.telemetry.longitude],
      [targetWp.latitude, targetWp.longitude],
    ];
  }, [activeDrone, draftWaypoints]);

  return (
    <div data-testid="map-container" className="flex-1 relative bg-[#0a0a0a]">
      <MapContainer
        center={center}
        zoom={17}
        className="w-full h-full"
        zoomControl={true}
        dragging={true}
        doubleClickZoom={true}
        scrollWheelZoom={true}
        ref={mapRef}
      >
        <TileLayer
          key={providerKey}
          attribution='&copy; Mission Planner Mapping'
          url={provider.url}
          maxZoom={provider.maxZoom}
          subdomains={provider.subdomains}
        />
        <MapClickHandler onClick={handleMapClick} />
        <UserInteractionHandler onUserDrag={() => setAutoPan(false)} />
        <AutoPanHandler activeDrone={activeDrone} autoPan={autoPan} />
        <MapResizeInvalidator />

        {/* Home positions */}
        {drones.map((d) => (
          <React.Fragment key={`home-group-${d.id}`}>
            <Circle
              center={[d.home_lat, d.home_lon]}
              radius={15}
              pathOptions={{ color: "#FFB000", weight: 1.5, dashArray: "3,3", fillColor: "#FFB000", fillOpacity: 0.1 }}
            />
            <Marker
              position={[d.home_lat, d.home_lon]}
              icon={homeIcon}
              interactive={false}
            />
          </React.Fragment>
        ))}

        {/* GPS Track Trail (Black / Purple Line like Mission Planner) */}
        {drones.map((d) => (
          <Polyline
            key={`trail-${d.id}`}
            positions={d.trail || []}
            pathOptions={{
              color: d.id === activeId ? "#800080" : "#00F0FF",
              weight: 3,
              opacity: 0.85,
            }}
          />
        ))}

        {/* Target Heading Line (Red Line) */}
        {targetHeadingLine && (
          <Polyline
            positions={targetHeadingLine}
            pathOptions={{ color: "#FF003C", weight: 2, opacity: 0.9 }}
          />
        )}

        {/* Direct to Waypoint Line (Orange Line) */}
        {directWpLine && (
          <Polyline
            positions={directWpLine}
            pathOptions={{ color: "#FFB000", weight: 2, dashArray: "5,5", opacity: 0.9 }}
          />
        )}

        {/* Drone Markers */}
        {drones.map((d) => (
          <Marker
            key={d.id}
            position={[d.telemetry.latitude, d.telemetry.longitude]}
            icon={quadcopterIcon(d.telemetry.heading, d.id === activeId, d.telemetry.armed)}
            eventHandlers={{ click: () => setActive(d.id) }}
          />
        ))}

        {/* Draft Mission Polyline */}
        {draftWaypoints.length > 1 && (
          <Polyline
            positions={draftWaypoints.map((w) => [w.latitude, w.longitude])}
            pathOptions={{ color: "#00F0FF", weight: 2.5, opacity: 0.9 }}
          />
        )}

        {/* Waypoint Markers */}
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

        {/* User GPS marker */}
        {userLocation && (
          <>
            <Circle
              center={[userLocation.lat, userLocation.lon]}
              radius={Math.min(userLocation.accuracy || 30, 200)}
              pathOptions={{ color: "#00F0FF", weight: 1, opacity: 0.6, fillColor: "#00F0FF", fillOpacity: 0.08 }}
            />
            <Marker position={[userLocation.lat, userLocation.lon]} icon={userIcon} interactive={false} />
          </>
        )}
      </MapContainer>

      {/* Top Left Instructions Overlay */}
      <div className="absolute top-3 left-3 z-[500] bg-zinc-900/90 border border-zinc-700 px-3 py-1.5 backdrop-blur-xs transition-all">
        <div className="font-mono text-[10px] text-zinc-200">
          CLICK MAP TO ADD WAYPOINT (<span className="text-[#FFB000]">{draftWaypoints.length}</span>)
        </div>
      </div>

      {/* Top Right Controls Overlay */}
      <div className="absolute top-3 right-3 z-[500] flex gap-1 bg-zinc-900/90 border border-zinc-700 p-1 backdrop-blur-xs">
        {/* Layer Selector */}
        <select
          value={providerKey}
          onChange={(e) => setProviderKey(e.target.value)}
          className="bg-zinc-800 border border-zinc-700 text-zinc-100 text-[11px] font-mono px-2 h-7 focus:outline-none"
        >
          <option value="satellite">Google Satellite</option>
          <option value="hybrid">Google Hybrid</option>
          <option value="dark">CartoDB Dark</option>
          <option value="osm">OpenStreetMap</option>
        </select>

        <button
          onClick={fitAll}
          className="bg-zinc-800 hover:bg-zinc-700 text-zinc-100 h-7 px-2.5 text-[10px] font-mono uppercase"
        >
          Fit All
        </button>
        <button
          onClick={centerOnUser}
          disabled={!userLocation}
          title="Center on my location"
          className="bg-zinc-800 hover:bg-zinc-700 text-zinc-100 h-7 w-7 flex items-center justify-center disabled:opacity-40"
        >
          <NavIcon className="w-3.5 h-3.5 text-[#00F0FF]" />
        </button>
        <button
          onClick={centerActive}
          title="Center on active drone"
          className="bg-zinc-800 hover:bg-zinc-700 text-zinc-100 h-7 w-7 flex items-center justify-center"
        >
          <Crosshair className="w-3.5 h-3.5 text-[#FFB000]" />
        </button>
      </div>

      {/* Bottom Mission Planner Style Telemetry & Location Bar */}
      <div className="absolute bottom-0 left-0 right-0 z-[500] bg-black/90 border-t border-zinc-700 px-3 py-1.5 flex flex-wrap items-center justify-between font-mono text-[10px] text-zinc-300 backdrop-blur-xs">
        <div className="flex items-center gap-4">
          <span className="text-[#00FF41]">
            GEO: <span className="text-white font-bold">{activeDrone ? `${activeDrone.telemetry.latitude.toFixed(7)} ${activeDrone.telemetry.longitude.toFixed(7)} ${(activeDrone.telemetry.altitude_relative ?? 0).toFixed(2)}m` : "-- -- --"}</span>
          </span>
          <span>hdop: <span className="text-white font-bold">{activeDrone?.telemetry?.hdop != null ? activeDrone.telemetry.hdop.toFixed(1) : "--"}</span></span>
          <span>Sats: <span className="text-white font-bold">{activeDrone?.telemetry?.satellites != null ? activeDrone.telemetry.satellites : "--"}</span></span>
        </div>

        {/* Legend Indicator Lines */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <span className="w-3 h-[2px] bg-[#FF003C]" />
            <span className="text-zinc-400">Heading</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-3 h-[2px]" style={{background:'#FFB000',borderTop:'2px dashed #FFB000'}} />
            <span className="text-zinc-400">To Waypoint</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-3 h-[2px] bg-[#800080]" />
            <span className="text-zinc-400">GPS Track</span>
          </div>

          {/* Auto Pan Toggle Button */}
          <button
            onClick={() => setAutoPan(!autoPan)}
            className={`flex items-center gap-1 px-2 py-0.5 rounded-xs border transition-colors ${autoPan
              ? "bg-[#00F0FF]/10 border-[#00F0FF] text-[#00F0FF]"
              : "bg-zinc-800 border-zinc-700 text-zinc-400"
              }`}
          >
            {autoPan ? <Lock className="w-3 h-3" /> : <Unlock className="w-3 h-3" />}
            Auto Pan {autoPan ? "ON" : "OFF"}
          </button>
        </div>
      </div>
    </div>
  );
}
