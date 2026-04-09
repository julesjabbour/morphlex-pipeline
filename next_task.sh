#!/bin/bash
# DEEP ANALYSIS OF DIFFERENT ROWS IN ENGLISH COMPARISON
# Timestamp: 2026-04-09-analyze-english-differences-v1
# - Load english_comparison.csv, filter to DIFFERENT rows
# - Analysis 1: Count disagreement patterns
# - Analysis 2: 10 random samples per pattern (100+ rows)
# - Analysis 3: Root agreement when type differs

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== DEEP ANALYSIS OF ENGLISH COMPARISON DIFFERENCES ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Sync code from git
git fetch origin > /dev/null 2>&1
git reset --hard origin/main > /dev/null 2>&1

# Run the analysis script
python3 scripts/analyze_english_differences.py

RESULT=$?

echo ""
echo "End: $(date -Iseconds)"
exit $RESULT
