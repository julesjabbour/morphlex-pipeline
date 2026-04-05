"""Latin morphological analyzer using Morpheus and LatMor."""

import subprocess
import xml.etree.ElementTree as ET
import re
import urllib.request
import urllib.error


# POS tag mapping from Morpheus
_MORPHEUS_POS_MAP = {
    'verb': 'verb',
    'noun': 'noun',
    'adj': 'adjective',
    'adv': 'adverb',
    'prep': 'preposition',
    'conj': 'conjunction',
    'pron': 'pronoun',
    'part': 'participle',
    'num': 'numeral',
    'interj': 'interjection',
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


def _check_morpheus_reachable() -> bool:
    """Check if Morpheus Docker service is reachable."""
    try:
        # Morpheus API uses /latin/:word endpoint format
        url = "http://localhost:1315/latin/laudo"
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return False


def _query_morpheus(word: str) -> list[dict]:
    """
    Query Morpheus REST API for Latin morphological analysis.

    Args:
        word: Latin word to analyze

    Returns:
        List of analysis dicts from Morpheus
    """
    results = []

    # Check if Morpheus is reachable
    if not _check_morpheus_reachable():
        print("Morpheus not reachable")
        return results

    try:
        url = f"http://localhost:1315/latin/{word}"
        with urllib.request.urlopen(url, timeout=5) as response:
            xml_data = response.read().decode('utf-8')

        # Parse XML response
        root = ET.fromstring(xml_data)

        for analysis in root.findall('.//analysis'):
            result = {
                'lemma': '',
                'stem': '',
                'pos': '',
                'features': {}
            }

            # Extract hdwd (lemma)
            hdwd = analysis.find('.//hdwd')
            if hdwd is not None and hdwd.text:
                result['lemma'] = hdwd.text.strip()

            # Extract stem
            stem = analysis.find('.//stem')
            if stem is not None and stem.text:
                result['stem'] = stem.text.strip()

            # Extract POS
            pos_elem = analysis.find('.//pofs')
            if pos_elem is not None and pos_elem.text:
                pos_raw = pos_elem.text.strip().lower()
                result['pos'] = _MORPHEUS_POS_MAP.get(pos_raw, pos_raw)

            # Extract morphological features
            # Case
            case_elem = analysis.find('.//case')
            if case_elem is not None and case_elem.text:
                result['features']['case'] = case_elem.text.strip().lower()

            # Gender
            gend_elem = analysis.find('.//gend')
            if gend_elem is not None and gend_elem.text:
                result['features']['gender'] = gend_elem.text.strip().lower()

            # Number
            num_elem = analysis.find('.//num')
            if num_elem is not None and num_elem.text:
                result['features']['number'] = num_elem.text.strip().lower()

            # Tense
            tense_elem = analysis.find('.//tense')
            if tense_elem is not None and tense_elem.text:
                result['features']['tense'] = tense_elem.text.strip().lower()

            # Mood
            mood_elem = analysis.find('.//mood')
            if mood_elem is not None and mood_elem.text:
                result['features']['mood'] = mood_elem.text.strip().lower()

            # Voice
            voice_elem = analysis.find('.//voice')
            if voice_elem is not None and voice_elem.text:
                result['features']['voice'] = voice_elem.text.strip().lower()

            # Person
            pers_elem = analysis.find('.//pers')
            if pers_elem is not None and pers_elem.text:
                result['features']['person'] = pers_elem.text.strip()

            if result['lemma']:
                results.append(result)

    except (urllib.error.URLError, urllib.error.HTTPError, ET.ParseError, TimeoutError):
        # Connection error or parse error - will fall back to LatMor
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
