import { useEffect } from "react";
import {
  Tabs, TabsList, TabsTrigger, TabsContent,
} from "@/components/ui/tabs";
import { useGCS } from "@/store/gcsStore";
import { createTelemetrySocket } from "@/services/telemetrySocket";
import { commandsApi, dronesApi, missionsApi } from "@/services/api";
import TopToolbar from "@/components/TopToolbar";
import DroneListSidebar from "@/components/DroneListSidebar";
import TelemetryPanel from "@/components/TelemetryPanel";
import DroneMap from "@/components/DroneMap";
import MissionPlanner from "@/components/MissionPlanner";
import CommandHistory from "@/components/CommandHistory";
import StatusBar from "@/components/StatusBar";

export default function GCSPage() {
  const setSnapshot = useGCS((s) => s.setSnapshot);
  const upsertDrone = useGCS((s) => s.upsertDrone);
  const removeDrone = useGCS((s) => s.removeDrone);
  const setWsStatus = useGCS((s) => s.setWsStatus);
  const addCommandLog = useGCS((s) => s.addCommandLog);
  const setCommandHistory = useGCS((s) => s.setCommandHistory);
  const setMissions = useGCS((s) => s.setMissions);

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
    <div className="h-screen w-screen flex flex-col bg-zinc-950 text-zinc-200 overflow-hidden">
      <TopToolbar />
      <div className="flex-1 flex overflow-hidden">
        <DroneListSidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <DroneMap />
          <div className="h-72 border-t border-zinc-800 bg-zinc-950 flex flex-col">
            <Tabs defaultValue="mission" className="h-full flex flex-col">
              <TabsList className="h-9 bg-transparent border-b border-zinc-800 rounded-none justify-start px-2 gap-1">
                <TabsTrigger
                  data-testid="tab-mission"
                  value="mission"
                  className="rounded-none data-[state=active]:bg-zinc-900 data-[state=active]:text-[#FFB000] data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-[#FFB000] text-[11px] font-mono uppercase tracking-wider"
                >
                  Mission Planner
                </TabsTrigger>
                <TabsTrigger
                  data-testid="tab-history"
                  value="history"
                  className="rounded-none data-[state=active]:bg-zinc-900 data-[state=active]:text-[#00F0FF] data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-[#00F0FF] text-[11px] font-mono uppercase tracking-wider"
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
        <TelemetryPanel />
      </div>
      <StatusBar />
    </div>
  );
}
