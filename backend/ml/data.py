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
    ML_LIMIT,
    ML_QUERY_JSON,
    ML_SORT_FIELD,
    ML_SORT_DIR,
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

    # Task 2: Support query filter and sort options
    query_filter = {}
    if ML_QUERY_JSON:
        import json
        try:
            query_filter = json.loads(ML_QUERY_JSON)
            print(f"  Using query filter: {query_filter}")
        except json.JSONDecodeError as e:
            print(f"  WARNING: Invalid ML_QUERY_JSON, ignoring: {e}")
    
    # Build cursor with filter
    cursor = db[collection_name].find(query_filter, projection)
    
    # Task: Use GAME_DATE for sorting if available, otherwise fall back to GAME_ID
    # Check if GAME_DATE exists in collection
    sample_doc = db[collection_name].find_one(query_filter, {"GAME_DATE": 1})
    has_gamedate = sample_doc and "GAME_DATE" in sample_doc and sample_doc.get("GAME_DATE") is not None
    
    if has_gamedate:
        # Prefer GAME_DATE for sorting (time-ordered)
        # Override if explicitly set via env var
        if ML_SORT_FIELD and ML_SORT_FIELD != "GAME_ID":
            sort_field = ML_SORT_FIELD
        else:
            sort_field = "GAME_DATE"
    else:
        # Fall back to GAME_ID if no GAME_DATE
        sort_field = ML_SORT_FIELD if ML_SORT_FIELD else "GAME_ID"
    
    sort_dir = ML_SORT_DIR
    cursor = cursor.sort(sort_field, sort_dir)
    print(f"  Using sort: {sort_field} ({'ascending' if sort_dir == 1 else 'descending'})")
    
    # Apply limit if specified
    if ML_LIMIT:
        limit_val = int(ML_LIMIT)
        cursor = cursor.limit(limit_val)
        print(f"  Using limit: {limit_val}")
    
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

    # Task: Normalize GAME_ID to string with leading zeros before any date processing
    game_id_col = _find_field(df, FIELD_MAPPINGS["game_id"])
    if game_id_col:
        # Normalize GAME_ID to string, preserving leading zeros (zfill to 10 digits)
        df["game_id"] = df[game_id_col].astype(str).str.strip()
        # Pad numeric GAME_IDs to 10 digits (NBA format: "0022300010")
        df["game_id"] = df["game_id"].apply(lambda x: x.zfill(10) if x.isdigit() and len(x) < 10 else x)
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

    # Parse date field - Task 1: Prefer GAME_DATE over other date fields
    # A) Debug print: list date-like columns
    date_like_cols = [col for col in df.columns if "DATE" in col.upper() or "TIME" in col.upper()]
    if date_like_cols:
        print(f"  Date-like columns found: {date_like_cols}")
    
    # Task: Prefer GAME_DATE if present, but do NOT drop rows
    date_col = DATE_FIELD_OVERRIDE
    if date_col is None:
        # First try GAME_DATE (preferred field)
        if "GAME_DATE" in df.columns:
            date_col = "GAME_DATE"
        else:
            # Fall back to other date mappings
            date_col = _find_field(df, FIELD_MAPPINGS["date"])

    if date_col and date_col in df.columns:
        # Parse GAME_DATE (use NaT for missing values, do NOT drop rows)
        df["date"] = pd.to_datetime(df[date_col], errors="coerce")
        
        # Task: Add has_real_date boolean column
        df["has_real_date"] = df["date"].notna().astype(int)
        
        valid_dates = df["has_real_date"].sum()
        invalid_dates = len(df) - valid_dates
        total_rows = len(df)
        
        # Task: Update logging - print coverage and missing count, NO "dropping rows"
        coverage_pct = (valid_dates / total_rows * 100) if total_rows > 0 else 0
        print(f"  Using date column: {date_col}")
        print(f"  GAME_DATE coverage: {valid_dates}/{total_rows} ({coverage_pct:.1f}%)")
        if invalid_dates > 0:
            print(f"  Rows missing GAME_DATE: {invalid_dates} (kept with NaT for sorting)")
    else:
        # No real date column found - all rows have no real date
        print("  WARNING: No real date field found (GAME_DATE or other)")
        df["date"] = pd.NaT
        df["has_real_date"] = 0
        print(f"  All {len(df)} rows missing GAME_DATE (using GAME_ID-based sorting)")

    # Task: Ensure GAME_ID and TEAM_ID exist for sorting
    if "team_id" not in df.columns:
        if "TEAM_ID" in df.columns:
            df["team_id"] = df["TEAM_ID"].astype(str)
        else:
            df["team_id"] = "UNKNOWN"
            print("  WARNING: No TEAM_ID field found, using 'UNKNOWN' for sorting")

    # Task: Sort by GAME_DATE when coverage is high (>=95%), otherwise use has_real_date priority
    # Primary sort: GAME_DATE if coverage >= 95%, then GAME_ID for tie-breaking, then TEAM_ID
    sort_cols = []
    ascending = []
    
    # Check GAME_DATE coverage
    if "date" in df.columns and "has_real_date" in df.columns:
        coverage_pct = (df["has_real_date"].sum() / len(df) * 100) if len(df) > 0 else 0
        
        if coverage_pct >= 95.0:
            # High coverage: sort primarily by GAME_DATE
            sort_cols = ["date", "game_id", "team_id"]
            ascending = [True, True, True]  # All ascending
            print(f"  Using GAME_DATE-based sorting (coverage: {coverage_pct:.1f}%)")
        else:
            # Low coverage: sort by has_real_date priority, then GAME_DATE, then GAME_ID
            sort_cols = ["has_real_date", "date", "game_id", "team_id"]
            ascending = [False, True, True, True]  # has_real_date descending, others ascending
            print(f"  Using hybrid sorting (GAME_DATE coverage: {coverage_pct:.1f}%)")
    else:
        # Fallback: no date column, sort by GAME_ID
        sort_cols = ["game_id"]
        if "team_id" in df.columns:
            sort_cols.append("team_id")
        ascending = [True] * len(sort_cols)
        print(f"  Using GAME_ID-based sorting (no GAME_DATE column)")
    
    if sort_cols:
        # Filter out columns that don't exist
        sort_cols = [col for col in sort_cols if col in df.columns]
        ascending = ascending[:len(sort_cols)]
        df = df.sort_values(sort_cols, ascending=ascending, na_position="last").reset_index(drop=True)

    print(f"  Final DataFrame shape: {df.shape}")
    
    # Task: Print date range only if we have real dates
    if "has_real_date" in df.columns and df["has_real_date"].sum() > 0:
        # Only look at rows with real dates for date range
        real_dates = df[df["has_real_date"] == 1]["date"]
        if len(real_dates) > 0:
            min_date = real_dates.min()
            max_date = real_dates.max()
            print(f"  Date range (rows with GAME_DATE): {min_date} to {max_date}")
    elif "date" in df.columns and df["date"].notna().sum() == 0:
        print(f"  Date ordering: GAME_ID-based (no real dates available)")
    
    # Task 4: Verify monotonic non-decreasing order by date
    if "date" in df.columns:
        # Check monotonicity (allowing NaT at end due to na_position="last")
        non_null_dates = df["date"].dropna()
        if len(non_null_dates) > 1:
            is_monotonic = non_null_dates.is_monotonic_increasing
            if not is_monotonic:
                print(f"  ⚠️  WARNING: 'date' column is not monotonic non-decreasing after sorting")
                # Show first violation
                for i in range(len(non_null_dates) - 1):
                    if non_null_dates.iloc[i] > non_null_dates.iloc[i + 1]:
                        print(f"    Violation at index {non_null_dates.index[i]}: {non_null_dates.iloc[i]} > {non_null_dates.iloc[i + 1]}")
                        break
            else:
                print(f"  ✓ Date column is monotonic non-decreasing")

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
