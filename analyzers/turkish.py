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


def _extract_lemma_from_analysis_string(analysis_str: str) -> tuple[str, str]:
    """
    Extract lemma and POS from Zeyrek analysis string.

    Format: [oku:Verb]+[Past:Past]+[A1sg:A1sg] or (okumak_Verb)(-)(...)

    Returns:
        Tuple of (lemma, pos)
    """
    import re

    # Try bracket format: [lemma:POS]+...
    bracket_match = re.match(r'\[([^:]+):([^\]]+)\]', str(analysis_str))
    if bracket_match:
        return bracket_match.group(1), bracket_match.group(2)

    # Try parenthesis format: (lemma_POS)
    paren_match = re.match(r'\(([^_]+)_([^)]+)\)', str(analysis_str))
    if paren_match:
        return paren_match.group(1), paren_match.group(2)

    return str(analysis_str), None


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

    results = []

    # Zeyrek returns list of Parse namedtuples with attributes:
    # .word, .lemma, .pos, .morphemes, .formatted
    for parse in (analyses[0] if analyses and isinstance(analyses[0], list) else analyses):
        # Handle Parse namedtuple objects (has .lemma, .pos, .morphemes attributes)
        if hasattr(parse, 'lemma') and hasattr(parse, 'pos'):
            morphemes = parse.morphemes if hasattr(parse, 'morphemes') and parse.morphemes else []
            morphological_features = _parse_morphemes(morphemes)

            result = {
                'language_code': 'tr',
                'word_native': word,
                'lemma': parse.lemma,
                'root': None,
                'pos': parse.pos,
                'morphological_features': morphological_features,
                'confidence': 0.0,
                'source_tool': 'zeyrek'
            }
            results.append(result)

    # Calculate confidence based on total number of results
    if results:
        confidence = 1.0 / len(results)
        for r in results:
            r['confidence'] = confidence

    return results
