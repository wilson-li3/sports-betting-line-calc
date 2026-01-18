from app.db import db
from statistics import median

ROLL_N = 10  # how many past games we use to make a synthetic "line"

def to_num(x):
    try:
        return float(x)
    except Exception:
        return 0.0

def round_half(x: float) -> float:
    return round(x * 2) / 2.0

def rolling_median(values):
    if not values:
        return None
    return median(values)

def get_team_last_values(team_id, before_game_id, field, n=ROLL_N):
    cur = db.team_game_stats.find(
        {"TEAM_ID": team_id, "GAME_ID": {"$lt": before_game_id}},
        {field: 1, "GAME_ID": 1}
    ).sort("GAME_ID", -1).limit(n)

    vals = [to_num(d.get(field)) for d in cur]
    return list(reversed(vals))

def get_player_last_values(player_id, before_game_id, field, n=ROLL_N):
    cur = db.player_game_stats.find(
        {"PLAYER_ID": player_id, "GAME_ID": {"$lt": before_game_id}},
        {field: 1, "GAME_ID": 1}
    ).sort("GAME_ID", -1).limit(n)

    vals = [to_num(d.get(field)) for d in cur]
    return list(reversed(vals))

def past_game_totals(before_game_id, n=ROLL_N):
    """
    team_game_stats has 2 docs per game (one per team).
    We group by GAME_ID to get total points per game.
    """
    cur = db.team_game_stats.find(
        {"GAME_ID": {"$lt": before_game_id}},
        {"GAME_ID": 1, "PTS": 1}
    ).sort("GAME_ID", -1).limit(n * 4)

    totals = {}
    for d in cur:
        gid = d.get("GAME_ID")
        totals.setdefault(gid, 0.0)
        totals[gid] += to_num(d.get("PTS"))

    # keep most recent games
    vals = list(totals.values())[:n]
    return list(reversed(vals))

def build_events_for_game(game_id: str, roll_n: int = None) -> int:
    """
    Build events for a game.
    
    Args:
        game_id: The game ID
        roll_n: Number of past games for rolling median (defaults to module ROLL_N if None)
    """
    if roll_n is None:
        roll_n = ROLL_N
    
    roles = list(db.roles_by_game.find({"GAME_ID": game_id}))
    if not roles:
        return 0

    teams = list(db.team_game_stats.find({"GAME_ID": game_id}))
    if len(teams) < 2:
        return 0

    # actual game total points
    game_total_actual = sum(to_num(t.get("PTS")) for t in teams)

    # synthetic game total line
    totals_hist = past_game_totals(game_id, n=roll_n)
    game_total_line = rolling_median(totals_hist)
    if game_total_line is None:
        return 0
    game_total_line = round_half(game_total_line)

    docs = []

    for r in roles:
        team_id = r["TEAM_ID"]

        team_doc = db.team_game_stats.find_one({"GAME_ID": game_id, "TEAM_ID": team_id})
        if not team_doc:
            continue

        team_total_actual = to_num(team_doc.get("PTS"))
        team_hist = get_team_last_values(team_id, game_id, "PTS", n=roll_n)
        team_total_line = rolling_median(team_hist)
        if team_total_line is None:
            continue
        team_total_line = round_half(team_total_line)

        # role players
        ps = r["primary_scorer"]
        pf = r["primary_facilitator"]
        pr = r["primary_rebounder"]

        # synthetic role-player lines
        ps_line = rolling_median(get_player_last_values(ps["PLAYER_ID"], game_id, "PTS", n=roll_n))
        pf_line = rolling_median(get_player_last_values(pf["PLAYER_ID"], game_id, "AST", n=roll_n))
        pr_line = rolling_median(get_player_last_values(pr["PLAYER_ID"], game_id, "REB", n=roll_n))

        if ps_line is None or pf_line is None or pr_line is None:
            continue

        ps_line = round_half(ps_line)
        pf_line = round_half(pf_line)
        pr_line = round_half(pr_line)

        ps_row = db.player_game_stats.find_one({"GAME_ID": game_id, "PLAYER_ID": ps["PLAYER_ID"]}) or {}
        pf_row = db.player_game_stats.find_one({"GAME_ID": game_id, "PLAYER_ID": pf["PLAYER_ID"]}) or {}
        pr_row = db.player_game_stats.find_one({"GAME_ID": game_id, "PLAYER_ID": pr["PLAYER_ID"]}) or {}

        ps_actual = to_num(ps_row.get("PTS"))
        pf_actual = to_num(pf_row.get("AST"))
        pr_actual = to_num(pr_row.get("REB"))

        docs.append({
            "GAME_ID": game_id,
            "TEAM_ID": team_id,
            "TEAM_ABBREVIATION": r.get("TEAM_ABBREVIATION"),

            "GAME_TOTAL_LINE": game_total_line,
            "GAME_TOTAL_ACTUAL": game_total_actual,
            "GAME_TOTAL_OVER_HIT": int(game_total_actual > game_total_line),

            "TEAM_TOTAL_LINE": team_total_line,
            "TEAM_TOTAL_ACTUAL": team_total_actual,
            "TEAM_TOTAL_OVER_HIT": int(team_total_actual > team_total_line),

            "PRIMARY_SCORER_PLAYER_ID": ps["PLAYER_ID"],
            "PRIMARY_SCORER_NAME": ps["PLAYER_NAME"],
            "PRIMARY_SCORER_PTS_LINE": ps_line,
            "PRIMARY_SCORER_PTS_ACTUAL": ps_actual,
            "PRIMARY_SCORER_PTS_OVER_HIT": int(ps_actual > ps_line),

            "PRIMARY_FACILITATOR_PLAYER_ID": pf["PLAYER_ID"],
            "PRIMARY_FACILITATOR_NAME": pf["PLAYER_NAME"],
            "PRIMARY_FACILITATOR_AST_LINE": pf_line,
            "PRIMARY_FACILITATOR_AST_ACTUAL": pf_actual,
            "PRIMARY_FACILITATOR_AST_OVER_HIT": int(pf_actual > pf_line),

            "PRIMARY_REBOUNDER_PLAYER_ID": pr["PLAYER_ID"],
            "PRIMARY_REBOUNDER_NAME": pr["PLAYER_NAME"],
            "PRIMARY_REBOUNDER_REB_LINE": pr_line,
            "PRIMARY_REBOUNDER_REB_ACTUAL": pr_actual,
            "PRIMARY_REBOUNDER_REB_OVER_HIT": int(pr_actual > pr_line),
        })

    db.events.delete_many({"GAME_ID": game_id})
    if docs:
        db.events.insert_many(docs)

    return len(docs)

def run(limit_games=10):
    # use games we already have player stats for
    game_ids = sorted(db.player_game_stats.distinct("GAME_ID"))[:limit_games]

    total = 0
    for i, gid in enumerate(game_ids, 1):
        n = build_events_for_game(gid)
        total += n
        print(f"[{i}/{len(game_ids)}] {gid}: inserted {n} event docs")

    print(f"Done. Inserted {total} event docs total.")

if __name__ == "__main__":
    run(limit_games=10)
