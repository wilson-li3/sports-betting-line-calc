"""
Data loading from MongoDB and DataFrame conversion.
"""
import pandas as pd
from pymongo import MongoClient

from .config import (
    EVENTS_COLLECTION,
    FIELD_MAPPINGS,
    DATE_FIELD_OVERRIDE,
    MONGO_URI,
    MONGO_DB,
)

# Cache the client/db so we don't reconnect each call
_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(MONGO_URI)
        _db = _client[MONGO_DB]
    return _db


def _find_field(df, candidates):
    """Find first matching field from candidates in df.columns."""
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None


def load_events_df(collection_name=None, projection=None):
    """
    Load all events from MongoDB and convert to pandas DataFrame.

    Args:
        collection_name: MongoDB collection name (defaults to config)
        projection: Optional projection dict to limit fields loaded

    Returns:
        DataFrame with events, sorted by date
    """
    if collection_name is None:
        collection_name = EVENTS_COLLECTION

    print(f"Loading events from {MONGO_DB}.{collection_name}...")

    db = _get_db()

    cursor = db[collection_name].find({}, projection)
    events = list(cursor)

    if not events:
        raise ValueError(f"No events found in {collection_name}")

    print(f"  Loaded {len(events)} event documents")

    df = pd.DataFrame(events)

    # Drop Mongo _id (not useful for modeling, can cause serialization issues)
    if "_id" in df.columns:
        df = df.drop(columns=["_id"], errors="ignore")

    # Flatten context field if present
    if "context" in df.columns:
        context_prefix = "ctx_"

        context_list = []
        for ctx in df["context"]:
            context_list.append(ctx if isinstance(ctx, dict) else {})

        context_df = pd.DataFrame(context_list)
        if not context_df.empty:
            context_df.columns = [context_prefix + col for col in context_df.columns]
            df = df.drop(columns=["context"], errors="ignore")
            df = pd.concat([df, context_df], axis=1)
        else:
            df = df.drop(columns=["context"], errors="ignore")

        # Map context.home to is_home (0/1)
        home_col = f"{context_prefix}home"
        if home_col in df.columns:
            # Support booleans or strings like "HOME"/"AWAY"
            if df[home_col].dtype == bool:
                df["is_home"] = df[home_col].astype(int)
            else:
                df["is_home"] = (df[home_col].astype(str).str.upper() == "HOME").astype(int)
            df = df.drop(columns=[home_col], errors="ignore")

        # Map context.pace_bucket to pace_bucket string
        pace_col = f"{context_prefix}pace_bucket"
        if pace_col in df.columns:
            df["pace_bucket"] = df[pace_col]
            df = df.drop(columns=[pace_col], errors="ignore")

        # Map context.competitive to is_competitive (0/1)
        comp_col = f"{context_prefix}competitive"
        if comp_col in df.columns:
            # Your old code assumed "CLOSE". Your summary says COMP_TRUE/COMP_FALSE.
            # Handle common cases:
            s = df[comp_col]
            if s.dtype == bool:
                df["is_competitive"] = s.astype(int)
            else:
                su = s.astype(str).str.upper()
                df["is_competitive"] = su.isin(["COMP_TRUE", "TRUE", "1", "YES", "CLOSE"]).astype(int)
            df = df.drop(columns=[comp_col], errors="ignore")

    # Ensure game_id exists
    game_id_col = _find_field(df, FIELD_MAPPINGS["game_id"])
    if game_id_col:
        df["game_id"] = df[game_id_col].astype(str)
    else:
        print("  WARNING: GAME_ID not found, creating synthetic IDs")
        df["game_id"] = df.index.astype(str)

    # Ensure team_id exists
    team_id_col = _find_field(df, FIELD_MAPPINGS["team_id"])
    if team_id_col:
        df["team_id"] = df[team_id_col].astype(str)
    else:
        team_abbrev_col = _find_field(df, FIELD_MAPPINGS["team_abbreviation"])
        if team_abbrev_col:
            df["team_id"] = df[team_abbrev_col].fillna("UNKNOWN_TEAM").astype(str)
        else:
            print("  WARNING: TEAM_ID not found, using UNKNOWN_TEAM")
            df["team_id"] = "UNKNOWN_TEAM"

    # Parse date field - Task 1: Fix date handling
    # A) Debug print: list date-like columns
    date_like_cols = [col for col in df.columns if "DATE" in col.upper() or "TIME" in col.upper()]
    if date_like_cols:
        print(f"  Date-like columns found: {date_like_cols}")
    
    date_col = DATE_FIELD_OVERRIDE
    if date_col is None:
        date_col = _find_field(df, FIELD_MAPPINGS["date"])

    if date_col and date_col in df.columns:
        # B) Real date column exists - parse it
        df["date"] = pd.to_datetime(df[date_col], errors="coerce")
        invalid_dates = df["date"].isna().sum()
        if invalid_dates > 0:
            print(f"  WARNING: {invalid_dates} rows with invalid dates dropped")
            df = df.dropna(subset=["date"])
        print(f"  Using date column: {date_col}")
    else:
        # C) No real date column - use GAME_ID as deterministic fallback for sorting
        print("  WARNING: No real date field found, using GAME_ID for deterministic sorting")
        if "game_id" in df.columns:
            # Create a deterministic date from GAME_ID for sorting
            # Convert GAME_ID to string, hash it, and use as days offset for deterministic ordering
            game_ids_str = df["game_id"].astype(str)
            # Use a simple hash-like approach: sum of character codes mod reasonable number
            # This gives deterministic ordering based on GAME_ID without requiring dates
            df["_sort_key"] = game_ids_str.apply(lambda x: sum(ord(c) for c in x) % 100000)
            df["date"] = pd.to_datetime("1970-01-01") + pd.to_timedelta(df["_sort_key"], unit="D")
            df = df.drop(columns=["_sort_key"])
        else:
            # Last resort: use index
            df["date"] = pd.to_datetime("1970-01-01") + pd.to_timedelta(df.index, unit="D")
        print("  Using deterministic sorting by GAME_ID (no real dates available)")

    # Sort by date ascending (important for leakage-safe features)
    df = df.sort_values("date").reset_index(drop=True)

    print(f"  Final DataFrame shape: {df.shape}")
    print(f"  Date range: {df['date'].min()} to {df['date'].max()}")

    return df


def get_base_features(df):
    """
    Get base feature column names from DataFrame.
    Returns list of column names that are safe to use as features.
    """
    exclude = [
        "GAME_ID", "TEAM_ID", "TEAM_ABBREVIATION", "game_id", "team_id",
        "date", "ctx_", "context",
        "PRIMARY_SCORER_NAME", "PRIMARY_FACILITATOR_NAME", "PRIMARY_REBOUNDER_NAME",
        "PRIMARY_SCORER_PLAYER_ID", "PRIMARY_FACILITATOR_PLAYER_ID", "PRIMARY_REBOUNDER_PLAYER_ID",
    ]

    exclude_patterns = [
        "_OVER_HIT", "_MARGIN", "_ACTUAL", "_STRONG_HIT"
    ]

    feature_cols = []
    for col in df.columns:
        if any(ex in col for ex in exclude):
            continue
        if any(pattern in col for pattern in exclude_patterns):
            continue

        if col not in ["is_home", "pace_bucket", "is_competitive"]:
            if df[col].dtype not in ["int64", "float64", "int32", "float32"]:
                continue

        feature_cols.append(col)

    return feature_cols
