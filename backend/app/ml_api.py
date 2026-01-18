"""
ML Dashboard API endpoints.
Separate module for ML dashboard to keep main.py clean.
"""
from fastapi import Query, HTTPException
from pathlib import Path
import json
import pandas as pd

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
