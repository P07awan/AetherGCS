import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import GCSPage from "@/pages/GCSPage";

export default function App() {
  return (
    <div className="App font-sans">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<GCSPage />} />
        </Routes>
      </BrowserRouter>
      <Toaster
        theme="dark"
        // Bottom-right, above the status bar: top-right covered Takeoff/Land
        // and E-STOP while a toast was showing.
        position="bottom-right"
        offset={44}
        toastOptions={{
          style: {
            background: "#18181b",
            color: "#f4f4f5",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: "2px",
            fontFamily: '"IBM Plex Sans", sans-serif',
          },
        }}
      />
    </div>
  );
}
