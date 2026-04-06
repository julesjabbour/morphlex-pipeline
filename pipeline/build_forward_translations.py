#!/usr/bin/env python3
"""
Build forward translations index from raw Wiktextract dump.

Streams raw-wiktextract-data.jsonl.gz and extracts translations from English entries.
Each English entry has a 'translations' list ordered by sense (primary first).
For each (english_word, target_lang) pair, we keep ONLY THE FIRST match.

Output: data/forward_translations.pkl
Format: {english_word: {lang_code: word}}
"""

import gzip
import json
import os
import pickle

RAW_WIKTEXTRACT_PATH = "/mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz"
OUTPUT_PATH = "/mnt/pgdata/morphlex/data/forward_translations.pkl"

TARGET_LANGUAGES = ['ar', 'he', 'ja', 'zh', 'de', 'tr', 'sa', 'la', 'grc']


def _valid_script(lang: str, word: str) -> bool:
    """Check if word contains characters from the expected script for the language."""
    if lang == 'zh':
        # CJK Unified Ideographs: U+4E00-U+9FFF
        return any('\u4e00' <= c <= '\u9fff' for c in word)
    elif lang == 'ar':
        # Arabic: U+0600-U+06FF
        return any('\u0600' <= c <= '\u06ff' for c in word)
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
    # de, tr, la use Latin script - no filter needed
    return True


def build_forward_translations():
    """
    Stream raw Wiktextract dump and build forward translations index.

    For each English entry with a 'translations' list:
    - Iterate translations IN ORDER (primary sense first)
    - For each (english_word, target_lang) pair, keep ONLY THE FIRST match
    - Apply script validation
    - Filter out empty words and "-"
    """
    if not os.path.exists(RAW_WIKTEXTRACT_PATH):
        print(f"ERROR: Raw file not found: {RAW_WIKTEXTRACT_PATH}")
        return

    print(f"=== BUILDING FORWARD TRANSLATIONS INDEX ===")
    print(f"Input: {RAW_WIKTEXTRACT_PATH}")
    print(f"Output: {OUTPUT_PATH}")
    print(f"Target languages: {TARGET_LANGUAGES}")
    print()

    # Result: {english_word: {lang_code: word}}
    forward_translations = {}

    line_count = 0
    entries_with_trans = 0

    print("Streaming raw Wiktextract dump...")

    with gzip.open(RAW_WIKTEXTRACT_PATH, 'rt', encoding='utf-8') as f:
        for line in f:
            line_count += 1

            if line_count % 100000 == 0:
                print(f"  Processed {line_count:,} lines, {entries_with_trans:,} entries with translations...")

            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            # Only process English entries
            if entry.get('lang_code') != 'en':
                continue

            word = entry.get('word', '').lower().strip()
            if not word:
                continue

            # Get translations list
            translations = entry.get('translations', [])
            if not translations or not isinstance(translations, list):
                continue

            entries_with_trans += 1

            # Initialize entry if needed
            if word not in forward_translations:
                forward_translations[word] = {}

            # Iterate translations IN ORDER (primary sense first)
            for trans in translations:
                if not isinstance(trans, dict):
                    continue

                lang_code = trans.get('lang_code', trans.get('code', ''))
                trans_word = trans.get('word', '')

                # Skip if not a target language
                if lang_code not in TARGET_LANGUAGES:
                    continue

                # Filter empty words and "-"
                if not trans_word or trans_word == '-':
                    continue

                # Script validation
                if not _valid_script(lang_code, trans_word):
                    continue

                # Keep ONLY THE FIRST match for each (word, lang) pair
                if lang_code not in forward_translations[word]:
                    forward_translations[word][lang_code] = trans_word

    print(f"\nDone! Processed {line_count:,} lines")
    print(f"English entries with translations: {entries_with_trans:,}")
    print(f"Unique English words with translations: {len(forward_translations):,}")

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
    with open(OUTPUT_PATH, 'wb') as f:
        pickle.dump(forward_translations, f)

    file_size = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"Saved {file_size:.1f}MB forward translations index")

    return forward_translations


if __name__ == '__main__':
    build_forward_translations()
