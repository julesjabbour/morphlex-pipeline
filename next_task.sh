#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "======================================================================"
echo "EXPLORATION AND PARSER SCRIPTS - FULL RUN"
echo "======================================================================"
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Run exploration first
echo "======================================================================"
echo "RUNNING EXPLORATION SCRIPT"
echo "======================================================================"
python3 scripts/explore_datasets.py

echo ""
echo "======================================================================"
echo "RUNNING PARSER SCRIPTS (using ; so all run even if one fails)"
echo "======================================================================"
echo ""

# Run each parser - use ; so all run even if one fails
echo ">>> Running parse_odenet.py (German)..."
python3 scripts/parse_odenet.py ; echo "parse_odenet.py exit code: $?"

echo ""
echo ">>> Running parse_kenet.py (Turkish)..."
python3 scripts/parse_kenet.py ; echo "parse_kenet.py exit code: $?"

echo ""
echo ">>> Running parse_latin_wordnet.py (Latin)..."
python3 scripts/parse_latin_wordnet.py ; echo "parse_latin_wordnet.py exit code: $?"

echo ""
echo ">>> Running parse_iwn_sanskrit.py (Sanskrit)..."
python3 scripts/parse_iwn_sanskrit.py ; echo "parse_iwn_sanskrit.py exit code: $?"

echo ""
echo ">>> Running parse_agwn_jcuenod.py (Greek)..."
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
