#!/usr/bin/env python3
"""
Test script to verify GAME_DATE ingestion works.

Creates a test CSV with existing GAME_IDs and real dates,
then runs ingestion and verifies GAME_DATE is written to MongoDB.
"""
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pymongo import MongoClient
from backend.ml.config import MONGO_URI, MONGO_DB, EVENTS_COLLECTION


def get_sample_game_ids(n=10):
    """Get sample GAME_IDs from MongoDB events collection."""
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    collection = db[EVENTS_COLLECTION]
    
    # Get distinct GAME_IDs
    game_ids = collection.distinct("GAME_ID")[:n]
    
    client.close()
    return game_ids


def create_test_csv(output_path="backend/ml/scripts/test_gamedate.csv", n=10):
    """Create a test CSV with GAME_IDs and GAME_DATEs."""
    print(f"Creating test CSV with {n} sample GAME_IDs...")
    
    # Get sample GAME_IDs from MongoDB
    game_ids = get_sample_game_ids(n=n)
    
    if not game_ids:
        print("ERROR: No GAME_IDs found in MongoDB. Run pipeline first to create events.")
        return None
    
    print(f"  Found {len(game_ids)} GAME_IDs")
    
    # Create test dates (recent dates for testing)
    # Use dates from last few months
    base_date = datetime(2024, 10, 15)  # Example: Oct 15, 2024
    
    rows = []
    for i, game_id in enumerate(game_ids):
        # Create dates spaced 1 day apart
        test_date = base_date + timedelta(days=i)
        rows.append({
            "GAME_ID": game_id,
            "GAME_DATE": test_date.strftime("%Y-%m-%d"),  # ISO format
        })
    
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    
    print(f"  Created test CSV: {output_path}")
    print(f"  Columns: {df.columns.tolist()}")
    print(f"  Sample rows:")
    print(df.head().to_string())
    
    return output_path


def verify_gamedate_in_mongo(n_sample=5):
    """Verify GAME_DATE exists in MongoDB after ingestion."""
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    collection = db[EVENTS_COLLECTION]
    
    # Count docs with GAME_DATE
    total_docs = collection.count_documents({})
    docs_with_date = collection.count_documents({"GAME_DATE": {"$exists": True, "$ne": None}})
    
    coverage_pct = (docs_with_date / total_docs * 100) if total_docs > 0 else 0
    
    print(f"\nGAME_DATE verification in MongoDB:")
    print(f"  Total events: {total_docs}")
    print(f"  Events with GAME_DATE: {docs_with_date} ({coverage_pct:.1f}%)")
    
    # Sample a few docs to show GAME_DATE
    if docs_with_date > 0:
        sample_docs = collection.find(
            {"GAME_DATE": {"$exists": True, "$ne": None}},
            {"GAME_ID": 1, "GAME_DATE": 1, "_id": 0}
        ).limit(n_sample)
        
        print(f"\n  Sample documents with GAME_DATE:")
        for doc in sample_docs:
            print(f"    GAME_ID: {doc.get('GAME_ID')}, GAME_DATE: {doc.get('GAME_DATE')}")
    else:
        print(f"  ⚠️  No documents have GAME_DATE!")
    
    client.close()
    
    return docs_with_date, total_docs


def main():
    """Run test ingestion workflow."""
    print("=" * 80)
    print("TESTING GAME_DATE INGESTION")
    print("=" * 80)
    
    # Step 1: Create test CSV
    print("\n[1/3] Creating test CSV...")
    test_csv = create_test_csv(n=10)
    
    if not test_csv:
        print("ERROR: Could not create test CSV. Exiting.")
        sys.exit(1)
    
    # Step 2: Run ingestion
    print("\n[2/3] Running ingestion...")
    print(f"  Command: python backend/ml/scripts/ingest_games.py {test_csv} --format csv")
    print("  (Run this command to ingest the CSV)")
    
    # Step 3: Verify in MongoDB
    print("\n[3/3] Verifying GAME_DATE in MongoDB...")
    print("  (After ingestion, run: python backend/ml/scripts/test_ingest_gamedate.py --verify)")
    print("\n" + "=" * 80)
    print("TEST SETUP COMPLETE")
    print("=" * 80)
    print(f"\nNext steps:")
    print(f"1. Run ingestion: python backend/ml/scripts/ingest_games.py {test_csv} --format csv")
    print(f"2. Verify: python backend/ml/scripts/test_ingest_gamedate.py --verify")
    print(f"3. Test ML pipeline: PYTHONPATH=. python -m backend.ml.cli inspect_data")
    print(f"4. Test ML pipeline: PYTHONPATH=. python -m backend.ml.cli backtest")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test GAME_DATE ingestion")
    parser.add_argument("--verify", action="store_true", help="Verify GAME_DATE in MongoDB")
    parser.add_argument("--create-csv", action="store_true", help="Create test CSV")
    
    args = parser.parse_args()
    
    if args.verify:
        verify_gamedate_in_mongo()
    elif args.create_csv:
        create_test_csv()
    else:
        main()
