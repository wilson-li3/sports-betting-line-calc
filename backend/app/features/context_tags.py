"""
Add context tags to events to capture regimes where relationships may change.

Context tags include:
- HOME vs AWAY
- REST_BUCKET (if dates available)
- PACE_BUCKET (LOW/MID/HIGH)
- GAME_COMPETITIVE (CLOSE vs BLOWOUT)
- OPPONENT_STRENGTH_BUCKET (if feasible)
"""

from app.db import db
from statistics import median

def to_num(x):
    try:
        return float(x) if x is not None else 0.0
    except:
        return 0.0

def compute_pace_proxy(team_doc):
    """
    Compute pace proxy: FGA + FTA + TOV - OREB
    If not available, use PTS as proxy.
    """
    fga = to_num(team_doc.get("FGA", 0))
    fta = to_num(team_doc.get("FTA", 0))
    tov = to_num(team_doc.get("TOV", 0))
    oreb = to_num(team_doc.get("OREB", 0))
    
    if fga > 0 or fta > 0:
        return fga + fta + tov - oreb
    else:
        # Fallback to PTS as proxy
        return to_num(team_doc.get("PTS", 0))


def get_pace_buckets(events):
    """
    Compute pace buckets (LOW/MID/HIGH) from all team pace proxies.
    """
    pace_values = []
    for event in events:
        team_id = event.get("TEAM_ID")
        game_id = event.get("GAME_ID")
        team_doc = db.team_game_stats.find_one({"GAME_ID": game_id, "TEAM_ID": team_id})
        if team_doc:
            pace_values.append(compute_pace_proxy(team_doc))
    
    if not pace_values:
        return None, None, None
    
    pace_sorted = sorted(pace_values)
    n = len(pace_sorted)
    low_threshold = pace_sorted[n // 3] if n >= 3 else pace_sorted[0]
    high_threshold = pace_sorted[2 * n // 3] if n >= 3 else pace_sorted[-1]
    
    return low_threshold, high_threshold, median(pace_values)


def add_context_tags_to_events():
    """
    Add context tags to all events in the events collection.
    Idempotent: updates existing context fields.
    """
    events = list(db.events.find({}))
    if not events:
        print("No events found.")
        return 0
    
    print(f"Adding context tags to {len(events)} events...")
    
    # Compute pace buckets once
    low_pace, high_pace, med_pace = get_pace_buckets(events)
    
    updated = 0
    for event in events:
        game_id = event.get("GAME_ID")
        team_id = event.get("TEAM_ID")
        
        if not game_id or not team_id:
            continue
        
        # Get game info
        game_doc = db.games.find_one({"GAME_ID": game_id})
        team_doc = db.team_game_stats.find_one({"GAME_ID": game_id, "TEAM_ID": team_id})
        
        context = {}
        
        # HOME vs AWAY (try to infer from MATCHUP or game structure)
        if game_doc:
            matchup = game_doc.get("MATCHUP", "")
            # NBA matchup format: "TEAM @ OPPONENT" or "TEAM vs OPPONENT"
            if "@" in matchup:
                context["home"] = False
            elif "vs" in matchup.lower():
                context["home"] = True
            else:
                # Default: assume home if we can't determine
                context["home"] = None
        
        # PACE_BUCKET
        if team_doc:
            pace_proxy = compute_pace_proxy(team_doc)
            if low_pace is not None and high_pace is not None:
                if pace_proxy < low_pace:
                    context["pace_bucket"] = "LOW"
                elif pace_proxy > high_pace:
                    context["pace_bucket"] = "HIGH"
                else:
                    context["pace_bucket"] = "MID"
            else:
                context["pace_bucket"] = None
        else:
            context["pace_bucket"] = None
        
        # GAME_COMPETITIVE (CLOSE vs BLOWOUT)
        if team_doc:
            team_pts = to_num(team_doc.get("PTS", 0))
            # Get opponent score
            teams = list(db.team_game_stats.find({"GAME_ID": game_id}))
            opp_pts = 0
            for t in teams:
                if t.get("TEAM_ID") != team_id:
                    opp_pts = to_num(t.get("PTS", 0))
                    break
            
            margin = abs(team_pts - opp_pts)
            # Close game: margin <= 10 points
            context["competitive"] = "CLOSE" if margin <= 10 else "BLOWOUT"
            context["score_margin"] = margin
        else:
            context["competitive"] = None
            context["score_margin"] = None
        
        # REST_BUCKET (skip if no date info available)
        # OPPONENT_STRENGTH_BUCKET (skip if not feasible)
        # These would require additional data we may not have
        
        # Update event with context
        db.events.update_one(
            {"_id": event["_id"]},
            {"$set": {"context": context}}
        )
        updated += 1
    
    print(f"Done. Updated {updated} events with context tags.")
    return updated


if __name__ == "__main__":
    add_context_tags_to_events()
