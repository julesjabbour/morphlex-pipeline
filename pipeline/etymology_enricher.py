"""
Etymology Enricher module for morphlex pipeline.

Extracts etymology data from Wiktextract dump - ancestors, cognates, and cross-language links.
Uses etymology_templates field for structured inh/der/cog/bor entries.

Architecture:
- Etymology index (etymology_index.pkl) = ancestor chains + cognates ONLY
- Wiktextract translation index (wiktextract_index.pkl, 41MB) = cross-language translations ONLY
- These two indexes serve different purposes and should not be mixed.
"""

import os
import gzip
import json
import pickle

# Paths
RAW_WIKTEXTRACT_PATH = "/mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz"
ETYMOLOGY_INDEX_PATH = "/mnt/pgdata/morphlex/data/etymology_index.pkl"
WIKTEXTRACT_INDEX_PATH = "/mnt/pgdata/morphlex/data/wiktextract_index.pkl"

# Target languages for cross-links
TARGET_LANGUAGES = ['ar', 'he', 'ja', 'zh', 'de', 'tr', 'sa', 'la', 'grc', 'ine-pro']

# Global indexes
_etymology_index: dict = {}
_wiktextract_index: dict = {}
_forward_translations: dict = None
_indexes_loaded: bool = False


def build_etymology_index(force_rebuild: bool = False) -> int:
    """
    Build etymology index from raw Wiktextract JSONL dump.

    Streams the 2.4GB JSONL and extracts etymology_templates for English entries.
    Saves to /mnt/pgdata/morphlex/data/etymology_index.pkl

    Args:
        force_rebuild: If True, rebuild even if index exists

    Returns:
        Number of English entries with etymology data
    """
    global _etymology_index

    # Check if index already exists
    if os.path.exists(ETYMOLOGY_INDEX_PATH) and not force_rebuild:
        print(f"Etymology index already exists at {ETYMOLOGY_INDEX_PATH}")
        print("Loading existing index...")
        with open(ETYMOLOGY_INDEX_PATH, 'rb') as f:
            _etymology_index = pickle.load(f)
        return len(_etymology_index)

    if not os.path.exists(RAW_WIKTEXTRACT_PATH):
        print(f"ERROR: Raw Wiktextract file not found: {RAW_WIKTEXTRACT_PATH}")
        return 0

    print(f"=== BUILDING ETYMOLOGY INDEX ===")
    print(f"Input: {RAW_WIKTEXTRACT_PATH}")
    print(f"Output: {ETYMOLOGY_INDEX_PATH}")
    print()

    _etymology_index = {}
    line_count = 0
    english_count = 0

    print(f"Streaming {RAW_WIKTEXTRACT_PATH}...")

    with gzip.open(RAW_WIKTEXTRACT_PATH, 'rt', encoding='utf-8') as f:
        for line in f:
            line_count += 1

            if line_count % 100000 == 0:
                print(f"  Processed {line_count:,} lines, {english_count:,} entries with etymology...")

            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            # Only process English entries
            lang_code = entry.get('lang_code', '')
            if lang_code != 'en':
                continue

            word = entry.get('word', '').lower().strip()
            if not word:
                continue

            # Check for etymology data
            etymology_templates = entry.get('etymology_templates', [])
            etymology_text = entry.get('etymology_text', '')

            # Skip if no etymology data
            if not etymology_templates and not etymology_text:
                continue

            # Store etymology data (templates + text only, no translations)
            if word not in _etymology_index:
                _etymology_index[word] = {
                    'templates': [],
                    'text': ''
                }

            # Add templates (avoid duplicates)
            existing_templates = {
                (t.get('name'), t.get('args', {}).get('1'), t.get('args', {}).get('2'))
                for t in _etymology_index[word]['templates']
            }

            for tmpl in etymology_templates:
                tmpl_key = (tmpl.get('name'), tmpl.get('args', {}).get('1'), tmpl.get('args', {}).get('2'))
                if tmpl_key not in existing_templates:
                    _etymology_index[word]['templates'].append(tmpl)
                    existing_templates.add(tmpl_key)

            # Keep the longest etymology text
            if len(etymology_text) > len(_etymology_index[word]['text']):
                _etymology_index[word]['text'] = etymology_text

            english_count += 1

    print(f"\nDone! Processed {line_count:,} lines")
    print(f"English entries with etymology: {len(_etymology_index):,}")

    # Save index
    print(f"\nSaving to {ETYMOLOGY_INDEX_PATH}...")
    with open(ETYMOLOGY_INDEX_PATH, 'wb') as f:
        pickle.dump(_etymology_index, f)

    file_size = os.path.getsize(ETYMOLOGY_INDEX_PATH) / (1024 * 1024)
    print(f"Saved {file_size:.1f}MB etymology index")

    return len(_etymology_index)


def _load_indexes():
    """Load etymology index, wiktextract index, and build forward translations."""
    global _etymology_index, _wiktextract_index, _forward_translations, _indexes_loaded

    if _indexes_loaded:
        return

    # Load etymology index with corruption handling
    if os.path.exists(ETYMOLOGY_INDEX_PATH):
        try:
            with open(ETYMOLOGY_INDEX_PATH, 'rb') as f:
                _etymology_index = pickle.load(f)
        except (EOFError, pickle.UnpicklingError):
            print(f"WARNING: Corrupted etymology index, rebuilding...")
            os.remove(ETYMOLOGY_INDEX_PATH)
            build_etymology_index()
            with open(ETYMOLOGY_INDEX_PATH, 'rb') as f:
                _etymology_index = pickle.load(f)
    else:
        print(f"WARNING: Etymology index not found at {ETYMOLOGY_INDEX_PATH}")
        print("Run build_etymology_index() first.")
        _etymology_index = {}

    # Load wiktextract index and build forward translations
    if os.path.exists(WIKTEXTRACT_INDEX_PATH):
        with open(WIKTEXTRACT_INDEX_PATH, 'rb') as f:
            _wiktextract_index = pickle.load(f)

        # Build forward translation index: english_word -> {lang: foreign_word}
        # First foreign word per language = Wiktionary's primary translation
        _forward_translations = {}
        for lang, words in _wiktextract_index.items():
            for foreign_word, concepts in words.items():
                for concept in concepts:
                    eng = concept.get('english_word', '') if isinstance(concept, dict) else str(concept)
                    if eng:
                        if eng not in _forward_translations:
                            _forward_translations[eng] = {}
                        if lang not in _forward_translations[eng]:
                            _forward_translations[eng][lang] = foreign_word
    else:
        _wiktextract_index = {}
        _forward_translations = {}

    _indexes_loaded = True


def load_indexes():
    """Public wrapper to load indexes."""
    _load_indexes()


def get_ancestors(concept: str) -> list[dict]:
    """
    Extract ancestor chain from etymology_templates.

    Looks for 'inh' (inherited) and 'der' (derived) entries.
    Builds chain: English -> Middle English -> Old English -> Proto-Germanic -> PIE

    Args:
        concept: English word to look up

    Returns:
        List of dicts: {"lang": str, "word": str, "relation": str}
    """
    _load_indexes()

    word = concept.lower().strip()
    if word not in _etymology_index:
        return []

    ancestors = []
    templates = _etymology_index[word].get('templates', [])

    # Track seen to avoid duplicates
    seen = set()

    for tmpl in templates:
        name = tmpl.get('name', '')
        args = tmpl.get('args', {})

        # inh = inherited, der = derived, bor = borrowed, slb = semi-learned borrowing
        if name in ('inh', 'inherited', 'der', 'derived', 'bor', 'borrowed', 'slb', 'inh+'):
            lang_code = args.get('1', args.get('2', ''))
            source_word = args.get('2', args.get('3', args.get('4', '')))

            # Sometimes the structure is different
            if not source_word:
                source_word = args.get('alt', args.get('t', ''))

            if lang_code and source_word:
                key = (lang_code, source_word)
                if key not in seen:
                    seen.add(key)
                    relation = 'inherited' if name.startswith('inh') else 'derived' if name.startswith('der') else 'borrowed'
                    ancestors.append({
                        'lang': lang_code,
                        'word': source_word,
                        'relation': relation
                    })

    return ancestors


def get_cognates(concept: str) -> list[dict]:
    """
    Extract cognates from etymology_templates.

    Looks for 'cog' (cognate) entries and groups by language.

    Args:
        concept: English word to look up

    Returns:
        List of dicts: {"lang": str, "word": str}
    """
    _load_indexes()

    word = concept.lower().strip()
    if word not in _etymology_index:
        return []

    cognates = []
    templates = _etymology_index[word].get('templates', [])

    seen = set()

    for tmpl in templates:
        name = tmpl.get('name', '')
        args = tmpl.get('args', {})

        # cog = cognate, ncog = non-cognate comparison, m = mention
        if name in ('cog', 'cognate', 'ncog', 'm', 'mention', 'l', 'link'):
            lang_code = args.get('1', '')
            cog_word = args.get('2', args.get('3', ''))

            if not cog_word:
                cog_word = args.get('alt', args.get('t', ''))

            if lang_code and cog_word:
                key = (lang_code, cog_word)
                if key not in seen:
                    seen.add(key)
                    cognates.append({
                        'lang': lang_code,
                        'word': cog_word
                    })

    return cognates


def get_cross_links(concept: str) -> dict:
    """
    Find cross-language links for target languages.

    Uses forward translations built from wiktextract_index.pkl (41MB).
    First foreign word per language = Wiktionary's primary translation.

    Args:
        concept: English word to look up

    Returns:
        Dict mapping language code to translation: {"de": "König", "la": "rex", ...}
    """
    if _forward_translations is None:
        load_indexes()
    return {lang: fw for lang, fw in _forward_translations.get(concept.lower().strip(), {}).items()
            if lang in TARGET_LANGUAGES and fw and fw != '-'}


def enrich_etymology(concept: str) -> dict:
    """
    Get full etymology enrichment for an English concept.

    Args:
        concept: English word to look up

    Returns:
        Dict with structure:
        {
            "concept": str,
            "ancestors": [{"lang": str, "word": str, "relation": str}],
            "cognates": [{"lang": str, "word": str}],
            "cross_links": {"de": "Wasser", "la": "aqua", ...}
        }
    """
    return {
        "concept": concept,
        "ancestors": get_ancestors(concept),
        "cognates": get_cognates(concept),
        "cross_links": get_cross_links(concept)
    }


def test_etymology():
    """
    Test etymology enrichment with 5 words.

    Tests: water, mother, book, king, star
    """
    print("=== ETYMOLOGY ENRICHER TEST ===")
    print(f"Etymology index path: {ETYMOLOGY_INDEX_PATH}")
    print(f"Wiktextract index path: {WIKTEXTRACT_INDEX_PATH}")
    print()

    # Check files exist
    print(f"Etymology index exists: {os.path.exists(ETYMOLOGY_INDEX_PATH)}")
    print(f"Wiktextract index exists: {os.path.exists(WIKTEXTRACT_INDEX_PATH)}")

    if os.path.exists(ETYMOLOGY_INDEX_PATH):
        size = os.path.getsize(ETYMOLOGY_INDEX_PATH) / (1024 * 1024)
        print(f"Etymology index size: {size:.1f}MB")

    print()

    # Load indexes
    _load_indexes()
    print(f"Etymology index entries: {len(_etymology_index):,}")
    print()

    # Test words
    test_words = ['water', 'mother', 'book', 'king', 'star']

    print("=== TEST RESULTS ===")

    for word in test_words:
        print(f"\n--- {word} ---")

        result = enrich_etymology(word)

        ancestors = result['ancestors']
        cognates = result['cognates']
        cross_links = result['cross_links']

        print(f"  Ancestors: {len(ancestors)}")
        print(f"  Cognates: {len(cognates)}")
        print(f"  Cross-links: {len(cross_links)}")

        # Show ancestor chain
        if ancestors:
            print(f"  Ancestor chain:")
            for anc in ancestors:
                print(f"    -> {anc['lang']}: {anc['word']} ({anc['relation']})")

        # Show some cognates
        if cognates:
            print(f"  Sample cognates (first 5):")
            for cog in cognates[:5]:
                print(f"    {cog['lang']}: {cog['word']}")

        # Show cross-links
        if cross_links:
            print(f"  Cross-links: {cross_links}")

    print("\n=== TEST COMPLETE ===")


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--build':
        build_etymology_index(force_rebuild=True)
    else:
        test_etymology()
