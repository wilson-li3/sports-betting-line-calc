# Complete App Guide - ML Dashboard + Backtest Review + Future Games

## Quick Start

### 1. Backend Setup

```bash
# Install dependencies (if not already done)
pip install -r backend/requirements.txt

# Start API server (from project root)
PYTHONPATH=./backend uvicorn app.main:app --reload --port 8000
```

The API will run at `http://localhost:8000`

### 2. Frontend Setup

```bash
# Install dependencies (first time only)
cd frontend
npm install

# Start dev server
npm run dev
```

The frontend will run at `http://localhost:5173`

### 3. Access Dashboard

Open `http://localhost:5173` and use the navigation bar to switch between:
- **Pairs Explorer**: Graph visualization
- **Graph Explorer**: Large-scale graph
- **ML Dashboard**: Overall metrics, calibration, ablation
- **Backtest Review**: Historical betting performance
- **Future Games**: Predictions for upcoming games

---

## What's Implemented

### A) Scrolling Fixed ✅
- Removed `overflow:hidden` from root containers
- Changed `height:100vh` to `min-height:100vh`
- Added proper scroll containers with `overflow-y: auto`
- All pages now scroll normally

### B) Backtest Review Page ✅
**Route**: `/backtest` (via navigation button)

**Features**:
- Summary cards: Total picks, hit rate, timeframe, folds
- Threshold explorer: Table showing performance at different confidence thresholds
- Top-K explorer: Table showing performance for top K picks per fold
- Decile performance chart: Model performance across confidence levels
- Example picks table: Top 50 picks by confidence with game details

**API Endpoints**:
- `GET /api/timeframe` - Get min/max date from backtest
- `GET /api/picks?limit=50&sort=confidence` - Get example picks

### C) Future Games Page ✅
**Route**: `/future` (via navigation button)

**Features**:
- Filters: Date range, min confidence slider, limit
- Summary cards: Total games, over/under breakdown, avg confidence
- Probability distribution chart
- Games table: Predictions with confidence, recommended side, hypothetical EV

**API Endpoints**:
- `GET /api/future_games?min_confidence=0.1&limit=100` - Get future games with predictions
- `GET /api/future_recommendations?threshold=0.15&limit=50` - Get high-confidence recommendations

**Data Sources** (in order of preference):
1. CSV file: Set `ML_FUTURE_GAMES_CSV=/path/to/upcoming_games.csv` env var
2. MongoDB: Queries `db.games` collection for games with `GAME_DATE >= today`

**Required CSV columns**:
- `GAME_DATE` or `date`: Game date (YYYY-MM-DD)
- `GAME_ID` or `game_id`: Game identifier
- `TEAM_ID` or `team_id`: Team identifier (one row per team per game)
- `TEAM_TOTAL_LINE`: Betting line (numeric, required for model)
- `TEAM_ABBREVIATION`: Team abbreviation (optional, for display)

**Note**: MongoDB `games` collection typically has one row per game, but the model needs one row per team per game (like the `events` collection). For future games, you may need to create team-level rows.

### D) Model Inference ✅
- Loads saved `model.joblib` from `backend/ml/artifacts/`
- Computes rolling features using historical data (leakage-safe)
- Applies same feature engineering as training
- Handles missing features gracefully (fills with neutral values)

---

## Testing

### Test API Endpoints

```bash
# Health check
curl http://localhost:8000/api/health

# Get metrics
curl http://localhost:8000/api/metrics

# Get picks (top 10 by confidence)
curl "http://localhost:8000/api/picks?limit=10&sort=confidence"

# Get timeframe
curl http://localhost:8000/api/timeframe

# Get future games (will error if no future games data)
curl "http://localhost:8000/api/future_games?min_confidence=0.1&limit=20"

# Get recommendations (high confidence only)
curl "http://localhost:8000/api/future_recommendations?threshold=0.15&limit=10"
```

### Test Frontend Pages

1. **ML Dashboard**: Should show overview cards, calibration chart, deciles, ablation, coefficients
2. **Backtest Review**: Should show summary, threshold/top-K tables, decile chart, example picks
3. **Future Games**: 
   - If no future games data: Shows error message with instructions
   - If future games exist: Shows filters, summary, probability distribution, games table

---

## Future Games Data Setup

### Option 1: CSV File (Easiest)

Create a CSV file with future games:

```csv
GAME_DATE,GAME_ID,TEAM_ID,TEAM_ABBREVIATION,TEAM_TOTAL_LINE
2025-01-20,0022500001,1610612737,ATL,115.5
2025-01-20,0022500001,1610612738,BOS,112.0
2025-01-21,0022500002,1610612741,CHI,108.5
2025-01-21,0022500002,1610612742,DAL,111.0
```

Set environment variable:
```bash
export ML_FUTURE_GAMES_CSV=/path/to/upcoming_games.csv
```

Restart backend server.

### Option 2: MongoDB

Ensure `db.games` collection has future games with:
- `GAME_DATE`: datetime field with future dates
- `GAME_ID`: string identifier
- `TEAM_ID`: team identifier (may need to create team-level rows)

**Note**: The model expects one row per team per game (like `events` collection). If `games` collection only has one row per game, you'll need to expand it to team-level.

---

## File Structure

```
backend/
  app/
    main.py              # FastAPI app with all endpoints
    ml_api.py            # ML dashboard API functions
  ml/
    artifacts/           # ML pipeline outputs
      model.joblib       # Saved model for inference
      metrics.json
      predictions.csv
      calibration.csv
      ablation_results.json
      picks_by_decile.csv
      picks_summary.json
      coefficients.json
    predict.py           # Model inference for future games
    data.py              # Data loading
    features.py          # Feature engineering
    train.py             # Model training
    backtest.py          # Walk-forward backtest
frontend/
  src/
    App.tsx              # Main app with navigation
    MLDashboard.tsx      # ML dashboard component
    BacktestReview.tsx   # Backtest review component
    FutureGames.tsx      # Future games component
    MLDashboard.css      # Shared styles
```

---

## Troubleshooting

### "Failed to resolve import './FutureGames'"
- ✅ Fixed: `FutureGames.tsx` component created

### "ML API not available"
- Ensure `backend/app/ml_api.py` exists
- Check that `pandas` is installed: `pip install pandas`

### "No future games found"
- Set `ML_FUTURE_GAMES_CSV` env var pointing to CSV file, OR
- Ensure MongoDB `db.games` collection has future games with `GAME_DATE >= today`

### "Model not found"
- Run backtest first: `PYTHONPATH=. python -m backend.ml.cli backtest`
- This generates `backend/ml/artifacts/model.joblib`

### Scrolling still not working
- Clear browser cache
- Check browser console for CSS conflicts
- Verify `frontend/src/index.css` has `overflow-y: auto` on body

### CORS errors
- Backend CORS is configured for `http://localhost:5173` and `http://127.0.0.1:5173`
- If using different port, update CORS in `backend/app/main.py`

---

## Next Steps

1. **Populate future games data**: Create CSV or add to MongoDB
2. **Test predictions**: Verify model loads and predictions are reasonable
3. **Enhance features**: Add more context features for future games (rest days, travel, etc.)
4. **Add live data**: Set up pipeline to pull current day's lines from API
5. **Track performance**: Log predictions and compare to actual outcomes

---

## Summary

✅ **Scrolling**: Fixed globally  
✅ **Backtest Review**: Complete with all features  
✅ **Future Games**: Complete with model inference  
✅ **API Endpoints**: All implemented  
✅ **Documentation**: Complete with test instructions

The app is ready to use! Start both servers and navigate to the different pages to explore your ML pipeline results.
