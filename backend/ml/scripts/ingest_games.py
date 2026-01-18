"""
Ingest games from CSV or JSONL into MongoDB events collection.

This script:
- Accepts a CSV or JSONL path of games including GAME_ID and GAME_DATE
- Writes/updates docs into nba_pairs.events
- Ensures GAME_ID stored as string
- Ensures GAME_DATE stored
"""
import sys
import argparse
import json
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
from pymongo import MongoClient
from datetime import datetime

from backend.ml.config import MONGO_URI, MONGO_DB, EVENTS_COLLECTION


def parse_date(date_str):
    """Parse date string to datetime object (MongoDB-compatible)."""
    if pd.isna(date_str) or date_str is None:
        return None
    try:
        # Convert to pandas datetime first, then to Python datetime
        dt = pd.to_datetime(date_str)
        # Convert to Python datetime.datetime (MongoDB compatible)
        if isinstance(dt, pd.Timestamp):
            return dt.to_pydatetime()
        return dt
    except Exception as e:
        print(f"  WARNING: Could not parse date '{date_str}': {e}")
        return None


def ingest_csv(csv_path, update_existing=True):
    """
    Ingest games from CSV.
    
    Args:
        csv_path: Path to CSV file
        update_existing: If True, update existing docs; if False, skip duplicates
    """
    print(f"Ingesting from CSV: {csv_path}")
    
    df = pd.read_csv(csv_path)
    print(f"  Loaded {len(df)} rows")
    
    # Required fields
    required_fields = ["GAME_ID"]
    for field in required_fields:
        if field not in df.columns:
            raise ValueError(f"Required field {field} not found in CSV")
    
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    collection = db[EVENTS_COLLECTION]
    
    inserted_count = 0
    updated_count = 0
    skipped_count = 0
    
    for _, row in df.iterrows():
        game_id_raw = row["GAME_ID"]
        
        # Task: Normalize GAME_ID to string, preserving leading zeros
        # If numeric, pad to 10 digits with leading zeros (NBA format: "0022300010")
        if pd.isna(game_id_raw):
            print(f"  WARNING: Skipping row with missing GAME_ID")
            continue
        
        # Convert to string first
        game_id_str = str(game_id_raw).strip()
        
        # If it's a numeric string without leading zeros, pad it
        # NBA GAME_IDs are typically 10 digits: "0022300010"
        if game_id_str.isdigit() and len(game_id_str) < 10:
            game_id = game_id_str.zfill(10)
        else:
            game_id = game_id_str
        
        doc = row.to_dict()
        
        # Ensure GAME_ID is normalized string
        doc["GAME_ID"] = game_id
        
        # Parse GAME_DATE if present (check both dict and original row)
        if "GAME_DATE" in doc or "GAME_DATE" in row.index:
            date_raw = doc.get("GAME_DATE") or row.get("GAME_DATE")
            parsed_date = parse_date(date_raw)
            if parsed_date is not None:
                doc["GAME_DATE"] = parsed_date
            elif "GAME_DATE" in doc:
                # Keep original if parsing fails (for debugging)
                pass
        
        # Check if document exists - use normalized GAME_ID for query
        # MongoDB query: match GAME_ID as string (normalize both sides for safety)
        existing = collection.find_one({"GAME_ID": game_id})
        
        if existing:
            if update_existing:
                collection.update_one(
                    {"GAME_ID": game_id},
                    {"$set": doc}
                )
                updated_count += 1
            else:
                skipped_count += 1
        else:
            collection.insert_one(doc)
            inserted_count += 1
    
    print(f"\nIngestion complete:")
    print(f"  Inserted: {inserted_count} documents")
    print(f"  Updated: {updated_count} documents")
    print(f"  Skipped: {skipped_count} documents")
    
    client.close()


def ingest_jsonl(jsonl_path, update_existing=True):
    """
    Ingest games from JSONL.
    
    Args:
        jsonl_path: Path to JSONL file
        update_existing: If True, update existing docs; if False, skip duplicates
    """
    print(f"Ingesting from JSONL: {jsonl_path}")
    
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    collection = db[EVENTS_COLLECTION]
    
    inserted_count = 0
    updated_count = 0
    skipped_count = 0
    
    with open(jsonl_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"  WARNING: Skipping line {line_num}: {e}")
                continue
            
            if "GAME_ID" not in doc:
                print(f"  WARNING: Skipping line {line_num}: missing GAME_ID")
                continue
            
            # Task: Normalize GAME_ID to string, preserving leading zeros
            game_id_raw = doc["GAME_ID"]
            game_id_str = str(game_id_raw).strip()
            
            # If it's a numeric string without leading zeros, pad it
            if game_id_str.isdigit() and len(game_id_str) < 10:
                game_id = game_id_str.zfill(10)
            else:
                game_id = game_id_str
            
            doc["GAME_ID"] = game_id
            
            # Parse GAME_DATE if present
            if "GAME_DATE" in doc:
                doc["GAME_DATE"] = parse_date(doc["GAME_DATE"])
            
            # Check if document exists
            existing = collection.find_one({"GAME_ID": game_id})
            
            if existing:
                if update_existing:
                    collection.update_one(
                        {"GAME_ID": game_id},
                        {"$set": doc}
                    )
                    updated_count += 1
                else:
                    skipped_count += 1
            else:
                collection.insert_one(doc)
                inserted_count += 1
    
    print(f"\nIngestion complete:")
    print(f"  Inserted: {inserted_count} documents")
    print(f"  Updated: {updated_count} documents")
    print(f"  Skipped: {skipped_count} documents")
    
    client.close()


def main():
    parser = argparse.ArgumentParser(description="Ingest games into MongoDB")
    parser.add_argument("input_path", help="Path to CSV or JSONL file")
    parser.add_argument("--format", choices=["csv", "jsonl"], help="Input format (auto-detected if not specified)")
    parser.add_argument("--skip-existing", action="store_true", help="Skip documents that already exist")
    
    args = parser.parse_args()
    
    input_path = Path(args.input_path)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)
    
    # Auto-detect format if not specified
    if args.format:
        file_format = args.format
    else:
        if input_path.suffix.lower() == ".csv":
            file_format = "csv"
        elif input_path.suffix.lower() == ".jsonl":
            file_format = "jsonl"
        else:
            print("Error: Could not detect file format. Use --format csv or --format jsonl")
            sys.exit(1)
    
    update_existing = not args.skip_existing
    
    if file_format == "csv":
        ingest_csv(input_path, update_existing=update_existing)
    else:
        ingest_jsonl(input_path, update_existing=update_existing)


if __name__ == "__main__":
    main()
