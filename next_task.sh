#!/bin/bash
# Arabic Anchor Pipeline Test - Full Output to File
# Tests the pipeline with 10 Arabic words across all 11 languages
#
# Writes FULL untruncated output (including all library warnings) to:
#   /mnt/pgdata/morphlex/arabic_anchor_test_full.md
# Outputs only a short summary to stdout (for Slack)
#
# Usage: bash next_task.sh
# Working directory: /mnt/pgdata/morphlex

set -e

cd /mnt/pgdata/morphlex && source venv/bin/activate

OUTPUT_FILE="/mnt/pgdata/morphlex/arabic_anchor_test_full.md"
WARNINGS_FILE="/mnt/pgdata/morphlex/arabic_anchor_warnings.tmp"

echo "=== ARABIC ANCHOR PIPELINE TEST ==="
echo "Start: $(date -Iseconds)"
echo ""

# Run the test, capturing stderr (warnings) separately
# The Python script writes its analysis to OUTPUT_FILE and summary to stdout
python3 test_arabic_anchor.py 2>"$WARNINGS_FILE"

# If warnings were captured, prepend them to the output file
if [ -s "$WARNINGS_FILE" ]; then
    # Create a temp file with warnings header + warnings + original output
    TEMP_OUTPUT="${OUTPUT_FILE}.tmp"
    {
        echo "## Library Warnings (Raw Output)"
        echo ""
        echo "All warnings from Zeyrek, CAMeL, spaCy, and other libraries:"
        echo ""
        echo '```'
        cat "$WARNINGS_FILE"
        echo '```'
        echo ""
        echo "---"
        echo ""
        cat "$OUTPUT_FILE"
    } > "$TEMP_OUTPUT"
    mv "$TEMP_OUTPUT" "$OUTPUT_FILE"
fi

# Clean up temp warnings file
rm -f "$WARNINGS_FILE"

echo ""
echo "End: $(date -Iseconds)"
echo "=== Test complete ==="
