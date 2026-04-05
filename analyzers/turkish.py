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

    results = []

    # Zeyrek returns list of WordAnalysis named tuples
    # Each WordAnalysis has: word, lemmas, roots, pos_tags, morphemes, formatted
    for analysis in analyses:
        # Handle both old tuple format and new WordAnalysis format
        if hasattr(analysis, 'lemmas'):
            # New Zeyrek format: WordAnalysis named tuple
            lemmas = analysis.lemmas if hasattr(analysis, 'lemmas') else []
            morpheme_lists = analysis.morphemes if hasattr(analysis, 'morphemes') else []

            for i, lemma in enumerate(lemmas):
                # Extract POS from lemma if present (e.g., "okumak_Verb" -> "Verb")
                pos = None
                clean_lemma = lemma
                if '_' in lemma:
                    parts = lemma.rsplit('_', 1)
                    clean_lemma = parts[0]
                    pos = parts[1] if len(parts) > 1 else None

                # Get morphemes for this analysis if available
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
        elif isinstance(analysis, tuple) and len(analysis) >= 2:
            # Old format: (word, [(lemma, pos, morphemes), ...])
            word_form, parse_results = analysis
            for item in parse_results:
                if len(item) >= 3:
                    lemma, pos, morphemes = item[0], item[1], item[2]
                elif len(item) >= 2:
                    lemma, pos, morphemes = item[0], item[1], []
                else:
                    continue

                morphological_features = _parse_morphemes(morphemes)
                result = {
                    'language_code': 'tr',
                    'word_native': word,
                    'lemma': lemma,
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
