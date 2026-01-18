import { useState, useEffect, useRef } from "react";
import ForceGraph2D from "react-force-graph-2d";
import * as d3Force from "d3-force";

type GraphNode = {
  id: string;
  type: "event" | "context" | "value";
  description: string;
  support: number;
  x?: number; // Added by react-force-graph-2d during simulation
  y?: number; // Added by react-force-graph-2d during simulation
  p_mean?: number; // Probability mean (optional - for event nodes)
  p_lo?: number; // Probability lower bound (optional)
  p_hi?: number; // Probability upper bound (optional)
};

type GraphLink = {
  source: string | GraphNode; // Can be string (from API) or node object (in force graph)
  target: string | GraphNode; // Can be string (from API) or node object (in force graph)
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
  const [canvasSize, setCanvasSize] = useState({ width: window.innerWidth, height: window.innerHeight });
  const [spread, setSpread] = useState(3);
  const [hasInitialized, setHasInitialized] = useState(false);
  const [showDebugLabels, setShowDebugLabels] = useState(false);
  const [showAllLabels, setShowAllLabels] = useState(false);
  const [edgesPerNode, setEdgesPerNode] = useState(3);
  const [radialGrouping, setRadialGrouping] = useState(true);
  const [filteredLinks, setFilteredLinks] = useState<GraphLink[]>([]);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const fgRef = useRef<any>(null);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      setCanvasSize({ width: window.innerWidth, height: window.innerHeight });
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

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
        // Filter edges before setting
        const filtered = filterEdges(data.nodes, data.links, edgesPerNode);
        setFilteredLinks(filtered);
        setDataSource("LIVE");
        // Set initial view - center and zoom in (no zoomToFit which shrinks)
        if (!hasInitialized && fgRef.current) {
          setTimeout(() => {
            fgRef.current?.centerAt(0, 0, 0);
            fgRef.current?.zoom(2.2, 0);
            setHasInitialized(true);
          }, 300);
        }
      })
      .catch((err) => {
        console.warn("Failed to fetch graph:", err);
        setDataSource("MOCK");
      });
  }, [minSupport, maxNodes, selectedFamilies, edgesPerNode]);

  // Re-filter edges when edgesPerNode changes
  useEffect(() => {
    if (graphData) {
      const filtered = filterEdges(graphData.nodes, graphData.links, edgesPerNode);
      setFilteredLinks(filtered);
    }
  }, [edgesPerNode, graphData]);

  const handleNodeClick = (node: any) => {
    const foundNode = graphData?.nodes.find((n) => n.id === node.id);
    setSelectedNode(foundNode || null);
    setSelectedLink(null);
  };

  const handleLinkClick = (link: any) => {
    // Normalize link source/target to strings for comparison
    const linkSourceId = typeof link.source === "string" ? link.source : link.source.id;
    const linkTargetId = typeof link.target === "string" ? link.target : link.target.id;
    
    const foundLink = graphData?.links.find(
      (l) => {
        const lSource = typeof l.source === "string" ? l.source : l.source.id;
        const lTarget = typeof l.target === "string" ? l.target : l.target.id;
        return lSource === linkSourceId && lTarget === linkTargetId;
      }
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

  const resetView = () => {
    if (fgRef.current) {
      fgRef.current.centerAt(0, 0, 600);
      fgRef.current.zoom(2.2, 600);
    }
  };

  // Calculate force parameters based on spread (1-5)
  const getForceParams = () => {
    const charge = -1500 * spread * spread; // spread=3 -> -13500
    const linkDistance = 220 * spread; // spread=3 -> 660
    return { charge, linkDistance };
  };

  // Hard cap node radius - small fixed sizes to prevent layout issues
  const getNodeRadius = (node: GraphNode): number => {
    if (node.type === "event") {
      return 8;
    } else if (node.type === "context") {
      return 6;
    } else { // value
      return 6;
    }
  };

  // Filter edges to prevent hairball - keep top K per node (union of edges from all nodes)
  const filterEdges = (nodes: GraphNode[], links: GraphLink[], maxPerNode: number = 3): GraphLink[] => {
    // Build adjacency list for both directions
    const edgesByNode: Record<string, GraphLink[]> = {};
    links.forEach(link => {
      const source = typeof link.source === "string" ? link.source : link.source.id;
      const target = typeof link.target === "string" ? link.target : link.target.id;
      
      if (!edgesByNode[source]) edgesByNode[source] = [];
      if (!edgesByNode[target]) edgesByNode[target] = [];
      
      edgesByNode[source].push(link);
      edgesByNode[target].push(link);
    });

    // Keep top K edges per node (by absolute weight)
    const keptLinks = new Set<string>(); // Use Set to avoid duplicates
    Object.keys(edgesByNode).forEach(nodeId => {
      const edges = edgesByNode[nodeId];
      edges.sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight));
      edges.slice(0, maxPerNode).forEach(link => {
        const source = typeof link.source === "string" ? link.source : link.source.id;
        const target = typeof link.target === "string" ? link.target : link.target.id;
        keptLinks.add(`${source}|${target}`);
      });
    });

    // Return union of kept edges
    const filtered = links.filter(link => {
      const source = typeof link.source === "string" ? link.source : link.source.id;
      const target = typeof link.target === "string" ? link.target : link.target.id;
      return keptLinks.has(`${source}|${target}`) || keptLinks.has(`${target}|${source}`);
    }).filter(link => Math.abs(link.weight) > 0.01);
    
    // Cap total edges globally
    const MAX_EDGES = 450;
    return filtered.slice(0, MAX_EDGES);
  };

  // Get 1-hop neighborhood for selected node
  const getNeighborhoodNodes = (nodeId: string): Set<string> => {
    const neighborhood = new Set<string>([nodeId]);
    filteredLinks.forEach(link => {
      const source = typeof link.source === "string" ? link.source : link.source.id;
      const target = typeof link.target === "string" ? link.target : link.target.id;
      if (source === nodeId) neighborhood.add(target);
      if (target === nodeId) neighborhood.add(source);
    });
    return neighborhood;
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
    const source = typeof link.source === "string" ? link.source : link.source.id;
    const target = typeof link.target === "string" ? link.target : link.target.id;
    
    // Edge fade/focus mode
    let opacity = 1; // Default low opacity (faint)
    
    // If node selected, highlight neighborhood
    if (selectedNode) {
      const neighborhood = getNeighborhoodNodes(selectedNode.id);
      if (neighborhood.has(source) && neighborhood.has(target)) {
        opacity = 0.9; // Highlight neighborhood edges
      } else {
        opacity = 0.05; // Fade everything else
      }
    }
    
    // If link selected, highlight it and endpoints
    if (selectedLink) {
      const selectedSource = typeof selectedLink.source === "string" ? selectedLink.source : selectedLink.source.id;
      const selectedTarget = typeof selectedLink.target === "string" ? selectedLink.target : selectedLink.target.id;
      if ((source === selectedSource && target === selectedTarget) || 
          (source === selectedTarget && target === selectedSource)) {
        opacity = 0.9;
      } else if (source === selectedSource || source === selectedTarget || 
                 target === selectedSource || target === selectedTarget) {
        opacity = 0.4;
      } else {
        opacity = 0.05;
      }
    }
    
    // Base color by family
    let baseColor = "120, 120, 120";
    if (link.family === "association") {
      if (link.classification === "STACK") baseColor = "0, 150, 0";
      else if (link.classification === "HEDGE") baseColor = "200, 0, 0";
      else baseColor = "120, 120, 120";
    } else if (link.family === "context") {
      baseColor = "123, 104, 238";
    } else if (link.family === "value") {
      baseColor = "255, 215, 0";
    }
    
    return `rgba(${baseColor}, ${opacity})`;
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

        {/* Spread Control */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", fontSize: 12, marginBottom: 4, fontWeight: 500 }}>
            Spread: {spread.toFixed(1)}
          </label>
          <input
            type="range"
            min="1"
            max="5"
            step="0.1"
            value={spread}
            onChange={(e) => setSpread(Number(e.target.value))}
            style={{ width: "100%" }}
          />
          <div style={{ fontSize: 10, color: "rgba(0,0,0,0.5)", marginTop: 2 }}>
            Controls node spacing
          </div>
        </div>

        {/* Edges per Node Slider */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", fontSize: 12, marginBottom: 4, fontWeight: 500 }}>
            Edges per node: {edgesPerNode}
          </label>
          <input
            type="range"
            min="1"
            max="10"
            value={edgesPerNode}
            onChange={(e) => setEdgesPerNode(Number(e.target.value))}
            style={{ width: "100%" }}
          />
          <div style={{ fontSize: 10, color: "rgba(0,0,0,0.5)", marginTop: 2 }}>
            Controls edge density
          </div>
        </div>

        {/* Radial Grouping Toggle */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "flex", alignItems: "center", fontSize: 12 }}>
            <input
              type="checkbox"
              checked={radialGrouping}
              onChange={(e) => setRadialGrouping(e.target.checked)}
              style={{ marginRight: 8 }}
            />
            Radial grouping
          </label>
        </div>

        {/* Show All Labels Toggle */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "flex", alignItems: "center", fontSize: 12 }}>
            <input
              type="checkbox"
              checked={showAllLabels}
              onChange={(e) => setShowAllLabels(e.target.checked)}
              style={{ marginRight: 8 }}
            />
            Show all labels
          </label>
        </div>

        {/* Debug Mode Toggle */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "flex", alignItems: "center", fontSize: 12 }}>
            <input
              type="checkbox"
              checked={showDebugLabels}
              onChange={(e) => setShowDebugLabels(e.target.checked)}
              style={{ marginRight: 8 }}
            />
            Show node types (debug)
          </label>
        </div>

        {/* Reset View Button */}
        <button
          onClick={resetView}
          style={{
            width: "100%",
            padding: "8px",
            marginBottom: 16,
            backgroundColor: "#4A90E2",
            color: "white",
            border: "none",
            borderRadius: 4,
            fontSize: 12,
            fontWeight: 500,
            cursor: "pointer",
          }}
        >
          Reset View
        </button>

        {/* Stats */}
        <div style={{ fontSize: 11, color: "rgba(0,0,0,0.7)", marginTop: 16 }}>
          <div>Nodes: {graphData.meta.node_count}</div>
          <div>Links: {graphData.meta.link_count}</div>
        </div>
      </div>

      {/* Center Graph */}
      <div style={{ flex: 1, position: "relative" }}>
        <ForceGraph2D
          ref={fgRef}
          graphData={{
            nodes: graphData.nodes,
            links: filteredLinks,
          }}
          width={canvasSize.width - (selectedNode || selectedLink ? 650 : 300)}
          height={canvasSize.height}
          nodeLabel={(n: any) => toPretty(n.id)}
          linkLabel={(l: any) => {
            const sourceId = typeof l.source === "string" ? l.source : l.source.id;
            const targetId = typeof l.target === "string" ? l.target : l.target.id;
            return l.explain || `${sourceId} → ${targetId}`;
          }}
          onNodeClick={handleNodeClick}
          onNodeHover={(node: any) => setHoveredNode(node ? node.id : null)}
          onLinkClick={handleLinkClick}
          nodeColor={(n: any) => getNodeColor(n)}
          nodeVal={(n: any) => {
            const node = graphData.nodes.find(nd => nd.id === n.id) || n;
            return getNodeRadius(node);
          }}
          linkColor={getLinkColor}
          linkWidth={(l: any) => Math.max(1, Math.abs(l.weight) / 10)}
          linkDirectionalArrowLength={6}
          linkDirectionalArrowRelPos={1}
          {...({
            // D3 force configuration - balanced forces to prevent string layout
            d3Force: (simulation: any) => {
              const { charge, linkDistance } = getForceParams();
              
              // Charge force
              simulation.force("charge", d3Force.forceManyBody().strength(charge));
              
              // Link force bound to filteredLinks with low strength
              const linkForce = d3Force.forceLink(filteredLinks as any)
                .id((d: any) => d.id)
                .distance(linkDistance)
                .strength(0.03);
              simulation.force("link", linkForce);
              
              // ForceX and forceY to anchor nodes near center (prevents string layout) - reduced strength
              simulation.force("x", d3Force.forceX(0).strength(0.03));
              simulation.force("y", d3Force.forceY(0).strength(0.03));
              
              // Very weak centering force (or none)
              simulation.force("center", d3Force.forceCenter(0, 0).strength(0.01));
              
              // Radial grouping by type (galaxy layout) - only if toggle is ON
              if (radialGrouping) {
                simulation.force("radial", d3Force.forceRadial((node: any) => {
                  const nodeData = graphData.nodes.find((n: GraphNode) => n.id === node.id);
                  if (!nodeData) return 150;
                  if (nodeData.type === "event") return 150;
                  if (nodeData.type === "context") return 320;
                  return 480; // value
                }).strength(0.05)); // Reduced strength to prevent continuous movement
              } else {
                // Remove radial force if toggle is OFF
                simulation.force("radial", null);
              }
              
              // Collision force with small padding
              simulation.force("collide", d3Force.forceCollide()
                .radius((node: any) => {
                  const nodeData = graphData.nodes.find((n: GraphNode) => n.id === node.id);
                  return nodeData ? getNodeRadius(nodeData) + 4 : 8; // Small padding
                })
                .strength(0.7)
                .iterations(2)
              );
              
              // Reheat simulation when forces change
              simulation.alpha(1).restart();
            }
          } as any)}
          cooldownTicks={600}
          cooldownAlpha={0.02}
          cooldownAlphaMin={0.01}
          warmupTicks={200}
          // Custom node rendering with conditional labels
          nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
            const nodeData = graphData.nodes.find((n: GraphNode) => n.id === node.id) || node;
            const nodeId = nodeData.id || node.id;
            const nodeRadius = getNodeRadius(nodeData);
            
            // Draw node circle always
            ctx.beginPath();
            ctx.arc(node.x!, node.y!, nodeRadius, 0, 2 * Math.PI);
            ctx.fillStyle = getNodeColor(nodeData);
            ctx.fill();
            
            // Label rules: only show if:
            // 1. Show all labels toggle is ON AND zoom >= 1.6
            // 2. OR node is hovered/selected
            const shouldShowLabel = 
              (showAllLabels && globalScale >= 1.6) ||
              hoveredNode === nodeId ||
              selectedNode?.id === nodeId ||
              (selectedNode && getNeighborhoodNodes(selectedNode.id).has(nodeId));
            
            if (shouldShowLabel && globalScale >= 1.6) {
              let label = toPretty(nodeId);
              
              // Debug mode: show node type
              if (showDebugLabels) {
                label = `${label} [${nodeData.type || "unknown"}]`;
              }
              
              const fontSize = 11 / globalScale;
              ctx.font = `${fontSize}px Sans-Serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "middle";
              
              // Draw label offset above node
              const labelY = (node.y || 0) - nodeRadius - 18;
              ctx.fillStyle = "#333";
              ctx.fillText(label, node.x!, labelY);
            }
          }}
          nodeCanvasObjectMode={() => "replace"} // Use custom rendering instead of default
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
                  {toPretty(typeof selectedLink.source === "string" ? selectedLink.source : selectedLink.source.id)} → {toPretty(typeof selectedLink.target === "string" ? selectedLink.target : selectedLink.target.id)}
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
