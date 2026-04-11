#!/usr/bin/env python3
"""
Build Morphlex table by combining English translations with etymology data from each language.

OPTIMIZED VERSION:
- Loads ALL language lookups into memory ONCE at startup
- Streams English file ONCE for both concepts and etymologies
- Pre-splits Chinese Traditional/Simplified variants
- Memory usage monitoring with 6GB abort threshold

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
CONCEPTS_TO_FIND = 100

DATA_DIR = '/mnt/pgdata/morphlex/data/open_wordnets'
OUTPUT_FILE = '/mnt/pgdata/morphlex/data/morphlex_test_100.csv'
MASTER_TABLE_FILE = '/mnt/pgdata/morphlex/data/master_table.csv'

# Memory limit in bytes (6GB)
MEMORY_LIMIT_BYTES = 6 * 1024 * 1024 * 1024


# ============== MEMORY MONITORING ==============

def get_memory_usage_mb():
    """Get current process memory usage in MB using /proc/self/status."""
    try:
        with open('/proc/self/status', 'r') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    # VmRSS is in kB
                    kb = int(line.split()[1])
                    return kb / 1024
    except Exception:
        pass
    return 0


def check_memory_limit(context=""):
    """Check if memory usage exceeds limit. Abort if so."""
    usage_mb = get_memory_usage_mb()
    limit_mb = MEMORY_LIMIT_BYTES / (1024 * 1024)
    if usage_mb > limit_mb:
        print(f"ABORT: Memory usage {usage_mb:.1f}MB exceeds limit {limit_mb:.1f}MB at {context}", file=sys.stderr)
        sys.exit(1)
    return usage_mb


# ============== HIT RATE FIX: Diacritic stripping ==============

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
    if ' /' in word:
        parts = [p.strip() for p in word.split(' /')]
    elif '／' in word:
        parts = [p.strip() for p in word.split('／')]
    else:
        parts = [word]
    return [p for p in parts if p]


# ============== CLASSIFICATION LAYER ==============

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
    """
    if not templates:
        fallback = classify_from_etymology_text(etymology_text)
        if fallback:
            return fallback
        if not etymology_text:
            return 'UNKNOWN'
        return 'UNKNOWN'

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

        if 'root' in name:
            has_root = True
            continue

        if name in ('inh', 'inh+', 'inherited'):
            has_inh = True
            continue

        if name in ('bor', 'bor+', 'lbor', 'borrowed', 'loanword'):
            has_bor = True
            continue

        if name in ('der', 'der+', 'derived'):
            target_lang = args.get('2', args.get('1', ''))
            if is_proto_language(target_lang):
                has_der_to_proto = True
            else:
                has_der = True
            continue

        if name in ('suffix', 'suf', 'prefix', 'pre', 'affix', 'af'):
            has_derivation_affix = True
            continue

        if name in ('compound', 'com', 'surf', 'surface analysis'):
            has_compound = True
            continue

        if name in ('sl', 'semantic loan', 'calque', 'cal', 'slbor', 'translit'):
            has_loan = True
            continue

        if 'noun of place' in name or 'tool noun' in name or 'etym-iyya' in name or \
           'verbal noun' in name or 'participle' in name or 'nisba' in name or \
           'agent noun' in name or 'deverbal' in name or 'denominal' in name:
            has_derivation_affix = True
            continue

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

    fallback = classify_from_etymology_text(etymology_text)
    if fallback:
        return fallback

    return 'UNKNOWN'


def classify_from_etymology_text(etymology_text):
    """Fallback classification from etymology_text using Wiktextract expansion patterns."""
    if not etymology_text:
        return None

    text = etymology_text.lower()

    if text.startswith('borrowed from') or 'a]borrowed from' in text:
        return 'BORROWED'

    if text.startswith('inherited from') or 'a]inherited from' in text:
        return 'ROOT_INHERITED'

    proto_match = re.search(r'from proto-\w+|from pie ', text)
    if proto_match:
        return 'ROOT_INHERITED'

    if re.search(r'from middle \w+.*from old \w+', text):
        return 'ROOT_INHERITED'

    if re.search(r'from the (adjective|verb|noun|root)', text):
        return 'DERIVATION'

    if re.search(r'with suffix|with prefix|\+ -\w+|-\w+ \+', text):
        return 'DERIVATION'

    if 'compound of' in text or re.search(r'\w+ \+ \w+', text):
        return 'COMPOUND'

    if 'ultimately from' in text and ('latin' in text or 'greek' in text or 'arabic' in text):
        return 'BORROWED'

    return None


def extract_root(templates):
    """Extract root consonants from any template with 'root' in the name."""
    for t in templates:
        name = t.get('name', '').lower()
        if 'root' in name:
            args = t.get('args', {})
            root_parts = []
            for i in range(2, 10):
                part = args.get(str(i), '')
                if part:
                    root_parts.append(part)
            if root_parts:
                return '-'.join(root_parts)
            if args.get('1') and not args.get('2'):
                return args.get('1', '')
    return ''


def extract_derivation_info(templates):
    """Extract derivation rule and source from suffix/prefix/affix templates."""
    derivation_rule = ''
    derivation_source = ''

    for t in templates:
        name = t.get('name', '').lower()
        args = t.get('args', {})

        if name in {'suffix', 'suf'}:
            affix = args.get('3', args.get('alt1', ''))
            derivation_rule = f"suffix -{affix}" if affix else "suffix"
            derivation_source = args.get('2', '')
            gloss = args.get('t', args.get('gloss', ''))
            if gloss and derivation_source:
                derivation_source = f"{derivation_source} ({gloss})"
            break

        elif name in {'prefix'}:
            affix = args.get('3', args.get('alt1', ''))
            derivation_rule = f"prefix {affix}-" if affix else "prefix"
            derivation_source = args.get('2', '')
            gloss = args.get('t', args.get('gloss', ''))
            if gloss and derivation_source:
                derivation_source = f"{derivation_source} ({gloss})"
            break

        elif name in {'affix', 'af'}:
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
            parts = [args.get(str(i), '') for i in range(2, 10) if args.get(str(i))]
            if parts:
                derivation_source = ' + '.join(parts)
            break

    return derivation_rule, derivation_source


def extract_compound_parts(templates):
    """Extract compound parts from compound/affix templates."""
    parts = []

    for t in templates:
        name = t.get('name', '').lower()
        if name not in {'compound', 'com', 'surf', 'affix', 'af'}:
            continue

        args = t.get('args', {})
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
    """Find deepest inh or der chain to proto-language."""
    proto_forms = []

    for t in templates:
        name = t.get('name', '').lower()
        if name in ('inh', 'inh+', 'inherited', 'der', 'der+', 'derived'):
            args = t.get('args', {})
            lang = args.get('2', args.get('1', ''))
            word = args.get('3', args.get('2', ''))

            if is_proto_language(lang):
                expansion = t.get('expansion', '')
                if expansion and 'Proto' in expansion:
                    proto_forms.append(expansion)
                elif word:
                    proto_forms.append(f"{lang} {word}")

    return proto_forms[0] if proto_forms else ''


def parse_etymology_templates(templates, etymology_text=''):
    """Parse etymology templates into structured classification fields."""
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
    """Stream master_table.csv, building english_word -> synset_id lookup."""
    lookup = {}

    if not os.path.exists(master_table_file):
        print(f"WARNING: master_table.csv not found at {master_table_file}", file=sys.stderr)
        return lookup

    print(f"Building english_word -> synset_id lookup from {master_table_file}...", file=sys.stderr)

    with open(master_table_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames:
            print("WARNING: master_table.csv has no headers", file=sys.stderr)
            return lookup

        synset_col = None
        english_col = None

        for col in fieldnames:
            col_lower = col.lower()
            if col_lower == 'synset_id' or col_lower == 'synset':
                synset_col = col
            elif col_lower in ('word', 'en', 'english', 'english_word'):
                english_col = col

        if not synset_col or not english_col:
            print(f"WARNING: Missing columns. Found: {fieldnames}", file=sys.stderr)
            return lookup

        print(f"  Using columns: synset_id='{synset_col}', english_word='{english_col}'", file=sys.stderr)

        row_count = 0
        for row in reader:
            row_count += 1
            synset_id = row.get(synset_col, '').strip()
            english_word = row.get(english_col, '').strip()

            if english_word and synset_id:
                lookup[english_word.lower()] = synset_id

        print(f"  Loaded {len(lookup)} unique english_word -> synset_id mappings from {row_count} rows", file=sys.stderr)

    return lookup


def get_concept_id(english_word, synset_lookup):
    """Look up concept_id for an english_word."""
    if not synset_lookup:
        return 'UNMAPPED'
    synset_id = synset_lookup.get(english_word.lower())
    return synset_id if synset_id else 'UNMAPPED'


# ============== OPTIMIZED LOOKUP BUILDING ==============

def build_full_language_lookup(lang_file, is_chinese=False):
    """
    Build complete word -> etymology lookup for a language file.
    Stores ONLY needed fields: etymology_text, etymology_templates, pos, forms_count.

    For Chinese, pre-splits Traditional/Simplified variants.

    Returns: dict {stripped_word: entry_data}
    """
    lookup = {}

    if not os.path.exists(lang_file):
        print(f"  WARNING: File not found: {lang_file}", file=sys.stderr)
        return lookup

    entries_read = 0
    entries_with_etym = 0

    with open(lang_file, 'r', encoding='utf-8') as f:
        for line in f:
            entries_read += 1
            entry = json.loads(line)
            word = entry.get('word', '')
            if not word:
                continue

            etymology_text = entry.get('etymology_text', '')
            etymology_templates = entry.get('etymology_templates', [])
            forms = entry.get('forms', [])

            # Only store entries that have etymology data (saves memory)
            if not etymology_text and not etymology_templates:
                continue

            entries_with_etym += 1

            entry_data = {
                'etymology_text': etymology_text[:500] if etymology_text else '',
                'etymology_templates': etymology_templates,
                'pos': entry.get('pos', ''),
                'forms_count': len(forms) if forms else 0,
            }

            # Store by stripped word for diacritic-insensitive lookup
            stripped_word = strip_diacritics(word)

            # Prefer entries with more templates
            if stripped_word not in lookup or (etymology_templates and
                len(etymology_templates) > len(lookup[stripped_word].get('etymology_templates', []))):
                lookup[stripped_word] = entry_data

            # For Chinese, also store split variants
            if is_chinese:
                variants = split_chinese_variants(word)
                for variant in variants:
                    sv = strip_diacritics(variant)
                    if sv != stripped_word:
                        if sv not in lookup or (etymology_templates and
                            len(etymology_templates) > len(lookup[sv].get('etymology_templates', []))):
                            lookup[sv] = entry_data

    print(f"  Loaded {len(lookup)} word lookups from {entries_read:,} entries ({entries_with_etym:,} with etymology)", file=sys.stderr)
    return lookup


def stream_english_for_concepts_and_etymology(english_file, concepts_needed):
    """
    Stream English Wiktextract file ONCE to collect:
    1. Concepts with translations to target languages
    2. Etymology data for English words

    Returns: (concepts dict, english_etymology_lookup dict)
    """
    concepts = {}
    english_etym = {}
    lines_read = 0

    print(f"Streaming {english_file} for concepts and etymologies...", file=sys.stderr)

    with open(english_file, 'r', encoding='utf-8') as f:
        for line in f:
            lines_read += 1
            if lines_read % 500000 == 0:
                print(f"  ...processed {lines_read:,} lines, found {len(concepts)} concepts", file=sys.stderr)

            entry = json.loads(line)

            # Only English language entries
            if entry.get('lang', '') != 'English':
                continue

            word = entry.get('word', '')
            if not word:
                continue

            # Always collect etymology for English words (for lookup later)
            etymology_text = entry.get('etymology_text', '')
            etymology_templates = entry.get('etymology_templates', [])

            if etymology_text or etymology_templates:
                stripped_word = strip_diacritics(word)
                if stripped_word not in english_etym or (etymology_templates and
                    len(etymology_templates) > len(english_etym[stripped_word].get('etymology_templates', []))):
                    english_etym[stripped_word] = {
                        'etymology_text': etymology_text[:500] if etymology_text else '',
                        'etymology_templates': etymology_templates,
                        'pos': entry.get('pos', ''),
                        'forms_count': len(entry.get('forms', [])),
                    }

            # Stop collecting concepts once we have enough
            if len(concepts) >= concepts_needed:
                # But continue collecting etymologies for words we need
                if word in concepts:
                    continue
                # Check if this word is in any concept's translations - skip for now
                continue

            # Check for translations
            translations = entry.get('translations', [])
            if not translations:
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

    print(f"  Found {len(concepts)} concepts from {lines_read:,} lines", file=sys.stderr)
    print(f"  Collected {len(english_etym)} English etymology entries", file=sys.stderr)

    return concepts, english_etym


def lookup_word(word, lookup, is_chinese=False):
    """
    Look up a word using stripped diacritic matching.
    For Chinese, also try splitting variants.
    """
    stripped_word = strip_diacritics(word)

    if stripped_word in lookup:
        return lookup[stripped_word]

    # For Chinese, try splitting variants
    if is_chinese:
        variants = split_chinese_variants(word)
        for variant in variants:
            sv = strip_diacritics(variant)
            if sv in lookup:
                return lookup[sv]

    return {}


def main():
    start_time = datetime.now()
    print(f"Start: {start_time.isoformat()}", file=sys.stderr)

    # Initial memory check
    initial_mem = check_memory_limit("startup")
    print(f"Initial memory: {initial_mem:.1f}MB", file=sys.stderr)

    # ============== PHASE 1: LOAD ALL LOOKUPS ==============
    print("\n=== PHASE 1: Loading all lookups into memory ===", file=sys.stderr)

    # Step 1a: Build synset lookup from master_table
    synset_lookup = build_english_to_synset_lookup(MASTER_TABLE_FILE)
    mem_after_synset = check_memory_limit("after synset lookup")
    print(f"Memory after synset lookup: {mem_after_synset:.1f}MB", file=sys.stderr)

    # Step 1b: Stream English file for concepts AND etymologies (ONE PASS)
    english_file = os.path.join(DATA_DIR, 'kaikki-english.jsonl')
    concepts, english_etym_lookup = stream_english_for_concepts_and_etymology(english_file, CONCEPTS_TO_FIND)

    if not concepts:
        print("ERROR: No concepts found!", file=sys.stderr)
        sys.exit(1)

    mem_after_english = check_memory_limit("after English")
    print(f"Memory after English: {mem_after_english:.1f}MB", file=sys.stderr)

    # Step 1c: Build lookups for all other languages
    lang_lookups = {}

    for lang_name in TARGET_LANGS:
        lang_code = LANG_CODES[lang_name]
        lang_file = os.path.join(DATA_DIR, LANG_FILE_MAP[lang_name])
        is_chinese = (lang_name == 'Chinese')

        print(f"Loading {lang_name} ({lang_code})...", file=sys.stderr)
        lang_lookups[lang_name] = build_full_language_lookup(lang_file, is_chinese=is_chinese)

        mem_now = check_memory_limit(f"after {lang_name}")

    # Final memory check after all lookups loaded
    peak_mem = check_memory_limit("after all lookups")
    print(f"\n=== All lookups loaded. Peak memory: {peak_mem:.1f}MB ===", file=sys.stderr)

    # ============== PHASE 2: PROCESS CONCEPTS ==============
    print("\n=== PHASE 2: Processing concepts (no file re-reading) ===", file=sys.stderr)

    rows = []
    hits_by_lang = {}
    morph_type_counts = Counter()

    # Process English (source words)
    print(f"Processing English...", file=sys.stderr)
    eng_hits = 0

    for eng_word, data in concepts.items():
        etym_data = lookup_word(eng_word, english_etym_lookup)
        templates = etym_data.get('etymology_templates', [])
        etymology_text = etym_data.get('etymology_text', '')
        classification = parse_etymology_templates(templates, etymology_text)

        if templates or etymology_text:
            eng_hits += 1
            morph_type_counts[classification['morph_type']] += 1

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

    # Process target languages (using pre-loaded lookups)
    for lang_name in TARGET_LANGS:
        lang_code = LANG_CODES[lang_name]
        is_chinese = (lang_name == 'Chinese')
        lookup = lang_lookups[lang_name]

        print(f"Processing {lang_name} ({lang_code})...", file=sys.stderr)

        lang_hits = 0
        for eng_word, data in concepts.items():
            trans_words = data['translations'].get(lang_name, [])
            concept_id = get_concept_id(eng_word, synset_lookup)

            if not trans_words:
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
            best_etym = lookup_word(best_word, lookup, is_chinese)

            for tw in trans_words:
                etym_data = lookup_word(tw, lookup, is_chinese)
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

    # ============== PHASE 3: WRITE CSV ==============
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

    # ============== PHASE 4: PRINT STATS ==============
    print(f"\n{'='*60}")
    print(f"MORPHLEX TABLE BUILD COMPLETE")
    print(f"{'='*60}")

    print(f"\nTotal concepts: {len(concepts)}")

    print(f"\nPer-language hit rates (of {len(concepts)}):")
    for lang_code in ['en', 'ar', 'de', 'he', 'tr', 'sa', 'la', 'grc', 'zh', 'ja']:
        hits = hits_by_lang.get(lang_code, 0)
        pct = 100 * hits / len(concepts) if concepts else 0
        print(f"  {lang_code}: {hits}/{len(concepts)} ({pct:.0f}%)")

    print(f"\nMorph type distribution (all rows with etymology):")
    for mtype, count in sorted(morph_type_counts.items(), key=lambda x: -x[1]):
        print(f"  {mtype}: {count}")

    # Concept ID statistics
    en_rows = [r for r in rows if r.get('lang') == 'en']
    mapped_concepts = sum(1 for r in en_rows if r.get('concept_id') != 'UNMAPPED')
    unmapped_concepts = len(en_rows) - mapped_concepts
    unique_concept_ids = len(set(r.get('concept_id') for r in en_rows if r.get('concept_id') != 'UNMAPPED'))

    print(f"\nConcept ID mapping (of {len(en_rows)} concepts):")
    print(f"  Mapped to synset_id: {mapped_concepts}")
    print(f"  UNMAPPED: {unmapped_concepts}")
    print(f"  Unique concept_ids: {unique_concept_ids}")

    print(f"\nTiming:")
    print(f"  Total time: {elapsed:.1f}s")

    if len(concepts) > 0:
        time_per_concept = elapsed / len(concepts)
        estimated_9000 = time_per_concept * 9000
        print(f"  Estimated time for 9000 concepts: {estimated_9000/60:.1f} minutes")

    print(f"\nMemory usage:")
    print(f"  Peak memory (after all lookups): {peak_mem:.1f}MB")
    final_mem = get_memory_usage_mb()
    print(f"  Final memory: {final_mem:.1f}MB")

    print(f"\nOutput saved to: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
