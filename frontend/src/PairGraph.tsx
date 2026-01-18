import { useState, useEffect } from "react";
import ForceGraph2D from "react-force-graph-2d";

// Updated types to match backend response
type PairStat = {
  A: string;
  B: string;
  lift: number;
  phi: number;
  n: number;
  confidence?: number;
  pair?: string;
  // Uncertainty fields (optional - may not be present)
  lift_lo?: number;
  lift_hi?: number;
  phi_lo?: number;
  phi_hi?: number;
  pBA_mean?: number;
  pBA_lo?: number;
  pBA_hi?: number;
};

type GraphNode = { 
  id: string;
  x?: number; // Added by react-force-graph-2d during simulation
  y?: number; // Added by react-force-graph-2d during simulation
};
type GraphLink = {
  source: string;
  target: string;
  lift: number;
  phi: number;
  n: number;
  confidence?: number;
  kind: "stack" | "hedge" | "neutral";
  selected?: boolean;
};

// API response types
type ExplorerResponse = {
  meta: {
    min_n: number;
    kind: string;
    sort: string;
    limit: number;
    count: number;
  };
  pairs: PairStat[];
};

// MOCK data kept as fallback
const MOCK: PairStat[] = [
  { A: "TEAM_TOTAL_OVER_HIT", B: "PRIMARY_SCORER_PTS_OVER_HIT", n: 7, lift: 1.40, phi: 0.40 },
  { A: "TEAM_TOTAL_OVER_HIT", B: "PRIMARY_FACILITATOR_AST_OVER_HIT", n: 7, lift: 1.17, phi: 0.26 },
  { A: "TEAM_TOTAL_OVER_HIT", B: "PRIMARY_REBOUNDER_REB_OVER_HIT", n: 7, lift: 1.00, phi: 0.00 },
  { A: "GAME_TOTAL_OVER_HIT", B: "PRIMARY_SCORER_PTS_OVER_HIT", n: 7, lift: 1.12, phi: 0.30 },
  { A: "GAME_TOTAL_OVER_HIT", B: "PRIMARY_FACILITATOR_AST_OVER_HIT", n: 7, lift: 0.93, phi: -0.26 },
];

// Helper functions
function toPretty(id: string): string {
  return id.replace(/_HIT$/, "").replace(/_/g, " ");
}

function classifyPair(lift: number, phi: number): "stack" | "hedge" | "neutral" {
  if (lift > 1.10 && phi > 0.10) return "stack";
  if (lift < 0.95 && phi < -0.10) return "hedge";
  return "neutral";
}

function computeConfidence(phi: number, n: number): number {
  if (n <= 1) return 0;
  return Math.abs(phi) * Math.log10(n);
}

// Add confidence and kind to MOCK data for consistency
const MOCK_ENHANCED: PairStat[] = MOCK.map((p) => ({
  ...p,
  confidence: computeConfidence(p.phi, p.n),
  pair: `${p.A} ↔ ${p.B}`,
}));

export default function PairGraph() {
  // Filter state
  const [minN, setMinN] = useState(50);
  const [kind, setKind] = useState<"all" | "stack" | "hedge" | "neutral">("all");
  const [sort, setSort] = useState<"confidence" | "lift" | "abs_phi">("confidence");

  // Data state
  const [pairData, setPairData] = useState<PairStat[]>(MOCK_ENHANCED);
  const [dataSource, setDataSource] = useState<"LIVE" | "MOCK">("MOCK");
  const [selectedPair, setSelectedPair] = useState<PairStat | null>(null);

  // Fetch filtered data from backend
  useEffect(() => {
    const params = new URLSearchParams({
      min_n: minN.toString(),
      kind: kind,
      sort: sort,
      limit: "100",
    });

    fetch(`http://127.0.0.1:8000/pairs/explorer?${params}`)
      .then((res) => {
        if (!res.ok) {
          throw new Error("Failed to fetch pairs");
        }
        return res.json();
      })
      .then((data: ExplorerResponse) => {
        // If fetch succeeds (HTTP 200), always set dataSource to "LIVE"
        // even if pairs array is empty (e.g., due to strict filters)
        const enhanced = (data.pairs || []).map((p) => ({
          ...p,
          confidence: p.confidence ?? computeConfidence(p.phi, p.n),
        }));
        setPairData(enhanced);
        setDataSource("LIVE");
      })
      .catch((err) => {
        // Only fall back to MOCK on actual errors (network, JSON parse, etc.)
        console.warn("Failed to fetch pairs from API, using MOCK data:", err);
        setPairData(MOCK_ENHANCED);
        setDataSource("MOCK");
      });
  }, [minN, kind, sort]);

  // Build graph nodes and links from filtered pair data
  const nodeIds = new Set<string>();
  const links: GraphLink[] = pairData.map((p) => {
    nodeIds.add(p.A);
    nodeIds.add(p.B);
    const pairKind = classifyPair(p.lift, p.phi);
    const isSelected = selectedPair && selectedPair.A === p.A && selectedPair.B === p.B;
    return {
      source: p.A,
      target: p.B,
      lift: p.lift,
      phi: p.phi,
      n: p.n,
      confidence: p.confidence ?? computeConfidence(p.phi, p.n),
      kind: pairKind,
      selected: isSelected || false,
    };
  });
  const nodes: GraphNode[] = Array.from(nodeIds).map((id) => ({ id }));
  const graphData = { nodes, links };

  // Handle pair selection from list or graph
  const handlePairSelect = (pair: PairStat) => {
    setSelectedPair(pair);
  };

  // Handle link click on graph
  const handleLinkClick = (link: GraphLink) => {
    const pair = pairData.find((p) => p.A === link.source && p.B === link.target);
    if (pair) {
      handlePairSelect(pair);
    }
  };

  return (
    <div style={{ height: "100vh", width: "100vw", display: "flex", overflow: "hidden" }}>
      {/* Left Sidebar - Controls and Ranked List */}
      <div
        style={{
          width: 320,
          borderRight: "1px solid rgba(0,0,0,0.1)",
          display: "flex",
          flexDirection: "column",
          background: "#f8f9fa",
          fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
        }}
      >
        {/* Controls Section */}
        <div style={{ padding: "16px", borderBottom: "1px solid rgba(0,0,0,0.1)" }}>
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12 }}>
            Pairs Explorer
          </div>

          {/* Min N Input */}
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: "block", fontSize: 12, marginBottom: 4, fontWeight: 500 }}>
              Min sample size (n): {minN}
            </label>
            <input
              type="range"
              min="1"
              max="500"
              value={minN}
              onChange={(e) => setMinN(Number(e.target.value))}
              style={{ width: "100%" }}
            />
          </div>

          {/* Kind Dropdown */}
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: "block", fontSize: 12, marginBottom: 4, fontWeight: 500 }}>
              Relationship type:
            </label>
            <select
              value={kind}
              onChange={(e) => setKind(e.target.value as typeof kind)}
              style={{ width: "100%", padding: "6px", fontSize: 12 }}
            >
              <option value="all">All</option>
              <option value="stack">Stack</option>
              <option value="hedge">Hedge</option>
              <option value="neutral">Neutral</option>
            </select>
          </div>

          {/* Sort Dropdown */}
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: "block", fontSize: 12, marginBottom: 4, fontWeight: 500 }}>
              Sort by:
            </label>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as typeof sort)}
              style={{ width: "100%", padding: "6px", fontSize: 12 }}
            >
              <option value="confidence">Confidence</option>
              <option value="lift">Lift</option>
              <option value="abs_phi">|Phi|</option>
            </select>
          </div>

          {/* Data Source Badge */}
          <div
            style={{
              display: "inline-block",
              padding: "4px 8px",
              borderRadius: 6,
              fontSize: 11,
              fontWeight: 600,
              background: dataSource === "LIVE" ? "rgba(0, 150, 0, 0.15)" : "rgba(200, 140, 0, 0.15)",
              color: dataSource === "LIVE" ? "rgba(0, 100, 0, 0.9)" : "rgba(140, 100, 0, 0.9)",
              border: `1px solid ${dataSource === "LIVE" ? "rgba(0, 150, 0, 0.3)" : "rgba(200, 140, 0, 0.3)"}`,
            }}
          >
            DATA: {dataSource}
          </div>
        </div>

        {/* Ranked List Section */}
        <div style={{ flex: 1, overflowY: "auto", padding: "8px" }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, padding: "0 8px" }}>
            Pairs ({pairData.length})
          </div>
          {pairData.map((pair, idx) => {
            const pairKind = classifyPair(pair.lift, pair.phi);
            const isSelected = selectedPair && selectedPair.A === pair.A && selectedPair.B === pair.B;
            const kindColors = {
              stack: { bg: "rgba(0, 150, 0, 0.15)", color: "rgba(0, 100, 0, 0.9)", border: "rgba(0, 150, 0, 0.3)" },
              hedge: { bg: "rgba(200, 0, 0, 0.15)", color: "rgba(140, 0, 0, 0.9)", border: "rgba(200, 0, 0, 0.3)" },
              neutral: { bg: "rgba(120, 120, 120, 0.15)", color: "rgba(80, 80, 80, 0.9)", border: "rgba(120, 120, 120, 0.3)" },
            };
            const colors = kindColors[pairKind];

            return (
              <div
                key={`${pair.A}-${pair.B}-${idx}`}
                onClick={() => handlePairSelect(pair)}
                style={{
                  padding: "10px",
                  marginBottom: 6,
                  borderRadius: 6,
                  fontSize: 11,
                  cursor: "pointer",
                  background: isSelected ? "rgba(0, 100, 200, 0.1)" : "white",
                  border: `1px solid ${isSelected ? "rgba(0, 100, 200, 0.3)" : "rgba(0,0,0,0.1)"}`,
                  transition: "all 0.2s",
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.background = "rgba(0,0,0,0.05)";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.background = "white";
                  }
                }}
              >
                <div style={{ marginBottom: 4, fontWeight: 600 }}>
                  {toPretty(pair.A)} ↔ {toPretty(pair.B)}
                </div>
                <div style={{ display: "flex", gap: 8, marginBottom: 6, fontSize: 10 }}>
                  <span>n: {pair.n}</span>
                  <span>lift: {pair.lift.toFixed(2)}</span>
                  <span>φ: {pair.phi.toFixed(2)}</span>
                </div>
                <div
                  style={{
                    display: "inline-block",
                    padding: "2px 6px",
                    borderRadius: 4,
                    fontSize: 10,
                    fontWeight: 600,
                    background: colors.bg,
                    color: colors.color,
                    border: `1px solid ${colors.border}`,
                  }}
                >
                  {pairKind.toUpperCase()}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Center Graph Panel */}
      <div style={{ flex: 1, position: "relative" }}>
        <ForceGraph2D
          graphData={graphData}
          nodeLabel={(n: GraphNode) => toPretty(n.id)}
          linkLabel={(l: GraphLink) =>
            `lift=${l.lift.toFixed(2)}, φ=${l.phi.toFixed(2)}, n=${l.n}`
          }
          onLinkClick={handleLinkClick}
          nodeCanvasObject={(node: GraphNode, ctx, globalScale) => {
            const label = toPretty(node.id);
            const fontSize = 12 / globalScale;
            ctx.font = `${fontSize}px Sans-Serif`;
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";

            ctx.beginPath();
            ctx.arc(node.x!, node.y!, 6, 0, 2 * Math.PI);
            ctx.fillStyle = "#111";
            ctx.fill();

            ctx.fillStyle = "#000";
            ctx.fillText(label, node.x!, (node.y || 0) - 14);
          }}
          linkWidth={(l: GraphLink) => {
            const strength = l.confidence ?? Math.abs(l.phi);
            const baseWidth = 1 + strength * 3;
            return l.selected ? baseWidth + 2 : baseWidth;
          }}
          linkColor={(l: GraphLink) => {
            // Check if any pair is selected
            const hasSelection = selectedPair !== null;
            
            if (l.selected) {
              // Selected edge: bright and opaque
              if (l.kind === "stack") return "rgba(0, 200, 0, 0.9)";
              if (l.kind === "hedge") return "rgba(255, 0, 0, 0.9)";
              return "rgba(150, 150, 150, 0.7)";
            }
            
            // Non-selected edges: dim when something is selected, normal otherwise
            const opacity = hasSelection ? 0.25 : 0.6;
            if (l.kind === "stack") return `rgba(0, 150, 0, ${opacity})`;
            if (l.kind === "hedge") return `rgba(200, 0, 0, ${opacity})`;
            return `rgba(120, 120, 120, ${opacity})`;
          }}
        />
      </div>

      {/* Right Details Panel */}
      {selectedPair && (
        <div
          style={{
            width: 300,
            borderLeft: "1px solid rgba(0,0,0,0.1)",
            padding: "16px",
            background: "#f8f9fa",
            fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
            overflowY: "auto",
          }}
        >
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 16 }}>
            Pair Details
          </div>

          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
              {toPretty(selectedPair.A)}
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 16 }}>
              ↔ {toPretty(selectedPair.B)}
            </div>
          </div>

          <div style={{ marginBottom: 16, fontSize: 12 }}>
            <div style={{ marginBottom: 4 }}><b>n:</b> {selectedPair.n}</div>
            <div style={{ marginBottom: 4 }}>
              <b>lift:</b> {selectedPair.lift.toFixed(3)}
              {selectedPair.lift_lo !== undefined && selectedPair.lift_hi !== undefined && (
                <span style={{ color: "rgba(0,0,0,0.6)", fontSize: 11, marginLeft: 4 }}>
                  [{selectedPair.lift_lo.toFixed(3)}, {selectedPair.lift_hi.toFixed(3)}]
                </span>
              )}
            </div>
            <div style={{ marginBottom: 4 }}>
              <b>φ (phi):</b> {selectedPair.phi.toFixed(3)}
              {selectedPair.phi_lo !== undefined && selectedPair.phi_hi !== undefined && (
                <span style={{ color: "rgba(0,0,0,0.6)", fontSize: 11, marginLeft: 4 }}>
                  [{selectedPair.phi_lo.toFixed(3)}, {selectedPair.phi_hi.toFixed(3)}]
                </span>
              )}
            </div>
            {selectedPair.pBA_mean !== undefined && (
              <div style={{ marginBottom: 4 }}>
                <b>P(B|A):</b> {selectedPair.pBA_mean.toFixed(3)}
                {selectedPair.pBA_lo !== undefined && selectedPair.pBA_hi !== undefined && (
                  <span style={{ color: "rgba(0,0,0,0.6)", fontSize: 11, marginLeft: 4 }}>
                    [{selectedPair.pBA_lo.toFixed(3)}, {selectedPair.pBA_hi.toFixed(3)}]
                  </span>
                )}
              </div>
            )}
            <div style={{ marginBottom: 4 }}>
              <b>confidence:</b> {(selectedPair.confidence ?? computeConfidence(selectedPair.phi, selectedPair.n)).toFixed(3)}
            </div>
          </div>

          {(() => {
            const pairKind = classifyPair(selectedPair.lift, selectedPair.phi);
            let interpretation = "";
            if (pairKind === "stack") {
              interpretation = "These hit together more than chance. Good for stacking.";
            } else if (pairKind === "hedge") {
              interpretation = "These move opposite. Good for hedging.";
            } else {
              interpretation = "Weak relationship. Treat as mostly independent.";
            }
            return (
              <div
                style={{
                  padding: "12px",
                  borderRadius: 6,
                  background: pairKind === "stack" ? "rgba(0, 150, 0, 0.1)" : pairKind === "hedge" ? "rgba(200, 0, 0, 0.1)" : "rgba(120, 120, 120, 0.1)",
                  marginBottom: 16,
                  fontSize: 12,
                  lineHeight: 1.5,
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: 4 }}>Interpretation:</div>
                <div>{interpretation}</div>
              </div>
            );
          })()}

          <div style={{ fontSize: 11, color: "rgba(0,0,0,0.7)", lineHeight: 1.6 }}>
            <div style={{ marginBottom: 8 }}>
              <b>Lift meaning:</b> Lift &gt; 1 means the pair hits together more than random chance would predict.
            </div>
            <div>
              <b>Phi meaning:</b> Phi measures correlation strength. Positive = move together, negative = move opposite.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
