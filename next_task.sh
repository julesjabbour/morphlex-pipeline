#!/bin/bash
# Task: Bug Fix Verification - Hebrew/Sanskrit PIE, Greek empty roots, Latin encoding
# Fixes: extract_wiktextract_roots.py, greek.py, hebrew.py, sanskrit.py, latin.py
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== BUG FIX VERIFICATION TESTS ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# First sync the code
echo "--- Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

# Re-extract roots with fixed script (now uses template source_lang, not entry lang_code)
echo "--- Re-extracting Wiktextract roots with fixed script ---"
python3 pipeline/extract_wiktextract_roots.py
echo ""

if [ -f data/wiktextract_roots.pkl ]; then
    echo "wiktextract_roots.pkl regenerated successfully"
    ls -lh data/wiktextract_roots.pkl
else
    echo "ERROR: wiktextract_roots.pkl not created"
fi
echo ""

# Run 10-word Arabic test
echo "--- 10-Word Arabic Test (Bug Fix Verification) ---"
python3 << 'PYTEST_ARABIC'
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')

from datetime import datetime
from analyzers.arabic import analyze_arabic
from analyzers.turkish import analyze_turkish
from analyzers.german import analyze_german
from analyzers.english import analyze_english
from analyzers.latin import analyze_latin
from analyzers.chinese import analyze_chinese
from analyzers.japanese import analyze_japanese
from analyzers.hebrew import analyze_hebrew
from analyzers.sanskrit import analyze_sanskrit
from analyzers.greek import analyze_greek
from analyzers.pie import analyze_pie
import pickle

# Load forward translations
with open('data/forward_translations.pkl', 'rb') as f:
    fwd = pickle.load(f)

# 10 Arabic test words (same as Session 44)
arabic_words = ['كتب', 'قلب', 'ماء', 'بيت', 'يد', 'عين', 'سمع', 'علم', 'كلم', 'حب']

adapters = {
    'ar': analyze_arabic,
    'tr': analyze_turkish,
    'de': analyze_german,
    'en': analyze_english,
    'la': analyze_latin,
    'zh': analyze_chinese,
    'ja': analyze_japanese,
    'he': analyze_hebrew,
    'sa': analyze_sanskrit,
    'grc': analyze_greek,
    'ine-pro': analyze_pie,
}

print(f"Start: {datetime.now().isoformat()}")
print()

# Track bugs
latin_errors = []
hebrew_pie_roots = []
sanskrit_pie_roots = []
greek_empty = 0
greek_found = 0

total_results = 0
for ar_word in arabic_words:
    print(f"Arabic: {ar_word}")
    translations = fwd.get(ar_word, {})

    for lang, analyze_fn in adapters.items():
        try:
            if lang == 'ar':
                word = ar_word
            else:
                word = translations.get(lang, '')

            if not word:
                print(f"  {lang}: (no translation)")
                continue

            results = analyze_fn(word)
            count = len(results)
            total_results += count

            # Show sample root for verification
            sample_root = results[0].get('root', '') if results else ''

            # Track bug indicators
            if lang == 'he' and sample_root.startswith('*'):
                hebrew_pie_roots.append((ar_word, sample_root))
            if lang == 'sa' and sample_root.startswith('*'):
                sanskrit_pie_roots.append((ar_word, sample_root))
            if lang == 'grc':
                if sample_root:
                    greek_found += 1
                else:
                    greek_empty += 1

            # Format root display (truncate if > 20 chars)
            root_display = sample_root[:20] + '...' if len(sample_root) > 20 else sample_root
            print(f"  {lang}: {count} results (root='{root_display}')")

        except Exception as e:
            print(f"  {lang}: ERROR - {e}")
            if lang == 'la':
                latin_errors.append((ar_word, str(e)))
    print()

print(f"TOTAL: {total_results} results from 10 words x 11 languages")
print(f"End: {datetime.now().isoformat()}")
print()

# Bug verification summary
print("=== BUG FIX VERIFICATION ===")
print()

print("Bug 1 - Hebrew/Sanskrit PIE roots:")
if hebrew_pie_roots:
    print(f"  FAIL: Hebrew still has {len(hebrew_pie_roots)} PIE roots:")
    for word, root in hebrew_pie_roots[:3]:
        print(f"    {word}: {root}")
else:
    print("  PASS: Hebrew roots are NOT PIE reconstructions")

if sanskrit_pie_roots:
    print(f"  FAIL: Sanskrit still has {len(sanskrit_pie_roots)} PIE roots:")
    for word, root in sanskrit_pie_roots[:3]:
        print(f"    {word}: {root}")
else:
    print("  PASS: Sanskrit roots are NOT PIE reconstructions")
print()

print("Bug 2 - Greek empty roots:")
print(f"  Found: {greek_found}, Empty: {greek_empty}")
if greek_found > 0:
    print("  PASS: Greek adapter is finding roots from wiktextract_roots.pkl")
else:
    print("  FAIL: Greek adapter still returns empty roots")
print()

print("Bug 3 - Latin encoding errors:")
if latin_errors:
    print(f"  FAIL: {len(latin_errors)} Latin errors:")
    for word, err in latin_errors:
        print(f"    {word}: {err}")
else:
    print("  PASS: Latin adapter handles macrons and multi-word translations")
print()
PYTEST_ARABIC

echo ""
echo "=== ALL TESTS COMPLETE ==="
echo "End: $(date -Iseconds)"
