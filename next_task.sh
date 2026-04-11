#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== DIAGNOSE AND FIX UNKNOWN ROWS ==="
echo "Git: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# PART 1: DIAGNOSTIC - Check why rows are UNKNOWN
echo "=== PART 1: DIAGNOSTIC ==="
python3 << 'DIAGNOSTIC_SCRIPT'
import csv
import json
import os
import unicodedata

DATA_DIR = '/mnt/pgdata/morphlex/data/open_wordnets'

LANG_FILE_MAP = {
    'ar': 'kaikki-arabic.jsonl',
    'de': 'kaikki-german.jsonl',
    'he': 'kaikki-hebrew.jsonl',
    'tr': 'kaikki-turkish.jsonl',
    'sa': 'kaikki-sanskrit.jsonl',
    'la': 'kaikki-latin.jsonl',
    'grc': 'kaikki-ancient-greek.jsonl',
    'zh': 'kaikki-chinese.jsonl',
    'ja': 'kaikki-japanese.jsonl',
    'en': 'kaikki-english.jsonl',
}

def strip_diacritics(text):
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))

# Step 1: Load UNKNOWN rows from CSV
unknowns = []
with open('data/morphlex_test_20.csv', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('morph_type', '') == 'UNKNOWN':
            unknowns.append({
                'english': row.get('english_word', ''),
                'lang': row.get('lang', ''),
                'word': row.get('translated_word', ''),
                'etym_text': row.get('etymology_text', '')[:100],
                'templates_json': row.get('root_templates', ''),
            })

print(f"Total UNKNOWN rows: {len(unknowns)}")
print()

# Step 2: For each UNKNOWN, look up word in source file
diagnosed = {'no_translation': 0, 'not_in_file': 0, 'in_file_no_templates': 0,
             'in_file_has_templates': 0, 'in_file_has_etym_text': 0}

print("=== DIAGNOSIS BY ROW ===")
for u in unknowns[:20]:  # First 20 for brevity
    lang = u['lang']
    word = u['word']

    if not word:
        diagnosed['no_translation'] += 1
        continue

    # Look up in source file
    filename = LANG_FILE_MAP.get(lang, '')
    if not filename:
        print(f"  {u['english']} | {lang} | {word}: UNKNOWN LANG CODE")
        continue

    fpath = os.path.join(DATA_DIR, filename)
    found_entry = None
    found_stripped = None
    stripped_word = strip_diacritics(word)

    with open(fpath, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line)
            ew = entry.get('word', '')
            if ew == word:
                found_entry = entry
                break
            if strip_diacritics(ew) == stripped_word and not found_stripped:
                found_stripped = entry

    final_entry = found_entry or found_stripped

    if not final_entry:
        diagnosed['not_in_file'] += 1
        print(f"  {u['english']} | {lang} | {word}")
        print(f"    -> NOT IN SOURCE FILE")
        print()
        continue

    file_templates = final_entry.get('etymology_templates', [])
    file_etym_text = final_entry.get('etymology_text', '')

    if file_templates:
        diagnosed['in_file_has_templates'] += 1
        tnames = [t.get('name', '') for t in file_templates]
        print(f"  {u['english']} | {lang} | {word}")
        print(f"    -> IN FILE, HAS TEMPLATES: {tnames}")
        print(f"    -> CSV etymology_text: {u['etym_text'][:80]}")
        print(f"    -> CSV templates_json: {u['templates_json'][:100]}")
        print()
    elif file_etym_text:
        diagnosed['in_file_has_etym_text'] += 1
        print(f"  {u['english']} | {lang} | {word}")
        print(f"    -> IN FILE, HAS etymology_text only: {file_etym_text[:100]}")
        print()
    else:
        diagnosed['in_file_no_templates'] += 1
        print(f"  {u['english']} | {lang} | {word}")
        print(f"    -> IN FILE, NO TEMPLATES, NO etymology_text")
        print()

print("=== DIAGNOSIS SUMMARY ===")
print(f"  No translation: {diagnosed['no_translation']}")
print(f"  Not in source file: {diagnosed['not_in_file']}")
print(f"  In file, no templates/text: {diagnosed['in_file_no_templates']}")
print(f"  In file, has etymology_text: {diagnosed['in_file_has_etym_text']}")
print(f"  In file, HAS TEMPLATES (BUG!): {diagnosed['in_file_has_templates']}")
print()
DIAGNOSTIC_SCRIPT

echo ""
echo "=== PART 2: RUN FIXED build_morphlex_table.py ==="
python3 scripts/build_morphlex_table.py

echo ""
echo "=== CSV PREVIEW (first 5 data rows) ==="
python3 -c "
import csv
with open('data/morphlex_test_20.csv', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        if i >= 5:
            break
        ew = row.get('english_word','')[:15]
        lang = row.get('lang','')
        mt = row.get('morph_type','')[:20]
        root = row.get('root','')[:15]
        rt = row.get('root_templates','')
        has_rt = 'YES' if rt else 'NO'
        print(f'  {ew:<15} | {lang} | {mt:<20} | root={root:<15} | has_templates={has_rt}')
"

echo ""
echo "=== DONE ==="
