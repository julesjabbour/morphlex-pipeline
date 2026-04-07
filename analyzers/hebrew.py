"""Hebrew morphological analyzer using Wiktextract data.

Uses reverse lookup from Hebrew words to English concepts via precomputed index.
"""

from typing import Optional

from pipeline.wiktextract_loader import load_index


# Module-level cache for loaded index
_hebrew_index: Optional[dict] = None


def _load_hebrew_data() -> None:
    """Load precomputed Hebrew reverse lookup index on first call."""
    global _hebrew_index

    if _hebrew_index is not None:
        return

    _hebrew_index = load_index('he')


def _normalize_hebrew(word: str) -> str:
    """Normalize Hebrew word for matching (remove niqqud/vowel points)."""
    import unicodedata
    # Remove combining marks (niqqud) but keep base consonants
    normalized = ''.join(
        c for c in unicodedata.normalize('NFD', word)
        if unicodedata.category(c) != 'Mn'
    )
    return normalized.strip()


def _extract_hebrew_root(word: str, etymology_links: list) -> str:
    """
    Extract Hebrew root from etymology data if available.

    Hebrew uses a triconsonantal root system similar to Arabic.
    """
    # Look for root info in etymology
    for link in etymology_links:
        if link.get('type') == 'root':
            return link.get('source_word', '')

    # No etymology root found - return empty string (root unknown)
    return ''


def _classify_hebrew_morph_type(word: str, etymology_links: list) -> str:
    """
    Classify Hebrew morphological type.

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


def analyze_hebrew(word: str) -> list[dict]:
    """
    Analyze a Hebrew word and return morphological analyses.

    Uses Wiktextract data via reverse lookup: finds English entries
    that have the given Hebrew word as a translation.

    Args:
        word: Hebrew word to analyze (Hebrew script or transliterated)

    Returns:
        List of dicts matching the lexicon.entries schema columns
    """
    _load_hebrew_data()

    results = []

    # Normalize input for matching
    word_normalized = _normalize_hebrew(word)

    # Direct lookup in Hebrew index
    matches = _hebrew_index.get(word, [])

    # If no direct match, try normalized version
    if not matches and word_normalized != word:
        matches = _hebrew_index.get(word_normalized, [])

    # If still no match, search through index for partial/normalized matches
    if not matches:
        for hebrew_word, entries in _hebrew_index.items():
            if _normalize_hebrew(hebrew_word) == word_normalized:
                matches.extend(entries)
                break

    # Convert matches to result format
    for match in matches:
        # Build etymology links from Wiktextract data
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
        root = _extract_hebrew_root(word, etymology_links)
        morph_type = _classify_hebrew_morph_type(word, etymology_links)

        result = {
            'language_code': 'he',
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
