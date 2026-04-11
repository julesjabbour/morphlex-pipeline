#!/usr/bin/env python3
"""
Build Morphlex table by combining English translations with etymology data from each language.

Reads English Wiktextract file to get translations, then looks up each translated word
in its respective language file to pull etymology templates.

Memory-efficient: processes one language file at a time.
"""

import csv
import json
import os
import sys
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


def extract_root_templates(etymology_templates):
    """Extract root/derivation/compound templates from etymology_templates list."""
    if not etymology_templates:
        return []

    root_keywords = {'root', 'inh', 'der', 'bor', 'compound', 'prefix', 'suffix', 'affix', 'com', 'suf', 'af'}
    result = []
    for t in etymology_templates:
        name = t.get('name', '')
        if name.lower() in root_keywords or 'root' in name.lower():
            result.append({
                'name': name,
                'args': t.get('args', {}),
                'expansion': t.get('expansion', '')
            })
    return result


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


def build_etymology_lookup_for_language(lang_file, words_to_find):
    """
    Stream a language file and build etymology lookup only for words we need.
    Returns dict: word -> {etymology_text, etymology_templates, pos, forms_count}
    """
    lookup = {}
    words_set = set(words_to_find)

    if not os.path.exists(lang_file):
        print(f"  WARNING: File not found: {lang_file}", file=sys.stderr)
        return lookup

    with open(lang_file, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line)
            word = entry.get('word', '')

            if word not in words_set:
                continue

            # If we already have this word, only replace if this entry has better etymology
            if word in lookup:
                existing = lookup[word]
                new_templates = entry.get('etymology_templates', [])
                if not new_templates or (existing['etymology_templates'] and len(existing['etymology_templates']) >= len(new_templates)):
                    continue

            etymology_text = entry.get('etymology_text', '')
            etymology_templates = entry.get('etymology_templates', [])
            forms = entry.get('forms', [])

            lookup[word] = {
                'etymology_text': etymology_text,
                'etymology_templates': etymology_templates,
                'pos': entry.get('pos', ''),
                'forms_count': len(forms) if forms else 0,
            }

    return lookup


def main():
    start_time = datetime.now()
    print(f"Start: {start_time.isoformat()}", file=sys.stderr)

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

    # Step 2: Process each language file one at a time, build CSV rows
    rows = []
    hits_by_lang = {}

    # First, handle English (source words)
    print(f"\nProcessing English...", file=sys.stderr)
    eng_lookup = build_etymology_lookup_for_language(
        os.path.join(DATA_DIR, LANG_FILE_MAP['English']),
        words_by_lang.get('English', set())
    )

    eng_hits = 0
    for eng_word, data in concepts.items():
        etym_data = eng_lookup.get(eng_word, {})
        root_templates = extract_root_templates(etym_data.get('etymology_templates', []))

        if etym_data.get('etymology_templates'):
            eng_hits += 1

        rows.append({
            'english_word': eng_word,
            'sense': data['sense'][:100] if data['sense'] else '',
            'lang': 'en',
            'translated_word': eng_word,
            'pos': etym_data.get('pos', data.get('pos', '')),
            'etymology_text': etym_data.get('etymology_text', '')[:500] if etym_data.get('etymology_text') else '',
            'root_templates': json.dumps(root_templates) if root_templates else '',
            'forms_count': etym_data.get('forms_count', 0),
        })

    hits_by_lang['en'] = eng_hits
    del eng_lookup  # Free memory

    # Now process target languages
    for lang_name in TARGET_LANGS:
        lang_code = LANG_CODES[lang_name]
        lang_file = os.path.join(DATA_DIR, LANG_FILE_MAP[lang_name])

        print(f"Processing {lang_name} ({lang_code})...", file=sys.stderr)

        words_needed = words_by_lang.get(lang_name, set())
        if not words_needed:
            print(f"  No words to look up", file=sys.stderr)
            hits_by_lang[lang_code] = 0
            continue

        # Build lookup for this language
        lookup = build_etymology_lookup_for_language(lang_file, words_needed)

        # Process each concept
        lang_hits = 0
        for eng_word, data in concepts.items():
            trans_words = data['translations'].get(lang_name, [])

            if not trans_words:
                # No translation for this language
                rows.append({
                    'english_word': eng_word,
                    'sense': data['sense'][:100] if data['sense'] else '',
                    'lang': lang_code,
                    'translated_word': '',
                    'pos': '',
                    'etymology_text': '',
                    'root_templates': '',
                    'forms_count': 0,
                })
                continue

            # Use first translation that has etymology data, otherwise just first
            best_word = trans_words[0]
            best_etym = lookup.get(best_word, {})

            for tw in trans_words:
                etym_data = lookup.get(tw, {})
                if etym_data.get('etymology_templates'):
                    best_word = tw
                    best_etym = etym_data
                    break

            if best_etym.get('etymology_templates'):
                lang_hits += 1

            root_templates = extract_root_templates(best_etym.get('etymology_templates', []))

            rows.append({
                'english_word': eng_word,
                'sense': data['sense'][:100] if data['sense'] else '',
                'lang': lang_code,
                'translated_word': best_word,
                'pos': best_etym.get('pos', ''),
                'etymology_text': best_etym.get('etymology_text', '')[:500] if best_etym.get('etymology_text') else '',
                'root_templates': json.dumps(root_templates) if root_templates else '',
                'forms_count': best_etym.get('forms_count', 0),
            })

        hits_by_lang[lang_code] = lang_hits
        del lookup  # Free memory

    # Step 3: Write CSV
    print(f"\nWriting CSV to {OUTPUT_FILE}...", file=sys.stderr)

    fieldnames = ['english_word', 'sense', 'lang', 'translated_word', 'pos', 'etymology_text', 'root_templates', 'forms_count']

    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    # Step 4: Print summary stats to stdout
    print(f"Total concepts: {len(concepts)}")
    print(f"Per-language etymology hits (of {len(concepts)}):")
    for lang_code in ['en', 'ar', 'de', 'he', 'tr', 'sa', 'la', 'grc', 'zh', 'ja']:
        hits = hits_by_lang.get(lang_code, 0)
        print(f"  {lang_code}: {hits}/{len(concepts)}")
    print(f"Total time: {elapsed:.1f}s")

    # Estimate for 9000 concepts
    if len(concepts) > 0:
        time_per_concept = elapsed / len(concepts)
        estimated_9000 = time_per_concept * 9000
        print(f"Estimated time for 9000 concepts: {estimated_9000/60:.1f} minutes")

    print(f"Output saved to: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
