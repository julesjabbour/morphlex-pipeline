#!/bin/bash
# BUILD CONCEPT MAP: Run build_concept_map.py with fixed language property bug
# Timestamp: 2026-04-09-fix-language-property
# Data already downloaded. Bug fix: lex.language() -> lex.language (property not method)

cd /mnt/pgdata/morphlex && source venv/bin/activate

echo "=== BUILD CONCEPT WORDNET MAP ==="
echo "Git HEAD: $(git rev-parse HEAD)"
echo "Start: $(date -Iseconds)"
echo ""

# Run the builder - all wn/nltk output suppressed in Python code
python3 pipeline/build_concept_map.py

RESULT=$?

echo ""
echo "End: $(date -Iseconds)"
exit $RESULT
