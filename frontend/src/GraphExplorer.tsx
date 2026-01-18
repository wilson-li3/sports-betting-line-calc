import { useState, useEffect } from "react";
import ForceGraph2D from "react-force-graph-2d";

type GraphNode = {
  id: string;
  type: "event" | "context" | "value";
  description: string;
  support: number;
};

type GraphLink = {
  source: string;
  target: string;
  family: "association" | "context" | "directional" | "value";
  weight: number;
  metrics: Record<string, any>;
  support: number;
  explain: string;
  classification?: string;
};

type GraphResponse = {
  nodes: GraphNode[];
  links: GraphLink[];
  meta: {
    min_support: number;
    max_nodes: number;
    families: string[];
    node_count: number;
    link_count: number;
  };
};

function toPretty(id: string): string {
  return id.replace(/_HIT$/, "").replace(/_MARGIN$/, "").replace(/_/g, " ");
}

export default function GraphExplorer() {
  const [minSupport, setMinSupport] = useState(200);
  const [maxNodes, setMaxNodes] = useState(200);
  const [selectedFamilies, setSelectedFamilies] = useState<string[]>(["association", "context", "value"]);
  const [graphData, setGraphData] = useState<GraphResponse | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedLink, setSelectedLink] = useState<GraphLink | null>(null);
  const [dataSource, setDataSource] = useState<"LIVE" | "MOCK">("MOCK");

  // Fetch graph data
  useEffect(() => {
    const familiesParam = selectedFamilies.join(",");
    const params = new URLSearchParams({
      min_support: minSupport.toString(),
      max_nodes: maxNodes.toString(),
      families: familiesParam,
    });

    fetch(`http://127.0.0.1:8000/graph?${params}`)
      .then((res) => {
        if (!res.ok) {
          throw new Error("Failed to fetch graph");
        }
        return res.json();
      })
      .then((data: GraphResponse) => {
        setGraphData(data);
        setDataSource("LIVE");
      })
      .catch((err) => {
        console.warn("Failed to fetch graph:", err);
        setDataSource("MOCK");
      });
  }, [minSupport, maxNodes, selectedFamilies]);

  const handleNodeClick = (node: any) => {
    const foundNode = graphData?.nodes.find((n) => n.id === node.id);
    setSelectedNode(foundNode || null);
    setSelectedLink(null);
  };

  const handleLinkClick = (link: any) => {
    const foundLink = graphData?.links.find(
      (l) => l.source === link.source.id && l.target === link.target.id
    );
    setSelectedLink(foundLink || null);
    setSelectedNode(null);
  };

  const toggleFamily = (family: string) => {
    if (selectedFamilies.includes(family)) {
      setSelectedFamilies(selectedFamilies.filter((f) => f !== family));
    } else {
      setSelectedFamilies([...selectedFamilies, family]);
    }
  };

  if (!graphData) {
    return (
      <div style={{ padding: 20, textAlign: "center" }}>
        <div>Loading graph...</div>
      </div>
    );
  }

  // Color encoding
  const getNodeColor = (node: GraphNode) => {
    if (node.type === "event") return "#4A90E2";
    if (node.type === "context") return "#7B68EE";
    if (node.type === "value") return "#FFD700";
    return "#888";
  };

  const getLinkColor = (link: GraphLink) => {
    if (link.family === "association") {
      if (link.classification === "STACK") return "rgba(0, 150, 0, 0.7)";
      if (link.classification === "HEDGE") return "rgba(200, 0, 0, 0.7)";
      return "rgba(120, 120, 120, 0.5)";
    }
    if (link.family === "context") return "rgba(123, 104, 238, 0.6)";
    if (link.family === "value") return "rgba(255, 215, 0, 0.7)";
    return "rgba(100, 100, 100, 0.4)";
  };

  return (
    <div style={{ height: "100vh", width: "100vw", display: "flex", overflow: "hidden" }}>
      {/* Left Sidebar - Controls */}
      <div
        style={{
          width: 300,
          borderRight: "1px solid rgba(0,0,0,0.1)",
          padding: "16px",
          background: "#f8f9fa",
          fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
          overflowY: "auto",
        }}
      >
        <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 16 }}>
          Graph Explorer
        </div>

        {/* Data Source Badge */}
        <div
          style={{
            display: "inline-block",
            padding: "4px 8px",
            borderRadius: 6,
            fontSize: 11,
            fontWeight: 600,
            marginBottom: 16,
            background: dataSource === "LIVE" ? "rgba(0, 150, 0, 0.15)" : "rgba(200, 140, 0, 0.15)",
            color: dataSource === "LIVE" ? "rgba(0, 100, 0, 0.9)" : "rgba(140, 100, 0, 0.9)",
            border: `1px solid ${dataSource === "LIVE" ? "rgba(0, 150, 0, 0.3)" : "rgba(200, 140, 0, 0.3)"}`,
          }}
        >
          DATA: {dataSource}
        </div>

        {/* Min Support */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", fontSize: 12, marginBottom: 4, fontWeight: 500 }}>
            Min support: {minSupport}
          </label>
          <input
            type="range"
            min="50"
            max="500"
            value={minSupport}
            onChange={(e) => setMinSupport(Number(e.target.value))}
            style={{ width: "100%" }}
          />
        </div>

        {/* Max Nodes */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", fontSize: 12, marginBottom: 4, fontWeight: 500 }}>
            Max nodes: {maxNodes}
          </label>
          <input
            type="range"
            min="50"
            max="500"
            value={maxNodes}
            onChange={(e) => setMaxNodes(Number(e.target.value))}
            style={{ width: "100%" }}
          />
        </div>

        {/* Edge Families */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 8 }}>Edge families:</div>
          {["association", "context", "value"].map((family) => (
            <label key={family} style={{ display: "flex", alignItems: "center", marginBottom: 6, fontSize: 12 }}>
              <input
                type="checkbox"
                checked={selectedFamilies.includes(family)}
                onChange={() => toggleFamily(family)}
                style={{ marginRight: 8 }}
              />
              {family.charAt(0).toUpperCase() + family.slice(1)}
            </label>
          ))}
        </div>

        {/* Stats */}
        <div style={{ fontSize: 11, color: "rgba(0,0,0,0.7)", marginTop: 16 }}>
          <div>Nodes: {graphData.meta.node_count}</div>
          <div>Links: {graphData.meta.link_count}</div>
        </div>
      </div>

      {/* Center Graph */}
      <div style={{ flex: 1, position: "relative" }}>
        <ForceGraph2D
          graphData={graphData}
          nodeLabel={(n: any) => toPretty(n.id)}
          linkLabel={(l: any) => l.explain || `${l.source.id} → ${l.target.id}`}
          onNodeClick={handleNodeClick}
          onLinkClick={handleLinkClick}
          nodeColor={(n: any) => getNodeColor(n)}
          nodeVal={(n: any) => Math.sqrt(n.support || 1) * 2}
          linkColor={getLinkColor}
          linkWidth={(l: any) => Math.max(1, Math.abs(l.weight) / 10)}
          linkDirectionalArrowLength={6}
          linkDirectionalArrowRelPos={1}
        />
      </div>

      {/* Right Details Panel */}
      {(selectedNode || selectedLink) && (
        <div
          style={{
            width: 350,
            borderLeft: "1px solid rgba(0,0,0,0.1)",
            padding: "16px",
            background: "#f8f9fa",
            fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
            overflowY: "auto",
          }}
        >
          {selectedNode && (
            <>
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 16 }}>
                Node Details
              </div>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                  {toPretty(selectedNode.id)}
                </div>
                <div style={{ fontSize: 11, color: "rgba(0,0,0,0.6)" }}>
                  Type: {selectedNode.type}
                </div>
              </div>
              <div style={{ fontSize: 12, marginBottom: 12 }}>
                <div><b>Support:</b> {selectedNode.support}</div>
                {selectedNode.p_mean !== undefined && (
                  <>
                    <div><b>Probability:</b> {selectedNode.p_mean.toFixed(3)}</div>
                    {selectedNode.p_lo !== undefined && selectedNode.p_hi !== undefined && (
                      <div style={{ fontSize: 11, color: "rgba(0,0,0,0.6)" }}>
                        [{selectedNode.p_lo.toFixed(3)}, {selectedNode.p_hi.toFixed(3)}]
                      </div>
                    )}
                  </>
                )}
              </div>
              <div style={{ fontSize: 11, color: "rgba(0,0,0,0.7)" }}>
                {selectedNode.description}
              </div>
            </>
          )}

          {selectedLink && (
            <>
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 16 }}>
                Edge Details
              </div>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                  {toPretty(selectedLink.source)} → {toPretty(selectedLink.target)}
                </div>
                <div style={{ fontSize: 11, color: "rgba(0,0,0,0.6)" }}>
                  Family: {selectedLink.family}
                </div>
              </div>
              <div style={{ fontSize: 12, marginBottom: 12 }}>
                <div><b>Weight:</b> {selectedLink.weight.toFixed(3)}</div>
                <div><b>Support:</b> {selectedLink.support}</div>
                {selectedLink.classification && (
                  <div><b>Classification:</b> {selectedLink.classification}</div>
                )}
              </div>
              {selectedLink.metrics && (
                <div style={{ fontSize: 11, marginBottom: 12, padding: 8, background: "rgba(0,0,0,0.05)", borderRadius: 4 }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>Metrics:</div>
                  {Object.entries(selectedLink.metrics).map(([key, value]) => (
                    <div key={key} style={{ marginBottom: 2 }}>
                      {key}: {typeof value === "number" ? value.toFixed(3) : String(value)}
                    </div>
                  ))}
                </div>
              )}
              <div style={{ fontSize: 11, color: "rgba(0,0,0,0.7)", lineHeight: 1.5 }}>
                {selectedLink.explain}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
