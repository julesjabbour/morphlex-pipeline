"""Wiktextract data loader for English Wiktionary dump.

Streams gzipped JSONL data and extracts words, definitions, translations, and etymology.
Also provides fast index-based lookup via precomputed pickle file.
"""

import gzip
import json
import pickle
from typing import Optional


DEFAULT_TARGET_LANGS = ['ar', 'he', 'ja', 'zh', 'de', 'tr', 'sa', 'la', 'grc', 'ine-pro']

# Module-level cache for precomputed index
_cached_index: Optional[dict] = None
_INDEX_PATH = '/mnt/pgdata/morphlex/data/wiktextract_index.pkl'


def load_index(lang_code: str) -> dict:
    """
    Load precomputed reverse lookup index for a specific language.

    This is MUCH faster than load_wiktextract() - loads in seconds instead of minutes.
    The index must be built first using build_wiktextract_index.py.

    Args:
        lang_code: Language code (e.g., 'he', 'grc', 'sa')

    Returns:
        Dict mapping foreign words to list of English concept dicts:
        {foreign_word: [{'english_word': str, 'pos': str, 'definitions': list, ...}]}
    """
    global _cached_index

    if _cached_index is None:
        with open(_INDEX_PATH, 'rb') as f:
            _cached_index = pickle.load(f)

    return _cached_index.get(lang_code, {})


def load_wiktextract(
    filepath: str,
    target_langs: Optional[list[str]] = None,
    max_entries: Optional[int] = None
) -> dict:
    """
    Load Wiktextract English dump and extract word data.

    Args:
        filepath: Path to gzipped JSONL file (raw-wiktextract-data.jsonl.gz)
        target_langs: List of language codes to filter translations (default: common PIE languages)
        max_entries: Maximum number of English entries to load (None = all)

    Returns:
        Dict keyed by English word, containing:
        - definitions: list of definition strings
        - pos: part of speech
        - translations: dict of {lang_code: [translated_words]}
        - etymology: list of etymology template info
    """
    if target_langs is None:
        target_langs = DEFAULT_TARGET_LANGS

    results = {}
    entry_count = 0

    with gzip.open(filepath, 'rt', encoding='utf-8') as f:
        for line in f:
            if max_entries is not None and entry_count >= max_entries:
                break

            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            # Only process English entries
            if entry.get('lang_code') != 'en':
                continue

            word = entry.get('word', '').strip()
            if not word:
                continue

            pos = entry.get('pos', '')

            # Extract definitions from senses[].glosses[]
            definitions = []
            for sense in entry.get('senses', []):
                glosses = sense.get('glosses', [])
                definitions.extend(glosses)

            # Extract translations filtered by target languages
            translations = {}
            for trans in entry.get('translations', []):
                lang_code = trans.get('code', '')
                trans_word = trans.get('word', '')
                if lang_code in target_langs and trans_word:
                    if lang_code not in translations:
                        translations[lang_code] = []
                    if trans_word not in translations[lang_code]:
                        translations[lang_code].append(trans_word)

            # Extract etymology from etymology_templates
            etymology = []
            for tmpl in entry.get('etymology_templates', []):
                etym_info = {
                    'name': tmpl.get('name', ''),
                    'args': tmpl.get('args', {})
                }
                if etym_info['name']:
                    etymology.append(etym_info)

            # Also capture etymology_text if available
            etymology_text = entry.get('etymology_text', '')

            # Build entry data
            entry_data = {
                'definitions': definitions,
                'pos': pos,
                'translations': translations,
                'etymology': etymology,
                'etymology_text': etymology_text
            }

            # Key by word - if word already exists, merge data
            if word in results:
                # Merge definitions (avoid duplicates)
                for defn in definitions:
                    if defn not in results[word]['definitions']:
                        results[word]['definitions'].append(defn)
                # Merge translations
                for lang, words in translations.items():
                    if lang not in results[word]['translations']:
                        results[word]['translations'][lang] = []
                    for w in words:
                        if w not in results[word]['translations'][lang]:
                            results[word]['translations'][lang].append(w)
                # Merge etymology
                results[word]['etymology'].extend(etymology)
                # Keep etymology_text if not already present
                if not results[word]['etymology_text'] and etymology_text:
                    results[word]['etymology_text'] = etymology_text
            else:
                results[word] = entry_data

            entry_count += 1

    return results


def get_stats(data: dict) -> dict:
    """Get statistics about loaded Wiktextract data."""
    total_words = len(data)
    total_definitions = sum(len(d['definitions']) for d in data.values())

    # Count translations per language
    lang_counts = {}
    for entry in data.values():
        for lang, words in entry['translations'].items():
            lang_counts[lang] = lang_counts.get(lang, 0) + len(words)

    # Count entries with etymology
    with_etymology = sum(1 for d in data.values() if d['etymology'])

    return {
        'total_words': total_words,
        'total_definitions': total_definitions,
        'translations_by_lang': lang_counts,
        'entries_with_etymology': with_etymology
    }


if __name__ == '__main__':
    import sys

    filepath = '/mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz'
    if len(sys.argv) > 1:
        filepath = sys.argv[1]

    print(f"Loading first 100 entries from {filepath}...")
    data = load_wiktextract(filepath, max_entries=100)
    stats = get_stats(data)

    print(f"\n=== WIKTEXTRACT LOADER TEST (100 entries) ===")
    print(f"Total unique words: {stats['total_words']}")
    print(f"Total definitions: {stats['total_definitions']}")
    print(f"Entries with etymology: {stats['entries_with_etymology']}")
    print(f"\nTranslations by language:")
    for lang, count in sorted(stats['translations_by_lang'].items()):
        print(f"  {lang}: {count} translations")

    # Show a sample entry with translations
    sample = None
    for word, entry in data.items():
        if entry['translations']:
            sample = (word, entry)
            break

    if sample:
        word, entry = sample
        print(f"\n=== SAMPLE ENTRY: '{word}' ===")
        print(f"POS: {entry['pos']}")
        print(f"Definitions: {entry['definitions'][:3]}")  # First 3
        print(f"Translations: {entry['translations']}")
        if entry['etymology']:
            print(f"Etymology templates: {entry['etymology'][:2]}")  # First 2

    print("\n=== TEST COMPLETE ===")
