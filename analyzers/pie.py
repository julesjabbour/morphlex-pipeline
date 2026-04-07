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


def _extract_pie_root(src_word: str) -> str:
    """
    Extract PIE root from reconstructed form.

    PIE roots typically start with * and may have various suffixes.
    """
    if not src_word:
        return ''

    # PIE forms start with * - keep the base root
    word = src_word.lstrip('*')

    # Many PIE roots end with laryngeals (h₁, h₂, h₃) or other suffixes
    # Strip common suffix patterns to get core root
    # Return without asterisk prefix
    return word


def _classify_pie_morph_type(src_word: str, relation: str) -> str:
    """
    Classify PIE morphological type.

    Most PIE forms we retrieve are roots themselves.
    """
    if not src_word:
        return 'UNKNOWN'

    # If it's marked as 'root' in the etymology, it's a ROOT
    if relation == 'root':
        return 'ROOT'

    # Most PIE reconstructions are roots
    # Forms with suffixes like *-ti-, *-trom, etc. are derivations
    deriv_suffixes = ['-ti-', '-trom', '-ter-', '-tor-', '-men-', '-tion']
    word_lower = src_word.lower()
    if any(s in word_lower for s in deriv_suffixes):
        return 'DERIVATION'

    return 'ROOT'


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

            # Extract root and classify morph type
            root = _extract_pie_root(src_word)
            morph_type = _classify_pie_morph_type(src_word, relation)

            result = {
                'language_code': 'ine-pro',
                'word_native': src_word,
                'word_translit': None,
                'lemma': src_word,
                'root': root,
                'pos': '',
                'morph_type': morph_type,
                'derived_from_root': root if morph_type == 'DERIVATION' else None,
                'derivation_mode': None,
                'compound_components': None,
                'morphological_features': {
                    'english_gloss': english_word,
                    'relation': relation
                },
                'source_tool': 'wiktextract-etymology',
                'confidence': 0.9
            }
            results.append(result)

    return results
