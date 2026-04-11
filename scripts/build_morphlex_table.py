#!/usr/bin/env python3
"""
Build Morphlex table by combining English translations with etymology data from each language.

Reads English Wiktextract file to get translations, then looks up each translated word
in its respective language file to pull etymology templates.

Memory-efficient: processes one language file at a time.

Features:
- Hit rate improvements: diacritic stripping, Chinese slash splitting
- Classification layer: morph_type, root, derivation_rule, compound_parts, cognates, proto_root
- Template-based classification using Wiktextract template names (no hardcoded strings)
"""

import csv
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime

# Target languages and their file mappings
LANG_FILE_MAP = {
    'Arabic': 'kaikki-arabic.jsonl',
    'German': 'kaikki-german.jsonl',
    'Hebrew': 'kaikki-hebrew.jsonl',
    'Turkish': 'kaikki-turkish.jsonl',
    'Sanskrit': 'kaikki-sanskrit.jsonl',
    'Latin': 'kaikki-latin.jsonl',
    'Ancient Greek': 'kaikki-ancient-greek.jsonl',
    'Chinese': 'kaikki-chinese.jsonl',
    'Japanese': 'kaikki-japanese.jsonl',
    'English': 'kaikki-english.jsonl',
}

# Short codes for output
LANG_CODES = {
    'Arabic': 'ar',
    'German': 'de',
    'Hebrew': 'he',
    'Turkish': 'tr',
    'Sanskrit': 'sa',
    'Latin': 'la',
    'Ancient Greek': 'grc',
    'Chinese': 'zh',
    'Japanese': 'ja',
    'English': 'en',
}

TARGET_LANGS = {'Arabic', 'German', 'Hebrew', 'Turkish', 'Sanskrit', 'Latin', 'Ancient Greek', 'Chinese', 'Japanese'}
MIN_LANGS_REQUIRED = 3
CONCEPTS_TO_FIND = 20

DATA_DIR = '/mnt/pgdata/morphlex/data/open_wordnets'
OUTPUT_FILE = '/mnt/pgdata/morphlex/data/morphlex_test_20.csv'
MASTER_TABLE_FILE = '/mnt/pgdata/morphlex/data/master_table.csv'


# ============== HIT RATE FIX 1: Diacritic stripping ==============

def strip_diacritics(text):
    """Strip all diacritics and combining marks from text."""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def split_chinese_variants(word):
    """
    For Chinese words with traditional/simplified variants like '貓 /猫',
    return list of individual words to try.
    """
    parts = []
    # Split on ' /' or '／'
    if ' /' in word:
        parts = [p.strip() for p in word.split(' /')]
    elif '／' in word:
        parts = [p.strip() for p in word.split('／')]
    else:
        parts = [word]
    return [p for p in parts if p]


# ============== CLASSIFICATION LAYER ==============
# Classification based on Wiktextract template names - NO hardcoded language/text patterns


def is_proto_language(lang_code):
    """Check if a language code represents a proto-language."""
    if not lang_code:
        return False
    lc = lang_code.lower()
    return lc.startswith('proto') or lc.endswith('-pro') or lc.startswith('ine-pro') or \
           lc.startswith('gem-pro') or lc.startswith('gmw-pro') or lc.startswith('sem-pro')


def classify_morph_type(templates, etymology_text=''):
    """
    Classify morphological type from etymology templates using template names.

    Classification rules (based on Wiktextract template naming conventions):
    1. Any template with "root" in name → ROOT
    2. inh, inh+ → ROOT_INHERITED
    3. bor, bor+, lbor → BORROWED
    4. der, der+ → check if proto-language → ROOT_INHERITED, else DERIVED_FROM
    5. suffix, suf, prefix, pre, affix, af, com → DERIVATION or COMPOUND
    6. compound, surf, surface analysis → COMPOUND
    7. sl, semantic loan, calque, cal → BORROWED
    8. Pattern-based derivation templates (noun of place, tool noun, etym-iyya) → DERIVATION

    Falls back to etymology_text expansion patterns when templates are empty.
    """
    if not templates:
        # Try fallback classification from etymology_text (Wiktextract expansion patterns)
        fallback = classify_from_etymology_text(etymology_text)
        if fallback:
            return fallback
        # If no etymology_text either, it's truly UNKNOWN
        if not etymology_text:
            return 'UNKNOWN'
        return 'UNKNOWN'

    # Analyze all template names
    has_root = False
    has_inh = False
    has_bor = False
    has_der = False
    has_der_to_proto = False
    has_derivation_affix = False
    has_compound = False
    has_loan = False

    for t in templates:
        name = t.get('name', '').lower()
        args = t.get('args', {})

        # 1. Any template with "root" in name → ROOT
        if 'root' in name:
            has_root = True
            continue

        # 2. inh, inh+ → ROOT_INHERITED
        if name in ('inh', 'inh+', 'inherited'):
            has_inh = True
            continue

        # 3. bor, bor+, lbor → BORROWED
        if name in ('bor', 'bor+', 'lbor', 'borrowed', 'loanword'):
            has_bor = True
            continue

        # 4. der, der+ → check target language
        if name in ('der', 'der+', 'derived'):
            # Check if deriving from proto-language
            target_lang = args.get('2', args.get('1', ''))
            if is_proto_language(target_lang):
                has_der_to_proto = True
            else:
                has_der = True
            continue

        # 5. Affix/derivation templates
        if name in ('suffix', 'suf', 'prefix', 'pre', 'affix', 'af'):
            has_derivation_affix = True
            continue

        # 6. Compound templates
        if name in ('compound', 'com', 'surf', 'surface analysis'):
            has_compound = True
            continue

        # 7. Loan/calque templates
        if name in ('sl', 'semantic loan', 'calque', 'cal', 'slbor', 'translit'):
            has_loan = True
            continue

        # 8. Pattern-based derivation templates (any language)
        if 'noun of place' in name or 'tool noun' in name or 'etym-iyya' in name or \
           'verbal noun' in name or 'participle' in name or 'nisba' in name or \
           'agent noun' in name or 'deverbal' in name or 'denominal' in name:
            has_derivation_affix = True
            continue

        # Also check for m, l, mention templates (these just cite words, not classify)
        # These don't contribute to classification

    # Classification priority logic
    if has_compound and has_derivation_affix:
        return 'COMPOUND_DERIVATION'
    if has_compound:
        return 'COMPOUND'
    if has_derivation_affix:
        return 'DERIVATION'
    if has_bor or has_loan:
        return 'BORROWED'
    if has_root and not has_derivation_affix and not has_compound:
        return 'ROOT'
    if has_inh or has_der_to_proto:
        return 'ROOT_INHERITED'
    if has_der:
        return 'DERIVED_FROM'

    # If we have templates but couldn't classify, try text fallback
    fallback = classify_from_etymology_text(etymology_text)
    if fallback:
        return fallback

    return 'UNKNOWN'


def classify_from_etymology_text(etymology_text):
    """
    Fallback classification from etymology_text using Wiktextract expansion patterns.
    These patterns come from template expansions, so they ARE systematic.
    Returns morph_type or None if no clear pattern found.
    """
    if not etymology_text:
        return None

    text = etymology_text.lower()

    # Wiktextract expansion patterns from templates:

    # BORROWED: "Borrowed from X" is the standard bor template expansion
    if text.startswith('borrowed from') or 'a]borrowed from' in text:
        return 'BORROWED'

    # ROOT_INHERITED: "Inherited from X" is the standard inh template expansion
    if text.startswith('inherited from') or 'a]inherited from' in text:
        return 'ROOT_INHERITED'

    # DERIVED_FROM: "From X" without borrowed/inherited prefix
    # Check for Proto-language derivation → ROOT_INHERITED
    proto_match = re.search(r'from proto-\w+|from pie ', text)
    if proto_match:
        return 'ROOT_INHERITED'

    # Check for "From Middle X, from Old X" inheritance chain
    if re.search(r'from middle \w+.*from old \w+', text):
        return 'ROOT_INHERITED'

    # DERIVATION: Common derivation patterns
    if re.search(r'from the (adjective|verb|noun|root)', text):
        return 'DERIVATION'

    # Suffix/prefix patterns in text
    if re.search(r'with suffix|with prefix|\+ -\w+|-\w+ \+', text):
        return 'DERIVATION'

    # Compound detection: "X + Y" or "compound of"
    if 'compound of' in text or re.search(r'\w+ \+ \w+', text):
        return 'COMPOUND'

    # Ultimate borrowing (borrowed through multiple languages)
    if 'ultimately from' in text and ('latin' in text or 'greek' in text or 'arabic' in text):
        return 'BORROWED'

    return None


def extract_root(templates):
    """Extract root consonants from any template with 'root' in the name."""
    for t in templates:
        name = t.get('name', '').lower()
        # Match any template with "root" in name (ar-root, he-root, sa-root, root, rootbox, etc.)
        if 'root' in name:
            args = t.get('args', {})
            # Root args are typically positional: arg 1 is lang, arg 2+ are root consonants
            root_parts = []
            for i in range(2, 10):
                part = args.get(str(i), '')
                if part:
                    root_parts.append(part)
            if root_parts:
                return '-'.join(root_parts)
            # Some root templates use arg 1 directly
            if args.get('1') and not args.get('2'):
                return args.get('1', '')
    return ''


def extract_derivation_info(templates):
    """
    Extract derivation rule and source from suffix/prefix/affix templates.
    Returns: (derivation_rule, derivation_source)
    """
    derivation_rule = ''
    derivation_source = ''

    for t in templates:
        name = t.get('name', '').lower()
        args = t.get('args', {})

        if name in {'suffix', 'suf'}:
            affix = args.get('3', args.get('alt1', ''))
            if affix:
                derivation_rule = f"suffix -{affix}"
            else:
                derivation_rule = "suffix"
            # Source word is typically arg 2
            derivation_source = args.get('2', '')
            gloss = args.get('t', args.get('gloss', ''))
            if gloss and derivation_source:
                derivation_source = f"{derivation_source} ({gloss})"
            break

        elif name in {'prefix'}:
            affix = args.get('3', args.get('alt1', ''))
            if affix:
                derivation_rule = f"prefix {affix}-"
            else:
                derivation_rule = "prefix"
            derivation_source = args.get('2', '')
            gloss = args.get('t', args.get('gloss', ''))
            if gloss and derivation_source:
                derivation_source = f"{derivation_source} ({gloss})"
            break

        elif name in {'affix', 'af'}:
            # Affix can have multiple parts
            parts = []
            for i in range(3, 10):
                part = args.get(str(i), '')
                if part:
                    parts.append(part)
            if parts:
                derivation_rule = f"affix {'+'.join(parts)}"
            derivation_source = args.get('2', '')
            break

        elif name == 'ar-noun of place':
            derivation_rule = "noun of place"
            derivation_source = args.get('1', args.get('2', ''))
            break

        elif name == 'ar-tool noun':
            derivation_rule = "tool noun"
            derivation_source = args.get('1', args.get('2', ''))
            break

        elif name == 'ar-etym-iyya':
            derivation_rule = "nisba -iyya"
            derivation_source = args.get('1', '')
            break

        elif name == 'surface analysis':
            derivation_rule = "surface analysis"
            # Args may contain component analysis
            parts = [args.get(str(i), '') for i in range(2, 10) if args.get(str(i))]
            if parts:
                derivation_source = ' + '.join(parts)
            break

    return derivation_rule, derivation_source


def extract_compound_parts(templates):
    """
    Extract compound parts from compound/affix templates.
    Returns: JSON list of {word, gloss} dicts
    """
    parts = []

    for t in templates:
        name = t.get('name', '').lower()
        if name not in {'compound', 'com', 'surf', 'affix', 'af'}:
            continue

        args = t.get('args', {})

        # Components are typically in positional args starting at 2 or 3
        # For compound: 1=lang, 2=first word, 3=second word, etc.
        # Glosses may be in t1, t2, etc. or alt1, alt2
        i = 2
        while True:
            word = args.get(str(i), '')
            if not word:
                break

            gloss = args.get(f't{i-1}', args.get(f'gloss{i-1}', ''))
            parts.append({'word': word, 'gloss': gloss})
            i += 1

        if parts:
            break

    return json.dumps(parts) if parts else ''


def extract_cognates(templates):
    """Extract cognates from 'cog' templates."""
    cognates = []

    for t in templates:
        if t.get('name', '').lower() == 'cog':
            args = t.get('args', {})
            lang = args.get('1', '')
            word = args.get('2', '')
            if lang and word:
                cognates.append({'lang': lang, 'word': word})

    return json.dumps(cognates) if cognates else ''


def extract_proto_root(templates):
    """
    Find deepest inh or der chain to proto-language.
    Returns string like "Proto-Semitic *bayt-"
    """
    proto_forms = []

    for t in templates:
        name = t.get('name', '').lower()
        # Check inheritance/derivation templates including + variants
        if name in ('inh', 'inh+', 'inherited', 'der', 'der+', 'derived'):
            args = t.get('args', {})
            lang = args.get('2', args.get('1', ''))
            word = args.get('3', args.get('2', ''))

            # Check if it's a proto-language using our helper
            if is_proto_language(lang):
                expansion = t.get('expansion', '')
                if expansion and 'Proto' in expansion:
                    proto_forms.append(expansion)
                elif word:
                    proto_forms.append(f"{lang} {word}")

    # Return the first (deepest in etymology chain is typically first)
    return proto_forms[0] if proto_forms else ''


def parse_etymology_templates(templates, etymology_text=''):
    """
    Parse etymology templates into structured classification fields.
    Returns dict with all classification columns.
    """
    return {
        'morph_type': classify_morph_type(templates, etymology_text),
        'root': extract_root(templates),
        'derivation_rule': extract_derivation_info(templates)[0],
        'derivation_source': extract_derivation_info(templates)[1],
        'compound_parts': extract_compound_parts(templates),
        'cognates': extract_cognates(templates),
        'proto_root': extract_proto_root(templates),
    }


# ============== CONCEPT ID LOOKUP ==============

def build_english_to_synset_lookup(master_table_file):
    """
    Stream master_table.csv line by line, building english_word -> synset_id lookup.
    Only keeps the small lookup dict in memory, not the full 51.5MB file.

    Returns: dict mapping english_word (lowercase) -> synset_id
    """
    lookup = {}

    if not os.path.exists(master_table_file):
        print(f"WARNING: master_table.csv not found at {master_table_file}", file=sys.stderr)
        return lookup

    print(f"Building english_word -> synset_id lookup from {master_table_file}...", file=sys.stderr)

    with open(master_table_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        # Find the English word column - could be 'word', 'en', 'english', etc.
        # And synset_id column
        fieldnames = reader.fieldnames
        if not fieldnames:
            print("WARNING: master_table.csv has no headers", file=sys.stderr)
            return lookup

        # Identify columns
        synset_col = None
        english_col = None

        for col in fieldnames:
            col_lower = col.lower()
            if col_lower == 'synset_id' or col_lower == 'synset':
                synset_col = col
            elif col_lower == 'word' or col_lower == 'en' or col_lower == 'english' or col_lower == 'english_word':
                english_col = col

        if not synset_col:
            print(f"WARNING: No synset_id column found in master_table. Columns: {fieldnames}", file=sys.stderr)
            return lookup

        if not english_col:
            print(f"WARNING: No English word column found in master_table. Columns: {fieldnames}", file=sys.stderr)
            return lookup

        print(f"  Using columns: synset_id='{synset_col}', english_word='{english_col}'", file=sys.stderr)

        row_count = 0
        for row in reader:
            row_count += 1
            synset_id = row.get(synset_col, '').strip()
            english_word = row.get(english_col, '').strip()

            if english_word and synset_id:
                # Store lowercase for case-insensitive lookup
                lookup[english_word.lower()] = synset_id

        print(f"  Loaded {len(lookup)} unique english_word -> synset_id mappings from {row_count} rows", file=sys.stderr)

    return lookup


def get_concept_id(english_word, synset_lookup):
    """
    Look up concept_id for an english_word.
    Returns synset_id if found, 'UNMAPPED' otherwise.
    """
    if not synset_lookup:
        return 'UNMAPPED'

    # Case-insensitive lookup
    synset_id = synset_lookup.get(english_word.lower())
    return synset_id if synset_id else 'UNMAPPED'


# ============== CORE FUNCTIONS ==============

def stream_english_for_concepts(english_file, concepts_needed):
    """
    Stream English Wiktextract file to find entries with translations to target languages.
    Returns dict: english_word -> {sense: str, translations: {lang: [words]}}
    """
    concepts = {}
    lines_read = 0

    print(f"Streaming {english_file} for concepts...", file=sys.stderr)

    with open(english_file, 'r', encoding='utf-8') as f:
        for line in f:
            lines_read += 1
            if lines_read % 100000 == 0:
                print(f"  ...processed {lines_read:,} lines, found {len(concepts)} concepts", file=sys.stderr)

            entry = json.loads(line)

            # Only English language entries
            if entry.get('lang', '') != 'English':
                continue

            word = entry.get('word', '')
            translations = entry.get('translations', [])

            if not translations or not word:
                continue

            # Skip if we already have this word
            if word in concepts:
                continue

            # Group translations by language
            lang_translations = {}
            first_sense = None

            for t in translations:
                lang = t.get('lang', '')
                tword = t.get('word', '')
                sense = t.get('sense', '')

                if lang in TARGET_LANGS and tword:
                    if lang not in lang_translations:
                        lang_translations[lang] = []
                    lang_translations[lang].append(tword)
                    if first_sense is None and sense:
                        first_sense = sense

            # Check if we have translations in at least MIN_LANGS_REQUIRED target languages
            if len(lang_translations) >= MIN_LANGS_REQUIRED:
                concepts[word] = {
                    'sense': first_sense or '',
                    'pos': entry.get('pos', ''),
                    'translations': lang_translations,
                }

                if len(concepts) >= concepts_needed:
                    break

    print(f"  Found {len(concepts)} concepts from {lines_read:,} lines", file=sys.stderr)
    return concepts


def build_etymology_lookup_for_language(lang_file, words_to_find, is_chinese=False):
    """
    Stream a language file and build etymology lookup for words we need.
    Uses BOTH exact and stripped diacritic matching.

    Returns: (exact_lookup, stripped_lookup)
    Both are dicts: word -> {etymology_text, etymology_templates, pos, forms_count}
    """
    exact_lookup = {}
    stripped_lookup = {}

    # Pre-compute stripped versions of words we're looking for
    words_set = set(words_to_find)
    stripped_targets = {}
    for w in words_to_find:
        sw = strip_diacritics(w)
        if sw not in stripped_targets:
            stripped_targets[sw] = []
        stripped_targets[sw].append(w)

    if not os.path.exists(lang_file):
        print(f"  WARNING: File not found: {lang_file}", file=sys.stderr)
        return exact_lookup, stripped_lookup

    with open(lang_file, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line)
            word = entry.get('word', '')
            stripped_word = strip_diacritics(word)

            etymology_text = entry.get('etymology_text', '')
            etymology_templates = entry.get('etymology_templates', [])
            forms = entry.get('forms', [])

            entry_data = {
                'etymology_text': etymology_text,
                'etymology_templates': etymology_templates,
                'pos': entry.get('pos', ''),
                'forms_count': len(forms) if forms else 0,
            }

            # Exact match
            if word in words_set:
                if word not in exact_lookup or (etymology_templates and
                    len(etymology_templates) > len(exact_lookup[word].get('etymology_templates', []))):
                    exact_lookup[word] = entry_data

            # Stripped match - map file word to entry, keyed by stripped form
            if stripped_word in stripped_targets:
                if stripped_word not in stripped_lookup or (etymology_templates and
                    len(etymology_templates) > len(stripped_lookup[stripped_word].get('etymology_templates', []))):
                    stripped_lookup[stripped_word] = entry_data

    return exact_lookup, stripped_lookup


def lookup_word(word, exact_lookup, stripped_lookup, is_chinese=False):
    """
    Look up a word, trying exact match first, then stripped match.
    For Chinese, also try splitting on ' /' and '／'.

    Returns entry_data dict or empty dict if not found.
    """
    # Try exact match first
    if word in exact_lookup:
        return exact_lookup[word]

    # Try stripped match
    stripped_word = strip_diacritics(word)
    if stripped_word in stripped_lookup:
        return stripped_lookup[stripped_word]

    # For Chinese, try splitting variants
    if is_chinese:
        variants = split_chinese_variants(word)
        for variant in variants:
            if variant in exact_lookup:
                return exact_lookup[variant]
            sv = strip_diacritics(variant)
            if sv in stripped_lookup:
                return stripped_lookup[sv]

    return {}


def main():
    start_time = datetime.now()
    print(f"Start: {start_time.isoformat()}", file=sys.stderr)

    # Step 0: Build english_word -> synset_id lookup from master_table
    synset_lookup = build_english_to_synset_lookup(MASTER_TABLE_FILE)

    # Step 1: Find concepts from English file
    english_file = os.path.join(DATA_DIR, 'kaikki-english.jsonl')
    concepts = stream_english_for_concepts(english_file, CONCEPTS_TO_FIND)

    if not concepts:
        print("ERROR: No concepts found!", file=sys.stderr)
        sys.exit(1)

    # Collect all words we need to look up per language
    words_by_lang = {}
    for eng_word, data in concepts.items():
        # Add English word itself
        if 'English' not in words_by_lang:
            words_by_lang['English'] = set()
        words_by_lang['English'].add(eng_word)

        # Add translations
        for lang, twords in data['translations'].items():
            if lang not in words_by_lang:
                words_by_lang[lang] = set()
            for tw in twords:
                words_by_lang[lang].add(tw)
                # For Chinese, also add split variants
                if lang == 'Chinese':
                    for variant in split_chinese_variants(tw):
                        words_by_lang[lang].add(variant)

    # Step 2: Process each language file one at a time, build CSV rows
    rows = []
    hits_by_lang = {}
    morph_type_counts = Counter()

    # First, handle English (source words)
    print(f"\nProcessing English...", file=sys.stderr)
    exact_lookup, stripped_lookup = build_etymology_lookup_for_language(
        os.path.join(DATA_DIR, LANG_FILE_MAP['English']),
        words_by_lang.get('English', set())
    )

    eng_hits = 0
    for eng_word, data in concepts.items():
        etym_data = lookup_word(eng_word, exact_lookup, stripped_lookup)
        templates = etym_data.get('etymology_templates', [])
        etymology_text = etym_data.get('etymology_text', '')
        classification = parse_etymology_templates(templates, etymology_text)

        if templates or etymology_text:
            eng_hits += 1
            morph_type_counts[classification['morph_type']] += 1

        # Get concept_id from synset lookup
        concept_id = get_concept_id(eng_word, synset_lookup)

        rows.append({
            'concept_id': concept_id,
            'english_word': eng_word,
            'sense': data['sense'][:100] if data['sense'] else '',
            'lang': 'en',
            'translated_word': eng_word,
            'pos': etym_data.get('pos', data.get('pos', '')),
            'morph_type': classification['morph_type'],
            'root': classification['root'],
            'derivation_rule': classification['derivation_rule'],
            'derivation_source': classification['derivation_source'],
            'compound_parts': classification['compound_parts'],
            'cognates': classification['cognates'],
            'proto_root': classification['proto_root'],
            'etymology_text': etymology_text[:500] if etymology_text else '',
            'forms_count': etym_data.get('forms_count', 0),
        })

    hits_by_lang['en'] = eng_hits
    del exact_lookup, stripped_lookup  # Free memory

    # Now process target languages
    for lang_name in TARGET_LANGS:
        lang_code = LANG_CODES[lang_name]
        lang_file = os.path.join(DATA_DIR, LANG_FILE_MAP[lang_name])
        is_chinese = (lang_name == 'Chinese')

        print(f"Processing {lang_name} ({lang_code})...", file=sys.stderr)

        words_needed = words_by_lang.get(lang_name, set())
        if not words_needed:
            print(f"  No words to look up", file=sys.stderr)
            hits_by_lang[lang_code] = 0
            continue

        # Build lookup for this language
        exact_lookup, stripped_lookup = build_etymology_lookup_for_language(
            lang_file, words_needed, is_chinese=is_chinese
        )

        # Process each concept
        lang_hits = 0
        for eng_word, data in concepts.items():
            trans_words = data['translations'].get(lang_name, [])

            # Get concept_id for this english_word (same for all languages)
            concept_id = get_concept_id(eng_word, synset_lookup)

            if not trans_words:
                # No translation for this language
                rows.append({
                    'concept_id': concept_id,
                    'english_word': eng_word,
                    'sense': data['sense'][:100] if data['sense'] else '',
                    'lang': lang_code,
                    'translated_word': '',
                    'pos': '',
                    'morph_type': '',
                    'root': '',
                    'derivation_rule': '',
                    'derivation_source': '',
                    'compound_parts': '',
                    'cognates': '',
                    'proto_root': '',
                    'etymology_text': '',
                    'forms_count': 0,
                })
                continue

            # Try each translation word, prefer one with etymology data
            best_word = trans_words[0]
            best_etym = lookup_word(best_word, exact_lookup, stripped_lookup, is_chinese)

            for tw in trans_words:
                etym_data = lookup_word(tw, exact_lookup, stripped_lookup, is_chinese)
                if etym_data.get('etymology_templates'):
                    best_word = tw
                    best_etym = etym_data
                    break

            templates = best_etym.get('etymology_templates', [])
            etymology_text = best_etym.get('etymology_text', '')
            classification = parse_etymology_templates(templates, etymology_text)

            if templates or etymology_text:
                lang_hits += 1
                morph_type_counts[classification['morph_type']] += 1

            rows.append({
                'concept_id': concept_id,
                'english_word': eng_word,
                'sense': data['sense'][:100] if data['sense'] else '',
                'lang': lang_code,
                'translated_word': best_word,
                'pos': best_etym.get('pos', ''),
                'morph_type': classification['morph_type'],
                'root': classification['root'],
                'derivation_rule': classification['derivation_rule'],
                'derivation_source': classification['derivation_source'],
                'compound_parts': classification['compound_parts'],
                'cognates': classification['cognates'],
                'proto_root': classification['proto_root'],
                'etymology_text': etymology_text[:500] if etymology_text else '',
                'forms_count': best_etym.get('forms_count', 0),
            })

        hits_by_lang[lang_code] = lang_hits
        del exact_lookup, stripped_lookup  # Free memory

    # Step 3: Write CSV
    print(f"\nWriting CSV to {OUTPUT_FILE}...", file=sys.stderr)

    fieldnames = ['concept_id', 'english_word', 'sense', 'lang', 'translated_word', 'pos',
                  'morph_type', 'root', 'derivation_rule', 'derivation_source',
                  'compound_parts', 'cognates', 'proto_root', 'etymology_text',
                  'forms_count']

    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    # Step 4: Print summary stats to stdout
    print(f"Total concepts: {len(concepts)}")
    print(f"\nPer-language hit rates (of {len(concepts)}):")
    for lang_code in ['en', 'ar', 'de', 'he', 'tr', 'sa', 'la', 'grc', 'zh', 'ja']:
        hits = hits_by_lang.get(lang_code, 0)
        pct = 100 * hits / len(concepts) if concepts else 0
        print(f"  {lang_code}: {hits}/{len(concepts)} ({pct:.0f}%)")

    print(f"\nMorph type distribution (all rows with etymology):")
    for mtype, count in sorted(morph_type_counts.items(), key=lambda x: -x[1]):
        print(f"  {mtype}: {count}")

    # Concept ID statistics
    # Count only English rows (one per concept) to get unique concept stats
    en_rows = [r for r in rows if r.get('lang') == 'en']
    mapped_concepts = sum(1 for r in en_rows if r.get('concept_id') != 'UNMAPPED')
    unmapped_concepts = len(en_rows) - mapped_concepts
    unique_concept_ids = len(set(r.get('concept_id') for r in en_rows if r.get('concept_id') != 'UNMAPPED'))

    print(f"\nConcept ID mapping (of {len(en_rows)} concepts):")
    print(f"  Mapped to synset_id: {mapped_concepts}")
    print(f"  UNMAPPED: {unmapped_concepts}")
    print(f"  Unique concept_ids: {unique_concept_ids}")

    print(f"\nTotal time: {elapsed:.1f}s")

    # Estimate for 9000 concepts
    if len(concepts) > 0:
        time_per_concept = elapsed / len(concepts)
        estimated_9000 = time_per_concept * 9000
        print(f"Estimated time for 9000 concepts: {estimated_9000/60:.1f} minutes")

    print(f"\nOutput saved to: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
