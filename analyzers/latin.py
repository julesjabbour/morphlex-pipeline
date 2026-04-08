"""Latin morphological analyzer using Morpheus and LatMor."""

import subprocess
import re
import unicodedata
import urllib.request
import urllib.error


def _strip_diacritics(text: str) -> str:
    """Remove diacritics/macrons from text (e.g., māter → mater)."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )


# POS tag mapping from Morpheus (uses single-letter codes in <NL> format)
_MORPHEUS_POS_MAP = {
    'V': 'verb',
    'N': 'noun',
    'ADJ': 'adjective',
    'ADV': 'adverb',
    'PREP': 'preposition',
    'CONJ': 'conjunction',
    'PRON': 'pronoun',
    'PART': 'participle',
    'NUM': 'numeral',
    'INTERJ': 'interjection',
}

# LatMor POS tag mapping
_LATMOR_POS_MAP = {
    'V': 'verb',
    'N': 'noun',
    'ADJ': 'adjective',
    'ADV': 'adverb',
    'PREP': 'preposition',
    'CONJ': 'conjunction',
    'PRON': 'pronoun',
    'NUM': 'numeral',
    'INTJ': 'interjection',
}


def _parse_morpheus_lemma(lemma_token: str) -> str:
    """
    Parse Morpheus lemma token to extract clean lemma.

    Morpheus format varies:
    - "scri_bo_,scribo" -> "scribo" (form with underscores, comma, then lemma)
    - "laudo_.laudo" -> "laudo" (form with underscore, dot, then lemma)
    - "amo" -> "amo" (simple lemma)

    The pattern is: underscores mark vowel length in the form,
    then comma or dot separates form from lemma.
    """
    if not lemma_token:
        return ''

    # Priority 1: comma separator (form,lemma)
    if ',' in lemma_token:
        parts = lemma_token.split(',')
        # Take last part (the clean lemma), strip any hash markers
        lemma = parts[-1].strip()
        if '#' in lemma:
            lemma = lemma.split('#')[0]
        return lemma

    # Priority 2: dot separator (form.lemma)
    if '.' in lemma_token:
        parts = lemma_token.split('.')
        lemma = parts[-1].strip()
        return lemma

    # Priority 3: underscore cleanup (remove vowel length markers)
    if '_' in lemma_token:
        # Remove underscores but keep the letters
        lemma = lemma_token.replace('_', '')
        return lemma

    return lemma_token


def _query_morpheus(word: str) -> list[dict]:
    """
    Query Morpheus REST API for Latin morphological analysis.

    Morpheus returns a custom text format (NOT JSON):
    <NL>V scri_bo_,scribo  pres ind act 1st sg        conj3</NL>

    Format: POS form_with_macrons,lemma features... conjugation_info

    Args:
        word: Latin word to analyze

    Returns:
        List of analysis dicts from Morpheus
    """
    results = []

    try:
        # Strip diacritics/macrons (Morpheus expects ASCII Latin)
        clean_word = _strip_diacritics(word)
        # Handle multi-word translations: take only the first word
        if ' ' in clean_word:
            clean_word = clean_word.split()[0]
        if not clean_word:
            return results

        url = f"http://localhost:1315/latin/{clean_word}"
        with urllib.request.urlopen(url, timeout=5) as response:
            text_data = response.read().decode('utf-8')

        # Parse each <NL>...</NL> block
        nl_blocks = re.findall(r'<NL>([^<]+)</NL>', text_data)

        for block in nl_blocks:
            block = block.strip()
            if not block:
                continue

            result = {
                'lemma': '',
                'pos': '',
                'features': {},
                'conjugation': ''
            }

            # Split on whitespace - POS is first token
            tokens = block.split()
            if not tokens:
                continue

            # First token is POS (V, N, ADJ, etc.)
            pos_raw = tokens[0].upper()
            result['pos'] = _MORPHEUS_POS_MAP.get(pos_raw, pos_raw.lower())

            # Second token contains lemma in format: form,lemma or form.lemma
            if len(tokens) > 1:
                result['lemma'] = _parse_morpheus_lemma(tokens[1])

            # Remaining tokens are morphological features and conjugation info
            feature_tokens = tokens[2:] if len(tokens) > 2 else []

            for feat in feature_tokens:
                feat_lower = feat.lower()

                # Capture conjugation info (e.g., conj1, conj3)
                if feat_lower.startswith('conj'):
                    result['conjugation'] = feat_lower
                    continue

                # Skip other dot-separated tokens (e.g., are.vb)
                if '.' in feat:
                    continue

                # Tense
                if feat_lower in ('pres', 'impf', 'fut', 'perf', 'plup', 'futperf'):
                    result['features']['tense'] = feat_lower
                # Mood
                elif feat_lower in ('ind', 'subj', 'imp', 'inf', 'supine', 'gerundive', 'gerund'):
                    result['features']['mood'] = feat_lower
                # Voice
                elif feat_lower in ('act', 'pass', 'mp'):
                    result['features']['voice'] = feat_lower
                # Number
                elif feat_lower in ('sg', 'pl', 'dual'):
                    result['features']['number'] = feat_lower
                # Person
                elif feat_lower in ('1st', '2nd', '3rd'):
                    result['features']['person'] = feat_lower
                # Case
                elif feat_lower in ('nom', 'gen', 'dat', 'acc', 'abl', 'voc', 'loc'):
                    result['features']['case'] = feat_lower
                # Gender
                elif feat_lower in ('masc', 'fem', 'neut'):
                    result['features']['gender'] = feat_lower
                # Degree
                elif feat_lower in ('pos', 'comp', 'superl'):
                    result['features']['degree'] = feat_lower

            if result['lemma']:
                results.append(result)

    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        # Connection error - will fall back to LatMor
        pass

    return results


def _query_latmor(word: str) -> list[dict]:
    """
    Query LatMor via subprocess for Latin morphological analysis.

    Args:
        word: Latin word to analyze

    Returns:
        List of analysis dicts from LatMor
    """
    results = []

    # Strip diacritics/macrons and handle multi-word translations
    clean_word = _strip_diacritics(word)
    if ' ' in clean_word:
        clean_word = clean_word.split()[0]
    if not clean_word:
        return results

    try:
        # Run fst-infl with the word
        proc = subprocess.run(
            ['fst-infl', '/mnt/pgdata/morphlex/data/latmor/latmor.a'],
            input=clean_word,
            capture_output=True,
            text=True,
            timeout=10
        )

        output = proc.stdout.strip()

        # Parse angle-bracket output like: laudare<V><pres><ind><active><sg><3>
        for line in output.split('\n'):
            line = line.strip()
            if not line or line.startswith('no result') or line == word:
                continue

            result = {
                'lemma': '',
                'pos': '',
                'features': {}
            }

            # Extract lemma (text before first <)
            lemma_match = re.match(r'^([^<]+)', line)
            if lemma_match:
                result['lemma'] = lemma_match.group(1).strip()

            # Extract all angle-bracket tags
            tags = re.findall(r'<([^>]+)>', line)

            for tag in tags:
                tag_upper = tag.upper()

                # Check for POS tag
                if tag_upper in _LATMOR_POS_MAP:
                    result['pos'] = _LATMOR_POS_MAP[tag_upper]
                    continue

                # Tense
                if tag.lower() in ('pres', 'impf', 'fut', 'perf', 'plup', 'futperf', 'present', 'imperfect', 'future', 'perfect', 'pluperfect'):
                    result['features']['tense'] = tag.lower()
                    continue

                # Mood
                if tag.lower() in ('ind', 'subj', 'imp', 'inf', 'indicative', 'subjunctive', 'imperative', 'infinitive'):
                    result['features']['mood'] = tag.lower()
                    continue

                # Voice
                if tag.lower() in ('act', 'pass', 'active', 'passive'):
                    result['features']['voice'] = tag.lower()
                    continue

                # Number
                if tag.lower() in ('sg', 'pl', 'singular', 'plural'):
                    result['features']['number'] = tag.lower()
                    continue

                # Person
                if tag in ('1', '2', '3'):
                    result['features']['person'] = tag
                    continue

                # Case
                if tag.lower() in ('nom', 'gen', 'dat', 'acc', 'abl', 'voc', 'loc', 'nominative', 'genitive', 'dative', 'accusative', 'ablative', 'vocative', 'locative'):
                    result['features']['case'] = tag.lower()
                    continue

                # Gender
                if tag.lower() in ('masc', 'fem', 'neut', 'masculine', 'feminine', 'neuter', 'm', 'f', 'n'):
                    result['features']['gender'] = tag.lower()
                    continue

                # Degree (for adjectives/adverbs)
                if tag.lower() in ('pos', 'comp', 'sup', 'positive', 'comparative', 'superlative'):
                    result['features']['degree'] = tag.lower()
                    continue

            if result['lemma']:
                results.append(result)

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass

    return results


def _extract_latin_root(lemma: str, pos: str) -> str:
    """
    Extract Latin root from lemma.

    For verbs, extract the verb stem.
    For nouns/adjectives, return the base form.
    """
    if not lemma:
        return ''

    # For verbs ending in -are, -ere, -ire, extract stem
    if pos == 'verb':
        for ending in ['are', 'ere', 'ire', 'ari', 'eri', 'iri']:
            if lemma.endswith(ending):
                return lemma[:-len(ending)]

    # For nouns/adjectives, strip common endings
    for ending in ['us', 'um', 'a', 'ae', 'is', 'es', 'os']:
        if lemma.endswith(ending) and len(lemma) > len(ending) + 1:
            return lemma[:-len(ending)]

    return lemma


def _disambiguate_latin_parses(morpheus_results: list[dict], latmor_results: list[dict]) -> tuple[dict, float]:
    """
    Disambiguate multiple Latin parses and select the best one.

    Strategy:
    1. Prefer analyses where both tools agree on lemma
    2. Prefer citation forms (nominative for nouns, infinitive/1st sg for verbs)
    3. Prefer more common POS (noun > verb > adjective for ambiguous forms)
    4. Use feature completeness as tiebreaker

    Returns:
        Tuple of (best_result, confidence) where confidence reflects certainty
    """
    if not morpheus_results and not latmor_results:
        return None, 0.0

    # Collect all results with source tags
    all_results = []
    for r in morpheus_results:
        all_results.append(('morpheus', r))
    for r in latmor_results:
        all_results.append(('latmor', r))

    if len(all_results) == 1:
        return all_results[0][1], 0.95  # Single result = high confidence

    # Score each result
    scored = []
    morpheus_lemmas = {r['lemma'].lower() for r in morpheus_results if r.get('lemma')}
    latmor_lemmas = {r['lemma'].lower() for r in latmor_results if r.get('lemma')}
    agreed_lemmas = morpheus_lemmas & latmor_lemmas

    for source, result in all_results:
        score = 0
        lemma = result.get('lemma', '').lower()
        pos = result.get('pos', '')
        features = result.get('features', {})

        # Bonus: lemma agreement between tools (+30 points)
        if lemma in agreed_lemmas:
            score += 30

        # Citation form bonus (+20 points)
        # For nouns: nominative singular
        # For verbs: present active indicative 1st sg, or infinitive
        if pos == 'noun':
            if features.get('case') == 'nom' and features.get('number') == 'sg':
                score += 20
        elif pos == 'verb':
            if features.get('mood') == 'inf':
                score += 20
            elif (features.get('tense') == 'pres' and
                  features.get('voice') == 'act' and
                  features.get('mood') == 'ind' and
                  features.get('person') == '1st' and
                  features.get('number') == 'sg'):
                score += 20

        # POS priority for ambiguous forms (+10 points)
        # Latin morphology: noun forms are more common in text
        pos_priority = {'noun': 15, 'verb': 12, 'adjective': 10, 'adverb': 8}
        score += pos_priority.get(pos, 5)

        # Feature completeness (+1 point per feature, max 5)
        score += min(len(features), 5)

        # Morpheus slightly preferred (more comprehensive) (+2)
        if source == 'morpheus':
            score += 2

        scored.append((score, source, result))

    # Sort by score descending
    scored.sort(key=lambda x: -x[0])

    best_score, best_source, best_result = scored[0]

    # Calculate confidence based on score gap
    if len(scored) > 1:
        second_score = scored[1][0]
        gap = best_score - second_score
        # Large gap = high confidence, small gap = low confidence
        if gap >= 20:
            confidence = 0.95
        elif gap >= 10:
            confidence = 0.85
        elif gap >= 5:
            confidence = 0.75
        else:
            confidence = 0.6  # Ambiguous - multiple valid parses
    else:
        confidence = 0.95

    return best_result, confidence


def _classify_latin_morph_type(lemma: str, pos: str) -> str:
    """
    Classify Latin morphological type.

    Returns: ROOT, DERIVATION, COMPOUND, COMPOUND_DERIVATION, OTHER, UNKNOWN
    """
    if not lemma:
        return 'UNKNOWN'

    lemma_lower = lemma.lower()

    # Common Latin derivational suffixes
    deriv_suffixes = ['tio', 'sio', 'tas', 'tudo', 'tor', 'sor', 'tura', 'sura', 'men', 'mentum']
    # Common Latin derivational prefixes
    deriv_prefixes = ['in', 'ex', 'de', 'con', 'dis', 'per', 'prae', 'pro', 're', 'sub', 'trans']

    has_deriv_suffix = any(lemma_lower.endswith(s) for s in deriv_suffixes)
    has_deriv_prefix = any(lemma_lower.startswith(p) for p in deriv_prefixes)

    if has_deriv_suffix or has_deriv_prefix:
        return 'DERIVATION'
    elif lemma:
        return 'ROOT'
    else:
        return 'UNKNOWN'


def analyze_latin(word: str, return_all: bool = False) -> list[dict]:
    """
    Analyze a Latin word and return morphological analyses.

    Queries both Morpheus REST API and LatMor, then disambiguates to pick
    the best parse. By default returns only the best parse; set return_all=True
    to get all parses with the best one marked.

    Disambiguation strategy:
    - Prefer lemmas where both tools agree
    - Prefer citation forms (nominative for nouns, infinitive for verbs)
    - Use morphological features for tiebreaking

    Args:
        word: Latin word to analyze
        return_all: If True, return all parses; if False (default), return only best

    Returns:
        List of dicts matching the lexicon.entries schema columns
    """
    # Query both sources
    morpheus_results = _query_morpheus(word)
    latmor_results = _query_latmor(word)

    # Disambiguate to find best parse
    best_parse, confidence = _disambiguate_latin_parses(morpheus_results, latmor_results)

    if not return_all and best_parse:
        # Return only the best parse
        lemma = best_parse['lemma']
        pos = best_parse['pos']
        root = _extract_latin_root(lemma, pos)
        morph_type = _classify_latin_morph_type(lemma, pos)

        result = {
            'language_code': 'la',
            'word_native': word,
            'lemma': lemma,
            'root': root,
            'pos': pos,
            'morph_type': morph_type,
            'derived_from_root': root if morph_type == 'DERIVATION' else None,
            'derivation_mode': 'suffix' if morph_type == 'DERIVATION' else None,
            'compound_components': None,
            'morphological_features': best_parse.get('features', {}),
            'source_tool': 'morpheus+latmor',
            'confidence': confidence
        }
        return [result]

    # Return all parses (with best one first and marked)
    results = []
    best_lemma = best_parse['lemma'] if best_parse else None

    # Add best parse first
    if best_parse:
        lemma = best_parse['lemma']
        pos = best_parse['pos']
        root = _extract_latin_root(lemma, pos)
        morph_type = _classify_latin_morph_type(lemma, pos)

        result = {
            'language_code': 'la',
            'word_native': word,
            'lemma': lemma,
            'root': root,
            'pos': pos,
            'morph_type': morph_type,
            'derived_from_root': root if morph_type == 'DERIVATION' else None,
            'derivation_mode': 'suffix' if morph_type == 'DERIVATION' else None,
            'compound_components': None,
            'morphological_features': best_parse.get('features', {}),
            'source_tool': 'morpheus+latmor',
            'confidence': confidence,
            'is_best_parse': True
        }
        results.append(result)

    # Add remaining parses
    for m in morpheus_results:
        if m.get('lemma') == best_lemma:
            continue  # Skip if already added as best
        lemma = m['lemma']
        pos = m['pos']
        root = _extract_latin_root(lemma, pos)
        morph_type = _classify_latin_morph_type(lemma, pos)

        result = {
            'language_code': 'la',
            'word_native': word,
            'lemma': lemma,
            'root': root,
            'pos': pos,
            'morph_type': morph_type,
            'derived_from_root': root if morph_type == 'DERIVATION' else None,
            'derivation_mode': 'suffix' if morph_type == 'DERIVATION' else None,
            'compound_components': None,
            'morphological_features': m['features'],
            'source_tool': 'morpheus',
            'confidence': 0.3,
            'is_best_parse': False
        }
        results.append(result)

    for l in latmor_results:
        if l.get('lemma') == best_lemma:
            continue  # Skip if already added as best
        lemma = l['lemma']
        pos = l['pos']
        root = _extract_latin_root(lemma, pos)
        morph_type = _classify_latin_morph_type(lemma, pos)

        result = {
            'language_code': 'la',
            'word_native': word,
            'lemma': lemma,
            'root': root,
            'pos': pos,
            'morph_type': morph_type,
            'derived_from_root': root if morph_type == 'DERIVATION' else None,
            'derivation_mode': 'suffix' if morph_type == 'DERIVATION' else None,
            'compound_components': None,
            'morphological_features': l['features'],
            'source_tool': 'latmor',
            'confidence': 0.3,
            'is_best_parse': False
        }
        results.append(result)

    return results
