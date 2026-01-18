"""
Inspect data: print data summary without running full pipeline.
"""
import pandas as pd
from .data import load_events_df


def cmd_inspect_data(args):
    """Inspect loaded data without running pipeline."""
    print("Inspecting data from MongoDB...")
    
    # Load data
    df = load_events_df()
    
    print("\n" + "=" * 80)
    print("DATA INSPECTION")
    print("=" * 80)
    
    print(f"\nTotal docs loaded: {len(df)}")
    print(f"Total columns: {len(df.columns)}")
    
    # Find columns containing SEASON/YEAR/DATE/TIME (case-insensitive)
    date_season_keywords = ['SEASON', 'YEAR', 'DATE', 'TIME']
    date_season_cols = []
    for col in df.columns:
        col_upper = col.upper()
        if any(kw in col_upper for kw in date_season_keywords):
            date_season_cols.append(col)
    
    if date_season_cols:
        print(f"\nColumns containing SEASON/YEAR/DATE/TIME: {date_season_cols}")
    else:
        print("\nNo columns containing SEASON/YEAR/DATE/TIME found")
    
    # Task 4: Check GAME_DATE coverage and range
    if 'GAME_DATE' in df.columns:
        game_dates = df['GAME_DATE'].dropna()
        if len(game_dates) > 0:
            try:
                dates_parsed = pd.to_datetime(game_dates, errors='coerce')
                valid_dates = dates_parsed.notna().sum()
                coverage_pct = (valid_dates / len(df) * 100) if len(df) > 0 else 0
                
                print(f"\nGAME_DATE field:")
                print(f"  Coverage: {valid_dates}/{len(df)} ({coverage_pct:.1f}%)")
                if valid_dates > 0:
                    min_date = dates_parsed.min()
                    max_date = dates_parsed.max()
                    print(f"  Min date: {min_date}")
                    print(f"  Max date: {max_date}")
            except Exception as e:
                print(f"\nGAME_DATE field found but error parsing: {e}")
        else:
            print(f"\nGAME_DATE field: all NaN")
    else:
        print(f"\nNo GAME_DATE field found")
    
    # Check for season field
    season_col = None
    for col in df.columns:
        if 'SEASON' in col.upper():
            season_col = col
            break
    
    if season_col:
        seasons = sorted(df[season_col].dropna().unique())
        print(f"\nDistinct values for {season_col} (showing top 10):")
        for s in seasons[:10]:
            count = (df[season_col] == s).sum()
            print(f"  {s}: {count} docs")
        if len(seasons) > 10:
            print(f"  ... ({len(seasons) - 10} more)")
        print(f"Total distinct seasons: {len(seasons)}")
    else:
        print("\nNo SEASON field found")
    
    # Check GAME_ID range
    game_id_col = None
    for col in df.columns:
        if 'GAME_ID' in col.upper():
            game_id_col = col
            break
    
    if game_id_col:
        game_ids = df[game_id_col].dropna()
        if len(game_ids) > 0:
            print(f"\n{game_id_col} range:")
            try:
                # Try to convert to numeric for min/max
                numeric_ids = pd.to_numeric(game_ids, errors='coerce')
                valid_ids = numeric_ids.dropna()
                if len(valid_ids) > 0:
                    print(f"  Min: {int(valid_ids.min())}")
                    print(f"  Max: {int(valid_ids.max())}")
                else:
                    print(f"  (non-numeric values)")
            except Exception as e:
                print(f"  (error computing range: {e})")
            print(f"  Unique values: {game_ids.nunique()}")
        else:
            print(f"\n{game_id_col}: all NaN")
    else:
        print("\nNo GAME_ID field found")
    
    # Show example docs
    print(f"\nExample docs (first 3):")
    for idx in range(min(3, len(df))):
        print(f"\n  Doc {idx + 1}:")
        if game_id_col:
            print(f"    {game_id_col}: {df.iloc[idx][game_id_col]}")
        for col in date_season_cols[:3]:  # Show first 3 date-like columns
            val = df.iloc[idx][col]
            print(f"    {col}: {val}")
    
    # Sample columns
    print(f"\nSample columns (first 20):")
    for col in df.columns[:20]:
        dtype = df[col].dtype
        non_null = df[col].notna().sum()
        print(f"  {col:<30} {str(dtype):<15} non-null: {non_null}/{len(df)}")
    
    if len(df.columns) > 20:
        print(f"  ... ({len(df.columns) - 20} more columns)")
    
    print("=" * 80)
    print("\nDone!")
