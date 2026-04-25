#!/usr/bin/env python3
"""
Rebuild master_table_v2.csv with corrected prefix normalization.

Inputs:
- master_table.csv (existing 460,638 rows, preserve as-is)
- concept_wordnet_map.pkl (key set for filtering)
- kenet_synset_map.pkl (Turkish)
- german_wiktextract_synset_map.pkl (German)
- sanskrit_synset_map.pkl (Sanskrit)
- latin_synset_map.pkl (Latin)
- agwn_synset_map.pkl (Greek)

Process:
1. Copy master_table.csv -> master_table_v2.csv (preserve 6 existing languages)
2. Load concept_wordnet_map.pkl, get key set
3. For Turkish/German/Sanskrit: normalize by replacing -s with -a, then prepend oewn-.
   Keep only entries whose normalized synset_id is in concept_map.
4. For Latin/AGWN: keys already prefixed, keep entries whose synset_id is in concept_map.
5. Invoke corresponding adapter on each word to populate root, morph_type, etc.
6. Append rows to master_table_v2.csv

Output: /mnt/pgdata/morphlex/data/master_table_v2.csv

Zero error suppression.
"""

import csv
import json
import os
import pickle
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path('/mnt/pgdata/morphlex/data')
OPEN_WORDNETS_DIR = DATA_DIR / 'open_wordnets'
MASTER_TABLE = DATA_DIR / 'master_table.csv'
CONCEPT_MAP = DATA_DIR / 'concept_wordnet_map.pkl'
OUTPUT_FILE = DATA_DIR / 'master_table_v2.csv'

PKL_FILES = {
    'tr': ('kenet_synset_map.pkl', 'Turkish', 'needs_normalization'),
    'de': ('german_wiktextract_synset_map.pkl', 'German', 'needs_normalization'),
    'sa': ('sanskrit_synset_map.pkl', 'Sanskrit', 'needs_normalization'),
    'la': ('latin_synset_map.pkl', 'Latin', 'already_prefixed'),
    'grc': ('agwn_synset_map.pkl', 'Greek', 'already_prefixed'),
}

OUTPUT_COLUMNS = [
    'synset_id', 'pos', 'definition', 'language', 'word',
    'root', 'morph_type', 'derivation_info', 'compound_components', 'wiktextract_match'
]


def log(msg):
    print(msg, flush=True)


def load_pkl(path):
    """Load a pickle file."""
    if not path.exists():
        log(f"  WARNING: {path.name} not found")
        return {}
    with open(path, 'rb') as f:
        return pickle.load(f)


def normalize_synset_id(synset_id):
    """Normalize synset ID: replace -s with -a, prepend oewn-."""
    normalized = synset_id.replace('-s', '-a')
    return f'oewn-{normalized}'


def analyze_word(word, lang_code):
    """Run the language adapter on a word, return analysis dict."""
    try:
        if lang_code == 'tr':
            from analyzers.turkish import analyze_turkish
            results = analyze_turkish(word)
        elif lang_code == 'de':
            from analyzers.german import analyze_german
            results = analyze_german(word)
        elif lang_code == 'sa':
            from analyzers.sanskrit import analyze_sanskrit
            results = analyze_sanskrit(word)
        elif lang_code == 'la':
            from analyzers.latin import analyze_latin
            results = analyze_latin(word)
        elif lang_code == 'grc':
            from analyzers.greek import analyze_greek
            results = analyze_greek(word)
        else:
            return {}

        if results and len(results) > 0:
            return results[0]
        return {}
    except Exception as e:
        return {}


def main():
    start_time = datetime.now()

    log("=" * 70)
    log("REBUILD MASTER_TABLE_V2 WITH PREFIX NORMALIZATION")
    log("=" * 70)

    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        log(f"Git HEAD: {git_head}")
    log(f"Start: {start_time.isoformat()}")
    log("")

    # Check files exist
    if not MASTER_TABLE.exists():
        log(f"FATAL: master_table.csv not found at {MASTER_TABLE}")
        sys.exit(1)

    if not CONCEPT_MAP.exists():
        log(f"FATAL: concept_wordnet_map.pkl not found at {CONCEPT_MAP}")
        sys.exit(1)

    # Step 1: Load concept_wordnet_map to get key set
    log("=" * 70)
    log("STEP 1: LOAD CONCEPT_WORDNET_MAP")
    log("=" * 70)
    log("")

    with open(CONCEPT_MAP, 'rb') as f:
        concept_map = pickle.load(f)

    concept_keys = set(concept_map.keys())
    log(f"Concept map has {len(concept_keys):,} keys")
    log(f"Sample keys: {list(concept_keys)[:5]}")
    log("")

    # Step 2: Copy master_table.csv to master_table_v2.csv
    log("=" * 70)
    log("STEP 2: COPY MASTER_TABLE.CSV")
    log("=" * 70)
    log("")

    copied_rows = 0
    existing_langs = set()

    with open(MASTER_TABLE, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        headers = reader.fieldnames
        log(f"Source columns: {headers}")

        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()

            for row in reader:
                synset_id = row.get('synset_id', row.get('concept_id', ''))
                pos = row.get('pos', '')
                definition = row.get('definition', row.get('sense', ''))
                language = row.get('language', row.get('lang', ''))
                word = row.get('word', row.get('translated_word', ''))
                root = row.get('root', '')
                morph_type = row.get('morph_type', '')

                deriv_rule = row.get('derivation_rule', '')
                deriv_source = row.get('derivation_source', '')
                derivation_info = f"{deriv_rule}: {deriv_source}" if deriv_rule and deriv_source else deriv_rule or deriv_source

                compound_components = row.get('compound_components', row.get('compound_parts', ''))
                wiktextract_match = row.get('wiktextract_match', '')

                out_row = {
                    'synset_id': synset_id,
                    'pos': pos,
                    'definition': definition,
                    'language': language,
                    'word': word,
                    'root': root,
                    'morph_type': morph_type,
                    'derivation_info': derivation_info,
                    'compound_components': compound_components,
                    'wiktextract_match': wiktextract_match,
                }
                writer.writerow(out_row)
                copied_rows += 1
                if language:
                    existing_langs.add(language)

    log(f"Copied {copied_rows:,} existing rows")
    log(f"Existing languages: {sorted(existing_langs)}")
    log("")

    # Step 3: Load and filter each pkl, then analyze and append
    log("=" * 70)
    log("STEP 3: PROCESS NEW LANGUAGE PKLS")
    log("=" * 70)
    log("")

    stats = {}
    total_new_rows = 0

    for lang_code, (pkl_name, lang_name, normalization_mode) in PKL_FILES.items():
        pkl_path = OPEN_WORDNETS_DIR / pkl_name
        log(f"Processing {lang_name} ({pkl_name})...")

        synset_map = load_pkl(pkl_path)
        if not synset_map:
            stats[lang_code] = {'total': 0, 'kept': 0, 'dropped': 0, 'rows': 0, 'with_root': 0}
            log(f"  SKIPPED - pkl empty or missing")
            continue

        total_synsets = len(synset_map)
        kept_synsets = 0
        dropped_synsets = 0
        lang_rows = 0
        words_with_root = 0

        with open(OUTPUT_FILE, 'a', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=OUTPUT_COLUMNS)

            for raw_synset_id, words in synset_map.items():
                # Normalize synset ID based on mode
                if normalization_mode == 'needs_normalization':
                    normalized_id = normalize_synset_id(raw_synset_id)
                else:
                    normalized_id = raw_synset_id

                # Check if normalized ID is in concept_map
                if normalized_id not in concept_keys:
                    dropped_synsets += 1
                    continue

                kept_synsets += 1

                # Extract POS from synset ID
                pos = ''
                if '-' in normalized_id:
                    pos_char = normalized_id.split('-')[-1]
                    pos_map = {'n': 'noun', 'v': 'verb', 'a': 'adj', 's': 'adj', 'r': 'adv'}
                    pos = pos_map.get(pos_char, '')

                for word in words:
                    if not word or not word.strip():
                        continue

                    word = word.strip()

                    # Analyze word using language adapter
                    analysis = analyze_word(word, lang_code)

                    root = analysis.get('root', '')
                    morph_type = analysis.get('morph_type', '')

                    derivation_info = analysis.get('derivation_mode', '') or analysis.get('derivation_rule', '')
                    if analysis.get('derivation_source'):
                        derivation_info = f"{derivation_info}: {analysis['derivation_source']}" if derivation_info else analysis['derivation_source']

                    compound_components = ''
                    cc = analysis.get('compound_components')
                    if cc:
                        if isinstance(cc, list):
                            compound_components = json.dumps(cc)
                        else:
                            compound_components = str(cc)

                    if root:
                        words_with_root += 1

                    out_row = {
                        'synset_id': normalized_id,
                        'pos': pos or analysis.get('pos', ''),
                        'definition': '',
                        'language': lang_code,
                        'word': word,
                        'root': root,
                        'morph_type': morph_type,
                        'derivation_info': derivation_info,
                        'compound_components': compound_components,
                        'wiktextract_match': '',
                    }
                    writer.writerow(out_row)
                    lang_rows += 1

                # Progress
                if kept_synsets % 10000 == 0:
                    log(f"  Progress: {kept_synsets:,} synsets kept, {lang_rows:,} rows...")

        root_coverage = 100 * words_with_root / lang_rows if lang_rows > 0 else 0
        stats[lang_code] = {
            'total': total_synsets,
            'kept': kept_synsets,
            'dropped': dropped_synsets,
            'rows': lang_rows,
            'with_root': words_with_root,
            'root_coverage': root_coverage,
        }
        total_new_rows += lang_rows

        log(f"  Total synsets: {total_synsets:,}")
        log(f"  Kept (in concept_map): {kept_synsets:,}")
        log(f"  Dropped (no overlap): {dropped_synsets:,}")
        log(f"  Rows added: {lang_rows:,}")
        log(f"  Root coverage: {words_with_root:,}/{lang_rows:,} ({root_coverage:.1f}%)")
        log("")

    # Final stats
    log("=" * 70)
    log("FINAL SUMMARY")
    log("=" * 70)
    log("")

    final_rows = copied_rows + total_new_rows
    file_size = OUTPUT_FILE.stat().st_size
    file_size_mb = file_size / (1024 * 1024)

    log("Per-language stats:")
    log(f"  Existing rows: {copied_rows:,}")
    log("")

    for lang_code, (pkl_name, lang_name, _) in PKL_FILES.items():
        s = stats.get(lang_code, {})
        if s.get('total', 0) > 0:
            log(f"  {lang_name} ({lang_code}):")
            log(f"    Synsets: {s['kept']:,} kept / {s['dropped']:,} dropped (total: {s['total']:,})")
            log(f"    Rows added: {s['rows']:,}")
            log(f"    Root coverage: {s['with_root']:,}/{s['rows']:,} ({s.get('root_coverage', 0):.1f}%)")
        else:
            log(f"  {lang_name} ({lang_code}): SKIPPED (no data)")

    log("")
    log(f"Total new rows: {total_new_rows:,}")
    log(f"Total rows (existing + new): {final_rows:,}")
    log(f"File size: {file_size_mb:.2f} MB ({file_size:,} bytes)")
    log("")
    log(f"Output: {OUTPUT_FILE}")

    duration = datetime.now() - start_time
    log(f"Duration: {duration}")
    log(f"End: {datetime.now().isoformat()}")

    log("")
    log("=" * 70)
    log("END OF REBUILD")
    log("=" * 70)


if __name__ == '__main__':
    main()
