#!/bin/bash
cd /mnt/pgdata/morphlex
source venv/bin/activate

echo "=== PART 1: FIX ANCIENT GREEK DOWNLOAD ==="
cd data/open_wordnets
# Find correct URL
for url in \
  "https://kaikki.org/dictionary/Ancient%20Greek/kaikki.org-dictionary-Ancient%20Greek.jsonl.gz" \
  "https://kaikki.org/dictionary/Ancient_Greek/kaikki.org-dictionary-Ancient_Greek.jsonl.gz" \
  "https://kaikki.org/dictionary/Ancient%20Greek/kaikki.org-dictionary-Ancient+Greek.jsonl.gz"
do
  echo "Trying: $url"
  wget -q "$url" -O kaikki-ancient-greek.jsonl.gz 2>&1
  if [ -s kaikki-ancient-greek.jsonl.gz ]; then
    gunzip -f kaikki-ancient-greek.jsonl.gz && echo "SUCCESS: $(ls -lh kaikki-ancient-greek.jsonl | awk '{print $5}')" && break
  else
    rm -f kaikki-ancient-greek.jsonl.gz
    echo "FAILED"
  fi
done

echo ""
echo "=== PART 2: FULL STATS FOR ALL WIKTEXTRACT FILES ==="
cd /mnt/pgdata/morphlex
python3 -c "
import json, os, glob

files = sorted(glob.glob('data/open_wordnets/kaikki-*.jsonl'))
for fpath in files:
    lang = os.path.basename(fpath).replace('kaikki-','').replace('.jsonl','')
    total = 0
    with_etym_text = 0
    with_etym_templates = 0
    with_translations = 0
    with_root = 0
    with_forms = 0
    root_template_names = set()

    with open(fpath) as f:
        for line in f:
            total += 1
            entry = json.loads(line)
            if entry.get('etymology_text','').strip():
                with_etym_text += 1
            templates = entry.get('etymology_templates', [])
            if templates:
                with_etym_templates += 1
            for t in templates:
                name = t.get('name','')
                if 'root' in name.lower() or name in ('inh', 'der', 'bor', 'compound', 'prefix', 'suffix', 'affix', 'com', 'suf', 'af', 'surf'):
                    with_root += 1
                    break
            if 'root' in str(templates).lower():
                for t in templates:
                    if 'root' in t.get('name','').lower():
                        root_template_names.add(t.get('name',''))
            if entry.get('translations'):
                with_translations += 1
            if entry.get('forms'):
                with_forms += 1

    print(f'===== {lang} =====')
    print(f'  Total entries: {total:,}')
    print(f'  With etymology text: {with_etym_text:,} ({100*with_etym_text/max(total,1):.1f}%)')
    print(f'  With etymology templates: {with_etym_templates:,} ({100*with_etym_templates/max(total,1):.1f}%)')
    print(f'  With root/derivation/compound template: {with_root:,} ({100*with_root/max(total,1):.1f}%)')
    print(f'  With translations: {with_translations:,} ({100*with_translations/max(total,1):.1f}%)')
    print(f'  With forms: {with_forms:,} ({100*with_forms/max(total,1):.1f}%)')
    if root_template_names:
        print(f'  Root template types found: {sorted(root_template_names)}')
    print()
"
