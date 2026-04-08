#!/usr/bin/env python3
"""
Comprehensive test of all language adapters after Greek Morpheus wiring.

Expected results:
- ar: roots from CAMeL (already working)
- tr: roots from Zeyrek (already working)
- de: roots from CharSplit (already working)
- en: roots from Wiktextract pkl or spaCy (already working)
- la: roots from Morpheus (already working)
- zh: roots from CEDICT/IDS (already working)
- ja: roots from MeCab (already working)
- grc: roots from Morpheus (NEW - must show non-empty roots)
- he: empty (EXPECTED - awaiting dedicated tool)
- sa: either from pkl or empty (report which and why)
- ine-pro: no translations (EXPECTED)
"""

import os
import pickle
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, '/mnt/pgdata/morphlex')

from pipeline.orchestrator import PipelineOrchestrator

# Test words (Arabic anchor)
TEST_WORDS = [
    'كتب',   # write
    'قلب',   # heart
    'ماء',   # water
    'بيت',   # house
    'يد',    # hand
    'عين',   # eye
    'سمع',   # hear
    'علم',   # proper noun / know
    'كلم',   # speak/word
    'حب',    # love
]

LANGUAGES = ['ar', 'tr', 'de', 'en', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro']

ROOTS_PKL_PATH = '/mnt/pgdata/morphlex/data/wiktextract_roots.pkl'
FORWARD_TRANSLATIONS_PATH = '/mnt/pgdata/morphlex/data/forward_translations.pkl'


def diagnose_sanskrit():
    """Diagnose Sanskrit lookup mismatch."""
    print("\n=== SANSKRIT DIAGNOSTIC ===")

    # Load pkl
    if not os.path.exists(ROOTS_PKL_PATH):
        print("ERROR: wiktextract_roots.pkl not found")
        return

    with open(ROOTS_PKL_PATH, 'rb') as f:
        all_roots = pickle.load(f)

    sa_roots = all_roots.get('sa', {})
    print(f"Sanskrit roots PKL has {len(sa_roots)} entries")

    # Show 5 sample keys
    print("\n5 sample Sanskrit PKL keys:")
    for i, (key, roots) in enumerate(list(sa_roots.items())[:5]):
        print(f"  {i+1}. '{key}' -> {roots}")

    # Load forward translations to see what Sanskrit words we're searching
    if os.path.exists(FORWARD_TRANSLATIONS_PATH):
        with open(FORWARD_TRANSLATIONS_PATH, 'rb') as f:
            translations = pickle.load(f)

        print("\n5 Sanskrit translations from forward_translations (what adapter searches):")
        count = 0
        for ar_word in TEST_WORDS:
            trans = translations.get(ar_word, {})
            sa_word = trans.get('sa')
            if sa_word:
                in_pkl = sa_word in sa_roots
                print(f"  '{ar_word}' -> '{sa_word}' (in PKL: {'YES' if in_pkl else 'NO'})")
                count += 1
                if count >= 5:
                    break

    # Assessment
    print("\nDIAGNOSIS:")
    if len(sa_roots) > 0:
        print(f"  PKL has {len(sa_roots)} Sanskrit entries with roots")
        print("  If adapter returns empty, it's likely a lookup MISMATCH")
        print("  (PKL keys don't match what forward_translations provides)")
    else:
        print("  PKL has NO Sanskrit entries - DATA GAP like Hebrew")


def run_test():
    print(f"=== COMPREHENSIVE LANGUAGE ADAPTER TEST ===")
    print(f"Git HEAD: {os.popen('git rev-parse HEAD').read().strip()}")
    print(f"Start: {datetime.now().isoformat()}")
    print()

    # Run Sanskrit diagnostic first
    diagnose_sanskrit()
    print()

    # Initialize orchestrator
    orchestrator = PipelineOrchestrator()

    total_results = 0
    lang_stats = {lang: {'found': 0, 'empty': 0, 'total': 0} for lang in LANGUAGES}

    print("--- 10-Word Arabic Test ---")
    print(f"Start: {datetime.now().isoformat()}")
    print()

    for arabic_word in TEST_WORDS:
        print(f"Arabic: {arabic_word}")

        for lang in LANGUAGES:
            results = orchestrator.analyze(arabic_word, lang)

            if not results:
                print(f"  {lang}: (no translation)")
                continue

            # Get first root from results
            root = ''
            for r in results:
                if r.get('root'):
                    root = r['root']
                    break

            # Track stats
            lang_stats[lang]['total'] += 1
            if root:
                lang_stats[lang]['found'] += 1
            else:
                lang_stats[lang]['empty'] += 1

            total_results += len(results)

            # Truncate long roots for display
            root_display = root[:30] + '...' if len(root) > 30 else root
            print(f"  {lang}: {len(results)} results (root='{root_display}')")

        print()

    print(f"TOTAL: {total_results} results from {len(TEST_WORDS)} words x {len(LANGUAGES)} languages")
    print(f"End: {datetime.now().isoformat()}")

    # Verification section
    print("\n=== ADAPTER VERIFICATION ===")
    print()

    # Greek verification (should now use Morpheus)
    grc_stats = lang_stats['grc']
    print(f"Greek adapter (NEW - Morpheus wired):")
    print(f"  Found roots: {grc_stats['found']}, Empty: {grc_stats['empty']}")
    if grc_stats['found'] > 0:
        print("  PASS: Greek adapter returns non-empty roots from Morpheus")
    else:
        print("  FAIL: Greek adapter still returns empty roots")
    print()

    # Hebrew verification (expected empty)
    he_stats = lang_stats['he']
    print(f"Hebrew adapter (EXPECTED: empty - awaiting dedicated tool):")
    print(f"  Found roots: {he_stats['found']}, Empty: {he_stats['empty']}")
    if he_stats['empty'] > 0 and he_stats['found'] == 0:
        print("  OK: Hebrew roots empty as expected (coverage 0.07%, 7 entries in pkl)")
    elif he_stats['found'] > 0:
        print("  NOTE: Hebrew found some roots (unexpected but not wrong)")
    print()

    # Sanskrit verification
    sa_stats = lang_stats['sa']
    print(f"Sanskrit adapter:")
    print(f"  Found roots: {sa_stats['found']}, Empty: {sa_stats['empty']}")
    if sa_stats['found'] > 0:
        print("  Result: Sanskrit adapter found roots in pkl")
    else:
        print("  Result: Sanskrit adapter returns empty (lookup mismatch or data gap)")
    print()

    # Arabic verification (not from pkl - CAMeL handles it)
    ar_stats = lang_stats['ar']
    print(f"Arabic adapter (CAMeL - does NOT use pkl):")
    print(f"  Found roots: {ar_stats['found']}, Empty: {ar_stats['empty']}")
    if ar_stats['found'] > 0:
        print("  PASS: Arabic roots from CAMeL working correctly")
    print()

    print("=== ALL TESTS COMPLETE ===")
    print(f"End: {datetime.now().isoformat()}")


if __name__ == '__main__':
    run_test()
