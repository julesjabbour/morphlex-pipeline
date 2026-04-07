#!/usr/bin/env python3
"""
Batch test script for the morphlex pipeline.

Runs 1000 Arabic words through all 11 language adapters and produces:
- batch_1000_v2_test.csv: Full results
- batch_1000_v2_errors.md: Error log
- Stats summary with per-language root fill rate, morph_type distribution, etc.
"""

import csv
import os
import pickle
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, '/mnt/pgdata/morphlex')

from pipeline.orchestrator import PipelineOrchestrator, post_slack_progress
from pipeline.build_forward_translations import build_forward_translations

# Configuration
FORWARD_TRANSLATIONS_PATH = '/mnt/pgdata/morphlex/data/forward_translations.pkl'
REPORTS_DIR = '/mnt/pgdata/morphlex/reports'
PKL_REBUILD_LOG = os.path.join(REPORTS_DIR, 'pkl_rebuild_log.md')
CSV_OUTPUT = os.path.join(REPORTS_DIR, 'batch_1000_v2_test.csv')
ERRORS_OUTPUT = os.path.join(REPORTS_DIR, 'batch_1000_v2_errors.md')

# Languages to test
LANGUAGES = ['ar', 'tr', 'de', 'en', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro']

# CSV columns (including new columns from Problems 2, 3)
CSV_COLUMNS = [
    'concept_id', 'arabic_word', 'language_code', 'word_native', 'lemma', 'root',
    'pos', 'morph_type', 'derived_from_root', 'derivation_mode', 'compound_components',
    'pattern', 'morphological_features', 'confidence', 'source_tool', 'word_translit'
]


def load_forward_translations():
    """Load forward translations pickle."""
    if os.path.exists(FORWARD_TRANSLATIONS_PATH):
        with open(FORWARD_TRANSLATIONS_PATH, 'rb') as f:
            return pickle.load(f)
    return {}


def rebuild_pkl_with_logging():
    """
    Problem 0: Rebuild pkl and save full log.
    """
    print("=== REBUILDING FORWARD TRANSLATIONS PKL ===")
    print(f"Log will be saved to: {PKL_REBUILD_LOG}")

    # Import and run with logging
    result = build_forward_translations(log_path=PKL_REBUILD_LOG)

    # Report results
    if result:
        print(f"\nPKL rebuilt successfully with {len(result)} keys")
    else:
        print("\nPKL rebuild returned no results")

    return result


def run_batch_test(num_words: int = 1000, rebuild_pkl: bool = True):
    """
    Run batch test on specified number of words.

    Args:
        num_words: Number of Arabic words to test
        rebuild_pkl: If True, rebuild pkl first (Problem 0)
    """
    start_time = datetime.now()
    print(f"=== BATCH TEST STARTED ===")
    print(f"Start: {start_time.isoformat()}")
    print(f"Words: {num_words}")
    print(f"Languages: {len(LANGUAGES)}")
    print()

    os.makedirs(REPORTS_DIR, exist_ok=True)

    # Problem 0: Rebuild pkl with logging
    if rebuild_pkl:
        forward_trans = rebuild_pkl_with_logging()
        if not forward_trans:
            print("ERROR: PKL rebuild failed, loading existing file")
            forward_trans = load_forward_translations()
    else:
        forward_trans = load_forward_translations()

    if not forward_trans:
        print("ERROR: No forward translations available")
        return

    print(f"\nForward translations loaded: {len(forward_trans)} Arabic words")

    # Report key count vs expected 18,807
    expected_keys = 18807
    actual_keys = len(forward_trans)
    diff = actual_keys - expected_keys
    print(f"Key count: {actual_keys} (expected: {expected_keys}, diff: {diff:+d})")

    # Get Arabic words to test
    arabic_words = list(forward_trans.keys())[:num_words]
    print(f"Testing {len(arabic_words)} Arabic words across {len(LANGUAGES)} languages")

    # Initialize orchestrator
    orch = PipelineOrchestrator()

    # Track results and errors
    all_rows = []
    errors = []
    stats = {
        'total_results': 0,
        'per_language': defaultdict(lambda: {'count': 0, 'root_filled': 0}),
        'morph_type_dist': Counter(),
        'rows_per_concept': [],
        'exceptions': []
    }

    # Progress tracking
    last_progress_time = time.time()
    progress_interval = 120  # 2 minutes

    print("\n=== PROCESSING ===")

    for concept_id, arabic_word in enumerate(arabic_words):
        concept_rows = 0

        for lang in LANGUAGES:
            try:
                results = orch.analyze(arabic_word, lang)

                for result in results:
                    # Build row
                    row = {
                        'concept_id': concept_id,
                        'arabic_word': arabic_word,
                        'language_code': result.get('language_code', lang),
                        'word_native': result.get('word_native', ''),
                        'lemma': result.get('lemma', ''),
                        'root': result.get('root', ''),
                        'pos': result.get('pos', ''),
                        'morph_type': result.get('morph_type', 'UNKNOWN'),
                        'derived_from_root': result.get('derived_from_root', ''),
                        'derivation_mode': result.get('derivation_mode', ''),
                        'compound_components': str(result.get('compound_components', '')) if result.get('compound_components') else '',
                        'pattern': result.get('pattern', ''),
                        'morphological_features': str(result.get('morphological_features', {})),
                        'confidence': result.get('confidence', 0),
                        'source_tool': result.get('source_tool', ''),
                        'word_translit': result.get('word_translit', '')
                    }
                    all_rows.append(row)
                    concept_rows += 1
                    stats['total_results'] += 1

                    # Track per-language stats
                    stats['per_language'][lang]['count'] += 1
                    if row['root']:
                        stats['per_language'][lang]['root_filled'] += 1

                    # Track morph_type distribution
                    stats['morph_type_dist'][row['morph_type']] += 1

            except Exception as e:
                error_msg = f"Exception for {arabic_word} ({lang}): {type(e).__name__}: {e}"
                errors.append(error_msg)
                stats['exceptions'].append(error_msg)
                print(f"  ERROR: {error_msg}")

        stats['rows_per_concept'].append(concept_rows)

        # Progress output
        if (concept_id + 1) % 100 == 0:
            elapsed = time.time() - start_time.timestamp()
            rate = (concept_id + 1) / elapsed
            print(f"  Processed {concept_id + 1}/{num_words} words, {stats['total_results']} results, {rate:.1f} words/s")

            # Problem 7: Slack progress every 2 minutes
            if time.time() - last_progress_time >= progress_interval:
                progress_pct = ((concept_id + 1) / num_words) * 100
                eta = (num_words - concept_id - 1) / rate if rate > 0 else 0
                msg = (
                    f"Batch test: {concept_id + 1}/{num_words} ({progress_pct:.1f}%) | "
                    f"Results: {stats['total_results']} | "
                    f"ETA: {eta / 60:.1f}min"
                )
                post_slack_progress(msg)
                last_progress_time = time.time()

    # Write CSV
    print(f"\n=== WRITING OUTPUT ===")
    print(f"CSV: {CSV_OUTPUT}")

    with open(CSV_OUTPUT, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Wrote {len(all_rows)} rows to CSV")

    # Write errors
    print(f"Errors: {ERRORS_OUTPUT}")

    with open(ERRORS_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(f"# Batch Test Errors\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write(f"Total errors: {len(errors)}\n\n")
        if errors:
            f.write("## Errors\n\n")
            for error in errors:
                f.write(f"- {error}\n")
        else:
            f.write("No errors encountered.\n")

    print(f"Wrote {len(errors)} errors")

    # Calculate and print stats
    end_time = datetime.now()
    duration = end_time - start_time

    print(f"\n=== STATS SUMMARY ===")
    print(f"Duration: {duration}")
    print(f"Total results: {stats['total_results']}")
    print(f"Total errors: {len(errors)}")

    print(f"\n--- Per-Language Root Fill Rate ---")
    for lang in LANGUAGES:
        lang_stats = stats['per_language'][lang]
        count = lang_stats['count']
        root_filled = lang_stats['root_filled']
        fill_rate = (root_filled / count * 100) if count > 0 else 0
        print(f"  {lang:8s}: {count:5d} results, {root_filled:5d} with root ({fill_rate:5.1f}%)")

    print(f"\n--- Morph Type Distribution ---")
    for morph_type, count in stats['morph_type_dist'].most_common():
        pct = count / stats['total_results'] * 100 if stats['total_results'] > 0 else 0
        print(f"  {morph_type:20s}: {count:5d} ({pct:5.1f}%)")

    print(f"\n--- Rows Per Concept ---")
    if stats['rows_per_concept']:
        avg_rows = sum(stats['rows_per_concept']) / len(stats['rows_per_concept'])
        min_rows = min(stats['rows_per_concept'])
        max_rows = max(stats['rows_per_concept'])
        print(f"  Average: {avg_rows:.1f}")
        print(f"  Min: {min_rows}")
        print(f"  Max: {max_rows}")

    if stats['exceptions']:
        print(f"\n--- Exceptions ({len(stats['exceptions'])}) ---")
        for exc in stats['exceptions'][:10]:  # Show first 10
            print(f"  {exc}")
        if len(stats['exceptions']) > 10:
            print(f"  ... and {len(stats['exceptions']) - 10} more")

    print(f"\n=== BATCH TEST COMPLETE ===")
    print(f"Start: {start_time.isoformat()}")
    print(f"End: {end_time.isoformat()}")
    print(f"Duration: {duration}")

    return stats


if __name__ == '__main__':
    # Default: 1000 words, rebuild pkl
    num_words = 1000
    rebuild = True

    if len(sys.argv) > 1:
        num_words = int(sys.argv[1])
    if len(sys.argv) > 2:
        rebuild = sys.argv[2].lower() in ('true', '1', 'yes')

    run_batch_test(num_words=num_words, rebuild_pkl=rebuild)
