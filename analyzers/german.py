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


def _get_compound_components(word: str) -> tuple[list[str] | None, float]:
    """
    Use CharSplit to split a German compound word.

    Args:
        word: German word to analyze

    Returns:
        Tuple of (list of compound components, score) if score > 0.3, else (None, 0)
        Lowered threshold from 0.5 to 0.3 to catch more compounds (Problem 6)
    """
    try:
        splits = char_split.split_compound(word)

        if splits and len(splits) > 0:
            # char_split returns list of tuples: (score, part1, part2)
            top_split = splits[0]
            if len(top_split) >= 3:
                score = top_split[0]
                # Lowered threshold to 0.3 for better compound detection
                if score > 0.3:
                    # Return the components
                    components = list(top_split[1:])
                    # Filter out empty strings
                    components = [c for c in components if c]
                    if len(components) > 1:
                        return components, score
    except Exception as e:
        print(f"CharSplit error for '{word}': {e}")

    return None, 0.0


def _classify_german_morph_type(lemma: str, compound_components: list | None, pos: str) -> str:
    """
    Classify German morphological type.

    Returns: ROOT, DERIVATION, COMPOUND, COMPOUND_DERIVATION, OTHER, UNKNOWN
    """
    # Common German derivational suffixes
    deriv_suffixes = [
        'ung', 'heit', 'keit', 'schaft', 'nis', 'tion', 'ismus', 'tät',
        'er', 'in', 'chen', 'lein', 'bar', 'lich', 'ig', 'isch', 'haft'
    ]

    # Common German derivational prefixes
    deriv_prefixes = [
        'un', 'be', 'ge', 'ver', 'er', 'ent', 'zer', 'miss', 'über', 'unter'
    ]

    word_lower = lemma.lower() if lemma else ''
    has_deriv_suffix = any(word_lower.endswith(s) for s in deriv_suffixes)
    has_deriv_prefix = any(word_lower.startswith(p) for p in deriv_prefixes)
    has_derivation = has_deriv_suffix or has_deriv_prefix
    is_compound = compound_components is not None and len(compound_components) > 1

    if is_compound and has_derivation:
        return 'COMPOUND_DERIVATION'
    elif is_compound:
        return 'COMPOUND'
    elif has_derivation:
        return 'DERIVATION'
    elif lemma:
        return 'ROOT'
    else:
        return 'UNKNOWN'


def _extract_german_root(lemma: str, compound_components: list | None) -> str:
    """
    Extract root from German word.

    For compounds, returns the head (usually last component).
    For derivations, strips common affixes.
    """
    if not lemma:
        return ''

    # For compounds, the head is typically the last component
    if compound_components and len(compound_components) > 1:
        return compound_components[-1]

    # Strip common derivational suffixes to get root
    word = lemma
    deriv_suffixes = ['ung', 'heit', 'keit', 'schaft', 'nis', 'tion', 'ismus', 'tät']
    for suffix in deriv_suffixes:
        if word.lower().endswith(suffix) and len(word) > len(suffix) + 2:
            return word[:-len(suffix)]

    return lemma


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
    compound_components, compound_score = _get_compound_components(word)

    # Try DWDSmor analysis
    if _dwdsmor_available:
        try:
            analyses = _dwdsmor_analyzer.analyze(word)

            if analyses:
                confidence = 1.0 / len(analyses)

                for analysis in analyses:
                    parsed = _parse_dwdsmor_tags(str(analysis))
                    lemma = parsed['lemma'] or word

                    # Extract root and classify morph type
                    root = _extract_german_root(lemma, compound_components)
                    morph_type = _classify_german_morph_type(lemma, compound_components, parsed['pos'])

                    # Determine derivation info
                    derived_from_root = root if morph_type in ('DERIVATION', 'COMPOUND_DERIVATION') else None
                    derivation_mode = None
                    if morph_type in ('DERIVATION', 'COMPOUND_DERIVATION'):
                        if any(lemma.lower().endswith(s) for s in ['ung', 'heit', 'keit', 'schaft', 'nis']):
                            derivation_mode = 'suffix'
                        elif any(lemma.lower().startswith(p) for p in ['un', 'be', 'ge', 'ver', 'er']):
                            derivation_mode = 'prefix'

                    result = {
                        'language_code': 'de',
                        'word_native': word,
                        'lemma': lemma,
                        'root': root,
                        'pos': parsed['pos'],
                        'morph_type': morph_type,
                        'derived_from_root': derived_from_root,
                        'derivation_mode': derivation_mode,
                        'compound_components': compound_components,
                        'morphological_features': parsed['features'],
                        'confidence': confidence,
                        'source_tool': 'dwdsmor+charsplit'
                    }
                    results.append(result)

                return results
        except Exception as e:
            print(f"DWDSmor analysis error for '{word}': {e}")

    # Fallback: CharSplit only (when DWDSmor unavailable or returns no results)
    root = _extract_german_root(word, compound_components)
    morph_type = _classify_german_morph_type(word, compound_components, '')

    result = {
        'language_code': 'de',
        'word_native': word,
        'lemma': word,
        'root': root,
        'pos': '',
        'morph_type': morph_type,
        'derived_from_root': root if morph_type in ('DERIVATION', 'COMPOUND_DERIVATION') else None,
        'derivation_mode': None,
        'compound_components': compound_components,
        'morphological_features': {},
        'confidence': 0.5 if compound_components else 0.1,
        'source_tool': 'charsplit'
    }
    results.append(result)

    return results
