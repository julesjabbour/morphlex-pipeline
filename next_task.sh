#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "======================================================================"
echo "FIXED PARSERS - LATIN, SANSKRIT, GREEK"
echo "======================================================================"
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

echo "======================================================================"
echo "RUNNING 3 FIXED PARSER SCRIPTS"
echo "======================================================================"
echo ""

# Run only the 3 fixed parsers - use ; so all run even if one fails
echo ">>> Running parse_latin_wordnet.py (Latin - SQL INSERT parsing)..."
python3 scripts/parse_latin_wordnet.py ; echo "parse_latin_wordnet.py exit code: $?"

echo ""
echo ">>> Running parse_iwn_sanskrit.py (Sanskrit - zero-padded PWN IDs)..."
python3 scripts/parse_iwn_sanskrit.py ; echo "parse_iwn_sanskrit.py exit code: $?"

echo ""
echo ">>> Running parse_agwn_jcuenod.py (Greek - SQL INSERT parsing)..."
python3 scripts/parse_agwn_jcuenod.py ; echo "parse_agwn_jcuenod.py exit code: $?"

echo ""
echo "======================================================================"
echo "ALL SCRIPTS COMPLETE"
echo "======================================================================"
echo "End: $(date -Iseconds)"

# List output files
echo ""
echo "Output files:"
ls -la /mnt/pgdata/morphlex/data/open_wordnets/*.pkl 2>/dev/null || echo "No pkl files found"

# Show sizes
echo ""
echo "Summary:"
for f in latin_synset_map.pkl sanskrit_synset_map.pkl agwn_synset_map.pkl; do
    path="/mnt/pgdata/morphlex/data/open_wordnets/$f"
    if [ -f "$path" ]; then
        size=$(stat -c%s "$path" 2>/dev/null || echo 0)
        if [ "$size" -gt 100 ]; then
            echo "  $f: $size bytes [OK - non-empty]"
        else
            echo "  $f: $size bytes [FAIL - too small]"
        fi
    else
        echo "  $f: NOT FOUND"
    fi
done
