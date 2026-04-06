"""Ancient Greek analyzer using Wiktextract data.

Performs reverse lookup: Greek word -> English concepts via translation mappings.
"""

from pipeline.wiktextract_loader import load_wiktextract

# Module-level cache for Wiktextract data and reverse index
_wiktextract_data = None
_greek_reverse_index = None

WIKTEXTRACT_PATH = '/mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz'


def _ensure_loaded():
    """Load Wiktextract data and build Greek reverse index on first call."""
    global _wiktextract_data, _greek_reverse_index

    if _greek_reverse_index is not None:
        return

    # Load Wiktextract data filtered to include grc translations
    _wiktextract_data = load_wiktextract(WIKTEXTRACT_PATH, target_langs=['grc'])

    # Build reverse index: Greek word -> list of (english_word, entry_data)
    _greek_reverse_index = {}

    for english_word, entry_data in _wiktextract_data.items():
        greek_translations = entry_data.get('translations', {}).get('grc', [])
        for greek_word in greek_translations:
            if greek_word not in _greek_reverse_index:
                _greek_reverse_index[greek_word] = []
            _greek_reverse_index[greek_word].append({
                'english_word': english_word,
                'pos': entry_data.get('pos', ''),
                'definitions': entry_data.get('definitions', [])
            })


def analyze_greek(word: str) -> list[dict]:
    """
    Analyze an Ancient Greek word via Wiktextract reverse lookup.

    Finds English entries where this Greek word appears as a translation,
    providing semantic/conceptual information about the word.

    Args:
        word: Ancient Greek word to analyze

    Returns:
        List of dicts matching the lexicon.entries schema columns
    """
    _ensure_loaded()

    results = []

    # Look up Greek word in reverse index
    matches = _greek_reverse_index.get(word, [])

    for match in matches:
        result = {
            'language_code': 'grc',
            'word_native': word,
            'lemma': word,  # Greek word itself as lemma
            'pos': match['pos'],
            'english_gloss': match['english_word'],
            'definitions': match['definitions'][:3],  # First 3 definitions
            'morphological_features': {},
            'source_tool': 'wiktextract'
        }
        results.append(result)

    # Calculate confidence based on total analyses
    total_analyses = len(results)
    if total_analyses > 0:
        confidence = 1.0 / total_analyses
        for r in results:
            r['confidence'] = confidence

    return results
