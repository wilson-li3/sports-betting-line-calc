"""
Metrics computation: accuracy, log_loss, ROC-AUC, calibration.
"""
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
from typing import Dict, Tuple


def compute_metrics(y_true, y_pred_proba, threshold=0.5):
    """
    Compute classification metrics.
    
    Args:
        y_true: True labels (0/1)
        y_pred_proba: Predicted probabilities for class 1 (array of shape [n_samples])
        threshold: Classification threshold (default 0.5)
        
    Returns:
        Dictionary with metrics
    """
    # Convert probabilities to binary predictions
    y_pred = (y_pred_proba >= threshold).astype(int)
    
    # Accuracy
    accuracy = accuracy_score(y_true, y_pred)
    
    # Log loss
    # Add small epsilon to avoid log(0)
    epsilon = 1e-15
    y_pred_proba_clipped = np.clip(y_pred_proba, epsilon, 1 - epsilon)
    loss = log_loss(y_true, y_pred_proba_clipped)
    
    # ROC-AUC (only if both classes present)
    try:
        if len(np.unique(y_true)) == 2:
            roc_auc = roc_auc_score(y_true, y_pred_proba)
        else:
            roc_auc = None
    except ValueError:
        roc_auc = None
    
    metrics = {
        "accuracy": float(accuracy),
        "log_loss": float(loss),
        "roc_auc": float(roc_auc) if roc_auc is not None else None,
        "threshold": threshold,
        "n_samples": len(y_true),
    }
    
    return metrics


def compute_calibration(y_true, y_pred_proba, n_bins=10):
    """
    Compute calibration table (bins by predicted probability).
    
    Args:
        y_true: True labels (0/1)
        y_pred_proba: Predicted probabilities for class 1 (array of shape [n_samples])
        n_bins: Number of bins (default 10 for deciles)
        
    Returns:
        DataFrame with columns: bin, count, mean_pred, mean_true, diff
    """
    # Create bins
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_pred_proba, bin_edges[1:], right=True)
    
    # Aggregate by bin
    results = []
    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() == 0:
            continue
        
        bin_count = mask.sum()
        bin_mean_pred = y_pred_proba[mask].mean()
        bin_mean_true = y_true[mask].mean()
        bin_diff = bin_mean_pred - bin_mean_true
        
        results.append({
            "bin": i + 1,
            "bin_low": bin_edges[i],
            "bin_high": bin_edges[i + 1],
            "count": int(bin_count),
            "mean_pred": float(bin_mean_pred),
            "mean_true": float(bin_mean_true),
            "diff": float(bin_diff),  # Positive = overconfident, Negative = underconfident
        })
    
    calibration_df = pd.DataFrame(results)
    
    return calibration_df


def compute_all_metrics(y_true, y_pred_proba, threshold=0.5, n_bins=10):
    """
    Compute all metrics and calibration table.
    
    Args:
        y_true: True labels (0/1)
        y_pred_proba: Predicted probabilities for class 1 (array of shape [n_samples])
        threshold: Classification threshold (default 0.5)
        n_bins: Number of calibration bins (default 10)
        
    Returns:
        Tuple of (metrics_dict, calibration_df)
    """
    metrics = compute_metrics(y_true, y_pred_proba, threshold=threshold)
    calibration_df = compute_calibration(y_true, y_pred_proba, n_bins=n_bins)
    
    return metrics, calibration_df
