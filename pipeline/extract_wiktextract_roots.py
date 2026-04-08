#!/usr/bin/env python3
"""Extract {{root|lang|...}} templates from Wiktextract data.

This script processes raw-wiktextract-data.jsonl.gz and extracts root information
from etymology_templates where name == 'root'.

Output: data/wiktextract_roots.pkl
Format: {lang_code: {word: [roots]}}
"""

import gzip
import json
import os
import pickle
import sys
from collections import defaultdict
from datetime import datetime

# Paths
DATA_DIR = '/mnt/pgdata/morphlex/data'
INPUT_FILE = os.path.join(DATA_DIR, 'raw-wiktextract-data.jsonl.gz')
OUTPUT_FILE = os.path.join(DATA_DIR, 'wiktextract_roots.pkl')

# Languages we care about (entry languages)
TARGET_LANGUAGES = {'he', 'sa', 'grc', 'ar', 'la', 'en', 'de', 'tr', 'zh', 'ja', 'ine-pro'}

# Languages where we want to filter out PIE reconstructions
# For these languages, exclude roots where source_lang is 'ine-pro'
FILTER_PIE_ROOTS = {'he', 'sa', 'ar', 'grc'}


def extract_roots():
    """Extract root templates from Wiktextract data."""
    print(f"[{datetime.now().isoformat()}] Starting root extraction from {INPUT_FILE}")

    if not os.path.exists(INPUT_FILE):
        print(f"ERROR: Input file not found: {INPUT_FILE}")
        sys.exit(1)

    # Structure: {lang_code: {word: [roots]}}
    roots_index = defaultdict(lambda: defaultdict(list))

    entries_processed = 0
    roots_found = 0

    with gzip.open(INPUT_FILE, 'rt', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if line_num % 100000 == 0:
                print(f"  Processed {line_num:,} entries, found {roots_found:,} roots...")

            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            entries_processed += 1

            # Get the word and its language (entry language)
            word = entry.get('word', '')
            lang_code = entry.get('lang_code', '')

            # Only process entries in target languages
            if not word or lang_code not in TARGET_LANGUAGES:
                continue

            # Check etymology_templates for root templates
            etymology_templates = entry.get('etymology_templates', [])
            if not etymology_templates:
                continue

            for tmpl in etymology_templates:
                if not isinstance(tmpl, dict):
                    continue

                # Look for {{root|...}} templates
                if tmpl.get('name') != 'root':
                    continue

                args = tmpl.get('args', {})
                if not isinstance(args, dict):
                    continue

                # Template format: {{root|target_lang|source_lang|root1|root2|...}}
                # args['1'] = target language (should match entry lang)
                # args['2'] = source language of the ROOT (he, sa, ine-pro, etc.)
                # args['3'], args['4'], etc. = actual root consonants

                source_lang = args.get('2', '').strip()

                # For Hebrew/Sanskrit/Arabic/Greek: filter out PIE reconstructions
                # This fixes Bug 1 where Hebrew roots showed *ḱerd- instead of consonantal roots
                # And Bug 2a where Greek roots showed *wed- instead of Greek roots
                if lang_code in FILTER_PIE_ROOTS:
                    if source_lang == 'ine-pro':
                        continue  # Skip PIE roots for these languages

                # Extract roots from position 3 onwards
                root_parts = []
                for i in range(3, 10):  # Check positions 3-9
                    root_val = args.get(str(i), '')
                    if root_val and root_val != '-':
                        root_parts.append(root_val)

                if root_parts:
                    # Store as joined root (e.g., "k-t-b" for triconsonantal)
                    root_str = '-'.join(root_parts)
                    # Index by entry language (so adapters can look up words)
                    if root_str not in roots_index[lang_code][word]:
                        roots_index[lang_code][word].append(root_str)
                        roots_found += 1

    print(f"[{datetime.now().isoformat()}] Extraction complete")
    print(f"  Total entries processed: {entries_processed:,}")
    print(f"  Total roots found: {roots_found:,}")
    print()

    # Convert defaultdicts to regular dicts for pickling
    roots_dict = {lang: dict(words) for lang, words in roots_index.items()}

    # Print per-language counts
    print("Roots per language:")
    total_words = 0
    for lang in sorted(roots_dict.keys()):
        word_count = len(roots_dict[lang])
        total_words += word_count
        print(f"  {lang}: {word_count:,} words with roots")
    print(f"  TOTAL: {total_words:,} words with roots")
    print()

    # Save to pickle
    print(f"Saving to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'wb') as f:
        pickle.dump(roots_dict, f)

    print(f"[{datetime.now().isoformat()}] Done. Output: {OUTPUT_FILE}")

    return roots_dict


if __name__ == '__main__':
    extract_roots()
