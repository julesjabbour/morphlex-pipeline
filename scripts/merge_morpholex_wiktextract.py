#!/usr/bin/env python3
"""Merge MorphoLex and Wiktextract for English using priority rule."""

import csv
import re
from collections import Counter
from datetime import datetime

# Priority: COMPOUND_DERIVATION > COMPOUND > DERIVATION > ROOT > UNKNOWN
PRIORITY = {
    'COMPOUND_DERIVATION': 5,
    'COMPOUND': 4,
    'DERIVATION': 3,
    'ROOT': 2,
    'UNKNOWN': 1,
    '': 0,
    None: 0
}

def parse_wiktextract_match(wikt_match):
    """Parse wiktextract_match field to extract type and root."""
    if not wikt_match or wikt_match.strip() == '':
        return None, None

    wikt_type = None
    wikt_root = None

    type_match = re.search(r'type=([A-Z_]+)', wikt_match)
    if type_match:
        wikt_type = type_match.group(1)

    from_match = re.search(r'from=([^|]+)', wikt_match)
    if from_match:
        wikt_root = from_match.group(1).strip()

    return wikt_type, wikt_root

def get_priority(morph_type):
    """Get priority value for a morph_type."""
    return PRIORITY.get(morph_type, 0)

def main():
    print("=== MERGE MORPHOLEX + WIKTEXTRACT FOR ENGLISH ===")
    print(f"Start: {datetime.now().isoformat()}")
    print()

    master_file = '/mnt/pgdata/morphlex/data/master_table.csv'

    print(f"Loading {master_file}...")

    all_rows = []
    english_indices = []

    with open(master_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for i, row in enumerate(reader):
            all_rows.append(row)
            if row.get('language') == 'en':
                english_indices.append(i)

    print(f"Total rows: {len(all_rows):,}")
    print(f"English rows: {len(english_indices):,}")
    print()

    # Track changes
    changed_rows = 0
    changed_samples = []
    old_type_dist = Counter()
    new_type_dist = Counter()

    for idx in english_indices:
        row = all_rows[idx]

        morpholex_type = row.get('morph_type', '') or ''
        morpholex_root = row.get('root', '') or ''
        morpholex_derivation = row.get('derivation_info', '') or ''
        wikt_match = row.get('wiktextract_match', '') or ''

        wikt_type, wikt_root = parse_wiktextract_match(wikt_match)
        wikt_type = wikt_type or ''

        old_type_dist[morpholex_type or 'UNKNOWN'] += 1

        # Determine winner by priority
        morpholex_priority = get_priority(morpholex_type)
        wikt_priority = get_priority(wikt_type)

        new_type = morpholex_type
        new_root = morpholex_root
        new_derivation = morpholex_derivation
        winner = 'morpholex'

        if wikt_priority > morpholex_priority:
            new_type = wikt_type
            winner = 'wiktextract'
        elif morpholex_priority > wikt_priority:
            new_type = morpholex_type
            winner = 'morpholex'
        else:
            # Tie - keep MorphoLex
            winner = 'morpholex'

        # Determine root
        if winner == 'wiktextract' and wikt_root:
            new_root = wikt_root
        elif winner == 'morpholex':
            new_root = morpholex_root
        else:
            # If winner has no root, use whichever source has one
            if wikt_root and not morpholex_root:
                new_root = wikt_root
            else:
                new_root = morpholex_root

        # Determine derivation_info
        if new_type in ('DERIVATION', 'COMPOUND_DERIVATION') and wikt_root and winner == 'wiktextract':
            new_derivation = wikt_root
        # Otherwise keep MorphoLex derivation_info

        # Check if anything changed
        type_changed = (new_type != morpholex_type)

        if type_changed:
            changed_rows += 1
            if len(changed_samples) < 10:
                changed_samples.append({
                    'word': row.get('word', ''),
                    'old_type': morpholex_type,
                    'new_type': new_type,
                    'old_root': morpholex_root,
                    'new_root': new_root
                })

        # Update row
        row['morph_type'] = new_type
        row['root'] = new_root
        row['derivation_info'] = new_derivation

        new_type_dist[new_type or 'UNKNOWN'] += 1

    # Save back to master_table.csv
    print("Saving to master_table.csv...")
    with open(master_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    print("Saved.")
    print()

    # Calculate overall distribution
    overall_dist = Counter()
    for row in all_rows:
        overall_dist[row.get('morph_type', '') or 'UNKNOWN'] += 1

    # Print results
    print(f"Total English rows processed: {len(english_indices):,}")
    print(f"Rows with morph_type changed: {changed_rows:,}")
    print()

    print("=== NEW ENGLISH MORPH_TYPE DISTRIBUTION ===")
    for t in ['COMPOUND_DERIVATION', 'COMPOUND', 'DERIVATION', 'ROOT', 'UNKNOWN']:
        count = new_type_dist.get(t, 0)
        pct = (count / len(english_indices) * 100) if english_indices else 0
        print(f"  {t}: {count:,} ({pct:.1f}%)")
    print()

    print("=== NEW OVERALL MORPH_TYPE DISTRIBUTION (ALL LANGUAGES) ===")
    for t in ['COMPOUND_DERIVATION', 'COMPOUND', 'DERIVATION', 'ROOT', 'UNKNOWN']:
        count = overall_dist.get(t, 0)
        pct = (count / len(all_rows) * 100) if all_rows else 0
        print(f"  {t}: {count:,} ({pct:.1f}%)")
    print()

    if changed_samples:
        print("=== 10 SAMPLE ROWS WHERE MERGE CHANGED SOMETHING ===")
        for i, s in enumerate(changed_samples, 1):
            print(f"[{i}] {s['word']}: {s['old_type']} -> {s['new_type']} | root: {s['old_root']} -> {s['new_root']}")

    print()
    print(f"End: {datetime.now().isoformat()}")

if __name__ == '__main__':
    main()
