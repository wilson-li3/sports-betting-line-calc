from app.db import db

def visualize_pairs():
    pairs = list(db.pair_stats.find())
    if not pairs:
        print("No pair_stats found.")
        return

    # sort by lift descending
    pairs = sorted(pairs, key=lambda x: x["lift"], reverse=True)

    print("\n=== MIXED PAIR RELATIONSHIPS ===\n")
    print(f"{'PAIR':55} {'n':>3} {'lift':>6} {'phi':>6}  INTERPRETATION")
    print("-" * 95)

    for p in pairs:
        lift = p["lift"]
        phi = p["phi"]

        if lift > 1.15 and phi > 0.2:
            tag = "STRONG STACK"
        elif lift > 1.0 and phi > 0:
            tag = "WEAK STACK"
        elif lift < 0.95 and phi < 0:
            tag = "HEDGE"
        else:
            tag = "NEUTRAL"

        print(
            f"{p['pair'][:55]:55} "
            f"{p['n']:>3} "
            f"{lift:>6.2f} "
            f"{phi:>6.2f}  "
            f"{tag}"
        )

if __name__ == "__main__":
    visualize_pairs()
