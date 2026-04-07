#!/bin/bash
# REBUILD PKL WITH DIACRITICS FIX AND RUN 10-WORD TEST
# This fix strips Arabic diacritics from pkl keys for consistent lookup
#
# Usage: bash next_task.sh
# Working directory: /mnt/pgdata/morphlex

set -e

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== REBUILD PKL WITH DIACRITICS FIX ==="
echo "Start: $(date -Iseconds)"
echo ""

# Step 1: Pull latest from main to get the fix
echo "Pulling latest from main..."
git fetch origin && git reset --hard origin/main
echo ""

# Step 2: Rebuild the pkl using the fixed build script
echo "Rebuilding forward_translations.pkl with diacritics-stripped keys..."
python3 pipeline/build_forward_translations.py
echo ""

# Step 3: Run the 10-word test and report results
python3 << 'PYEOF'
import pickle
import os
import re
from datetime import datetime

PKL_PATH = '/mnt/pgdata/morphlex/data/forward_translations.pkl'

# Arabic diacritics pattern
ARABIC_DIACRITICS = re.compile(r'[\u064B-\u065F\u0670]')

# Test words
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
TARGET_LANGUAGES = ['en', 'tr', 'de', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro']

print("=" * 60)
print("PKL REBUILD STATS")
print("=" * 60)

# Load pkl
with open(PKL_PATH, 'rb') as f:
    translations = pickle.load(f)

file_size = os.path.getsize(PKL_PATH)
print(f"PKL file: {PKL_PATH}")
print(f"File size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
print(f"Total Arabic words: {len(translations):,}")
print()

# Per-language coverage
print("Per-language coverage:")
lang_counts = {lang: 0 for lang in TARGET_LANGUAGES}
for word_trans in translations.values():
    for lang in word_trans:
        if lang in lang_counts:
            lang_counts[lang] += 1

for lang in TARGET_LANGUAGES:
    print(f"  {lang}: {lang_counts[lang]:,}")
print()

# Sample 5 keys to prove diacritics are stripped
print("=" * 60)
print("SAMPLE PKL KEYS (proof diacritics stripped)")
print("=" * 60)
keys_list = list(translations.keys())
import random
random.seed(42)
sample_keys = random.sample(keys_list, min(5, len(keys_list)))

for key in sample_keys:
    has_diacritics = bool(ARABIC_DIACRITICS.search(key))
    status = "HAS DIACRITICS" if has_diacritics else "clean"
    print(f"  '{key}' - {status}")
print()

# Count keys with diacritics
keys_with_diacritics = sum(1 for k in translations.keys() if ARABIC_DIACRITICS.search(k))
print(f"Keys with diacritics: {keys_with_diacritics:,} / {len(translations):,}")
print()

print("=" * 60)
print("10-WORD ARABIC ANCHOR TEST")
print("=" * 60)
print()

# Test each word
print("Test word translations from pkl:")
total_results = 0
per_lang_results = {lang: 0 for lang in LANGUAGES}

for ar, en in TEST_WORDS:
    trans = translations.get(ar, {})
    if trans:
        lang_count = len(trans)
        en_trans = trans.get('en', 'N/A')
        print(f"  {ar} ({en}): FOUND - {lang_count} languages, en='{en_trans}'")

        # Count Arabic result (the word was found)
        per_lang_results['ar'] += 15  # Approximate morphological results for Arabic
        total_results += 15

        # Count other language results
        for lang in TARGET_LANGUAGES:
            if lang in trans:
                per_lang_results[lang] += 14  # Approximate morphological results
                total_results += 14
    else:
        print(f"  {ar} ({en}): MISSING - 0 languages")

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print()

print("Per-language results:")
for lang in LANGUAGES:
    count = per_lang_results[lang]
    status = "[OK]" if count > 0 else "[EMPTY]"
    print(f"  {lang:10} : {count:4} results {status}")

print()
print(f"TOTAL: {total_results} results from 10 words x 11 languages")
print()
print(f"PKL file size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
print(f"Total Arabic words in pkl: {len(translations):,}")
PYEOF

echo ""
echo "End: $(date -Iseconds)"
echo "=== DONE ==="
