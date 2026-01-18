# ML Dashboard - Quick Start Guide

## Part 1: Interpretation Summary

See `backend/ml/README_INTERPRETATION.md` for a comprehensive guide to understanding your ML pipeline outputs.

**Quick Summary:**
- You've built a leakage-safe ML pipeline for predicting NBA team total over/under outcomes
- Current best model: `B: line_plus_context` (lines + context features like home/away, competitive, pace)
- Performance: Accuracy ~66%, LogLoss ~0.61, ROC-AUC ~0.72
- Dataset: 2422 events, 1218 games, 30 teams, 100% GAME_DATE coverage (2023-10-24 to 2024-10-24)
- Key insight: Context features add signal beyond market lines; rolling features may add noise

## Part 2: Dashboard Setup & Usage

### Prerequisites

1. **Backend dependencies** (should already be installed):
   ```bash
   pip install -r backend/requirements.txt
   ```

2. **Frontend dependencies** (new):
   ```bash
   cd frontend
   npm install
   ```
   
   This will install `recharts` for charting.

### Running the Dashboard

#### 1. Start Backend API Server

```bash
# From project root (set PYTHONPATH to backend/)
PYTHONPATH=./backend uvicorn app.main:app --reload --port 8000

# OR from backend/ directory
cd backend
uvicorn app.main:app --reload --port 8000
```

The API server will run at `http://localhost:8000`

#### 2. Start Frontend Dev Server

```bash
# From frontend/ directory (or project root with npm -C frontend)
cd frontend
npm run dev
```

The frontend will run at `http://localhost:5173`

#### 3. Access Dashboard

Open `http://localhost:5173` in your browser. Click the "ML Dashboard" button in the navigation bar.

### API Endpoints

The backend provides the following endpoints (all under `/api/`):

- `GET /api/health` - Health check
- `GET /api/metrics` - Overall model metrics (accuracy, logloss, AUC, etc.)
- `GET /api/predictions?limit=1000` - Predictions CSV as JSON
- `GET /api/calibration` - Calibration table (deciles)
- `GET /api/ablation` - Ablation study results (feature set comparison)
- `GET /api/deciles` - Deciles analysis (performance by confidence level)
- `GET /api/picks_summary` - Picks analysis (threshold/top-K policies)
- `GET /api/coefficients` - Model coefficients (interpretability)

All endpoints return JSON. The frontend fetches these on load and visualizes them.

### Dashboard Features

The dashboard includes:

1. **Overview Cards**: Key metrics at a glance (Accuracy, LogLoss, AUC, samples, folds, best model)

2. **Calibration Chart**: Scatter plot of predicted vs actual probabilities. Well-calibrated models fall on the diagonal line.

3. **Deciles Chart**: Line chart showing predicted vs actual hit rates across confidence deciles (1=low, 10=high)

4. **Ablation Comparison**: Bar chart comparing LogLoss across feature sets (A/B/C/D) and variants (uncalibrated/sigmoid/isotonic)

5. **Threshold Policy Table**: Decision rule results (pick Over if `p_hat >= threshold`). Shows hit rates, CI, over/under breakdown.

6. **Top-K Policy Table**: Selective picking strategy (top K most confident predictions). Shows hit rates, CI, over/under breakdown.

7. **Coefficients Tables**: Top positive and negative features with their coefficients (interpretability)

### Troubleshooting

**"ML API not available" error:**
- Ensure `backend/app/ml_api.py` exists and imports correctly
- Check that `pandas` is installed: `pip install pandas`

**404 errors on API endpoints:**
- Verify artifact files exist in `backend/ml/artifacts/`:
  - `metrics.json`
  - `calibration.csv`
  - `ablation_results.json`
  - `picks_by_decile.csv`
  - `picks_summary.json`
  - `coefficients.json`
- If files are missing, run: `PYTHONPATH=. python -m backend.ml.cli backtest`

**Frontend not loading:**
- Check that `recharts` is installed: `cd frontend && npm install`
- Check browser console for errors
- Verify backend is running on port 8000

**CORS errors:**
- Ensure backend `main.py` has CORS middleware configured for `http://localhost:5173`

### File Structure

```
backend/
  app/
    main.py              # FastAPI app with ML dashboard endpoints
    ml_api.py            # ML dashboard API functions (loads artifacts)
  ml/
    artifacts/           # ML pipeline outputs
      metrics.json
      calibration.csv
      ablation_results.json
      picks_by_decile.csv
      picks_summary.json
      coefficients.json
      predictions.csv
frontend/
  src/
    App.tsx              # Main app with navigation
    MLDashboard.tsx      # ML dashboard component
    MLDashboard.css      # Dashboard styles
  package.json           # Dependencies (includes recharts)
```

### Next Steps (from README_INTERPRETATION.md)

1. **Sanity checks**: Verify no data leakage, check calibration, verify temporal order
2. **Split by season**: Add season-based validation (train on 2020-2022, test on 2023-2024)
3. **Expand dataset**: Pull more historical data (last 7 years = ~5000 games)
4. **Add bet simulation**: Implement realistic odds, track units, account for line movement
5. **Feature engineering**: Add team-specific features, opponent strength, non-linear features
6. **Live testing**: Set up live data pipeline, track predictions before games
7. **Risk management**: Set betting limits, monitor drawdown, diversify
8. **Documentation**: Document assumptions, track hyperparameters, create run reports
