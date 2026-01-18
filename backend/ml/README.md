# ML Pipeline for NBA Betting Analytics

Leakage-safe walk-forward backtesting pipeline for NBA team total predictions.

## Quick Start

```bash
# Set environment variables (optional, defaults provided)
export MONGO_URI="mongodb://localhost:27017"
export DB_NAME="nba_pairs"
export ML_LABEL_FIELD="TEAM_TOTAL_OVER_HIT"  # or "TEAM_TOTAL_STRONG_HIT"

# Run backtest
python -m backend.ml.cli backtest
```

## Configuration

Configuration is read from environment variables (see `ml/config.py`):

- `MONGO_URI`: MongoDB connection URI (default: `mongodb://localhost:27017`)
- `DB_NAME`: MongoDB database name (default: `nba_pairs`)
- `EVENTS_COLLECTION`: Collection name for events (default: `events`)
- `ML_OUTPUT_DIR`: Output directory for artifacts (default: `backend/ml/artifacts`)
- `ML_LABEL_FIELD`: Label field to predict (default: `TEAM_TOTAL_OVER_HIT`)
- `ML_MIN_TRAIN_SIZE`: Minimum training set size (default: `1000`)
- `ML_TEST_CHUNK_SIZE`: Test chunk size in rows (default: `250`)

## Features

### Base Features
- **Context features**: `is_home`, `pace_low`, `pace_mid`, `pace_high`, `is_competitive`
- **Market lines**: `TEAM_TOTAL_LINE`, `GAME_TOTAL_LINE` (if available)

### Rolling Features (Leakage-Safe)
All rolling features use `shift(1)` to ensure no same-game leakage:
- **Rolling margins** (mean, std): `rolling_*_margin_mean_5`, `rolling_*_margin_std_5`, etc.
- **Rolling hit rates**: `rolling_*_over_rate_5`, `rolling_*_over_rate_10`, etc.

Windows: `[5, 10]` (configurable via `ROLLING_WINDOWS` in `config.py`)

## Output Artifacts

After running `backtest`, artifacts are saved to `backend/ml/artifacts/`:

- `predictions.csv`: All predictions with `y_true`, `p_hat`, `fold`, and metadata
- `metrics.json`: Overall and per-fold metrics (accuracy, log_loss, ROC-AUC)
- `calibration.csv`: Calibration table by probability bins (deciles)
- `model.joblib`: Final model trained on all data

## Model

Baseline: **LogisticRegression** with:
- `StandardScaler` for numeric features
- `SimpleImputer(strategy="median")` for missing values
- Scikit-learn `Pipeline` for preprocessing + model

## Walk-Forward Backtest

Uses an expanding window:
- **Training**: All data up to test start (minimum `MIN_TRAIN_SIZE` rows)
- **Testing**: Fixed chunk size (`TEST_CHUNK_SIZE` rows) per fold
- **Progress**: Moves forward through time, accumulating training data

## Metrics

- **Accuracy**: Classification accuracy at threshold 0.5
- **Log Loss**: Binary cross-entropy loss
- **ROC-AUC**: Area under ROC curve (if both classes present)
- **Calibration**: Binned by predicted probability (deciles)

## Safety Checks

The pipeline includes safety checks for:
- Missing label column (fails loudly)
- Missing date field (auto-detects or uses fallback)
- Missing `TEAM_TOTAL_LINE` (required, fails loudly)
- Leakage verification (spot-checks rolling features use `shift(1)`)

## Notes

- All rolling features are computed per-team and shifted by 1 to avoid leakage
- Early rows may have NaN rolling features (handled via imputation)
- The pipeline automatically discovers available event fields from the `events` collection
