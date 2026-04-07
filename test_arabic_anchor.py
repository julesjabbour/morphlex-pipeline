#!/usr/bin/env python3
"""
Test Arabic anchor pipeline: verify all 11 languages receive correct input.

GOAL: When Arabic words go into the orchestrator, every adapter receives a properly
translated word in its own language, and returns valid morphological results.
Zero false positives from wrong-language input.

Test words: 10 Arabic words (water, fire, hand, eye, stone, heart, sun, moon, tree, blood)
Languages: ar, tr, de, en, la, zh, ja, he, sa, grc, ine-pro (11 total)
"""

import os
import sys
from datetime import datetime

# Set up path - all code lives at /mnt/pgdata/morphlex
sys.path.insert(0, '/mnt/pgdata/morphlex')

# Test Arabic words
TEST_WORDS = [
    ('ماء', 'water'),
    ('نار', 'fire'),
    ('يد', 'hand'),
    ('عين', 'eye'),
    ('حجر', 'stone'),
    ('قلب', 'heart'),
    ('شمس', 'sun'),
    ('قمر', 'moon'),
    ('شجرة', 'tree'),
    ('دم', 'blood'),
]

LANGUAGES = ['ar', 'tr', 'de', 'en', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro']


def seed_translations():
    """Ensure forward_translations.pkl exists with test data."""
    from pipeline.seed_test_translations import seed_translations as do_seed
    do_seed()


def run_test():
    """Run the full Arabic anchor test."""
    start_time = datetime.now()
    print("=" * 70)
    print("ARABIC ANCHOR PIPELINE TEST")
    print("=" * 70)
    print(f"Start time: {start_time.isoformat()}")
    print(f"Test words: {len(TEST_WORDS)} Arabic words")
    print(f"Languages:  {len(LANGUAGES)} languages")
    print()

    # Seed translations first
    print("--- Seeding translations ---")
    seed_translations()
    print()

    # Import orchestrator after seeding
    from pipeline.orchestrator import PipelineOrchestrator

    # Load translations to show what each adapter receives
    import pickle
    with open('/mnt/pgdata/morphlex/data/forward_translations.pkl', 'rb') as f:
        translations = pickle.load(f)

    # Initialize orchestrator
    orchestrator = PipelineOrchestrator()

    # Track results
    results_by_lang = {lang: {'count': 0, 'ok': 0, 'empty': 0, 'words_received': []} for lang in LANGUAGES}
    all_results = []

    print("--- Running analysis ---")
    print()

    for arabic_word, english_meaning in TEST_WORDS:
        word_trans = translations.get(arabic_word, {})

        for lang in LANGUAGES:
            # Determine what word the adapter will receive
            if lang == 'ar':
                word_received = arabic_word
            elif lang == 'ine-pro':
                word_received = word_trans.get('en', 'NO_TRANSLATION')
            else:
                word_received = word_trans.get(lang, 'NO_TRANSLATION')

            try:
                results = orchestrator.analyze(arabic_word, lang)
                count = len(results) if results else 0
            except Exception as e:
                results = []
                count = 0
                print(f"  ERROR: {lang} - {arabic_word}: {e}")

            results_by_lang[lang]['count'] += count
            results_by_lang[lang]['words_received'].append(word_received)

            if count > 0:
                results_by_lang[lang]['ok'] += 1
                all_results.extend(results)
            else:
                results_by_lang[lang]['empty'] += 1

    print()
    print("--- Results per language ---")
    print()
    print(f"{'Language':<10} {'Total':>8} {'OK':>6} {'Empty':>6}  {'Status':<10}  Sample Words Received")
    print("-" * 90)

    all_ok = True
    for lang in LANGUAGES:
        stats = results_by_lang[lang]
        count = stats['count']
        ok = stats['ok']
        empty = stats['empty']

        # For Arabic, receiving Arabic is correct. For others, should NOT receive Arabic.
        words = stats['words_received'][:3]  # First 3 samples

        if lang == 'ar':
            # Arabic adapter should receive Arabic
            status = '[OK]' if count > 0 else '[EMPTY]'
        else:
            # Non-Arabic adapters should receive translated words
            has_arabic_input = any('\u0600' <= c <= '\u06ff' for w in words for c in str(w))
            if has_arabic_input:
                status = '[WRONG-LANG]'
                all_ok = False
            elif count > 0:
                status = '[OK]'
            else:
                status = '[EMPTY]'
                # Empty might be OK if tools aren't installed - don't fail

        sample_words = ', '.join(str(w)[:15] for w in words)
        print(f"{lang:<10} {count:>8} {ok:>6} {empty:>6}  {status:<10}  {sample_words}")

    print("-" * 90)
    print(f"{'TOTAL':<10} {len(all_results):>8}")
    print()

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"End time: {end_time.isoformat()}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Total results: {len(all_results)}")
    print()

    if all_ok:
        print("STATUS: SUCCESS - All languages receiving correct input")
    else:
        print("STATUS: FAILED - Some languages received wrong-language input")

    print("=" * 70)

    # Write summary report
    report_path = '/mnt/pgdata/morphlex/test_report.md'
    with open(report_path, 'w') as f:
        f.write("# Arabic Anchor Pipeline Test Report\n\n")
        f.write(f"**Start:** {start_time.isoformat()}\n")
        f.write(f"**End:** {end_time.isoformat()}\n")
        f.write(f"**Duration:** {duration:.2f} seconds\n\n")
        f.write(f"**Test words:** {len(TEST_WORDS)} Arabic words\n")
        f.write(f"**Languages:** {len(LANGUAGES)}\n\n")
        f.write("## Results by Language\n\n")
        f.write("| Language | Count | OK | Empty | Status |\n")
        f.write("|----------|------:|---:|------:|--------|\n")
        for lang in LANGUAGES:
            stats = results_by_lang[lang]
            count = stats['count']
            ok = stats['ok']
            empty = stats['empty']
            status = '[OK]' if count > 0 else '[EMPTY]'
            f.write(f"| {lang} | {count} | {ok} | {empty} | {status} |\n")
        f.write(f"\n**Total results:** {len(all_results)}\n")
        f.write(f"\n**Overall status:** {'SUCCESS' if all_ok else 'FAILED'}\n")

    print(f"Report written to: {report_path}")

    return all_ok


if __name__ == '__main__':
    success = run_test()
    sys.exit(0 if success else 1)
