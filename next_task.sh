#!/bin/bash
# ENG-019: Greek Morpheus Diagnostic

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== GREEK MORPHEUS DIAGNOSTIC ==="
echo "--- Test 1: romanized 'logos' ---"
curl -s http://localhost:1315/greek/logos
echo ""
echo "--- Test 2: Greek Unicode λόγος ---"
curl -s http://localhost:1315/greek/λόγος
echo ""
echo "--- Test 3: no accents λογος ---"
curl -s http://localhost:1315/greek/λογος
echo ""
echo "--- Test 4: Beta code logos ---"
curl -s http://localhost:1315/greek/lo/gos
echo ""
echo "=== DIAGNOSTIC COMPLETE ==="
