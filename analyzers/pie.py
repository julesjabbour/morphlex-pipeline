"""Proto-Indo-European (PIE) morphological analyzer using etymology_index.pkl.

Uses FORWARD lookup: given an English word, find its PIE ancestors from etymology templates.
PIE data is extracted from etymology_templates where source language is 'ine-pro'.
"""

import os
import pickle
from typing import Optional


# Module-level cache for loaded etymology index
_etymology_index: Optional[dict] = None
ETYMOLOGY_INDEX_PATH = '/mnt/pgdata/morphlex/data/etymology_index.pkl'


def _load_etymology_data() -> None:
    """Load etymology index on first call."""
    global _etymology_index

    if _etymology_index is not None:
        return

    if os.path.exists(ETYMOLOGY_INDEX_PATH):
        with open(ETYMOLOGY_INDEX_PATH, 'rb') as f:
            _etymology_index = pickle.load(f)
    else:
        _etymology_index = {}


def analyze_pie(english_word: str) -> list[dict]:
    """
    Forward lookup: given an English word, find its PIE ancestors from etymology templates.

    Searches etymology_index.pkl for templates where the source language is 'ine-pro'.

    Args:
        english_word: English word to look up (e.g., 'water', 'mother')

    Returns:
        List of dicts matching the lexicon.entries schema columns
    """
    _load_etymology_data()

    results = []
    word = english_word.lower().strip()

    entry = _etymology_index.get(word)
    if not entry:
        return results

    # Track seen PIE forms to avoid duplicates
    seen_forms = set()

    for tmpl in entry.get('templates', []):
        if not isinstance(tmpl, dict):
            continue

        args = tmpl.get('args', {})
        if not isinstance(args, dict):
            continue

        # Check for PIE source language in args['2'] position
        src_lang = args.get('2', '')
        src_word = args.get('3', '')

        if src_lang == 'ine-pro' and src_word:
            if src_word in seen_forms:
                continue
            seen_forms.add(src_word)

            relation = tmpl.get('name', '')
            result = {
                'language_code': 'ine-pro',
                'word_native': src_word,
                'word_translit': None,
                'lemma': src_word,
                'pos': '',
                'morphological_features': {
                    'english_gloss': english_word,
                    'relation': relation
                },
                'source_tool': 'wiktextract-etymology',
                'confidence': 0.9
            }
            results.append(result)

    return results
