#!/usr/bin/env python3
"""Compare MorphoLex vs Wiktextract for English words."""

import csv
import re
import os
from collections import Counter
from datetime import datetime

def parse_wiktextract_match(wikt_match):
    """Parse wiktextract_match field to extract type and root."""
    if not wikt_match or wikt_match.strip() == '':
        return None, None

    wikt_type = None
    wikt_root = None

    # Parse type=VALUE
    type_match = re.search(r'type=([A-Z_]+)', wikt_match)
    if type_match:
        wikt_type = type_match.group(1)

    # Parse from=VALUE
    from_match = re.search(r'from=([^|]+)', wikt_match)
    if from_match:
        wikt_root = from_match.group(1).strip()

    return wikt_type, wikt_root

def determine_agreement(morpholex_type, wiktextract_type):
    """Determine agreement category between two sources."""
    morpholex_has_type = morpholex_type and morpholex_type != 'UNKNOWN'
    wiktextract_has_type = wiktextract_type is not None

    if not morpholex_has_type and not wiktextract_has_type:
        return 'BOTH_UNKNOWN'
    elif morpholex_has_type and not wiktextract_has_type:
        return 'MORPHOLEX_ONLY'
    elif not morpholex_has_type and wiktextract_has_type:
        return 'WIKTEXTRACT_ONLY'
    elif morpholex_type == wiktextract_type:
        return 'MATCH'
    else:
        return 'DIFFERENT'

def main():
    print("=== COMPARE MORPHOLEX vs WIKTEXTRACT FOR ENGLISH ===")
    print(f"Start: {datetime.now().isoformat()}")
    print()

    input_file = '/mnt/pgdata/morphlex/data/master_table.csv'
    output_file = '/mnt/pgdata/morphlex/data/english_comparison.csv'

    print(f"Loading {input_file}...")

    english_rows = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('language') == 'en':
                english_rows.append(row)

    print(f"Total English rows: {len(english_rows)}")
    print()

    # Process and categorize
    comparison_rows = []
    agreement_counts = Counter()
    different_samples = []

    for row in english_rows:
        synset_id = row.get('synset_id', '')
        word = row.get('word', '')
        morpholex_root = row.get('root', '')
        morpholex_type = row.get('morph_type', '')
        wikt_match = row.get('wiktextract_match', '')

        wikt_type, wikt_root = parse_wiktextract_match(wikt_match)

        agreement = determine_agreement(morpholex_type, wikt_type)
        agreement_counts[agreement] += 1

        comparison_rows.append({
            'synset_id': synset_id,
            'word': word,
            'morpholex_root': morpholex_root,
            'morpholex_type': morpholex_type,
            'wiktextract_root': wikt_root or '',
            'wiktextract_type': wikt_type or '',
            'agreement': agreement
        })

        if agreement == 'DIFFERENT' and len(different_samples) < 10:
            different_samples.append({
                'word': word,
                'morpholex_type': morpholex_type,
                'wiktextract_type': wikt_type,
                'morpholex_root': morpholex_root,
                'wiktextract_root': wikt_root
            })

    # Write output file
    fieldnames = ['synset_id', 'word', 'morpholex_root', 'morpholex_type',
                  'wiktextract_root', 'wiktextract_type', 'agreement']

    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(comparison_rows)

    file_size = os.path.getsize(output_file)

    # Print results
    print("=== AGREEMENT DISTRIBUTION ===")
    total = len(english_rows)
    for category in ['MATCH', 'DIFFERENT', 'MORPHOLEX_ONLY', 'WIKTEXTRACT_ONLY', 'BOTH_UNKNOWN']:
        count = agreement_counts[category]
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {category}: {count:,} ({pct:.1f}%)")
    print()

    if different_samples:
        print("=== 10 SAMPLE ROWS WHERE THEY DISAGREE ===")
        for i, sample in enumerate(different_samples, 1):
            print(f"[{i}] word: '{sample['word']}'")
            print(f"    MorphoLex: type={sample['morpholex_type']}, root={sample['morpholex_root']}")
            print(f"    Wiktextract: type={sample['wiktextract_type']}, root={sample['wiktextract_root']}")
        print()

    print(f"Output file: {output_file}")
    print(f"File size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
    print()
    print(f"End: {datetime.now().isoformat()}")

if __name__ == '__main__':
    main()
