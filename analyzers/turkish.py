"""Turkish morphological analyzer using Zeyrek."""

import zeyrek


# Initialize the analyzer
_analyzer = zeyrek.MorphAnalyzer()


def _parse_morphemes(morphemes: list) -> dict:
    """
    Parse Zeyrek morphemes list into structured morphological features.

    Args:
        morphemes: List of morpheme tags from Zeyrek

    Returns:
        Dict of structured morphological features
    """
    features = {}

    # Mapping of Zeyrek morpheme tags to feature categories
    tense_tags = {'Past', 'Pres', 'Fut', 'Aor', 'Prog1', 'Prog2', 'Narr', 'Cond'}
    person_tags = {'A1sg', 'A2sg', 'A3sg', 'A1pl', 'A2pl', 'A3pl'}
    number_tags = {'Sing', 'Plur'}
    case_tags = {'Nom', 'Acc', 'Dat', 'Loc', 'Abl', 'Gen', 'Ins', 'Equ'}
    polarity_tags = {'Pos', 'Neg'}
    voice_tags = {'Pass', 'Caus', 'Recip', 'Reflex'}
    mood_tags = {'Imp', 'Opt', 'Neces', 'Desr'}
    aspect_tags = {'Perf', 'Prog', 'Hab'}

    for morpheme in morphemes:
        tag = str(morpheme)
        if tag in tense_tags:
            features['tense'] = tag
        elif tag in person_tags:
            features['person'] = tag
        elif tag in number_tags:
            features['number'] = tag
        elif tag in case_tags:
            features['case'] = tag
        elif tag in polarity_tags:
            features['polarity'] = tag
        elif tag in voice_tags:
            features['voice'] = tag
        elif tag in mood_tags:
            features['mood'] = tag
        elif tag in aspect_tags:
            features['aspect'] = tag

    return features


def analyze_turkish(word: str) -> list[dict]:
    """
    Analyze a Turkish word and return morphological analyses.

    Args:
        word: Turkish word to analyze

    Returns:
        List of dicts matching the lexicon.entries schema columns
    """
    analyses = _analyzer.analyze(word)

    if not analyses:
        return []

    confidence = 1.0 / len(analyses)
    results = []

    for parse in analyses:
        # parse is a tuple: (word, [(lemma, pos, morphemes), ...])
        # Each analysis is (lemma, pos, morphemes_list)
        word_form, parse_results = parse

        for lemma, pos, morphemes in parse_results:
            morphological_features = _parse_morphemes(morphemes)

            result = {
                'language_code': 'tr',
                'word_native': word,
                'lemma': lemma,
                'root': None,
                'pos': pos,
                'morphological_features': morphological_features,
                'confidence': confidence,
                'source_tool': 'zeyrek'
            }
            results.append(result)

    # Recalculate confidence based on total number of results
    if results:
        confidence = 1.0 / len(results)
        for r in results:
            r['confidence'] = confidence

    return results
