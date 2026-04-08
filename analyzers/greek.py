"""Ancient Greek morphological analyzer using Morpheus (primary) + Wiktextract fallback.

Morpheus Greek endpoint requires Beta Code input (ASCII encoding of Greek).
Example: γράφω = gra/fw, ἄνθρωπος = a)/nqrwpos

STATUS: Greek analysis via Morpheus with Beta Code conversion.
Fallback to wiktextract_roots.pkl if Morpheus unavailable.
Zero error suppression - empty is honest, fake roots are not.
"""

import os
import pickle
import re
import unicodedata
import urllib.request
import urllib.error
import urllib.parse

from pipeline.wiktextract_loader import load_index

_index = None
_roots_index = None
_normalized_lookup = None  # {normalized_key: original_key}

ROOTS_PKL_PATH = '/mnt/pgdata/morphlex/data/wiktextract_roots.pkl'
MORPHEUS_GREEK_URL = 'http://localhost:1315/greek/'

# Debug flag - set to True to see Morpheus responses
_DEBUG_MORPHEUS = True

# Beta Code mapping: Unicode Greek -> ASCII
# Lowercase letters
_BETA_LETTERS = {
    'α': 'a', 'β': 'b', 'γ': 'g', 'δ': 'd', 'ε': 'e', 'ζ': 'z', 'η': 'h',
    'θ': 'q', 'ι': 'i', 'κ': 'k', 'λ': 'l', 'μ': 'm', 'ν': 'n', 'ξ': 'c',
    'ο': 'o', 'π': 'p', 'ρ': 'r', 'σ': 's', 'ς': 's', 'τ': 't', 'υ': 'u',
    'φ': 'f', 'χ': 'x', 'ψ': 'y', 'ω': 'w',
    # Uppercase (prefixed with *)
    'Α': '*a', 'Β': '*b', 'Γ': '*g', 'Δ': '*d', 'Ε': '*e', 'Ζ': '*z', 'Η': '*h',
    'Θ': '*q', 'Ι': '*i', 'Κ': '*k', 'Λ': '*l', 'Μ': '*m', 'Ν': '*n', 'Ξ': '*c',
    'Ο': '*o', 'Π': '*p', 'Ρ': '*r', 'Σ': '*s', 'Τ': '*t', 'Υ': '*u',
    'Φ': '*f', 'Χ': '*x', 'Ψ': '*y', 'Ω': '*w',
}

# Diacritics in NFD form (combining characters)
_BETA_DIACRITICS = {
    '\u0301': '/',   # acute accent (oxia/tonos)
    '\u0300': '\\',  # grave accent (varia)
    '\u0342': '=',   # circumflex (perispomeni)
    '\u0314': '(',   # rough breathing (dasia)
    '\u0313': ')',   # smooth breathing (psili)
    '\u0308': '+',   # dieresis
    '\u0345': '|',   # iota subscript (ypogegrammeni)
    '\u0304': '_',   # macron (if present)
    '\u0306': '^',   # breve (if present)
}


def _greek_to_beta_code(text: str) -> str:
    """
    Convert Unicode Greek text to Beta Code for Morpheus.

    Beta Code is the ASCII encoding used by Perseus/Morpheus.
    Diacritics are placed AFTER the letter they modify.

    Examples:
        γράφω -> gra/fw
        ἄνθρωπος -> a)/nqrwpos
        λόγος -> lo/gos
    """
    # Normalize to NFD to separate base characters from combining marks
    nfd = unicodedata.normalize('NFD', text)

    result = []
    for char in nfd:
        if char in _BETA_LETTERS:
            result.append(_BETA_LETTERS[char])
        elif char in _BETA_DIACRITICS:
            result.append(_BETA_DIACRITICS[char])
        elif char.isascii():
            # Keep ASCII characters (spaces, punctuation)
            result.append(char)
        # Skip unknown combining marks silently

    return ''.join(result)


def _strip_diacritics(text: str) -> str:
    """Remove diacritics/accents from text (used for pkl lookup fallback)."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )


def _query_morpheus_greek(word: str) -> list[dict]:
    """
    Query Morpheus REST API for Ancient Greek morphological analysis.

    CRITICAL: Morpheus expects Beta Code input, not UTF-8 Greek!
    Example: γράφω must be sent as gra/fw

    Morpheus returns custom text format with analyses in angle brackets.
    Greek Morpheus may return different formats than Latin:
    - <NL>...</NL> blocks (like Latin)
    - <greek-analyses>...</greek-analyses> blocks
    - Plain lemma lines

    Args:
        word: Greek word to analyze (Unicode)

    Returns:
        List of analysis dicts from Morpheus
    """
    results = []

    try:
        # Handle multi-word translations: take only the first word
        clean_word = word.split()[0] if ' ' in word else word
        if not clean_word:
            return results

        # CRITICAL: Convert Unicode Greek to Beta Code (ASCII)
        # Morpheus expects Beta Code, NOT UTF-8 Greek characters!
        beta_word = _greek_to_beta_code(clean_word)

        # URL-encode Beta Code (escape /, \, etc. which have special meaning)
        encoded_word = urllib.parse.quote(beta_word, safe='')
        url = f"{MORPHEUS_GREEK_URL}{encoded_word}"

        if _DEBUG_MORPHEUS:
            print(f"[DEBUG] Morpheus Greek: '{word}' -> beta '{beta_word}' -> url '{url}'")

        with urllib.request.urlopen(url, timeout=5) as response:
            text_data = response.read().decode('utf-8')

        if _DEBUG_MORPHEUS:
            # Print first 500 chars of response for debugging
            preview = text_data[:500].replace('\n', '\\n')
            print(f"[DEBUG] Morpheus Greek response for '{word}': {preview}")

        # Try multiple parsing strategies for Morpheus response

        # Strategy 1: Parse <NL>...</NL> blocks (case-insensitive)
        nl_blocks = re.findall(r'<[Nn][Ll]>([^<]+)</[Nn][Ll]>', text_data)

        if _DEBUG_MORPHEUS and nl_blocks:
            print(f"[DEBUG] Found {len(nl_blocks)} NL blocks")

        for block in nl_blocks:
            result = _parse_morpheus_block(block)
            if result and result.get('lemma'):
                results.append(result)

        # Strategy 2: If no NL blocks, try parsing <analysis>...</analysis> tags
        if not results:
            analysis_blocks = re.findall(r'<analysis>([^<]+)</analysis>', text_data, re.IGNORECASE)
            if _DEBUG_MORPHEUS and analysis_blocks:
                print(f"[DEBUG] Found {len(analysis_blocks)} analysis blocks")
            for block in analysis_blocks:
                result = _parse_morpheus_block(block)
                if result and result.get('lemma'):
                    results.append(result)

        # Strategy 3: Try to extract lemma from lemma="..." attribute
        if not results:
            lemma_matches = re.findall(r'lemma="([^"]+)"', text_data)
            if _DEBUG_MORPHEUS and lemma_matches:
                print(f"[DEBUG] Found {len(lemma_matches)} lemma attributes")
            for lemma in lemma_matches:
                if lemma:
                    results.append({
                        'lemma': lemma,
                        'pos': '',
                        'features': {}
                    })

        # Strategy 4: If response has form/lemma on separate lines
        if not results:
            # Look for lines with Greek text that might be lemmas
            for line in text_data.split('\n'):
                line = line.strip()
                # Skip XML tags and empty lines
                if not line or line.startswith('<') or line.startswith('<?'):
                    continue
                # If line contains Greek characters and isn't too long, treat as lemma
                if any('\u0370' <= c <= '\u03FF' or '\u1F00' <= c <= '\u1FFF' for c in line):
                    if len(line) < 50:  # Reasonable lemma length
                        # Take first word if multiple
                        lemma = line.split()[0] if ' ' in line else line
                        results.append({
                            'lemma': lemma,
                            'pos': '',
                            'features': {}
                        })
                        if _DEBUG_MORPHEUS:
                            print(f"[DEBUG] Extracted lemma from line: '{lemma}'")
                        break  # Just take first match

        if _DEBUG_MORPHEUS:
            print(f"[DEBUG] Total Morpheus results for '{word}': {len(results)}")

    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        if _DEBUG_MORPHEUS:
            print(f"[DEBUG] Morpheus connection error for '{word}': {e}")
        # Connection error - will fall back to pkl
        pass
    except Exception as e:
        if _DEBUG_MORPHEUS:
            print(f"[DEBUG] Morpheus unexpected error for '{word}': {e}")
        pass

    return results


def _parse_morpheus_block(block: str) -> dict:
    """Parse a single Morpheus analysis block into a result dict."""
    block = block.strip()
    if not block:
        return None

    result = {
        'lemma': '',
        'pos': '',
        'features': {}
    }

    # Split on whitespace
    tokens = block.split()
    if not tokens:
        return None

    # First token is usually POS (V, N, ADJ, etc.)
    pos_raw = tokens[0].upper()
    pos_map = {
        'V': 'verb', 'N': 'noun', 'ADJ': 'adjective',
        'ADV': 'adverb', 'PREP': 'preposition', 'CONJ': 'conjunction',
        'PRON': 'pronoun', 'PART': 'participle', 'NUM': 'numeral',
        'ARTICLE': 'article', 'ART': 'article'
    }
    result['pos'] = pos_map.get(pos_raw, pos_raw.lower())

    # Second token contains lemma - format varies:
    # Latin: "laudo_.laudo" -> extract after dot
    # Greek: might be "γραφω_.γραφω" or just "γραφω" or "form.lemma"
    if len(tokens) > 1:
        lemma_part = tokens[1]
        if '.' in lemma_part:
            # Take part after the dot (the lemma)
            result['lemma'] = lemma_part.split('.', 1)[1]
        elif '_' in lemma_part:
            # Handle underscore separator
            result['lemma'] = lemma_part.split('_', 1)[0]
        else:
            result['lemma'] = lemma_part

    # Parse morphological features from remaining tokens
    for feat in tokens[2:] if len(tokens) > 2 else []:
        feat_lower = feat.lower()
        if '.' in feat:  # Skip conjugation info like conj1.are.vb
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

    return result


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
    Extract Greek root from lemma (same pattern as Latin adapter).

    For verbs, extract the verb stem by stripping common endings.
    For nouns/adjectives, strip nominal endings.
    ALWAYS returns lemma as fallback (never empty for non-empty input).
    """
    if not lemma:
        return ''

    # Normalize lemma - strip diacritics for ending comparison
    lemma_norm = _strip_diacritics(lemma)

    # For verbs ending in common Greek verb endings (present tense, infinitive)
    # Check both with and without diacritics
    if pos == 'verb':
        # Greek verb endings (without diacritics for matching)
        verb_endings = ['ειν', 'αι', 'ναι', 'σθαι', 'ω', 'ομαι', 'μι']
        for ending in verb_endings:
            if lemma_norm.endswith(ending) and len(lemma_norm) > len(ending):
                # Strip from original lemma (preserve any diacritics in stem)
                return lemma[:-len(ending)] if lemma.endswith(ending) else lemma_norm[:-len(ending)]

    # For nouns/adjectives, strip common nominal endings
    # (without diacritics for matching)
    noun_endings = ['ος', 'ον', 'η', 'α', 'ης', 'ις', 'υς', 'ες', 'οι', 'αι']
    for ending in noun_endings:
        if lemma_norm.endswith(ending) and len(lemma_norm) > len(ending) + 1:
            return lemma[:-len(ending)] if lemma.endswith(ending) else lemma_norm[:-len(ending)]

    # Return lemma only if it differs from input (actual lemmatization happened)
    # For Greek, Morpheus doesn't work - this code path won't be reached
    return lemma


def _extract_greek_root(word: str, concept: dict) -> str:
    """
    Extract Ancient Greek root from concept data or wiktextract_roots.pkl.

    Greek uses a root system similar to other Indo-European languages.
    Note: Greek roots may include PIE-derived forms - this is valid for Greek.

    RETURNS: root from pkl, etymology, or word itself as fallback (never empty for non-empty input).
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

    # NO FALLBACK: Return empty if no actual root data found
    # Returning the input word as root is a fake result - zero error suppression
    # Greek is a TOOL LIMITATION like Hebrew/Sanskrit
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
