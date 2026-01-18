import { useState } from "react";
import PairGraph from "./PairGraph";
import GraphExplorer from "./GraphExplorer";
import MLDashboard from "./MLDashboard";

export default function App() {
  const [view, setView] = useState<"pairs" | "graph" | "ml">("ml");

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Simple Navigation */}
      <div
        style={{
          padding: "8px 16px",
          borderBottom: "1px solid rgba(0,0,0,0.1)",
          background: "#f8f9fa",
          display: "flex",
          gap: 16,
          fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
        }}
      >
        <button
          onClick={() => setView("pairs")}
          style={{
            padding: "6px 12px",
            border: "1px solid rgba(0,0,0,0.2)",
            borderRadius: 4,
            background: view === "pairs" ? "#4A90E2" : "white",
            color: view === "pairs" ? "white" : "black",
            cursor: "pointer",
            fontSize: 12,
            fontWeight: view === "pairs" ? 600 : 400,
          }}
        >
          Pairs Explorer
        </button>
        <button
          onClick={() => setView("graph")}
          style={{
            padding: "6px 12px",
            border: "1px solid rgba(0,0,0,0.2)",
            borderRadius: 4,
            background: view === "graph" ? "#4A90E2" : "white",
            color: view === "graph" ? "white" : "black",
            cursor: "pointer",
            fontSize: 12,
            fontWeight: view === "graph" ? 600 : 400,
          }}
        >
          Graph Explorer
        </button>
        <button
          onClick={() => setView("ml")}
          style={{
            padding: "6px 12px",
            border: "1px solid rgba(0,0,0,0.2)",
            borderRadius: 4,
            background: view === "ml" ? "#4A90E2" : "white",
            color: view === "ml" ? "white" : "black",
            cursor: "pointer",
            fontSize: 12,
            fontWeight: view === "ml" ? 600 : 400,
          }}
        >
          ML Dashboard
        </button>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "hidden" }}>
        {view === "pairs" ? <PairGraph /> : view === "graph" ? <GraphExplorer /> : <MLDashboard />}
      </div>
    </div>
  );
}
