"""
Compute pair statistics with uncertainty: bootstrap confidence intervals for lift/phi,
and conditional probabilities with credible intervals.

For each pair (A,B):
- Compute base stats: lift, phi
- Conditional probability P(B|A) with Beta credible interval
- Bootstrap confidence intervals for lift and phi
- Store in pair_stats collection (extends existing documents)
"""

from app.db import db
from app.analytics.compute_pairs import phi_correlation
from app.analytics.estimate_event_probs import beta_quantiles, discover_event_fields
import math
import random
import argparse


def compute_pair_base_stats(events, A: str, B: str):
    """
    Compute base statistics for a pair (A,B).
    
    Returns:
        dict with n, a, b, ab, pA, pB, pAB, lift, phi
    """
    n = 0
    a = 0  # A == True
    b = 0  # B == True
    ab = 0  # A == True AND B == True
    
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
    
    if n == 0:
        return None
    
    pA = a / n if n > 0 else 0.0
    pB = b / n if n > 0 else 0.0
    pAB = ab / n if n > 0 else 0.0
    
    # Lift: pAB / (pA * pB)
    lift = pAB / (pA * pB) if (pA * pB) > 0 else 0.0
    
    # Phi correlation: (a*b*c*d) counts
    # a = both True (ab)
    # b = A True, B False (a - ab)
    # c = A False, B True (b - ab)
    # d = both False (n - a - b + ab)
    b_count = a - ab  # A hit, B miss
    c_count = b - ab  # A miss, B hit
    d_count = n - a - b + ab  # both miss
    phi = phi_correlation(ab, b_count, c_count, d_count)
    
    return {
        "n": n,
        "a": a,
        "b": b,
        "ab": ab,
        "pA": pA,
        "pB": pB,
        "pAB": pAB,
        "lift": lift,
        "phi": phi,
    }


def compute_conditional_prob(base_stats):
    """
    Compute P(B|A) with Beta credible interval.
    
    Args:
        base_stats: dict with a, ab, pB
    
    Returns:
        dict with pBA_mean, pBA_lo, pBA_hi
    """
    a = base_stats["a"]  # count of A == True
    ab = base_stats["ab"]  # count of A == True AND B == True
    
    if a == 0:
        return {
            "pBA_mean": 0.0,
            "pBA_lo": 0.0,
            "pBA_hi": 0.0,
        }
    
    # Beta(1,1) prior -> Beta(1+ab, 1+a-ab) posterior for P(B|A)
    alpha = 1 + ab
    beta = 1 + a - ab
    
    pBA_mean = alpha / (alpha + beta)  # (1+ab)/(2+a)
    
    # Compute credible intervals
    pBA_lo, pBA_hi = beta_quantiles(alpha, beta)
    
    return {
        "pBA_mean": pBA_mean,
        "pBA_lo": pBA_lo,
        "pBA_hi": pBA_hi,
    }


def bootstrap_lift_phi(events, A: str, B: str, n_bootstrap: int = 500, seed: int = None):
    """
    Compute bootstrap confidence intervals for lift and phi.
    
    Args:
        events: list of event documents
        A: event field name for A
        B: event field name for B
        n_bootstrap: number of bootstrap samples
        seed: random seed for reproducibility
    
    Returns:
        dict with lift_lo, lift_hi, phi_lo, phi_hi
    """
    if seed is not None:
        random.seed(seed)
    
    # Filter events that have both A and B
    valid_events = [e for e in events if e.get(A) is not None and e.get(B) is not None]
    
    if len(valid_events) == 0:
        return {
            "lift_lo": 0.0,
            "lift_hi": 0.0,
            "phi_lo": 0.0,
            "phi_hi": 0.0,
        }
    
    n = len(valid_events)
    lift_samples = []
    phi_samples = []
    
    # Bootstrap resampling
    for _ in range(n_bootstrap):
        # Resample with replacement
        resample = [random.choice(valid_events) for _ in range(n)]
        
        # Compute stats on resample
        base_stats = compute_pair_base_stats(resample, A, B)
        if base_stats is not None:
            lift_samples.append(base_stats["lift"])
            phi_samples.append(base_stats["phi"])
    
    # Compute percentiles
    lift_samples.sort()
    phi_samples.sort()
    
    idx_lo = int(0.025 * len(lift_samples))
    idx_hi = int(0.975 * len(lift_samples))
    
    lift_lo = lift_samples[idx_lo] if idx_lo < len(lift_samples) else lift_samples[0] if lift_samples else 0.0
    lift_hi = lift_samples[idx_hi] if idx_hi < len(lift_samples) else lift_samples[-1] if lift_samples else 0.0
    
    phi_lo = phi_samples[idx_lo] if idx_lo < len(phi_samples) else phi_samples[0] if phi_samples else 0.0
    phi_hi = phi_samples[idx_hi] if idx_hi < len(phi_samples) else phi_samples[-1] if phi_samples else 0.0
    
    return {
        "lift_lo": lift_lo,
        "lift_hi": lift_hi,
        "phi_lo": phi_lo,
        "phi_hi": phi_hi,
    }


def compute_confidence(phi: float, n: int) -> float:
    """
    Compute confidence score: abs(phi) * log10(n)
    """
    if n <= 1:
        return 0.0
    return abs(phi) * math.log10(n)


def discover_event_pairs(min_n: int = 200):
    """
    Dynamically discover all event pairs from discovered event fields.
    Prunes pairs with insufficient support before heavy computation.
    
    Returns:
        list of (A, B) tuples
    """
    events = list(db.events.find({}))
    if not events:
        return []
    
    # Discover all event fields
    event_fields = discover_event_fields()
    print(f"Discovered {len(event_fields)} event fields")
    
    # Quick pass: count support for each event field
    field_counts = {}
    for event_field in event_fields:
        count = sum(1 for e in events if e.get(event_field) is not None)
        field_counts[event_field] = count
    
    # Generate pairs and filter by min_n before computation
    pairs = []
    for i, A in enumerate(event_fields):
        # Skip if A has insufficient support
        if field_counts[A] < min_n:
            continue
        
        for B in event_fields[i+1:]:
            # Skip if B has insufficient support
            if field_counts[B] < min_n:
                continue
            
            # Check joint support (quick pass)
            joint_support = 0
            for e in events:
                if e.get(A) is not None and e.get(B) is not None:
                    joint_support += 1
                    if joint_support >= min_n:
                        break
            
            # Only include if joint support >= min_n
            if joint_support >= min_n:
                pairs.append((A, B))
    
    return pairs


def compute_pair_cis(n_bootstrap: int = 500, seed: int = None, min_n: int = 200):
    """
    Compute pair statistics with confidence intervals for all discovered pairs.
    
    Dynamically generates pairs from all event fields and prunes by min_n.
    
    Updates existing pair_stats documents or creates new ones.
    """
    events = list(db.events.find({}))
    if not events:
        print("No events found.")
        return
    
    # Discover all qualifying pairs (pruned by min_n)
    pairs = discover_event_pairs(min_n=min_n)
    print(f"Computing pair CIs for {len(pairs)} pairs (min_n={min_n})...")
    print(f"Bootstrap samples: {n_bootstrap}")
    if seed is not None:
        print(f"Random seed: {seed}")
    
    results = []
    
    for idx, (A, B) in enumerate(pairs, 1):
        if idx % 50 == 0:
            print(f"Processing {idx}/{len(pairs)}: {A} ↔ {B}...")
        
        # Compute base stats
        base_stats = compute_pair_base_stats(events, A, B)
        if base_stats is None or base_stats["n"] < min_n:
            print(f"  Skipped: insufficient data (n={base_stats['n'] if base_stats else 0})")
            continue
        
        # Compute conditional probability P(B|A)
        cond_probs = compute_conditional_prob(base_stats)
        
        # Compute bootstrap CIs
        bootstrap_cis = bootstrap_lift_phi(events, A, B, n_bootstrap=n_bootstrap, seed=seed)
        
        # Compute confidence scores
        confidence = compute_confidence(base_stats["phi"], base_stats["n"])
        phi_abs_lo = abs(bootstrap_cis["phi_lo"])
        phi_abs_hi = abs(bootstrap_cis["phi_hi"])
        confidence_lo = max(0, phi_abs_lo) * math.log10(base_stats["n"]) if base_stats["n"] > 1 else 0.0
        
        # Prepare document (merge with existing if present)
        doc = {
            "pair": f"{A} ↔ {B}",
            "A": A,
            "B": B,
            "n": base_stats["n"],
            "pA": base_stats["pA"],
            "pB": base_stats["pB"],
            "pAB": base_stats["pAB"],
            "lift": base_stats["lift"],
            "phi": base_stats["phi"],
            "confidence": confidence,
            # New uncertainty fields
            "lift_lo": bootstrap_cis["lift_lo"],
            "lift_hi": bootstrap_cis["lift_hi"],
            "phi_lo": bootstrap_cis["phi_lo"],
            "phi_hi": bootstrap_cis["phi_hi"],
            "pBA_mean": cond_probs["pBA_mean"],
            "pBA_lo": cond_probs["pBA_lo"],
            "pBA_hi": cond_probs["pBA_hi"],
            "confidence_lo": confidence_lo,
        }
        
        # Update existing or insert new
        db.pair_stats.update_one(
            {"A": A, "B": B},
            {"$set": doc},
            upsert=True
        )
        
        results.append(doc)
        print(f"  Completed: n={base_stats['n']}, lift={base_stats['lift']:.3f} [{bootstrap_cis['lift_lo']:.3f}, {bootstrap_cis['lift_hi']:.3f}], phi={base_stats['phi']:.3f} [{bootstrap_cis['phi_lo']:.3f}, {bootstrap_cis['phi_hi']:.3f}]")
    
    print(f"\nDone. Updated {len(results)} pair statistics.")
    
    return len(results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute pair statistics with confidence intervals")
    parser.add_argument("--boot", type=int, default=500, help="Number of bootstrap samples (default: 500)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--min-n", type=int, default=200, help="Minimum sample size for pairs (default: 200)")
    
    args = parser.parse_args()
    compute_pair_cis(n_bootstrap=args.boot, seed=args.seed, min_n=args.min_n)
