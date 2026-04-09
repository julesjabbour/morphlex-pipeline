#!/usr/bin/env python3
"""
Backfill English morph_type from wiktextract_match data.
For rows where language=en AND morph_type=UNKNOWN AND wiktextract_match is non-empty,
parse the type= value and update morph_type.
"""

import pandas as pd
from datetime import datetime
import re

DATA_PATH = "/mnt/pgdata/morphlex/data/master_table.csv"

def parse_wiktextract_type(wikt_match):
    """Extract type= value from wiktextract_match field."""
    if not wikt_match or pd.isna(wikt_match):
        return None
    # Format: "type=ROOT" or "type=DERIVATION|from=comfortable"
    match = re.search(r'type=([A-Z]+)', str(wikt_match))
    if match:
        return match.group(1)
    return None

def main():
    print(f"=== BACKFILL ENGLISH MORPH_TYPE ===")
    print(f"Start: {datetime.now().isoformat()}")
    print()

    # Load data
    print(f"Loading {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)
    total_rows = len(df)
    print(f"Loaded {total_rows:,} rows")
    print()

    # Find English rows with UNKNOWN morph_type and non-empty wiktextract_match
    en_unknown_mask = (df['language'] == 'en') & (df['morph_type'] == 'UNKNOWN')
    en_unknown_count = en_unknown_mask.sum()

    has_wikt_mask = en_unknown_mask & df['wiktextract_match'].notna() & (df['wiktextract_match'] != '')
    candidates = df[has_wikt_mask].copy()
    print(f"English UNKNOWN rows: {en_unknown_count:,}")
    print(f"With wiktextract_match: {len(candidates):,}")
    print()

    # Parse and update
    updated_count = 0
    for idx in candidates.index:
        wikt_match = df.at[idx, 'wiktextract_match']
        new_type = parse_wiktextract_type(wikt_match)
        if new_type:
            df.at[idx, 'morph_type'] = new_type
            updated_count += 1

    print(f"=== RESULTS ===")
    print(f"Rows updated: {updated_count:,}")
    print()

    # Save
    print(f"Saving to {DATA_PATH}...")
    df.to_csv(DATA_PATH, index=False)
    print("Saved.")
    print()

    # New English morph_type distribution
    en_rows = df[df['language'] == 'en']
    print("=== NEW ENGLISH MORPH_TYPE DISTRIBUTION ===")
    en_dist = en_rows['morph_type'].value_counts()
    for mtype, count in en_dist.items():
        pct = 100.0 * count / len(en_rows)
        print(f"  {mtype}: {count:,} ({pct:.1f}%)")
    print()

    # New overall morph_type distribution
    print("=== NEW OVERALL MORPH_TYPE DISTRIBUTION ===")
    overall_dist = df['morph_type'].value_counts()
    for mtype, count in overall_dist.items():
        pct = 100.0 * count / total_rows
        print(f"  {mtype}: {count:,} ({pct:.1f}%)")
    print()

    print(f"End: {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()
