#!/bin/bash
# DIAGNOSE PKL KEY MISMATCH AND FIX
# The pkl has 19,948 keys but test words don't match - likely Arabic diacritics issue
#
# Usage: bash next_task.sh
# Working directory: /mnt/pgdata/morphlex

set -e

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== DIAGNOSE PKL KEY MISMATCH ==="
echo "Start: $(date -Iseconds)"
echo ""

# Part 1: Diagnose the key mismatch
python3 << 'PYEOF'
import pickle
import unicodedata
import re
import os

PKL_PATH = '/mnt/pgdata/morphlex/data/forward_translations.pkl'

print("=" * 60)
print("DIAGNOSTIC: PKL KEY ANALYSIS")
print("=" * 60)

# Test words (plain Arabic without diacritics)
test_words = ['ماء', 'نار', 'يد', 'عين', 'حجر', 'قلب', 'شمس', 'قمر', 'شجرة', 'دم']

# Arabic tashkeel (diacritics) range: U+064B to U+065F plus U+0670
ARABIC_DIACRITICS = re.compile(r'[\u064B-\u065F\u0670]')

def strip_arabic_diacritics(text):
    """Remove Arabic tashkeel/diacritics."""
    return ARABIC_DIACRITICS.sub('', text)

def show_codepoints(s):
    """Show Unicode codepoints for a string."""
    return ' '.join(f'U+{ord(c):04X}' for c in s)

# Load pkl
with open(PKL_PATH, 'rb') as f:
    translations = pickle.load(f)

print(f"Total keys in pkl: {len(translations):,}")
print()

# Sample first 20 keys
keys_list = list(translations.keys())[:30]
print("First 30 pkl keys:")
for i, k in enumerate(keys_list, 1):
    has_diacritics = bool(ARABIC_DIACRITICS.search(k))
    stripped = strip_arabic_diacritics(k)
    diac_note = " [HAS DIACRITICS]" if has_diacritics else ""
    print(f"  {i:2}. '{k}' -> stripped: '{stripped}'{diac_note}")

print()
print("=" * 60)
print("TEST WORD LOOKUP ATTEMPTS")
print("=" * 60)
print()

# Try to find test words
for word in test_words:
    # Direct lookup
    found_direct = word in translations

    # Try to find keys that match when stripped
    matches = []
    for k in translations.keys():
        if strip_arabic_diacritics(k) == word:
            matches.append(k)

    print(f"Test word: '{word}' ({show_codepoints(word)})")
    print(f"  Direct lookup: {'FOUND' if found_direct else 'NOT FOUND'}")
    if matches:
        print(f"  Matches when stripped ({len(matches)}):")
        for m in matches[:3]:
            print(f"    - '{m}' ({show_codepoints(m)})")
            trans = translations[m]
            print(f"      Translations: en={trans.get('en', 'N/A')}, de={trans.get('de', 'N/A')}")
    else:
        print(f"  No matches even when stripping diacritics")
    print()

# Count keys with diacritics
keys_with_diacritics = sum(1 for k in translations.keys() if ARABIC_DIACRITICS.search(k))
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Keys WITH Arabic diacritics: {keys_with_diacritics:,}")
print(f"Keys WITHOUT diacritics: {len(translations) - keys_with_diacritics:,}")
print()

if keys_with_diacritics > len(translations) * 0.5:
    print("DIAGNOSIS: Majority of pkl keys have Arabic diacritics (tashkeel).")
    print("FIX NEEDED: Strip diacritics when building pkl keys.")
else:
    print("DIAGNOSIS: Keys don't have significant diacritics.")
    print("Need further investigation...")
PYEOF

echo ""
echo "=" * 60
echo "Now fixing the build script and rebuilding..."
echo "=" * 60
echo ""

# Part 2: Fix the build script to strip Arabic diacritics
python3 << 'PYEOF'
import gzip
import json
import os
import pickle
import re

RAW_WIKTEXTRACT_PATH = "/mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz"
OUTPUT_PATH = "/mnt/pgdata/morphlex/data/forward_translations.pkl"
TARGET_LANGUAGES = ['en', 'tr', 'de', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro']

# Arabic diacritics (tashkeel) to strip from keys
ARABIC_DIACRITICS = re.compile(r'[\u064B-\u065F\u0670]')

def strip_arabic_diacritics(text):
    """Remove Arabic tashkeel/diacritics for consistent key lookup."""
    return ARABIC_DIACRITICS.sub('', text)

def _valid_script(lang, word):
    if lang == 'zh':
        return any('\u4e00' <= c <= '\u9fff' for c in word)
    elif lang == 'he':
        return any('\u0590' <= c <= '\u05ff' for c in word)
    elif lang == 'ja':
        return any(('\u3040' <= c <= '\u30ff') or ('\u4e00' <= c <= '\u9fff') for c in word)
    elif lang == 'sa':
        return any('\u0900' <= c <= '\u097f' for c in word)
    elif lang == 'grc':
        return any(('\u0370' <= c <= '\u03ff') or ('\u1f00' <= c <= '\u1fff') for c in word)
    elif lang == 'ar':
        return any('\u0600' <= c <= '\u06ff' for c in word)
    return True

def _extract_translations_from_entry(entry):
    translations = entry.get('translations', [])
    if not translations or not isinstance(translations, list):
        return {}
    result = {}
    for trans in translations:
        if not isinstance(trans, dict):
            continue
        lang_code = trans.get('lang_code', trans.get('code', ''))
        trans_word = trans.get('word', '').strip()
        if not lang_code or not trans_word or trans_word == '-':
            continue
        if not _valid_script(lang_code, trans_word):
            continue
        if lang_code not in result:
            result[lang_code] = trans_word
    return result

print("=== REBUILDING FORWARD TRANSLATIONS (with diacritic-stripped keys) ===")
print(f"Input: {RAW_WIKTEXTRACT_PATH}")
print(f"Output: {OUTPUT_PATH}")
print()

forward_translations = {}
line_count = 0
entries_with_arabic = 0

print("Streaming Wiktextract dump...")

with gzip.open(RAW_WIKTEXTRACT_PATH, 'rt', encoding='utf-8') as f:
    for line in f:
        line_count += 1
        if line_count % 500000 == 0:
            print(f"  Processed {line_count:,} lines, {entries_with_arabic:,} entries...")

        try:
            entry = json.loads(line.strip())
        except json.JSONDecodeError:
            continue

        if entry.get('lang_code') != 'en':
            continue

        english_word = entry.get('word', '').strip()
        if not english_word:
            continue

        all_trans = _extract_translations_from_entry(entry)
        arabic_word_raw = all_trans.get('ar')
        if not arabic_word_raw:
            continue

        if not _valid_script('ar', arabic_word_raw):
            continue

        # KEY FIX: Strip Arabic diacritics from the key
        arabic_word = strip_arabic_diacritics(arabic_word_raw).strip()
        if not arabic_word:
            continue

        entries_with_arabic += 1

        if arabic_word not in forward_translations:
            forward_translations[arabic_word] = {}

        # Add English word
        if 'en' not in forward_translations[arabic_word]:
            forward_translations[arabic_word]['en'] = english_word

        # Add other translations
        for lang_code in TARGET_LANGUAGES:
            if lang_code == 'en':
                continue
            if lang_code in all_trans and lang_code not in forward_translations[arabic_word]:
                forward_translations[arabic_word][lang_code] = all_trans[lang_code]

print(f"\nProcessed {line_count:,} lines")
print(f"English entries with Arabic: {entries_with_arabic:,}")
print(f"Unique Arabic words (diacritics stripped): {len(forward_translations):,}")

# Stats per language
print("\nPer-language coverage:")
lang_counts = {lang: 0 for lang in TARGET_LANGUAGES}
for word_trans in forward_translations.values():
    for lang in word_trans:
        if lang in lang_counts:
            lang_counts[lang] += 1

for lang in TARGET_LANGUAGES:
    print(f"  {lang}: {lang_counts[lang]:,}")

# Save
print(f"\nSaving to {OUTPUT_PATH}...")
with open(OUTPUT_PATH, 'wb') as f:
    pickle.dump(forward_translations, f)

file_size = os.path.getsize(OUTPUT_PATH)
print(f"Saved: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
print(f"Total Arabic words: {len(forward_translations):,}")
PYEOF

echo ""
echo "=" * 60
echo "Verifying test words are now found..."
echo "=" * 60
echo ""

# Part 3: Quick verification (NO heavy ML models to avoid OOM)
python3 << 'PYEOF'
import pickle
import os

PKL_PATH = '/mnt/pgdata/morphlex/data/forward_translations.pkl'
test_words = [
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

with open(PKL_PATH, 'rb') as f:
    translations = pickle.load(f)

print("Test word verification (pkl lookup only):")
found_count = 0
for ar, en in test_words:
    trans = translations.get(ar, {})
    if trans:
        found_count += 1
        en_trans = trans.get('en', 'N/A')
        lang_count = len(trans)
        print(f"  {ar} ({en}): FOUND - {lang_count} languages, en='{en_trans}'")
    else:
        print(f"  {ar} ({en}): NOT FOUND")

print()
print(f"Found: {found_count}/10 test words")
print(f"PKL size: {os.path.getsize(PKL_PATH):,} bytes")
print(f"Total keys: {len(translations):,}")
PYEOF

echo ""
echo "End: $(date -Iseconds)"
echo "=== DIAGNOSTIC COMPLETE ==="
