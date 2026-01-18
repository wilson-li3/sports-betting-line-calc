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
        
        # Additional player stats
        ps_ast_actual = to_num(ps_row.get("AST"))
        ps_reb_actual = to_num(ps_row.get("REB"))
        ps_fg3m_actual = to_num(ps_row.get("FG3M", 0))  # 3-pointers made (may not exist)
        pf_reb_actual = to_num(pf_row.get("REB"))
        pr_pts_actual = to_num(pr_row.get("PTS"))
        
        # Compute PRA (Points + Rebounds + Assists)
        ps_pra_actual = ps_actual + ps_reb_actual + ps_ast_actual
        pf_pra_actual = pr_pts_actual + pf_reb_actual + pf_actual
        pr_pra_actual = pr_actual + pr_pts_actual + to_num(pr_row.get("AST"))
        
        # Synthetic lines for additional stats
        ps_ast_line = rolling_median(get_player_last_values(ps["PLAYER_ID"], game_id, "AST", n=roll_n))
        ps_reb_line = rolling_median(get_player_last_values(ps["PLAYER_ID"], game_id, "REB", n=roll_n))
        ps_fg3m_line = rolling_median(get_player_last_values(ps["PLAYER_ID"], game_id, "FG3M", n=roll_n)) if ps_fg3m_actual > 0 or any(get_player_last_values(ps["PLAYER_ID"], game_id, "FG3M", n=roll_n)) else None
        pf_reb_line = rolling_median(get_player_last_values(pf["PLAYER_ID"], game_id, "REB", n=roll_n))
        pr_pts_line = rolling_median(get_player_last_values(pr["PLAYER_ID"], game_id, "PTS", n=roll_n))
        
        # PRA lines (sum of component lines)
        ps_pra_line = (ps_line or 0) + (ps_reb_line or 0) + (ps_ast_line or 0)
        pf_pra_line = (pr_pts_line or 0) + (pf_reb_line or 0) + (pf_line or 0)
        pr_pra_line = (pr_line or 0) + (pr_pts_line or 0) + (rolling_median(get_player_last_values(pr["PLAYER_ID"], game_id, "AST", n=roll_n)) or 0)
        
        # Round lines
        ps_ast_line = round_half(ps_ast_line) if ps_ast_line is not None else None
        ps_reb_line = round_half(ps_reb_line) if ps_reb_line is not None else None
        ps_fg3m_line = round_half(ps_fg3m_line) if ps_fg3m_line is not None else None
        pf_reb_line = round_half(pf_reb_line) if pf_reb_line is not None else None
        pr_pts_line = round_half(pr_pts_line) if pr_pts_line is not None else None
        ps_pra_line = round_half(ps_pra_line)
        pf_pra_line = round_half(pf_pra_line)
        pr_pra_line = round_half(pr_pra_line)
        
        # Strong hit thresholds
        STRONG_HIT_THRESHOLDS = {
            "PTS": 3.0,
            "AST": 1.0,
            "REB": 2.0,
            "PRA": 5.0,
            "FG3M": 1.0,
        }
        
        # Build event doc with expanded stats and margins
        doc = {
            "GAME_ID": game_id,
            "TEAM_ID": team_id,
            "TEAM_ABBREVIATION": r.get("TEAM_ABBREVIATION"),

            # Game-level events
            "GAME_TOTAL_LINE": game_total_line,
            "GAME_TOTAL_ACTUAL": game_total_actual,
            "GAME_TOTAL_OVER_HIT": int(game_total_actual > game_total_line),
            "GAME_TOTAL_MARGIN": game_total_actual - game_total_line,
            "GAME_TOTAL_STRONG_HIT": int((game_total_actual - game_total_line) >= STRONG_HIT_THRESHOLDS.get("PTS", 3.0)),

            # Team-level events
            "TEAM_TOTAL_LINE": team_total_line,
            "TEAM_TOTAL_ACTUAL": team_total_actual,
            "TEAM_TOTAL_OVER_HIT": int(team_total_actual > team_total_line),
            "TEAM_TOTAL_MARGIN": team_total_actual - team_total_line,
            "TEAM_TOTAL_STRONG_HIT": int((team_total_actual - team_total_line) >= STRONG_HIT_THRESHOLDS.get("PTS", 3.0)),

            # Primary scorer events
            "PRIMARY_SCORER_PLAYER_ID": ps["PLAYER_ID"],
            "PRIMARY_SCORER_NAME": ps["PLAYER_NAME"],
            "PRIMARY_SCORER_PTS_LINE": ps_line,
            "PRIMARY_SCORER_PTS_ACTUAL": ps_actual,
            "PRIMARY_SCORER_PTS_OVER_HIT": int(ps_actual > ps_line),
            "PRIMARY_SCORER_PTS_MARGIN": ps_actual - ps_line,
            "PRIMARY_SCORER_PTS_STRONG_HIT": int((ps_actual - ps_line) >= STRONG_HIT_THRESHOLDS["PTS"]),
            "PRIMARY_SCORER_AST_LINE": ps_ast_line,
            "PRIMARY_SCORER_AST_ACTUAL": ps_ast_actual,
            "PRIMARY_SCORER_AST_OVER_HIT": int(ps_ast_actual > ps_ast_line) if ps_ast_line is not None else None,
            "PRIMARY_SCORER_AST_MARGIN": ps_ast_actual - ps_ast_line if ps_ast_line is not None else None,
            "PRIMARY_SCORER_AST_STRONG_HIT": int((ps_ast_actual - ps_ast_line) >= STRONG_HIT_THRESHOLDS["AST"]) if ps_ast_line is not None else None,
            "PRIMARY_SCORER_REB_LINE": ps_reb_line,
            "PRIMARY_SCORER_REB_ACTUAL": ps_reb_actual,
            "PRIMARY_SCORER_REB_OVER_HIT": int(ps_reb_actual > ps_reb_line) if ps_reb_line is not None else None,
            "PRIMARY_SCORER_REB_MARGIN": ps_reb_actual - ps_reb_line if ps_reb_line is not None else None,
            "PRIMARY_SCORER_REB_STRONG_HIT": int((ps_reb_actual - ps_reb_line) >= STRONG_HIT_THRESHOLDS["REB"]) if ps_reb_line is not None else None,
            "PRIMARY_SCORER_PRA_LINE": ps_pra_line,
            "PRIMARY_SCORER_PRA_ACTUAL": ps_pra_actual,
            "PRIMARY_SCORER_PRA_OVER_HIT": int(ps_pra_actual > ps_pra_line),
            "PRIMARY_SCORER_PRA_MARGIN": ps_pra_actual - ps_pra_line,
            "PRIMARY_SCORER_PRA_STRONG_HIT": int((ps_pra_actual - ps_pra_line) >= STRONG_HIT_THRESHOLDS["PRA"]),
        }
        
        # Add 3PTM if available
        if ps_fg3m_line is not None:
            doc["PRIMARY_SCORER_FG3M_LINE"] = ps_fg3m_line
            doc["PRIMARY_SCORER_FG3M_ACTUAL"] = ps_fg3m_actual
            doc["PRIMARY_SCORER_FG3M_OVER_HIT"] = int(ps_fg3m_actual > ps_fg3m_line)
            doc["PRIMARY_SCORER_FG3M_MARGIN"] = ps_fg3m_actual - ps_fg3m_line
            doc["PRIMARY_SCORER_FG3M_STRONG_HIT"] = int((ps_fg3m_actual - ps_fg3m_line) >= STRONG_HIT_THRESHOLDS["FG3M"])
        
        # Primary facilitator events
        doc.update({
            "PRIMARY_FACILITATOR_PLAYER_ID": pf["PLAYER_ID"],
            "PRIMARY_FACILITATOR_NAME": pf["PLAYER_NAME"],
            "PRIMARY_FACILITATOR_AST_LINE": pf_line,
            "PRIMARY_FACILITATOR_AST_ACTUAL": pf_actual,
            "PRIMARY_FACILITATOR_AST_OVER_HIT": int(pf_actual > pf_line),
            "PRIMARY_FACILITATOR_AST_MARGIN": pf_actual - pf_line,
            "PRIMARY_FACILITATOR_AST_STRONG_HIT": int((pf_actual - pf_line) >= STRONG_HIT_THRESHOLDS["AST"]),
            "PRIMARY_FACILITATOR_REB_LINE": pf_reb_line,
            "PRIMARY_FACILITATOR_REB_ACTUAL": pf_reb_actual,
            "PRIMARY_FACILITATOR_REB_OVER_HIT": int(pf_reb_actual > pf_reb_line) if pf_reb_line is not None else None,
            "PRIMARY_FACILITATOR_REB_MARGIN": pf_reb_actual - pf_reb_line if pf_reb_line is not None else None,
            "PRIMARY_FACILITATOR_REB_STRONG_HIT": int((pf_reb_actual - pf_reb_line) >= STRONG_HIT_THRESHOLDS["REB"]) if pf_reb_line is not None else None,
            "PRIMARY_FACILITATOR_PRA_LINE": pf_pra_line,
            "PRIMARY_FACILITATOR_PRA_ACTUAL": pf_pra_actual,
            "PRIMARY_FACILITATOR_PRA_OVER_HIT": int(pf_pra_actual > pf_pra_line),
            "PRIMARY_FACILITATOR_PRA_MARGIN": pf_pra_actual - pf_pra_line,
            "PRIMARY_FACILITATOR_PRA_STRONG_HIT": int((pf_pra_actual - pf_pra_line) >= STRONG_HIT_THRESHOLDS["PRA"]),
        })
        
        # Primary rebounder events
        doc.update({
            "PRIMARY_REBOUNDER_PLAYER_ID": pr["PLAYER_ID"],
            "PRIMARY_REBOUNDER_NAME": pr["PLAYER_NAME"],
            "PRIMARY_REBOUNDER_REB_LINE": pr_line,
            "PRIMARY_REBOUNDER_REB_ACTUAL": pr_actual,
            "PRIMARY_REBOUNDER_REB_OVER_HIT": int(pr_actual > pr_line),
            "PRIMARY_REBOUNDER_REB_MARGIN": pr_actual - pr_line,
            "PRIMARY_REBOUNDER_REB_STRONG_HIT": int((pr_actual - pr_line) >= STRONG_HIT_THRESHOLDS["REB"]),
            "PRIMARY_REBOUNDER_PTS_LINE": pr_pts_line,
            "PRIMARY_REBOUNDER_PTS_ACTUAL": pr_pts_actual,
            "PRIMARY_REBOUNDER_PTS_OVER_HIT": int(pr_pts_actual > pr_pts_line) if pr_pts_line is not None else None,
            "PRIMARY_REBOUNDER_PTS_MARGIN": pr_pts_actual - pr_pts_line if pr_pts_line is not None else None,
            "PRIMARY_REBOUNDER_PTS_STRONG_HIT": int((pr_pts_actual - pr_pts_line) >= STRONG_HIT_THRESHOLDS["PTS"]) if pr_pts_line is not None else None,
            "PRIMARY_REBOUNDER_PRA_LINE": pr_pra_line,
            "PRIMARY_REBOUNDER_PRA_ACTUAL": pr_pra_actual,
            "PRIMARY_REBOUNDER_PRA_OVER_HIT": int(pr_pra_actual > pr_pra_line),
            "PRIMARY_REBOUNDER_PRA_MARGIN": pr_pra_actual - pr_pra_line,
            "PRIMARY_REBOUNDER_PRA_STRONG_HIT": int((pr_pra_actual - pr_pra_line) >= STRONG_HIT_THRESHOLDS["PRA"]),
        })
        
        docs.append(doc)

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
