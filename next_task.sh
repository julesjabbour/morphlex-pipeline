#!/bin/bash
# Read diagnostic report and output summary/key findings only

REPORT="/mnt/pgdata/morphlex/diagnostic_report.md"

if [ ! -f "$REPORT" ]; then
    echo "ERROR: Diagnostic report not found at $REPORT"
    exit 1
fi

# Extract key sections using sed
echo "=== DIAGNOSTIC REPORT: KEY FINDINGS ==="
echo ""

# Title and Executive Summary (lines 1-20)
sed -n '1,20p' "$REPORT"

echo ""
echo "---"
echo ""

# Language-by-Language Code Path Trace table (lines 32-47)
echo "### Language-by-Language Code Path Trace"
echo ""
sed -n '34,47p' "$REPORT"

echo ""
echo "---"
echo ""

# Section 5: False Positive Risk Summary (extract risk levels only)
echo "### False Positive Risk by Adapter"
echo ""
grep -E "^####.*RISK" "$REPORT" | sed 's/^#### /- /'

echo ""
echo "---"
echo ""

# Section 8: Summary Results Matrix - Current State table
echo "## Summary Results Matrix"
echo ""
echo "### Current State: Arabic Word Input"
echo ""
sed -n '516,529p' "$REPORT"

echo ""
echo "### After Proposed Changes"
echo ""
sed -n '532,547p' "$REPORT"

echo ""
echo "---"
echo ""

# Section 6: Required Changes summary
echo "## Required Changes for Arabic Anchor (Section Headers)"
echo ""
grep -E "^### [0-9]+\." "$REPORT"

echo ""
echo "=== END KEY FINDINGS ==="
