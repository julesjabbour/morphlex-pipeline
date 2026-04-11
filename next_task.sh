#!/bin/bash
cd /mnt/pgdata/morphlex
source venv/bin/activate

python3 -c "
import csv, json

unknowns = []
all_templates = {}
with open('data/morphlex_test_20.csv', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        mt = row.get('morph_type','')
        if mt == 'UNKNOWN':
            etym = row.get('etymology_text','')
            root_t = row.get('root_templates','')
            unknowns.append({
                'english': row.get('english_word',''),
                'lang': row.get('lang',''),
                'word': row.get('translated_word',''),
                'etymology': etym[:200],
                'root_templates': root_t[:500]
            })
        # Also collect all template names across ALL rows
        rt = row.get('root_templates','')
        if rt:
            try:
                templates = json.loads(rt)
                for t in templates:
                    name = t.get('name','')
                    if name:
                        if name not in all_templates:
                            all_templates[name] = 0
                        all_templates[name] += 1
            except:
                pass

print(f'=== UNKNOWN ROWS: {len(unknowns)} ===')
print()
for u in unknowns[:15]:
    print(f'{u[\"english\"]} | {u[\"lang\"]} | {u[\"word\"]}')
    print(f'  Etymology: {u[\"etymology\"]}')
    try:
        templates = json.loads(u['root_templates'])
        names = [t.get('name','') for t in templates]
        print(f'  Template names: {names}')
    except:
        print(f'  Raw templates: {u[\"root_templates\"][:200]}')
    print()

print(f'=== ALL TEMPLATE NAMES ACROSS DATASET ({len(all_templates)} unique) ===')
for name, count in sorted(all_templates.items(), key=lambda x: -x[1]):
    print(f'  {name}: {count}')
"
