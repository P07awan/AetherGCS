import { useEffect, useRef } from "react";
import { toast } from "sonner";
import { useGCS } from "@/store/gcsStore";

/**
 * Requests the browser's geolocation and stores it in the GCS store.
 * Subscribes to updates via watchPosition so the map / home fields
 * stay accurate as the operator moves.
 */
export function useUserGeolocation() {
  const setUserLocation = useGCS((s) => s.setUserLocation);
  const watchIdRef = useRef(null);

  useEffect(() => {
    if (!("geolocation" in navigator)) {
      toast.warning("Geolocation not supported by this browser");
      return;
    }

    // one-time high-accuracy fix
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude, accuracy } = pos.coords;
        setUserLocation({ lat: latitude, lon: longitude, accuracy });
        toast.success(
          `Location acquired · ±${accuracy.toFixed(0)}m`,
          { description: `${latitude.toFixed(5)}, ${longitude.toFixed(5)}` }
        );
      },
      (err) => {
        toast.warning(
          "Location permission denied",
          { description: "Falling back to default. Enable location to auto-home." }
        );
        console.warn("Geolocation error:", err.message);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );

    // ongoing watch (low freq)
    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        const { latitude, longitude, accuracy } = pos.coords;
        setUserLocation({ lat: latitude, lon: longitude, accuracy });
      },
      () => {},
      { enableHighAccuracy: false, maximumAge: 30000, timeout: 60000 }
    );

    return () => {
      if (watchIdRef.current != null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
      }
    };
  }, [setUserLocation]);
}
