#!/usr/bin/env python3
"""
Data Quality Check for master_table.csv
Read-only diagnostic - prints statistics without modifying any files.
"""

import pandas as pd
import random
from datetime import datetime
from collections import defaultdict

def main():
    print("=" * 70)
    print("DATA QUALITY CHECK: master_table.csv")
    print("=" * 70)
    print(f"Start: {datetime.now().isoformat()}")
    print()

    # Load the CSV
    csv_path = "/mnt/pgdata/morphlex/data/master_table.csv"
    print(f"Loading {csv_path}...")
    df = pd.read_csv(csv_path)
    total_rows = len(df)
    print(f"Loaded {total_rows:,} rows")
    print()

    # =========================================================================
    # 1. MORPH_TYPE DISTRIBUTION
    # =========================================================================
    print("=" * 70)
    print("1. MORPH_TYPE DISTRIBUTION (all rows)")
    print("=" * 70)
    morph_counts = df['morph_type'].value_counts()
    print(f"{'morph_type':<15} {'count':>12} {'percentage':>12}")
    print("-" * 40)
    for mtype, count in morph_counts.items():
        pct = 100.0 * count / total_rows
        print(f"{str(mtype):<15} {count:>12,} {pct:>11.2f}%")
    print(f"{'TOTAL':<15} {total_rows:>12,} {'100.00%':>12}")
    print()

    # =========================================================================
    # 2. PER-LANGUAGE MORPH_TYPE
    # =========================================================================
    print("=" * 70)
    print("2. PER-LANGUAGE MORPH_TYPE DISTRIBUTION")
    print("=" * 70)

    morph_types = ['ROOT', 'DERIVATION', 'COMPOUND', 'UNKNOWN']
    # Check for OTHER or any other values
    all_types = df['morph_type'].unique()
    other_types = [t for t in all_types if t not in morph_types]
    if other_types:
        morph_types.append('OTHER')

    print(f"{'language':<12} {'ROOT':>10} {'DERIVATION':>12} {'COMPOUND':>10} {'UNKNOWN':>10} {'OTHER':>8} {'TOTAL':>10}")
    print("-" * 75)

    for lang in sorted(df['language'].unique()):
        lang_df = df[df['language'] == lang]
        lang_total = len(lang_df)

        root_count = len(lang_df[lang_df['morph_type'] == 'ROOT'])
        deriv_count = len(lang_df[lang_df['morph_type'] == 'DERIVATION'])
        comp_count = len(lang_df[lang_df['morph_type'] == 'COMPOUND'])
        unk_count = len(lang_df[lang_df['morph_type'] == 'UNKNOWN'])
        other_count = lang_total - root_count - deriv_count - comp_count - unk_count

        print(f"{lang:<12} {root_count:>10,} {deriv_count:>12,} {comp_count:>10,} {unk_count:>10,} {other_count:>8,} {lang_total:>10,}")

    print("-" * 75)
    # Totals row
    root_total = len(df[df['morph_type'] == 'ROOT'])
    deriv_total = len(df[df['morph_type'] == 'DERIVATION'])
    comp_total = len(df[df['morph_type'] == 'COMPOUND'])
    unk_total = len(df[df['morph_type'] == 'UNKNOWN'])
    other_total = total_rows - root_total - deriv_total - comp_total - unk_total
    print(f"{'TOTAL':<12} {root_total:>10,} {deriv_total:>12,} {comp_total:>10,} {unk_total:>10,} {other_total:>8,} {total_rows:>10,}")
    print()

    # =========================================================================
    # 3. ROOT COLUMN ANALYSIS
    # =========================================================================
    print("=" * 70)
    print("3. ROOT COLUMN (non-empty vs empty)")
    print("=" * 70)

    # Check for non-empty root values
    df['root_filled'] = df['root'].notna() & (df['root'].astype(str).str.strip() != '')

    print(f"{'language':<12} {'non-empty':>12} {'empty':>12} {'total':>12} {'fill_rate':>12}")
    print("-" * 55)

    for lang in sorted(df['language'].unique()):
        lang_df = df[df['language'] == lang]
        filled = lang_df['root_filled'].sum()
        empty = len(lang_df) - filled
        fill_rate = 100.0 * filled / len(lang_df) if len(lang_df) > 0 else 0
        print(f"{lang:<12} {filled:>12,} {empty:>12,} {len(lang_df):>12,} {fill_rate:>11.1f}%")

    print("-" * 55)
    total_filled = df['root_filled'].sum()
    total_empty = total_rows - total_filled
    total_rate = 100.0 * total_filled / total_rows
    print(f"{'TOTAL':<12} {total_filled:>12,} {total_empty:>12,} {total_rows:>12,} {total_rate:>11.1f}%")
    print()

    # =========================================================================
    # 4. WIKTEXTRACT MATCH
    # =========================================================================
    print("=" * 70)
    print("4. WIKTEXTRACT_MATCH (non-empty per language)")
    print("=" * 70)

    df['wikt_filled'] = df['wiktextract_match'].notna() & (df['wiktextract_match'].astype(str).str.strip() != '')

    print(f"{'language':<12} {'has_match':>12} {'no_match':>12} {'total':>12} {'match_rate':>12}")
    print("-" * 55)

    for lang in sorted(df['language'].unique()):
        lang_df = df[df['language'] == lang]
        has_match = lang_df['wikt_filled'].sum()
        no_match = len(lang_df) - has_match
        match_rate = 100.0 * has_match / len(lang_df) if len(lang_df) > 0 else 0
        print(f"{lang:<12} {has_match:>12,} {no_match:>12,} {len(lang_df):>12,} {match_rate:>11.1f}%")

    print("-" * 55)
    total_match = df['wikt_filled'].sum()
    total_no = total_rows - total_match
    total_rate = 100.0 * total_match / total_rows
    print(f"{'TOTAL':<12} {total_match:>12,} {total_no:>12,} {total_rows:>12,} {total_rate:>11.1f}%")
    print()

    # =========================================================================
    # 5. SAMPLE ROWS (3 per morph_type)
    # =========================================================================
    print("=" * 70)
    print("5. SAMPLE ROWS (3 per morph_type, 12 total)")
    print("=" * 70)

    random.seed(42)  # Reproducible samples

    sample_types = ['ROOT', 'DERIVATION', 'COMPOUND', 'UNKNOWN']
    sample_num = 0

    for mtype in sample_types:
        mtype_df = df[df['morph_type'] == mtype]
        if len(mtype_df) == 0:
            print(f"\n[{mtype}] No rows found")
            continue

        sample_indices = random.sample(range(len(mtype_df)), min(3, len(mtype_df)))
        print(f"\n--- {mtype} ({len(mtype_df):,} total rows) ---")

        for idx in sample_indices:
            sample_num += 1
            row = mtype_df.iloc[idx]
            print(f"\n[{sample_num}] synset_id: {row['synset_id']}")
            print(f"    language: {row['language']}, word: '{row['word']}'")
            print(f"    root: '{row['root']}', morph_type: {row['morph_type']}")
            wikt = row['wiktextract_match'] if pd.notna(row['wiktextract_match']) else '(empty)'
            print(f"    wiktextract_match: {wikt}")

    print()

    # =========================================================================
    # 6. POS DISTRIBUTION
    # =========================================================================
    print("=" * 70)
    print("6. POS DISTRIBUTION")
    print("=" * 70)

    pos_counts = df['pos'].value_counts()
    print(f"{'POS':<10} {'count':>12} {'percentage':>12}")
    print("-" * 35)
    for pos, count in pos_counts.items():
        pct = 100.0 * count / total_rows
        print(f"{str(pos):<10} {count:>12,} {pct:>11.2f}%")
    print(f"{'TOTAL':<10} {total_rows:>12,} {'100.00%':>12}")
    print()

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("=" * 70)
    print("DATA QUALITY CHECK COMPLETE")
    print("=" * 70)
    print(f"End: {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()
