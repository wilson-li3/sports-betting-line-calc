"""
Estimate event probabilities with Bayesian Beta-Binomial credible intervals.

For each event field in the events collection, computes:
- n: total number of event docs
- k: number of docs where event == True
- p_mean: posterior mean (using Beta(1,1) prior)
- p_lo, p_hi: 2.5% and 97.5% quantiles of Beta posterior

Uses Monte Carlo sampling (random.betavariate) for quantile estimation.
"""

from app.db import db
import random

# Event fields to analyze (boolean fields in events collection)
EVENT_FIELDS = [
    "TEAM_TOTAL_OVER_HIT",
    "GAME_TOTAL_OVER_HIT",
    "PRIMARY_SCORER_PTS_OVER_HIT",
    "PRIMARY_FACILITATOR_AST_OVER_HIT",
    "PRIMARY_REBOUNDER_REB_OVER_HIT",
]

# Number of Monte Carlo samples for quantile estimation
MC_SAMPLES = 50000


def beta_quantiles(alpha: float, beta: float, mc_samples: int = MC_SAMPLES):
    """
    Compute 2.5% and 97.5% quantiles of Beta(alpha, beta) using Monte Carlo sampling.
    
    Args:
        alpha: Beta distribution alpha parameter
        beta: Beta distribution beta parameter
        mc_samples: Number of Monte Carlo samples
    
    Returns:
        (q_lo, q_hi): 2.5% and 97.5% quantiles
    """
    samples = [random.betavariate(alpha, beta) for _ in range(mc_samples)]
    samples.sort()
    
    idx_lo = int(0.025 * mc_samples)
    idx_hi = int(0.975 * mc_samples)
    
    q_lo = samples[idx_lo] if idx_lo < mc_samples else samples[0]
    q_hi = samples[idx_hi] if idx_hi < mc_samples else samples[-1]
    
    return q_lo, q_hi


def estimate_event_prob(event_field: str):
    """
    Estimate probability for a single event field.
    
    Args:
        event_field: Name of the event field (e.g., "TEAM_TOTAL_OVER_HIT")
    
    Returns:
        dict with event, n, k, p_mean, p_lo, p_hi
    """
    # Get all events
    events = list(db.events.find({event_field: {"$exists": True}}))
    
    if not events:
        return None
    
    n = len(events)
    k = sum(1 for e in events if e.get(event_field) == 1)
    
    # Beta(1,1) prior -> Beta(1+k, 1+n-k) posterior
    alpha = 1 + k
    beta = 1 + n - k
    
    # Posterior mean
    p_mean = alpha / (alpha + beta)  # (1+k)/(2+n)
    
    # Compute credible intervals using Monte Carlo
    p_lo, p_hi = beta_quantiles(alpha, beta)
    
    return {
        "event": event_field,
        "n": n,
        "k": k,
        "p_mean": p_mean,
        "p_lo": p_lo,
        "p_hi": p_hi,
    }


def estimate_all_event_probs():
    """
    Estimate probabilities for all event fields and store in event_probs collection.
    """
    print("Estimating event probabilities...")
    print(f"Event fields: {', '.join(EVENT_FIELDS)}")
    
    # Delete existing event_probs (idempotent: rebuild collection)
    db.event_probs.delete_many({})
    
    results = []
    for event_field in EVENT_FIELDS:
        result = estimate_event_prob(event_field)
        if result:
            results.append(result)
    
    if results:
        db.event_probs.insert_many(results)
        print(f"\nInserted {len(results)} event probabilities.")
    else:
        print("\nNo event probabilities computed (no events found).")
    
    # Print summary
    if results:
        print("\nTop events by sample size:")
        sorted_results = sorted(results, key=lambda x: x["n"], reverse=True)
        for r in sorted_results[:5]:
            print(f"  {r['event']}: n={r['n']}, p_mean={r['p_mean']:.3f} [{r['p_lo']:.3f}, {r['p_hi']:.3f}]")
    
    return len(results)


if __name__ == "__main__":
    estimate_all_event_probs()
