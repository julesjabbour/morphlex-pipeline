"""Ancient Greek morphological analyzer using Wiktextract index."""

from pipeline.wiktextract_loader import load_index

_index = None


def _extract_greek_root(word: str, concept: dict) -> str:
    """
    Extract Ancient Greek root from concept data.

    Greek uses a root system similar to other Indo-European languages.
    """
    # Try to get root from etymology if available
    etymology = concept.get('etymology', []) if isinstance(concept, dict) else []
    for etym in etymology:
        if isinstance(etym, dict) and etym.get('type') == 'root':
            return etym.get('source_word', word)

    # Fallback to word itself
    return word


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
