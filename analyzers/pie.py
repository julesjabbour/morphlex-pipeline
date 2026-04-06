"""Proto-Indo-European (PIE) morphological analyzer using Wiktextract data.

Uses reverse lookup from PIE reconstructed forms to English concepts via precomputed index.
PIE data is extracted from etymology_templates, not translations.
"""

from typing import Optional

from pipeline.wiktextract_loader import load_index


# Module-level cache for loaded index
_pie_index: Optional[dict] = None


def _load_pie_data() -> None:
    """Load precomputed PIE reverse lookup index on first call."""
    global _pie_index

    if _pie_index is not None:
        return

    _pie_index = load_index('ine-pro')


def analyze_pie(word: str) -> list[dict]:
    """
    Analyze a Proto-Indo-European reconstructed form and return associated English concepts.

    Uses Wiktextract data via reverse lookup: finds English entries
    that have the given PIE form in their etymology.

    Args:
        word: PIE reconstructed form (e.g., '*wódr̥', '*ph₂tḗr')

    Returns:
        List of dicts matching the lexicon.entries schema columns
    """
    _load_pie_data()

    results = []

    # Direct lookup in PIE index
    matches = _pie_index.get(word, [])

    # If no direct match, try without leading asterisk
    if not matches and word.startswith('*'):
        matches = _pie_index.get(word[1:], [])

    # If still no match, try with leading asterisk
    if not matches and not word.startswith('*'):
        matches = _pie_index.get('*' + word, [])

    # Convert matches to result format
    for match in matches:
        # Build etymology links from Wiktextract data
        etymology_links = []
        for etym in match.get('etymology', []):
            etym_name = etym.get('name', '')
            etym_args = etym.get('args', {})
            if etym_name in ('inh', 'bor', 'der', 'cog', 'root', 'etymon'):
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
            'language_code': 'ine-pro',
            'word_native': word,
            'word_translit': None,
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
