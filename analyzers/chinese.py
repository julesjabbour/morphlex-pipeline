"""Chinese morphological analyzer using pkuseg, CC-CEDICT, and CJKVI-IDS."""

import spacy_pkuseg as pkuseg
import subprocess
import os

# Initialize the segmenter
_seg = pkuseg.pkuseg()

# Paths to data files
_CEDICT_PATH = '/mnt/pgdata/morphlex/data/cedict.txt'
_IDS_PATH = '/mnt/pgdata/morphlex/data/cjkvi-ids/ids.txt'

# Lazy-loaded lookup dictionaries
_cedict = None
_ids = None


def _find_cedict_path() -> str:
    """Find cedict.txt by searching multiple locations."""
    # Try common locations first
    candidates = [
        '/mnt/pgdata/morphlex/cedict.txt',
        '/mnt/pgdata/morphlex/data/cedict.txt',
    ]

    for path in candidates:
        if os.path.exists(path):
            print(f"CEDICT found at: {path}")
            return path

    # Fallback: use find command
    try:
        result = subprocess.run(
            ['find', '/mnt/pgdata', '-name', 'cedict*', '-type', 'f'],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.stdout.strip():
            found_path = result.stdout.strip().split('\n')[0]
            print(f"CEDICT found via search at: {found_path}")
            return found_path
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        pass

    raise FileNotFoundError("cedict.txt not found in any expected location")


def _load_cedict():
    """Load and parse CC-CEDICT dictionary."""
    global _cedict
    if _cedict is not None:
        return _cedict

    _cedict = {}
    with open(_CEDICT_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Format: Traditional Simplified [pin1 yin1] /definition1/definition2/
            try:
                # Split on first [ to get characters and rest
                parts = line.split('[', 1)
                if len(parts) < 2:
                    continue

                chars_part = parts[0].strip()
                rest = parts[1]

                # Get traditional and simplified
                char_parts = chars_part.split()
                if len(char_parts) < 2:
                    continue
                traditional = char_parts[0]
                simplified = char_parts[1]

                # Get pinyin (between [ and ])
                pinyin_end = rest.find(']')
                if pinyin_end == -1:
                    continue
                pinyin = rest[:pinyin_end].strip()

                # Get definitions (between / characters)
                defs_part = rest[pinyin_end + 1:].strip()
                definitions = [d for d in defs_part.split('/') if d.strip()]

                # Extract POS from definitions if present (e.g., "(noun)" or "v.")
                pos = None
                for defn in definitions:
                    if defn.startswith('(') and ')' in defn:
                        pos_candidate = defn[1:defn.find(')')].lower()
                        if pos_candidate in ['noun', 'verb', 'adj', 'adv', 'particle', 'classifier']:
                            pos = pos_candidate
                            break

                # Store by simplified character (primary lookup)
                entry = {
                    'traditional': traditional,
                    'simplified': simplified,
                    'pinyin': pinyin,
                    'definitions': definitions,
                    'pos': pos
                }
                _cedict[simplified] = entry
                # Also store by traditional if different
                if traditional != simplified:
                    _cedict[traditional] = entry

            except Exception:
                continue

    return _cedict


def _load_ids():
    """Load CJKVI-IDS decomposition data."""
    global _ids
    if _ids is not None:
        return _ids

    _ids = {}
    with open(_IDS_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Tab-separated: codepoint, character, IDS decomposition
            parts = line.split('\t')
            if len(parts) >= 3:
                char = parts[1]
                ids_decomposition = parts[2]
                _ids[char] = ids_decomposition

    return _ids


def analyze_chinese(word: str) -> list[dict]:
    """
    Analyze a Chinese word/phrase and return morphological analyses.

    Uses pkuseg for word segmentation, CC-CEDICT for pinyin and definitions,
    and CJKVI-IDS for character decomposition.

    Args:
        word: Chinese word or phrase to analyze

    Returns:
        List of dicts (one per segment) matching the lexicon.entries schema
    """
    # Load dictionaries
    cedict = _load_cedict()
    ids = _load_ids()

    # Segment the input
    segments = _seg.cut(word)

    results = []
    for segment in segments:
        # Look up in CEDICT
        cedict_entry = cedict.get(segment, {})
        pinyin = cedict_entry.get('pinyin', '')
        definitions = cedict_entry.get('definitions', [])
        pos = cedict_entry.get('pos')

        # For single characters, look up IDS decomposition
        compound_components = None
        if len(segment) == 1:
            ids_decomposition = ids.get(segment)
            if ids_decomposition:
                compound_components = ids_decomposition

        # Build morphological features
        morphological_features = {}
        if pinyin:
            morphological_features['pinyin'] = pinyin
        if definitions:
            morphological_features['definitions'] = definitions

        result = {
            'language_code': 'zh',
            'word_native': segment,
            'lemma': segment,
            'pos': pos,
            'compound_components': compound_components,
            'morphological_features': morphological_features,
            'source_tool': 'pkuseg+cedict+ids'
        }
        results.append(result)

    return results
