"""
Expected Value (EV) utilities for line value vs implied odds.

Converts American odds to implied probabilities and computes EV.
"""

def american_to_implied_prob(odds: int) -> float:
    """
    Convert American odds to implied probability.
    
    Args:
        odds: American odds (e.g., -110, +150)
    
    Returns:
        Implied probability (0.0 to 1.0)
    """
    if odds > 0:
        # Positive odds: implied_prob = 100 / (odds + 100)
        return 100.0 / (odds + 100)
    else:
        # Negative odds: implied_prob = abs(odds) / (abs(odds) + 100)
        return abs(odds) / (abs(odds) + 100)


def compute_ev(p_mean: float, p_lo: float, p_hi: float, odds: int, stake: float = 100.0):
    """
    Compute expected value for a single event.
    
    Args:
        p_mean: Mean probability
        p_lo: Lower bound (2.5th percentile)
        p_hi: Upper bound (97.5th percentile)
        odds: American odds
        stake: Bet size (default 100)
    
    Returns:
        dict with ev_mean, ev_lo, ev_hi
    """
    implied_prob = american_to_implied_prob(odds)
    
    # Payout if win
    if odds > 0:
        payout = stake * (odds / 100.0)
    else:
        payout = stake * (100.0 / abs(odds))
    
    # EV = p * payout - (1-p) * stake
    ev_mean = p_mean * payout - (1 - p_mean) * stake
    ev_lo = p_lo * payout - (1 - p_lo) * stake
    ev_hi = p_hi * payout - (1 - p_hi) * stake
    
    return {
        "ev_mean": ev_mean,
        "ev_lo": ev_lo,
        "ev_hi": ev_hi,
        "implied_prob": implied_prob,
        "p_mean": p_mean,
        "p_lo": p_lo,
        "p_hi": p_hi,
    }


def compute_joint_ev(pA_mean: float, pA_lo: float, pA_hi: float,
                     pB_mean: float, pB_lo: float, pB_hi: float,
                     pAB_mean: float, pAB_lo: float, pAB_hi: float,
                     parlay_odds: int, stake: float = 100.0):
    """
    Compute EV for a parlay (joint probability).
    
    Uses dependence-adjusted probability if available, otherwise independence assumption.
    """
    implied_prob = american_to_implied_prob(parlay_odds)
    
    # Payout
    if parlay_odds > 0:
        payout = stake * (parlay_odds / 100.0)
    else:
        payout = stake * (100.0 / abs(parlay_odds))
    
    # Use pAB if available, otherwise pA * pB (independence)
    joint_p_mean = pAB_mean if pAB_mean > 0 else pA_mean * pB_mean
    joint_p_lo = pAB_lo if pAB_lo > 0 else pA_lo * pB_lo
    joint_p_hi = pAB_hi if pAB_hi > 0 else pA_hi * pB_hi
    
    ev_mean = joint_p_mean * payout - (1 - joint_p_mean) * stake
    ev_lo = joint_p_lo * payout - (1 - joint_p_lo) * stake
    ev_hi = joint_p_hi * payout - (1 - joint_p_hi) * stake
    
    return {
        "ev_mean": ev_mean,
        "ev_lo": ev_lo,
        "ev_hi": ev_hi,
        "implied_prob": implied_prob,
        "joint_p_mean": joint_p_mean,
        "joint_p_lo": joint_p_lo,
        "joint_p_hi": joint_p_hi,
    }
