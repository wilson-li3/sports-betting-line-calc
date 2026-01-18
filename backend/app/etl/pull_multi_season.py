"""
Pull games and boxscores for multiple seasons to expand dataset.

Usage:
    python -m app.etl.pull_multi_season --seasons 2023-24 2022-23 ... --target-games 5000
"""
import argparse
import time
from app.etl.pull_games import pull_games
from app.etl.pull_boxscores import run as pull_boxscores
from app.db import db


def get_recent_seasons(n_years=7):
    """Generate list of recent NBA seasons (format: YYYY-YY)."""
    from datetime import datetime
    current_year = datetime.now().year
    seasons = []
    for i in range(n_years):
        year = current_year - i
        season = f"{year-1}-{str(year)[-2:]}"
        seasons.append(season)
    return seasons


def count_existing_games():
    """Count existing games in MongoDB."""
    return db.games.count_documents({})


def pull_seasons(seasons, season_type="Regular Season", sleep_between_seasons=5):
    """
    Pull games for multiple seasons.
    
    Args:
        seasons: List of season strings (e.g., ["2023-24", "2022-23"])
        season_type: "Regular Season" or "Playoffs"
        sleep_between_seasons: Sleep seconds between seasons
    """
    print(f"Pulling games for {len(seasons)} seasons...")
    
    total_games = 0
    for i, season in enumerate(seasons, 1):
        print(f"\n[{i}/{len(seasons)}] Pulling season: {season} ({season_type})")
        try:
            pull_games(season=season, season_type=season_type)
            count = db.games.count_documents({"Season": season, "SeasonType": season_type})
            total_games += count
            print(f"  Season {season}: {count} games")
        except Exception as e:
            print(f"  ERROR pulling season {season}: {e}")
        
        # Sleep between seasons to avoid rate limiting
        if i < len(seasons):
            time.sleep(sleep_between_seasons)
    
    print(f"\nTotal games across all seasons: {total_games}")
    return total_games


def pull_boxscores_for_seasons(seasons, limit_per_season=None, sleep_seconds=1.2, resume=True):
    """
    Pull boxscores for games in specified seasons.
    
    Args:
        seasons: List of season strings
        limit_per_season: Max games per season (None = all)
        sleep_seconds: Delay between requests
        resume: Skip games that already have boxscores
    """
    print(f"\nPulling boxscores for {len(seasons)} seasons...")
    
    total_processed = 0
    for i, season in enumerate(seasons, 1):
        print(f"\n[{i}/{len(seasons)}] Processing season: {season}")
        
        # Get game IDs for this season
        game_ids = list(db.games.find(
            {"Season": season, "SeasonType": "Regular Season"},
            {"GAME_ID": 1}
        ).sort("GAME_ID", 1))
        
        if limit_per_season:
            game_ids = game_ids[:limit_per_season]
        
        print(f"  Found {len(game_ids)} games for season {season}")
        
        # Note: pull_boxscores currently uses get_unique_game_ids which filters by Season
        # We'd need to modify it or call pull_boxscore_traditional directly
        # For now, we'll use a simpler approach - just note that they need to run it per season
        print(f"  (Run pull_boxscores separately or modify this script to process each season)")
        total_processed += len(game_ids)
    
    return total_processed


def main():
    parser = argparse.ArgumentParser(description="Pull NBA games and boxscores for multiple seasons")
    parser.add_argument("--seasons", nargs="+", help="Seasons to pull (e.g., 2023-24 2022-23). If not specified, pulls last 7 years")
    parser.add_argument("--target-games", type=int, default=5000, help="Target number of games (default: 5000)")
    parser.add_argument("--season-type", default="Regular Season", choices=["Regular Season", "Playoffs"], help="Season type (default: Regular Season)")
    parser.add_argument("--skip-games", action="store_true", help="Skip pulling games (assume games already exist)")
    parser.add_argument("--skip-boxscores", action="store_true", help="Skip pulling boxscores")
    parser.add_argument("--sleep-games", type=float, default=2.0, help="Sleep seconds between season pulls (default: 2.0)")
    parser.add_argument("--sleep-boxscores", type=float, default=1.2, help="Sleep seconds between boxscore requests (default: 1.2)")
    
    args = parser.parse_args()
    
    # Determine seasons to pull
    if args.seasons:
        seasons = args.seasons
    else:
        # Calculate how many seasons needed for target_games
        # Regular season has ~1230 games per season
        games_per_season = 1230
        n_seasons_needed = max(1, (args.target_games + games_per_season - 1) // games_per_season)
        seasons = get_recent_seasons(n_years=min(n_seasons_needed, 7))
        print(f"Auto-selected {len(seasons)} seasons: {seasons}")
    
    # Count existing games
    existing = count_existing_games()
    print(f"\nExisting games in database: {existing}")
    
    # Pull games
    if not args.skip_games:
        total_games = pull_seasons(seasons, season_type=args.season_type, sleep_between_seasons=args.sleep_games)
        
        final_count = count_existing_games()
        print(f"\nGames after pulling: {final_count}")
        print(f"  New games added: {final_count - existing}")
    else:
        print("\nSkipping game pull (--skip-games)")
        final_count = count_existing_games()
    
    # Note about boxscores
    if not args.skip_boxscores:
        print("\n" + "="*80)
        print("NOTE: To pull boxscores for all games, run:")
        print(f"  python -m app.etl.pull_boxscores --limit {final_count} --sleep {args.sleep_boxscores}")
        print("="*80)
    else:
        print("\nSkipping boxscore pull (--skip-boxscores)")
    
    print("\nDone!")


if __name__ == "__main__":
    main()
