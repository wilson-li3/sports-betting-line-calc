from app.db import db
from app.etl.nba_api import nba_get

def get_unique_game_ids(limit=10, season="2023-24", season_type="Regular Season"):
    # leaguegamelog returns two rows per game (one per team), so we dedupe by GAME_ID
    cursor = db.games.find(
        {"Season": season, "SeasonType": season_type},
        {"GAME_ID": 1}
    ).limit(limit * 3)  # small cushion
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

def pull_boxscore_traditional(game_id: str):
    data = nba_get("boxscoretraditionalv2", {"GameID": game_id})

    result_sets = data.get("resultSets", [])
    if not result_sets:
        return 0

    # Find the "PlayerStats" table
    player_rs = None
    for rs in result_sets:
        if rs.get("name") == "PlayerStats":
            player_rs = rs
            break

    if player_rs is None:
        return 0

    headers = player_rs["headers"]
    rows = player_rs["rowSet"]
    docs = [dict(zip(headers, row)) for row in rows]

    for d in docs:
        d["GAME_ID"] = game_id

    if docs:
        # upsert strategy: delete existing for that game then insert fresh
        db.player_game_stats.delete_many({"GAME_ID": game_id})
        db.player_game_stats.insert_many(docs)

    return len(docs)

def run(limit=10):
    game_ids = get_unique_game_ids(limit=limit)
    print(f"Found {len(game_ids)} unique game IDs")

    total_players = 0
    for i, gid in enumerate(game_ids, 1):
        n = pull_boxscore_traditional(gid)
        total_players += n
        print(f"[{i}/{len(game_ids)}] {gid}: inserted {n} player rows")

    print(f"Done. Inserted {total_players} player rows total.")

if __name__ == "__main__":
    run(limit=10)
