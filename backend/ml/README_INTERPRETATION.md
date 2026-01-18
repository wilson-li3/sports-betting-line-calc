# ML Pipeline Interpretation Guide

## What You've Built

You've built a **leakage-safe machine learning pipeline** for predicting NBA team total over/under outcomes. The pipeline uses walk-forward backtesting to evaluate model performance on historical data, ensuring no data leakage (no future information used to predict past events).

### Pipeline Components

1. **Data Loading (`inspect_data`)**
   - Validates MongoDB `events` collection structure
   - Checks for GAME_DATE coverage (critical for temporal ordering)
   - Verifies GAME_ID, TEAM_ID, and label field presence
   - Reports dataset size, date ranges, and data quality

2. **Feature Engineering**
   - **Context features**: `is_home`, `is_competitive`, `pace_bucket` (LOW/MID/HIGH)
   - **Market features**: `TEAM_TOTAL_LINE`, `GAME_TOTAL_LINE` (betting lines)
   - **Rolling features**: Mean/std of margins and hit rates over past 5/10 games per team
   - **Leakage prevention**: All rolling features use `shift(1)` (only past games)

3. **Model Training**
   - **Logistic Regression** with StandardScaler and SimpleImputer
   - **Probability calibration**: Sigmoid (Platt scaling) and Isotonic regression
   - **Regularization**: Default C=0.1 (stronger regularization to prevent overfitting)

4. **Walk-Forward Backtesting**
   - Expanding window: Train on all data up to test chunk start
   - Test chunks: Fixed size (e.g., 100 rows) moved forward in time
   - **Critical**: Data is sorted by GAME_DATE to ensure proper temporal order
   - Multiple folds: Usually 3-5 folds depending on dataset size

5. **Ablation Study**
   - Evaluates 4 feature sets:
     - **A: line_only**: Just betting lines (`TEAM_TOTAL_LINE`, `GAME_TOTAL_LINE`)
     - **B: line_plus_context**: Lines + context features (home, competitive, pace)
     - **C: line_plus_rolling_totals**: Lines + rolling features for totals only
     - **D: full_model**: All features (~99 features)
   - Tests each with uncalibrated and calibrated models
   - Selects best by LogLoss (primary metric)

6. **Picks Analysis**
   - **Deciles**: Bins predictions by confidence (0-10%, 10-20%, ..., 90-100%)
   - **Threshold policy**: Pick Over if `p_hat >= t`, Under if `p_hat <= (1-t)` for thresholds [0.55, 0.60, 0.65, 0.70]
   - **Top-K policy**: Pick top K most confident predictions per fold (K = 5, 10, 20)
   - **Hypothetical EV**: Assumes -110 odds (0.9091 payout) for picks with positive expected value
   - **Warnings**: Explicitly labels as "HYPOTHETICAL" - not a profitability claim

---

## Metric Interpretation

### Accuracy
- **What it is**: % of predictions where `p_hat >= 0.5` matches actual outcome
- **Interpretation**: Higher is better, but can be misleading if probabilities are miscalibrated
- **Baseline**: 50% for a random model, ~52-53% for line-only baseline
- **Your results**: ~66% suggests the model has signal beyond market lines

### Log Loss (Primary Metric)
- **What it is**: Penalizes confident wrong predictions more than unsure wrong predictions
- **Formula**: `-log(p_hat)` if actual=1, `-log(1-p_hat)` if actual=0
- **Interpretation**: Lower is better. LogLoss < 0.693 (random) indicates skill
- **Why it's primary**: Measures calibration quality. A model can have high accuracy but poor LogLoss if probabilities are miscalibrated
- **Your results**: ~0.61 is good (below random 0.693), but still above line-only baseline (~0.65)
- **Calibration fix**: When LogLoss improves after calibration (sigmoid/isotonic), it means probabilities were too extreme

### ROC-AUC (Area Under ROC Curve)
- **What it is**: Measures ability to rank predictions (distinguish Over vs Under)
- **Range**: 0.5 (random) to 1.0 (perfect)
- **Interpretation**: AUC > 0.7 suggests good ranking ability
- **Your results**: ~0.72 indicates the model can rank games by over probability

### Calibration Table
- **What it is**: Bins predictions into deciles (0-10%, 10-20%, ..., 90-100%)
- **Columns**:
  - `mean_pred`: Average predicted probability in that bin
  - `mean_true`: Actual hit rate in that bin
  - `diff`: `mean_pred - mean_true` (calibration error)
- **Interpretation**: 
  - **Well-calibrated**: `mean_pred ≈ mean_true` (diff near 0)
  - **Overconfident**: `mean_pred > mean_true` (diff positive) - model too confident
  - **Underconfident**: `mean_pred < mean_true` (diff negative) - model too cautious
- **Example**: If bin 80-90% has `mean_pred=0.85` but `mean_true=0.70`, the model is overconfident at high probabilities

### Ablation Results
- **What it shows**: Which feature set performs best
- **Common result**: "B: line_plus_context" often wins
  - Context features (home, competitive, pace) add signal beyond market lines
  - Rolling totals and full model may add noise (overfitting)
- **How to choose**: Pick feature set with lowest LogLoss (best calibration)
- **Note**: Isotonic calibration excluded if LogLoss > 1.0 (unstable)

### Deciles Analysis
- **What it shows**: Model performance across confidence levels
- **Columns**:
  - `decile`: 1 (low confidence) to 10 (high confidence)
  - `mean_pred`: Average predicted probability
  - `mean_true`: Actual hit rate
  - `calibration_diff`: Prediction error
- **Interpretation**: 
  - High deciles (8-10): Most confident predictions
  - If high deciles have good hit rates, model is useful for selective picks
  - Calibration diff should be small for well-calibrated models

### Threshold Policy
- **What it is**: Decision rule: pick Over if `p_hat >= threshold`, Under if `p_hat <= (1-threshold)`
- **Metrics**: 
  - `num_picks`: How many picks made (vs all games)
  - `hit_rate`: Accuracy on those picks
  - `over_pick_count` / `under_pick_count`: Direction breakdown
  - `over_hit_rate` / `under_hit_rate`: Direction-specific accuracy
- **Interpretation**: Higher thresholds = fewer picks but potentially higher hit rate (selective strategy)
- **Trade-off**: More selective (higher threshold) → fewer picks → higher hit rate (if model is good)

### Top-K Policy
- **What it is**: Pick top K most confident predictions per fold (highest `|p_hat - 0.5|`)
- **Metrics**: Same as threshold policy
- **Interpretation**: Another selective strategy - only bet when very confident
- **Use case**: Simulates a "best bets" strategy

---

## Important Warnings

### Overfitting / Selection Bias
- **Walk-forward backtesting helps**, but it's still historical data
- **Ablation study may overfit**: Testing multiple feature sets on same data
- **Picks analysis is retrospective**: Assumes you could pick those exact games in real-time
- **Hypothetical EV assumes perfect execution**: Real betting has slippage, line movement, limits

### Why This Is "Backtest Only"
- **No live testing**: Results are on historical data only
- **Market efficiency**: If model finds edges, market may adjust (lines shift)
- **Survivorship bias**: Dataset may exclude games with missing data (if any)
- **Regime changes**: NBA rules/trends change over time (3-point era, pace changes)

### Model Limitations
- **Linear model**: Logistic Regression can't capture complex interactions
- **Feature engineering**: Manual features may miss hidden patterns
- **Label noise**: `TEAM_TOTAL_OVER_HIT` is binary, loses margin information
- **Market efficiency**: Lines are already efficient - beating them consistently is hard

---

## What To Do Next (Practical Checklist)

### 1. Sanity Checks
- [ ] Verify no data leakage: Check that rolling features are `shift(1)` (no same-game data)
- [ ] Check calibration: If `calibration_diff` > 0.1 in any decile, model is miscalibrated
- [ ] Verify temporal order: Ensure predictions are sorted by GAME_DATE (not GAME_ID)
- [ ] Check for overfitting: Compare train vs test metrics (if available)

### 2. Split by Season
- [ ] Add season-based validation: Train on 2020-2022, test on 2023-2024
- [ ] Check for temporal drift: Compare model performance across seasons
- [ ] Report season-specific metrics: Does model work in all eras?

### 3. Expand Dataset
- [ ] Pull more historical data (last 7 years = ~5000 games)
- [ ] Add playoff games (if currently only regular season)
- [ ] Include more seasons for robustness testing

### 4. Add Bet Simulation with Vig
- [ ] Implement realistic odds: Use actual line history if available, or simulate with -110 vig
- [ ] Track units: Calculate profit/loss in units (not just hit rate)
- [ ] Account for line movement: Simulate getting worse odds when betting late
- [ ] Add bankroll management: Kelly criterion, flat betting, or fixed unit sizing

### 5. Feature Engineering
- [ ] Add team-specific features: Head-to-head history, rest days, travel distance
- [ ] Add opponent strength: Opponent defensive ratings, pace adjustments
- [ ] Experiment with non-linear features: Interactions, polynomial features
- [ ] Try different models: Random Forest, XGBoost, Neural Networks (if dataset is large enough)

### 6. Live Testing (Future)
- [ ] Set up live data pipeline: Pull current day's lines from API
- [ ] Track predictions: Log model predictions before games
- [ ] Verify execution: Compare predicted lines to actual closing lines
- [ ] Monitor performance: Track hit rate and calibration over time

### 7. Risk Management
- [ ] Set betting limits: Max picks per day, max stake per game
- [ ] Monitor drawdown: Track worst losing streak
- [ ] Diversify: Don't bet correlated outcomes (same game totals + overs)
- [ ] Account for variance: Use confidence intervals, not point estimates

### 8. Documentation
- [ ] Document assumptions: What the model assumes (no line movement, perfect execution)
- [ ] Record hyperparameters: C, max_iter, calibration method, feature set
- [ ] Track changes: Version control for models and features
- [ ] Create run reports: Save timestamps, dataset size, key metrics for each run

---

## Quick Reference: Your Typical Results

- **Best Model**: `B: line_plus_context (uncalibrated or sigmoid)`
- **Metrics**: Accuracy ~0.66, LogLoss ~0.61, ROC-AUC ~0.72
- **Coverage**: 2422 events, 1218 games, 30 teams, 100% GAME_DATE coverage
- **Date Range**: 2023-10-24 to 2024-10-24 (full season)
- **Key Insight**: Context features (home, competitive, pace) add signal beyond market lines. Rolling features may add noise.

---

## Files Generated

- `metrics.json`: Overall model performance (accuracy, logloss, AUC)
- `calibration.csv`: Binned calibration table (deciles)
- `ablation_results.json`: Feature set comparison
- `picks_summary.json`: Threshold/top-K policy results
- `picks_by_decile.csv`: Decile-level performance
- `coefficients.json`: Model interpretability (top positive/negative features)
- `predictions.csv`: Full prediction dataset (game_id, team_id, y_true, p_hat, fold)
- `model.joblib`: Trained model (for future predictions)
