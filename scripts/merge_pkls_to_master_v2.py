#!/usr/bin/env python3
"""
Merge 5 pkl files into master_table_v2.csv.

Inputs:
- master_table.csv (existing 460,638 rows, 6 languages)
- kenet_synset_map.pkl (Turkish)
- german_wiktextract_synset_map.pkl (German)
- sanskrit_synset_map.pkl (Sanskrit)
- latin_synset_map.pkl (Latin)
- agwn_synset_map.pkl (Greek)
- pwn30_to_oewn_map.pkl (synset ID bridge)

Output: master_table_v2.csv

Zero error suppression.
"""

import csv
import os
import pickle
import sys
import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path('/mnt/pgdata/morphlex/data')
OPEN_WORDNETS_DIR = DATA_DIR / 'open_wordnets'
MASTER_TABLE = DATA_DIR / 'master_table.csv'
OUTPUT_FILE = DATA_DIR / 'master_table_v2.csv'

PKL_FILES = {
    'tr': ('kenet_synset_map.pkl', 'Turkish'),
    'de': ('german_wiktextract_synset_map.pkl', 'German'),
    'sa': ('sanskrit_synset_map.pkl', 'Sanskrit'),
    'la': ('latin_synset_map.pkl', 'Latin'),
    'grc': ('agwn_synset_map.pkl', 'Greek'),
}

BRIDGE_FILE = OPEN_WORDNETS_DIR / 'pwn30_to_oewn_map.pkl'


def log(msg):
    print(msg, flush=True)


def load_pkl(path):
    """Load a pickle file, return empty dict if not found or empty."""
    if not path.exists():
        log(f"  WARNING: {path.name} not found")
        return {}

    with open(path, 'rb') as f:
        data = pickle.load(f)

    if not data:
        log(f"  WARNING: {path.name} is empty")
        return {}

    return data


def load_bridge():
    """Load PWN30 to OEWN bridge mapping."""
    if not BRIDGE_FILE.exists():
        log(f"WARNING: Bridge file not found: {BRIDGE_FILE}")
        return {}

    with open(BRIDGE_FILE, 'rb') as f:
        bridge = pickle.load(f)

    log(f"Loaded bridge: {len(bridge):,} mappings")
    return bridge


def convert_to_oewn(synset_id, bridge):
    """Convert a synset ID to OEWN format if needed."""
    if synset_id.startswith('oewn-'):
        return synset_id

    if synset_id in bridge:
        return bridge[synset_id]

    oewn_id = f"oewn-{synset_id}"
    return oewn_id


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
    log("MERGE 5 PKLS INTO MASTER_TABLE_V2.CSV")
    log("=" * 70)

    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        log(f"Git HEAD: {git_head}")
    log(f"Start: {start_time.isoformat()}")
    log("")

    # Check master_table.csv exists
    if not MASTER_TABLE.exists():
        log(f"FATAL: master_table.csv not found at {MASTER_TABLE}")
        sys.exit(1)

    # Count existing rows
    log("=" * 70)
    log("STEP 1: COUNT EXISTING MASTER_TABLE.CSV")
    log("=" * 70)
    log("")

    existing_rows = 0
    existing_langs = set()

    with open(MASTER_TABLE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        log(f"Existing columns: {headers}")

        for row in reader:
            existing_rows += 1
            lang = row.get('language', row.get('lang', ''))
            if lang:
                existing_langs.add(lang)

    log(f"Existing rows: {existing_rows:,}")
    log(f"Existing languages: {sorted(existing_langs)}")
    log("")

    # Load PWN30 to OEWN bridge
    log("=" * 70)
    log("STEP 2: LOAD BRIDGE AND PKL FILES")
    log("=" * 70)
    log("")

    bridge = load_bridge()

    # Load each pkl file
    synset_maps = {}
    skipped_langs = []

    for lang_code, (pkl_name, lang_name) in PKL_FILES.items():
        pkl_path = OPEN_WORDNETS_DIR / pkl_name
        log(f"Loading {lang_name} ({pkl_name})...")
        synset_map = load_pkl(pkl_path)

        if synset_map:
            synset_count = len(synset_map)
            word_count = sum(len(words) for words in synset_map.values())
            log(f"  {synset_count:,} synsets, {word_count:,} words")
            synset_maps[lang_code] = synset_map
        else:
            log(f"  SKIPPING {lang_name} - empty or missing pkl")
            skipped_langs.append(lang_name)

    log("")

    # Copy master_table.csv to master_table_v2.csv and prepare to append
    log("=" * 70)
    log("STEP 3: COPY MASTER_TABLE AND PROCESS NEW LANGUAGES")
    log("=" * 70)
    log("")

    # Define output columns
    output_columns = [
        'synset_id', 'pos', 'definition', 'language', 'word',
        'root', 'morph_type', 'derivation_info', 'compound_components', 'wiktextract_match'
    ]

    # First, copy existing data
    log("Copying existing master_table.csv...")

    copied_rows = 0
    with open(MASTER_TABLE, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)

        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=output_columns)
            writer.writeheader()

            for row in reader:
                # Map old columns to new columns
                synset_id = row.get('synset_id', row.get('concept_id', ''))
                pos = row.get('pos', '')
                definition = row.get('definition', row.get('sense', ''))
                language = row.get('language', row.get('lang', ''))
                word = row.get('word', row.get('translated_word', ''))
                root = row.get('root', '')
                morph_type = row.get('morph_type', '')

                # Combine derivation fields
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

    log(f"Copied {copied_rows:,} existing rows")
    log("")

    # Process each language and append new rows
    log("Processing new languages...")
    log("")

    new_rows_by_lang = {}
    total_new_rows = 0

    for lang_code, synset_map in synset_maps.items():
        lang_name = PKL_FILES[lang_code][1]
        log(f"Processing {lang_name} ({lang_code})...")

        lang_rows = 0
        words_analyzed = 0
        words_with_root = 0

        with open(OUTPUT_FILE, 'a', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=output_columns)

            for synset_id, words in synset_map.items():
                # Convert synset ID to OEWN format
                oewn_id = convert_to_oewn(synset_id, bridge)

                # Extract POS from synset ID if present
                pos = ''
                if '-' in synset_id:
                    pos_char = synset_id.split('-')[-1]
                    pos_map = {'n': 'noun', 'v': 'verb', 'a': 'adj', 's': 'adj', 'r': 'adv'}
                    pos = pos_map.get(pos_char, '')

                for word in words:
                    if not word or not word.strip():
                        continue

                    word = word.strip()
                    words_analyzed += 1

                    # Analyze word using language adapter
                    analysis = analyze_word(word, lang_code)

                    root = analysis.get('root', '')
                    morph_type = analysis.get('morph_type', '')

                    # Get derivation info
                    derivation_info = analysis.get('derivation_mode', '') or analysis.get('derivation_rule', '')
                    if analysis.get('derivation_source'):
                        derivation_info = f"{derivation_info}: {analysis['derivation_source']}" if derivation_info else analysis['derivation_source']

                    # Get compound components
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
                        'synset_id': oewn_id,
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

                    # Progress report every 50k words
                    if words_analyzed % 50000 == 0:
                        log(f"  Progress: {words_analyzed:,} words processed...")

        new_rows_by_lang[lang_code] = lang_rows
        total_new_rows += lang_rows
        root_pct = 100 * words_with_root / words_analyzed if words_analyzed > 0 else 0
        log(f"  {lang_name}: {lang_rows:,} rows added, {words_with_root:,}/{words_analyzed:,} words with roots ({root_pct:.1f}%)")

    log("")

    # Final stats
    log("=" * 70)
    log("FINAL STATS")
    log("=" * 70)
    log("")

    final_rows = copied_rows + total_new_rows
    file_size = OUTPUT_FILE.stat().st_size
    file_size_mb = file_size / (1024 * 1024)

    log("Per-language row counts:")
    log(f"  BEFORE (existing): {copied_rows:,} rows")
    for lang_code, count in new_rows_by_lang.items():
        lang_name = PKL_FILES[lang_code][1]
        log(f"  {lang_name} ({lang_code}): +{count:,} rows")
    log(f"  TOTAL NEW: +{total_new_rows:,} rows")
    log("")
    log(f"Total rows: {final_rows:,}")
    log(f"File size: {file_size_mb:.2f} MB ({file_size:,} bytes)")
    log("")

    if skipped_langs:
        log(f"Languages skipped (empty pkls): {', '.join(skipped_langs)}")
    else:
        log("All 5 languages processed successfully")

    log("")
    log(f"Output: {OUTPUT_FILE}")

    duration = datetime.now() - start_time
    log(f"Duration: {duration}")
    log(f"End: {datetime.now().isoformat()}")


if __name__ == '__main__':
    main()
