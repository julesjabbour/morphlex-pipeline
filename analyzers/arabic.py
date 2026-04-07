"""Arabic morphological analyzer using CAMeL Tools."""

from camel_tools.morphology.database import MorphologyDB
from camel_tools.morphology.analyzer import Analyzer


# Initialize the analyzer with the built-in database
_db = MorphologyDB.builtin_db()
_analyzer = Analyzer(_db)


def _classify_arabic_morph_type(root: str, pattern: str, pos: str) -> str:
    """
    Classify Arabic morphological type based on root and pattern.

    Returns: ROOT, DERIVATION, COMPOUND, COMPOUND_DERIVATION, OTHER, UNKNOWN
    """
    has_root = bool(root)
    has_pattern = bool(pattern)

    # Arabic uses root+pattern system - if we have both, it's a derivation
    if has_root and has_pattern:
        return 'DERIVATION'
    elif has_root:
        return 'ROOT'
    elif has_pattern:
        return 'OTHER'
    else:
        return 'UNKNOWN'


def analyze_arabic(word: str) -> list[dict]:
    """
    Analyze an Arabic word and return morphological analyses.

    Args:
        word: Arabic word to analyze

    Returns:
        List of dicts matching the lexicon.entries schema columns
    """
    analyses = _analyzer.analyze(word)

    if not analyses:
        return []

    confidence = 1.0 / len(analyses)
    results = []

    for a in analyses:
        # Extract morphological features
        morphological_features = {}
        feature_keys = ['gen', 'num', 'cas', 'stt', 'per', 'asp', 'vox', 'mod']
        for key in feature_keys:
            if key in a and a[key]:
                morphological_features[key] = a[key]

        # Format root as dot-separated
        root = a.get('root', '')
        if root:
            root = '.'.join(root)

        pattern = a.get('atbtok', '')
        pos = a.get('pos', '')

        # Classify morphological type
        morph_type = _classify_arabic_morph_type(root, pattern, pos)

        # Store diacritic form for deduplication
        diac_form = a.get('diac', '')

        result = {
            'language_code': 'ar',
            'word_native': word,
            'lemma': a.get('lex', ''),
            'root': root,
            'pattern': pattern,
            'pos': pos,
            'morph_type': morph_type,
            'derived_from_root': root if morph_type == 'DERIVATION' else None,
            'derivation_mode': 'root+pattern' if pattern else None,
            'compound_components': None,  # Arabic doesn't typically use compounding
            'morphological_features': morphological_features,
            'confidence': confidence,
            'source_tool': 'camel_tools',
            '_diac_form': diac_form  # Internal field for deduplication
        }
        results.append(result)

    return results
