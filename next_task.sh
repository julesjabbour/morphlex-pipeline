#!/bin/bash
cd /mnt/pgdata/morphlex
source venv/bin/activate

python3 -c "
import json, re, unicodedata

# Strip all diacritics/combining marks
def strip_all(text):
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))

target_langs = {
    'ar': 'kaikki-arabic.jsonl',
    'he': 'kaikki-hebrew.jsonl',
    'sa': 'kaikki-sanskrit.jsonl',
    'grc': 'kaikki-ancient-greek.jsonl',
    'zh': 'kaikki-chinese.jsonl',
    'de': 'kaikki-german.jsonl',
    'tr': 'kaikki-turkish.jsonl',
    'la': 'kaikki-latin.jsonl',
    'ja': 'kaikki-japanese.jsonl'
}

# Step 1: Get 20 concepts with translations
print('=== STEP 1: LOADING 20 CONCEPTS FROM ENGLISH FILE ===')
concepts = {}
with open('data/open_wordnets/kaikki-english.jsonl') as f:
    for line in f:
        entry = json.loads(line)
        if entry.get('lang','') != 'English' or not entry.get('translations'):
            continue
        lang_words = {}
        for t in entry['translations']:
            lc = t.get('lang_code','')
            w = t.get('word','')
            if lc in target_langs and w:
                if lc not in lang_words:
                    lang_words[lc] = []
                lang_words[lc].append(w)
        if len(lang_words) >= 3:
            concepts[entry['word']] = lang_words
        if len(concepts) >= 20:
            break

print(f'Loaded {len(concepts)} concepts')
print()

# Step 2: For each language, check exact vs stripped match
for lang_code, filename in sorted(target_langs.items()):
    words_needed = set()
    for eng, lw in concepts.items():
        for w in lw.get(lang_code, []):
            words_needed.add(w)

    if not words_needed:
        print(f'===== {lang_code} — 0 words needed from translations =====')
        print()
        continue

    file_words = set()
    file_words_stripped = {}
    exact_hits = set()

    fpath = f'data/open_wordnets/{filename}'
    try:
        with open(fpath) as f:
            for line in f:
                entry = json.loads(line)
                w = entry.get('word','')
                file_words.add(w)
                sw = strip_all(w)
                file_words_stripped[sw] = w
    except FileNotFoundError:
        print(f'===== {lang_code} — FILE NOT FOUND: {fpath} =====')
        print()
        continue

    stripped_hits = set()
    for w in words_needed:
        if w in file_words:
            exact_hits.add(w)
        sw = strip_all(w)
        if sw in file_words_stripped:
            stripped_hits.add(w)

    print(f'===== {lang_code} =====')
    print(f'  Words needed: {len(words_needed)}')
    print(f'  Exact matches: {len(exact_hits)} ({100*len(exact_hits)/max(len(words_needed),1):.0f}%)')
    print(f'  After strip diacritics: {len(stripped_hits)} ({100*len(stripped_hits)/max(len(words_needed),1):.0f}%)')
    print(f'  File vocabulary size: {len(file_words):,}')

    misses = words_needed - stripped_hits
    if misses:
        print(f'  Sample misses ({len(misses)} total):')
        for w in list(misses)[:5]:
            print(f'    [{w}] stripped=[{strip_all(w)}]')
    print()
"
