"""
Walk-forward backtest with expanding window.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from .config import MIN_TRAIN_SIZE, TEST_CHUNK_SIZE
from .train import train_model, predict_proba, train_calibrated_model
from .metrics import compute_all_metrics


def walk_forward_backtest(df, feature_cols, label_col, min_train_size=None, test_chunk_size=None):
    """
    Run walk-forward backtest with expanding window.
    
    Args:
        df: DataFrame sorted by date with features and label
        feature_cols: List of feature column names
        label_col: Column name for label
        min_train_size: Minimum training set size (defaults to config)
        test_chunk_size: Test chunk size in rows (defaults to config)
        
    Returns:
        Tuple of (predictions_df, metrics_dict, calibration_df)
    """
    if min_train_size is None:
        min_train_size = MIN_TRAIN_SIZE
    if test_chunk_size is None:
        test_chunk_size = TEST_CHUNK_SIZE
    
    print(f"\nWalk-forward backtest:")
    print(f"  Min train size: {min_train_size}")
    print(f"  Test chunk size: {test_chunk_size}")
    print(f"  Total rows: {len(df)}")
    
    # Ensure df is sorted by date
    df = df.sort_values("date").reset_index(drop=True)
    
    # Adjust min_train_size if dataset is too small
    # Use 80% of data for training minimum if dataset < min_train_size
    if len(df) < min_train_size:
        adjusted_min_train_size = max(100, int(len(df) * 0.8))
        print(f"  WARNING: Dataset has {len(df)} rows < {min_train_size}, adjusting min_train_size to {adjusted_min_train_size}")
        min_train_size = adjusted_min_train_size
    
    # Extract feature matrix and labels
    X = df[feature_cols].copy()
    y = df[label_col].copy()
    meta = df[["date", "team_id", "game_id", "TEAM_TOTAL_LINE"]].copy() if all(c in df.columns for c in ["date", "team_id", "game_id", "TEAM_TOTAL_LINE"]) else df[["date"]].copy()
    
    # Store all predictions
    all_predictions = []
    all_y_true = []
    all_y_pred_proba = []
    fold_metrics = []
    
    # Task 5: Store baseline predictions
    all_baseline_05_proba = []
    all_baseline_line_proba = []
    
    # Task 2: Store calibrated predictions
    all_y_pred_proba_sigmoid = []
    all_y_pred_proba_isotonic = []
    
    # Walk-forward: expanding window
    train_start = 0
    test_start = min_train_size
    fold = 0
    
    # If we still don't have enough data, use single train/test split
    if test_start >= len(df):
        # Use 80/20 split
        split_idx = int(len(df) * 0.8)
        print(f"  WARNING: Dataset too small for multiple folds, using single 80/20 split (train={split_idx}, test={len(df)-split_idx})")
        test_start = split_idx
    
    while test_start < len(df):
        test_end = min(test_start + test_chunk_size, len(df))
        
        # Training set: all data up to test_start
        train_indices = range(train_start, test_start)
        test_indices = range(test_start, test_end)
        
        X_train = X.iloc[train_indices].copy()
        y_train = y.iloc[train_indices].copy()
        X_test = X.iloc[test_indices].copy()
        y_test = y.iloc[test_indices].copy()
        meta_test = meta.iloc[test_indices].copy()
        
        if len(X_train) < min_train_size:
            print(f"  Fold {fold}: Skipping (train size {len(X_train)} < {min_train_size})")
            test_start = test_end
            continue
        
        print(f"  Fold {fold}: train=[{train_start}:{test_start}] ({len(X_train)} rows), test=[{test_start}:{test_end}] ({len(X_test)} rows)")
        
        # Task 5: Baseline A - Constant probability 0.5
        baseline_05_proba = np.full(len(y_test), 0.5)
        
        # Task 5: Baseline B - Line-only model (TEAM_TOTAL_LINE, GAME_TOTAL_LINE if available)
        baseline_line_feature_cols = []
        if "TEAM_TOTAL_LINE" in X_test.columns:
            baseline_line_feature_cols.append("TEAM_TOTAL_LINE")
        if "GAME_TOTAL_LINE" in X_test.columns:
            baseline_line_feature_cols.append("GAME_TOTAL_LINE")
        
        baseline_line_proba = None
        if baseline_line_feature_cols:
            try:
                X_train_line = X_train[baseline_line_feature_cols].copy()
                X_test_line = X_test[baseline_line_feature_cols].copy()
                baseline_line_model = train_model(X_train_line, y_train)
                baseline_line_proba_array = predict_proba(baseline_line_model, X_test_line)
                baseline_line_proba = baseline_line_proba_array[:, 1]
            except Exception as e:
                print(f"    WARNING: Line-only baseline failed: {e}")
                baseline_line_proba = baseline_05_proba.copy()  # Fallback to 0.5
        else:
            baseline_line_proba = baseline_05_proba.copy()  # Fallback to 0.5
        
        # Task 1: Test multiple C values - use default C for now (we'll test multiple in CLI)
        # Task 2: Add calibration inside each fold
        try:
            # Split train into train_fit (80%) and train_cal (20%) for calibration
            train_fit_size = int(len(X_train) * 0.8)
            X_train_fit = X_train.iloc[:train_fit_size].copy()
            y_train_fit = y_train.iloc[:train_fit_size].copy()
            X_train_cal = X_train.iloc[train_fit_size:].copy()
            y_train_cal = y_train.iloc[train_fit_size:].copy()
            
            # Train base model on train_fit
            model = train_model(X_train_fit, y_train_fit)
            
            # Predict uncalibrated
            proba = predict_proba(model, X_test)
            y_pred_proba = proba[:, 1]  # Probability of class 1
            
            # Task 2: Calibrate on train_cal (sigmoid and isotonic)
            y_pred_proba_sigmoid = y_pred_proba.copy()
            y_pred_proba_isotonic = y_pred_proba.copy()
            
            if len(X_train_cal) > 10:  # Need minimum samples for calibration
                try:
                    # Sigmoid calibration
                    calibrated_sigmoid = train_calibrated_model(model, X_train_cal, y_train_cal, method="sigmoid")
                    proba_sigmoid = predict_proba(calibrated_sigmoid, X_test)
                    y_pred_proba_sigmoid = proba_sigmoid[:, 1]
                except Exception as e:
                    print(f"      WARNING: Sigmoid calibration failed: {e}")
                
                try:
                    # Isotonic calibration
                    calibrated_isotonic = train_calibrated_model(model, X_train_cal, y_train_cal, method="isotonic")
                    proba_isotonic = predict_proba(calibrated_isotonic, X_test)
                    y_pred_proba_isotonic = proba_isotonic[:, 1]
                except Exception as e:
                    print(f"      WARNING: Isotonic calibration failed: {e}")
            
            # Compute fold metrics (uncalibrated)
            fold_metrics_dict, fold_calibration = compute_all_metrics(y_test, y_pred_proba)
            fold_metrics_dict["fold"] = fold
            fold_metrics_dict["train_size"] = len(X_train)
            fold_metrics_dict["test_size"] = len(X_test)
            fold_metrics.append(fold_metrics_dict)
            
            print(f"    Accuracy: {fold_metrics_dict['accuracy']:.3f}, Log Loss: {fold_metrics_dict['log_loss']:.3f}")
            if fold_metrics_dict["roc_auc"] is not None:
                print(f"    ROC-AUC: {fold_metrics_dict['roc_auc']:.3f}")
            
            # Store predictions (uncalibrated for now, we'll add calibrated columns later)
            fold_predictions = meta_test.copy()
            fold_predictions["y_true"] = y_test.values
            fold_predictions["p_hat"] = y_pred_proba
            fold_predictions["p_hat_sigmoid"] = y_pred_proba_sigmoid
            fold_predictions["p_hat_isotonic"] = y_pred_proba_isotonic
            fold_predictions["fold"] = fold
            all_predictions.append(fold_predictions)
            
            all_y_true.extend(y_test.values.tolist())
            all_y_pred_proba.extend(y_pred_proba.tolist())
            
            # Task 2: Store calibrated predictions
            all_y_pred_proba_sigmoid.extend(y_pred_proba_sigmoid.tolist())
            all_y_pred_proba_isotonic.extend(y_pred_proba_isotonic.tolist())
            
            # Task 5: Store baseline predictions
            all_baseline_05_proba.extend(baseline_05_proba.tolist())
            all_baseline_line_proba.extend(baseline_line_proba.tolist())
            
        except Exception as e:
            print(f"    ERROR in fold {fold}: {e}")
            import traceback
            traceback.print_exc()
        
        # Move to next fold
        test_start = test_end
        fold += 1
    
    if not all_predictions:
        raise ValueError("No valid folds completed")
    
    # Combine all predictions
    predictions_df = pd.concat(all_predictions, ignore_index=True)
    
    # Compute overall metrics
    y_true_all = np.array(all_y_true)
    y_pred_proba_all = np.array(all_y_pred_proba)
    
    overall_metrics, overall_calibration = compute_all_metrics(y_true_all, y_pred_proba_all)
    overall_metrics["n_folds"] = fold
    overall_metrics["fold_metrics"] = fold_metrics
    
    # Task 2: Compute calibrated metrics
    y_pred_proba_sigmoid_all = np.array(all_y_pred_proba_sigmoid)
    y_pred_proba_isotonic_all = np.array(all_y_pred_proba_isotonic)
    
    metrics_sigmoid, calibration_sigmoid = compute_all_metrics(y_true_all, y_pred_proba_sigmoid_all)
    metrics_isotonic, calibration_isotonic = compute_all_metrics(y_true_all, y_pred_proba_isotonic_all)
    
    # Task 5: Compute baseline metrics
    baseline_05_proba_all = np.array(all_baseline_05_proba)
    baseline_line_proba_all = np.array(all_baseline_line_proba)
    
    baseline_05_metrics, _ = compute_all_metrics(y_true_all, baseline_05_proba_all)
    baseline_line_metrics, _ = compute_all_metrics(y_true_all, baseline_line_proba_all)
    
    # Task 4: Print comparison table (emphasize LogLoss as primary)
    print(f"\n{'='*80}")
    print("METRICS COMPARISON (LogLoss is primary metric)")
    print(f"{'='*80}")
    print(f"{'Model':<35} {'Accuracy':<12} {'Log Loss':<12} {'ROC-AUC':<12}")
    print(f"{'-'*80}")
    print(f"{'baseline_0.5':<35} {baseline_05_metrics['accuracy']:<12.3f} {baseline_05_metrics['log_loss']:<12.3f} {str(baseline_05_metrics.get('roc_auc', 'N/A')):<12}")
    print(f"{'baseline_line_only':<35} {baseline_line_metrics['accuracy']:<12.3f} {baseline_line_metrics['log_loss']:<12.3f} {str(baseline_line_metrics.get('roc_auc', 'N/A')):<12}")
    print(f"{'full_model (uncalibrated)':<35} {overall_metrics['accuracy']:<12.3f} {overall_metrics['log_loss']:<12.3f} {str(overall_metrics.get('roc_auc', 'N/A')):<12}")
    print(f"{'full_model_calibrated (sigmoid)':<35} {metrics_sigmoid['accuracy']:<12.3f} {metrics_sigmoid['log_loss']:<12.3f} {str(metrics_sigmoid.get('roc_auc', 'N/A')):<12}")
    print(f"{'full_model_calibrated (isotonic)':<35} {metrics_isotonic['accuracy']:<12.3f} {metrics_isotonic['log_loss']:<12.3f} {str(metrics_isotonic.get('roc_auc', 'N/A')):<12}")
    print(f"{'='*80}")
    
    # Store all metrics in overall_metrics for saving
    overall_metrics["baseline_05"] = baseline_05_metrics
    overall_metrics["baseline_line_only"] = baseline_line_metrics
    overall_metrics["calibrated_sigmoid"] = metrics_sigmoid
    overall_metrics["calibrated_isotonic"] = metrics_isotonic
    overall_metrics["calibration_sigmoid"] = calibration_sigmoid.to_dict("records") if calibration_sigmoid is not None else None
    overall_metrics["calibration_isotonic"] = calibration_isotonic.to_dict("records") if calibration_isotonic is not None else None
    
    # Task 1: Select best model by LogLoss (primary metric)
    # Compare: uncalibrated, sigmoid, isotonic (skip isotonic if unstable/logloss > 1.0)
    candidates = [
        ("uncalibrated", overall_metrics, overall_calibration),
        ("sigmoid", metrics_sigmoid, calibration_sigmoid),
    ]
    
    # Only include isotonic if it's stable (logloss < 1.0)
    if metrics_isotonic['log_loss'] < 1.0:
        candidates.append(("isotonic", metrics_isotonic, calibration_isotonic))
    
    # Find best by LogLoss
    best_name = None
    best_metrics = None
    best_calibration = None
    best_logloss = float('inf')
    
    for name, metrics, calib in candidates:
        if metrics['log_loss'] < best_logloss:
            best_logloss = metrics['log_loss']
            best_name = name
            best_metrics = metrics
            best_calibration = calib
    
    # Task 1: Update predictions_df to use best model's predictions
    if best_name == "sigmoid":
        # Replace p_hat with sigmoid-calibrated predictions
        predictions_df["p_hat"] = predictions_df["p_hat_sigmoid"]
    elif best_name == "isotonic":
        # Replace p_hat with isotonic-calibrated predictions
        predictions_df["p_hat"] = predictions_df["p_hat_isotonic"]
    # else: keep uncalibrated (already in p_hat)
    
    # Task 1: Store selected model info in overall_metrics
    # IMPORTANT: Copy best_metrics to avoid circular reference if best_metrics == overall_metrics
    overall_metrics["selected_model"] = best_name
    overall_metrics["selected_model_metrics"] = best_metrics.copy() if isinstance(best_metrics, dict) else best_metrics
    
    # Use best model's calibration for main calibration_df
    overall_calibration = best_calibration
    
    print(f"\nBest model (by LogLoss): {best_name}")
    print(f"  Accuracy: {best_metrics['accuracy']:.3f}")
    print(f"  Log Loss: {best_metrics['log_loss']:.3f}")
    if best_metrics.get('roc_auc') is not None:
        print(f"  ROC-AUC: {best_metrics['roc_auc']:.3f}")
    
    return predictions_df, overall_metrics, overall_calibration
