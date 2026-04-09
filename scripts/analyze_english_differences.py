#!/usr/bin/env python3
"""Deep analysis of DIFFERENT rows in english_comparison.csv."""

import csv
import random
from collections import Counter
from datetime import datetime

def main():
    print("=== DEEP ANALYSIS OF DIFFERENT ROWS ===")
    print(f"Start: {datetime.now().isoformat()}")
    print()

    input_file = '/mnt/pgdata/morphlex/data/english_comparison.csv'

    # Load all DIFFERENT rows
    different_rows = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('agreement') == 'DIFFERENT':
                different_rows.append(row)

    print(f"Total DIFFERENT rows: {len(different_rows):,}")
    print()

    # ============================================================
    # ANALYSIS 1: DISAGREEMENT PATTERNS
    # ============================================================
    print("=" * 60)
    print("ANALYSIS 1: DISAGREEMENT PATTERNS")
    print("=" * 60)
    print()

    pattern_counts = Counter()
    pattern_rows = {}  # Store rows per pattern for sampling

    for row in different_rows:
        m_type = row['morpholex_type'] or 'EMPTY'
        w_type = row['wiktextract_type'] or 'EMPTY'
        pattern = f"MorphoLex={m_type}, Wiktextract={w_type}"
        pattern_counts[pattern] += 1

        if pattern not in pattern_rows:
            pattern_rows[pattern] = []
        pattern_rows[pattern].append(row)

    total = len(different_rows)
    print(f"{'Pattern':<55} {'Count':>8} {'Pct':>8}")
    print("-" * 73)

    sorted_patterns = sorted(pattern_counts.items(), key=lambda x: -x[1])
    for pattern, count in sorted_patterns:
        pct = (count / total * 100) if total > 0 else 0
        print(f"{pattern:<55} {count:>8,} {pct:>7.1f}%")

    print("-" * 73)
    print(f"{'TOTAL':<55} {total:>8,} {100.0:>7.1f}%")
    print()

    # ============================================================
    # ANALYSIS 2: 10 RANDOM SAMPLES PER PATTERN (100+ rows)
    # ============================================================
    print("=" * 60)
    print("ANALYSIS 2: 10 RANDOM SAMPLES PER PATTERN (100+ rows)")
    print("=" * 60)
    print()

    random.seed(42)  # Reproducible samples

    for pattern, count in sorted_patterns:
        if count < 100:
            continue

        print(f"--- {pattern} ({count:,} rows) ---")
        print()

        samples = random.sample(pattern_rows[pattern], min(10, count))

        print(f"{'Word':<25} {'MorphoLex type (root)':<30} {'Wiktextract type (root)':<30}")
        print("-" * 85)

        for row in samples:
            word = row['word'][:24]
            m_info = f"{row['morpholex_type']} ({row['morpholex_root'][:15]})" if row['morpholex_root'] else row['morpholex_type']
            w_info = f"{row['wiktextract_type']} ({row['wiktextract_root'][:15]})" if row['wiktextract_root'] else row['wiktextract_type']
            print(f"{word:<25} {m_info:<30} {w_info:<30}")

        print()

    # ============================================================
    # ANALYSIS 3: ROOT AGREEMENT
    # ============================================================
    print("=" * 60)
    print("ANALYSIS 3: ROOT AGREEMENT (when type differs)")
    print("=" * 60)
    print()

    # Count rows where both have non-empty roots
    both_have_root = []
    for row in different_rows:
        m_root = row['morpholex_root'].strip()
        w_root = row['wiktextract_root'].strip()
        if m_root and w_root:
            both_have_root.append(row)

    print(f"DIFFERENT rows where both sources provide a root: {len(both_have_root):,}")
    print()

    # Compare roots
    same_root = 0
    different_root = 0
    same_root_examples = []
    different_root_examples = []

    for row in both_have_root:
        m_root = row['morpholex_root'].strip().lower()
        w_root = row['wiktextract_root'].strip().lower()

        if m_root == w_root:
            same_root += 1
            if len(same_root_examples) < 10:
                same_root_examples.append(row)
        else:
            different_root += 1
            if len(different_root_examples) < 10:
                different_root_examples.append(row)

    total_with_roots = same_root + different_root
    same_pct = (same_root / total_with_roots * 100) if total_with_roots > 0 else 0
    diff_pct = (different_root / total_with_roots * 100) if total_with_roots > 0 else 0

    print(f"Same root (despite type disagreement): {same_root:,} ({same_pct:.1f}%)")
    print(f"Different root: {different_root:,} ({diff_pct:.1f}%)")
    print()

    if same_root_examples:
        print("--- Examples: SAME ROOT (type differs) ---")
        for row in same_root_examples[:5]:
            print(f"  {row['word']}: MorphoLex={row['morpholex_type']}({row['morpholex_root']}), "
                  f"Wiktextract={row['wiktextract_type']}({row['wiktextract_root']})")
        print()

    if different_root_examples:
        print("--- Examples: DIFFERENT ROOT ---")
        for row in different_root_examples[:5]:
            print(f"  {row['word']}: MorphoLex={row['morpholex_type']}({row['morpholex_root']}), "
                  f"Wiktextract={row['wiktextract_type']}({row['wiktextract_root']})")
        print()

    print(f"End: {datetime.now().isoformat()}")

if __name__ == '__main__':
    main()
