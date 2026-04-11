#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate && python3 -c "
import json

words = ['Haus', 'Krankenhaus', 'Freiheit', 'verstehen', 'Handschuh', 'Kindergarten', 'Wissenschaft', 'arbeiten', 'Löffel', 'Fahrrad', 'Schlüssel', 'Erdbeere', 'Fernseher', 'Flugzeug', 'Brücke', 'Schmetterling', 'Tisch', 'Wasserhahn', 'Geburtstag', 'Bäckerei']
found = {}
with open('/mnt/pgdata/morphlex/data/open_wordnets/kaikki-german.jsonl') as f:
    for line in f:
        entry = json.loads(line)
        w = entry.get('word','')
        if w in words and w not in found:
            found[w] = {
                'word': w,
                'pos': entry.get('pos',''),
                'etymology_text': entry.get('etymology_text',''),
                'etymology_templates': entry.get('etymology_templates', []),
                'senses_count': len(entry.get('senses', [])),
                'forms_count': len(entry.get('forms', []))
            }
            if len(found) == 20:
                break

for w in words:
    if w in found:
        e = found[w]
        print(f'===== {e[\"word\"]} ({e[\"pos\"]}) =====')
        print(f'Etymology: {e[\"etymology_text\"]}')
        print(f'Templates: {json.dumps(e[\"etymology_templates\"], ensure_ascii=False, indent=2)}')
        print(f'Senses: {e[\"senses_count\"]}, Forms: {e[\"forms_count\"]}')
        print()
    else:
        print(f'===== {w}: NOT FOUND =====')
        print()
"
