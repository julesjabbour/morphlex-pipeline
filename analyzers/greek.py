"""Ancient Greek morphological analyzer using Morpheus (primary) and Wiktextract (fallback)."""

import os
import pickle
import re
import unicodedata
import urllib.request
import urllib.error

from pipeline.wiktextract_loader import load_index

_index = None
_roots_index = None
_normalized_lookup = None  # {normalized_key: original_key}

ROOTS_PKL_PATH = '/mnt/pgdata/morphlex/data/wiktextract_roots.pkl'
MORPHEUS_GREEK_URL = 'http://localhost:1315/greek/'


def _strip_diacritics(text: str) -> str:
    """Remove diacritics/accents from text for Morpheus lookup."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )


def _query_morpheus_greek(word: str) -> list[dict]:
    """
    Query Morpheus REST API for Ancient Greek morphological analysis.

    Same pattern as Latin adapter - Morpheus returns custom text format:
    <NL>V λύω  pres ind act 1st sg</NL>

    Args:
        word: Greek word to analyze

    Returns:
        List of analysis dicts from Morpheus
    """
    results = []

    try:
        # Strip diacritics for Morpheus lookup (may need original Greek chars)
        clean_word = _strip_diacritics(word)
        # Handle multi-word translations: take only the first word
        if ' ' in clean_word:
            clean_word = clean_word.split()[0]
        if not clean_word:
            return results

        url = f"{MORPHEUS_GREEK_URL}{clean_word}"
        with urllib.request.urlopen(url, timeout=5) as response:
            text_data = response.read().decode('utf-8')

        # Parse each <NL>...</NL> block (same format as Latin)
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
            pos_map = {
                'V': 'verb', 'N': 'noun', 'ADJ': 'adjective',
                'ADV': 'adverb', 'PREP': 'preposition', 'CONJ': 'conjunction',
                'PRON': 'pronoun', 'PART': 'participle', 'NUM': 'numeral'
            }
            result['pos'] = pos_map.get(pos_raw, pos_raw.lower())

            # Second token contains lemma - extract part after dot if present
            if len(tokens) > 1:
                lemma_part = tokens[1]
                if '.' in lemma_part:
                    result['lemma'] = lemma_part.split('.', 1)[1]
                else:
                    result['lemma'] = lemma_part

            # Parse morphological features from remaining tokens
            for feat in tokens[2:] if len(tokens) > 2 else []:
                feat_lower = feat.lower()
                if '.' in feat:  # Skip conjugation info
                    continue
                if feat_lower in ('pres', 'impf', 'fut', 'perf', 'plup', 'aor'):
                    result['features']['tense'] = feat_lower
                elif feat_lower in ('ind', 'subj', 'imp', 'inf', 'opt', 'part'):
                    result['features']['mood'] = feat_lower
                elif feat_lower in ('act', 'mid', 'pass', 'mp'):
                    result['features']['voice'] = feat_lower
                elif feat_lower in ('sg', 'pl', 'dual'):
                    result['features']['number'] = feat_lower
                elif feat_lower in ('1st', '2nd', '3rd'):
                    result['features']['person'] = feat_lower
                elif feat_lower in ('nom', 'gen', 'dat', 'acc', 'voc'):
                    result['features']['case'] = feat_lower
                elif feat_lower in ('masc', 'fem', 'neut'):
                    result['features']['gender'] = feat_lower

            if result['lemma']:
                results.append(result)

    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        # Connection error - will fall back to pkl
        pass

    return results


def _load_roots_index():
    """Load wiktextract_roots.pkl and return Greek roots with normalized lookup."""
    global _roots_index, _normalized_lookup
    if _roots_index is None:
        if os.path.exists(ROOTS_PKL_PATH):
            with open(ROOTS_PKL_PATH, 'rb') as f:
                all_roots = pickle.load(f)
            _roots_index = all_roots.get('grc', {})
            # Build normalized lookup table for efficient matching
            # PKL keys may have diacritics, translations may not
            _normalized_lookup = {}
            for greek_word in _roots_index:
                norm = _normalize_greek(greek_word)
                if norm not in _normalized_lookup:
                    _normalized_lookup[norm] = greek_word
        else:
            _roots_index = {}
            _normalized_lookup = {}
    return _roots_index


def _normalize_greek(word: str) -> str:
    """Normalize Greek word for matching (remove diacritics/accents)."""
    # Decompose and remove combining marks
    normalized = ''.join(
        c for c in unicodedata.normalize('NFD', word)
        if unicodedata.category(c) != 'Mn'
    )
    return normalized.strip().lower()


def _extract_greek_root_from_lemma(lemma: str, pos: str) -> str:
    """
    Extract Greek root from lemma (similar to Latin pattern).

    For verbs, extract the verb stem.
    For nouns/adjectives, return the base form.
    """
    if not lemma:
        return ''

    # For verbs ending in common Greek infinitive endings
    if pos == 'verb':
        for ending in ['ειν', 'αι', 'ναι', 'σθαι', 'εῖν']:
            if lemma.endswith(ending):
                return lemma[:-len(ending)]

    # For nouns/adjectives, strip common endings
    for ending in ['ος', 'ον', 'η', 'α', 'ης', 'ις', 'υς']:
        if lemma.endswith(ending) and len(lemma) > len(ending) + 1:
            return lemma[:-len(ending)]

    return lemma


def _extract_greek_root(word: str, concept: dict) -> str:
    """
    Extract Ancient Greek root from concept data or wiktextract_roots.pkl.

    Greek uses a root system similar to other Indo-European languages.
    Note: Greek roots may include PIE-derived forms - this is valid for Greek.
    """
    global _normalized_lookup
    roots_index = _load_roots_index()

    def is_pie_reconstruction(root_str):
        """Check if root is a PIE reconstruction (starts with *)."""
        if not root_str:
            return False
        # Only filter out explicit reconstructions marked with *
        return root_str.startswith('*')

    # Try direct lookup
    if word in roots_index and roots_index[word]:
        root = roots_index[word][0]
        if not is_pie_reconstruction(root):
            return root

    # Try normalized lookup via precomputed table (O(1) instead of O(n))
    word_normalized = _normalize_greek(word)
    if _normalized_lookup and word_normalized in _normalized_lookup:
        original_key = _normalized_lookup[word_normalized]
        if roots_index.get(original_key):
            root = roots_index[original_key][0]
            if not is_pie_reconstruction(root):
                return root

    # Fallback: Try to get root from etymology_templates if available
    etymology = concept.get('etymology_templates', []) if isinstance(concept, dict) else []
    for etym in etymology:
        if isinstance(etym, dict) and etym.get('name') == 'root':
            args = etym.get('args', {})
            # Skip PIE root templates (source_lang in args['2'])
            source_lang = args.get('2', '')
            if source_lang == 'ine-pro':
                continue
            # Extract root parts from positions 3+
            root_parts = []
            for i in range(3, 10):
                root_val = args.get(str(i), '')
                if root_val and root_val != '-':
                    root_parts.append(root_val)
            if root_parts:
                root_str = '-'.join(root_parts)
                if not is_pie_reconstruction(root_str):
                    return root_str

    # No root found - return empty string (not the word itself)
    return ''


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
    """
    Analyze an Ancient Greek word and return morphological analyses.

    Primary: Query Morpheus REST API (same pattern as Latin adapter).
    Fallback: Use Wiktextract pkl if Morpheus unavailable.

    Args:
        word: Greek word to analyze

    Returns:
        List of dicts matching the lexicon.entries schema columns
    """
    results = []

    # PRIMARY: Query Morpheus for Greek analysis
    morpheus_results = _query_morpheus_greek(word)

    if morpheus_results:
        # Convert Morpheus results to output format
        for m in morpheus_results:
            lemma = m['lemma']
            pos = m['pos']
            root = _extract_greek_root_from_lemma(lemma, pos)
            morph_type = _classify_greek_morph_type(lemma, {})

            result = {
                'language_code': 'grc',
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
                'confidence': 0.9,
                'word_translit': '',
                'english_concept': ''
            }
            results.append(result)

        return results

    # FALLBACK: Use Wiktextract pkl if Morpheus unavailable
    global _index
    if _index is None:
        _index = load_index('grc')

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
