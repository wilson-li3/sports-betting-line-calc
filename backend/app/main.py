from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from app.db import db
import math
from typing import Literal

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
