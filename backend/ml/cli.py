"""
CLI entrypoint for ML pipeline.
"""
import argparse
import json
import sys
from pathlib import Path
import pandas as pd
import joblib
from .config import (
    OUTPUT_DIR, LABEL_FIELD, MIN_TRAIN_SIZE, TEST_CHUNK_SIZE
)
from .data import load_events_df, get_base_features
from .features import select_base_features, rolling_features, finalize_matrix, verify_no_leakage
from .backtest import walk_forward_backtest
from .train import train_model
from .ablation import run_ablation_study


def print_summary(df, label_col):
    """Print data summary."""
    print("\n" + "=" * 80)
    print("DATA SUMMARY")
    print("=" * 80)
    print(f"Total rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")
    print(f"\nDate range: {df['date'].min()} to {df['date'].max()}")
    print(f"Unique games: {df['game_id'].nunique()}")
    print(f"Unique teams: {df['team_id'].nunique()}")
    
    if label_col in df.columns:
        label_counts = df[label_col].value_counts()
        label_mean = df[label_col].mean()
        print(f"\nLabel ({label_col}):")
        print(f"  Mean: {label_mean:.3f}")
        print(f"  Distribution: {label_counts.to_dict()}")
    
    print("\nSample columns:")
    print(f"  {df.columns.tolist()[:20]}")
    print("=" * 80)


def cmd_backtest(args):
    """Run walk-forward backtest."""
    print("Starting ML backtest pipeline...")
    
    # Load data
    print("\n1. Loading data...")
    df = load_events_df()
    
    # Print summary
    print_summary(df, LABEL_FIELD)
    
    # Build features
    print("\n2. Building features...")
    df = select_base_features(df)
    df = rolling_features(df, team_id_col="team_id", windows=[5, 10])
    
    # Verify no leakage (spot check)
    print("\n3. Verifying no leakage...")
    rolling_cols = [col for col in df.columns if col.startswith("rolling_")]
    if rolling_cols:
        sample_col = rolling_cols[0]
        verify_no_leakage(df, sample_col, LABEL_FIELD, team_id_col="team_id", n_check=5)
    
    # Finalize matrix
    print("\n4. Finalizing feature matrix...")
    X, y, meta = finalize_matrix(df, LABEL_FIELD)
    
    # Get feature column names
    feature_cols = X.columns.tolist()
    print(f"  Feature columns ({len(feature_cols)}): {feature_cols[:10]}...")
    
    # Merge X, y, meta for backtest
    df_final = pd.concat([X, y, meta], axis=1)
    
    # Task 1: Test multiple C values (keep default for main backtest, test others separately)
    # Run backtest with default C (from config, default 0.1)
    print("\n5. Running walk-forward backtest...")
    predictions_df, metrics_dict, calibration_df = walk_forward_backtest(
        df_final,
        feature_cols,
        LABEL_FIELD,
        min_train_size=MIN_TRAIN_SIZE,
        test_chunk_size=TEST_CHUNK_SIZE,
    )
    
    # Save predictions
    print("\n6. Saving artifacts...")
    predictions_path = OUTPUT_DIR / "predictions.csv"
    predictions_df.to_csv(predictions_path, index=False)
    print(f"  Saved predictions to {predictions_path}")
    
    # Save metrics (convert to JSON-safe format)
    metrics_path = OUTPUT_DIR / "metrics.json"
    # Remove fold_metrics DataFrame if present (already serialized as list of dicts)
    metrics_safe = {k: v for k, v in metrics_dict.items() if k != "fold_metrics"}
    if "fold_metrics" in metrics_dict:
        metrics_safe["fold_metrics"] = metrics_dict["fold_metrics"]
    with open(metrics_path, "w") as f:
        json.dump(metrics_safe, f, indent=2, default=str)
    print(f"  Saved metrics to {metrics_path}")
    
    # Save calibration
    calibration_path = OUTPUT_DIR / "calibration.csv"
    calibration_df.to_csv(calibration_path, index=False)
    print(f"  Saved calibration to {calibration_path}")
    
    # Train final model on all data and save
    print("\n7. Training final model on all data...")
    final_model = train_model(X, y)
    model_path = OUTPUT_DIR / "model.joblib"
    joblib.dump(final_model, model_path)
    print(f"  Saved model to {model_path}")
    
    # Task 1: Print final summary using selected model metrics
    selected_model = metrics_dict.get("selected_model", "uncalibrated")
    selected_metrics = metrics_dict.get("selected_model_metrics", metrics_dict)
    
    print("\n" + "=" * 80)
    print("BACKTEST SUMMARY")
    print(f"Selected model: {selected_model} (by LogLoss)")
    print("=" * 80)
    print(f"Accuracy: {selected_metrics['accuracy']:.3f}")
    print(f"Log Loss: {selected_metrics['log_loss']:.3f}")
    if selected_metrics.get("roc_auc") is not None:
        print(f"ROC-AUC: {selected_metrics['roc_auc']:.3f}")
    print(f"Number of folds: {metrics_dict['n_folds']}")
    print(f"Total predictions: {len(predictions_df)}")
    print("=" * 80)
    
    print("\nCalibration table (first 5 bins):")
    print(calibration_df.head().to_string())
    
    # Task 2: Run ablation study
    print("\n8. Running ablation study...")
    ablation_results = run_ablation_study(
        df_final,
        LABEL_FIELD,
        feature_cols,
    )
    
    # Save ablation results
    ablation_path = OUTPUT_DIR / "ablation_results.json"
    with open(ablation_path, "w") as f:
        json.dump(ablation_results, f, indent=2, default=str)
    print(f"  Saved ablation results to {ablation_path}")
    
    print(f"\nArtifacts saved to: {OUTPUT_DIR}")
    print("\nDone!")


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="ML pipeline for NBA betting analytics")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Backtest command
    backtest_parser = subparsers.add_parser("backtest", help="Run walk-forward backtest")
    # Add any backtest-specific args here if needed
    
    args = parser.parse_args()
    
    if args.command == "backtest":
        cmd_backtest(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
