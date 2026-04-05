"""Latin morphological analyzer using Morpheus and LatMor."""

import subprocess
import re
import urllib.request
import urllib.error


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


def _query_morpheus(word: str) -> list[dict]:
    """
    Query Morpheus REST API for Latin morphological analysis.

    Morpheus returns a custom text format (NOT JSON):
    <NL>V laudo_.laudo  pres ind act 1st sg        conj1.are.vb</NL>

    Args:
        word: Latin word to analyze

    Returns:
        List of analysis dicts from Morpheus
    """
    results = []

    try:
        url = f"http://localhost:1315/latin/{word}"
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
                'features': {}
            }

            # Split on whitespace - POS is first token
            tokens = block.split()
            if not tokens:
                continue

            # First token is POS (V, N, ADJ, etc.)
            pos_raw = tokens[0].upper()
            result['pos'] = _MORPHEUS_POS_MAP.get(pos_raw, pos_raw.lower())

            # Second token contains lemma: format is "word_.lemma" - extract part after the dot
            if len(tokens) > 1:
                lemma_part = tokens[1]
                # Lemma is the part after the dot (e.g., "laudo_.laudo" -> "laudo")
                if '.' in lemma_part:
                    result['lemma'] = lemma_part.split('.', 1)[1]
                else:
                    result['lemma'] = lemma_part

            # Remaining tokens (before the conjugation info) are morphological features
            # Features like: pres ind act 1st sg
            feature_tokens = tokens[2:] if len(tokens) > 2 else []

            for feat in feature_tokens:
                feat_lower = feat.lower()

                # Skip conjugation info (e.g., conj1.are.vb)
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

    try:
        # Run fst-infl with the word
        proc = subprocess.run(
            ['fst-infl', '/mnt/pgdata/morphlex/data/latmor/latmor.a'],
            input=word,
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


def analyze_latin(word: str) -> list[dict]:
    """
    Analyze a Latin word and return morphological analyses.

    Queries both Morpheus REST API and LatMor, merging results from both sources.
    Falls back to LatMor only if Morpheus connection fails.

    Args:
        word: Latin word to analyze

    Returns:
        List of dicts matching the lexicon.entries schema columns
    """
    results = []

    # Query both sources
    morpheus_results = _query_morpheus(word)
    latmor_results = _query_latmor(word)

    # Convert Morpheus results
    for m in morpheus_results:
        result = {
            'language_code': 'la',
            'word_native': word,
            'lemma': m['lemma'],
            'pos': m['pos'],
            'morphological_features': m['features'],
            'source_tool': 'morpheus'
        }
        results.append(result)

    # Convert LatMor results
    for l in latmor_results:
        result = {
            'language_code': 'la',
            'word_native': word,
            'lemma': l['lemma'],
            'pos': l['pos'],
            'morphological_features': l['features'],
            'source_tool': 'latmor'
        }
        results.append(result)

    # Calculate confidence based on total analyses
    total_analyses = len(results)
    if total_analyses > 0:
        confidence = 1.0 / total_analyses
        for r in results:
            r['confidence'] = confidence

    return results
