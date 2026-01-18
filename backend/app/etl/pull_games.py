from app.db import db
from app.etl.nba_api import nba_get

def pull_games(season="2023-24", season_type="Regular Season"):
    data = nba_get(
        "leaguegamelog",
        {
            "Season": season,
            "SeasonType": season_type,
            "LeagueID": "00",
        },
    )

    rs = data["resultSets"][0]
    headers = rs["headers"]
    rows = rs["rowSet"]

    docs = [dict(zip(headers, row)) for row in rows]

    # keep it simple: one season+type at a time
    db.games.delete_many({"Season": season, "SeasonType": season_type})
    for d in docs:
        d["Season"] = season
        d["SeasonType"] = season_type

    if docs:
        db.games.insert_many(docs)

    print(f"Inserted {len(docs)} game rows for {season} ({season_type})")

if __name__ == "__main__":
    pull_games()
