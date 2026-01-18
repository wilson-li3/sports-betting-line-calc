"""
Refresh all analytics: roles, events, and pair stats for all available games.

This script:
1. Reads all distinct GAME_IDs from player_game_stats
2. Builds team_game_stats if needed
3. Generates roles for all games
4. Builds events for all games
5. Computes pair_stats from events

Safe to run multiple times (idempotent).
"""

from app.db import db
from app.features.roles import compute_roles_for_game
from app.features.team_aggregate import build_team_game_stats_for_game
from app.analytics.build_events import build_events_for_game, ROLL_N
from app.analytics.compute_pairs import compute_pairs
import argparse

def build_team_stats_for_all_games():
    """
    Build team_game_stats for all games that have player_game_stats but no team_game_stats.
    """
    # Get all game IDs from player_game_stats
    all_game_ids = sorted(db.player_game_stats.distinct("GAME_ID"))
    
    # Find games that need team stats
    games_with_team_stats = set(db.team_game_stats.distinct("GAME_ID"))
    games_needing_stats = [gid for gid in all_game_ids if gid not in games_with_team_stats]
    
    if not games_needing_stats:
        print("All games already have team_game_stats.")
        return len(all_game_ids)
    
    print(f"Building team_game_stats for {len(games_needing_stats)} games...")
    total = 0
    for i, gid in enumerate(games_needing_stats, 1):
        n = build_team_game_stats_for_game(gid)
        total += n
        if i % 50 == 0 or i == len(games_needing_stats):
            print(f"  [{i}/{len(games_needing_stats)}] {gid}: {n} team docs")
    
    print(f"Done. Built team_game_stats for {len(games_needing_stats)} games ({total} team docs total).")
    return len(all_game_ids)

def refresh_roles_for_all_games():
    """
    Generate roles for all games that have player_game_stats and team_game_stats.
    """
    # Get all game IDs that have both player and team stats
    player_games = set(db.player_game_stats.distinct("GAME_ID"))
    team_games = set(db.team_game_stats.distinct("GAME_ID"))
    game_ids = sorted(list(player_games & team_games))
    
    if not game_ids:
        print("No games found with both player_game_stats and team_game_stats.")
        return 0
    
    print(f"Generating roles for {len(game_ids)} games...")
    total = 0
    for i, gid in enumerate(game_ids, 1):
        n = compute_roles_for_game(gid)
        total += n
        if i % 50 == 0 or i == len(game_ids):
            print(f"  [{i}/{len(game_ids)}] {gid}: {n} role docs")
    
    print(f"Done. Generated {total} role docs for {len(game_ids)} games.")
    return total

def refresh_events_for_all_games(roll_n=5):
    """
    Build events for all games that have roles.
    
    Args:
        roll_n: Number of past games to use for rolling median (default 5)
    """
    # Get all game IDs that have roles
    game_ids = sorted(db.roles_by_game.distinct("GAME_ID"))
    
    if not game_ids:
        print("No games found with roles. Run roles generation first.")
        return 0
    
    print(f"Building events for {len(game_ids)} games (ROLL_N={roll_n})...")
    
    total = 0
    for i, gid in enumerate(game_ids, 1):
        n = build_events_for_game(gid, roll_n=roll_n)
        total += n
        if i % 50 == 0 or i == len(game_ids):
            print(f"  [{i}/{len(game_ids)}] {gid}: {n} event docs")
    
    print(f"Done. Built {total} event docs for {len(game_ids)} games.")
    return total

def refresh_all(roll_n=5):
    """
    Run the complete refresh sequence:
    1. Build team_game_stats
    2. Generate roles
    3. Build events
    4. Compute pair_stats
    """
    print("=" * 60)
    print("REFRESH ALL ANALYTICS")
    print("=" * 60)
    
    # Step 1: Team stats
    print("\n[1/4] Building team_game_stats...")
    num_games = build_team_stats_for_all_games()
    
    # Step 2: Roles
    print("\n[2/4] Generating roles...")
    num_roles = refresh_roles_for_all_games()
    
    # Step 3: Events
    print(f"\n[3/4] Building events (ROLL_N={roll_n})...")
    num_events = refresh_events_for_all_games(roll_n=roll_n)
    
    # Step 4: Pair stats
    print("\n[4/4] Computing pair_stats...")
    compute_pairs()
    
    print("\n" + "=" * 60)
    print("REFRESH COMPLETE")
    print("=" * 60)
    print(f"Games processed: {num_games}")
    print(f"Roles generated: {num_roles}")
    print(f"Events built: {num_events}")
    print(f"Pair stats: computed from events")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh all analytics (roles, events, pairs)")
    parser.add_argument("--roll-n", type=int, default=5, help="Number of past games for rolling median (default: 5)")
    
    args = parser.parse_args()
    refresh_all(roll_n=args.roll_n)
