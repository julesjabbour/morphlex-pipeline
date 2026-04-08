"""Sanskrit morphological analyzer using Wiktextract data.

Uses reverse lookup from Sanskrit words to English concepts via precomputed index.
Sanskrit is a major source language for PIE etymologies.
"""

import os
import pickle
from typing import Optional

from pipeline.wiktextract_loader import load_index


# Module-level cache for loaded index
_sanskrit_index: Optional[dict] = None
_roots_index: Optional[dict] = None
_normalized_lookup: Optional[dict] = None  # {normalized_key: original_key}

ROOTS_PKL_PATH = '/mnt/pgdata/morphlex/data/wiktextract_roots.pkl'


def _load_roots_index():
    """Load wiktextract_roots.pkl and return Sanskrit roots with normalized lookup."""
    global _roots_index, _normalized_lookup
    if _roots_index is None:
        if os.path.exists(ROOTS_PKL_PATH):
            with open(ROOTS_PKL_PATH, 'rb') as f:
                all_roots = pickle.load(f)
            _roots_index = all_roots.get('sa', {})
            # Build normalized lookup table for efficient matching
            # PKL keys may have diacritics, translations may not
            _normalized_lookup = {}
            for sanskrit_word in _roots_index:
                norm = _normalize_sanskrit(sanskrit_word)
                if norm not in _normalized_lookup:
                    _normalized_lookup[norm] = sanskrit_word
        else:
            _roots_index = {}
            _normalized_lookup = {}
    return _roots_index


def _load_sanskrit_data() -> None:
    """Load precomputed Sanskrit reverse lookup index on first call."""
    global _sanskrit_index

    if _sanskrit_index is not None:
        return

    _sanskrit_index = load_index('sa')


def _normalize_sanskrit(word: str) -> str:
    """Normalize Sanskrit word for matching (remove combining marks)."""
    import unicodedata
    # Remove combining marks but keep base characters
    normalized = ''.join(
        c for c in unicodedata.normalize('NFD', word)
        if unicodedata.category(c) != 'Mn'
    )
    return normalized.strip()


def _extract_sanskrit_stems(word: str) -> list:
    """
    Extract potential stems from a Sanskrit word by stripping common endings.

    Sanskrit verb endings: -ति, -नि, -सि, -मि, -न्ति, -थ, -ध्वम्, -ते, etc.
    Sanskrit noun endings: -म्, -ः, -आ, -अम्, -एन, -आय, -आत्, etc.

    Returns list of possible stems (longer stems first).
    """
    stems = []

    # Common verb endings (present tense, etc.)
    verb_endings = ['न्ति', 'ति', 'नि', 'सि', 'मि', 'थ', 'ध्वम्', 'ते', 'न्ते', 'से', 'वहे', 'महे']
    # Common noun/adjective endings
    noun_endings = ['म्', 'ः', 'आ', 'अम्', 'एन', 'आय', 'आत्', 'स्य', 'ई', 'ऊ', 'औ', 'अः', 'आः', 'इ', 'उ']

    all_endings = verb_endings + noun_endings

    for ending in all_endings:
        if word.endswith(ending) and len(word) > len(ending):
            stem = word[:-len(ending)]
            if len(stem) >= 2 and stem not in stems:  # At least 2 chars
                stems.append(stem)

    return stems


def _extract_sanskrit_root(word: str, etymology_links: list) -> str:
    """
    Extract Sanskrit root (dhatu) from wiktextract_roots.pkl or etymology data.

    Sanskrit uses a root (dhatu) system. The adapter receives translated words
    (inflected forms like लिखति "writes") but PKL has base forms/lemmas.
    We try: direct lookup -> normalized lookup -> stem-based lookup.
    """
    global _normalized_lookup
    # First, try direct lookup in wiktextract_roots.pkl
    roots_index = _load_roots_index()
    if word in roots_index and roots_index[word]:
        return roots_index[word][0]  # Return first root

    # Try normalized lookup via precomputed table (O(1) instead of O(n))
    # PKL keys may have diacritics, translations may not
    word_normalized = _normalize_sanskrit(word)
    if _normalized_lookup and word_normalized in _normalized_lookup:
        original_key = _normalized_lookup[word_normalized]
        if roots_index.get(original_key):
            return roots_index[original_key][0]

    # Try stem-based lookup (strip common verb/noun endings)
    # Translated words are often inflected forms; PKL has base forms
    stems = _extract_sanskrit_stems(word)
    for stem in stems:
        # Direct stem lookup
        if stem in roots_index and roots_index[stem]:
            return roots_index[stem][0]
        # Normalized stem lookup
        stem_normalized = _normalize_sanskrit(stem)
        if _normalized_lookup and stem_normalized in _normalized_lookup:
            original_key = _normalized_lookup[stem_normalized]
            if roots_index.get(original_key):
                return roots_index[original_key][0]

    # Fallback: Look for root info in etymology
    for link in etymology_links:
        if link.get('type') == 'root':
            source_word = link.get('source_word', '')
            # Filter out PIE reconstructions (they start with * or contain PIE-specific chars)
            if source_word and not source_word.startswith('*') and not any(c in source_word for c in ['ḱ', 'ǵ', 'ʰ', 'ʷ', '₂', '₃']):
                return source_word

    # No root found - return empty string (not the normalized word)
    return ''


def _classify_sanskrit_morph_type(word: str, etymology_links: list) -> str:
    """
    Classify Sanskrit morphological type.

    Returns: ROOT, DERIVATION, COMPOUND, COMPOUND_DERIVATION, OTHER, UNKNOWN
    """
    has_root_etym = any(l.get('type') == 'root' for l in etymology_links)
    has_derivation_etym = any(l.get('type') in ('der', 'inh') for l in etymology_links)

    if has_root_etym and has_derivation_etym:
        return 'DERIVATION'
    elif has_root_etym:
        return 'ROOT'
    elif has_derivation_etym:
        return 'DERIVATION'
    else:
        return 'UNKNOWN'


def analyze_sanskrit(word: str) -> list[dict]:
    """
    Analyze a Sanskrit word and return morphological analyses.

    Uses Wiktextract data via reverse lookup: finds English entries
    that have the given Sanskrit word as a translation.

    Handles both Devanagari input and romanized/transliterated input.

    Args:
        word: Sanskrit word to analyze (Devanagari or transliterated)

    Returns:
        List of dicts matching the lexicon.entries schema columns
    """
    _load_sanskrit_data()

    results = []

    # Normalize input for matching
    word_normalized = _normalize_sanskrit(word)

    # Direct lookup in Sanskrit index
    matches = _sanskrit_index.get(word, [])

    # If no direct match, try normalized version
    if not matches and word_normalized != word:
        matches = _sanskrit_index.get(word_normalized, [])

    # If still no match, search through index for partial/normalized matches
    if not matches:
        for sanskrit_word, entries in _sanskrit_index.items():
            if _normalize_sanskrit(sanskrit_word) == word_normalized:
                matches.extend(entries)
                break

    # Convert matches to result format
    for match in matches:
        # Build etymology links from Wiktextract data
        # Sanskrit is a major source language for PIE etymologies
        etymology_links = []
        for etym in match.get('etymology', []):
            etym_name = etym.get('name', '')
            etym_args = etym.get('args', {})
            if etym_name in ('inh', 'bor', 'der', 'cog', 'etymon', 'root'):
                # Extract source language and word from etymology template
                source_lang = etym_args.get('2', '')
                source_word = etym_args.get('3', '')
                if source_lang and source_word:
                    etymology_links.append({
                        'type': etym_name,
                        'source_language': source_lang,
                        'source_word': source_word
                    })

        # Extract root and classify morph type
        root = _extract_sanskrit_root(word, etymology_links)
        morph_type = _classify_sanskrit_morph_type(word, etymology_links)

        result = {
            'language_code': 'sa',
            'word_native': word,
            'word_translit': None,  # Could add transliteration if available
            'lemma': word,
            'root': root,
            'pos': match.get('pos', ''),
            'morph_type': morph_type,
            'derived_from_root': root if morph_type == 'DERIVATION' else None,
            'derivation_mode': None,
            'compound_components': None,
            'morphological_features': {
                'english_gloss': match.get('english_word', ''),
                'definitions': match.get('definitions', [])[:3],  # First 3 definitions
                'etymology_links': etymology_links if etymology_links else None,
                'etymology_text': match.get('etymology_text', '') or None
            },
            'source_tool': 'wiktextract'
        }
        results.append(result)

    # Calculate confidence based on number of analyses
    total_analyses = len(results)
    if total_analyses > 0:
        confidence = 1.0 / total_analyses
        for r in results:
            r['confidence'] = confidence

    return results
