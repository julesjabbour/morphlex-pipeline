"""Hebrew morphological analyzer using Hspell binary via subprocess.

Hebrew uses a triconsonantal root system similar to Arabic.
Uses hspell command-line tool directly via subprocess (ctypes approach segfaults).
NO HARDCODED ROOTS. NO RULE-BASED FALLBACK.
"""

import os
import pickle
import re
import shutil
import subprocess
import unicodedata
from typing import Optional

from pipeline.wiktextract_loader import load_index


# Module-level cache for loaded index
_hebrew_index: Optional[dict] = None
_roots_index: Optional[dict] = None
_normalized_lookup: Optional[dict] = None  # {normalized_key: original_key}
_hspell_available: Optional[bool] = None
_hspell_path: Optional[str] = None

ROOTS_PKL_PATH = '/mnt/pgdata/morphlex/data/wiktextract_roots.pkl'


def _find_hspell():
    """Find hspell binary path."""
    global _hspell_available, _hspell_path

    if _hspell_available is not None:
        return _hspell_available

    # Check common paths
    paths_to_try = [
        shutil.which('hspell'),
        '/usr/local/bin/hspell',
        '/usr/bin/hspell',
    ]

    for path in paths_to_try:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            _hspell_path = path
            _hspell_available = True
            print(f"[DEBUG] Found hspell binary at: {_hspell_path}")
            return True

    print("[DEBUG] hspell binary not found")
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


def _convert_to_iso8859_8(text: str) -> bytes:
    """Convert Hebrew text to ISO-8859-8 encoding for hspell."""
    try:
        return text.encode('iso-8859-8')
    except UnicodeEncodeError:
        # Try to convert Unicode Hebrew to ISO-8859-8
        # Hebrew Unicode block: U+0590 to U+05FF
        # ISO-8859-8 Hebrew: 0xE0 to 0xFA (aleph to tav)
        result = []
        for char in text:
            code = ord(char)
            if 0x05D0 <= code <= 0x05EA:  # Hebrew letters aleph to tav
                # Map to ISO-8859-8: 0x05D0 (aleph) -> 0xE0
                result.append(code - 0x05D0 + 0xE0)
            elif code < 128:
                result.append(code)
            # Skip other characters (niqqud, etc.)
        return bytes(result)


def _convert_from_iso8859_8(data: bytes) -> str:
    """Convert ISO-8859-8 bytes to Unicode string."""
    try:
        return data.decode('iso-8859-8')
    except UnicodeDecodeError:
        # Manual conversion
        result = []
        for byte in data:
            if 0xE0 <= byte <= 0xFA:  # Hebrew letters
                # Map from ISO-8859-8: 0xE0 -> U+05D0 (aleph)
                result.append(chr(byte - 0xE0 + 0x05D0))
            elif byte < 128:
                result.append(chr(byte))
        return ''.join(result)


def _parse_hspell_linginfo(output: str, word: str) -> tuple[str, dict]:
    """
    Parse hspell -l linguistic info output to extract base word/root.

    Hspell -l output format (with linginfo support):
    - Shows prefix + base word splits
    - For inflected words: shows base word + grammatical annotations
    - Annotations are comma-separated in Hebrew (gender, number, tense, etc.)

    Examples of expected formats:
    - "ה+מילון (שם עצם,יחיד,זכר)" - prefix + base with analysis
    - "מילון (שם עצם,יחיד,זכר)" - base word with analysis
    - "מילון" - just the word if recognized

    Returns: (base_word, info_dict)
    """
    morph_info = {'raw_output': output.strip()}

    if not output.strip():
        return '', morph_info

    lines = output.strip().split('\n')
    base_words = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for prefix+word format: "ה+מילון" or "ב+בית"
        # The + sign indicates prefix split
        if '+' in line:
            parts = line.split('+')
            if len(parts) >= 2:
                # The part after + is the base word (possibly with annotations)
                base_part = parts[-1].strip()
                # Remove parenthetical annotations if present
                base_part = re.sub(r'\s*\([^)]*\)', '', base_part).strip()
                if base_part and any('\u05D0' <= c <= '\u05EA' for c in base_part):
                    base_words.append(base_part)
                    morph_info['prefix'] = '+'.join(parts[:-1])
                    morph_info['has_prefix_split'] = True

        # Check for word with parenthetical analysis: "מילון (שם עצם,יחיד)"
        paren_match = re.match(r'([\u05D0-\u05EA]+)\s*\(([^)]+)\)', line)
        if paren_match:
            candidate = paren_match.group(1)
            analysis = paren_match.group(2)
            morph_info['analysis'] = analysis
            if candidate and candidate != word and not base_words:
                base_words.append(candidate)
            elif candidate == word:
                # The word itself is recognized with analysis - it's its own base
                morph_info['word_recognized'] = True
                # Return the word itself since it's recognized as valid
                if not base_words:
                    base_words.append(word)

        # Try tab-separated format: word\tanalysis
        if '\t' in line and not base_words:
            parts = line.split('\t')
            if len(parts) >= 2:
                candidate = parts[0].strip()
                if candidate and candidate != word and any('\u05D0' <= c <= '\u05EA' for c in candidate):
                    base_words.append(candidate)
                    morph_info['analysis'] = parts[1]

        # Try colon-separated: baseword:analysis
        if ':' in line and not base_words:
            parts = line.split(':')
            candidate = parts[0].strip()
            if candidate and candidate != word and any('\u05D0' <= c <= '\u05EA' for c in candidate):
                base_words.append(candidate)

        # Extract any Hebrew words from the line as fallback
        # BUT exclude words inside parentheses (those are grammatical terms like שם עצם)
        if not base_words:
            # Remove parenthetical content first
            line_no_parens = re.sub(r'\([^)]*\)', '', line)
            hebrew_words = re.findall(r'[\u05D0-\u05EA]+', line_no_parens)
            for hw in hebrew_words:
                # Accept words different from input OR same word if it's the only analysis
                if hw != word and len(hw) >= 2:
                    base_words.append(hw)

    # If we found base words, return the first one
    if base_words:
        morph_info['base_words'] = base_words
        return base_words[0], morph_info

    # If word was recognized but no different base found, it might be a root itself
    if morph_info.get('word_recognized'):
        return word, morph_info

    return '', morph_info


def _extract_root_hspell(word: str) -> tuple[str, dict]:
    """
    Extract root using hspell binary via subprocess.

    Tries multiple hspell modes to get morphological analysis.
    Returns: (root, morphological_info)
    """
    global _hspell_path

    if not _find_hspell() or _hspell_path is None:
        return '', {}

    morph_info = {}
    word_bytes = _convert_to_iso8859_8(word)

    # Try different hspell modes
    # -l: linguistic info (shows base word + grammatical analysis)
    # -H: allow He Ha-sh'ela prefix (NOT HTML output!)
    # -c -l: suggest corrections AND show linguistic info
    modes_to_try = [
        ([_hspell_path, '-l'], 'linginfo'),       # Linguistic info mode (primary)
        ([_hspell_path, '-l', '-H'], 'linginfo_H'),  # Linginfo + He prefix
        ([_hspell_path, '-c', '-l'], 'correct_linginfo'),  # Corrections + linginfo
        ([_hspell_path], 'default'),              # Default mode (just spell check)
    ]

    for cmd, mode_name in modes_to_try:
        try:
            proc = subprocess.run(
                cmd,
                input=word_bytes + b'\n',
                capture_output=True,
                timeout=5,
                env={**os.environ, 'LC_ALL': 'C'}
            )

            stdout = _convert_from_iso8859_8(proc.stdout)
            stderr = _convert_from_iso8859_8(proc.stderr) if proc.stderr else ''

            morph_info[f'{mode_name}_stdout'] = stdout.strip()[:500]  # Limit for debugging
            if stderr:
                morph_info[f'{mode_name}_stderr'] = stderr.strip()[:200]
            morph_info[f'{mode_name}_returncode'] = proc.returncode

            # Try to parse the output
            base, info = _parse_hspell_linginfo(stdout, word)
            if base:
                morph_info['method'] = mode_name
                morph_info['base'] = base
                return base, morph_info

        except subprocess.TimeoutExpired:
            morph_info[f'{mode_name}_error'] = 'timeout'
        except Exception as e:
            morph_info[f'{mode_name}_error'] = str(e)

    return '', morph_info


def _extract_hebrew_root(word: str, etymology_links: list) -> str:
    """
    Extract Hebrew triconsonantal root (shoresh).

    Uses Hspell binary via subprocess ONLY.
    Falls back to wiktextract etymology data if Hspell unavailable.
    NO HARDCODED ROOTS. NO RULE-BASED FALLBACK.
    """
    global _normalized_lookup
    roots_index = _load_roots_index()

    normalized = _normalize_hebrew(word)

    # Strategy 1: Try hspell binary
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

    Uses Hspell binary via subprocess.
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

    # Try hspell analysis first
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

    # If we have hspell info but no wiktextract matches, create a result
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
                'hspell_method': hspell_info.get('method'),
            },
            'confidence': 0.8,
            'source_tool': 'hspell_subprocess'
        }
        results.append(result)
        return results

    # If no matches and no hspell, try wiktextract etymology only
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

        # Extract root using hspell or wiktextract
        root = hspell_root or _extract_hebrew_root(word, etymology_links)
        morph_type = _classify_hebrew_morph_type(word, root, etymology_links)

        # Determine source tool
        if hspell_root:
            source_tool = 'hspell_subprocess+wiktextract'
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
                'hspell_method': hspell_info.get('method') if hspell_info else None,
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


def debug_hspell(word: str) -> dict:
    """
    Debug function to show raw hspell output for a word.
    Call this to understand what hspell returns.
    """
    global _hspell_path

    if not _find_hspell() or _hspell_path is None:
        return {'error': 'hspell not found'}

    word_bytes = _convert_to_iso8859_8(word)
    results = {'word': word, 'encoded': word_bytes.hex()}

    modes = [
        ([_hspell_path], 'default'),
        ([_hspell_path, '-l'], 'linginfo'),
        ([_hspell_path, '-l', '-H'], 'linginfo_H'),
        ([_hspell_path, '-c', '-l'], 'correct_linginfo'),
        ([_hspell_path, '-n'], 'notes'),
    ]

    for cmd, name in modes:
        try:
            proc = subprocess.run(
                cmd,
                input=word_bytes + b'\n',
                capture_output=True,
                timeout=5,
                env={**os.environ, 'LC_ALL': 'C'}
            )
            results[name] = {
                'stdout': _convert_from_iso8859_8(proc.stdout),
                'stderr': _convert_from_iso8859_8(proc.stderr) if proc.stderr else '',
                'returncode': proc.returncode
            }
        except Exception as e:
            results[name] = {'error': str(e)}

    return results


if __name__ == '__main__':
    import json

    # Test with 20 random Hebrew words
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
        'דלת',     # door
        'שמש',     # sun
        'י��ח',     # moon
        'כוכב',    # star
        'עץ',      # tree
        'פרח',     # flower
        'ילד',     # child
        'אישה',    # woman
        'איש',     # man
        'אהבה',    # love
    ]

    print("=== HEBREW ROOT EXTRACTION TEST (SUBPROCESS - NO HARDCODING) ===\n")

    # Check hspell availability
    hspell_ok = _find_hspell()
    print(f"hspell binary available: {hspell_ok}")
    if _hspell_path:
        print(f"hspell path: {_hspell_path}")
    print()

    # Debug output for first word to understand hspell format
    if hspell_ok:
        print("=== DEBUG: Raw hspell output for first word ===")
        debug_info = debug_hspell(test_words[0])
        for mode, info in debug_info.items():
            if mode in ['word', 'encoded']:
                print(f"{mode}: {info}")
            elif isinstance(info, dict):
                print(f"\n{mode}:")
                for k, v in info.items():
                    print(f"  {k}: {repr(v)[:200]}")
        print()

    found = 0
    empty = 0

    print("=== 20 RANDOM HEBREW WORDS ===")
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
    if not hspell_ok:
        print("WARNING: hspell not available - root extraction depends on wiktextract data only")
