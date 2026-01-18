import { useState } from "react";
import PairGraph from "./PairGraph";
import GraphExplorer from "./GraphExplorer";
import MLDashboard from "./MLDashboard";

import BacktestReview from "./BacktestReview";
import FutureGames from "./FutureGames";

export default function App() {
  const [view, setView] = useState<"pairs" | "graph" | "ml" | "backtest" | "future">("ml");

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Simple Navigation */}
      <div
        style={{
          padding: "8px 16px",
          borderBottom: "1px solid rgba(0,0,0,0.1)",
          background: "#f8f9fa",
          display: "flex",
          gap: 16,
          flexWrap: "wrap",
          fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
          position: "sticky",
          top: 0,
          zIndex: 100,
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
        <button
          onClick={() => setView("backtest")}
          style={{
            padding: "6px 12px",
            border: "1px solid rgba(0,0,0,0.2)",
            borderRadius: 4,
            background: view === "backtest" ? "#4A90E2" : "white",
            color: view === "backtest" ? "white" : "black",
            cursor: "pointer",
            fontSize: 12,
            fontWeight: view === "backtest" ? 600 : 400,
          }}
        >
          Backtest Review
        </button>
        <button
          onClick={() => setView("future")}
          style={{
            padding: "6px 12px",
            border: "1px solid rgba(0,0,0,0.2)",
            borderRadius: 4,
            background: view === "future" ? "#4A90E2" : "white",
            color: view === "future" ? "white" : "black",
            cursor: "pointer",
            fontSize: 12,
            fontWeight: view === "future" ? 600 : 400,
          }}
        >
          Future Games
        </button>
      </div>

      {/* Content - allow scrolling */}
      <div style={{ flex: 1, overflowY: "auto", overflowX: "hidden" }}>
        {view === "pairs" ? <PairGraph /> : 
         view === "graph" ? <GraphExplorer /> : 
         view === "ml" ? <MLDashboard /> :
         view === "backtest" ? <BacktestReview /> :
         <FutureGames />}
      </div>
    </div>
  );
}
