"""
Ablation study: Evaluate different feature sets.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from .config import MIN_TRAIN_SIZE, TEST_CHUNK_SIZE
from .backtest import walk_forward_backtest


def get_feature_set_A_line_only(df, feature_cols_all):
    """
    Feature set A: line_only
    - TEAM_TOTAL_LINE
    - GAME_TOTAL_LINE (if exists)
    """
    feature_set = []
    if "TEAM_TOTAL_LINE" in feature_cols_all:
        feature_set.append("TEAM_TOTAL_LINE")
    if "GAME_TOTAL_LINE" in feature_cols_all:
        feature_set.append("GAME_TOTAL_LINE")
    return feature_set


def get_feature_set_B_line_plus_context(df, feature_cols_all):
    """
    Feature set B: line_plus_context
    - A (line_only)
    - is_home
    - is_competitive
    - pace_low, pace_mid, pace_high (if present)
    """
    feature_set = get_feature_set_A_line_only(df, feature_cols_all)
    
    # Add context features
    context_features = ["is_home", "is_competitive", "pace_low", "pace_mid", "pace_high"]
    for feat in context_features:
        if feat in feature_cols_all:
            feature_set.append(feat)
    
    return feature_set


def get_feature_set_C_line_plus_rolling_totals(df, feature_cols_all):
    """
    Feature set C: line_plus_rolling_totals
    - A (line_only)
    - Rolling features from TEAM_TOTAL and GAME_TOTAL only:
      - rolling_TEAM_TOTAL_margin_{mean,std}_{5,10}
      - rolling_TEAM_TOTAL_over_rate_{5,10}
      - rolling_GAME_TOTAL_margin_{mean,std}_{5,10}
      - rolling_GAME_TOTAL_over_rate_{5,10}
    """
    feature_set = get_feature_set_A_line_only(df, feature_cols_all)
    
    # Add rolling features from TEAM_TOTAL and GAME_TOTAL only
    rolling_prefixes = [
        "rolling_TEAM_TOTAL",
        "rolling_team_total",
        "rolling_GAME_TOTAL",
        "rolling_game_total",
    ]
    
    for feat in feature_cols_all:
        if feat.startswith("rolling_"):
            # Check if it's from TEAM_TOTAL or GAME_TOTAL
            for prefix in rolling_prefixes:
                if feat.startswith(prefix):
                    feature_set.append(feat)
                    break
    
    return feature_set


def get_feature_set_D_full_model(df, feature_cols_all):
    """
    Feature set D: full_model
    - All 99 features (current full model)
    """
    return feature_cols_all.copy()


def run_ablation_study(df_final, label_col, feature_cols_all):
    """
    Run ablation study with 4 feature sets.
    Each evaluated with uncalibrated and sigmoid-calibrated models.
    
    Args:
        df_final: DataFrame with all features, label, and metadata
        label_col: Label column name
        feature_cols_all: List of all available feature columns
        
    Returns:
        List of results dicts with metrics for each feature set + calibration variant
    """
    print("\n" + "=" * 80)
    print("ABLATION STUDY")
    print("=" * 80)
    
    # Define feature sets
    feature_sets = {
        "A: line_only": get_feature_set_A_line_only(df_final, feature_cols_all),
        "B: line_plus_context": get_feature_set_B_line_plus_context(df_final, feature_cols_all),
        "C: line_plus_rolling_totals": get_feature_set_C_line_plus_rolling_totals(df_final, feature_cols_all),
        "D: full_model": get_feature_set_D_full_model(df_final, feature_cols_all),
    }
    
    results = []
    
    # Evaluate each feature set
    for set_name, feature_cols in feature_sets.items():
        if not feature_cols:
            print(f"\n  Skipping {set_name}: no features")
            continue
        
        print(f"\n  Evaluating {set_name} ({len(feature_cols)} features)...")
        
        # Filter df_final to only include these features + label + metadata
        # Ensure no duplicates (TEAM_TOTAL_LINE might be in both feature_cols and metadata list)
        metadata_cols = [label_col, "date", "team_id", "game_id", "TEAM_TOTAL_LINE"]
        cols_needed = feature_cols + [c for c in metadata_cols if c not in feature_cols]
        cols_available = [c for c in cols_needed if c in df_final.columns]
        # Remove any remaining duplicates while preserving order
        seen = set()
        cols_unique = []
        for c in cols_available:
            if c not in seen:
                seen.add(c)
                cols_unique.append(c)
        df_filtered = df_final[cols_unique].copy()
        
        # Run backtest with this feature set
        try:
            _, metrics_dict, _ = walk_forward_backtest(
                df_filtered,
                feature_cols,
                label_col,
                min_train_size=MIN_TRAIN_SIZE,
                test_chunk_size=TEST_CHUNK_SIZE,
            )
            
            # Extract metrics for uncalibrated and sigmoid
            selected_model = metrics_dict.get("selected_model", "uncalibrated")
            selected_metrics = metrics_dict.get("selected_model_metrics", metrics_dict)
            
            # Get sigmoid metrics if available
            sigmoid_metrics = metrics_dict.get("calibrated_sigmoid", {})
            if not sigmoid_metrics:
                sigmoid_metrics = selected_metrics  # Fallback
            
            results.append({
                "feature_set": set_name,
                "n_features": len(feature_cols),
                "variant": "uncalibrated",
                "accuracy": metrics_dict.get("accuracy", 0),
                "log_loss": metrics_dict.get("log_loss", float('inf')),
                "roc_auc": metrics_dict.get("roc_auc"),
            })
            
            results.append({
                "feature_set": set_name,
                "n_features": len(feature_cols),
                "variant": "sigmoid",
                "accuracy": sigmoid_metrics.get("accuracy", 0),
                "log_loss": sigmoid_metrics.get("log_loss", float('inf')),
                "roc_auc": sigmoid_metrics.get("roc_auc"),
            })
            
        except Exception as e:
            print(f"    ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    # Print comparison table
    print("\n" + "=" * 80)
    print("ABLATION RESULTS (sorted by LogLoss)")
    print("=" * 80)
    print(f"{'Feature Set':<35} {'Variant':<15} {'Accuracy':<12} {'Log Loss':<12} {'ROC-AUC':<12}")
    print("-" * 80)
    
    # Sort by log_loss (primary metric)
    results_sorted = sorted(results, key=lambda x: x['log_loss'])
    
    for r in results_sorted:
        roc_auc_str = f"{r['roc_auc']:.3f}" if r.get('roc_auc') else "N/A"
        print(f"{r['feature_set']:<35} {r['variant']:<15} {r['accuracy']:<12.3f} {r['log_loss']:<12.3f} {roc_auc_str:<12}")
    
    print("=" * 80)
    
    return results
