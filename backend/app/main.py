from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from app.db import db
from app.analytics.ev_utils import american_to_implied_prob, compute_ev, compute_joint_ev
import math
import json
import csv
import io
import os
from pathlib import Path
from typing import Literal, Optional, List, Dict, Any

# Import ML dashboard API functions
try:
    from app.ml_api import (
        get_ml_metrics, get_predictions, get_calibration, get_ablation,
        get_deciles, get_picks_summary, get_coefficients, get_timeframe, get_picks, get_future_games
    )
    ML_API_AVAILABLE = True
except ImportError:
    ML_API_AVAILABLE = False

# Create FastAPI app instance
app = FastAPI()

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/pairs")
def get_pairs():
    """
    GET endpoint that returns all documents from the MongoDB collection 'pair_stats'.
    Excludes MongoDB's _id field and returns data in the expected format.
    """
    # Fetch all documents from pair_stats collection
    pairs_cursor = db.pair_stats.find({})
    
    # Convert to list and exclude _id field
    pairs_list = []
    for doc in pairs_cursor:
        # Create a new dict without _id
        pair_doc = {
            "A": doc.get("A"),
            "B": doc.get("B"),
            "lift": doc.get("lift"),
            "phi": doc.get("phi"),
            "n": doc.get("n"),
        }
        pairs_list.append(pair_doc)
    
    return {"pairs": pairs_list}


def classify_pair(lift: float, phi: float) -> str:
    """
    Classify a pair as STACK, HEDGE, or NEUTRAL.
    STACK: lift > 1.10 AND phi > 0.10
    HEDGE: lift < 0.95 AND phi < -0.10
    NEUTRAL: everything else
    """
    if lift > 1.10 and phi > 0.10:
        return "stack"
    elif lift < 0.95 and phi < -0.10:
        return "hedge"
    else:
        return "neutral"


def compute_confidence(phi: float, n: int) -> float:
    """
    Compute confidence score: abs(phi) * log10(n)
    Returns 0 if n <= 1
    """
    if n <= 1:
        return 0.0
    return abs(phi) * math.log10(n)


@app.get("/pairs/explorer")
def get_pairs_explorer(
    min_n: int = Query(50, ge=1, description="Minimum sample size"),
    kind: Literal["stack", "hedge", "neutral", "all"] = Query("all", description="Filter by relationship type"),
    sort: Literal["lift", "abs_phi", "confidence"] = Query("confidence", description="Sort by field"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results")
):
    """
    GET endpoint for pairs explorer with filtering and sorting.
    Returns filtered and sorted pair_stats documents.
    """
    # Fetch all documents from pair_stats collection
    pairs_cursor = db.pair_stats.find({})
    
    # Convert to list with computed confidence and classification
    pairs_list = []
    for doc in pairs_cursor:
        n = doc.get("n", 0)
        lift = doc.get("lift", 0.0)
        phi = doc.get("phi", 0.0)
        
        # Filter by min_n
        if n < min_n:
            continue
        
        # Compute confidence and classify
        confidence = compute_confidence(phi, n)
        pair_kind = classify_pair(lift, phi)
        
        # Filter by kind
        if kind != "all" and pair_kind != kind:
            continue
        
        # Create pair doc without _id (include CI fields if present)
        pair_doc = {
            "A": doc.get("A"),
            "B": doc.get("B"),
            "n": n,
            "lift": lift,
            "phi": phi,
            "confidence": confidence,
            "pair": doc.get("pair", f"{doc.get('A')} ↔ {doc.get('B')}"),
        }
        
        # Include uncertainty fields if present
        if "lift_lo" in doc:
            pair_doc["lift_lo"] = doc.get("lift_lo")
        if "lift_hi" in doc:
            pair_doc["lift_hi"] = doc.get("lift_hi")
        if "phi_lo" in doc:
            pair_doc["phi_lo"] = doc.get("phi_lo")
        if "phi_hi" in doc:
            pair_doc["phi_hi"] = doc.get("phi_hi")
        if "pBA_mean" in doc:
            pair_doc["pBA_mean"] = doc.get("pBA_mean")
        if "pBA_lo" in doc:
            pair_doc["pBA_lo"] = doc.get("pBA_lo")
        if "pBA_hi" in doc:
            pair_doc["pBA_hi"] = doc.get("pBA_hi")
        
        pairs_list.append(pair_doc)
    
    # Sort by requested field
    if sort == "lift":
        pairs_list.sort(key=lambda x: x["lift"], reverse=True)
    elif sort == "abs_phi":
        pairs_list.sort(key=lambda x: abs(x["phi"]), reverse=True)
    else:  # confidence
        pairs_list.sort(key=lambda x: x["confidence"], reverse=True)
    
    # Apply limit
    pairs_list = pairs_list[:limit]
    
    return {
        "meta": {
            "min_n": min_n,
            "kind": kind,
            "sort": sort,
            "limit": limit,
            "count": len(pairs_list),
        },
        "pairs": pairs_list,
    }


@app.get("/pairs/summary")
def get_pairs_summary():
    """
    GET endpoint that returns summary statistics for pair_stats collection.
    """
    # Fetch all documents
    pairs_cursor = db.pair_stats.find({})
    
    total = 0
    n_values = []
    stacks = 0
    hedges = 0
    neutral = 0
    
    for doc in pairs_cursor:
        total += 1
        n = doc.get("n", 0)
        lift = doc.get("lift", 0.0)
        phi = doc.get("phi", 0.0)
        
        n_values.append(n)
        pair_kind = classify_pair(lift, phi)
        
        if pair_kind == "stack":
            stacks += 1
        elif pair_kind == "hedge":
            hedges += 1
        else:
            neutral += 1
    
    # Compute n statistics
    n_min = min(n_values) if n_values else 0
    n_max = max(n_values) if n_values else 0
    
    # Compute median
    n_median = 0
    if n_values:
        sorted_n = sorted(n_values)
        mid = len(sorted_n) // 2
        if len(sorted_n) % 2 == 0:
            n_median = (sorted_n[mid - 1] + sorted_n[mid]) / 2
        else:
            n_median = sorted_n[mid]
    
    return {
        "total": total,
        "stacks": stacks,
        "hedges": hedges,
        "neutral": neutral,
        "n_stats": {
            "min": n_min,
            "median": n_median,
            "max": n_max,
        },
    }


@app.get("/events/probs")
def get_events_probs():
    """
    GET endpoint that returns event probabilities with credible intervals.
    Returns event_probs documents sorted by n descending.
    """
    events_cursor = db.event_probs.find({}).sort("n", -1)
    
    events_list = []
    for doc in events_cursor:
        event_doc = {
            "event": doc.get("event"),
            "n": doc.get("n"),
            "k": doc.get("k"),
            "p_mean": doc.get("p_mean"),
            "p_lo": doc.get("p_lo"),
            "p_hi": doc.get("p_hi"),
        }
        events_list.append(event_doc)
    
    return {"events": events_list}


@app.get("/recommendations")
def get_recommendations(
    min_n: int = Query(100, ge=1, description="Minimum sample size"),
    limit: int = Query(25, ge=1, le=100, description="Maximum number of recommendations per category")
):
    """
    GET endpoint that returns ranked stack and hedge candidates based on probabilities and uncertainty.
    This does NOT output betting picks - only ranked candidates for analysis.
    """
    pairs_cursor = db.pair_stats.find({})
    
    stacks = []
    hedges = []
    
    for doc in pairs_cursor:
        n = doc.get("n", 0)
        if n < min_n:
            continue
        
        lift = doc.get("lift", 0.0)
        lift_lo = doc.get("lift_lo")
        lift_hi = doc.get("lift_hi")
        phi = doc.get("phi", 0.0)
        phi_lo = doc.get("phi_lo")
        phi_hi = doc.get("phi_hi")
        pB = doc.get("pB", 0.0)
        pBA_mean = doc.get("pBA_mean")
        pBA_lo = doc.get("pBA_lo")
        pBA_hi = doc.get("pBA_hi")
        
        # Stack candidate filter: n >= min_n, lift_lo > 1.0, phi > 0
        if lift_lo is not None and lift_lo > 1.0 and phi > 0:
            # Stack score: (pBA_mean - pB) * log10(n)
            if pBA_mean is not None and pB > 0:
                score = (pBA_mean - pB) * math.log10(n) if n > 1 else 0.0
            else:
                score = lift * math.log10(n) if n > 1 else 0.0
            
            reason = "Stack candidate because lift_lo > 1 and phi > 0."
            if pBA_mean is not None and pBA_lo is not None and pBA_hi is not None:
                reason += f" P(B|A)={pBA_mean:.3f} [{pBA_lo:.3f}, {pBA_hi:.3f}] vs baseline P(B)={pB:.3f}."
            
            stacks.append({
                "A": doc.get("A"),
                "B": doc.get("B"),
                "n": n,
                "lift": lift,
                "lift_lo": lift_lo,
                "lift_hi": lift_hi,
                "phi": phi,
                "phi_lo": phi_lo,
                "phi_hi": phi_hi,
                "pB": pB,
                "pBA_mean": pBA_mean,
                "pBA_lo": pBA_lo,
                "pBA_hi": pBA_hi,
                "score": score,
                "reason": reason,
            })
        
        # Hedge candidate filter: n >= min_n, phi_hi < 0
        if phi_hi is not None and phi_hi < 0:
            # Hedge score: (pB - pBA_mean) * log10(n)
            if pBA_mean is not None and pB > 0:
                score = (pB - pBA_mean) * math.log10(n) if n > 1 else 0.0
            else:
                score = abs(phi) * math.log10(n) if n > 1 else 0.0
            
            reason = "Hedge candidate because phi_hi < 0."
            if pBA_mean is not None and pBA_lo is not None and pBA_hi is not None:
                reason += f" P(B|A)={pBA_mean:.3f} [{pBA_lo:.3f}, {pBA_hi:.3f}] vs baseline P(B)={pB:.3f}."
            
            hedges.append({
                "A": doc.get("A"),
                "B": doc.get("B"),
                "n": n,
                "lift": lift,
                "lift_lo": lift_lo,
                "lift_hi": lift_hi,
                "phi": phi,
                "phi_lo": phi_lo,
                "phi_hi": phi_hi,
                "pB": pB,
                "pBA_mean": pBA_mean,
                "pBA_lo": pBA_lo,
                "pBA_hi": pBA_hi,
                "score": score,
                "reason": reason,
            })
    
    # Sort by score descending
    stacks.sort(key=lambda x: x["score"], reverse=True)
    hedges.sort(key=lambda x: x["score"], reverse=True)
    
    # Apply limit
    stacks = stacks[:limit]
    hedges = hedges[:limit]
    
    return {
        "stacks": stacks,
        "hedges": hedges,
    }


@app.get("/graph")
def get_graph(
    min_support: int = Query(200, ge=1, description="Minimum support for edges"),
    max_nodes: int = Query(200, ge=1, le=1000, description="Maximum number of nodes"),
    max_edges: int = Query(1500, ge=1, le=10000, description="Maximum number of edges"),
    families: str = Query("association,context,value", description="Comma-separated list of edge families")
):
    """
    GET endpoint that returns graph nodes and edges for visualization.
    """
    try:
        # Parse families
        family_list = [f.strip() for f in families.split(",")]
        
        # Get nodes (exclude _id)
        nodes_cursor = db.graph_nodes.find({}, {"_id": 0}).sort("support", -1).limit(max_nodes)
        node_ids = set()
        nodes_list = []
        for doc in nodes_cursor:
            node_id = doc.get("node_id")
            if node_id:
                node_ids.add(node_id)
                nodes_list.append({
                    "id": node_id,
                    "type": doc.get("type", "event"),
                    "description": doc.get("description", node_id),
                    "support": doc.get("support", 0),
                })
        
        # Get edges (only between nodes we're returning, exclude _id)
        # Convert node_ids set to list for MongoDB $in query (sets are not JSON-serializable)
        node_ids_list = list(node_ids)
        edges_cursor = db.graph_edges.find({
            "family": {"$in": family_list},
            "support": {"$gte": min_support},
            "source": {"$in": node_ids_list},
            "target": {"$in": node_ids_list},
        }, {"_id": 0}).sort("weight", -1).limit(max_edges)
        
        edges_list = []
        for doc in edges_cursor:
            # Convert metrics dict, ensuring no sets (sets are not JSON-serializable)
            metrics = doc.get("metrics", {})
            if isinstance(metrics, dict):
                metrics_clean = {}
                for k, v in metrics.items():
                    if isinstance(v, set):
                        metrics_clean[k] = list(v)
                    else:
                        metrics_clean[k] = v
                metrics = metrics_clean
            
            edges_list.append({
                "source": doc.get("source"),
                "target": doc.get("target"),
                "family": doc.get("family"),
                "weight": doc.get("weight", 0.0),
                "metrics": metrics,
                "support": doc.get("support", 0),
                "explain": doc.get("explain", ""),
                "classification": doc.get("classification"),
            })
        
        return {
            "nodes": nodes_list,
            "links": edges_list,
            "meta": {
                "min_support": min_support,
                "max_nodes": max_nodes,
                "max_edges": max_edges,
                "families": family_list,
                "node_count": len(nodes_list),
                "link_count": len(edges_list),
            },
        }
    except Exception as e:
        print("GRAPH ERROR:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/recommendations/ev")
def get_recommendations_ev(
    min_n: int = Query(100, ge=1, description="Minimum sample size"),
    limit: int = Query(25, ge=1, le=100, description="Maximum number of recommendations"),
    odds: int = Query(-110, description="American odds (default -110)"),
    parlay_odds: Optional[int] = Query(None, description="Parlay odds (optional)")
):
    """
    GET endpoint that returns EV-ranked recommendations.
    Does NOT output betting picks - only probabilistic insights and EV estimates.
    """
    pairs_cursor = db.pair_stats.find({})
    
    candidates = []
    
    for doc in pairs_cursor:
        n = doc.get("n", 0)
        if n < min_n:
            continue
        
        pA = doc.get("pA", 0.0)
        pB = doc.get("pB", 0.0)
        pAB = doc.get("pAB", 0.0)
        lift = doc.get("lift", 0.0)
        phi = doc.get("phi", 0.0)
        
        # Get probabilities with CI from event_probs
        eventA = db.event_probs.find_one({"event": doc.get("A")})
        eventB = db.event_probs.find_one({"event": doc.get("B")})
        
        pA_mean = eventA.get("p_mean") if eventA else pA
        pA_lo = eventA.get("p_lo") if eventA else pA * 0.9
        pA_hi = eventA.get("p_hi") if eventA else pA * 1.1
        
        pB_mean = eventB.get("p_mean") if eventB else pB
        pB_lo = eventB.get("p_lo") if eventB else pB * 0.9
        pB_hi = eventB.get("p_hi") if eventB else pB * 1.1
        
        # Joint probability
        pAB_mean = doc.get("pAB", pA_mean * pB_mean)
        pAB_lo = doc.get("pBA_lo", pA_lo * pB_lo)  # Approximate
        pAB_hi = doc.get("pBA_hi", pA_hi * pB_hi)  # Approximate
        
        # Compute EV for single events
        evA = compute_ev(pA_mean, pA_lo, pA_hi, odds)
        evB = compute_ev(pB_mean, pB_lo, pB_hi, odds)
        
        # Compute joint EV if parlay odds provided
        joint_ev = None
        if parlay_odds is not None:
            joint_ev = compute_joint_ev(
                pA_mean, pA_lo, pA_hi,
                pB_mean, pB_lo, pB_hi,
                pAB_mean, pAB_lo, pAB_hi,
                parlay_odds
            )
        
        # Reasoning
        reasoning = f"Event A: P={pA_mean:.3f} [{pA_lo:.3f}, {pA_hi:.3f}], EV={evA['ev_mean']:.2f} [{evA['ev_lo']:.2f}, {evA['ev_hi']:.2f}]. "
        reasoning += f"Event B: P={pB_mean:.3f} [{pB_lo:.3f}, {pB_hi:.3f}], EV={evB['ev_mean']:.2f} [{evB['ev_lo']:.2f}, {evB['ev_hi']:.2f}]. "
        if joint_ev:
            reasoning += f"Joint: P={joint_ev['joint_p_mean']:.3f} [{joint_ev['joint_p_lo']:.3f}, {joint_ev['joint_p_hi']:.3f}], EV={joint_ev['ev_mean']:.2f} [{joint_ev['ev_lo']:.2f}, {joint_ev['ev_hi']:.2f}]."
        
        # Score: use max EV (single or joint)
        if joint_ev:
            score = max(evA["ev_mean"], evB["ev_mean"], joint_ev["ev_mean"])
        else:
            score = max(evA["ev_mean"], evB["ev_mean"])
        
        candidates.append({
            "A": doc.get("A"),
            "B": doc.get("B"),
            "n": n,
            "lift": lift,
            "phi": phi,
            "evA": evA,
            "evB": evB,
            "joint_ev": joint_ev,
            "score": score,
            "reasoning": reasoning,
        })
    
    # Sort by score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)
    candidates = candidates[:limit]
    
    return {
        "candidates": candidates,
        "meta": {
            "min_n": min_n,
            "limit": limit,
            "odds": odds,
            "parlay_odds": parlay_odds,
            "count": len(candidates),
        },
    }


# ============================================================================
# ML Dashboard API Endpoints
# ============================================================================

@app.get("/api/health")
def api_health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "ml-dashboard"}


@app.get("/api/metrics")
def api_get_metrics():
    """Get ML metrics from metrics.json."""
    if not ML_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="ML API not available")
    return get_ml_metrics()


@app.get("/api/predictions")
def api_get_predictions(limit: int = Query(1000, ge=1, le=10000, description="Max rows to return")):
    """Get predictions from predictions.csv as JSON."""
    if not ML_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="ML API not available")
    return get_predictions(limit=limit)


@app.get("/api/calibration")
def api_get_calibration():
    """Get calibration table from calibration.csv as JSON."""
    if not ML_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="ML API not available")
    return get_calibration()


@app.get("/api/ablation")
def api_get_ablation():
    """Get ablation results from ablation_results.json."""
    if not ML_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="ML API not available")
    return get_ablation()


@app.get("/api/deciles")
def api_get_deciles():
    """Get deciles analysis from picks_by_decile.csv as JSON."""
    if not ML_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="ML API not available")
    return get_deciles()


@app.get("/api/picks_summary")
def api_get_picks_summary():
    """Get picks summary from picks_summary.json."""
    if not ML_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="ML API not available")
    return get_picks_summary()


@app.get("/api/coefficients")
def api_get_coefficients():
    """Get model coefficients from coefficients.json."""
    if not ML_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="ML API not available")
    return get_coefficients()


@app.get("/api/timeframe")
def api_get_timeframe():
    """Get timeframe (min/max date) from metrics or predictions."""
    if not ML_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="ML API not available")
    return get_timeframe()


@app.get("/api/picks")
def api_get_picks(
    limit: int = Query(100, ge=1, le=10000, description="Max picks to return"),
    sort: str = Query("confidence", description="Sort by 'confidence' or 'date'"),
    threshold: Optional[float] = Query(None, ge=0, le=0.5, description="Min confidence |p-0.5|"),
    topk: Optional[int] = Query(None, ge=1, description="Return top K picks by confidence")
):
    """Get example picks from predictions.csv."""
    if not ML_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="ML API not available")
    return get_picks(limit=limit, sort=sort, threshold=threshold, topk=topk)


@app.get("/api/future_games")
def api_get_future_games(
    date_from: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    min_confidence: float = Query(0.0, ge=0, le=0.5, description="Min confidence |p-0.5|"),
    limit: int = Query(100, ge=1, le=1000, description="Max games to return")
):
    """Get future games with model predictions."""
    if not ML_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="ML API not available")
    return get_future_games(date_from=date_from, date_to=date_to, min_confidence=min_confidence, limit=limit)


@app.get("/api/future_recommendations")
def api_get_future_recommendations(
    threshold: float = Query(0.15, ge=0, le=0.5, description="Min confidence threshold"),
    limit: int = Query(50, ge=1, le=500, description="Max recommendations")
):
    """Get future game recommendations (high confidence picks only)."""
    if not ML_API_AVAILABLE:
        raise HTTPException(status_code=503, detail="ML API not available")
    return get_future_games(min_confidence=threshold, limit=limit)
