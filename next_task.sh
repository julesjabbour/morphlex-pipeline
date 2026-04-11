#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== STEP 1: DOWNLOAD ARABIC WIKTEXTRACT ==="
wget -q https://kaikki.org/dictionary/Arabic/kaikki.org-dictionary-Arabic.jsonl.gz -O /mnt/pgdata/morphlex/data/open_wordnets/kaikki-arabic.jsonl.gz && gunzip -f /mnt/pgdata/morphlex/data/open_wordnets/kaikki-arabic.jsonl.gz && ls -lh /mnt/pgdata/morphlex/data/open_wordnets/kaikki-arabic.jsonl

echo ""
echo "=== STEP 2: PROBE ETYMOLOGY DATA ==="
python3 -c "
import json

words = ['بيت', 'كتاب', 'علم', 'مدرسة', 'حرية', 'مستشفى', 'طائرة', 'جامعة', 'مفتاح', 'ميلاد', 'فراشة', 'جسر', 'ملعقة', 'دراجة', 'تلفاز', 'فاكهة', 'مخبز', 'عمل', 'فهم', 'طاولة']
found = {}
with open('/mnt/pgdata/morphlex/data/open_wordnets/kaikki-arabic.jsonl') as f:
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
