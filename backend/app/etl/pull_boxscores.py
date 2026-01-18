from app.db import db
from app.etl.nba_api import nba_get
import time
import argparse
import requests

def get_unique_game_ids(limit=500, season="2023-24", season_type="Regular Season"):
    """
    Get unique game IDs from the games collection, sorted by GAME_ID for stable order.
    """
    cursor = db.games.find(
        {"Season": season, "SeasonType": season_type},
        {"GAME_ID": 1}
    ).sort("GAME_ID", 1)  # Sort for stable order
    
    game_ids = []
    seen = set()
    for doc in cursor:
        gid = doc.get("GAME_ID")
        if gid and gid not in seen:
            seen.add(gid)
            game_ids.append(gid)
        if len(game_ids) >= limit:
            break
    return game_ids

def game_already_exists(game_id: str) -> bool:
    """
    Check if player_game_stats already has documents for this GAME_ID.
    Used for resume functionality.
    """
    count = db.player_game_stats.count_documents({"GAME_ID": game_id})
    return count > 0

def pull_boxscore_traditional(game_id: str, max_retries=3):
    """
    Pull boxscore for a game with retry logic for network errors.
    nba_get already has retry logic, but we add an extra layer for persistent failures.
    Returns (success: bool, count: int)
    """
    for attempt in range(1, max_retries + 1):
        try:
            data = nba_get("boxscoretraditionalv2", {"GameID": game_id})

            result_sets = data.get("resultSets", [])
            if not result_sets:
                return (True, 0)

            # Find the "PlayerStats" table
            player_rs = None
            for rs in result_sets:
                if rs.get("name") == "PlayerStats":
                    player_rs = rs
                    break

            if player_rs is None:
                return (True, 0)

            headers = player_rs["headers"]
            rows = player_rs["rowSet"]
            docs = [dict(zip(headers, row)) for row in rows]

            for d in docs:
                d["GAME_ID"] = game_id

            if docs:
                # upsert strategy: delete existing for that game then insert fresh
                db.player_game_stats.delete_many({"GAME_ID": game_id})
                db.player_game_stats.insert_many(docs)

            return (True, len(docs))
            
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            # Network errors: retry with exponential backoff
            if attempt < max_retries:
                sleep_time = 2 ** (attempt - 1)  # 1s, 2s, 4s
                print(f"  Network error (attempt {attempt}/{max_retries}), retrying in {sleep_time}s...")
                time.sleep(sleep_time)
                continue
            else:
                print(f"  Failed after {max_retries} attempts: {type(e).__name__}")
                return (False, 0)
                
        except requests.exceptions.HTTPError as e:
            # HTTP errors (429, 5xx): retry with exponential backoff
            status_code = e.response.status_code if e.response else None
            if status_code in [429, 500, 502, 503, 504]:
                if attempt < max_retries:
                    sleep_time = 2 ** (attempt - 1)
                    print(f"  HTTP {status_code} (attempt {attempt}/{max_retries}), retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                    continue
                else:
                    print(f"  Failed after {max_retries} attempts: HTTP {status_code}")
                    return (False, 0)
            else:
                # Other HTTP errors: don't retry
                print(f"  HTTP error: {status_code if status_code else 'unknown'}")
                return (False, 0)
                
        except Exception as e:
            # Other errors (including from nba_get after its retries): log and continue
            if attempt < max_retries:
                sleep_time = 2 ** (attempt - 1)
                print(f"  Error {type(e).__name__} (attempt {attempt}/{max_retries}), retrying in {sleep_time}s...")
                time.sleep(sleep_time)
                continue
            else:
                print(f"  Failed after {max_retries} attempts: {type(e).__name__}: {str(e)[:100]}")
                return (False, 0)
    
    return (False, 0)

def run(limit=500, sleep_seconds=1.2, resume=True):
    """
    Pull boxscores for multiple games with rate limiting and resume support.
    
    Args:
        limit: Maximum number of game IDs to process (default 500)
        sleep_seconds: Delay between requests in seconds (default 1.2)
        resume: If True, skip games that already exist in player_game_stats (default True)
    """
    game_ids = get_unique_game_ids(limit=limit)
    print(f"Found {len(game_ids)} unique game IDs")
    
    if resume:
        # Filter out games that already exist
        existing_count = 0
        filtered_ids = []
        for gid in game_ids:
            if game_already_exists(gid):
                existing_count += 1
            else:
                filtered_ids.append(gid)
        game_ids = filtered_ids
        if existing_count > 0:
            print(f"Skipping {existing_count} games that already exist (resume mode)")
            print(f"Processing {len(game_ids)} remaining games")

    total_players = 0
    skipped = 0
    failed = 0
    
    for i, gid in enumerate(game_ids, 1):
        # Check if already exists (in case resume check was done earlier)
        if resume and game_already_exists(gid):
            skipped += 1
            print(f"[{i}/{len(game_ids)}] {gid}: skipped (already exists)")
            continue
        
        # Pull boxscore with retry logic
        success, count = pull_boxscore_traditional(gid)
        
        if success:
            total_players += count
            print(f"[{i}/{len(game_ids)}] {gid}: inserted {count} player rows (skipped? false)")
        else:
            failed += 1
            print(f"[{i}/{len(game_ids)}] {gid}: failed to pull (continuing...)")
        
        # Sleep between requests to avoid rate limiting (except after last request)
        if i < len(game_ids):
            time.sleep(sleep_seconds)
    
    print(f"\nDone.")
    print(f"  Inserted: {total_players} player rows total")
    if skipped > 0:
        print(f"  Skipped: {skipped} games (already existed)")
    if failed > 0:
        print(f"  Failed: {failed} games (network/API errors)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pull NBA boxscores with rate limiting and resume support")
    parser.add_argument("--limit", type=int, default=500, help="Maximum number of games to process (default: 500)")
    parser.add_argument("--sleep", type=float, default=1.2, help="Sleep seconds between requests (default: 1.2)")
    parser.add_argument("--no-resume", action="store_true", help="Disable resume mode (reprocess all games)")
    
    args = parser.parse_args()
    run(limit=args.limit, sleep_seconds=args.sleep, resume=not args.no_resume)
