#!/bin/bash
# Task: Phase 1-2 Verification Tests
# Tests: PIE asterisk fix, root fallback fix, schema columns, wiktextract root extraction
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== PHASE 1-2 VERIFICATION TESTS ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# First sync the code
echo "--- Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

# Apply schema changes (Phase 1.2)
echo "--- Phase 1.2: Applying schema changes ---"
PGPASSWORD=morphlex_2026 psql -h localhost -U morphlex_user -d morphlex -c "
ALTER TABLE lexicon.entries ADD COLUMN IF NOT EXISTS morph_type VARCHAR(20);
ALTER TABLE lexicon.entries ADD COLUMN IF NOT EXISTS derived_from_root TEXT;
ALTER TABLE lexicon.entries ADD COLUMN IF NOT EXISTS derivation_mode VARCHAR(50);
"
echo "Verifying columns exist:"
PGPASSWORD=morphlex_2026 psql -h localhost -U morphlex_user -d morphlex -c "\d lexicon.entries" | grep -E "(morph_type|derived_from_root|derivation_mode)"
echo ""

# Test Phase 1.1: PIE asterisk fix
echo "--- Phase 1.1: PIE Asterisk Fix Test ---"
python3 << 'PYTEST_PIE'
from analyzers.pie import analyze_pie

# Test words known to have PIE etymologies
test_words = ['water', 'mother', 'father', 'brother', 'sister']
asterisk_count = 0
no_asterisk_count = 0

print("PIE root extraction test:")
for word in test_words:
    results = analyze_pie(word)
    for r in results:
        root = r.get('root', '')
        has_asterisk = root.startswith('*')
        if has_asterisk:
            asterisk_count += 1
        else:
            no_asterisk_count += 1
        print(f"  {word} -> root='{root}' {'[FAIL: has asterisk]' if has_asterisk else '[OK]'}")

print(f"\nSummary: {no_asterisk_count} without asterisk, {asterisk_count} with asterisk")
if asterisk_count == 0:
    print("PASS: PIE roots no longer have asterisk prefix")
else:
    print("FAIL: Some PIE roots still have asterisk prefix")
PYTEST_PIE
echo ""

# Test Phase 1.3: Root fallback returns '' not normalized word
echo "--- Phase 1.3: Root Fallback Test ---"
python3 << 'PYTEST_FALLBACK'
from analyzers.hebrew import analyze_hebrew, _extract_hebrew_root
from analyzers.sanskrit import analyze_sanskrit, _extract_sanskrit_root
from analyzers.greek import analyze_greek, _extract_greek_root

# Test with made-up words that won't have etymology entries
test_cases = [
    ('hebrew', 'בדיקה123', analyze_hebrew, _extract_hebrew_root),
    ('sanskrit', 'परीक्षा123', analyze_sanskrit, _extract_sanskrit_root),
    ('greek', 'δοκιμή123', analyze_greek, _extract_greek_root),
]

print("Testing root fallback behavior:")
print("(When etymology lookup fails, adapters should return '' not the normalized word)")
print()

all_pass = True
for lang, test_word, analyze_fn, extract_fn in test_cases:
    # Test the extract function directly with empty etymology
    root = extract_fn(test_word, []) if lang != 'greek' else extract_fn(test_word, {})

    if root == '':
        print(f"  {lang}: _extract_{lang}_root('{test_word}', []) -> '' [OK]")
    else:
        print(f"  {lang}: _extract_{lang}_root('{test_word}', []) -> '{root}' [FAIL: should be '']")
        all_pass = False

print()
if all_pass:
    print("PASS: All adapters return '' when no etymology root found")
else:
    print("FAIL: Some adapters still return normalized word as fallback")
PYTEST_FALLBACK
echo ""

# Run Phase 2: Extract Wiktextract roots
echo "--- Phase 2: Extract Wiktextract Roots ---"
echo "Running extract_wiktextract_roots.py..."
python3 pipeline/extract_wiktextract_roots.py
echo ""

# Check if wiktextract_roots.pkl was created
if [ -f data/wiktextract_roots.pkl ]; then
    echo "wiktextract_roots.pkl created successfully"
    ls -lh data/wiktextract_roots.pkl
else
    echo "ERROR: wiktextract_roots.pkl not created"
fi
echo ""

# Run 10-word Arabic test
echo "--- 10-Word Arabic Test ---"
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

# 10 Arabic test words
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
            print(f"  {lang}: {count} results (root='{sample_root[:20]}...' if len(sample_root) > 20 else sample_root)")
        except Exception as e:
            print(f"  {lang}: ERROR - {e}")
    print()

print(f"TOTAL: {total_results} results from 10 words x 11 languages")
print(f"End: {datetime.now().isoformat()}")
PYTEST_ARABIC
echo ""

echo "=== ALL TESTS COMPLETE ==="
echo "End: $(date -Iseconds)"
