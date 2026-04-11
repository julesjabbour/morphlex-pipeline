#!/bin/bash
cd /mnt/pgdata/morphlex/data/open_wordnets

echo "=== DOWNLOADING ANCIENT GREEK ==="
rm -f kaikki-ancient-greek.jsonl kaikki-ancient-greek.jsonl.gz
wget -q "https://kaikki.org/dictionary/Ancient%20Greek/kaikki.org-dictionary-AncientGreek.jsonl" -O kaikki-ancient-greek.jsonl
if [ -s kaikki-ancient-greek.jsonl ]; then
  echo "SUCCESS: $(ls -lh kaikki-ancient-greek.jsonl | awk '{print $5}')"
  echo ""
  echo "=== QUICK STATS ==="
  wc -l kaikki-ancient-greek.jsonl
  python3 -c "
import json
total = 0
with_etym = 0
with open('kaikki-ancient-greek.jsonl') as f:
    for line in f:
        total += 1
        entry = json.loads(line)
        if entry.get('etymology_templates'):
            with_etym += 1
print(f'Total entries: {total:,}')
print(f'With etymology templates: {with_etym:,} ({100*with_etym/max(total,1):.1f}%)')
"
else
  echo "FAILED"
  # Try without gz
  wget -q "https://kaikki.org/dictionary/Ancient%20Greek/kaikki.org-dictionary-AncientGreek.jsonl.gz" -O kaikki-ancient-greek.jsonl.gz
  if [ -s kaikki-ancient-greek.jsonl.gz ]; then
    gunzip -f kaikki-ancient-greek.jsonl.gz && echo "SUCCESS (gz): $(ls -lh kaikki-ancient-greek.jsonl | awk '{print $5}')"
  else
    echo "BOTH FAILED"
  fi
fi
