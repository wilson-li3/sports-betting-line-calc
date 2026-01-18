"""
Data summary script - provides overview of all graph data
"""
from app.db import db
from collections import Counter

def summarize_data():
    """
    Summarize all graph data: nodes, edges, events, pairs
    """
    print("=" * 80)
    print("DATA SUMMARY")
    print("=" * 80)
    
    # 1. Graph Nodes
    print("\n1. GRAPH NODES")
    print("-" * 80)
    nodes = list(db.graph_nodes.find({}))
    node_by_type = Counter(n["type"] for n in nodes if "type" in n)
    
    print(f"  Total nodes: {len(nodes)}")
    for node_type, count in node_by_type.items():
        print(f"    {node_type}: {count}")
    
    # Sample nodes
    if nodes:
        print("\n  Sample event nodes:")
        event_nodes = [n for n in nodes if n.get("type") == "event"][:5]
        for node in event_nodes:
            support = node.get("support", 0)
            print(f"    - {node.get('node_id', 'N/A')}: support={support}")
        
        print("\n  Sample context nodes:")
        context_nodes = [n for n in nodes if n.get("type") == "context"][:5]
        for node in context_nodes:
            support = node.get("support", 0)
            print(f"    - {node.get('node_id', 'N/A')}: support={support}")
        
        print("\n  Sample value nodes:")
        value_nodes = [n for n in nodes if n.get("type") == "value"][:5]
        for node in value_nodes:
            support = node.get("support", 0)
            print(f"    - {node.get('node_id', 'N/A')}: support={support}")
    
    # 2. Graph Edges
    print("\n2. GRAPH EDGES")
    print("-" * 80)
    edges = list(db.graph_edges.find({}))
    edges_by_family = Counter(e["family"] for e in edges if "family" in e)
    
    print(f"  Total edges: {len(edges)}")
    for family, count in edges_by_family.items():
        print(f"    {family}: {count}")
    
    # Sample edges by family
    if edges:
        print("\n  Sample association edges:")
        assoc_edges = [e for e in edges if e.get("family") == "association"][:5]
        for edge in assoc_edges:
            weight = edge.get("weight", 0)
            classification = edge.get("classification", "N/A")
            print(f"    - {edge.get('source', 'N/A')} → {edge.get('target', 'N/A')}: weight={weight:.3f}, class={classification}")
        
        print("\n  Sample context edges:")
        ctx_edges = [e for e in edges if e.get("family") == "context"][:5]
        for edge in ctx_edges:
            weight = edge.get("weight", 0)
            print(f"    - {edge.get('source', 'N/A')} → {edge.get('target', 'N/A')}: weight={weight:.3f}")
        
        print("\n  Sample value edges:")
        value_edges = [e for e in edges if e.get("family") == "value"][:5]
        for edge in value_edges:
            weight = edge.get("weight", 0)
            print(f"    - {edge.get('source', 'N/A')} → {edge.get('target', 'N/A')}: weight={weight:.3f}")
    
    # 3. Event Probabilities
    print("\n3. EVENT PROBABILITIES")
    print("-" * 80)
    event_probs = list(db.event_probs.find({}))
    print(f"  Total events with probabilities: {len(event_probs)}")
    
    if event_probs:
        print("\n  Sample event probabilities (top 10 by support):")
        sorted_probs = sorted(event_probs, key=lambda x: x.get("n", 0), reverse=True)[:10]
        for prob in sorted_probs:
            event = prob.get("event", "N/A")
            n = prob.get("n", 0)
            p_mean = prob.get("p_mean", 0)
            print(f"    - {event}: n={n}, p={p_mean:.3f}")
    
    # 4. Pair Statistics
    print("\n4. PAIR STATISTICS")
    print("-" * 80)
    pairs = list(db.pair_stats.find({}))
    print(f"  Total pairs: {len(pairs)}")
    
    if pairs:
        # Count by type (stack/hedge/neutral based on lift and phi)
        stacks = sum(1 for p in pairs if p.get("lift", 0) > 1.10 and p.get("phi", 0) > 0.10)
        hedges = sum(1 for p in pairs if p.get("lift", 0) < 0.95 and p.get("phi", 0) < -0.10)
        neutral = len(pairs) - stacks - hedges
        
        print(f"    Stacks (lift>1.10, phi>0.10): {stacks}")
        print(f"    Hedges (lift<0.95, phi<-0.10): {hedges}")
        print(f"    Neutral: {neutral}")
        
        print("\n  Sample pairs (top 5 by lift):")
        sorted_pairs = sorted(pairs, key=lambda x: x.get("lift", 0), reverse=True)[:5]
        for pair in sorted_pairs:
            A = pair.get("A", "N/A")
            B = pair.get("B", "N/A")
            lift = pair.get("lift", 0)
            phi = pair.get("phi", 0)
            n = pair.get("n", 0)
            print(f"    - {A} ↔ {B}: lift={lift:.3f}, phi={phi:.3f}, n={n}")
    
    # 5. Raw Events
    print("\n5. RAW EVENTS")
    print("-" * 80)
    events = list(db.events.find({}))
    print(f"  Total game/team events: {len(events)}")
    
    if events:
        # Count unique games
        game_ids = set(e.get("GAME_ID") for e in events if "GAME_ID" in e)
        print(f"  Unique games: {len(game_ids)}")
        
        # Count event fields
        sample_event = events[0] if events else {}
        event_fields = [k for k in sample_event.keys() if k.endswith("_OVER_HIT") or k.endswith("_STRONG_HIT")]
        print(f"  Sample event fields per game: {len(event_fields)}")
        print(f"    Examples: {event_fields[:5]}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    summarize_data()
