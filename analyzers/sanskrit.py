"""Sanskrit morphological analyzer using Vidyut.

Uses Ambuda's Vidyut library for morphological analysis of Sanskrit words.
Vidyut provides comprehensive Sanskrit morphological data including:
- 45,000+ dhatu (verbal root) entries
- 1.5 million+ pratipadika (nominal stem) entries

NO HARDCODED ROOTS. NO RULE-BASED FALLBACK.
All analysis comes from Vidyut's morphological database.
"""

import os
import re
from typing import Optional

# Module-level cache
_kosha: Optional[object] = None
_vidyut_available: Optional[bool] = None
_sanscript: Optional[object] = None

VIDYUT_DATA_PATH = '/mnt/pgdata/morphlex/data/vidyut_data/kosha'


def _init_vidyut():
    """Initialize Vidyut Kosha on first use."""
    global _kosha, _vidyut_available, _sanscript

    if _vidyut_available is not None:
        return _vidyut_available

    try:
        from vidyut import kosha
        from indic_transliteration import sanscript
        _sanscript = sanscript

        # Check if data directory exists
        if not os.path.exists(VIDYUT_DATA_PATH):
            _vidyut_available = False
            return False

        _kosha = kosha.Kosha(VIDYUT_DATA_PATH)
        _vidyut_available = True
        return True

    except ImportError:
        _vidyut_available = False
        return False
    except Exception:
        _vidyut_available = False
        return False


def _extract_root_vidyut(word: str) -> tuple[str, str, str]:
    """
    Extract root/stem from a Sanskrit word using Vidyut.

    Args:
        word: Sanskrit word in Devanagari script

    Returns:
        Tuple of (root_slp1, root_devanagari, root_type)
        root_type is either 'dhatu' (verbal root) or 'pratipadika' (nominal stem)
        Returns (None, None, None) if no analysis found.
    """
    if not _init_vidyut() or _kosha is None or _sanscript is None:
        return None, None, None

    # Transliterate Devanagari to SLP1 (internal format used by Vidyut)
    try:
        slp1 = _sanscript.transliterate(word, _sanscript.DEVANAGARI, _sanscript.SLP1)
    except Exception:
        return None, None, None

    # Get morphological analyses from Vidyut
    try:
        entries = _kosha.get(slp1)
    except Exception:
        return None, None, None

    if not entries:
        return None, None, None

    # Find the best entry - prefer Basic pratipadika over derived forms
    best_entry = None
    for entry in entries:
        entry_str = str(entry)
        if "PratipadikaEntry.Basic" in entry_str:
            best_entry = entry
            break

    if best_entry is None:
        best_entry = entries[0]

    entry_str = str(best_entry)

    # Extract pratipadika (nominal stem) for basic words - prefer this
    if "PratipadikaEntry.Basic" in entry_str:
        match = re.search(r"text='([^']+)'", entry_str)
        if match:
            stem_slp1 = match.group(1)
            stem_deva = _sanscript.transliterate(stem_slp1, _sanscript.SLP1, _sanscript.DEVANAGARI)
            return stem_slp1, stem_deva, 'pratipadika'

    # Extract dhatu if it's a derived form (krdanta)
    if 'dhatu_entry=DhatuEntry' in entry_str:
        match = re.search(r"aupadeshika='([^']+)'", entry_str)
        if match:
            # Remove anubandha markers (~ and ^)
            dhatu_slp1 = match.group(1).replace('~', '').replace('^', '')
            dhatu_deva = _sanscript.transliterate(dhatu_slp1, _sanscript.SLP1, _sanscript.DEVANAGARI)
            return dhatu_slp1, dhatu_deva, 'dhatu'

    return None, None, None


def analyze_sanskrit(word: str) -> list[dict]:
    """
    Analyze a Sanskrit word and return morphological analyses.

    Uses Vidyut's Kosha for morphological analysis.
    NO HARDCODED ROOTS. NO RULE-BASED FALLBACK.

    Args:
        word: Sanskrit word to analyze (Devanagari script)

    Returns:
        List of dicts matching the lexicon.entries schema columns
    """
    results = []

    # Get root using Vidyut
    root_slp1, root_deva, root_type = _extract_root_vidyut(word)

    if root_slp1:
        result = {
            'language_code': 'sa',
            'word_native': word,
            'word_translit': None,
            'lemma': root_deva,
            'root': root_deva,
            'pos': 'noun' if root_type == 'pratipadika' else 'verb',
            'morph_type': 'ROOT' if root_type == 'dhatu' else 'PRATIPADIKA',
            'derived_from_root': root_deva if root_type == 'dhatu' else None,
            'derivation_mode': 'krdanta' if root_type == 'dhatu' else None,
            'compound_components': None,
            'morphological_features': {
                'root_type': root_type,
                'root_slp1': root_slp1,
            },
            'confidence': 0.9,
            'source_tool': 'vidyut'
        }
        results.append(result)

    return results


if __name__ == '__main__':
    # Test with 20 random Sanskrit words
    test_words = [
        'पुस्तक',   # book
        'नदी',      # river
        'वायु',     # wind
        'अग्नि',    # fire
        'पर्वत',    # mountain
        'सूर्य',    # sun
        'चन्द्र',   # moon
        'वृक्ष',    # tree
        'पुष्प',    # flower
        'जल',       # water
        'पृथ्वी',   # earth
        'आकाश',     # sky
        'मार्ग',    # path
        'नगर',      # city
        'राजा',     # king
        'देव',      # god
        'कन्या',    # daughter
        'पुत्र',    # son
        'गुरु',     # teacher
        'शिष्य',    # student
    ]

    print("=== SANSKRIT ROOT EXTRACTION TEST (VIDYUT - NO HARDCODING) ===\n")

    # Check Vidyut availability
    vidyut_ok = _init_vidyut()
    print(f"Vidyut available: {vidyut_ok}")
    if not vidyut_ok:
        print(f"Data path: {VIDYUT_DATA_PATH}")
        print("Install: pip install vidyut indic-transliteration")
        print("Download data: import vidyut; vidyut.download_data('/mnt/pgdata/morphlex/data/vidyut_data')")
    print()

    found = 0
    empty = 0

    print(f"{'Word':<12} {'Root':<12} {'Type':<12} {'Source'}")
    print("-" * 50)

    for word in test_words:
        results = analyze_sanskrit(word)
        if results and results[0].get('root'):
            r = results[0]
            root_type = r['morphological_features'].get('root_type', 'unknown')
            print(f"{word:<12} {r['root']:<12} {root_type:<12} {r['source_tool']}")
            found += 1
        else:
            print(f"{word:<12} NO ROOT FOUND")
            empty += 1

    print("-" * 50)
    print(f"\n=== RESULTS: {found} roots found, {empty} empty ===")
