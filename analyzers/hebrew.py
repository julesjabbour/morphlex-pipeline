"""Hebrew morphological analyzer using Hspell C library via ctypes.

Hebrew uses a triconsonantal root system similar to Arabic.
Uses libhspell.so.0 directly via ctypes (HspellPy is broken on Python 3.12).
NO HARDCODED ROOTS. NO RULE-BASED FALLBACK.
"""

import ctypes
import os
import pickle
import unicodedata
from ctypes import c_char_p, c_int, c_void_p, CFUNCTYPE, POINTER, byref
from typing import Optional

from pipeline.wiktextract_loader import load_index


# Module-level cache for loaded index
_hebrew_index: Optional[dict] = None
_roots_index: Optional[dict] = None
_normalized_lookup: Optional[dict] = None  # {normalized_key: original_key}
_hspell_dict: c_void_p = None
_hspell_lib: Optional[ctypes.CDLL] = None
_hspell_available: Optional[bool] = None

ROOTS_PKL_PATH = '/mnt/pgdata/morphlex/data/wiktextract_roots.pkl'
HSPELL_LIB_PATH = '/usr/local/lib/libhspell.so.0'

# Hspell callback type: int callback(const char *word, const char *baseword, const char *desc, void *data)
HSPELL_CALLBACK = CFUNCTYPE(c_int, c_char_p, c_char_p, c_char_p, c_void_p)


def _init_hspell():
    """Initialize Hspell C library via ctypes."""
    global _hspell_dict, _hspell_lib, _hspell_available

    if _hspell_available is not None:
        return _hspell_available

    try:
        # Load the shared library
        if not os.path.exists(HSPELL_LIB_PATH):
            print(f"[DEBUG] libhspell.so.0 not found at {HSPELL_LIB_PATH}")
            _hspell_available = False
            return False

        _hspell_lib = ctypes.CDLL(HSPELL_LIB_PATH)

        # Define function signatures
        # int hspell_init(struct dict_radix **dictp, int flags)
        _hspell_lib.hspell_init.argtypes = [POINTER(c_void_p), c_int]
        _hspell_lib.hspell_init.restype = c_int

        # int hspell_check_word(struct dict_radix *dict, const char *word, int *preflen)
        _hspell_lib.hspell_check_word.argtypes = [c_void_p, c_char_p, POINTER(c_int)]
        _hspell_lib.hspell_check_word.restype = c_int

        # void hspell_enum_splits(struct dict_radix *dict, const char *word,
        #                         int (*callback)(const char *, const char *, const char *, void *),
        #                         void *data)
        _hspell_lib.hspell_enum_splits.argtypes = [c_void_p, c_char_p, HSPELL_CALLBACK, c_void_p]
        _hspell_lib.hspell_enum_splits.restype = None

        # void hspell_uninit(struct dict_radix *dict)
        _hspell_lib.hspell_uninit.argtypes = [c_void_p]
        _hspell_lib.hspell_uninit.restype = None

        # Initialize the dictionary
        # HSPELL_OPT_LINGUISTICS = 16 (enables linguistic info)
        HSPELL_OPT_LINGUISTICS = 16
        dict_ptr = c_void_p()
        ret = _hspell_lib.hspell_init(byref(dict_ptr), HSPELL_OPT_LINGUISTICS)

        if ret != 0:
            print(f"[DEBUG] hspell_init failed with code {ret}")
            _hspell_available = False
            return False

        _hspell_dict = dict_ptr
        _hspell_available = True
        print("[DEBUG] Hspell C library initialized successfully via ctypes")
        return True

    except OSError as e:
        print(f"[DEBUG] Failed to load libhspell.so.0: {e}")
        _hspell_available = False
        return False
    except Exception as e:
        print(f"[DEBUG] Hspell init failed: {e}")
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


def _extract_root_hspell(word: str) -> tuple[str, dict]:
    """
    Extract root using Hspell C library via ctypes.

    Calls hspell_enum_splits() to get morphological analyses.
    Returns: (root, morphological_info)
    """
    global _hspell_dict, _hspell_lib

    if not _init_hspell() or _hspell_dict is None:
        return '', {}

    try:
        # Encode word to ISO-8859-8 (Hebrew encoding used by Hspell)
        try:
            word_bytes = word.encode('iso-8859-8')
        except UnicodeEncodeError:
            # Try UTF-8 as fallback
            word_bytes = word.encode('utf-8')

        # Collect results from callback
        results = []

        def splits_callback(word_ptr, baseword_ptr, desc_ptr, data_ptr):
            """Callback for hspell_enum_splits - collects base words and descriptions."""
            try:
                base = baseword_ptr.decode('iso-8859-8') if baseword_ptr else ''
                desc = desc_ptr.decode('iso-8859-8') if desc_ptr else ''
                results.append({'base': base, 'desc': desc})
            except Exception:
                try:
                    base = baseword_ptr.decode('utf-8') if baseword_ptr else ''
                    desc = desc_ptr.decode('utf-8') if desc_ptr else ''
                    results.append({'base': base, 'desc': desc})
                except Exception:
                    pass
            return 0  # Continue enumeration

        callback = HSPELL_CALLBACK(splits_callback)

        # Call hspell_enum_splits
        _hspell_lib.hspell_enum_splits(_hspell_dict, word_bytes, callback, None)

        if not results:
            # Try hspell_check_word as fallback
            preflen = c_int()
            ret = _hspell_lib.hspell_check_word(_hspell_dict, word_bytes, byref(preflen))
            if ret > 0:
                # Word is valid but no splits - use word minus prefix as base
                if preflen.value > 0:
                    base = word[preflen.value:]
                    return base, {'check_word': True, 'preflen': preflen.value}
            return '', {}

        # Parse results to find the root/base
        morph_info = {'splits': results}

        # The first result's base word is typically the lemma/root
        for r in results:
            base = r.get('base', '')
            if base:
                morph_info['base'] = base
                morph_info['desc'] = r.get('desc', '')
                # Return the base form - Hspell gives the dictionary form
                return base, morph_info

        return '', morph_info

    except Exception as e:
        print(f"[DEBUG] Hspell ctypes error for '{word}': {e}")
        return '', {}


def _extract_hebrew_root(word: str, etymology_links: list) -> str:
    """
    Extract Hebrew triconsonantal root (shoresh).

    Uses Hspell C library via ctypes ONLY.
    Falls back to wiktextract etymology data if Hspell unavailable.
    NO HARDCODED ROOTS. NO RULE-BASED FALLBACK.
    """
    global _normalized_lookup
    roots_index = _load_roots_index()

    normalized = _normalize_hebrew(word)

    # Strategy 1: Try HspellPy
    root, _ = _extract_root_hspell(word)
    if root:
        return root

    # Strategy 2: Try wiktextract roots pkl
    if word in roots_index and roots_index[word]:
        return roots_index[word][0]

    if _normalized_lookup and normalized in _normalized_lookup:
        original_key = _normalized_lookup[normalized]
        if roots_index.get(original_key):
            return roots_index[original_key][0]

    # Strategy 3: Look for root info in etymology
    for link in etymology_links:
        if link.get('type') == 'root':
            source_word = link.get('source_word', '')
            # Filter out PIE reconstructions
            if source_word and not source_word.startswith('*'):
                return source_word

    # No root found - return empty (honest result)
    return ''


def _classify_hebrew_morph_type(word: str, root: str, etymology_links: list) -> str:
    """
    Classify Hebrew morphological type.

    Returns: ROOT, DERIVATION, COMPOUND, COMPOUND_DERIVATION, OTHER, UNKNOWN
    """
    has_root = bool(root)
    has_root_etym = any(l.get('type') == 'root' for l in etymology_links)
    has_derivation_etym = any(l.get('type') in ('der', 'inh') for l in etymology_links)

    if has_root or has_root_etym:
        return 'ROOT'
    elif has_derivation_etym:
        return 'DERIVATION'
    else:
        return 'UNKNOWN'


def analyze_hebrew(word: str) -> list[dict]:
    """
    Analyze a Hebrew word and return morphological analyses.

    Uses Hspell C library (libhspell.so.0) via ctypes.
    NO HARDCODED ROOTS. NO RULE-BASED FALLBACK.

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
    if not matches and hspell_root:
        morph_type = _classify_hebrew_morph_type(word, hspell_root, [])

        result = {
            'language_code': 'he',
            'word_native': word,
            'word_translit': None,
            'lemma': hspell_info.get('base', word),
            'root': hspell_root,
            'pos': '',
            'morph_type': morph_type,
            'derived_from_root': hspell_root if morph_type == 'DERIVATION' else None,
            'derivation_mode': 'root+pattern' if morph_type == 'DERIVATION' else None,
            'compound_components': None,
            'morphological_features': {
                'hspell_info': hspell_info.get('raw') if hspell_info else None,
            },
            'confidence': 0.8,
            'source_tool': 'hspell_ctypes'
        }
        results.append(result)
        return results

    # If no matches and no HspellPy, try wiktextract etymology only
    if not matches:
        root = _extract_hebrew_root(word, [])
        if root:
            result = {
                'language_code': 'he',
                'word_native': word,
                'word_translit': None,
                'lemma': word,
                'root': root,
                'pos': '',
                'morph_type': 'ROOT',
                'derived_from_root': None,
                'derivation_mode': None,
                'compound_components': None,
                'morphological_features': {},
                'confidence': 0.5,
                'source_tool': 'wiktextract'
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
                source_lang = etym_args.get('2', '')
                source_word = etym_args.get('3', '')
                if source_lang and source_word:
                    etymology_links.append({
                        'type': etym_name,
                        'source_language': source_lang,
                        'source_word': source_word
                    })

        # Extract root using HspellPy or wiktextract
        root = hspell_root or _extract_hebrew_root(word, etymology_links)
        morph_type = _classify_hebrew_morph_type(word, root, etymology_links)

        # Determine source tool
        if hspell_root:
            source_tool = 'hspell_ctypes+wiktextract'
        elif root:
            source_tool = 'wiktextract'
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
    # Test with random Hebrew words NOT in any hardcoded list
    test_words = [
        'מילון',   # dictionary
        'לב',      # heart
        'מים',     # water
        'בית',     # house
        'יד',      # hand
        'עין',     # eye
        'ספר',     # book
        'שולחן',   # table
        'כיסא',    # chair
        'חלון',    # window
    ]

    print("=== HEBREW ROOT EXTRACTION TEST (CTYPES - NO HARDCODING) ===\n")

    # Check Hspell C library availability
    hspell_ok = _init_hspell()
    print(f"Hspell C library available: {hspell_ok}")
    print(f"Library path: {HSPELL_LIB_PATH}\n")

    found = 0
    empty = 0

    for word in test_words:
        results = analyze_hebrew(word)
        if results and results[0].get('root'):
            r = results[0]
            print(f"{word}: root='{r['root']}', source={r['source_tool']}")
            found += 1
        else:
            print(f"{word}: NO ROOT FOUND")
            empty += 1

    print(f"\n=== RESULTS: {found} roots found, {empty} empty ===")
    print("NOTE: Without Hspell C library, root extraction depends on wiktextract data only.")
