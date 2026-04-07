#!/bin/bash
# COMPREHENSIVE DIAGNOSTIC: Find how Arabic translations are stored in Wiktextract dump
# Then build Arabic→X forward_translations.pkl
#
# This script does deep analysis of the dump to understand its structure.
#
# Usage: bash next_task.sh
# Working directory: /mnt/pgdata/morphlex

set -e

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== COMPREHENSIVE WIKTEXTRACT DUMP ANALYSIS ==="
echo "Start: $(date -Iseconds)"
echo ""

###############################################################################
# STEP 1: DEEP DUMP ANALYSIS - Find all translation language codes
###############################################################################

python3 << 'ANALYZE_EOF'
import gzip
import json
import os
import pickle
from collections import Counter, defaultdict

RAW_PATH = "/mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz"
OUTPUT_PATH = "/mnt/pgdata/morphlex/data/forward_translations.pkl"
TARGET_LANGUAGES = ['en', 'tr', 'de', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro']

print("=" * 60)
print("PHASE 1: DUMP STRUCTURE ANALYSIS (first 500K lines)")
print("=" * 60)
print("")

# Counters for analysis
entry_lang_codes = Counter()  # lang_code field of entries
trans_lang_codes = Counter()  # lang_code/code field inside translations
entries_with_translations = 0
arabic_related = []  # entries that mention Arabic somehow
sample_entries_with_trans = []

with gzip.open(RAW_PATH, 'rt', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 500000:
            break

        try:
            entry = json.loads(line.strip())
        except json.JSONDecodeError:
            continue

        # Track entry-level lang_code
        entry_lang = entry.get('lang_code', entry.get('lang', 'NONE'))
        entry_lang_codes[entry_lang] += 1

        # Check translations
        translations = entry.get('translations', [])
        if translations and isinstance(translations, list):
            entries_with_translations += 1

            # Sample entries with translations
            if len(sample_entries_with_trans) < 3:
                sample_entries_with_trans.append({
                    'word': entry.get('word', '?'),
                    'lang_code': entry_lang,
                    'translations': translations[:5]
                })

            for trans in translations:
                if isinstance(trans, dict):
                    # Track translation language codes
                    trans_lang = trans.get('lang_code', trans.get('code', 'NONE'))
                    trans_lang_codes[trans_lang] += 1

                    # Look for Arabic-related codes
                    trans_word = trans.get('word', '')
                    if trans_lang and ('ar' in trans_lang.lower() or 'arab' in trans_lang.lower()):
                        if len(arabic_related) < 10:
                            arabic_related.append({
                                'en_word': entry.get('word', '?'),
                                'trans_lang': trans_lang,
                                'trans_word': trans_word,
                                'trans_keys': list(trans.keys())
                            })
                    # Also check if word contains Arabic script
                    elif any('\u0600' <= c <= '\u06ff' for c in trans_word):
                        if len(arabic_related) < 10:
                            arabic_related.append({
                                'en_word': entry.get('word', '?'),
                                'trans_lang': trans_lang,
                                'trans_word': trans_word,
                                'trans_keys': list(trans.keys())
                            })

print(f"Analyzed: 500,000 lines")
print(f"Entries with 'translations' field: {entries_with_translations:,}")
print("")

print("--- Entry-level lang_code distribution (top 10) ---")
for lang, count in entry_lang_codes.most_common(10):
    print(f"  {lang}: {count:,}")
print("")

print("--- Translation lang_code distribution (top 30) ---")
for lang, count in trans_lang_codes.most_common(30):
    print(f"  {lang}: {count:,}")
print("")

print("--- Sample entries with translations ---")
for i, s in enumerate(sample_entries_with_trans, 1):
    print(f"Sample {i}: '{s['word']}' (entry lang_code: {s['lang_code']})")
    for t in s['translations'][:3]:
        if isinstance(t, dict):
            print(f"  -> {t.get('lang_code', t.get('code', '?'))}: {t.get('word', '?')}")
    print("")

print("--- Arabic-related translations found ---")
if arabic_related:
    for ar in arabic_related[:5]:
        print(f"  English '{ar['en_word']}' -> lang={ar['trans_lang']}, word={ar['trans_word']}")
        print(f"    translation keys: {ar['trans_keys']}")
else:
    print("  NONE FOUND in first 500K lines")
print("")

# Check specifically for 'ar' translations
ar_count = trans_lang_codes.get('ar', 0)
print(f"Translations with lang_code='ar': {ar_count:,}")
print("")

###############################################################################
# PHASE 2: If 'ar' exists, build the Arabic→X index
###############################################################################

if ar_count > 0:
    print("=" * 60)
    print("PHASE 2: BUILDING ARABIC->X FORWARD TRANSLATIONS")
    print("=" * 60)
    print("")

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
    entries_with_arabic = 0

    print("Full scan: Looking for English entries with Arabic translations...")
    print("")

    with gzip.open(RAW_PATH, 'rt', encoding='utf-8') as f:
        for line in f:
            line_count += 1

            if line_count % 500000 == 0:
                print(f"  {line_count:,} lines | {english_entries:,} English entries | {entries_with_arabic:,} with Arabic")

            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            # Only English entries
            if entry.get('lang_code') != 'en':
                continue

            english_entries += 1
            english_word = entry.get('word', '').strip()
            if not english_word:
                continue

            translations = entry.get('translations', [])
            if not translations or not isinstance(translations, list):
                continue

            # Extract all translations
            all_trans = {}
            for trans in translations:
                if not isinstance(trans, dict):
                    continue
                trans_lang = trans.get('lang_code', trans.get('code', ''))
                trans_word = trans.get('word', '').strip()
                if not trans_lang or not trans_word or trans_word == '-':
                    continue
                if not valid_script(trans_lang, trans_word):
                    continue
                if trans_lang not in all_trans:
                    all_trans[trans_lang] = trans_word

            arabic_word = all_trans.get('ar')
            if not arabic_word:
                continue

            if not valid_script('ar', arabic_word):
                continue

            entries_with_arabic += 1

            if arabic_word not in forward_translations:
                forward_translations[arabic_word] = {}

            if 'en' not in forward_translations[arabic_word]:
                forward_translations[arabic_word]['en'] = english_word

            for lang in TARGET_LANGUAGES:
                if lang == 'en':
                    continue
                if lang in all_trans and lang not in forward_translations[arabic_word]:
                    forward_translations[arabic_word][lang] = all_trans[lang]

    print("")
    print("=" * 60)
    print("BUILD RESULTS")
    print("=" * 60)
    print(f"Total lines: {line_count:,}")
    print(f"English entries: {english_entries:,}")
    print(f"English entries with Arabic translation: {entries_with_arabic:,}")
    print(f"Unique Arabic words: {len(forward_translations):,}")
    print("")

    if forward_translations:
        print("--- Per-language coverage ---")
        lang_counts = {lang: 0 for lang in TARGET_LANGUAGES}
        for word_trans in forward_translations.values():
            for lang in word_trans:
                if lang in lang_counts:
                    lang_counts[lang] += 1

        for lang in TARGET_LANGUAGES:
            print(f"  {lang}: {lang_counts[lang]:,}")
        print("")

        # Save
        print(f"Saving to {OUTPUT_PATH}...")
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(OUTPUT_PATH, 'wb') as f:
            pickle.dump(forward_translations, f)

        file_size = os.path.getsize(OUTPUT_PATH)
        if file_size >= 1024 * 1024:
            print(f"SUCCESS: Saved {file_size / (1024*1024):.2f} MB")
        else:
            print(f"SUCCESS: Saved {file_size / 1024:.2f} KB")

        # Show sample entries
        print("")
        print("--- Sample Arabic->X entries ---")
        for ar_word in list(forward_translations.keys())[:5]:
            print(f"  {ar_word}: {forward_translations[ar_word]}")
    else:
        print("ERROR: No Arabic translations found even though analysis showed they exist!")
else:
    print("=" * 60)
    print("ANALYSIS CONCLUSION")
    print("=" * 60)
    print("The Wiktextract dump does NOT contain Arabic translations (lang_code='ar').")
    print("")
    print("Possible reasons:")
    print("1. Arabic uses a different language code")
    print("2. This is a limited/filtered dump")
    print("3. Arabic translations are in a different field")
    print("")
    print("Available translation language codes that might be Arabic:")
    for code, count in trans_lang_codes.most_common(50):
        if any(c for c in code if '\u0600' <= c <= '\u06ff') or 'ar' in code.lower():
            print(f"  {code}: {count:,}")
ANALYZE_EOF

echo ""
echo "End: $(date -Iseconds)"
echo "=== DONE ==="
