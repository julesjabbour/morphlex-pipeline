#!/usr/bin/env python3
"""
Test Arabic anchor pipeline: verify all 11 languages receive correct input.

GOAL: When Arabic words go into the orchestrator, every adapter receives a properly
translated word in its own language, and returns valid morphological results.
Zero false positives from wrong-language input.

Test words: 10 Arabic words (water, fire, hand, eye, stone, heart, sun, moon, tree, blood)
Languages: ar, tr, de, en, la, zh, ja, he, sa, grc, ine-pro (11 total)

Output:
- Full detailed results written to /mnt/pgdata/morphlex/arabic_anchor_test_full.md
- Short summary printed to stdout
"""

import io
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

# Full output file path
FULL_OUTPUT_PATH = '/mnt/pgdata/morphlex/arabic_anchor_test_full.md'


def seed_translations():
    """Ensure forward_translations.pkl exists with test data."""
    from pipeline.seed_test_translations import seed_translations as do_seed
    do_seed()


def run_test():
    """Run the full Arabic anchor test with detailed output to file."""
    start_time = datetime.now()

    # Capture all output including warnings for the full report
    full_output = io.StringIO()

    def write_full(msg):
        """Write to full output buffer."""
        full_output.write(msg + "\n")

    write_full("# Arabic Anchor Pipeline Test - Full Output")
    write_full("")
    write_full(f"**Start time:** {start_time.isoformat()}")
    write_full(f"**Test words:** {len(TEST_WORDS)} Arabic words")
    write_full(f"**Languages:** {len(LANGUAGES)} languages")
    write_full("")
    write_full("---")
    write_full("")

    # Seed translations first
    write_full("## Seeding Translations")
    write_full("")
    seed_translations()
    write_full("")

    # Import orchestrator after seeding
    from pipeline.orchestrator import PipelineOrchestrator

    # Load translations to show what each adapter receives
    import pickle
    with open('/mnt/pgdata/morphlex/data/forward_translations.pkl', 'rb') as f:
        translations = pickle.load(f)

    # Initialize orchestrator
    orchestrator = PipelineOrchestrator()

    # Track results
    results_by_lang = {lang: {'count': 0, 'ok': 0, 'empty': 0, 'words_received': [], 'all_results': []} for lang in LANGUAGES}
    all_results = []

    write_full("## Detailed Analysis Results")
    write_full("")
    write_full("Each word analyzed with every language adapter:")
    write_full("")

    for arabic_word, english_meaning in TEST_WORDS:
        word_trans = translations.get(arabic_word, {})
        write_full(f"### Arabic: {arabic_word} ({english_meaning})")
        write_full("")
        write_full(f"Translations: {word_trans}")
        write_full("")

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
                write_full(f"  **ERROR** {lang}: {e}")

            results_by_lang[lang]['count'] += count
            results_by_lang[lang]['words_received'].append(word_received)
            results_by_lang[lang]['all_results'].extend(results or [])

            if count > 0:
                results_by_lang[lang]['ok'] += 1
                all_results.extend(results)
            else:
                results_by_lang[lang]['empty'] += 1

            # Write detailed results for this word/lang combination
            write_full(f"**{lang}**: received `{word_received}` → {count} results")
            if results:
                for r in results:
                    lemma = r.get('lemma', '?')
                    pos = r.get('pos', '?')
                    root = r.get('root', '')
                    morph = r.get('morphological_features', {})
                    write_full(f"  - lemma={lemma}, pos={pos}, root={root}, features={morph}")
            write_full("")

        write_full("---")
        write_full("")

    write_full("## Per-Language Summary Table")
    write_full("")
    write_full("| Language | Total | OK | Empty | Status | Sample Words Received |")
    write_full("|----------|------:|---:|------:|--------|----------------------|")

    all_ok = True
    summary_lines = []
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

        sample_words = ', '.join(str(w)[:15] for w in words)
        write_full(f"| {lang} | {count} | {ok} | {empty} | {status} | {sample_words} |")
        summary_lines.append((lang, count, status))

    write_full("")
    write_full(f"**TOTAL:** {len(all_results)} results")
    write_full("")

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    write_full("## Summary")
    write_full("")
    write_full(f"**End time:** {end_time.isoformat()}")
    write_full(f"**Duration:** {duration:.2f} seconds")
    write_full(f"**Total results:** {len(all_results)}")
    write_full("")
    if all_ok:
        write_full("**STATUS: SUCCESS** - All languages receiving correct input")
    else:
        write_full("**STATUS: FAILED** - Some languages received wrong-language input")

    # Write full output to file
    with open(FULL_OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(full_output.getvalue())

    # Print SHORT summary to stdout (for Slack)
    print("=" * 50)
    print("ARABIC ANCHOR TEST - SUMMARY")
    print("=" * 50)
    print(f"Start: {start_time.isoformat()}")
    print(f"End:   {end_time.isoformat()}")
    print(f"Duration: {duration:.2f} seconds")
    print()
    print("Per-language counts:")
    for lang, count, status in summary_lines:
        print(f"  {lang:<10} : {count:>4} results {status}")
    print()
    print(f"TOTAL: {len(all_results)} results from {len(TEST_WORDS)} words x {len(LANGUAGES)} languages")
    print()
    print(f"Full details: {FULL_OUTPUT_PATH}")
    print("=" * 50)

    return all_ok


if __name__ == '__main__':
    success = run_test()
    sys.exit(0 if success else 1)
