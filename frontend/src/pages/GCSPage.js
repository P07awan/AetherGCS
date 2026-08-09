import { useEffect, useRef } from "react";
import {
  Tabs, TabsList, TabsTrigger, TabsContent,
} from "@/components/ui/tabs";
import { useGCS } from "@/store/gcsStore";
import { createTelemetrySocket } from "@/services/telemetrySocket";
import { commandsApi, dronesApi, missionsApi } from "@/services/api";
import { useUserGeolocation } from "@/hooks/useUserGeolocation";
import TopToolbar from "@/components/TopToolbar";
import DroneListSidebar from "@/components/DroneListSidebar";
import TelemetryPanel from "@/components/TelemetryPanel";
import DroneMap from "@/components/DroneMap";
import MissionPlanner from "@/components/MissionPlanner";
import CommandHistory from "@/components/CommandHistory";
import StatusBar from "@/components/StatusBar";
import { useResizable } from "@/hooks/useResizable";
import { ResizeHandle } from "@/components/ResizeHandle";

// Constants for layout constraints
const LEFT   = { min: 50, default: 360, max: 600, field: "leftSidebarWidth" };
const RIGHT  = { min: 50, default: 360, max: 650, field: "rightSidebarWidth" };
const BOTTOM = { min: 50, default: 350, max: 1000, field: "missionPlannerHeight" };

export default function GCSPage() {
  const setSnapshot = useGCS((s) => s.setSnapshot);
  const upsertDrone = useGCS((s) => s.upsertDrone);
  const removeDrone = useGCS((s) => s.removeDrone);
  const setWsStatus = useGCS((s) => s.setWsStatus);
  const addCommandLog = useGCS((s) => s.addCommandLog);
  const setCommandHistory = useGCS((s) => s.setCommandHistory);
  const setMissions = useGCS((s) => s.setMissions);

  useUserGeolocation();

  // Resizable layout hooks
  const leftPanel = useResizable({
    id: LEFT.field,
    initialSize: LEFT.default,
    minSize: LEFT.min,
    maxSize: LEFT.max,
    direction: "vertical",
  });

  const rightPanel = useResizable({
    id: RIGHT.field,
    initialSize: RIGHT.default,
    minSize: RIGHT.min,
    maxSize: RIGHT.max,
    direction: "vertical",
    invert: true, // Dragging left increases right panel width
  });

  const bottomPanel = useResizable({
    id: BOTTOM.field,
    initialSize: BOTTOM.default,
    minSize: BOTTOM.min,
    maxSize: BOTTOM.max,
    direction: "horizontal",
    invert: true, // Dragging up increases bottom panel height
  });

  // Initial data + WS
  useEffect(() => {
    (async () => {
      try {
        const [drones, history, missions] = await Promise.all([
          dronesApi.list(),
          commandsApi.history(200),
          missionsApi.list(),
        ]);
        setSnapshot(drones);
        setCommandHistory(history);
        setMissions(missions);
      } catch (e) {
        console.error("Initial load failed", e);
      }
    })();

    const socket = createTelemetrySocket({
      onSnapshot: setSnapshot,
      onDrone: upsertDrone,
      onDroneRemoved: (msg) => removeDrone(msg.id),
      onCommand: addCommandLog,
      onStatus: setWsStatus,
    });
    return () => socket.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="h-screen w-screen flex flex-col bg-zinc-950 text-zinc-100 overflow-hidden">
      <TopToolbar />
      <div className="flex-1 flex overflow-hidden">
        
        {/* Left Sidebar */}
        <DroneListSidebar 
          ref={leftPanel.ref}
          style={{ width: leftPanel.size, minWidth: leftPanel.size, maxWidth: leftPanel.size }} 
        />
        
        {/* Resize Handle for Left Sidebar */}
        <ResizeHandle direction="vertical" {...leftPanel.handleProps} />

        {/* Center Panel (Map + Mission Planner) */}
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          <DroneMap />
          
          {/* Resize Handle for Mission Planner */}
          <ResizeHandle direction="horizontal" {...bottomPanel.handleProps} />

          {/* Bottom Mission Planner */}
          <div 
            ref={bottomPanel.ref}
            className="border-t border-zinc-700 bg-zinc-900 flex flex-col overflow-hidden"
            style={{ height: bottomPanel.size }}
          >
            <Tabs defaultValue="mission" className="h-full flex flex-col">
              <TabsList className="h-9 bg-zinc-800/60 border-b border-zinc-700 rounded-none justify-start px-2 gap-1 shrink-0">
                <TabsTrigger
                  data-testid="tab-mission"
                  value="mission"
                  className="rounded-none data-[state=active]:bg-zinc-950 data-[state=active]:text-[#FFB000] data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-[#FFB000] text-[11px] font-mono uppercase tracking-wider text-zinc-300"
                >
                  Mission Planner
                </TabsTrigger>
                <TabsTrigger
                  data-testid="tab-history"
                  value="history"
                  className="rounded-none data-[state=active]:bg-zinc-950 data-[state=active]:text-[#00F0FF] data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-[#00F0FF] text-[11px] font-mono uppercase tracking-wider text-zinc-300"
                >
                  Command Log
                </TabsTrigger>
              </TabsList>
              <TabsContent value="mission" className="flex-1 mt-0 overflow-hidden">
                <MissionPlanner />
              </TabsContent>
              <TabsContent value="history" className="flex-1 mt-0 overflow-hidden">
                <CommandHistory />
              </TabsContent>
            </Tabs>
          </div>
        </div>

        {/* Resize Handle for Right Sidebar */}
        <ResizeHandle direction="vertical" {...rightPanel.handleProps} />

        {/* Right Sidebar */}
        <TelemetryPanel 
          ref={rightPanel.ref}
          style={{ width: rightPanel.size, minWidth: rightPanel.size, maxWidth: rightPanel.size }} 
        />
        
      </div>
      <StatusBar />
    </div>
  );
}
