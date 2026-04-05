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

    # Zeyrek returns list of tuples: (word, analyses_list)
    # Each analysis in analyses_list can be a string or structured object
    for word_result in analyses:
        if isinstance(word_result, tuple) and len(word_result) >= 2:
            word_form, analyses_list = word_result[0], word_result[1]

            for analysis in analyses_list:
                # Handle string format analysis
                if isinstance(analysis, str):
                    lemma, pos = _extract_lemma_from_analysis_string(analysis)
                    result = {
                        'language_code': 'tr',
                        'word_native': word,
                        'lemma': lemma,
                        'root': None,
                        'pos': pos,
                        'morphological_features': {},
                        'confidence': 0.0,
                        'source_tool': 'zeyrek'
                    }
                    results.append(result)
                # Handle object with formatted attribute
                elif hasattr(analysis, 'formatted'):
                    lemma, pos = _extract_lemma_from_analysis_string(analysis.formatted)
                    result = {
                        'language_code': 'tr',
                        'word_native': word,
                        'lemma': lemma,
                        'root': None,
                        'pos': pos,
                        'morphological_features': {},
                        'confidence': 0.0,
                        'source_tool': 'zeyrek'
                    }
                    results.append(result)
                # Handle tuple/list item format
                elif isinstance(analysis, (tuple, list)) and len(analysis) >= 2:
                    lemma = analysis[0]
                    pos = analysis[1] if len(analysis) > 1 else None
                    morphemes = analysis[2] if len(analysis) > 2 else []

                    # Extract clean lemma if it has POS suffix
                    clean_lemma = lemma
                    if isinstance(lemma, str) and '_' in lemma:
                        parts = lemma.rsplit('_', 1)
                        clean_lemma = parts[0]
                        if pos is None:
                            pos = parts[1]

                    morphological_features = _parse_morphemes(morphemes) if morphemes else {}
                    result = {
                        'language_code': 'tr',
                        'word_native': word,
                        'lemma': clean_lemma,
                        'root': None,
                        'pos': pos,
                        'morphological_features': morphological_features,
                        'confidence': 0.0,
                        'source_tool': 'zeyrek'
                    }
                    results.append(result)
        # Handle WordAnalysis named tuple format
        elif hasattr(word_result, 'lemmas'):
            lemmas = word_result.lemmas if hasattr(word_result, 'lemmas') else []
            morpheme_lists = word_result.morphemes if hasattr(word_result, 'morphemes') else []

            for i, lemma in enumerate(lemmas):
                pos = None
                clean_lemma = lemma
                if '_' in lemma:
                    parts = lemma.rsplit('_', 1)
                    clean_lemma = parts[0]
                    pos = parts[1] if len(parts) > 1 else None

                morphemes = morpheme_lists[i] if i < len(morpheme_lists) else []
                morphological_features = _parse_morphemes(morphemes)

                result = {
                    'language_code': 'tr',
                    'word_native': word,
                    'lemma': clean_lemma,
                    'root': None,
                    'pos': pos,
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
