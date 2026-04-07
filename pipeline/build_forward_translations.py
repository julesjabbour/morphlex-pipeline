#!/usr/bin/env python3
"""
Build forward translations index from raw Wiktextract dump.

For Arabic anchor mode: builds Arabic→X translation dictionary.

IMPORTANT: The Wiktextract dump is from English Wiktionary, so all entries are
English words with their translations TO other languages. To build Arabic→X:
1. Find English entries that have an Arabic translation
2. Use the Arabic word as the KEY
3. Collect all other translations (en, tr, de, la, zh, ja, he, sa, grc, ine-pro) as VALUES

Output: data/forward_translations.pkl
Format: {arabic_word: {lang_code: word}}
"""

import gzip
import json
import os
import pickle
import random

RAW_WIKTEXTRACT_PATH = "/mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz"
OUTPUT_PATH = "/mnt/pgdata/morphlex/data/forward_translations.pkl"

# Target languages for Arabic anchor mode (all languages except Arabic itself)
TARGET_LANGUAGES = ['en', 'tr', 'de', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro']


def _valid_script(lang: str, word: str) -> bool:
    """Check if word contains characters from the expected script for the language."""
    if lang == 'zh':
        # CJK Unified Ideographs: U+4E00-U+9FFF
        return any('\u4e00' <= c <= '\u9fff' for c in word)
    elif lang == 'he':
        # Hebrew: U+0590-U+05FF
        return any('\u0590' <= c <= '\u05ff' for c in word)
    elif lang == 'ja':
        # CJK or Hiragana/Katakana: U+3040-U+30FF or U+4E00-U+9FFF
        return any(('\u3040' <= c <= '\u30ff') or ('\u4e00' <= c <= '\u9fff') for c in word)
    elif lang == 'sa':
        # Devanagari: U+0900-U+097F
        return any('\u0900' <= c <= '\u097f' for c in word)
    elif lang == 'grc':
        # Greek: U+0370-U+03FF or Extended Greek: U+1F00-U+1FFF
        return any(('\u0370' <= c <= '\u03ff') or ('\u1f00' <= c <= '\u1fff') for c in word)
    elif lang == 'ar':
        # Arabic: U+0600-U+06FF
        return any('\u0600' <= c <= '\u06ff' for c in word)
    # en, tr, de, la use Latin script - no filter needed
    # ine-pro uses reconstructed forms with * prefix - allow any
    return True


def _extract_translations_from_entry(entry: dict) -> dict:
    """
    Extract all translations from an entry.
    Returns: {lang_code: word} for all translations found
    """
    translations = entry.get('translations', [])
    if not translations or not isinstance(translations, list):
        return {}

    result = {}
    for trans in translations:
        if not isinstance(trans, dict):
            continue

        # Try both 'lang_code' and 'code' fields
        lang_code = trans.get('lang_code', trans.get('code', ''))
        trans_word = trans.get('word', '').strip()

        if not lang_code or not trans_word or trans_word == '-':
            continue

        # Script validation
        if not _valid_script(lang_code, trans_word):
            continue

        # Keep first match for each language
        if lang_code not in result:
            result[lang_code] = trans_word

    return result


def build_forward_translations():
    """
    Stream raw Wiktextract dump and build forward translations index.

    INVERTED LOGIC for English Wiktionary dump:
    - Process English language entries (lang_code == 'en')
    - Find entries that have an Arabic translation
    - Use the Arabic word as KEY
    - Collect all other translations as VALUES (including the English word itself)
    """
    if not os.path.exists(RAW_WIKTEXTRACT_PATH):
        print(f"ERROR: Raw file not found: {RAW_WIKTEXTRACT_PATH}")
        return

    print(f"=== BUILDING FORWARD TRANSLATIONS INDEX (Arabic Anchor - Inverted) ===")
    print(f"Input: {RAW_WIKTEXTRACT_PATH}")
    print(f"Output: {OUTPUT_PATH}")
    print(f"Target languages: {TARGET_LANGUAGES}")
    print()

    # Result: {arabic_word: {lang_code: word}}
    forward_translations = {}

    line_count = 0
    english_entries = 0
    entries_with_arabic = 0
    sample_entries = []  # For debugging if needed

    print("Streaming raw Wiktextract dump (looking for English entries with Arabic translations)...")

    with gzip.open(RAW_WIKTEXTRACT_PATH, 'rt', encoding='utf-8') as f:
        for line in f:
            line_count += 1

            if line_count % 100000 == 0:
                print(f"  Processed {line_count:,} lines, {entries_with_arabic:,} English entries with Arabic translations...")

            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            # Only process English entries (the Wiktextract dump is from English Wiktionary)
            if entry.get('lang_code') != 'en':
                continue

            english_entries += 1
            english_word = entry.get('word', '').strip()
            if not english_word:
                continue

            # Extract all translations from this entry
            all_trans = _extract_translations_from_entry(entry)

            # Check if there's an Arabic translation
            arabic_word = all_trans.get('ar')
            if not arabic_word:
                continue

            # Validate Arabic script
            if not _valid_script('ar', arabic_word):
                continue

            entries_with_arabic += 1

            # Save samples for debugging
            if len(sample_entries) < 10 and random.random() < 0.001:
                sample_entries.append({
                    'en': english_word,
                    'ar': arabic_word,
                    'trans': all_trans
                })

            # Initialize entry if needed
            if arabic_word not in forward_translations:
                forward_translations[arabic_word] = {}

            # Add English word as the 'en' translation
            if 'en' not in forward_translations[arabic_word]:
                forward_translations[arabic_word]['en'] = english_word

            # Add all other target language translations
            for lang_code in TARGET_LANGUAGES:
                if lang_code == 'en':
                    continue  # Already added above
                if lang_code in all_trans and lang_code not in forward_translations[arabic_word]:
                    forward_translations[arabic_word][lang_code] = all_trans[lang_code]

    print(f"\nDone! Processed {line_count:,} lines")
    print(f"Total English entries: {english_entries:,}")
    print(f"English entries with Arabic translation: {entries_with_arabic:,}")
    print(f"Unique Arabic words with translations: {len(forward_translations):,}")

    # Show samples if result is small or for debugging
    if entries_with_arabic < 5000 and sample_entries:
        print(f"\n=== SAMPLE ENTRIES (for debugging) ===")
        for s in sample_entries[:5]:
            print(f"  English: {s['en']} → Arabic: {s['ar']}")
            print(f"    Translations: {s['trans']}")

    # If no results, sample the dump to show data structure
    if entries_with_arabic == 0:
        print("\n=== DEBUG: No Arabic translations found. Sampling dump structure... ===")
        _sample_dump_structure()
        return

    # Stats per language
    print("\n=== STATS PER LANGUAGE ===")
    lang_counts = {lang: 0 for lang in TARGET_LANGUAGES}
    for word_trans in forward_translations.values():
        for lang in word_trans:
            if lang in lang_counts:
                lang_counts[lang] += 1

    for lang in TARGET_LANGUAGES:
        print(f"  {lang}: {lang_counts[lang]:,} entries")

    # Save
    print(f"\nSaving to {OUTPUT_PATH}...")
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'wb') as f:
        pickle.dump(forward_translations, f)

    file_size = os.path.getsize(OUTPUT_PATH)
    if file_size >= 1024 * 1024:
        print(f"Saved {file_size / (1024 * 1024):.1f}MB forward translations index")
    else:
        print(f"Saved {file_size / 1024:.1f}KB forward translations index")

    return forward_translations


def _sample_dump_structure():
    """Sample the Wiktextract dump to show its structure for debugging."""
    print("\nSampling 5 random English entries with translations:")

    samples = []
    line_count = 0

    with gzip.open(RAW_WIKTEXTRACT_PATH, 'rt', encoding='utf-8') as f:
        for line in f:
            line_count += 1
            if line_count > 500000:  # Don't scan entire file
                break

            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            # Look for English entries with translations
            if entry.get('lang_code') == 'en' and entry.get('translations'):
                trans = entry.get('translations', [])
                if len(trans) > 3 and random.random() < 0.0001:
                    samples.append({
                        'word': entry.get('word'),
                        'lang_code': entry.get('lang_code'),
                        'translations': trans[:10],  # First 10 translations
                        'keys': list(entry.keys())
                    })
                    if len(samples) >= 5:
                        break

    if not samples:
        print("  No English entries with translations found in first 500K lines!")
        print("  Checking what languages exist in the dump...")

        # Show what languages are in the dump
        from collections import Counter
        lang_counter = Counter()
        has_trans = 0
        sample_any = None

        with gzip.open(RAW_WIKTEXTRACT_PATH, 'rt', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= 10000:
                    break
                try:
                    entry = json.loads(line.strip())
                    lang = entry.get('lang_code', entry.get('lang', 'unknown'))
                    lang_counter[lang] += 1
                    if entry.get('translations') and not sample_any:
                        has_trans += 1
                        sample_any = entry
                except:
                    pass

        print(f"  Languages in first 10K lines: {dict(lang_counter.most_common(10))}")
        print(f"  Entries with translations: {has_trans}")
        if sample_any:
            print(f"  Sample entry keys: {list(sample_any.keys())}")
            print(f"  Sample word: {sample_any.get('word')}")
            print(f"  Sample translations (first 3): {sample_any.get('translations', [])[:3]}")
    else:
        for i, s in enumerate(samples, 1):
            print(f"\n  Sample {i}: {s['word']}")
            print(f"    Entry keys: {s['keys']}")
            print(f"    Translations:")
            for t in s['translations'][:5]:
                if isinstance(t, dict):
                    print(f"      {t.get('lang_code', t.get('code', '?'))}: {t.get('word', '?')}")


if __name__ == '__main__':
    build_forward_translations()
