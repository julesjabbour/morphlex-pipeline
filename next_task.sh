#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== DISK USAGE ==="
df -h /mnt/pgdata
echo ""

echo "=== /mnt/pgdata/morphlex/ TOP LEVEL ==="
ls -la /mnt/pgdata/morphlex/ 2>&1
echo ""

echo "=== /mnt/pgdata/morphlex/data/ ==="
ls -lhS /mnt/pgdata/morphlex/data/ 2>&1 | head -50
echo ""

echo "=== /mnt/pgdata/morphlex/data/open_wordnets/ ==="
ls -lhS /mnt/pgdata/morphlex/data/open_wordnets/ 2>&1 | head -30
echo ""

echo "=== /mnt/pgdata/morphlex/analyzers/ ==="
ls -la /mnt/pgdata/morphlex/analyzers/ 2>&1
echo ""

echo "=== /mnt/pgdata/morphlex/pipeline/ ==="
ls -la /mnt/pgdata/morphlex/pipeline/ 2>&1
echo ""

echo "=== /mnt/pgdata/morphlex/scripts/ ==="
ls -la /mnt/pgdata/morphlex/scripts/ 2>&1
echo ""

echo "=== /mnt/pgdata/morphlex/reports/ ==="
ls -lhS /mnt/pgdata/morphlex/reports/ 2>&1 | head -20
echo ""

echo "=== KEY FILES — check existence and size ==="
for f in \
  /mnt/pgdata/morphlex/data/master_table.csv \
  /mnt/pgdata/morphlex/data/forward_translations.pkl \
  /mnt/pgdata/morphlex/data/etymology_index.pkl \
  /mnt/pgdata/morphlex/data/wiktextract_morphology.pkl \
  /mnt/pgdata/morphlex/data/wiktextract_index.pkl \
  /mnt/pgdata/morphlex/data/wiktextract_roots.pkl \
  /mnt/pgdata/morphlex/data/morphlex_full.csv \
  /mnt/pgdata/morphlex/data/morphlex_test_20.csv \
  /mnt/pgdata/morphlex/data/open_wordnets/pwn30_to_oewn_map.pkl
do
  if [ -f "$f" ]; then
    echo "EXISTS: $(ls -lh $f | awk '{print $5"\t"$9}')"
  else
    echo "MISSING: $f"
  fi
done
echo ""

echo "=== POSTGRES TABLES ==="
sudo -u postgres psql -d morphlex -c "\dt lexicon.*" 2>&1 | head -20
sudo -u postgres psql -d morphlex -c "SELECT COUNT(*) FROM lexicon.entries;" 2>&1
echo ""

echo "=== GIT STATUS ==="
cd /mnt/pgdata/morphlex
git log --oneline -10 2>&1
echo ""
git status 2>&1
