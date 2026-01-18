"""
Interpretability: Extract and visualize model coefficients.
"""
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from pathlib import Path
from .config import OUTPUT_DIR


def extract_coefficients(model, feature_names):
    """
    Extract coefficients from a LogisticRegression model.
    
    Args:
        model: Fitted sklearn pipeline (with LogisticRegression as final step)
        feature_names: List of feature names (matching order in model)
        
    Returns:
        Dict mapping feature name to coefficient value, plus intercept if available
    """
    # Get the classifier (final step in pipeline)
    classifier = model.named_steps['classifier']
    
    # Get coefficients (shape: [n_classes, n_features])
    # For binary classification, shape is [2, n_features]
    coef = classifier.coef_[0]  # Get coefficients for positive class
    
    # Create feature -> coefficient mapping
    coef_dict = {name: float(coef) for name, coef in zip(feature_names, coef)}
    
    # Add intercept if available
    if hasattr(classifier, 'intercept_'):
        coef_dict['_intercept'] = float(classifier.intercept_[0])
    
    return coef_dict


def get_top_coefficients(coef_dict, n=10):
    """
    Get top positive and negative coefficients.
    
    Args:
        coef_dict: Dict mapping feature name to coefficient
        n: Number of top coefficients to return (default 10)
        
    Returns:
        Tuple of (top_positive, top_negative) lists of (feature, coef) tuples
    """
    # Filter by sign (exclude exactly 0 from both lists)
    positive_coefs = [(feat, coef) for feat, coef in coef_dict.items() if coef > 0]
    negative_coefs = [(feat, coef) for feat, coef in coef_dict.items() if coef < 0]
    
    # Sort positive descending (largest first)
    if positive_coefs:
        top_positive = sorted(positive_coefs, key=lambda x: x[1], reverse=True)[:n]
    else:
        top_positive = []
    
    # Sort negative ascending (most negative first)
    if negative_coefs:
        top_negative = sorted(negative_coefs, key=lambda x: x[1])[:n]
    else:
        top_negative = []
    
    return top_positive, top_negative


def print_coefficients_table(coef_dict, n=10):
    """
    Print a formatted table of top coefficients.
    
    Args:
        coef_dict: Dict mapping feature name to coefficient (may include '_intercept')
        n: Number of top coefficients to show (default 10)
    """
    # Extract intercept if present (don't modify original dict)
    intercept = coef_dict.get('_intercept', None)
    coef_dict_filtered = {k: v for k, v in coef_dict.items() if k != '_intercept'}
    
    top_pos, top_neg = get_top_coefficients(coef_dict_filtered, n)
    
    print("\n" + "=" * 80)
    print("TOP COEFFICIENTS (feature -> log-odds)")
    print("=" * 80)
    
    if intercept is not None:
        print(f"\nIntercept: {intercept:.4f}")
    
    print(f"\nTop {n} POSITIVE (increase probability):")
    print(f"{'Feature':<40} {'Coefficient':<12}")
    print("-" * 52)
    if top_pos:
        display_count = min(len(top_pos), n)
        if display_count < n:
            print(f"  (only {display_count} positive coefficients available)")
        for feat, coef in top_pos:
            print(f"{feat:<40} {coef:>12.4f}")
    else:
        print("  (no positive coefficients)")
    
    print(f"\nTop {n} NEGATIVE (decrease probability):")
    print(f"{'Feature':<40} {'Coefficient':<12}")
    print("-" * 52)
    if top_neg:
        display_count = min(len(top_neg), n)
        if display_count < n:
            print(f"  (only {display_count} negative coefficients available)")
        for feat, coef in top_neg:
            print(f"{feat:<40} {coef:>12.4f}")
    else:
        print("  (no negative coefficients)")
    
    print("\nNote: Coefficients are for standardized features (StandardScaler applied).")
    print("=" * 80)


def save_coefficients(coef_dict, output_path=None):
    """
    Save coefficients to JSON file.
    
    Args:
        coef_dict: Dict mapping feature name to coefficient
        output_path: Path to save JSON (defaults to OUTPUT_DIR/coefficients.json)
    """
    if output_path is None:
        output_path = OUTPUT_DIR / "coefficients.json"
    
    # Convert to sorted list for readability
    coef_list = sorted(coef_dict.items(), key=lambda x: x[1], reverse=True)
    coef_json = {
        "coefficients": [{"feature": feat, "coefficient": float(coef)} for feat, coef in coef_list],
        "n_features": len(coef_dict),
    }
    
    with open(output_path, "w") as f:
        json.dump(coef_json, f, indent=2)
    
    print(f"\nSaved coefficients to {output_path}")
