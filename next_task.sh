#!/bin/bash
# FIX CRON AND BUILD ARABIC->X FORWARD TRANSLATIONS
# This script diagnoses the dump structure and builds the correct pkl
#
# Usage: bash next_task.sh
# Working directory: /mnt/pgdata/morphlex

set -e

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== FIX FORWARD TRANSLATIONS BUILD ==="
echo "Start: $(date -Iseconds)"
echo "Git commit on VM: $(git rev-parse --short HEAD)"
echo ""

# Force sync with latest main
echo "=== SYNCING WITH REMOTE ==="
git fetch origin main 2>&1 || echo "Warning: git fetch failed"
git reset --hard origin/main 2>&1 || echo "Warning: git reset failed"
echo "After sync: $(git rev-parse --short HEAD)"
echo ""

python3 << 'PYEOF'
import gzip
import json
import os
import pickle
from collections import Counter, defaultdict

RAW_PATH = "/mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz"
OUTPUT_PATH = "/mnt/pgdata/morphlex/data/forward_translations.pkl"
TARGET_LANGUAGES = ['en', 'tr', 'de', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro']

print("=" * 60)
print("PHASE 1: DUMP STRUCTURE ANALYSIS")
print("=" * 60)

# Quick sample to understand structure
trans_lang_codes = Counter()
entries_with_trans = 0
arabic_samples = []

print("Sampling first 200K lines for structure analysis...")
with gzip.open(RAW_PATH, 'rt', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 200000:
            break
        try:
            entry = json.loads(line.strip())
        except:
            continue

        # Only English entries (this dump is from English Wiktionary)
        if entry.get('lang_code') != 'en':
            continue

        translations = entry.get('translations', [])
        if not translations or not isinstance(translations, list):
            continue

        entries_with_trans += 1

        for trans in translations:
            if isinstance(trans, dict):
                # Try multiple field names for language code
                lang = trans.get('lang_code') or trans.get('code') or trans.get('lang') or 'NONE'
                trans_lang_codes[lang] += 1

                # Sample Arabic translations
                word = trans.get('word', '')
                if lang == 'ar' or any('\u0600' <= c <= '\u06ff' for c in word):
                    if len(arabic_samples) < 10:
                        arabic_samples.append({
                            'en': entry.get('word'),
                            'trans_lang': lang,
                            'trans_word': word,
                            'trans_keys': list(trans.keys())
                        })

print(f"English entries with translations: {entries_with_trans:,}")
print()

print("--- Translation language codes (top 40) ---")
for lang, count in trans_lang_codes.most_common(40):
    marker = " <-- ARABIC?" if 'ar' in lang.lower() else ""
    print(f"  {lang}: {count:,}{marker}")
print()

print("--- Arabic-related samples found ---")
if arabic_samples:
    for s in arabic_samples[:5]:
        print(f"  EN '{s['en']}' -> lang={s['trans_lang']}, word={s['trans_word']}")
        print(f"    keys: {s['trans_keys']}")
else:
    print("  NONE in first 200K lines - checking for Arabic-script words...")
print()

# Check if 'ar' exists in language codes
ar_count = trans_lang_codes.get('ar', 0)
print(f"Translations with lang_code='ar': {ar_count:,}")

if ar_count == 0:
    # Look for any Arabic-script words regardless of lang_code
    print("\nSearching for Arabic-script words in any language field...")
    arabic_script_count = 0
    arabic_script_samples = []

    with gzip.open(RAW_PATH, 'rt', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 500000:
                break
            try:
                entry = json.loads(line.strip())
            except:
                continue

            if entry.get('lang_code') != 'en':
                continue

            for trans in entry.get('translations', []):
                if isinstance(trans, dict):
                    word = trans.get('word', '')
                    if word and any('\u0600' <= c <= '\u06ff' for c in word):
                        arabic_script_count += 1
                        if len(arabic_script_samples) < 5:
                            arabic_script_samples.append({
                                'en': entry.get('word'),
                                'trans': trans
                            })

    print(f"Arabic-script translations found: {arabic_script_count:,}")
    for s in arabic_script_samples:
        print(f"  EN '{s['en']}' -> {s['trans']}")

###############################################################################
# PHASE 2: BUILD ARABIC->X INDEX
###############################################################################

print()
print("=" * 60)
print("PHASE 2: BUILDING ARABIC->X FORWARD TRANSLATIONS")
print("=" * 60)

def valid_script(lang, word):
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

forward_translations = {}
line_count = 0
english_entries = 0
english_with_arabic = 0

print("Full scan: Finding English entries with Arabic translations...")
print("(Looking for lang_code='ar' or Arabic-script words)")
print()

with gzip.open(RAW_PATH, 'rt', encoding='utf-8') as f:
    for line in f:
        line_count += 1

        if line_count % 500000 == 0:
            print(f"  {line_count:,} lines | {english_entries:,} EN | {english_with_arabic:,} with AR")

        try:
            entry = json.loads(line.strip())
        except:
            continue

        if entry.get('lang_code') != 'en':
            continue

        english_entries += 1
        english_word = entry.get('word', '').strip()
        if not english_word:
            continue

        translations = entry.get('translations', [])
        if not translations:
            continue

        # Extract all translations
        all_trans = {}
        arabic_word = None

        for trans in translations:
            if not isinstance(trans, dict):
                continue

            # Try multiple field names
            lang = trans.get('lang_code') or trans.get('code') or trans.get('lang') or ''
            word = trans.get('word', '').strip()

            if not lang or not word or word == '-':
                continue

            if not valid_script(lang, word):
                continue

            if lang not in all_trans:
                all_trans[lang] = word

            # Check for Arabic
            if lang == 'ar' and valid_script('ar', word):
                if not arabic_word:
                    arabic_word = word

        if not arabic_word:
            continue

        english_with_arabic += 1

        if arabic_word not in forward_translations:
            forward_translations[arabic_word] = {}

        # Add English as translation
        if 'en' not in forward_translations[arabic_word]:
            forward_translations[arabic_word]['en'] = english_word

        # Add other target languages
        for lang in TARGET_LANGUAGES:
            if lang == 'en':
                continue
            if lang in all_trans and lang not in forward_translations[arabic_word]:
                forward_translations[arabic_word][lang] = all_trans[lang]

print()
print("=" * 60)
print("BUILD RESULTS")
print("=" * 60)
print(f"Total lines: {line_count:,}")
print(f"English entries: {english_entries:,}")
print(f"English entries with Arabic: {english_with_arabic:,}")
print(f"Unique Arabic words: {len(forward_translations):,}")
print()

if forward_translations:
    print("--- Per-language coverage ---")
    lang_counts = {lang: 0 for lang in TARGET_LANGUAGES}
    for word_trans in forward_translations.values():
        for lang in word_trans:
            if lang in lang_counts:
                lang_counts[lang] += 1

    for lang in TARGET_LANGUAGES:
        print(f"  {lang}: {lang_counts[lang]:,}")
    print()

    # Save
    print(f"Saving to {OUTPUT_PATH}...")
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'wb') as f:
        pickle.dump(forward_translations, f)

    file_size = os.path.getsize(OUTPUT_PATH)
    print(f"SUCCESS: Saved {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")

    print()
    print("--- Sample entries ---")
    for ar_word in list(forward_translations.keys())[:5]:
        print(f"  {ar_word}: {forward_translations[ar_word]}")
else:
    print("ERROR: No Arabic translations found!")
    print()
    print("This means the Wiktextract dump either:")
    print("1. Uses a different language code for Arabic (not 'ar')")
    print("2. Doesn't have Arabic translations at all")
    print()
    print("Check trans_lang_codes output above for available language codes.")
PYEOF

echo ""
echo "End: $(date -Iseconds)"
echo "=== DONE ==="
