"""German morphological analyzer using DWDSmor and CharSplit."""

from compound_split import char_split

try:
    import dwdsmor
    _dwdsmor_analyzer = dwdsmor.Analyzer()
    _dwdsmor_available = True
except (ImportError, Exception):
    _dwdsmor_available = False


# POS tag mapping from DWDSmor angle-bracket tags
_POS_TAGS = {
    '+NN': 'noun',
    '+NE': 'proper_noun',
    '+V': 'verb',
    '+ADJ': 'adjective',
    '+ADV': 'adverb',
    '+ART': 'article',
    '+PREP': 'preposition',
    '+CONJ': 'conjunction',
    '+PRON': 'pronoun',
    '+PART': 'particle',
    '+INTJ': 'interjection',
    '+NUM': 'numeral',
}


def _parse_dwdsmor_tags(analysis_str: str) -> dict:
    """
    Parse DWDSmor analysis string to extract morphological features.

    Args:
        analysis_str: DWDSmor analysis output with angle-bracket tags

    Returns:
        Dict with 'lemma', 'pos', and 'features' keys
    """
    import re

    result = {
        'lemma': '',
        'pos': '',
        'features': {}
    }

    # Extract all angle-bracket tags
    tags = re.findall(r'<([^>]+)>', analysis_str)

    # Extract lemma (text before first tag)
    lemma_match = re.match(r'^([^<]+)', analysis_str)
    if lemma_match:
        result['lemma'] = lemma_match.group(1).strip()

    # Parse tags
    for tag in tags:
        tag_with_plus = '+' + tag if not tag.startswith('+') else tag

        # Check for POS tag
        for pos_tag, pos_name in _POS_TAGS.items():
            if tag_with_plus == pos_tag or tag == pos_tag.lstrip('+'):
                result['pos'] = pos_name
                break

        # Gender
        if tag in ('Masc', 'Fem', 'Neut'):
            result['features']['gender'] = tag.lower()

        # Number
        if tag in ('Sg', 'Pl'):
            result['features']['number'] = 'singular' if tag == 'Sg' else 'plural'

        # Case
        if tag in ('Nom', 'Gen', 'Dat', 'Acc'):
            result['features']['case'] = tag.lower()

        # Tense
        if tag in ('Pres', 'Past', 'Perf', 'Fut'):
            result['features']['tense'] = tag.lower()

        # Person
        if tag in ('1', '2', '3'):
            result['features']['person'] = tag

        # Mood
        if tag in ('Ind', 'Subj', 'Imp'):
            result['features']['mood'] = tag.lower()

        # Degree (for adjectives)
        if tag in ('Pos', 'Comp', 'Sup'):
            result['features']['degree'] = tag.lower()

        # Definiteness
        if tag in ('Def', 'Indef'):
            result['features']['definiteness'] = tag.lower()

        # Strong/Weak inflection
        if tag in ('St', 'Wk', 'Mix'):
            result['features']['inflection'] = tag.lower()

    return result


def _get_compound_components(word: str) -> list[str] | None:
    """
    Use CharSplit to split a German compound word.

    Args:
        word: German word to analyze

    Returns:
        List of compound components if score > 0.5, else None
    """
    splits = char_split.split_compound(word)

    if splits and len(splits) > 0:
        # char_split returns list of tuples: (score, part1, part2)
        top_split = splits[0]
        if len(top_split) >= 3:
            score = top_split[0]
            if score > 0.5:
                # Return the components
                components = list(top_split[1:])
                # Filter out empty strings
                components = [c for c in components if c]
                if len(components) > 1:
                    return components

    return None


def analyze_german(word: str) -> list[dict]:
    """
    Analyze a German word and return morphological analyses.

    Uses DWDSmor for morphological analysis and CharSplit for compound splitting.
    Falls back to CharSplit only if DWDSmor returns no results.

    Args:
        word: German word to analyze

    Returns:
        List of dicts matching the lexicon.entries schema columns
    """
    results = []
    compound_components = _get_compound_components(word)

    # Try DWDSmor analysis
    if _dwdsmor_available:
        try:
            analyses = _dwdsmor_analyzer.analyze(word)

            if analyses:
                confidence = 1.0 / len(analyses)

                for analysis in analyses:
                    parsed = _parse_dwdsmor_tags(str(analysis))

                    result = {
                        'language_code': 'de',
                        'word_native': word,
                        'lemma': parsed['lemma'] or word,
                        'pos': parsed['pos'],
                        'morphological_features': parsed['features'],
                        'compound_components': compound_components,
                        'confidence': confidence,
                        'source_tool': 'dwdsmor+charsplit'
                    }
                    results.append(result)

                return results
        except Exception as e:
            print(f"DWDSmor analysis error for '{word}': {e}")

    # Fallback: CharSplit only (when DWDSmor unavailable or returns no results)
    result = {
        'language_code': 'de',
        'word_native': word,
        'lemma': word,
        'pos': '',
        'morphological_features': {},
        'compound_components': compound_components,
        'confidence': 0.5 if compound_components else 0.1,
        'source_tool': 'dwdsmor+charsplit'
    }
    results.append(result)

    return results
