#!/bin/bash
FLAG="/tmp/.eng015_rawdump"
if [ -f "$FLAG" ]; then
    echo "=== ALREADY COMPLETE ==="
    exit 0
fi
cd /mnt/pgdata/morphlex && source venv/bin/activate

python3 -c "
import gzip, json, sys

# Find the entry for 'house' and dump its top-level keys and translations structure
with gzip.open('data/raw-wiktextract-data.jsonl.gz', 'rt') as f:
    for line in f:
        entry = json.loads(line)
        if entry.get('word') == 'house' and entry.get('lang_code') == 'en':
            print('=== TOP LEVEL KEYS ===')
            print(list(entry.keys()))
            print()

            # Check for translations at top level
            if 'translations' in entry:
                print('=== translations field type:', type(entry['translations']))
                trans = entry['translations']
                if isinstance(trans, list):
                    print(f'translations list length: {len(trans)}')
                    for t in trans[:5]:
                        print(f'  {t}')
                elif isinstance(trans, dict):
                    print(f'translations dict keys: {list(trans.keys())[:10]}')
            else:
                print('NO translations at top level')

            print()
            # Check senses for translations
            if 'senses' in entry:
                print(f'=== senses count: {len(entry[\"senses\"])} ===')
                for i, sense in enumerate(entry['senses'][:3]):
                    print(f'  sense {i} keys: {list(sense.keys())}')
                    if 'translations' in sense:
                        print(f'  sense {i} translations type: {type(sense[\"translations\"])}')
                        strans = sense['translations']
                        if isinstance(strans, list):
                            print(f'  sense {i} translations count: {len(strans)}')
                            for t in strans[:3]:
                                print(f'    {t}')
                    if 'glosses' in sense:
                        print(f'  sense {i} gloss: {sense[\"glosses\"][0][:80]}')

            break
" 2>&1

touch "$FLAG"
echo "=== DONE ==="
