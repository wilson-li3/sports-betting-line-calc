#!/usr/bin/env python3
"""
Complete script to expand dataset to ~5000 games (last 7 years).

This script orchestrates:
1. Pull games for multiple seasons
2. Pull boxscores for all games
3. Build events from raw data
4. Run analytics pipeline

Usage:
    python backend/app/scripts/expand_dataset.py --target-games 5000
"""
import sys
import argparse
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.db import db
from app.etl.pull_games import pull_games
from app.etl.pull_boxscores import pull_boxscore_traditional, game_already_exists, get_unique_game_ids
from app.analytics.refresh_all import (
    build_team_stats_for_all_games,
    refresh_roles_for_all_games,
    refresh_events_for_all_games,
)
from app.features.context_tags import add_context_tags_to_events
import time


def get_recent_seasons(n_years=7):
    """Generate list of recent NBA seasons."""
    from datetime import datetime
    current_year = datetime.now().year
    seasons = []
    for i in range(n_years):
        year = current_year - i
        season = f"{year-1}-{str(year)[-2:]}"
        seasons.append(season)
    return seasons


def pull_games_for_seasons(seasons, season_type="Regular Season"):
    """Pull games for multiple seasons."""
    print(f"\n{'='*80}")
    print("STEP 1: Pulling games from NBA API")
    print(f"{'='*80}")
    
    existing_count = db.games.count_documents({})
    print(f"Existing games: {existing_count}")
    
    for i, season in enumerate(seasons, 1):
        print(f"\n[{i}/{len(seasons)}] Season: {season}")
        try:
            pull_games(season=season, season_type=season_type)
            count = db.games.count_documents({"Season": season, "SeasonType": season_type})
            print(f"  ✓ Pulled {count} games")
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
        
        if i < len(seasons):
            time.sleep(2)  # Rate limiting between seasons
    
    final_count = db.games.count_documents({})
    print(f"\nTotal games: {final_count} (added {final_count - existing_count})")
    return final_count


def pull_boxscores_for_all_games(limit=None, sleep_seconds=1.2):
    """Pull boxscores for all games in database."""
    print(f"\n{'='*80}")
    print("STEP 2: Pulling boxscores from NBA API")
    print(f"{'='*80}")
    
    # Get all game IDs
    if limit:
        game_ids = get_unique_game_ids(limit=limit)
    else:
        game_ids = get_unique_game_ids(limit=10000)  # Large limit to get all
    
    print(f"Found {len(game_ids)} games to process")
    
    # Filter existing
    filtered_ids = []
    skipped = 0
    for gid in game_ids:
        if game_already_exists(gid):
            skipped += 1
        else:
            filtered_ids.append(gid)
    
    if skipped > 0:
        print(f"Skipping {skipped} games that already have boxscores")
    print(f"Processing {len(filtered_ids)} games...")
    
    total_players = 0
    failed = 0
    
    for i, gid in enumerate(filtered_ids, 1):
        success, count = pull_boxscore_traditional(gid)
        if success:
            total_players += count
            if i % 50 == 0:
                print(f"  Progress: {i}/{len(filtered_ids)} ({i*100//len(filtered_ids)}%)")
        else:
            failed += 1
        
        if i < len(filtered_ids):
            time.sleep(sleep_seconds)
    
    print(f"\n✓ Inserted {total_players} player rows")
    if failed > 0:
        print(f"  ✗ Failed: {failed} games")
    
    return total_players


def build_all_analytics(roll_n=5):
    """Build events and run full analytics pipeline."""
    print(f"\n{'='*80}")
    print("STEP 3: Building events and analytics")
    print(f"{'='*80}")
    
    # Step 1: Build team stats
    print("\n3a. Building team_game_stats...")
    num_games = build_team_stats_for_all_games()
    print(f"  ✓ Built team stats for {num_games} games")
    
    # Step 2: Build roles
    print("\n3b. Generating roles...")
    roles_count = refresh_roles_for_all_games()
    print(f"  ✓ Generated {roles_count} role documents")
    
    # Step 3: Build events
    print(f"\n3c. Building events (ROLL_N={roll_n})...")
    events_count = refresh_events_for_all_games(roll_n=roll_n)
    print(f"  ✓ Built {events_count} event documents")
    
    # Step 4: Add context tags
    print("\n3d. Adding context tags...")
    add_context_tags_to_events()
    print(f"  ✓ Context tags added")
    
    # Note: event_probs, pairs, graph can be run separately via refresh_all.py
    print("\n  Note: Run analytics pipeline separately for event_probs, pairs, graph if needed")
    
    return events_count


def main():
    parser = argparse.ArgumentParser(description="Expand dataset to ~5000 games")
    parser.add_argument("--target-games", type=int, default=5000, help="Target number of games (default: 5000)")
    parser.add_argument("--seasons", nargs="+", help="Specific seasons (e.g., 2023-24 2022-23). Auto-calculates if not provided")
    parser.add_argument("--season-type", default="Regular Season", help="Season type (default: Regular Season)")
    parser.add_argument("--skip-games", action="store_true", help="Skip pulling games")
    parser.add_argument("--skip-boxscores", action="store_true", help="Skip pulling boxscores")
    parser.add_argument("--skip-analytics", action="store_true", help="Skip building analytics")
    parser.add_argument("--sleep-boxscores", type=float, default=1.2, help="Sleep between boxscore requests (default: 1.2)")
    
    args = parser.parse_args()
    
    # Determine seasons
    if args.seasons:
        seasons = args.seasons
    else:
        # Calculate seasons needed (~1230 games per season)
        games_per_season = 1230
        n_seasons = max(1, (args.target_games + games_per_season - 1) // games_per_season)
        seasons = get_recent_seasons(n_years=min(n_seasons, 7))
        print(f"Auto-calculated {len(seasons)} seasons for ~{args.target_games} games: {seasons}")
    
    print(f"\n{'='*80}")
    print("DATASET EXPANSION")
    print(f"Target: ~{args.target_games} games")
    print(f"Seasons: {seasons}")
    print(f"{'='*80}")
    
    # Step 1: Pull games
    if not args.skip_games:
        total_games = pull_games_for_seasons(seasons, season_type=args.season_type)
    else:
        total_games = db.games.count_documents({})
        print(f"\nSkipping game pull. Existing games: {total_games}")
    
    # Step 2: Pull boxscores
    if not args.skip_boxscores:
        pull_boxscores_for_all_games(limit=None, sleep_seconds=args.sleep_boxscores)
    else:
        print("\nSkipping boxscore pull (--skip-boxscores)")
    
    # Step 3: Build analytics
    if not args.skip_analytics:
        build_all_analytics(roll_n=5)
    else:
        print("\nSkipping analytics build (--skip-analytics)")
    
    # Final summary
    events_count = db.events.count_documents({})
    print(f"\n{'='*80}")
    print("EXPANSION COMPLETE")
    print(f"{'='*80}")
    print(f"Total games: {total_games}")
    print(f"Total events: {events_count}")
    print(f"\nRun ML pipeline:")
    print(f"  PYTHONPATH=. python -m backend.ml.cli backtest")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
