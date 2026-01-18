from app.db import db

COLLECTIONS = [
    "games",
    "player_game_stats",
    "team_game_stats",
    "roles_by_game",
    "pair_stats",
]

def init_db():
    existing = set(db.list_collection_names())
    for name in COLLECTIONS:
        if name not in existing:
            db.create_collection(name)
            print(f"Created collection: {name}")
        else:
            print(f"Collection exists: {name}")

if __name__ == "__main__":
    init_db()
