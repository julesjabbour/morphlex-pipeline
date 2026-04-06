#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== WIKTEXTRACT LOADER TEST (ENG-021) ==="
python3 -c "
import sys
sys.path.insert(0, '/mnt/pgdata/morphlex')
from pipeline.wiktextract_loader import load_wiktextract

filepath = '/mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz'
print('Loading first 1000 English entries...')
data = load_wiktextract(filepath, max_entries=1000)

print(f'Entries loaded: {len(data)}')

# Show languages found in translations
all_langs = set()
for word, info in data.items():
    if 'translations' in info:
        all_langs.update(info['translations'].keys())
print(f'Languages in translations: {sorted(all_langs)}')

# Show a sample entry
for word, info in list(data.items())[:1]:
    print(f'\nSample entry: {word}')
    print(f'  POS: {info.get(\"pos\")}')
    print(f'  Definitions: {info.get(\"definitions\", [])[:2]}')
    print(f'  Translations: {dict(list(info.get(\"translations\", {}).items())[:3])}')
    print(f'  Etymology: {info.get(\"etymology\", {})[:2] if info.get(\"etymology\") else \"none\"}')
" 2>&1

echo "=== TEST COMPLETE ==="
