# Dataset Expansion Guide

To expand your dataset to ~5000 games (last 7 years), use the `expand_dataset.py` script.

## Quick Start

```bash
# Expand to ~5000 games (auto-calculates seasons)
python backend/app/scripts/expand_dataset.py --target-games 5000

# Or specify specific seasons
python backend/app/scripts/expand_dataset.py --seasons 2023-24 2022-23 2021-22 2020-21

# Resume mode (skip existing games/boxscores)
python backend/app/scripts/expand_dataset.py --target-games 5000 --skip-games --skip-boxscores
```

## What It Does

1. **Pulls games** from NBA API for specified seasons (~1230 games per season)
2. **Pulls boxscores** for all games (with rate limiting)
3. **Builds analytics**:
   - Team stats aggregation
   - Role computation
   - Event building
   - Context tags

## Time Estimate

- **Pulling games**: ~2-3 seconds per season (fast)
- **Pulling boxscores**: ~1.2 seconds per game = ~6000 seconds (~100 minutes) for 5000 games
- **Building analytics**: ~1-5 minutes depending on dataset size

**Total**: ~2-3 hours for 5000 games

## Options

- `--target-games N`: Target number of games (default: 5000)
- `--seasons SEASON1 SEASON2 ...`: Specific seasons (e.g., `2023-24 2022-23`)
- `--skip-games`: Skip pulling games (use existing)
- `--skip-boxscores`: Skip pulling boxscores (use existing)
- `--skip-analytics`: Skip building analytics (run separately)
- `--sleep-boxscores SECONDS`: Sleep between boxscore requests (default: 1.2)

## Example: Pull Last 7 Seasons

```bash
python backend/app/scripts/expand_dataset.py \
  --seasons 2023-24 2022-23 2021-22 2020-21 2019-20 2018-19 2017-18 \
  --sleep-boxscores 1.5
```

## After Expansion

Once data is pulled and events are built, run the ML pipeline:

```bash
PYTHONPATH=. python -m backend.ml.cli backtest
```

The ML pipeline will automatically use the expanded dataset with real dates if `GAME_DATE` is available.
