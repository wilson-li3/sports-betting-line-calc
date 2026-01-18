"""
Backfill GAME_DATE field in MongoDB events collection.

This script:
- Iterates over all docs in nba_pairs.events
- If GAME_DATE already exists, skip
- Else tries to derive GAME_DATE from GAME_ID if possible
- Leaves missing if derivation isn't reliable
"""
import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pymongo import MongoClient
from datetime import datetime
from backend.ml.config import MONGO_URI, MONGO_DB, EVENTS_COLLECTION


def derive_date_from_game_id(game_id):
    """
    Attempt to derive date from GAME_ID.
    
    NBA GAME_ID format is typically: "0022300010" (season prefix + game number)
    - First 3 digits: season prefix (e.g., 002 for 2022-23 season)
    - Remaining: game number
    
    This is NOT reliable for exact date derivation without a lookup table.
    Returns None if derivation isn't reliable.
    """
    # For now, return None - we'd need a lookup table or API to get real dates
    # This is a placeholder for future implementation if a reliable mapping exists
    return None


def backfill_game_dates():
    """Backfill GAME_DATE for documents that don't have it."""
    print("Backfilling GAME_DATE field in MongoDB...")
    
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    collection = db[EVENTS_COLLECTION]
    
    # Count total docs
    total_docs = collection.count_documents({})
    print(f"Total documents in {MONGO_DB}.{EVENTS_COLLECTION}: {total_docs}")
    
    # Count docs with GAME_DATE
    has_date = collection.count_documents({"GAME_DATE": {"$exists": True, "$ne": None}})
    print(f"Documents with GAME_DATE: {has_date}")
    
    missing_date = total_docs - has_date
    print(f"Documents missing GAME_DATE: {missing_date}")
    
    if missing_date == 0:
        print("\nAll documents already have GAME_DATE. Nothing to backfill.")
        return
    
    # Find docs without GAME_DATE
    docs_without_date = collection.find({"GAME_DATE": {"$exists": False}})
    docs_without_date = list(docs_without_date)
    
    updated_count = 0
    skipped_count = 0
    
    print(f"\nProcessing {len(docs_without_date)} documents...")
    
    for doc in docs_without_date:
        game_id = doc.get("GAME_ID")
        if not game_id:
            skipped_count += 1
            continue
        
        # Try to derive date from GAME_ID
        derived_date = derive_date_from_game_id(game_id)
        
        if derived_date is not None:
            # Update document with derived date
            collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"GAME_DATE": derived_date}}
            )
            updated_count += 1
        else:
            # Can't reliably derive, skip
            skipped_count += 1
    
    print(f"\nBackfill complete:")
    print(f"  Updated: {updated_count} documents")
    print(f"  Skipped (no reliable derivation): {skipped_count} documents")
    print(f"  Remaining missing GAME_DATE: {skipped_count} documents")
    
    client.close()


if __name__ == "__main__":
    backfill_game_dates()
