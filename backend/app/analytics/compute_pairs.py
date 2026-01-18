from app.db import db
import math

PAIR_FIELDS = [
    ("TEAM_TOTAL_OVER_HIT", "PRIMARY_SCORER_PTS_OVER_HIT"),
    ("TEAM_TOTAL_OVER_HIT", "PRIMARY_FACILITATOR_AST_OVER_HIT"),
    ("TEAM_TOTAL_OVER_HIT", "PRIMARY_REBOUNDER_REB_OVER_HIT"),
    ("GAME_TOTAL_OVER_HIT", "PRIMARY_SCORER_PTS_OVER_HIT"),
    ("GAME_TOTAL_OVER_HIT", "PRIMARY_FACILITATOR_AST_OVER_HIT"),
]

def phi_correlation(a, b, c, d):
    # a = both hit
    # b = A hit, B miss
    # c = A miss, B hit
    # d = both miss
    num = (a * d) - (b * c)
    den = math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    return num / den if den != 0 else 0.0

def compute_pairs():
    events = list(db.events.find())
    if not events:
        print("No events found.")
        return

    db.pair_stats.delete_many({})

    for A, B in PAIR_FIELDS:
        a = b = c = d = 0

        for e in events:
            av = e.get(A)
            bv = e.get(B)
            if av is None or bv is None:
                continue

            if av == 1 and bv == 1:
                a += 1
            elif av == 1 and bv == 0:
                b += 1
            elif av == 0 and bv == 1:
                c += 1
            elif av == 0 and bv == 0:
                d += 1

        n = a + b + c + d
        if n < 5:
            continue

        pA = (a + b) / n
        pB = (a + c) / n
        pAB = a / n
        lift = pAB / (pA * pB) if pA * pB > 0 else 0
        phi = phi_correlation(a, b, c, d)

        db.pair_stats.insert_one({
            "pair": f"{A} ↔ {B}",
            "A": A,
            "B": B,
            "n": n,
            "pA": pA,
            "pB": pB,
            "pAB": pAB,
            "lift": lift,
            "phi": phi,
        })

        print(f"Computed pair {A} ↔ {B} (n={n}, lift={lift:.2f}, phi={phi:.2f})")

if __name__ == "__main__":
    compute_pairs()
