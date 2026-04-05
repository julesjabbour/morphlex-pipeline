"""
Etymology Enricher module for morphlex pipeline.

Loads etymology data from etymology-db and CogNet to find
borrowings, cognates, and derivation relationships across languages.
"""

import os
import json
import csv
from pathlib import Path
from typing import Optional

# Global indexes for fast lookup
_etymology_db_index: dict = {}
_cognet_index: dict = {}
_indexes_loaded: bool = False

ETYMOLOGY_DB_PATH = "/mnt/pgdata/morphlex/etymology-db/"
COGNET_PATH = "/mnt/pgdata/morphlex/CogNet/"


def _parse_json_etymology(filepath: str) -> list[dict]:
    """Parse a JSON etymology file."""
    entries = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                entries = data
            elif isinstance(data, dict):
                # Handle dict with 'entries' or 'relations' key
                entries = data.get('entries', data.get('relations', []))
    except (json.JSONDecodeError, IOError):
        pass
    return entries


def _parse_csv_etymology(filepath: str) -> list[dict]:
    """Parse a CSV/TSV etymology file."""
    entries = []
    delimiter = '\t' if filepath.endswith('.tsv') else ','
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Try to detect if there's a header
            sample = f.read(4096)
            f.seek(0)
            has_header = csv.Sniffer().has_header(sample) if sample.strip() else True

            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                # Normalize field names
                entry = {}
                for key, value in row.items():
                    if key is None:
                        continue
                    key_lower = key.lower().strip()
                    if 'source' in key_lower and 'word' in key_lower:
                        entry['source_word'] = value
                    elif 'target' in key_lower and 'word' in key_lower:
                        entry['target_word'] = value
                    elif 'source' in key_lower and 'lang' in key_lower:
                        entry['source_language'] = value
                    elif 'target' in key_lower and 'lang' in key_lower:
                        entry['target_language'] = value
                    elif 'relation' in key_lower or 'type' in key_lower:
                        entry['relation_type'] = value
                    elif key_lower in ('word1', 'word_1'):
                        entry['source_word'] = value
                    elif key_lower in ('word2', 'word_2'):
                        entry['target_word'] = value
                    elif key_lower in ('lang1', 'lang_1', 'language1'):
                        entry['source_language'] = value
                    elif key_lower in ('lang2', 'lang_2', 'language2'):
                        entry['target_language'] = value
                    else:
                        entry[key_lower] = value
                if entry.get('source_word') or entry.get('target_word'):
                    entries.append(entry)
    except (csv.Error, IOError):
        pass
    return entries


def _load_etymology_db() -> dict:
    """
    Load etymology-db into an index keyed by (word, language).
    Returns dict mapping (word, lang) -> list of relationships.
    """
    index = {}

    if not os.path.exists(ETYMOLOGY_DB_PATH):
        return index

    for root, dirs, files in os.walk(ETYMOLOGY_DB_PATH):
        for filename in files:
            filepath = os.path.join(root, filename)
            entries = []

            if filename.endswith('.json'):
                entries = _parse_json_etymology(filepath)
            elif filename.endswith(('.csv', '.tsv', '.txt')):
                entries = _parse_csv_etymology(filepath)

            for entry in entries:
                source_word = entry.get('source_word', '').lower().strip()
                target_word = entry.get('target_word', '').lower().strip()
                source_lang = entry.get('source_language', '').lower().strip()
                target_lang = entry.get('target_language', '').lower().strip()
                relation = entry.get('relation_type', 'related').lower().strip()

                # Index by source word
                if source_word and source_lang:
                    key = (source_word, source_lang)
                    if key not in index:
                        index[key] = []
                    index[key].append({
                        'relation_type': relation,
                        'related_word': target_word,
                        'related_language': target_lang,
                        'source': 'etymology-db'
                    })

                # Also index by target word (reverse relationship)
                if target_word and target_lang:
                    key = (target_word, target_lang)
                    if key not in index:
                        index[key] = []
                    # Reverse the relation if applicable
                    reverse_relation = relation
                    if relation == 'derived':
                        reverse_relation = 'derived_from'
                    elif relation == 'derived_from':
                        reverse_relation = 'derived'
                    elif relation == 'borrowed':
                        reverse_relation = 'borrowed_from'
                    elif relation == 'borrowed_from':
                        reverse_relation = 'borrowed'

                    index[key].append({
                        'relation_type': reverse_relation,
                        'related_word': source_word,
                        'related_language': source_lang,
                        'source': 'etymology-db'
                    })

    return index


def _load_cognet() -> dict:
    """
    Load CogNet cognate pairs into an index keyed by (word, language).
    Returns dict mapping (word, lang) -> list of cognate relationships.
    """
    index = {}

    if not os.path.exists(COGNET_PATH):
        return index

    for root, dirs, files in os.walk(COGNET_PATH):
        for filename in files:
            filepath = os.path.join(root, filename)

            if filename.endswith('.json'):
                entries = _parse_json_etymology(filepath)
                for entry in entries:
                    word1 = entry.get('word1', entry.get('source_word', '')).lower().strip()
                    word2 = entry.get('word2', entry.get('target_word', '')).lower().strip()
                    lang1 = entry.get('lang1', entry.get('language1', entry.get('source_language', ''))).lower().strip()
                    lang2 = entry.get('lang2', entry.get('language2', entry.get('target_language', ''))).lower().strip()

                    if word1 and lang1 and word2 and lang2:
                        # Add both directions for cognates
                        key1 = (word1, lang1)
                        key2 = (word2, lang2)

                        if key1 not in index:
                            index[key1] = []
                        index[key1].append({
                            'relation_type': 'cognate',
                            'related_word': word2,
                            'related_language': lang2,
                            'source': 'cognet'
                        })

                        if key2 not in index:
                            index[key2] = []
                        index[key2].append({
                            'relation_type': 'cognate',
                            'related_word': word1,
                            'related_language': lang1,
                            'source': 'cognet'
                        })

            elif filename.endswith(('.csv', '.tsv', '.txt')):
                entries = _parse_csv_etymology(filepath)
                for entry in entries:
                    word1 = entry.get('word1', entry.get('source_word', '')).lower().strip()
                    word2 = entry.get('word2', entry.get('target_word', '')).lower().strip()
                    lang1 = entry.get('lang1', entry.get('language1', entry.get('source_language', ''))).lower().strip()
                    lang2 = entry.get('lang2', entry.get('language2', entry.get('target_language', ''))).lower().strip()

                    if word1 and lang1 and word2 and lang2:
                        key1 = (word1, lang1)
                        key2 = (word2, lang2)

                        if key1 not in index:
                            index[key1] = []
                        index[key1].append({
                            'relation_type': 'cognate',
                            'related_word': word2,
                            'related_language': lang2,
                            'source': 'cognet'
                        })

                        if key2 not in index:
                            index[key2] = []
                        index[key2].append({
                            'relation_type': 'cognate',
                            'related_word': word1,
                            'related_language': lang1,
                            'source': 'cognet'
                        })

    return index


def build_etymology_index() -> None:
    """
    Pre-load both etymology-db and CogNet databases into memory for fast lookup.
    Call this once at startup for better performance on repeated queries.
    """
    global _etymology_db_index, _cognet_index, _indexes_loaded

    _etymology_db_index = _load_etymology_db()
    _cognet_index = _load_cognet()
    _indexes_loaded = True


def enrich_etymology(word: str, language: str) -> list[dict]:
    """
    Find all etymology relationships for a given word and language.

    Args:
        word: The word to look up
        language: The language code (e.g., 'en', 'de', 'fr')

    Returns:
        List of dicts matching lexicon.etymology schema with keys:
        - relation_type: 'derived', 'borrowed', 'cognate', etc.
        - related_word: The related word
        - related_language: Language of the related word
        - source: 'etymology-db' or 'cognet'
    """
    global _etymology_db_index, _cognet_index, _indexes_loaded

    # Load indexes if not already loaded
    if not _indexes_loaded:
        build_etymology_index()

    results = []
    key = (word.lower().strip(), language.lower().strip())

    # Look up in etymology-db index
    if key in _etymology_db_index:
        results.extend(_etymology_db_index[key])

    # Look up in CogNet index
    if key in _cognet_index:
        results.extend(_cognet_index[key])

    # Deduplicate results
    seen = set()
    unique_results = []
    for r in results:
        signature = (r['relation_type'], r['related_word'], r['related_language'], r['source'])
        if signature not in seen:
            seen.add(signature)
            unique_results.append(r)

    return unique_results
