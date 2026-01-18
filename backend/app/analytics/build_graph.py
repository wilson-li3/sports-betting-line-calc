"""
Build a large graph of relationships from events.

Creates graph_nodes and graph_edges collections with:
- Nodes: event types, context tags
- Edges: association (lift/phi), context-conditioned, value (margins)
"""

from app.db import db
from app.analytics.compute_pairs import phi_correlation
from app.analytics.estimate_event_probs import beta_quantiles, discover_event_fields
import math
import random

def to_num(x):
    try:
        return float(x) if x is not None else 0.0
    except:
        return 0.0


def compute_confidence(phi: float, n: int) -> float:
    """Compute confidence score: abs(phi) * log10(n)"""
    if n <= 1:
        return 0.0
    return abs(phi) * math.log10(n)


def build_graph_nodes():
    """
    Build graph nodes from event fields and context tags.
    Dynamically discovers all event fields from event_probs.
    """
    print("Building graph nodes...")
    
    # Clear existing nodes
    db.graph_nodes.delete_many({})
    
    events = list(db.events.find({}))
    if not events:
        print("No events found.")
        return []
    
    nodes = []
    node_ids = set()
    
    # Get all event fields from event_probs (dynamically discovered)
    event_probs = list(db.event_probs.find({}))
    event_field_map = {doc["event"]: doc for doc in event_probs}
    
    # If event_probs is empty, fall back to discovering from events
    if not event_field_map:
        discovered_fields = discover_event_fields()
        print(f"Discovered {len(discovered_fields)} event fields from events collection")
        for event_field in discovered_fields:
            event_field_map[event_field] = None
    
    # Create nodes for all discovered event fields
    for event_field in event_field_map.keys():
        node_id = event_field
        if node_id not in node_ids:
            prob_doc = event_field_map.get(event_field)
            nodes.append({
                "node_id": node_id,
                "type": "event",
                "description": event_field.replace("_", " ").title(),
                "p_mean": prob_doc.get("p_mean") if prob_doc else None,
                "p_lo": prob_doc.get("p_lo") if prob_doc else None,
                "p_hi": prob_doc.get("p_hi") if prob_doc else None,
                "support": prob_doc.get("n") if prob_doc else 0,
            })
            node_ids.add(node_id)
    
    # Extract context nodes from events
    for event in events:
        context = event.get("context", {})
        for key, value in context.items():
            if value is not None:
                if key == "pace_bucket":
                    node_id = f"PACE_{value}"
                elif key == "competitive":
                    node_id = f"COMP_{value}"
                elif key == "home":
                    node_id = "HOME" if value else "AWAY"
                else:
                    continue
                
                if node_id not in node_ids:
                    nodes.append({
                        "node_id": node_id,
                        "type": "context",
                        "description": node_id.replace("_", " ").title(),
                        "support": 0,  # Will compute
                    })
                    node_ids.add(node_id)
    
    # Compute support for context nodes
    for node in nodes:
        if node["type"] == "context":
            node_id = node["node_id"]
            count = 0
            for event in events:
                context = event.get("context", {})
                if node_id == "HOME" and context.get("home") == True:
                    count += 1
                elif node_id == "AWAY" and context.get("home") == False:
                    count += 1
                elif node_id.startswith("PACE_") and context.get("pace_bucket") == node_id.replace("PACE_", ""):
                    count += 1
                elif node_id.startswith("COMP_") and context.get("competitive") == node_id.replace("COMP_", ""):
                    count += 1
            node["support"] = count
    
    if nodes:
        db.graph_nodes.insert_many(nodes)
        print(f"Inserted {len(nodes)} graph nodes.")
    
    return nodes


def compute_pair_stats_with_ci(events, A: str, B: str, n_bootstrap: int = 200):
    """
    Compute pair statistics with bootstrap CI (simplified version).
    """
    n = 0
    a = b = ab = 0
    
    for e in events:
        av = e.get(A)
        bv = e.get(B)
        if av is None or bv is None:
            continue
        
        n += 1
        if av == 1:
            a += 1
        if bv == 1:
            b += 1
        if av == 1 and bv == 1:
            ab += 1
    
    if n < 5:
        return None
    
    pA = a / n
    pB = b / n
    pAB = ab / n
    lift = pAB / (pA * pB) if (pA * pB) > 0 else 0.0
    
    b_count = a - ab
    c_count = b - ab
    d_count = n - a - b + ab
    phi = phi_correlation(ab, b_count, c_count, d_count)
    
    # Bootstrap CI (simplified - sample fewer times for speed)
    lift_samples = []
    phi_samples = []
    valid_events = [e for e in events if e.get(A) is not None and e.get(B) is not None]
    
    for _ in range(min(n_bootstrap, 200)):
        resample = [random.choice(valid_events) for _ in range(len(valid_events))]
        n_r = 0
        a_r = b_r = ab_r = 0
        for e in resample:
            av = e.get(A)
            bv = e.get(B)
            if av is None or bv is None:
                continue
            n_r += 1
            if av == 1:
                a_r += 1
            if bv == 1:
                b_r += 1
            if av == 1 and bv == 1:
                ab_r += 1
        
        if n_r > 0:
            pA_r = a_r / n_r
            pB_r = b_r / n_r
            pAB_r = ab_r / n_r
            lift_r = pAB_r / (pA_r * pB_r) if (pA_r * pB_r) > 0 else 0.0
            b_r_count = a_r - ab_r
            c_r_count = b_r - ab_r
            d_r_count = n_r - a_r - b_r + ab_r
            phi_r = phi_correlation(ab_r, b_r_count, c_r_count, d_r_count)
            lift_samples.append(lift_r)
            phi_samples.append(phi_r)
    
    lift_samples.sort()
    phi_samples.sort()
    idx_lo = int(0.025 * len(lift_samples)) if lift_samples else 0
    idx_hi = int(0.975 * len(lift_samples)) if lift_samples else 0
    
    lift_lo = lift_samples[idx_lo] if lift_samples else lift
    lift_hi = lift_samples[idx_hi] if lift_samples else lift
    phi_lo = phi_samples[idx_lo] if phi_samples else phi
    phi_hi = phi_samples[idx_hi] if phi_samples else phi
    
    # Conditional probability P(B|A)
    if a > 0:
        alpha = 1 + ab
        beta = 1 + a - ab
        pBA_mean = alpha / (alpha + beta)
        pBA_lo, pBA_hi = beta_quantiles(alpha, beta, mc_samples=10000)
    else:
        pBA_mean = pBA_lo = pBA_hi = 0.0
    
    return {
        "n": n,
        "lift": lift,
        "lift_lo": lift_lo,
        "lift_hi": lift_hi,
        "phi": phi,
        "phi_lo": phi_lo,
        "phi_hi": phi_hi,
        "pA": pA,
        "pB": pB,
        "pBA_mean": pBA_mean,
        "pBA_lo": pBA_lo,
        "pBA_hi": pBA_hi,
    }


def build_association_edges(min_support: int = 200):
    """
    Build association edges (co-occurrence relationships).
    """
    print("Building association edges...")
    
    events = list(db.events.find({}))
    if not events:
        return []
    
    # Get all event field nodes
    event_nodes = [n["node_id"] for n in db.graph_nodes.find({"type": "event"})]
    
    edges = []
    pairs_checked = set()
    total_pairs = len(event_nodes) * (len(event_nodes) - 1) // 2
    
    print(f"  Computing {total_pairs} potential pairs...")
    
    processed = 0
    for i, A in enumerate(event_nodes):
        for B in event_nodes[i+1:]:
            pair_key = tuple(sorted([A, B]))
            if pair_key in pairs_checked:
                continue
            pairs_checked.add(pair_key)
            
            processed += 1
            if processed % 100 == 0:
                print(f"  Processed {processed}/{total_pairs} pairs...")
            
            stats = compute_pair_stats_with_ci(events, A, B, n_bootstrap=200)
            if stats is None or stats["n"] < min_support:
                continue
            
            # Classification with CI-aware rules
            if stats["lift_lo"] > 1.05 and stats["phi_lo"] > 0:
                edge_type = "STACK"
            elif stats["phi_hi"] < 0 and stats["lift_hi"] < 1.0:
                edge_type = "HEDGE"
            else:
                edge_type = "NEUTRAL"
            
            # Score: confidence-adjusted
            score = (stats["pBA_mean"] - stats["pB"]) * math.log10(stats["n"]) if stats["n"] > 1 else 0.0
            
            edges.append({
                "source": A,
                "target": B,
                "family": "association",
                "weight": score,
                "metrics": {
                    "lift": stats["lift"],
                    "lift_lo": stats["lift_lo"],
                    "lift_hi": stats["lift_hi"],
                    "phi": stats["phi"],
                    "phi_lo": stats["phi_lo"],
                    "phi_hi": stats["phi_hi"],
                    "pBA_mean": stats["pBA_mean"],
                    "pBA_lo": stats["pBA_lo"],
                    "pBA_hi": stats["pBA_hi"],
                },
                "support": stats["n"],
                "classification": edge_type,
                "explain": f"{edge_type} relationship: lift={stats['lift']:.2f} [{stats['lift_lo']:.2f}, {stats['lift_hi']:.2f}], phi={stats['phi']:.2f} [{stats['phi_lo']:.2f}, {stats['phi_hi']:.2f}]",
            })
    
    if edges:
        db.graph_edges.delete_many({"family": "association"})
        db.graph_edges.insert_many(edges)
        print(f"Inserted {len(edges)} association edges.")
    
    return edges


def build_context_edges(min_support: int = 200):
    """
    Build context-conditioned edges.
    """
    print("Building context edges...")
    
    events = list(db.events.find({}))
    if not events:
        return []
    
    context_nodes = [n["node_id"] for n in db.graph_nodes.find({"type": "context"})]
    event_nodes = [n["node_id"] for n in db.graph_nodes.find({"type": "event"})]
    
    edges = []
    
    for ctx_node in context_nodes:
        # Filter events by context
        ctx_events = []
        for e in events:
            context = e.get("context", {})
            ctx_id = ctx_node
            match = False
            if ctx_id == "HOME" and context.get("home") == True:
                match = True
            elif ctx_id == "AWAY" and context.get("home") == False:
                match = True
            elif ctx_id.startswith("PACE_") and context.get("pace_bucket") == ctx_id.replace("PACE_", ""):
                match = True
            elif ctx_id.startswith("COMP_") and context.get("competitive") == ctx_id.replace("COMP_", ""):
                match = True
            
            if match:
                ctx_events.append(e)
        
        if len(ctx_events) < min_support:
            continue
        
        # Compute P(Event|Context) for each event
        for event_node in event_nodes:
            k = sum(1 for e in ctx_events if e.get(event_node) == 1)
            n = len(ctx_events)
            
            if n < min_support:
                continue
            
            # Beta credible interval
            alpha = 1 + k
            beta = 1 + n - k
            p_mean = alpha / (alpha + beta)
            p_lo, p_hi = beta_quantiles(alpha, beta, mc_samples=10000)
            
            # Compare to baseline
            baseline_doc = db.event_probs.find_one({"event": event_node})
            baseline_p = baseline_doc.get("p_mean") if baseline_doc else 0.5
            delta = p_mean - baseline_p
            
            edges.append({
                "source": ctx_node,
                "target": event_node,
                "family": "context",
                "weight": abs(delta) * math.log10(n),
                "metrics": {
                    "p_mean": p_mean,
                    "p_lo": p_lo,
                    "p_hi": p_hi,
                    "baseline_p": baseline_p,
                    "delta": delta,
                },
                "support": n,
                "explain": f"P({event_node}|{ctx_node})={p_mean:.3f} [{p_lo:.3f}, {p_hi:.3f}] vs baseline {baseline_p:.3f} (Δ={delta:+.3f})",
            })
    
    if edges:
        db.graph_edges.delete_many({"family": "context"})
        db.graph_edges.insert_many(edges)
        print(f"Inserted {len(edges)} context edges.")
    
    return edges


def discover_margin_fields():
    """
    Dynamically discover all margin fields (ending in _MARGIN).
    """
    sample_events = list(db.events.find({}).limit(10))
    if not sample_events:
        return []
    
    margin_fields = set()
    for event in sample_events:
        for key in event.keys():
            if key.endswith("_MARGIN"):
                margin_fields.add(key)
    
    return sorted(list(margin_fields))


def build_value_edges(min_support: int = 200):
    """
    Build value edges from margins (EV proxy).
    Dynamically discovers all margin fields.
    """
    print("Building value edges...")
    
    events = list(db.events.find({}))
    if not events:
        return []
    
    # Discover all margin fields dynamically
    margin_patterns = discover_margin_fields()
    print(f"  Discovered {len(margin_patterns)} margin fields")
    
    edges = []
    
    for pattern in margin_patterns:
        margins = [to_num(e.get(pattern)) for e in events if e.get(pattern) is not None]
        
        if len(margins) < min_support:
            continue
        
        # Bootstrap CI for mean margin
        margin_samples = []
        for _ in range(200):
            resample = [random.choice(margins) for _ in range(len(margins))]
            margin_samples.append(sum(resample) / len(resample))
        
        margin_samples.sort()
        margin_mean = sum(margins) / len(margins)
        margin_lo = margin_samples[int(0.025 * len(margin_samples))]
        margin_hi = margin_samples[int(0.975 * len(margin_samples))]
        
        # Create value node
        value_node_id = f"VALUE_{pattern.replace('_MARGIN', '')}"
        
        # Check if value node exists, create if not
        if db.graph_nodes.count_documents({"node_id": value_node_id}) == 0:
            db.graph_nodes.insert_one({
                "node_id": value_node_id,
                "type": "value",
                "description": f"Positive value for {pattern.replace('_MARGIN', '')}",
                "support": len(margins),
            })
        
        # Edge from event to value
        event_node_id = pattern.replace("_MARGIN", "_OVER_HIT")
        if db.graph_nodes.count_documents({"node_id": event_node_id}) > 0:
            edges.append({
                "source": event_node_id,
                "target": value_node_id,
                "family": "value",
                "weight": max(0, margin_mean) * math.log10(len(margins)),
                "metrics": {
                    "margin_mean": margin_mean,
                    "margin_lo": margin_lo,
                    "margin_hi": margin_hi,
                },
                "support": len(margins),
                "explain": f"Mean margin: {margin_mean:.2f} [{margin_lo:.2f}, {margin_hi:.2f}]",
            })
    
    if edges:
        db.graph_edges.delete_many({"family": "value"})
        db.graph_edges.insert_many(edges)
        print(f"Inserted {len(edges)} value edges.")
    
    return edges


def build_graph(min_support: int = 200):
    """
    Build complete graph: nodes and all edge families.
    """
    print("=" * 60)
    print("BUILDING RELATIONSHIP GRAPH")
    print("=" * 60)
    
    nodes = build_graph_nodes()
    assoc_edges = build_association_edges(min_support=min_support)
    ctx_edges = build_context_edges(min_support=min_support)
    val_edges = build_value_edges(min_support=min_support)
    
    print("\n" + "=" * 60)
    print("GRAPH BUILD COMPLETE")
    print("=" * 60)
    print(f"Nodes: {len(nodes)}")
    print(f"Association edges: {len(assoc_edges)}")
    print(f"Context edges: {len(ctx_edges)}")
    print(f"Value edges: {len(val_edges)}")
    print(f"Total edges: {len(assoc_edges) + len(ctx_edges) + len(val_edges)}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build relationship graph")
    parser.add_argument("--min-support", type=int, default=200, help="Minimum support for edges")
    args = parser.parse_args()
    build_graph(min_support=args.min_support)
