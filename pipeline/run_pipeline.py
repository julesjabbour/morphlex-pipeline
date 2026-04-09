#!/usr/bin/env python3
"""
FULL PRODUCTION RUN: Run Morphological Pipeline on ALL WordNet Concepts

Processes ALL concepts from data/concept_wordnet_map.pkl through language adapters
and cross-references with data/wiktextract_morphology.pkl.

Output: data/master_table.csv
Columns: synset_id, pos, definition, language, word, root, morph_type,
         derivation_info, compound_components, wiktextract_match

With checkpointing every 1,000 concepts for crash recovery.
"""
import sys
# Fix Python path BEFORE any local imports
sys.path.insert(0, '/mnt/pgdata/morphlex')

# Suppress all library debug output - set logging to WARNING level
import logging
logging.basicConfig(level=logging.WARNING)
# Also suppress specific noisy loggers
for name in ['urllib3', 'camel_tools', 'spacy', 'mecab', 'hspell']:
    logging.getLogger(name).setLevel(logging.WARNING)

import csv
import importlib
import os
import pickle
import time
from datetime import datetime

# Output paths
CONCEPT_MAP_PATH = '/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl'
WIKTEXTRACT_MORPH_PATH = '/mnt/pgdata/morphlex/data/wiktextract_morphology.pkl'
OUTPUT_CSV_PATH = '/mnt/pgdata/morphlex/data/master_table.csv'
CHECKPOINT_PATH = '/mnt/pgdata/morphlex/data/pipeline_checkpoint.pkl'

# Target languages (only process concepts with 2+ of these)
TARGET_LANGS = {'arb', 'en', 'cmn-Hans', 'ja', 'he', 'el'}

# Language code to adapter module mapping
# Maps concept_wordnet_map language codes to analyzer modules and functions
ADAPTER_MAP = {
    'arb': ('analyzers.arabic', 'analyze_arabic'),
    'en': ('analyzers.english', 'analyze_english'),
    'cmn-Hans': ('analyzers.chinese', 'analyze_chinese'),
    'ja': ('analyzers.japanese', 'analyze_japanese'),
    'he': ('analyzers.hebrew', 'analyze_hebrew'),
    'el': ('analyzers.greek', 'analyze_greek'),
}

# Wiktextract language code mapping (concept map codes -> wiktextract codes)
WIKTEXTRACT_LANG_MAP = {
    'arb': 'ar',
    'en': 'en',
    'cmn-Hans': 'zh',
    'ja': 'ja',
    'he': 'he',
    'el': 'grc',
}


def log(msg):
    """Print with timestamp."""
    print(f"[{datetime.now().isoformat()}] {msg}", flush=True)


def load_adapter(lang_code):
    """
    Load adapter for a language code.

    Returns: (analyze_function, error_message)
    If adapter can't be loaded, returns (None, error_message)
    """
    if lang_code not in ADAPTER_MAP:
        return None, f"No adapter mapping for language '{lang_code}'"

    module_name, func_name = ADAPTER_MAP[lang_code]

    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        return None, f"Cannot import module '{module_name}': {e}"
    except Exception as e:
        return None, f"Error loading module '{module_name}': {e}"

    if not hasattr(module, func_name):
        # Try alternate function names
        alt_names = ['analyze', 'get_root', f'analyze_{lang_code}']
        for alt in alt_names:
            if hasattr(module, alt):
                return getattr(module, alt), None
        return None, f"Module '{module_name}' has no function '{func_name}'"

    func = getattr(module, func_name)
    if not callable(func):
        return None, f"'{func_name}' in module '{module_name}' is not callable"

    return func, None


def get_wiktextract_match(word, lang_code, wiktextract_data):
    """
    Look up word in wiktextract_morphology.pkl.

    Returns: dict with match data or None
    """
    wikt_lang = WIKTEXTRACT_LANG_MAP.get(lang_code, lang_code)

    if wikt_lang not in wiktextract_data:
        return None

    return wiktextract_data[wikt_lang].get(word)


def run_adapter(adapter_func, word, lang_code):
    """
    Run adapter on a word safely.

    Returns: dict with root, morph_type, derivation_info, compound_components
    or dict with empty values on error
    """
    result = {
        'root': '',
        'morph_type': '',
        'derivation_info': '',
        'compound_components': '',
    }

    try:
        analyses = adapter_func(word)
        if analyses and len(analyses) > 0:
            # Take first analysis
            analysis = analyses[0]
            result['root'] = analysis.get('root', '') or ''
            result['morph_type'] = analysis.get('morph_type', '') or ''

            # Get derivation info (different adapters use different keys)
            deriv = (analysis.get('derivation_type') or
                     analysis.get('derivation_mode') or
                     analysis.get('derived_from_root', ''))
            result['derivation_info'] = str(deriv) if deriv else ''

            # Get compound components
            components = analysis.get('compound_components')
            if components:
                if isinstance(components, list):
                    result['compound_components'] = '|'.join(str(c) for c in components)
                else:
                    result['compound_components'] = str(components)
    except Exception as e:
        log(f"  ERROR: Adapter error for '{word}' ({lang_code}): {e}")

    return result


def main():
    """Main entry point."""
    start_time = time.time()

    log("=" * 70)
    log("FULL PRODUCTION RUN: Morphological Pipeline on ALL Concepts")
    log("=" * 70)
    log(f"Git HEAD: {os.popen('git rev-parse HEAD 2>/dev/null').read().strip()}")
    log(f"Start: {datetime.now().isoformat()}")
    log("")

    # Load concept map
    log(f"Loading concept map from {CONCEPT_MAP_PATH}...")
    if not os.path.exists(CONCEPT_MAP_PATH):
        log(f"FATAL: Concept map not found at {CONCEPT_MAP_PATH}")
        sys.exit(1)

    with open(CONCEPT_MAP_PATH, 'rb') as f:
        concept_map = pickle.load(f)
    log(f"Loaded {len(concept_map):,} synsets")

    # Load wiktextract morphology data
    log(f"Loading wiktextract morphology from {WIKTEXTRACT_MORPH_PATH}...")
    wiktextract_data = {}
    if os.path.exists(WIKTEXTRACT_MORPH_PATH):
        with open(WIKTEXTRACT_MORPH_PATH, 'rb') as f:
            wiktextract_data = pickle.load(f)
        log(f"Loaded wiktextract data for {len(wiktextract_data)} languages")
    else:
        log("WARNING: Wiktextract morphology file not found - proceeding without it")

    # Load adapters
    log("\nLoading language adapters...")
    adapters = {}
    for lang_code in ADAPTER_MAP:
        func, error = load_adapter(lang_code)
        if func:
            adapters[lang_code] = func
            log(f"  {lang_code}: OK")
        else:
            log(f"  {lang_code}: SKIPPED - {error}")

    log(f"\nLoaded {len(adapters)} adapters: {list(adapters.keys())}")

    # Filter concepts with 2+ of our target languages
    log("\nFiltering concepts with 2+ target languages...")
    multilingual = []
    for synset_id, data in concept_map.items():
        words = data.get('words', {})
        target_lang_count = sum(1 for lang in words if lang in TARGET_LANGS)
        if target_lang_count >= 2:
            multilingual.append((synset_id, data))

    total_concepts = len(multilingual)
    log(f"Found {total_concepts:,} concepts with 2+ target languages")

    # Check for checkpoint - resume if exists
    processed_synsets = set()
    rows = []
    lang_row_counts = {}
    start_idx = 0

    if os.path.exists(CHECKPOINT_PATH):
        log(f"\nLoading checkpoint from {CHECKPOINT_PATH}...")
        with open(CHECKPOINT_PATH, 'rb') as f:
            checkpoint = pickle.load(f)
        processed_synsets = set(checkpoint.get('processed_synset_ids', []))
        rows = checkpoint.get('rows', [])
        lang_row_counts = checkpoint.get('lang_row_counts', {})
        log(f"Resuming from checkpoint: {len(processed_synsets)} concepts already done.")
        log(f"Rows recovered: {len(rows)}")

    log(f"\nProcessing ALL {total_concepts:,} concepts...")

    # Process concepts
    log("\n" + "=" * 70)
    log("PROCESSING")
    log("=" * 70)

    errors_count = 0
    skipped_count = len(processed_synsets)
    processed_count = skipped_count

    try:
        for idx, (synset_id, data) in enumerate(multilingual):
            # Skip already processed
            if synset_id in processed_synsets:
                continue

            pos = data.get('pos', '')
            definition = data.get('definition', '')
            words_by_lang = data.get('words', {})

            for lang_code, words in words_by_lang.items():
                # Check if we have an adapter for this language
                if lang_code not in adapters:
                    continue

                adapter_func = adapters[lang_code]

                for word in words:
                    # Run adapter
                    adapter_result = run_adapter(adapter_func, word, lang_code)

                    # Get wiktextract match
                    wikt_match = get_wiktextract_match(word, lang_code, wiktextract_data)
                    wikt_match_str = ''
                    if wikt_match:
                        wikt_match_str = f"type={wikt_match.get('morph_type', '')}"
                        if wikt_match.get('derived_from_root'):
                            wikt_match_str += f"|from={wikt_match.get('derived_from_root')}"

                    row = {
                        'synset_id': synset_id,
                        'pos': pos,
                        'definition': definition[:100] + '...' if len(definition) > 100 else definition,
                        'language': lang_code,
                        'word': word,
                        'root': adapter_result['root'],
                        'morph_type': adapter_result['morph_type'],
                        'derivation_info': adapter_result['derivation_info'],
                        'compound_components': adapter_result['compound_components'],
                        'wiktextract_match': wikt_match_str,
                    }
                    rows.append(row)

                    # Count per language
                    lang_row_counts[lang_code] = lang_row_counts.get(lang_code, 0) + 1

            processed_synsets.add(synset_id)
            processed_count += 1

            # Progress and checkpoint every 1,000 concepts
            if processed_count % 1000 == 0:
                log(f"Processed {processed_count:,}/{total_concepts:,} concepts, {len(rows):,} rows so far...")
                # Save checkpoint
                checkpoint = {
                    'processed_synset_ids': list(processed_synsets),
                    'row_count': len(rows),
                    'rows': rows,
                    'lang_row_counts': lang_row_counts,
                }
                with open(CHECKPOINT_PATH, 'wb') as f:
                    pickle.dump(checkpoint, f)

    except Exception as e:
        # Crash handler - save checkpoint and exit
        log(f"\nCRASHED at concept {processed_count} of {total_concepts}. Error: {e}")
        checkpoint = {
            'processed_synset_ids': list(processed_synsets),
            'row_count': len(rows),
            'rows': rows,
            'lang_row_counts': lang_row_counts,
        }
        with open(CHECKPOINT_PATH, 'wb') as f:
            pickle.dump(checkpoint, f)
        log(f"Checkpoint saved with {len(processed_synsets)} concepts completed. Restart to resume.")
        return 1

    log(f"\nTotal rows produced: {len(rows):,}")

    # Write CSV
    log(f"\nWriting to {OUTPUT_CSV_PATH}...")
    os.makedirs(os.path.dirname(OUTPUT_CSV_PATH), exist_ok=True)

    fieldnames = ['synset_id', 'pos', 'definition', 'language', 'word',
                  'root', 'morph_type', 'derivation_info', 'compound_components',
                  'wiktextract_match']

    with open(OUTPUT_CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    file_size = os.path.getsize(OUTPUT_CSV_PATH)
    elapsed = time.time() - start_time

    # Delete checkpoint on successful completion
    if os.path.exists(CHECKPOINT_PATH):
        os.remove(CHECKPOINT_PATH)
        log("Checkpoint deleted (successful completion)")

    # Print statistics
    log("\n" + "=" * 70)
    log("RESULTS")
    log("=" * 70)
    log(f"Total concepts processed: {processed_count:,}")
    log(f"Total rows produced: {len(rows):,}")
    log(f"Output file: {OUTPUT_CSV_PATH}")
    log(f"File size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
    log(f"Processing time: {elapsed:.1f} seconds ({elapsed/3600:.2f} hours)")

    log("\nPer-language row counts:")
    for lang in sorted(lang_row_counts.keys()):
        log(f"  {lang}: {lang_row_counts[lang]:,} rows")

    # Print 5 sample rows
    log("\n" + "=" * 70)
    log("5 SAMPLE ROWS")
    log("=" * 70)
    for i, row in enumerate(rows[:5], 1):
        log(f"\n[{i}] {row['synset_id']} ({row['pos']})")
        log(f"    Lang: {row['language']}, Word: '{row['word']}'")
        log(f"    Root: '{row['root']}', Type: {row['morph_type']}")
        if row['derivation_info']:
            log(f"    Derivation: {row['derivation_info']}")
        if row['compound_components']:
            log(f"    Compound: {row['compound_components']}")
        if row['wiktextract_match']:
            log(f"    Wiktextract: {row['wiktextract_match']}")

    log("\n" + "=" * 70)
    log("FULL PRODUCTION RUN COMPLETE")
    log("=" * 70)
    log(f"End: {datetime.now().isoformat()}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
