#!/bin/bash
# DIAGNOSE and REBUILD forward_translations.pkl with INLINE Python
#
# This script does NOT rely on build_forward_translations.py - all logic is inline.
#
# Usage: bash next_task.sh
# Working directory: /mnt/pgdata/morphlex

set -e

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== DIAGNOSE AND REBUILD FORWARD TRANSLATIONS ==="
echo "Start: $(date -Iseconds)"
echo ""

###############################################################################
# STEP 1: DIAGNOSE - What's actually on the VM?
###############################################################################

echo "=========================================="
echo "STEP 1: DIAGNOSTIC - Checking VM state"
echo "=========================================="
echo ""

echo "--- Git log (last 5 commits) ---"
git log --oneline -5
echo ""

echo "--- build_forward_translations.py (first 100 lines) ---"
head -100 pipeline/build_forward_translations.py
echo ""

echo "--- Sample 3 entries from raw Wiktextract dump ---"
python3 << 'DIAG_EOF'
import gzip
import json

RAW_PATH = "/mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz"

print("Reading first 3 entries from raw-wiktextract-data.jsonl.gz...\n")

with gzip.open(RAW_PATH, 'rt', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 3:
            break
        try:
            entry = json.loads(line.strip())
            print(f"Entry {i+1}:")
            print(f"  lang_code: {entry.get('lang_code', 'NOT PRESENT')}")
            print(f"  lang: {entry.get('lang', 'NOT PRESENT')}")
            print(f"  word: {entry.get('word', 'NOT PRESENT')}")
            print(f"  has 'translations' field: {'translations' in entry}")
            if 'translations' in entry:
                trans = entry['translations']
                print(f"  translations type: {type(trans).__name__}, count: {len(trans) if isinstance(trans, list) else 'N/A'}")
                if isinstance(trans, list) and len(trans) > 0:
                    print(f"  first translation item: {trans[0]}")
            print(f"  all keys: {list(entry.keys())[:15]}...")
            print("")
        except Exception as e:
            print(f"Entry {i+1}: ERROR parsing: {e}")
            print("")
DIAG_EOF

echo ""

###############################################################################
# STEP 2: BUILD INLINE - Complete logic embedded in this script
###############################################################################

echo "=========================================="
echo "STEP 2: BUILD - Inline Python build logic"
echo "=========================================="
echo ""

python3 << 'BUILD_EOF'
import gzip
import json
import os
import pickle

RAW_PATH = "/mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz"
OUTPUT_PATH = "/mnt/pgdata/morphlex/data/forward_translations.pkl"
TARGET_LANGUAGES = ['en', 'tr', 'de', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro']

def valid_script(lang, word):
    """Check if word contains expected script characters."""
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

print("=== BUILDING FORWARD TRANSLATIONS (Arabic Anchor - INLINE) ===")
print(f"Input: {RAW_PATH}")
print(f"Output: {OUTPUT_PATH}")
print(f"Target languages: {TARGET_LANGUAGES}")
print("")

# Result: {arabic_word: {lang_code: word}}
forward_translations = {}

line_count = 0
english_entries = 0
entries_with_arabic = 0
entries_with_translations = 0
sample_english_entries = []  # For debugging if 0 results

print("Streaming Wiktextract dump...")
print("Looking for English entries (lang_code='en') with Arabic translations...")
print("")

with gzip.open(RAW_PATH, 'rt', encoding='utf-8') as f:
    for line in f:
        line_count += 1

        if line_count % 500000 == 0:
            print(f"  {line_count:,} lines | {english_entries:,} English | {entries_with_translations:,} have translations | {entries_with_arabic:,} have Arabic")

        try:
            entry = json.loads(line.strip())
        except json.JSONDecodeError:
            continue

        # Check lang_code field - could be 'en' for English entries
        lang_code = entry.get('lang_code', '')

        # Only process English entries
        if lang_code != 'en':
            continue

        english_entries += 1
        english_word = entry.get('word', '').strip()
        if not english_word:
            continue

        # Get translations
        translations = entry.get('translations', [])
        if not translations or not isinstance(translations, list):
            # Save sample English entries for debugging
            if len(sample_english_entries) < 5:
                sample_english_entries.append({
                    'word': english_word,
                    'keys': list(entry.keys()),
                    'has_senses': 'senses' in entry
                })
            continue

        entries_with_translations += 1

        # Extract all translations: {lang_code: word}
        all_trans = {}
        for trans in translations:
            if not isinstance(trans, dict):
                continue
            # Try both 'lang_code' and 'code' fields for the translation's language
            trans_lang = trans.get('lang_code', trans.get('code', ''))
            trans_word = trans.get('word', '').strip()
            if not trans_lang or not trans_word or trans_word == '-':
                continue
            if not valid_script(trans_lang, trans_word):
                continue
            if trans_lang not in all_trans:
                all_trans[trans_lang] = trans_word

        # Check if there's an Arabic translation
        arabic_word = all_trans.get('ar')
        if not arabic_word:
            continue

        if not valid_script('ar', arabic_word):
            continue

        entries_with_arabic += 1

        # Initialize entry if needed
        if arabic_word not in forward_translations:
            forward_translations[arabic_word] = {}

        # Add English word
        if 'en' not in forward_translations[arabic_word]:
            forward_translations[arabic_word]['en'] = english_word

        # Add all other target language translations
        for lang in TARGET_LANGUAGES:
            if lang == 'en':
                continue
            if lang in all_trans and lang not in forward_translations[arabic_word]:
                forward_translations[arabic_word][lang] = all_trans[lang]

print("")
print("=== BUILD RESULTS ===")
print(f"Total lines processed: {line_count:,}")
print(f"English entries found: {english_entries:,}")
print(f"English entries with translations field: {entries_with_translations:,}")
print(f"English entries with Arabic translation: {entries_with_arabic:,}")
print(f"Unique Arabic words collected: {len(forward_translations):,}")
print("")

# If 0 results, show sample English entries
if entries_with_arabic == 0:
    print("=== DEBUG: 0 Arabic translations found ===")
    print("")
    if sample_english_entries:
        print("Sample English entries (showing their structure):")
        for i, s in enumerate(sample_english_entries, 1):
            print(f"  {i}. word: {s['word']}")
            print(f"     keys: {s['keys']}")
            print(f"     has_senses: {s['has_senses']}")
        print("")

    # Show a sample entry with translations if any exist
    print("Looking for ANY entry with 'translations' field in first 100K lines...")
    with gzip.open(RAW_PATH, 'rt', encoding='utf-8') as f:
        found_trans = None
        for i, line in enumerate(f):
            if i >= 100000:
                break
            try:
                entry = json.loads(line.strip())
                if entry.get('translations'):
                    found_trans = entry
                    break
            except:
                pass

        if found_trans:
            print(f"Found entry with translations at line {i+1}:")
            print(f"  word: {found_trans.get('word')}")
            print(f"  lang_code: {found_trans.get('lang_code')}")
            print(f"  translations count: {len(found_trans.get('translations', []))}")
            print(f"  first 3 translations:")
            for t in found_trans.get('translations', [])[:3]:
                print(f"    {t}")
        else:
            print("NO entries with 'translations' field found in first 100K lines!")
            print("The dump may not have translation data.")
else:
    # Per-language stats
    print("=== PER-LANGUAGE COVERAGE ===")
    lang_counts = {lang: 0 for lang in TARGET_LANGUAGES}
    for word_trans in forward_translations.values():
        for lang in word_trans:
            if lang in lang_counts:
                lang_counts[lang] += 1

    for lang in TARGET_LANGUAGES:
        print(f"  {lang}: {lang_counts[lang]:,} entries")
    print("")

    # Save
    print(f"Saving to {OUTPUT_PATH}...")
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'wb') as f:
        pickle.dump(forward_translations, f)

    file_size = os.path.getsize(OUTPUT_PATH)
    if file_size >= 1024 * 1024:
        print(f"Saved: {file_size / (1024 * 1024):.2f} MB")
    else:
        print(f"Saved: {file_size / 1024:.2f} KB")
    print(f"Total bytes: {file_size}")

BUILD_EOF

echo ""

###############################################################################
# STEP 3: REPORT - Final summary
###############################################################################

echo "=========================================="
echo "STEP 3: REPORT - Final Summary"
echo "=========================================="
echo ""

if [ -f "data/forward_translations.pkl" ]; then
    FILE_SIZE=$(stat -c%s "data/forward_translations.pkl")
    echo "forward_translations.pkl exists: $FILE_SIZE bytes"
else
    echo "forward_translations.pkl NOT FOUND"
fi

echo ""
echo "End: $(date -Iseconds)"
echo "=== DONE ==="
