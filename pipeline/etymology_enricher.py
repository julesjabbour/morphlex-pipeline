"""
Etymology Enricher module for morphlex pipeline.

Loads etymology data from etymology-db (4.2M relationships) and CogNet (8.1M cognates)
to find etymological ancestors, cognates, and derivation chains across languages.
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

# Data paths on VM
ETYMOLOGY_DB_PATH = "/mnt/pgdata/morphlex/data/etymology-db/"
COGNET_PATH = "/mnt/pgdata/morphlex/data/CogNet/"


def _parse_json_file(filepath: str) -> list[dict]:
    """Parse a JSON file containing etymology/cognate entries."""
    entries = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                entries = data
            elif isinstance(data, dict):
                # Handle dict with 'entries', 'relations', 'cognates', or 'data' key
                for key in ('entries', 'relations', 'cognates', 'data'):
                    if key in data:
                        entries = data[key]
                        break
    except (json.JSONDecodeError, IOError) as e:
        pass
    return entries


def _parse_tsv_file(filepath: str) -> list[dict]:
    """Parse a TSV/CSV file containing etymology/cognate entries."""
    entries = []
    delimiter = '\t' if filepath.endswith('.tsv') else ','
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Try to detect header
            sample = f.read(4096)
            f.seek(0)
            has_header = csv.Sniffer().has_header(sample) if sample.strip() else True

            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                entry = {}
                for key, value in row.items():
                    if key is None:
                        continue
                    key_lower = key.lower().strip()
                    # Normalize field names
                    if 'source' in key_lower and 'word' in key_lower:
                        entry['source_word'] = value
                    elif 'target' in key_lower and 'word' in key_lower:
                        entry['target_word'] = value
                    elif 'source' in key_lower and 'lang' in key_lower:
                        entry['source_language'] = value
                    elif 'target' in key_lower and 'lang' in key_lower:
                        entry['target_language'] = value
                    elif 'relation' in key_lower or key_lower == 'type':
                        entry['relation_type'] = value
                    elif key_lower in ('word1', 'word_1', 'form1'):
                        entry['source_word'] = value
                    elif key_lower in ('word2', 'word_2', 'form2'):
                        entry['target_word'] = value
                    elif key_lower in ('lang1', 'lang_1', 'language1', 'lang'):
                        entry['source_language'] = value
                    elif key_lower in ('lang2', 'lang_2', 'language2'):
                        entry['target_language'] = value
                    else:
                        entry[key_lower] = value
                if entry.get('source_word') or entry.get('target_word'):
                    entries.append(entry)
    except (csv.Error, IOError) as e:
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
                entries = _parse_json_file(filepath)
            elif filename.endswith(('.csv', '.tsv', '.txt')):
                entries = _parse_tsv_file(filepath)

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
                entries = _parse_json_file(filepath)
            elif filename.endswith(('.csv', '.tsv', '.txt')):
                entries = _parse_tsv_file(filepath)
            else:
                continue

            for entry in entries:
                word1 = entry.get('word1', entry.get('source_word', entry.get('form1', ''))).lower().strip()
                word2 = entry.get('word2', entry.get('target_word', entry.get('form2', ''))).lower().strip()
                lang1 = entry.get('lang1', entry.get('language1', entry.get('source_language', ''))).lower().strip()
                lang2 = entry.get('lang2', entry.get('language2', entry.get('target_language', ''))).lower().strip()

                if word1 and lang1 and word2 and lang2:
                    # Add both directions for cognates (symmetric relationship)
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


def build_etymology_index() -> tuple[int, int]:
    """
    Pre-load both etymology-db and CogNet databases into memory for fast lookup.
    Call this once at startup for better performance on repeated queries.

    Returns:
        Tuple of (etymology_db_count, cognet_count)
    """
    global _etymology_db_index, _cognet_index, _indexes_loaded

    _etymology_db_index = _load_etymology_db()
    _cognet_index = _load_cognet()
    _indexes_loaded = True

    return len(_etymology_db_index), len(_cognet_index)


def get_etymological_ancestors(word: str, language: str, max_depth: int = 5) -> list[dict]:
    """
    Find etymological ancestors (words this word derived from).

    Args:
        word: The word to look up
        language: The language code (e.g., 'en', 'de', 'fr')
        max_depth: Maximum depth of ancestor chain to follow

    Returns:
        List of dicts with ancestor information, ordered from closest to furthest
    """
    global _etymology_db_index, _indexes_loaded

    if not _indexes_loaded:
        build_etymology_index()

    ancestors = []
    visited = set()
    queue = [(word.lower().strip(), language.lower().strip(), 0)]

    while queue:
        current_word, current_lang, depth = queue.pop(0)

        if depth > max_depth:
            continue

        key = (current_word, current_lang)
        if key in visited:
            continue
        visited.add(key)

        if key in _etymology_db_index:
            for rel in _etymology_db_index[key]:
                if rel['relation_type'] in ('derived_from', 'borrowed_from', 'inherited_from'):
                    ancestor = {
                        'word': rel['related_word'],
                        'language': rel['related_language'],
                        'relation_type': rel['relation_type'],
                        'depth': depth + 1,
                        'source': rel['source']
                    }
                    ancestors.append(ancestor)

                    if depth + 1 < max_depth:
                        queue.append((rel['related_word'], rel['related_language'], depth + 1))

    return ancestors


def get_cognates(word: str, language: str) -> list[dict]:
    """
    Find cognates of a word in other languages.

    Args:
        word: The word to look up
        language: The language code

    Returns:
        List of dicts with cognate information
    """
    global _cognet_index, _indexes_loaded

    if not _indexes_loaded:
        build_etymology_index()

    cognates = []
    key = (word.lower().strip(), language.lower().strip())

    if key in _cognet_index:
        for rel in _cognet_index[key]:
            if rel['relation_type'] == 'cognate':
                cognates.append({
                    'word': rel['related_word'],
                    'language': rel['related_language'],
                    'relation_type': 'cognate',
                    'source': rel['source']
                })

    return cognates


def get_derivation_chain(word: str, language: str) -> list[dict]:
    """
    Build the complete derivation chain for a word (both ancestors and descendants).

    Args:
        word: The word to look up
        language: The language code

    Returns:
        List of dicts representing the derivation chain
    """
    global _etymology_db_index, _indexes_loaded

    if not _indexes_loaded:
        build_etymology_index()

    chain = []
    key = (word.lower().strip(), language.lower().strip())

    if key in _etymology_db_index:
        for rel in _etymology_db_index[key]:
            chain.append({
                'word': rel['related_word'],
                'language': rel['related_language'],
                'relation_type': rel['relation_type'],
                'source': rel['source']
            })

    return chain


def enrich_etymology(word: str, language: str) -> list[dict]:
    """
    Find all etymology relationships for a given word and language.

    Matches the standard adapter pattern - returns list of dicts with standardized fields.

    Args:
        word: The word to look up
        language: The language code (e.g., 'en', 'de', 'fr')

    Returns:
        List of dicts with keys:
        - relation_type: 'derived', 'borrowed', 'cognate', 'inherited', etc.
        - related_word: The related word
        - related_language: Language of the related word
        - source: 'etymology-db' or 'cognet'
    """
    global _etymology_db_index, _cognet_index, _indexes_loaded

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


def test_etymology() -> dict:
    """
    Test etymology enrichment with 5 words across multiple languages.

    Returns:
        Dict with test results including counts and sample data
    """
    print("=== ETYMOLOGY ENRICHER TEST ===")
    print(f"Etymology DB path: {ETYMOLOGY_DB_PATH}")
    print(f"CogNet path: {COGNET_PATH}")
    print(f"Etymology DB exists: {os.path.exists(ETYMOLOGY_DB_PATH)}")
    print(f"CogNet exists: {os.path.exists(COGNET_PATH)}")

    # List directory contents if they exist
    if os.path.exists(ETYMOLOGY_DB_PATH):
        files = list(Path(ETYMOLOGY_DB_PATH).rglob('*'))[:10]
        print(f"Etymology DB files (first 10): {[str(f) for f in files]}")

    if os.path.exists(COGNET_PATH):
        files = list(Path(COGNET_PATH).rglob('*'))[:10]
        print(f"CogNet files (first 10): {[str(f) for f in files]}")

    # Build indexes
    print("\nBuilding indexes...")
    etym_count, cognet_count = build_etymology_index()
    print(f"Etymology DB entries: {etym_count}")
    print(f"CogNet entries: {cognet_count}")

    # Test words across multiple languages
    test_cases = [
        ('water', 'en'),      # English - common word with PIE root
        ('wasser', 'de'),     # German - cognate of water
        ('aqua', 'la'),       # Latin - different PIE root
        ('mother', 'en'),     # English - universal concept
        ('pater', 'la'),      # Latin - father
    ]

    results = {
        'index_counts': {
            'etymology_db': etym_count,
            'cognet': cognet_count
        },
        'test_results': []
    }

    print("\n=== TEST RESULTS ===")
    for word, lang in test_cases:
        print(f"\n--- {word} ({lang}) ---")

        # Get all enrichments
        enrichments = enrich_etymology(word, lang)
        ancestors = get_etymological_ancestors(word, lang)
        cognates = get_cognates(word, lang)
        chain = get_derivation_chain(word, lang)

        test_result = {
            'word': word,
            'language': lang,
            'enrichments_count': len(enrichments),
            'ancestors_count': len(ancestors),
            'cognates_count': len(cognates),
            'chain_count': len(chain)
        }

        print(f"  Total enrichments: {len(enrichments)}")
        print(f"  Ancestors: {len(ancestors)}")
        print(f"  Cognates: {len(cognates)}")
        print(f"  Derivation chain: {len(chain)}")

        if enrichments:
            print(f"  Sample enrichment: {enrichments[0]}")
            test_result['sample'] = enrichments[0]

        results['test_results'].append(test_result)

    print("\n=== TEST COMPLETE ===")
    return results


if __name__ == '__main__':
    test_etymology()
