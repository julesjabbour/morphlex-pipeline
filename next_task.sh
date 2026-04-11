#!/bin/bash
cd /mnt/pgdata/morphlex/data/open_wordnets

echo "=== PART 1: FIX ANCIENT GREEK DOWNLOAD ==="
rm -f kaikki-ancient-greek.jsonl.gz
wget -q "https://kaikki.org/dictionary/Ancient%20Greek/kaikki.org-dictionary-Ancient%20Greek.jsonl.gz" -O kaikki-ancient-greek.jsonl.gz && gunzip -f kaikki-ancient-greek.jsonl.gz && echo "DONE: $(ls -lh kaikki-ancient-greek.jsonl | awk '{print $5}')" || echo "FAILED - trying alternate URL..." && wget -q "https://kaikki.org/dictionary/Ancient Greek/kaikki.org-dictionary-Ancient Greek.jsonl.gz" -O kaikki-ancient-greek.jsonl.gz 2>/dev/null && gunzip -f kaikki-ancient-greek.jsonl.gz && echo "DONE ALT: $(ls -lh kaikki-ancient-greek.jsonl | awk '{print $5}')" || echo "BOTH FAILED"

echo ""
echo "=== PART 2: PROBE ENGLISH TRANSLATIONS FIELD ==="
cd /mnt/pgdata/morphlex
source venv/bin/activate
python3 -c "
import json

words = ['house', 'book', 'water', 'bridge', 'key', 'school', 'freedom', 'work', 'bicycle', 'airplane']
found = {}
with open('data/open_wordnets/kaikki-english.jsonl') as f:
    for line in f:
        entry = json.loads(line)
        w = entry.get('word','')
        if w in words and w not in found and entry.get('lang','') == 'English':
            trans = entry.get('translations', [])
            if trans:
                found[w] = {
                    'word': w,
                    'pos': entry.get('pos',''),
                    'translations_count': len(trans),
                    'sample_translations': trans[:15]
                }
                if len(found) == 10:
                    break

for w in words:
    if w in found:
        e = found[w]
        print(f'===== {e[\"word\"]} ({e[\"pos\"]}) — {e[\"translations_count\"]} translations =====')
        for t in e['sample_translations']:
            lang = t.get('lang','?')
            tw = t.get('word', t.get('note','?'))
            sense = t.get('sense','')
            print(f'  {lang}: {tw}  [{sense[:50]}]')
        print()
    else:
        print(f'===== {w}: NOT FOUND =====')
        print()
"
