"""
ML Dashboard API endpoints.
Separate module for ML dashboard to keep main.py clean.
"""
from fastapi import Query, HTTPException
from pathlib import Path
import json
import pandas as pd
import os
from datetime import datetime

# ML artifacts path (relative to project root)
ML_ARTIFACTS_DIR = Path(__file__).parent.parent / "ml" / "artifacts"


def make_json_safe(obj):
    """Convert pandas/numpy types to JSON-safe Python types."""
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_safe(item) for item in obj]
    elif isinstance(obj, pd.Series):
        return obj.tolist()
    elif isinstance(obj, (pd.Timestamp, pd.Timedelta)):
        return str(obj)
    elif pd.isna(obj):
        return None
    elif isinstance(obj, (int, float)):
        if pd.api.types.is_integer_dtype(type(obj)):
            return int(obj)
        return float(obj)
    elif isinstance(obj, (str, bool, type(None))):
        return obj
    else:
        return str(obj)


def get_ml_metrics():
    """Get ML metrics from metrics.json."""
    metrics_path = ML_ARTIFACTS_DIR / "metrics.json"
    if not metrics_path.exists():
        raise HTTPException(status_code=404, detail="metrics.json not found")
    
    with open(metrics_path, "r") as f:
        return json.load(f)


def get_predictions(limit: int = 1000):
    """Get predictions from predictions.csv as JSON."""
    predictions_path = ML_ARTIFACTS_DIR / "predictions.csv"
    if not predictions_path.exists():
        raise HTTPException(status_code=404, detail="predictions.csv not found")
    
    df = pd.read_csv(predictions_path)
    
    # Limit rows
    if len(df) > limit:
        df = df.head(limit)
    
    # Convert to dict records (JSON-safe)
    records = df.to_dict("records")
    
    # Convert numpy/pandas types to Python types
    for record in records:
        for k, v in record.items():
            if pd.isna(v):
                record[k] = None
            elif isinstance(v, (pd.Timestamp, pd.Timedelta)):
                record[k] = str(v)
            elif isinstance(v, (int, float)):
                if pd.api.types.is_integer_dtype(type(v)):
                    record[k] = int(v)
                else:
                    record[k] = float(v)
    
    return {"predictions": records, "total": len(df), "returned": len(records)}


def get_calibration():
    """Get calibration table from calibration.csv as JSON."""
    calibration_path = ML_ARTIFACTS_DIR / "calibration.csv"
    if not calibration_path.exists():
        raise HTTPException(status_code=404, detail="calibration.csv not found")
    
    df = pd.read_csv(calibration_path)
    return df.to_dict("records")


def get_ablation():
    """Get ablation results from ablation_results.json."""
    ablation_path = ML_ARTIFACTS_DIR / "ablation_results.json"
    if not ablation_path.exists():
        raise HTTPException(status_code=404, detail="ablation_results.json not found")
    
    with open(ablation_path, "r") as f:
        return json.load(f)


def get_deciles():
    """Get deciles analysis from picks_by_decile.csv as JSON."""
    deciles_path = ML_ARTIFACTS_DIR / "picks_by_decile.csv"
    if not deciles_path.exists():
        raise HTTPException(status_code=404, detail="picks_by_decile.csv not found")
    
    df = pd.read_csv(deciles_path)
    return df.to_dict("records")


def get_picks_summary():
    """Get picks summary from picks_summary.json."""
    picks_path = ML_ARTIFACTS_DIR / "picks_summary.json"
    if not picks_path.exists():
        raise HTTPException(status_code=404, detail="picks_summary.json not found")
    
    with open(picks_path, "r") as f:
        return json.load(f)


def get_coefficients():
    """Get model coefficients from coefficients.json."""
    coefficients_path = ML_ARTIFACTS_DIR / "coefficients.json"
    if not coefficients_path.exists():
        raise HTTPException(status_code=404, detail="coefficients.json not found")
    
    with open(coefficients_path, "r") as f:
        return json.load(f)


def get_timeframe():
    """Get timeframe (min/max date) from metrics.json or predictions.csv."""
    # Try metrics.json first
    metrics_path = ML_ARTIFACTS_DIR / "metrics.json"
    if metrics_path.exists():
        with open(metrics_path, "r") as f:
            metrics = json.load(f)
            # Check if timeframe is in metrics
            if "timeframe" in metrics:
                return metrics["timeframe"]
    
    # Fall back to predictions.csv
    predictions_path = ML_ARTIFACTS_DIR / "predictions.csv"
    if predictions_path.exists():
        df = pd.read_csv(predictions_path)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            valid_dates = df["date"].dropna()
            if len(valid_dates) > 0:
                return {
                    "min_date": str(valid_dates.min().date()),
                    "max_date": str(valid_dates.max().date()),
                    "n_samples": len(df)
                }
    
    return {"min_date": None, "max_date": None, "n_samples": 0}


def get_picks(limit=100, sort="confidence", threshold=None, topk=None):
    """
    Get example picks from predictions.csv.
    
    Args:
        limit: Max number of picks to return
        sort: Sort by "confidence" (descending |p-0.5|) or "date"
        threshold: Filter picks where |p-0.5| >= threshold (0 to 0.5)
        topk: Return top K picks by confidence
    """
    predictions_path = ML_ARTIFACTS_DIR / "predictions.csv"
    if not predictions_path.exists():
        raise HTTPException(status_code=404, detail="predictions.csv not found")
    
    df = pd.read_csv(predictions_path)
    
    # Compute confidence (distance from 0.5)
    if "p_hat" in df.columns:
        df["confidence"] = (df["p_hat"] - 0.5).abs()
        df["predicted_side"] = df["p_hat"].apply(lambda p: "OVER" if p >= 0.5 else "UNDER")
    else:
        df["confidence"] = 0.0
        df["predicted_side"] = "UNKNOWN"
    
    # Apply threshold filter
    if threshold is not None:
        df = df[df["confidence"] >= threshold]
    
    # Sort
    if sort == "confidence":
        df = df.sort_values("confidence", ascending=False)
    elif sort == "date" and "date" in df.columns:
        df = df.sort_values("date", ascending=False)
    
    # Apply topk
    if topk is not None:
        df = df.head(topk)
    else:
        df = df.head(limit)
    
    # Convert to records (JSON-safe)
    records = df.to_dict("records")
    for record in records:
        for k, v in record.items():
            if pd.isna(v):
                record[k] = None
            elif isinstance(v, (pd.Timestamp, pd.Timedelta)):
                record[k] = str(v)
            elif isinstance(v, (int, float)):
                if pd.api.types.is_integer_dtype(type(v)):
                    record[k] = int(v)
                else:
                    record[k] = float(v)
    
    return {"picks": records, "total": len(df), "returned": len(records)}


def get_future_games(date_from=None, date_to=None, min_confidence=0.0, limit=100):
    """
    Get future games with predictions.
    
    Loads future games from:
    1. MongoDB db.games collection (filtered by GAME_DATE > today)
    2. Or CSV file at ML_FUTURE_GAMES_CSV env var path
    
    Args:
        date_from: Filter games from this date (YYYY-MM-DD)
        date_to: Filter games to this date (YYYY-MM-DD)
        min_confidence: Minimum confidence |p-0.5| (0 to 0.5)
        limit: Max games to return
        
    Returns:
        Dict with games list and metadata
    """
    try:
        from app.db import db
        from backend.ml.predict import predict_future_games
        from backend.ml.data import load_events_df
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"ML prediction module not available: {e}")
    
    # Try to load future games from MongoDB or CSV
    df_future = None
    
    # Option 1: Try CSV file (env var ML_FUTURE_GAMES_CSV)
    csv_path = os.getenv("ML_FUTURE_GAMES_CSV")
    if csv_path and Path(csv_path).exists():
        print(f"Loading future games from CSV: {csv_path}")
        df_future = pd.read_csv(csv_path)
        # Ensure date column
        if "GAME_DATE" in df_future.columns:
            df_future["date"] = pd.to_datetime(df_future["GAME_DATE"], errors="coerce")
        elif "date" not in df_future.columns:
            raise ValueError("CSV must have GAME_DATE or date column")
    else:
        # Option 2: Try MongoDB games collection
        try:
            today = datetime.now().date()
            query = {"GAME_DATE": {"$gte": datetime.combine(today, datetime.min.time())}}
            
            # Apply date filters
            if date_from:
                query["GAME_DATE"]["$gte"] = datetime.strptime(date_from, "%Y-%m-%d")
            if date_to:
                if "$gte" not in query["GAME_DATE"]:
                    query["GAME_DATE"] = {}
                query["GAME_DATE"]["$lte"] = datetime.strptime(date_to, "%Y-%m-%d")
            
            games_cursor = db.games.find(query).limit(limit * 2)  # Get extra for filtering
            games_list = list(games_cursor)
            
            if games_list:
                print(f"Loading {len(games_list)} future games from MongoDB")
                df_future = pd.DataFrame(games_list)
                
                # Convert GAME_DATE to date column
                if "GAME_DATE" in df_future.columns:
                    df_future["date"] = pd.to_datetime(df_future["GAME_DATE"], errors="coerce")
                
                # Ensure required columns exist
                if "GAME_ID" in df_future.columns:
                    df_future["game_id"] = df_future["GAME_ID"].astype(str)
                if "TEAM_ID" in df_future.columns:
                    df_future["team_id"] = df_future["TEAM_ID"].astype(str)
        except Exception as e:
            print(f"WARNING: Could not load from MongoDB: {e}")
    
    if df_future is None or len(df_future) == 0:
        raise HTTPException(
            status_code=404,
            detail="No future games found. Set ML_FUTURE_GAMES_CSV env var or ensure MongoDB games collection has future games."
        )
    
    # Ensure required columns
    required_cols = ["game_id", "team_id", "date"]
    for col in required_cols:
        if col not in df_future.columns:
            raise HTTPException(status_code=400, detail=f"Missing required column: {col}")
    
    # Add TEAM_TOTAL_LINE if missing (required for model)
    if "TEAM_TOTAL_LINE" not in df_future.columns:
        # Try to get from events or use default
        print("WARNING: TEAM_TOTAL_LINE not found, using placeholder 110.0")
        df_future["TEAM_TOTAL_LINE"] = 110.0
    
    # Load historical data for rolling features
    try:
        df_history = load_events_df()
        print(f"Loaded {len(df_history)} historical events for rolling features")
    except Exception as e:
        print(f"WARNING: Could not load history: {e}. Rolling features will be NaNs.")
        df_history = None
    
    # Generate predictions
    try:
        results = predict_future_games(df_future, df_history=df_history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")
    
    # Apply filters
    if min_confidence > 0:
        results = results[results["confidence"] >= min_confidence]
    
    if date_from:
        results = results[results["date"] >= pd.to_datetime(date_from)]
    if date_to:
        results = results[results["date"] <= pd.to_datetime(date_to)]
    
    # Limit results
    results = results.head(limit)
    
    # Convert to JSON-safe records
    records = results.to_dict("records")
    for record in records:
        for k, v in record.items():
            if pd.isna(v):
                record[k] = None
            elif isinstance(v, (pd.Timestamp, pd.Timedelta)):
                record[k] = str(v.date()) if isinstance(v, pd.Timestamp) else str(v)
            elif isinstance(v, (int, float)):
                if pd.api.types.is_integer_dtype(type(v)):
                    record[k] = int(v)
                else:
                    record[k] = float(v)
    
    return {
        "games": records,
        "total": len(results),
        "meta": {
            "date_from": date_from,
            "date_to": date_to,
            "min_confidence": min_confidence,
            "limit": limit,
        }
    }
