#!/bin/bash
cd /mnt/pgdata/morphlex/data/open_wordnets

for lang_url in \
  "English/kaikki.org-dictionary-English.jsonl.gz kaikki-english.jsonl" \
  "Hebrew/kaikki.org-dictionary-Hebrew.jsonl.gz kaikki-hebrew.jsonl" \
  "Sanskrit/kaikki.org-dictionary-Sanskrit.jsonl.gz kaikki-sanskrit.jsonl" \
  "Turkish/kaikki.org-dictionary-Turkish.jsonl.gz kaikki-turkish.jsonl" \
  "Latin/kaikki.org-dictionary-Latin.jsonl.gz kaikki-latin.jsonl" \
  "Ancient%20Greek/kaikki.org-dictionary-Ancient%20Greek.jsonl.gz kaikki-ancient-greek.jsonl" \
  "Chinese/kaikki.org-dictionary-Chinese.jsonl.gz kaikki-chinese.jsonl" \
  "Japanese/kaikki.org-dictionary-Japanese.jsonl.gz kaikki-japanese.jsonl"
do
  url_part=$(echo "$lang_url" | cut -d' ' -f1)
  outfile=$(echo "$lang_url" | cut -d' ' -f2)
  if [ -f "$outfile" ]; then
    echo "SKIP: $outfile already exists ($(ls -lh $outfile | awk '{print $5}'))"
  else
    echo "DOWNLOADING: $outfile..."
    wget -q "https://kaikki.org/dictionary/$url_part" -O "${outfile}.gz" && gunzip -f "${outfile}.gz" && echo "DONE: $(ls -lh $outfile | awk '{print $5}')" || echo "FAILED: $outfile"
  fi
done

echo ""
echo "=== ALL FILES ==="
ls -lhS /mnt/pgdata/morphlex/data/open_wordnets/kaikki-*.jsonl
echo ""
df -h /mnt/pgdata
