"""Ancient Greek morphological analyzer using Wiktextract index."""

import os
import pickle
import unicodedata

from pipeline.wiktextract_loader import load_index

_index = None
_roots_index = None

ROOTS_PKL_PATH = '/mnt/pgdata/morphlex/data/wiktextract_roots.pkl'


def _load_roots_index():
    """Load wiktextract_roots.pkl and return Greek roots."""
    global _roots_index
    if _roots_index is None:
        if os.path.exists(ROOTS_PKL_PATH):
            with open(ROOTS_PKL_PATH, 'rb') as f:
                all_roots = pickle.load(f)
            _roots_index = all_roots.get('grc', {})
        else:
            _roots_index = {}
    return _roots_index


def _normalize_greek(word: str) -> str:
    """Normalize Greek word for matching (remove diacritics/accents)."""
    # Decompose and remove combining marks
    normalized = ''.join(
        c for c in unicodedata.normalize('NFD', word)
        if unicodedata.category(c) != 'Mn'
    )
    return normalized.strip().lower()


def _extract_greek_root(word: str, concept: dict) -> str:
    """
    Extract Ancient Greek root from concept data or wiktextract_roots.pkl.

    Greek uses a root system similar to other Indo-European languages.
    """
    roots_index = _load_roots_index()

    # Try direct lookup
    if word in roots_index and roots_index[word]:
        return roots_index[word][0]

    # Try normalized lookup
    word_normalized = _normalize_greek(word)
    for greek_word, root_list in roots_index.items():
        if root_list and _normalize_greek(greek_word) == word_normalized:
            return root_list[0]

    # Fallback: Try to get root from etymology_templates if available
    etymology = concept.get('etymology_templates', []) if isinstance(concept, dict) else []
    for etym in etymology:
        if isinstance(etym, dict) and etym.get('name') == 'root':
            args = etym.get('args', {})
            # Extract root parts from positions 3+
            root_parts = []
            for i in range(3, 10):
                root_val = args.get(str(i), '')
                if root_val and root_val != '-':
                    root_parts.append(root_val)
            if root_parts:
                return '-'.join(root_parts)

    # No root found - return empty string (not the word itself)
    return ''


def _classify_greek_morph_type(word: str, concept: dict) -> str:
    """
    Classify Ancient Greek morphological type.

    Returns: ROOT, DERIVATION, COMPOUND, COMPOUND_DERIVATION, OTHER, UNKNOWN
    """
    # Check for common Greek compound indicators
    # Many Greek words are compounds (e.g., philosophia = philo + sophia)
    if isinstance(concept, dict):
        etymology = concept.get('etymology', [])
        has_derivation = any(
            isinstance(e, dict) and e.get('type') in ('der', 'inh')
            for e in etymology
        )
        if has_derivation:
            return 'DERIVATION'

    # Check for compound indicators in the word itself
    compound_prefixes = ['φιλο', 'θεο', 'αντι', 'συν', 'μετα', 'επι', 'υπερ', 'υπο']
    word_lower = word.lower() if word else ''
    if any(word_lower.startswith(p) for p in compound_prefixes):
        return 'COMPOUND'

    return 'UNKNOWN'


def analyze_greek(word):
    global _index
    if _index is None:
        _index = load_index('grc')
    results = []
    if word in _index:
        for concept in _index[word]:
            # Handle both dict and string concept formats
            if isinstance(concept, dict):
                pos = concept.get('pos', '')
                english_gloss = concept.get('english_word', '')
                morph_features = {
                    'english_gloss': english_gloss,
                    'definitions': concept.get('definitions', [])[:3]
                }
            else:
                pos = ''
                english_gloss = str(concept)
                morph_features = {'english_gloss': english_gloss}

            root = _extract_greek_root(word, concept)
            morph_type = _classify_greek_morph_type(word, concept)

            results.append({
                'language_code': 'grc',
                'word_native': word,
                'lemma': word,
                'root': root,
                'pos': pos,
                'morph_type': morph_type,
                'derived_from_root': root if morph_type == 'DERIVATION' else None,
                'derivation_mode': None,
                'compound_components': None,
                'morphological_features': morph_features,
                'source_tool': 'wiktextract',
                'confidence': 0.8,
                'word_translit': '',
                'english_concept': english_gloss
            })
    return results
