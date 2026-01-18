"""
CLI entrypoint for ML pipeline.
"""
import argparse
import json
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
from .config import (
    OUTPUT_DIR, LABEL_FIELD, MIN_TRAIN_SIZE, TEST_CHUNK_SIZE
)
from .data import load_events_df, get_base_features
from .features import select_base_features, rolling_features, finalize_matrix, verify_no_leakage
from .backtest import walk_forward_backtest
from .train import train_model
from .ablation import run_ablation_study
from .interpretability import extract_coefficients, print_coefficients_table, save_coefficients
from .summary import create_ablation_summary
from .picks import run_picks_analysis, save_picks_results, print_picks_summary


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
    
    # Task 1: Run ablation study FIRST to find best model
    print("\n5. Running ablation study to find best model...")
    ablation_results = run_ablation_study(
        df_final,
        LABEL_FIELD,
        feature_cols,
    )
    
    # Find best model (by LogLoss)
    best_result = min(ablation_results, key=lambda x: x['log_loss'])
    best_feature_set_name = best_result['feature_set']
    best_variant = best_result['variant']
    print(f"\nBest model identified: {best_feature_set_name} ({best_variant})")
    print(f"  Log Loss: {best_result['log_loss']:.3f}, AUC: {best_result.get('roc_auc', 'N/A')}")
    
    # Get best feature set columns
    from .ablation import (
        get_feature_set_A_line_only,
        get_feature_set_B_line_plus_context,
        get_feature_set_C_line_plus_rolling_totals,
        get_feature_set_D_full_model,
    )
    
    if "A: line_only" in best_feature_set_name:
        best_feature_cols = get_feature_set_A_line_only(df_final, feature_cols)
    elif "B: line_plus_context" in best_feature_set_name:
        best_feature_cols = get_feature_set_B_line_plus_context(df_final, feature_cols)
    elif "C: line_plus_rolling_totals" in best_feature_set_name:
        best_feature_cols = get_feature_set_C_line_plus_rolling_totals(df_final, feature_cols)
    else:  # D: full_model
        best_feature_cols = get_feature_set_D_full_model(df_final, feature_cols)
    
    # Task 1: Run backtest with BEST feature set for artifacts
    print(f"\n6. Running walk-forward backtest with best feature set ({len(best_feature_cols)} features)...")
    
    # Filter df_final for best feature set
    metadata_cols = [LABEL_FIELD, "date", "team_id", "game_id", "TEAM_TOTAL_LINE"]
    cols_needed = best_feature_cols + [c for c in metadata_cols if c not in best_feature_cols]
    cols_available = [c for c in cols_needed if c in df_final.columns]
    seen = set()
    cols_unique = [c for c in cols_available if c not in seen and not seen.add(c)]
    df_best = df_final[cols_unique].copy()
    
    predictions_df, metrics_dict, calibration_df = walk_forward_backtest(
        df_best,
        best_feature_cols,
        LABEL_FIELD,
        min_train_size=MIN_TRAIN_SIZE,
        test_chunk_size=TEST_CHUNK_SIZE,
    )
    
    # Save predictions (from best model)
    print("\n7. Saving artifacts from best model...")
    predictions_path = OUTPUT_DIR / "predictions.csv"
    predictions_df.to_csv(predictions_path, index=False)
    print(f"  Saved predictions to {predictions_path}")
    
    # Save metrics (convert to JSON-safe format)
    metrics_path = OUTPUT_DIR / "metrics.json"
    
    def make_json_safe(obj):
        """Recursively convert objects to JSON-safe types."""
        if isinstance(obj, dict):
            return {k: make_json_safe(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [make_json_safe(item) for item in obj]
        elif isinstance(obj, (pd.DataFrame, pd.Series)):
            # Convert pandas objects to dict/list
            if isinstance(obj, pd.DataFrame):
                return obj.to_dict("records")
            else:
                return obj.tolist()
        elif isinstance(obj, (np.integer, np.floating)):
            return float(obj) if isinstance(obj, np.floating) else int(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            # Fallback: convert to string
            return str(obj)
    
    # Convert metrics_dict to JSON-safe format (handles circular refs by copying)
    import copy
    metrics_dict_copy = copy.deepcopy(metrics_dict)
    metrics_safe = make_json_safe(metrics_dict_copy)
    
    # Ensure fold_metrics is handled if it exists
    if "fold_metrics" in metrics_dict:
        # If fold_metrics is a DataFrame, convert it
        if isinstance(metrics_dict["fold_metrics"], pd.DataFrame):
            metrics_safe["fold_metrics"] = metrics_dict["fold_metrics"].to_dict("records")
    
    # Add best feature set info
    metrics_safe["best_feature_set"] = best_feature_set_name
    metrics_safe["best_variant"] = best_variant
    
    with open(metrics_path, "w") as f:
        json.dump(metrics_safe, f, indent=2)
    print(f"  Saved metrics to {metrics_path}")
    
    # Save calibration (from best model)
    calibration_path = OUTPUT_DIR / "calibration.csv"
    calibration_df.to_csv(calibration_path, index=False)
    print(f"  Saved calibration to {calibration_path}")
    
    # Task 2: Extract and save coefficients from best model
    print("\n8. Extracting coefficients from best model...")
    # Train final model on all data with best feature set
    X_best = df_best[best_feature_cols].copy()
    y_best = df_best[LABEL_FIELD].copy()
    final_model = train_model(X_best, y_best)
    
    # Extract coefficients
    coef_dict = extract_coefficients(final_model, best_feature_cols)
    print_coefficients_table(coef_dict, n=10)
    save_coefficients(coef_dict)
    
    # Save final model
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
    
    # Task 3: Save ablation summary markdown
    print("\n9. Creating ablation summary...")
    ablation_summary_path = OUTPUT_DIR / "ablation_summary.md"
    create_ablation_summary(ablation_results, best_result, ablation_summary_path)
    print(f"  Saved ablation summary to {ablation_summary_path}")
    
    # Save ablation results JSON
    ablation_path = OUTPUT_DIR / "ablation_results.json"
    with open(ablation_path, "w") as f:
        json.dump(ablation_results, f, indent=2, default=str)
    print(f"  Saved ablation results to {ablation_path}")
    
    # Task 3: Run picks analysis
    print("\n10. Running picks analysis...")
    picks_results, decile_df = run_picks_analysis()
    save_picks_results(picks_results, decile_df)
    print_picks_summary(picks_results)
    
    print(f"\nArtifacts saved to: {OUTPUT_DIR}")
    print("\nDone!")


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="ML pipeline for NBA betting analytics")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Backtest command
    backtest_parser = subparsers.add_parser("backtest", help="Run walk-forward backtest")
    # Add any backtest-specific args here if needed
    
    # Inspect data command
    inspect_parser = subparsers.add_parser("inspect_data", help="Inspect data without running pipeline")
    
    args = parser.parse_args()
    
    if args.command == "backtest":
        cmd_backtest(args)
    elif args.command == "inspect_data":
        from .inspect import cmd_inspect_data
        cmd_inspect_data(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
