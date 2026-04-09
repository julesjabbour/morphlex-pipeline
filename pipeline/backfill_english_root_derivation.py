#!/usr/bin/env python3
"""
Backfill English root and derivation_info from wiktextract_match data.
For rows where language=en AND wiktextract_match is non-empty:
- If "from=X" is present, set derivation_info=X and root=X
- If compound data is present, set compound_components
Does NOT change morph_type.
"""

import pandas as pd
from datetime import datetime
import re

DATA_PATH = "/mnt/pgdata/morphlex/data/master_table.csv"

def parse_from_value(wikt_match):
    """Extract from= value from wiktextract_match field."""
    if not wikt_match or pd.isna(wikt_match):
        return None
    match = re.search(r'from=([^|]+)', str(wikt_match))
    if match:
        return match.group(1).strip()
    return None

def parse_compound_value(wikt_match):
    """Extract compound= or component data from wiktextract_match field."""
    if not wikt_match or pd.isna(wikt_match):
        return None
    # Look for compound= or components= pattern
    match = re.search(r'(?:compound|components?)=([^|]+)', str(wikt_match))
    if match:
        return match.group(1).strip()
    return None

def main():
    print(f"=== BACKFILL ENGLISH ROOT AND DERIVATION ===")
    print(f"Git HEAD: ", end="")
    import subprocess
    print(subprocess.getoutput("git rev-parse HEAD"))
    print(f"Start: {datetime.now().isoformat()}")
    print()

    # Load data
    print(f"Loading {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)
    total_rows = len(df)
    print(f"Loaded {total_rows:,} rows")
    print()

    # Find English rows with non-empty wiktextract_match
    en_mask = df['language'] == 'en'
    en_count = en_mask.sum()

    has_wikt_mask = en_mask & df['wiktextract_match'].notna() & (df['wiktextract_match'] != '')
    candidates = df[has_wikt_mask].copy()
    print(f"English rows: {en_count:,}")
    print(f"With wiktextract_match: {len(candidates):,}")
    print()

    # Ensure columns exist
    if 'derivation_info' not in df.columns:
        df['derivation_info'] = ''
    if 'compound_components' not in df.columns:
        df['compound_components'] = ''

    # Collect samples before/after
    samples = []

    # Update derivation_info and root
    derivation_updated = 0
    compound_updated = 0
    root_updated = 0

    for idx in candidates.index:
        wikt_match = df.at[idx, 'wiktextract_match']
        old_root = df.at[idx, 'root']
        old_deriv = df.at[idx, 'derivation_info'] if pd.notna(df.at[idx, 'derivation_info']) else ''
        old_compound = df.at[idx, 'compound_components'] if pd.notna(df.at[idx, 'compound_components']) else ''
        word = df.at[idx, 'word']

        from_val = parse_from_value(wikt_match)
        compound_val = parse_compound_value(wikt_match)

        new_root = old_root
        new_deriv = old_deriv
        new_compound = old_compound
        changed = False

        if from_val:
            df.at[idx, 'derivation_info'] = from_val
            new_deriv = from_val
            derivation_updated += 1
            # Also update root to from_val (replacing word itself as root)
            df.at[idx, 'root'] = from_val
            new_root = from_val
            root_updated += 1
            changed = True

        if compound_val:
            df.at[idx, 'compound_components'] = compound_val
            new_compound = compound_val
            compound_updated += 1
            changed = True

        # Collect sample if changed and we need more
        if changed and len(samples) < 5:
            samples.append({
                'word': word,
                'wiktextract_match': wikt_match,
                'old_root': old_root,
                'new_root': new_root,
                'old_derivation_info': old_deriv,
                'new_derivation_info': new_deriv,
                'old_compound_components': old_compound,
                'new_compound_components': new_compound
            })

    print(f"=== RESULTS ===")
    print(f"Rows with derivation_info updated: {derivation_updated:,}")
    print(f"Rows with compound_components updated: {compound_updated:,}")
    print(f"Rows with root updated: {root_updated:,}")
    print()

    # Save
    print(f"Saving to {DATA_PATH}...")
    df.to_csv(DATA_PATH, index=False)
    print("Saved.")
    print()

    # Print samples
    print("=== 5 SAMPLE BEFORE/AFTER ROWS ===")
    for i, s in enumerate(samples, 1):
        print(f"[{i}] word: '{s['word']}'")
        print(f"    wiktextract: {s['wiktextract_match']}")
        print(f"    root: '{s['old_root']}' -> '{s['new_root']}'")
        print(f"    derivation_info: '{s['old_derivation_info']}' -> '{s['new_derivation_info']}'")
        print(f"    compound_components: '{s['old_compound_components']}' -> '{s['new_compound_components']}'")
    print()

    print(f"End: {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()
