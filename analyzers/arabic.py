"""Arabic morphological analyzer using CAMeL Tools."""

from camel_tools.morphology.database import MorphologyDB
from camel_tools.morphology.analyzer import Analyzer


# Initialize the analyzer with the built-in database
_db = MorphologyDB.builtin_db()
_analyzer = Analyzer(_db)


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

        result = {
            'language_code': 'ar',
            'word_native': word,
            'lemma': a.get('lex', ''),
            'root': root,
            'pattern': a.get('atbtok', ''),
            'pos': a.get('pos', ''),
            'morphological_features': morphological_features,
            'confidence': confidence,
            'source_tool': 'camel_tools'
        }
        results.append(result)

    return results
