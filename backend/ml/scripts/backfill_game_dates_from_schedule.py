#!/usr/bin/env python3
"""
Backfill GAME_DATE in MongoDB events collection from authoritative NBA schedule data.

This script:
1. Loads NBA schedule data (from API or local file)
2. Creates GAME_ID → GAME_DATE mapping (normalized strings)
3. Updates MongoDB events where GAME_DATE is missing
4. Safety checks: don't overwrite existing dates, warn if coverage < 80%

Usage:
    # From NBA API (preferred if available)
    python backend/ml/scripts/backfill_game_dates_from_schedule.py --api

    # From local CSV file
    python backend/ml/scripts/backfill_game_dates_from_schedule.py --csv path/to/schedule.csv

    # Dry run (no writes)
    python backend/ml/scripts/backfill_game_dates_from_schedule.py --api --dry-run
"""
import sys
import argparse
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
from pymongo import MongoClient

from backend.ml.config import MONGO_URI, MONGO_DB, EVENTS_COLLECTION


def normalize_game_id(game_id_raw):
    """
    Normalize GAME_ID to string with leading zeros.
    
    NBA GAME_IDs are 10-digit strings (e.g., "0022300010").
    Preserves leading zeros and ensures consistent format.
    """
    if game_id_raw is None:
        return None
    
    # Convert to string and strip whitespace
    game_id_str = str(game_id_raw).strip()
    
    # If numeric and < 10 digits, pad with leading zeros
    if game_id_str.isdigit():
        game_id = game_id_str.zfill(10)
    else:
        game_id = game_id_str
    
    return game_id


def load_schedule_from_db():
    """
    Load NBA schedule from existing db.games collection in MongoDB.
    
    This is the preferred method if games collection already has GAME_DATE.
    
    Returns:
        Dict mapping normalized GAME_ID (string) -> GAME_DATE (datetime, date only)
    """
    print("Loading schedule from MongoDB db.games collection...")
    
    from app.db import db
    
    games = list(db.games.find({}, {"GAME_ID": 1, "GAME_DATE": 1, "GAME_DATE_EST": 1, "GAME_DATE_UTC": 1}))
    
    print(f"  Loaded {len(games)} games from db.games")
    
    schedule_map = {}
    
    # Find which date column is present
    date_col = None
    for game in games[:10]:  # Sample first 10
        for col in ["GAME_DATE", "GAME_DATE_EST", "GAME_DATE_UTC"]:
            if col in game and game[col] is not None:
                date_col = col
                break
        if date_col:
            break
    
    if not date_col:
        print("  WARNING: No GAME_DATE column found in db.games collection")
        return schedule_map
    
    print(f"  Using date column: {date_col}")
    
    for game in games:
        game_id_raw = game.get("GAME_ID")
        game_date_raw = game.get(date_col)
        
        # Normalize GAME_ID
        game_id = normalize_game_id(game_id_raw)
        if not game_id:
            continue
        
        # Parse GAME_DATE
        if game_date_raw:
            try:
                # Parse as datetime and extract date only
                if isinstance(game_date_raw, datetime):
                    game_date = game_date_raw.replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    game_date = pd.to_datetime(game_date_raw).to_pydatetime().replace(hour=0, minute=0, second=0, microsecond=0)
                schedule_map[game_id] = game_date
            except Exception as e:
                # Skip unparseable dates
                continue
    
    print(f"  Total schedule entries: {len(schedule_map)}")
    return schedule_map


def load_schedule_from_api(seasons=None):
    """
    Load NBA schedule from NBA API (leaguegamelog endpoint).
    
    Args:
        seasons: List of seasons (e.g., ["2023-24", "2022-23"]). If None, uses last 7 years.
    
    Returns:
        Dict mapping normalized GAME_ID (string) -> GAME_DATE (datetime, date only)
    """
    print("Loading schedule from NBA API...")
    
    # Import here to avoid dependency if not using API
    from app.etl.nba_api import nba_get
    
    if seasons is None:
        # Auto-calculate last 7 seasons
        from datetime import datetime as dt
        current_year = dt.now().year
        seasons = []
        for i in range(7):
            year = current_year - i
            seasons.append(f"{year-1}-{str(year)[-2:]}")
        print(f"  Auto-selected seasons: {seasons}")
    
    schedule_map = {}
    
    for season in seasons:
        print(f"  Fetching season: {season}")
        try:
            # Fetch regular season games
            data = nba_get(
                "leaguegamelog",
                {
                    "Season": season,
                    "SeasonType": "Regular Season",
                    "LeagueID": "00",
                }
            )
            
            rs = data["resultSets"][0]
            headers = rs["headers"]
            rows = rs["rowSet"]
            
            # Find GAME_ID and GAME_DATE columns
            game_id_idx = None
            game_date_idx = None
            
            for i, h in enumerate(headers):
                if h.upper() in ["GAME_ID", "GAMEID"]:
                    game_id_idx = i
                if h.upper() in ["GAME_DATE", "GAME_DATE_EST", "GAME_DATE_UTC", "DATE"]:
                    game_date_idx = i
            
            if game_id_idx is None:
                print(f"    WARNING: No GAME_ID column found in season {season}")
                continue
            
            if game_date_idx is None:
                print(f"    WARNING: No GAME_DATE column found in season {season}")
                continue
            
            # Parse rows
            for row in rows:
                game_id_raw = row[game_id_idx]
                game_date_raw = row[game_date_idx]
                
                # Normalize GAME_ID
                game_id = normalize_game_id(game_id_raw)
                if not game_id:
                    continue
                
                # Parse GAME_DATE
                if game_date_raw:
                    try:
                        # Try parsing as datetime
                        if isinstance(game_date_raw, str):
                            # Common formats: "2023-10-15T00:00:00", "2023-10-15"
                            date_str = game_date_raw.split("T")[0]  # Take date part
                            game_date = pd.to_datetime(date_str).to_pydatetime().replace(hour=0, minute=0, second=0, microsecond=0)
                        else:
                            game_date = pd.to_datetime(game_date_raw).to_pydatetime().replace(hour=0, minute=0, second=0, microsecond=0)
                        
                        schedule_map[game_id] = game_date
                    except Exception as e:
                        print(f"    WARNING: Could not parse date '{game_date_raw}' for GAME_ID {game_id}: {e}")
                        continue
            
            print(f"    Loaded {len([k for k in schedule_map.keys() if k.startswith(str(season[:4]))])} games")
            
        except Exception as e:
            print(f"    ERROR fetching season {season}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"  Total schedule entries: {len(schedule_map)}")
    return schedule_map


def load_schedule_from_csv(csv_path):
    """
    Load NBA schedule from CSV file.
    
    Expected columns: GAME_ID, GAME_DATE (or GAME_DATE_EST, GAME_DATE_UTC, DATE)
    
    Args:
        csv_path: Path to CSV file
    
    Returns:
        Dict mapping normalized GAME_ID (string) -> GAME_DATE (datetime, date only)
    """
    print(f"Loading schedule from CSV: {csv_path}")
    
    df = pd.read_csv(csv_path)
    print(f"  Loaded {len(df)} rows")
    
    # Find GAME_ID column
    game_id_col = None
    for col in df.columns:
        if col.upper() in ["GAME_ID", "GAMEID"]:
            game_id_col = col
            break
    
    if game_id_col is None:
        raise ValueError(f"No GAME_ID column found in CSV. Available columns: {df.columns.tolist()}")
    
    # Find GAME_DATE column
    game_date_col = None
    for col in df.columns:
        if col.upper() in ["GAME_DATE", "GAME_DATE_EST", "GAME_DATE_UTC", "DATE"]:
            game_date_col = col
            break
    
    if game_date_col is None:
        raise ValueError(f"No GAME_DATE column found in CSV. Available columns: {df.columns.tolist()}")
    
    print(f"  Using columns: {game_id_col}, {game_date_col}")
    
    schedule_map = {}
    
    for _, row in df.iterrows():
        game_id_raw = row[game_id_col]
        game_date_raw = row[game_date_col]
        
        # Normalize GAME_ID
        game_id = normalize_game_id(game_id_raw)
        if not game_id or pd.isna(game_id):
            continue
        
        # Parse GAME_DATE
        if not pd.isna(game_date_raw):
            try:
                # Parse as datetime and extract date only
                game_date = pd.to_datetime(game_date_raw).to_pydatetime().replace(hour=0, minute=0, second=0, microsecond=0)
                schedule_map[game_id] = game_date
            except Exception as e:
                print(f"  WARNING: Could not parse date '{game_date_raw}' for GAME_ID {game_id}: {e}")
                continue
    
    print(f"  Total schedule entries: {len(schedule_map)}")
    return schedule_map


def backfill_game_dates(schedule_map, dry_run=False, min_coverage_pct=80.0):
    """
    Backfill GAME_DATE in MongoDB events collection.
    
    Args:
        schedule_map: Dict mapping GAME_ID (string) -> GAME_DATE (datetime)
        dry_run: If True, don't write changes (default: False)
        min_coverage_pct: Minimum coverage percentage before warning (default: 80.0)
    
    Returns:
        Dict with stats: total, already_had_date, backfilled, missing_from_schedule
    """
    print(f"\nBackfilling GAME_DATE in MongoDB...")
    
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    collection = db[EVENTS_COLLECTION]
    
    # Get all events
    events = list(collection.find({}, {"GAME_ID": 1, "GAME_DATE": 1}))
    total_events = len(events)
    
    print(f"  Total events scanned: {total_events}")
    
    stats = {
        "total": total_events,
        "already_had_date": 0,
        "backfilled": 0,
        "missing_from_schedule": 0,
    }
    
    # Track which GAME_IDs need updates
    updates_to_apply = []
    
    for event in events:
        game_id_raw = event.get("GAME_ID")
        
        # Normalize GAME_ID for matching
        game_id = normalize_game_id(game_id_raw)
        if not game_id:
            continue
        
        # Check if GAME_DATE already exists
        if "GAME_DATE" in event and event["GAME_DATE"] is not None:
            stats["already_had_date"] += 1
            continue
        
        # Check if schedule has this GAME_ID
        if game_id in schedule_map:
            game_date = schedule_map[game_id]
            updates_to_apply.append((game_id, game_date))
            stats["backfilled"] += 1
        else:
            stats["missing_from_schedule"] += 1
    
    # Safety check: calculate coverage after backfill
    total_with_date = stats["already_had_date"] + stats["backfilled"]
    coverage_pct = (total_with_date / total_events * 100) if total_events > 0 else 0
    
    print(f"\nBackfill statistics:")
    print(f"  Events already had GAME_DATE: {stats['already_had_date']}")
    print(f"  Events to backfill: {stats['backfilled']}")
    print(f"  Events missing from schedule: {stats['missing_from_schedule']}")
    print(f"  Coverage after backfill: {total_with_date}/{total_events} ({coverage_pct:.1f}%)")
    
    # Safety check: warn if coverage is too low
    if coverage_pct < min_coverage_pct:
        print(f"\n⚠️  WARNING: Coverage {coverage_pct:.1f}% is below minimum {min_coverage_pct}%")
        if not dry_run:
            print("  Exiting without writing changes for safety.")
            client.close()
            return stats
    
    # Apply updates
    if dry_run:
        print(f"\n⚠️  DRY RUN: Would update {len(updates_to_apply)} events (no changes written)")
    else:
        print(f"\nApplying updates to MongoDB...")
        updated_count = 0
        
        for game_id, game_date in updates_to_apply:
            # CRITICAL: Only update if GAME_DATE is missing or null (never overwrite existing dates)
            result = collection.update_many(
                {
                    "GAME_ID": game_id,
                    "$or": [
                        {"GAME_DATE": {"$exists": False}},
                        {"GAME_DATE": None}
                    ]
                },
                {"$set": {"GAME_DATE": game_date}}
            )
            updated_count += result.modified_count
        
        print(f"  Updated {updated_count} event documents")
    
    client.close()
    return stats


def main():
    parser = argparse.ArgumentParser(description="Backfill GAME_DATE from NBA schedule")
    parser.add_argument("--db", action="store_true", help="Load schedule from MongoDB db.games collection (preferred if available)")
    parser.add_argument("--api", action="store_true", help="Load schedule from NBA API")
    parser.add_argument("--csv", type=str, help="Load schedule from CSV file")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (no writes to MongoDB)")
    parser.add_argument("--min-coverage", type=float, default=80.0, help="Minimum coverage percentage (default: 80.0)")
    parser.add_argument("--seasons", nargs="+", help="Seasons to fetch from API (e.g., 2023-24 2022-23). Auto-calculates if not provided")
    
    args = parser.parse_args()
    
    # Count how many sources specified
    sources = sum([args.db, args.api, bool(args.csv)])
    
    if sources == 0:
        # Default to --db if no source specified
        args.db = True
    elif sources > 1:
        parser.error("Cannot specify multiple sources. Use --db, --api, or --csv (not multiple)")
    
    print("=" * 80)
    print("BACKFILL GAME_DATE FROM NBA SCHEDULE")
    print("=" * 80)
    
    # Load schedule
    if args.db:
        schedule_map = load_schedule_from_db()
    elif args.api:
        schedule_map = load_schedule_from_api(seasons=args.seasons)
    else:
        schedule_map = load_schedule_from_csv(args.csv)
    
    if not schedule_map:
        print("ERROR: No schedule data loaded. Exiting.")
        sys.exit(1)
    
    # Backfill dates
    stats = backfill_game_dates(
        schedule_map,
        dry_run=args.dry_run,
        min_coverage_pct=args.min_coverage
    )
    
    print("\n" + "=" * 80)
    print("BACKFILL COMPLETE")
    print("=" * 80)
    
    if args.dry_run:
        print("\n⚠️  This was a DRY RUN. No changes were written.")
        print("   Remove --dry-run to apply changes.")
    else:
        print(f"\n✓ Backfilled {stats['backfilled']} events with GAME_DATE")
    
    print(f"\nNext steps:")
    print(f"1. Verify: python backend/ml/scripts/test_ingest_gamedate.py --verify")
    print(f"2. Inspect: PYTHONPATH=. python -m backend.ml.cli inspect_data")
    print(f"3. Test ML: PYTHONPATH=. python -m backend.ml.cli backtest")


if __name__ == "__main__":
    main()
