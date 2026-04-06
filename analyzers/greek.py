"""Ancient Greek morphological analyzer using Wiktextract index."""

from pipeline.wiktextract_loader import load_index

_index = None


def analyze_greek(word):
    global _index
    if _index is None:
        _index = load_index('grc')
    results = []
    if word in _index:
        for concept in _index[word]:
            results.append({
                'language_code': 'grc',
                'word_native': word,
                'lemma': word,
                'root': '',
                'stem': '',
                'pattern': '',
                'pos': '',
                'morphological_features': {},
                'derivation_type': '',
                'compound_components': [],
                'source_tool': 'wiktextract',
                'confidence': 0.8,
                'word_translit': '',
                'english_concept': concept
            })
    return results
