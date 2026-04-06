"""Hebrew morphological analyzer using Wiktextract data.

Uses reverse lookup from Hebrew words to English concepts via translation mappings.
"""

from typing import Optional

from pipeline.wiktextract_loader import load_wiktextract


# Module-level cache for loaded data
_wiktextract_data: Optional[dict] = None
_hebrew_index: Optional[dict] = None  # Hebrew word -> list of English entries


def _load_hebrew_data() -> None:
    """Load Wiktextract data and build Hebrew reverse lookup index on first call."""
    global _wiktextract_data, _hebrew_index

    if _wiktextract_data is not None:
        return

    filepath = '/mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz'
    _wiktextract_data = load_wiktextract(filepath, target_langs=['he'])

    # Build reverse index: Hebrew word -> list of (english_word, entry_data)
    _hebrew_index = {}
    for english_word, entry in _wiktextract_data.items():
        hebrew_translations = entry.get('translations', {}).get('he', [])
        for hebrew_word in hebrew_translations:
            if hebrew_word not in _hebrew_index:
                _hebrew_index[hebrew_word] = []
            _hebrew_index[hebrew_word].append({
                'english_word': english_word,
                'pos': entry.get('pos', ''),
                'definitions': entry.get('definitions', []),
                'etymology': entry.get('etymology', []),
                'etymology_text': entry.get('etymology_text', '')
            })


def _normalize_hebrew(word: str) -> str:
    """Normalize Hebrew word for matching (remove niqqud/vowel points)."""
    import unicodedata
    # Remove combining marks (niqqud) but keep base consonants
    normalized = ''.join(
        c for c in unicodedata.normalize('NFD', word)
        if unicodedata.category(c) != 'Mn'
    )
    return normalized.strip()


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
            if etym_name in ('inh', 'bor', 'der', 'cog', 'etymon'):
                # Extract source language and word from etymology template
                source_lang = etym_args.get('2', '')
                source_word = etym_args.get('3', '')
                if source_lang and source_word:
                    etymology_links.append({
                        'type': etym_name,
                        'source_language': source_lang,
                        'source_word': source_word
                    })

        result = {
            'language_code': 'he',
            'word_native': word,
            'word_translit': None,  # Could add transliteration if available
            'lemma': word,
            'pos': match.get('pos', ''),
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
