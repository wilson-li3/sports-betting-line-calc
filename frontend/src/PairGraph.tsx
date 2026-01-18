import { useState, useEffect } from "react";
import ForceGraph2D from "react-force-graph-2d";

type PairStat = {
  A: string;
  B: string;
  lift: number;
  phi: number;
  n: number;
};

type GraphNode = { id: string };
type GraphLink = { source: string; target: string; lift: number; phi: number; n: number };

// API response type
type PairsResponse = {
  pairs: PairStat[];
};

function toPretty(id: string) {
  return id.replace(/_HIT$/, "").replace(/_/g, " ");
}

// MOCK data kept as fallback
const MOCK: PairStat[] = [
  { A: "TEAM_TOTAL_OVER_HIT", B: "PRIMARY_SCORER_PTS_OVER_HIT", n: 7, lift: 1.40, phi: 0.40 },
  { A: "TEAM_TOTAL_OVER_HIT", B: "PRIMARY_FACILITATOR_AST_OVER_HIT", n: 7, lift: 1.17, phi: 0.26 },
  { A: "TEAM_TOTAL_OVER_HIT", B: "PRIMARY_REBOUNDER_REB_OVER_HIT", n: 7, lift: 1.00, phi: 0.00 },
  { A: "GAME_TOTAL_OVER_HIT", B: "PRIMARY_SCORER_PTS_OVER_HIT", n: 7, lift: 1.12, phi: 0.30 },
  { A: "GAME_TOTAL_OVER_HIT", B: "PRIMARY_FACILITATOR_AST_OVER_HIT", n: 7, lift: 0.93, phi: -0.26 },
];

export default function PairGraph() {
  // State to store fetched pair data, defaults to MOCK data as fallback
  const [pairData, setPairData] = useState<PairStat[]>(MOCK);
  // State to track data source: "LIVE" for backend data, "MOCK" for fallback
  const [dataSource, setDataSource] = useState<"LIVE" | "MOCK">("MOCK");

  // Fetch data from backend API on component mount
  useEffect(() => {
    fetch("http://127.0.0.1:8000/pairs")
      .then((res) => {
        if (!res.ok) {
          throw new Error("Failed to fetch pairs");
        }
        return res.json();
      })
      .then((data: PairsResponse) => {
        // If successful AND data.pairs exists with length > 0: use LIVE data
        if (data.pairs && data.pairs.length > 0) {
          setPairData(data.pairs);
          setDataSource("LIVE");
        } else {
          // If data is empty, fall back to MOCK
          setDataSource("MOCK");
        }
      })
      .catch((err) => {
        // If fetch fails, continue using MOCK data (already in state)
        console.warn("Failed to fetch pairs from API, using MOCK data:", err);
        setDataSource("MOCK");
      });
  }, []);

  // Build nodes/links dynamically from pair data (fetched or MOCK)
  const nodeIds = new Set<string>();
  const links: GraphLink[] = pairData.map((p) => {
    nodeIds.add(p.A);
    nodeIds.add(p.B);
    return { source: p.A, target: p.B, lift: p.lift, phi: p.phi, n: p.n };
  });
  const nodes: GraphNode[] = Array.from(nodeIds).map((id) => ({ id }));

  const data = { nodes, links };

  return (
  <div style={{ height: "100vh", width: "100vw", position: "relative" }}>
    {/* Legend overlay */}
    <div
      style={{
        position: "absolute",
        top: 12,
        left: 12,
        zIndex: 10,
        background: "rgba(255, 255, 255, 0.92)",
        border: "1px solid rgba(0,0,0,0.12)",
        borderRadius: 10,
        padding: "10px 12px",
        width: 280,
        fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
        fontSize: 12,
        lineHeight: 1.35,
      }}
    >
      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 8 }}>
        Graph Legend
      </div>

      {/* Data source indicator badge */}
      <div
        style={{
          display: "inline-block",
          padding: "4px 8px",
          borderRadius: 6,
          fontSize: 11,
          fontWeight: 600,
          marginBottom: 8,
          background: dataSource === "LIVE" ? "rgba(0, 150, 0, 0.15)" : "rgba(200, 140, 0, 0.15)",
          color: dataSource === "LIVE" ? "rgba(0, 100, 0, 0.9)" : "rgba(140, 100, 0, 0.9)",
          border: `1px solid ${dataSource === "LIVE" ? "rgba(0, 150, 0, 0.3)" : "rgba(200, 140, 0, 0.3)"}`,
        }}
      >
        DATA: {dataSource}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span
          style={{
            display: "inline-block",
            width: 26,
            height: 4,
            background: "rgba(0, 150, 0, 0.75)",
            borderRadius: 4,
          }}
        />
        <span><b>Green edge</b>: moves together (stack candidate)</span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span
          style={{
            display: "inline-block",
            width: 26,
            height: 4,
            background: "rgba(200, 0, 0, 0.75)",
            borderRadius: 4,
          }}
        />
        <span><b>Red edge</b>: opposite relationship (hedge candidate)</span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span
          style={{
            display: "inline-block",
            width: 26,
            height: 4,
            background: "rgba(120, 120, 120, 0.55)",
            borderRadius: 4,
          }}
        />
        <span><b>Gray edge</b>: neutral / weak relationship</span>
      </div>

      <div style={{ marginBottom: 6 }}>
        <b>Edge thickness</b>: strength (|phi| correlation)
      </div>
      <div style={{ color: "rgba(0,0,0,0.75)" }}>
        <b>Lift</b> &gt; 1 means the pair hits together more than random chance.
      </div>

      <div style={{ marginTop: 10, color: "rgba(0,0,0,0.7)" }}>
        Tip: hover an edge to see <b>lift</b>, <b>phi</b>, and <b>n</b>.
      </div>
    </div>

    <ForceGraph2D
      graphData={data}
      nodeLabel={(n: any) => toPretty(n.id)}
      linkLabel={(l: any) => `lift=${l.lift.toFixed(2)}, phi=${l.phi.toFixed(2)}, n=${l.n}`}
      nodeCanvasObject={(node: any, ctx, globalScale) => {
        const label = toPretty(node.id);
        const fontSize = 12 / globalScale;
        ctx.font = `${fontSize}px Sans-Serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";

        ctx.beginPath();
        ctx.arc(node.x, node.y, 6, 0, 2 * Math.PI);
        ctx.fillStyle = "#111";
        ctx.fill();

        ctx.fillStyle = "#000";
        ctx.fillText(label, node.x, node.y - 14);
      }}
      linkWidth={(l: any) => {
        const strength = Math.max(0, Math.abs(l.phi));
        return 1 + strength * 6;
      }}
      linkColor={(l: any) => {
        if (l.phi > 0) return "rgba(0, 150, 0, 0.7)";
        if (l.phi < 0) return "rgba(200, 0, 0, 0.7)";
        return "rgba(120, 120, 120, 0.5)";
      }}
    />
  </div>
);

}
