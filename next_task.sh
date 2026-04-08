#!/bin/bash
# Task: Unified Fix for 3 Interconnected Bugs
# A. Extraction: Apply PIE filter only to he/sa/ar, not globally (restores grc)
# B. PIE contamination: Filter PIE roots for Hebrew/Sanskrit/Arabic only
# C. Adapter lookup: Add normalized lookup tables to he/grc/sa adapters
# Timestamp: 2026-04-08T-unified-fix
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== UNIFIED BUG FIX VERIFICATION ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# First sync the code
echo "--- Step 1: Syncing code from origin/main ---"
git fetch origin && git reset --hard origin/main
echo "Now at: $(git rev-parse HEAD)"
echo ""

# Re-extract roots with fixed script
echo "--- Step 2: Re-extracting Wiktextract roots ---"
echo "Expected: en>=10K, de>=400, grc>=2K, tr>=2.5K, la>=2K, sa>=1K, he>0, ar>0"
echo ""
python3 pipeline/extract_wiktextract_roots.py

if [ -f data/wiktextract_roots.pkl ]; then
    echo ""
    echo "wiktextract_roots.pkl regenerated successfully"
    ls -lh data/wiktextract_roots.pkl
else
    echo "ERROR: wiktextract_roots.pkl not created"
    exit 1
fi
echo ""

# Verify extraction counts
echo "--- Step 3: Verifying extraction counts against baseline ---"
python3 << 'VERIFY_COUNTS'
import pickle
import sys

with open('data/wiktextract_roots.pkl', 'rb') as f:
    roots = pickle.load(f)

# Baseline counts from commit 3369cdd
baseline = {
    'en': 10000,  # was 10,138
    'de': 400,    # was 402
    'grc': 2000,  # was 2,341
    'tr': 2500,   # was 2,734
    'la': 2000,   # was 2,095
    'sa': 1000,   # was 1,482
    'he': 1,      # any count > 0
    'ar': 1,      # any count > 0
}

print("Extraction count verification:")
print("-" * 40)
all_pass = True
for lang, min_count in baseline.items():
    actual = len(roots.get(lang, {}))
    status = "PASS" if actual >= min_count else "FAIL"
    if status == "FAIL":
        all_pass = False
    print(f"  {lang}: {actual:,} (min: {min_count:,}) [{status}]")

print("-" * 40)
if all_pass:
    print("EXTRACTION: ALL COUNTS PASS")
else:
    print("EXTRACTION: SOME COUNTS BELOW BASELINE")
    print("WARNING: Fix required before proceeding")
VERIFY_COUNTS
echo ""

# Show Hebrew PKL keys vs adapter lookup
echo "--- Step 4: Hebrew PKL keys vs adapter lookup (Problem C debug) ---"
python3 << 'HEBREW_DEBUG'
import pickle
import unicodedata

def normalize_hebrew(word):
    normalized = ''.join(
        c for c in unicodedata.normalize('NFD', word)
        if unicodedata.category(c) != 'Mn'
    )
    return normalized.strip()

# Load roots PKL
with open('data/wiktextract_roots.pkl', 'rb') as f:
    roots = pickle.load(f)
he_roots = roots.get('he', {})

# Load forward translations
with open('data/forward_translations.pkl', 'rb') as f:
    fwd = pickle.load(f)

print(f"Hebrew roots PKL has {len(he_roots)} entries")
print()

if he_roots:
    print("5 sample Hebrew PKL keys:")
    for i, key in enumerate(list(he_roots.keys())[:5]):
        roots_list = he_roots[key]
        norm = normalize_hebrew(key)
        print(f"  {i+1}. '{key}' (normalized: '{norm}') -> {roots_list[:2]}")
    print()

# Show what adapter searches for
print("5 Hebrew words from forward_translations (what adapter searches):")
count = 0
for ar_word, trans in fwd.items():
    he_word = trans.get('he', '')
    if he_word and count < 5:
        in_pkl = "YES" if he_word in he_roots else "NO"
        norm = normalize_hebrew(he_word)
        norm_in_pkl = "YES" if any(normalize_hebrew(k) == norm for k in he_roots) else "NO"
        print(f"  {count+1}. '{he_word}' (in PKL direct: {in_pkl}, normalized: {norm_in_pkl})")
        count += 1
HEBREW_DEBUG
echo ""

# Run 10-word Arabic test
echo "--- Step 5: 10-Word Arabic Test ---"
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

# Track bugs
hebrew_pie_roots = []
sanskrit_pie_roots = []
greek_empty = 0
greek_found = 0
hebrew_empty = 0
hebrew_found = 0

def is_pie_root(root):
    """Check if a root is a PIE reconstruction."""
    if not root:
        return False
    return root.startswith('*')

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
            if lang == 'he':
                if is_pie_root(sample_root):
                    hebrew_pie_roots.append((ar_word, sample_root))
                elif sample_root:
                    hebrew_found += 1
                else:
                    hebrew_empty += 1
            if lang == 'sa' and is_pie_root(sample_root):
                sanskrit_pie_roots.append((ar_word, sample_root))
            if lang == 'grc':
                if sample_root:
                    greek_found += 1
                else:
                    greek_empty += 1

            # Format root display
            root_display = sample_root[:20] + '...' if len(sample_root) > 20 else sample_root
            print(f"  {lang}: {count} results (root='{root_display}')")

        except Exception as e:
            print(f"  {lang}: ERROR - {e}")
    print()

print(f"TOTAL: {total_results} results from 10 words x 11 languages")
print(f"End: {datetime.now().isoformat()}")
print()

# Bug verification summary
print("=== BUG FIX VERIFICATION ===")
print()

print("Bug A - Hebrew/Sanskrit PIE contamination:")
if hebrew_pie_roots:
    print(f"  FAIL: Hebrew has {len(hebrew_pie_roots)} PIE roots:")
    for word, root in hebrew_pie_roots[:3]:
        print(f"    {word}: {root}")
else:
    print("  PASS: Hebrew roots are NOT PIE reconstructions")

if sanskrit_pie_roots:
    print(f"  FAIL: Sanskrit has {len(sanskrit_pie_roots)} PIE roots:")
    for word, root in sanskrit_pie_roots[:3]:
        print(f"    {word}: {root}")
else:
    print("  PASS: Sanskrit roots are NOT PIE reconstructions")
print()

print("Bug B - Greek extraction regression:")
print(f"  Greek adapter: found={greek_found}, empty={greek_empty}")
if greek_found > 0:
    print("  PASS: Greek adapter finds roots (was: grc=0)")
else:
    print("  FAIL: Greek adapter still returns empty roots")
print()

print("Bug C - Hebrew adapter lookup mismatch:")
print(f"  Hebrew adapter: found={hebrew_found}, empty={hebrew_empty}")
if hebrew_found > 0:
    print("  PASS: Hebrew adapter finds roots via normalized lookup")
else:
    print("  FAIL: Hebrew adapter can't find roots despite data in pkl")
print()
PYTEST_ARABIC

echo ""
echo "=== ALL TESTS COMPLETE ==="
echo "End: $(date -Iseconds)"
