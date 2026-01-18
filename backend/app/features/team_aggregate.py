from app.db import db

STAT_FIELDS = [
    "PTS", "AST", "REB", "FGA", "FTA", "FG3A", "TOV", "OREB", "DREB"
]

def to_num(x):
    try:
        return 0 if x is None else float(x)
    except Exception:
        return 0

def build_team_game_stats_for_game(game_id: str) -> int:
    players = list(db.player_game_stats.find({"GAME_ID": game_id}))
    if not players:
        return 0

    # group by TEAM_ID
    team_map = {}
    for p in players:
        team_id = p.get("TEAM_ID")
        if team_id is None:
            continue

        if team_id not in team_map:
            team_map[team_id] = {
                "GAME_ID": game_id,
                "TEAM_ID": team_id,
                "TEAM_ABBREVIATION": p.get("TEAM_ABBREVIATION"),
            }
            for f in STAT_FIELDS:
                team_map[team_id][f] = 0.0

        for f in STAT_FIELDS:
            team_map[team_id][f] += to_num(p.get(f))

    docs = list(team_map.values())

    # replace existing for that game
    db.team_game_stats.delete_many({"GAME_ID": game_id})
    db.team_game_stats.insert_many(docs)

    return len(docs)

def build_team_game_stats(limit_games: int = 10):
    # only build for games we already have player stats for
    game_ids = db.player_game_stats.distinct("GAME_ID")
    game_ids = game_ids[:limit_games]

    total_docs = 0
    for i, gid in enumerate(game_ids, 1):
        n = build_team_game_stats_for_game(gid)
        total_docs += n
        print(f"[{i}/{len(game_ids)}] {gid}: inserted {n} team docs")

    print(f"Done. Inserted {total_docs} team_game_stats docs.")

if __name__ == "__main__":
    build_team_game_stats(limit_games=10)
