#!/bin/bash
# REBUILD PKL WITH DIACRITICS FIX AND RUN 10-WORD TEST
# This fix strips Arabic diacritics from pkl keys for consistent lookup
#
# Usage: bash next_task.sh
# Working directory: /mnt/pgdata/morphlex
#
# NOTE: git fetch/reset is handled by run.sh - do not duplicate here

set -e

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== REBUILD PKL WITH DIACRITICS FIX ==="
echo "Start: $(date -Iseconds)"
echo "Git HEAD: $(git rev-parse --short HEAD)"
echo ""

# Step 1: Show current pkl stats
echo "Current pkl before rebuild:"
ls -la data/forward_translations.pkl 2>/dev/null || echo "  (does not exist)"
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

# Test each word - check if in pkl
print("Test word translations from pkl:")
words_found = 0
words_missing = 0

for ar, en in TEST_WORDS:
    trans = translations.get(ar, {})
    if trans:
        words_found += 1
        lang_count = len(trans)
        en_trans = trans.get('en', 'N/A')
        print(f"  {ar} ({en}): FOUND - {lang_count} languages, en='{en_trans}'")
    else:
        words_missing += 1
        print(f"  {ar} ({en}): MISSING - 0 languages")

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print()

print(f"Test words found in pkl: {words_found}/10")
print(f"Test words missing from pkl: {words_missing}/10")
print()
print(f"PKL file size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
print(f"Total Arabic words in pkl: {len(translations):,}")
print(f"Keys with diacritics: {keys_with_diacritics:,}")

# If all 10 words are missing, show what keys look like
if words_missing == 10:
    print()
    print("=" * 60)
    print("DEBUG: All test words missing - showing 10 random keys")
    print("=" * 60)
    for k in random.sample(keys_list, min(10, len(keys_list))):
        print(f"  '{k}'")
PYEOF

echo ""
echo "End: $(date -Iseconds)"
echo "=== DONE ==="
