"""
Model inference for future games.
Loads saved model.joblib and generates predictions for upcoming games.
"""
import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from typing import Dict, List, Optional
from backend.ml.config import OUTPUT_DIR, LABEL_FIELD
from backend.ml.data import load_events_df
from backend.ml.features import select_base_features, rolling_features

MODEL_PATH = OUTPUT_DIR / "model.joblib"


def load_model():
    """Load the saved model from model.joblib."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Run backtest first to generate model.")
    
    model = joblib.load(MODEL_PATH)
    return model


def prepare_future_features(df_future, df_history=None):
    """
    Prepare features for future games.
    
    If df_history is provided, append future rows in chronological order per TEAM_ID
    to compute rolling features without leakage (rolling uses only past games).
    
    Args:
        df_future: DataFrame with future games (must have date, team_id, game_id, TEAM_TOTAL_LINE, etc.)
        df_history: Optional DataFrame with historical games for rolling feature computation
        
    Returns:
        DataFrame with features ready for prediction (same columns as training)
    """
    from .features import select_base_features, rolling_features
    
    # If history provided, append future to history for rolling computation
    if df_history is not None and len(df_history) > 0:
        # Ensure history is sorted by date
        if "date" in df_history.columns:
            df_history = df_history.sort_values(["team_id", "date"], ascending=[True, True]).reset_index(drop=True)
        
        # Append future rows
        df_combined = pd.concat([df_history, df_future], ignore_index=True)
        df_combined = df_combined.sort_values(["team_id", "date"], ascending=[True, True], na_position="last").reset_index(drop=True)
        
        # Compute rolling features on combined (rolling for future rows uses only history)
        df_combined = rolling_features(df_combined, team_id_col="team_id")
        
        # Extract future rows (after history)
        future_start_idx = len(df_history)
        df_future_with_features = df_combined.iloc[future_start_idx:].copy()
    else:
        # No history - just compute base features (rolling will be NaNs)
        df_future_with_features = df_future.copy()
        df_future_with_features = select_base_features(df_future_with_features)
        # Try rolling anyway (will have NaNs for first games)
        df_future_with_features = rolling_features(df_future_with_features, team_id_col="team_id")
    
    return df_future_with_features


def predict_future_games(df_future, df_history=None, feature_cols=None):
    """
    Generate predictions for future games.
    
    Args:
        df_future: DataFrame with future games (must have date, team_id, game_id, TEAM_TOTAL_LINE)
        df_history: Optional DataFrame with historical games for rolling features
        feature_cols: Optional list of feature columns (auto-detected from model if None)
        
    Returns:
        DataFrame with predictions added (columns: game_id, team_id, date, p_hat, confidence, recommended_side, etc.)
    """
    # Load model
    model = load_model()
    
    # Prepare features
    df_features = prepare_future_features(df_future, df_history)
    
    # Auto-detect feature columns from model if not provided
    if feature_cols is None:
        # Try to get feature names from model (if it's a Pipeline with ColumnTransformer)
        try:
            preprocessor = model.named_steps.get("preprocessor")
            if preprocessor is not None:
                # Extract feature names from ColumnTransformer
                feature_cols = []
                for name, transformer, cols in preprocessor.transformers:
                    if hasattr(transformer, 'get_feature_names_out'):
                        feature_cols.extend(transformer.get_feature_names_out(cols))
                    else:
                        feature_cols.extend(cols if isinstance(cols, list) else [cols])
        except Exception:
            # Fallback: use all numeric columns except metadata
            exclude = ["game_id", "team_id", "date", LABEL_FIELD, "TEAM_TOTAL_ACTUAL", "GAME_TOTAL_ACTUAL"]
            feature_cols = [col for col in df_features.columns if col not in exclude and df_features[col].dtype in ["int64", "float64"]]
            # Remove duplicate feature names
            feature_cols = list(dict.fromkeys(feature_cols))  # Preserves order
    
    # Filter to available features
    available_features = [col for col in feature_cols if col in df_features.columns]
    missing_features = [col for col in feature_cols if col not in df_features.columns]
    
    if missing_features:
        print(f"WARNING: Missing {len(missing_features)} features, using {len(available_features)} available features")
        print(f"  Missing: {missing_features[:10]}...")
    
    # Get feature matrix
    X_future = df_features[available_features].copy()
    
    # Predict probabilities
    try:
        proba = model.predict_proba(X_future)
        p_hat = proba[:, 1] if proba.shape[1] > 1 else proba[:, 0]
    except Exception as e:
        print(f"ERROR in prediction: {e}")
        raise
    
    # Create results DataFrame
    results = df_future[["game_id", "team_id", "date"]].copy() if all(c in df_future.columns for c in ["game_id", "team_id", "date"]) else df_future[["game_id", "team_id"]].copy()
    
    # Add prediction columns
    results["p_hat"] = p_hat
    results["confidence"] = np.abs(p_hat - 0.5)  # Distance from 0.5
    results["recommended_side"] = np.where(p_hat >= 0.5, "OVER", "UNDER")
    
    # Add market info if available
    if "TEAM_TOTAL_LINE" in df_future.columns:
        results["TEAM_TOTAL_LINE"] = df_future["TEAM_TOTAL_LINE"]
    if "GAME_TOTAL_LINE" in df_future.columns:
        results["GAME_TOTAL_LINE"] = df_future["GAME_TOTAL_LINE"]
    if "TEAM_ABBREVIATION" in df_future.columns:
        results["TEAM_ABBREVIATION"] = df_future["TEAM_ABBREVIATION"]
    
    # Hypothetical EV (assuming -110 odds, payout 0.9091)
    # EV = p * 0.9091 - (1-p) * 1.0
    results["hypothetical_ev"] = p_hat * 0.9091 - (1 - p_hat) * 1.0
    
    return results
