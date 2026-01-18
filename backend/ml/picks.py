"""
Picks simulation and decision policy analysis.
Turns model probabilities into realistic decision rule reports.
"""
import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
from .config import OUTPUT_DIR

# Try to import scipy for stats, fall back to manual normal approximation
try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


def compute_hit_rate_ci(n, successes, confidence=0.95):
    """
    Compute confidence interval for hit rate using normal approximation.
    
    Args:
        n: Total number of picks
        successes: Number of successful picks
        confidence: Confidence level (default 0.95)
        
    Returns:
        Tuple of (hit_rate, ci_lower, ci_upper) or (None, None, None) if n == 0
    """
    if n == 0:
        return None, None, None
    
    p = successes / n
    
    # Z-score for confidence level (1.96 for 95%)
    if SCIPY_AVAILABLE:
        z = stats.norm.ppf((1 + confidence) / 2)
    else:
        # Manual approximation: 1.96 for 95%, 2.576 for 99%
        if confidence == 0.95:
            z = 1.96
        elif confidence == 0.99:
            z = 2.576
        else:
            # Approximate for other confidence levels
            z = 1.96  # Default to 95%
    
    se = np.sqrt(p * (1 - p) / n)
    
    ci_lower = max(0.0, p - z * se)
    ci_upper = min(1.0, p + z * se)
    
    return float(p), float(ci_lower), float(ci_upper)


def analyze_deciles(predictions_df):
    """
    Bin predictions into deciles and compute hit rates.
    
    Args:
        predictions_df: DataFrame with 'p_hat' and 'y_true' columns
        
    Returns:
        DataFrame with decile analysis
    """
    df = predictions_df.copy()
    df['decile'] = pd.cut(df['p_hat'], bins=10, labels=False, include_lowest=True)
    
    decile_stats = df.groupby('decile').agg({
        'p_hat': ['count', 'mean'],
        'y_true': 'mean',
    }).reset_index()
    
    decile_stats.columns = ['decile', 'count', 'mean_pred', 'mean_true']
    decile_stats['decile'] = decile_stats['decile'] + 1  # 1-indexed
    decile_stats['calibration_diff'] = decile_stats['mean_true'] - decile_stats['mean_pred']
    
    # Add bin ranges
    decile_stats['bin_low'] = decile_stats['decile'] / 10.0 - 0.1
    decile_stats['bin_high'] = decile_stats['decile'] / 10.0
    
    return decile_stats[['decile', 'bin_low', 'bin_high', 'count', 'mean_pred', 'mean_true', 'calibration_diff']]


def analyze_threshold_policy(predictions_df, thresholds=[0.55, 0.60, 0.65, 0.70]):
    """
    Analyze threshold-based picking policy.
    Pick Over if p_hat >= threshold, Under if p_hat <= (1 - threshold).
    
    Args:
        predictions_df: DataFrame with 'p_hat' and 'y_true' columns
        thresholds: List of thresholds to evaluate
        
    Returns:
        List of dicts with results for each threshold
    """
    results = []
    
    for t in thresholds:
        # Pick Over if p_hat >= t
        over_picks = predictions_df[predictions_df['p_hat'] >= t].copy()
        over_hit_rate = over_picks['y_true'].mean() if len(over_picks) > 0 else None
        
        # Pick Under if p_hat <= (1 - t)
        under_picks = predictions_df[predictions_df['p_hat'] <= (1 - t)].copy()
        under_hit_rate = (1 - under_picks['y_true']).mean() if len(under_picks) > 0 else None
        
        # Overall picks (both directions)
        total_picks = len(over_picks) + len(under_picks)
        if total_picks > 0:
            over_correct = over_picks['y_true'].sum() if len(over_picks) > 0 else 0
            under_correct = (1 - under_picks['y_true']).sum() if len(under_picks) > 0 else 0
            overall_hit_rate = (over_correct + under_correct) / total_picks
        else:
            overall_hit_rate = None
        
        # Compute CI for overall hit rate
        total_correct = over_correct + under_correct if total_picks > 0 else 0
        overall_hr, overall_ci_lo, overall_ci_hi = compute_hit_rate_ci(total_picks, total_correct)
        
        # Compute CI for over picks
        over_correct_count = over_picks['y_true'].sum() if len(over_picks) > 0 else 0
        over_hr, over_ci_lo, over_ci_hi = compute_hit_rate_ci(len(over_picks), over_correct_count)
        
        # Compute CI for under picks
        under_correct_count = (1 - under_picks['y_true']).sum() if len(under_picks) > 0 else 0
        under_hr, under_ci_lo, under_ci_hi = compute_hit_rate_ci(len(under_picks), under_correct_count)
        
        results.append({
            'threshold': t,
            'num_picks': total_picks,
            'hit_rate': overall_hr,
            'hit_rate_ci_lower': overall_ci_lo,
            'hit_rate_ci_upper': overall_ci_hi,
            'over_pick_count': len(over_picks),
            'over_hit_rate': over_hr,
            'over_hit_rate_ci_lower': over_ci_lo,
            'over_hit_rate_ci_upper': over_ci_hi,
            'under_pick_count': len(under_picks),
            'under_hit_rate': under_hr,
            'under_hit_rate_ci_lower': under_ci_lo,
            'under_hit_rate_ci_upper': under_ci_hi,
        })
    
    return results


def analyze_topk_policy(predictions_df, k_values=[5, 10, 20]):
    """
    Analyze top-K picking policy per fold.
    Pick top K highest |p_hat - 0.5| per fold.
    
    Args:
        predictions_df: DataFrame with 'p_hat', 'y_true', and 'fold' columns
        k_values: List of K values to evaluate
        
    Returns:
        List of dicts with results for each K
    """
    results = []
    
    if 'fold' not in predictions_df.columns:
        # If no fold column, treat all as one fold
        predictions_df = predictions_df.copy()
        predictions_df['fold'] = 0
    
    for k in k_values:
        picks_list = []
        
        for fold in predictions_df['fold'].unique():
            fold_data = predictions_df[predictions_df['fold'] == fold].copy()
            fold_data['confidence'] = abs(fold_data['p_hat'] - 0.5)
            
            # Pick top K by confidence
            topk = fold_data.nlargest(k, 'confidence')
            picks_list.append(topk)
        
        if picks_list:
            all_picks = pd.concat(picks_list, ignore_index=True)
            
            # For picks, determine correct direction:
            # If p_hat > 0.5, pick Over (correct if y_true == 1)
            # If p_hat < 0.5, pick Under (correct if y_true == 0)
            over_picks = all_picks[all_picks['p_hat'] > 0.5]
            under_picks = all_picks[all_picks['p_hat'] < 0.5]
            
            over_correct = over_picks['y_true'].sum() if len(over_picks) > 0 else 0
            under_correct = (1 - under_picks['y_true']).sum() if len(under_picks) > 0 else 0
            
            total_picks = len(all_picks)
            total_correct = over_correct + under_correct
            hit_rate = total_correct / total_picks if total_picks > 0 else None
            
            # Compute CI
            hr, ci_lo, ci_hi = compute_hit_rate_ci(total_picks, total_correct)
            
            # Over/under breakdown
            over_correct_count = over_picks['y_true'].sum() if len(over_picks) > 0 else 0
            over_hr, over_ci_lo, over_ci_hi = compute_hit_rate_ci(len(over_picks), over_correct_count)
            
            under_correct_count = (1 - under_picks['y_true']).sum() if len(under_picks) > 0 else 0
            under_hr, under_ci_lo, under_ci_hi = compute_hit_rate_ci(len(under_picks), under_correct_count)
        else:
            total_picks = 0
            hr = None
            ci_lo = None
            ci_hi = None
            over_picks = pd.DataFrame()
            under_picks = pd.DataFrame()
            over_hr = None
            over_ci_lo = None
            over_ci_hi = None
            under_hr = None
            under_ci_lo = None
            under_ci_hi = None
        
        results.append({
            'k': k,
            'num_picks': total_picks,
            'hit_rate': hr,
            'hit_rate_ci_lower': ci_lo,
            'hit_rate_ci_upper': ci_hi,
            'over_pick_count': len(over_picks),
            'over_hit_rate': over_hr,
            'over_hit_rate_ci_lower': over_ci_lo,
            'over_hit_rate_ci_upper': over_ci_hi,
            'under_pick_count': len(under_picks),
            'under_hit_rate': under_hr,
            'under_hit_rate_ci_lower': under_ci_lo,
            'under_hit_rate_ci_upper': under_ci_hi,
        })
    
    return results


def analyze_hypothetical_ev(predictions_df, assumed_payout=0.9091):
    """
    Hypothetical EV analysis assuming -110 odds (clearly labeled as hypothetical).
    
    Args:
        predictions_df: DataFrame with 'p_hat' and 'y_true' columns
        assumed_payout: Payout on wins (default 0.9091 for -110)
        
    Returns:
        Dict with EV-positive picks analysis
    """
    df = predictions_df.copy()
    
    # EV = p_hat * payout - (1 - p_hat) * 1
    df['ev'] = df['p_hat'] * assumed_payout - (1 - df['p_hat']) * 1.0
    
    # Only count picks where EV > 0
    ev_positive = df[df['ev'] > 0].copy()
    
    if len(ev_positive) > 0:
        # Determine correct direction
        over_picks = ev_positive[ev_positive['p_hat'] > 0.5]
        under_picks = ev_positive[ev_positive['p_hat'] < 0.5]
        
        over_correct = over_picks['y_true'].sum() if len(over_picks) > 0 else 0
        under_correct = (1 - under_picks['y_true']).sum() if len(under_picks) > 0 else 0
        
        total_picks = len(ev_positive)
        hit_rate = (over_correct + under_correct) / total_picks
        avg_ev = ev_positive['ev'].mean()
    else:
        total_picks = 0
        hit_rate = None
        avg_ev = None
    
    return {
        'num_ev_positive_picks': int(total_picks),
        'avg_ev': float(avg_ev) if avg_ev is not None else None,
        'hit_rate': float(hit_rate) if hit_rate is not None else None,
        'assumed_payout': assumed_payout,
        'note': 'HYPOTHETICAL: Assumes -110 odds. Not a profitability claim.',
    }


def run_picks_analysis(predictions_path=None):
    """
    Run complete picks analysis on saved predictions.
    
    Args:
        predictions_path: Path to predictions.csv (defaults to OUTPUT_DIR/predictions.csv)
        
    Returns:
        Dict with all analysis results
    """
    if predictions_path is None:
        predictions_path = OUTPUT_DIR / "predictions.csv"
    
    if not predictions_path.exists():
        raise FileNotFoundError(f"Predictions file not found: {predictions_path}")
    
    # Load predictions
    predictions_df = pd.read_csv(predictions_path)
    
    # Ensure required columns exist
    if 'p_hat' not in predictions_df.columns or 'y_true' not in predictions_df.columns:
        raise ValueError("predictions_df must contain 'p_hat' and 'y_true' columns")
    
    # Run analyses
    decile_df = analyze_deciles(predictions_df)
    threshold_results = analyze_threshold_policy(predictions_df)
    topk_results = analyze_topk_policy(predictions_df)
    hypothetical_ev = analyze_hypothetical_ev(predictions_df)
    
    # Compile results
    results = {
        'decile_analysis': decile_df.to_dict('records'),
        'threshold_policy': threshold_results,
        'topk_policy': topk_results,
        'hypothetical_ev': hypothetical_ev,
    }
    
    return results, decile_df


def save_picks_results(results, decile_df):
    """
    Save picks analysis results to files.
    
    Args:
        results: Dict with analysis results
        decile_df: DataFrame with decile analysis
    """
    # Save summary JSON
    summary_path = OUTPUT_DIR / "picks_summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"  Saved picks summary to {summary_path}")
    
    # Save decile CSV
    decile_path = OUTPUT_DIR / "picks_by_decile.csv"
    decile_df.to_csv(decile_path, index=False)
    print(f"  Saved decile analysis to {decile_path}")


def print_picks_summary(results):
    """
    Print concise picks summary to console.
    
    Args:
        results: Dict with analysis results
    """
    print("\n" + "=" * 80)
    print("PICKS ANALYSIS SUMMARY")
    print("=" * 80)
    
    # Decile lift (top 2 bins)
    deciles = results['decile_analysis']
    if deciles:
        top_deciles = sorted(deciles, key=lambda x: x['decile'], reverse=True)[:2]
        print("\nTop 2 Deciles (highest confidence):")
        for d in top_deciles:
            print(f"  Decile {d['decile']}: pred={d['mean_pred']:.3f}, hit_rate={d['mean_true']:.3f}, diff={d['calibration_diff']:.3f}, n={d['count']}")
    
    # Threshold policy
    print("\nThreshold Policy (pick Over if p>=t, Under if p<=(1-t)):")
    print(f"{'Threshold':<12} {'Total':<8} {'Hit Rate':<12} {'95% CI':<20} {'Over':<8} {'Over HR':<10} {'Under':<8} {'Under HR':<10}")
    print("-" * 100)
    for t in results['threshold_policy']:
        hr_str = f"{t['hit_rate']:.3f}" if t['hit_rate'] is not None else "N/A"
        ci_str = f"[{t['hit_rate_ci_lower']:.3f}, {t['hit_rate_ci_upper']:.3f}]" if t['hit_rate_ci_lower'] is not None else "N/A"
        over_hr_str = f"{t['over_hit_rate']:.3f}" if t['over_hit_rate'] is not None and t['over_pick_count'] > 0 else "N/A"
        under_hr_str = f"{t['under_hit_rate']:.3f}" if t['under_hit_rate'] is not None and t['under_pick_count'] > 0 else "N/A"
        print(f"{t['threshold']:<12.2f} {t['num_picks']:<8} {hr_str:<12} {ci_str:<20} {t['over_pick_count']:<8} {over_hr_str:<10} {t['under_pick_count']:<8} {under_hr_str:<10}")
    
    # Top-K policy
    print("\nTop-K Policy (top K |p-0.5| per fold):")
    print(f"{'K':<8} {'Total':<8} {'Hit Rate':<12} {'95% CI':<20} {'Over':<8} {'Over HR':<10} {'Under':<8} {'Under HR':<10}")
    print("-" * 100)
    for k in results['topk_policy']:
        hr_str = f"{k['hit_rate']:.3f}" if k['hit_rate'] is not None else "N/A"
        ci_str = f"[{k['hit_rate_ci_lower']:.3f}, {k['hit_rate_ci_upper']:.3f}]" if k['hit_rate_ci_lower'] is not None else "N/A"
        over_hr_str = f"{k['over_hit_rate']:.3f}" if k['over_hit_rate'] is not None and k['over_pick_count'] > 0 else "N/A"
        under_hr_str = f"{k['under_hit_rate']:.3f}" if k['under_hit_rate'] is not None and k['under_pick_count'] > 0 else "N/A"
        print(f"{k['k']:<8} {k['num_picks']:<8} {hr_str:<12} {ci_str:<20} {k['over_pick_count']:<8} {over_hr_str:<10} {k['under_pick_count']:<8} {under_hr_str:<10}")
    
    # Hypothetical EV (clearly labeled)
    ev = results['hypothetical_ev']
    print(f"\n{ev['note']}")
    print(f"  EV-positive picks: {ev['num_ev_positive_picks']}")
    if ev['avg_ev'] is not None:
        print(f"  Avg EV: {ev['avg_ev']:.4f}")
    if ev['hit_rate'] is not None:
        print(f"  Hit rate: {ev['hit_rate']:.3f}")
    
    print("=" * 80)
