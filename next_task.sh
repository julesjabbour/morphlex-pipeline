#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "======================================================================"
echo "LIST WORDNET SUBDIRECTORY CONTENTS"
echo "======================================================================"
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

echo "=== latin-wordnet/latinwordnet subdirectory ==="
ls -lahR /mnt/pgdata/morphlex/data/open_wordnets/latin-wordnet/latinwordnet/ 2>&1 | head -100

echo ""
echo "=== agwn-jcuenod/greekwordnet subdirectory ==="
ls -lahR /mnt/pgdata/morphlex/data/open_wordnets/agwn-jcuenod/greekwordnet/ 2>&1 | head -100

echo ""
echo "=== find all .sql files anywhere on VM ==="
find /mnt/pgdata/morphlex -name '*.sql' -type f 2>/dev/null | head -30

echo ""
echo "=== find all files mentioning latin_synonyms ==="
find /mnt/pgdata/morphlex -name '*latin_synonyms*' 2>/dev/null

echo ""
echo "=== find all files mentioning greek_synonyms ==="
find /mnt/pgdata/morphlex -name '*greek_synonyms*' 2>/dev/null

echo ""
echo "======================================================================"
echo "END OF LISTING"
echo "======================================================================"
echo "End: $(date -Iseconds)"
