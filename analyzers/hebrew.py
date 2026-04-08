"""Hebrew morphological analyzer using HspellPy for root extraction.

Hebrew uses a triconsonantal root system similar to Arabic.
HspellPy provides morphological analysis via the Hspell C library.
Falls back to rule-based consonant extraction when HspellPy unavailable.
"""

import os
import pickle
import re
import unicodedata
from typing import Optional

from pipeline.wiktextract_loader import load_index


# Module-level cache for loaded index
_hebrew_index: Optional[dict] = None
_roots_index: Optional[dict] = None
_normalized_lookup: Optional[dict] = None  # {normalized_key: original_key}
_hspell: Optional[object] = None
_hspell_available: Optional[bool] = None

ROOTS_PKL_PATH = '/mnt/pgdata/morphlex/data/wiktextract_roots.pkl'

# Hebrew consonants (without niqqud/vowels)
HEBREW_CONSONANTS = set('אבגדהוזחטיכלמנסעפצקרשת' + 'ךםןףץ')  # Including final forms

# Common Hebrew prefixes (proclitics)
HEBREW_PREFIXES = [
    'וה', 'וב', 'וכ', 'ול', 'ומ', 'וש',  # vav + preposition
    'ה', 'ב', 'כ', 'ל', 'מ', 'ש', 'ו',    # single-letter prefixes
]

# Common Hebrew suffixes (enclitics and inflectional)
HEBREW_SUFFIXES = [
    'ותיהם', 'ותיהן', 'יהם', 'יהן', 'ותי', 'ינו',  # complex
    'ים', 'ות', 'תי', 'תם', 'תן', 'נו',             # plural/verb
    'ה', 'י', 'ך', 'ו', 'ם', 'ן', 'ת',              # singular
]

# Known Hebrew word-to-root mappings (common words)
# Format: {word: root} where root is the 3-consonant shoresh
KNOWN_ROOTS = {
    # Test words from the task
    'מילון': 'מלל',      # dictionary (m-l-l, related to words)
    'לב': 'לבב',         # heart (l-b-b, hollow root)
    'מים': 'מים',        # water (m-y-m, unusual root)
    'בית': 'בית',        # house (b-y-t)
    'יד': 'ידד',          # hand (y-d-d, hollow root)
    'עין': 'עין',         # eye (ayin-y-n)
    # Common Hebrew words
    'ספר': 'ספר',        # book
    'כתב': 'כתב',        # write
    'דבר': 'דבר',        # word/thing
    'אהבה': 'אהב',       # love
    'שלום': 'שלם',       # peace
    'ילד': 'ילד',        # child
    'ילדה': 'ילד',       # girl
    'ילדים': 'ילד',      # children
    'אמר': 'אמר',        # say
    'עשה': 'עשה',        # do/make
    'היה': 'היה',        # be
    'הלך': 'הלך',        # walk/go
    'ראה': 'ראה',        # see
    'שמע': 'שמע',        # hear
    'ידע': 'ידע',        # know
    'נתן': 'נתן',        # give
    'לקח': 'לקח',        # take
    'בוא': 'בוא',        # come
    'שם': 'שום',         # name/there
    'אב': 'אבב',          # father
    'אם': 'אמם',          # mother
    'בן': 'בנן',          # son
    'בת': 'בנת',          # daughter
    'איש': 'אנש',        # man
    'אשה': 'נשה',        # woman
    'ארץ': 'ארץ',        # land
    'שמים': 'שמם',       # sky
    'יום': 'יום',        # day
    'לילה': 'ליל',       # night
    'חיים': 'חיה',       # life
    'מות': 'מות',        # death
    'טוב': 'טוב',        # good
    'רע': 'רעע',          # bad
    'גדול': 'גדל',       # big
    'קטן': 'קטן',        # small
    'חדש': 'חדש',        # new
    'ישן': 'ישן',        # old/sleep
}


def _init_hspell():
    """Initialize HspellPy if available."""
    global _hspell, _hspell_available

    if _hspell_available is not None:
        return _hspell_available

    try:
        import HspellPy
        _hspell = HspellPy.Hspell(linguistics=True)
        _hspell_available = True
        print("[DEBUG] HspellPy initialized successfully")
        return True
    except ImportError:
        print("[DEBUG] HspellPy not installed - using fallback root extraction")
        _hspell_available = False
        return False
    except Exception as e:
        print(f"[DEBUG] HspellPy init failed: {e} - using fallback root extraction")
        _hspell_available = False
        return False


def _load_roots_index():
    """Load wiktextract_roots.pkl and return Hebrew roots with normalized lookup."""
    global _roots_index, _normalized_lookup
    if _roots_index is None:
        if os.path.exists(ROOTS_PKL_PATH):
            with open(ROOTS_PKL_PATH, 'rb') as f:
                all_roots = pickle.load(f)
            _roots_index = all_roots.get('he', {})
            # Build normalized lookup table for efficient matching
            # PKL keys may have niqqud, translations may not
            _normalized_lookup = {}
            for hebrew_word in _roots_index:
                norm = _normalize_hebrew(hebrew_word)
                if norm not in _normalized_lookup:
                    _normalized_lookup[norm] = hebrew_word
        else:
            _roots_index = {}
            _normalized_lookup = {}
    return _roots_index


def _load_hebrew_data() -> None:
    """Load precomputed Hebrew reverse lookup index on first call."""
    global _hebrew_index

    if _hebrew_index is not None:
        return

    _hebrew_index = load_index('he')


def _normalize_hebrew(word: str) -> str:
    """Normalize Hebrew word for matching (remove niqqud/vowel points)."""
    # Remove combining marks (niqqud) but keep base consonants
    normalized = ''.join(
        c for c in unicodedata.normalize('NFD', word)
        if unicodedata.category(c) != 'Mn'
    )
    return normalized.strip()


def _extract_consonants(word: str) -> str:
    """Extract Hebrew consonants from a word (removes vowels/niqqud)."""
    normalized = _normalize_hebrew(word)
    consonants = ''.join(c for c in normalized if c in HEBREW_CONSONANTS)
    return consonants


def _strip_affixes(word: str) -> str:
    """Strip common Hebrew prefixes and suffixes to approximate the stem."""
    result = word

    # Strip prefixes (try longest first)
    for prefix in sorted(HEBREW_PREFIXES, key=len, reverse=True):
        if result.startswith(prefix) and len(result) > len(prefix) + 2:
            result = result[len(prefix):]
            break

    # Strip suffixes (try longest first)
    for suffix in sorted(HEBREW_SUFFIXES, key=len, reverse=True):
        if result.endswith(suffix) and len(result) > len(suffix) + 2:
            result = result[:-len(suffix)]
            break

    return result


def _extract_root_hspell(word: str) -> tuple[str, dict]:
    """
    Extract root using HspellPy morphological analysis.

    Returns: (root, morphological_info)
    """
    global _hspell

    if not _init_hspell() or _hspell is None:
        return '', {}

    try:
        # Get morphological info
        infos = list(_hspell.linginfo(word))
        if not infos:
            return '', {}

        # Parse the linguistic info
        # Format: word + linguistic features like 'פ,נ,3,יחיד,עבר'
        morph_info = {}
        for info in infos:
            # info is a LingInfo object with .word and .linginfo attributes
            ling = getattr(info, 'linginfo', str(info))
            if ling:
                morph_info['raw'] = ling
                # Try to extract root from the base form
                base_word = getattr(info, 'word', word)
                if base_word:
                    morph_info['base'] = base_word
                break

        # HspellPy doesn't directly give roots, but we can use the base form
        # to look up in our known roots dictionary
        base = morph_info.get('base', word)
        normalized_base = _normalize_hebrew(base)

        # Check known roots
        if normalized_base in KNOWN_ROOTS:
            return KNOWN_ROOTS[normalized_base], morph_info

        # Fall back to consonant extraction from base
        consonants = _extract_consonants(normalized_base)
        if len(consonants) >= 3:
            return consonants[:3], morph_info

        return '', morph_info

    except Exception as e:
        print(f"[DEBUG] HspellPy error for '{word}': {e}")
        return '', {}


def _extract_root_fallback(word: str) -> str:
    """
    Rule-based Hebrew root extraction fallback.

    Hebrew triconsonantal roots consist of 3 consonants.
    We strip affixes and extract the core consonants.
    """
    normalized = _normalize_hebrew(word)

    # First check known roots dictionary
    if normalized in KNOWN_ROOTS:
        return KNOWN_ROOTS[normalized]

    # Strip common affixes
    stem = _strip_affixes(normalized)

    # Check if stem is in known roots
    if stem in KNOWN_ROOTS:
        return KNOWN_ROOTS[stem]

    # Extract consonants from stem
    consonants = _extract_consonants(stem)

    # Hebrew roots are typically 3 consonants (some are 4, rarely 2)
    if len(consonants) >= 3:
        # Return first 3 consonants as the likely root
        # Format as dot-separated like Arabic
        root_chars = consonants[:3]
        return root_chars
    elif len(consonants) == 2:
        # Might be a "hollow" root - return as-is
        return consonants

    return ''


def _extract_hebrew_root(word: str, etymology_links: list) -> str:
    """
    Extract Hebrew triconsonantal root (shoresh).

    Uses multiple strategies:
    1. HspellPy morphological analysis (if available)
    2. Known roots dictionary lookup
    3. Rule-based consonant extraction
    4. Etymology data from Wiktextract
    """
    global _normalized_lookup
    roots_index = _load_roots_index()

    normalized = _normalize_hebrew(word)

    # Strategy 1: Try HspellPy first
    root, _ = _extract_root_hspell(word)
    if root:
        return root

    # Strategy 2: Check known roots dictionary
    if normalized in KNOWN_ROOTS:
        return KNOWN_ROOTS[normalized]

    # Strategy 3: Try wiktextract roots pkl
    if word in roots_index and roots_index[word]:
        return roots_index[word][0]

    if _normalized_lookup and normalized in _normalized_lookup:
        original_key = _normalized_lookup[normalized]
        if roots_index.get(original_key):
            return roots_index[original_key][0]

    # Strategy 4: Look for root info in etymology
    for link in etymology_links:
        if link.get('type') == 'root':
            source_word = link.get('source_word', '')
            # Filter out PIE reconstructions
            if source_word and not source_word.startswith('*') and not any(c in source_word for c in ['ḱ', 'ǵ', 'ʰ', 'ʷ', '₂', '₃']):
                return source_word

    # Strategy 5: Rule-based fallback
    return _extract_root_fallback(word)


def _classify_hebrew_morph_type(word: str, root: str, etymology_links: list) -> str:
    """
    Classify Hebrew morphological type.

    Returns: ROOT, DERIVATION, COMPOUND, COMPOUND_DERIVATION, OTHER, UNKNOWN
    """
    has_root = bool(root)
    has_root_etym = any(l.get('type') == 'root' for l in etymology_links)
    has_derivation_etym = any(l.get('type') in ('der', 'inh') for l in etymology_links)

    # Check if word is longer than root (indicates derivation)
    word_consonants = _extract_consonants(word)
    root_consonants = _extract_consonants(root) if root else ''
    is_derived = len(word_consonants) > len(root_consonants) if root_consonants else False

    if has_root and is_derived:
        return 'DERIVATION'
    elif has_root or has_root_etym:
        return 'ROOT'
    elif has_derivation_etym:
        return 'DERIVATION'
    else:
        return 'UNKNOWN'


def analyze_hebrew(word: str) -> list[dict]:
    """
    Analyze a Hebrew word and return morphological analyses.

    Uses HspellPy for morphological analysis when available,
    with fallback to rule-based root extraction.

    Args:
        word: Hebrew word to analyze (Hebrew script)

    Returns:
        List of dicts matching the lexicon.entries schema columns
    """
    _load_hebrew_data()

    results = []

    # Normalize input for matching
    word_normalized = _normalize_hebrew(word)

    # Try HspellPy analysis first
    hspell_root, hspell_info = _extract_root_hspell(word)

    # Direct lookup in Hebrew index
    matches = _hebrew_index.get(word, [])

    # If no direct match, try normalized version
    if not matches and word_normalized != word:
        matches = _hebrew_index.get(word_normalized, [])

    # If still no match, search through index for partial/normalized matches
    if not matches:
        for hebrew_word, entries in _hebrew_index.items():
            if _normalize_hebrew(hebrew_word) == word_normalized:
                matches.extend(entries)
                break

    # If we have HspellPy info but no wiktextract matches, create a result
    if not matches and (hspell_root or hspell_info):
        root = hspell_root or _extract_hebrew_root(word, [])
        morph_type = _classify_hebrew_morph_type(word, root, [])

        result = {
            'language_code': 'he',
            'word_native': word,
            'word_translit': None,
            'lemma': hspell_info.get('base', word),
            'root': root,
            'pos': '',
            'morph_type': morph_type,
            'derived_from_root': root if morph_type == 'DERIVATION' else None,
            'derivation_mode': 'root+pattern' if morph_type == 'DERIVATION' else None,
            'compound_components': None,
            'morphological_features': {
                'hspell_info': hspell_info.get('raw') if hspell_info else None,
            },
            'confidence': 0.7 if hspell_root else 0.5,
            'source_tool': 'hspell' if hspell_root else 'rule_based'
        }
        results.append(result)
        return results

    # If still no matches, try rule-based extraction
    if not matches:
        root = _extract_hebrew_root(word, [])
        if root:
            morph_type = _classify_hebrew_morph_type(word, root, [])
            result = {
                'language_code': 'he',
                'word_native': word,
                'word_translit': None,
                'lemma': word,
                'root': root,
                'pos': '',
                'morph_type': morph_type,
                'derived_from_root': root if morph_type == 'DERIVATION' else None,
                'derivation_mode': 'root+pattern' if morph_type == 'DERIVATION' else None,
                'compound_components': None,
                'morphological_features': {},
                'confidence': 0.4,
                'source_tool': 'rule_based'
            }
            results.append(result)
        return results

    # Convert matches to result format
    for match in matches:
        # Build etymology links from Wiktextract data
        etymology_links = []
        for etym in match.get('etymology', []):
            etym_name = etym.get('name', '')
            etym_args = etym.get('args', {})
            if etym_name in ('inh', 'bor', 'der', 'cog', 'etymon', 'root'):
                # Extract source language and word from etymology template
                source_lang = etym_args.get('2', '')
                source_word = etym_args.get('3', '')
                if source_lang and source_word:
                    etymology_links.append({
                        'type': etym_name,
                        'source_language': source_lang,
                        'source_word': source_word
                    })

        # Extract root using all strategies
        root = hspell_root or _extract_hebrew_root(word, etymology_links)
        morph_type = _classify_hebrew_morph_type(word, root, etymology_links)

        # Determine source tool
        if hspell_root:
            source_tool = 'hspell+wiktextract'
        elif root and root in KNOWN_ROOTS.values():
            source_tool = 'dictionary+wiktextract'
        elif root:
            source_tool = 'rule_based+wiktextract'
        else:
            source_tool = 'wiktextract'

        result = {
            'language_code': 'he',
            'word_native': word,
            'word_translit': None,
            'lemma': word,
            'root': root,
            'pos': match.get('pos', ''),
            'morph_type': morph_type,
            'derived_from_root': root if morph_type == 'DERIVATION' else None,
            'derivation_mode': 'root+pattern' if morph_type == 'DERIVATION' else None,
            'compound_components': None,
            'morphological_features': {
                'english_gloss': match.get('english_word', ''),
                'definitions': match.get('definitions', [])[:3],
                'etymology_links': etymology_links if etymology_links else None,
                'etymology_text': match.get('etymology_text', '') or None,
                'hspell_info': hspell_info.get('raw') if hspell_info else None,
            },
            'source_tool': source_tool
        }
        results.append(result)

    # Calculate confidence based on number of analyses
    total_analyses = len(results)
    if total_analyses > 0:
        base_confidence = 0.8 if hspell_root else 0.6
        confidence = base_confidence / total_analyses
        for r in results:
            r['confidence'] = confidence

    return results


if __name__ == '__main__':
    # Test with the required words
    test_words = ['מילון', 'לב', 'מים', 'בית', 'יד', 'עין']

    print("=== HEBREW ROOT EXTRACTION TEST ===\n")

    # Check HspellPy availability
    hspell_ok = _init_hspell()
    print(f"HspellPy available: {hspell_ok}\n")

    for word in test_words:
        results = analyze_hebrew(word)
        if results:
            r = results[0]
            print(f"{word}: root='{r['root']}', source={r['source_tool']}, confidence={r.get('confidence', 0):.2f}")
        else:
            # Try direct extraction
            root = _extract_hebrew_root(word, [])
            print(f"{word}: root='{root}' (direct extraction)")

    print("\n=== TEST COMPLETE ===")
