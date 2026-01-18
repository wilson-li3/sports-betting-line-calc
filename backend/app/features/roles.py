from app.db import db

MIN_MINUTES = 20  # ignore fringe players

def to_num(x):
    try:
        return float(x)
    except Exception:
        return 0.0

def parse_minutes(x):
    """
    NBA boxscore MIN is often 'MM:SS' (e.g. '34:12').
    Convert to minutes as a float (34.2).
    """
    if x is None:
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)

    s = str(x).strip()
    if ":" in s:
        parts = s.split(":")
        if len(parts) == 2:
            m = to_num(parts[0])
            sec = to_num(parts[1])
            return m + sec / 60.0

    return to_num(s)

def compute_roles_for_game(game_id: str) -> int:
    players = list(db.player_game_stats.find({"GAME_ID": game_id}))
    if not players:
        return 0

    teams = {}
    for p in players:
        team_id = p.get("TEAM_ID")
        if team_id is None:
            continue
        teams.setdefault(team_id, []).append(p)

    role_docs = []

    for team_id, team_players in teams.items():
        # filter by minutes (handle 'MM:SS')
        eligible = [p for p in team_players if parse_minutes(p.get("MIN")) >= MIN_MINUTES]
        if not eligible:
            continue

        # team totals
        team_totals = db.team_game_stats.find_one({
            "GAME_ID": game_id,
            "TEAM_ID": team_id,
        })
        if not team_totals:
            continue

        team_pts = to_num(team_totals.get("PTS"))
        team_ast = to_num(team_totals.get("AST"))
        team_reb = to_num(team_totals.get("REB"))

        def shares(p):
            return {
                "pts_share": to_num(p.get("PTS")) / team_pts if team_pts > 0 else 0.0,
                "ast_share": to_num(p.get("AST")) / team_ast if team_ast > 0 else 0.0,
                "reb_share": to_num(p.get("REB")) / team_reb if team_reb > 0 else 0.0,
            }

        scored = [(p, shares(p)) for p in eligible]

        primary_scorer = max(scored, key=lambda x: x[1]["pts_share"])
        primary_facilitator = max(scored, key=lambda x: x[1]["ast_share"])
        primary_rebounder = max(scored, key=lambda x: x[1]["reb_share"])

        role_docs.append({
            "GAME_ID": game_id,
            "TEAM_ID": team_id,
            "TEAM_ABBREVIATION": primary_scorer[0].get("TEAM_ABBREVIATION"),

            "primary_scorer": {
                "PLAYER_ID": primary_scorer[0].get("PLAYER_ID"),
                "PLAYER_NAME": primary_scorer[0].get("PLAYER_NAME"),
                "MIN": parse_minutes(primary_scorer[0].get("MIN")),
                "PTS": to_num(primary_scorer[0].get("PTS")),
                "share": primary_scorer[1]["pts_share"],
            },

            "primary_facilitator": {
                "PLAYER_ID": primary_facilitator[0].get("PLAYER_ID"),
                "PLAYER_NAME": primary_facilitator[0].get("PLAYER_NAME"),
                "MIN": parse_minutes(primary_facilitator[0].get("MIN")),
                "AST": to_num(primary_facilitator[0].get("AST")),
                "share": primary_facilitator[1]["ast_share"],
            },

            "primary_rebounder": {
                "PLAYER_ID": primary_rebounder[0].get("PLAYER_ID"),
                "PLAYER_NAME": primary_rebounder[0].get("PLAYER_NAME"),
                "MIN": parse_minutes(primary_rebounder[0].get("MIN")),
                "REB": to_num(primary_rebounder[0].get("REB")),
                "share": primary_rebounder[1]["reb_share"],
            },
        })

    # replace roles for this game
    db.roles_by_game.delete_many({"GAME_ID": game_id})
    if role_docs:
        db.roles_by_game.insert_many(role_docs)

    return len(role_docs)

def compute_roles(limit_games=10):
    game_ids = db.team_game_stats.distinct("GAME_ID")
    game_ids = game_ids[:limit_games]

    total = 0
    for i, gid in enumerate(game_ids, 1):
        n = compute_roles_for_game(gid)
        total += n
        print(f"[{i}/{len(game_ids)}] {gid}: inserted {n} role docs")

    print(f"Done. Inserted {total} roles.")

if __name__ == "__main__":
    compute_roles(limit_games=10)
