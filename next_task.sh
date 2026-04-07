#!/bin/bash
# Full Pipeline Health Check and Production Readiness Audit
# Session 45 - Comprehensive 3-part report
# Output goes to /mnt/pgdata/morphlex/health_check_report.md

cd /mnt/pgdata/morphlex && source venv/bin/activate

REPORT="/mnt/pgdata/morphlex/health_check_report.md"
GIT_HEAD=$(git rev-parse HEAD)
GIT_SHORT=$(git rev-parse --short HEAD)
START_TIME=$(date -Iseconds)

echo "=== FULL PIPELINE HEALTH CHECK ==="
echo "Start: $START_TIME"
echo "Git HEAD: $GIT_HEAD"
echo ""

# Write report header
cat > "$REPORT" << EOF
# Morphlex Pipeline Health Check Report

**Date:** $(date -u '+%Y-%m-%d %H:%M:%S UTC')
**Git HEAD:** \`$GIT_HEAD\`
**Start:** $START_TIME

---

EOF

echo "=== PART 1: INFRASTRUCTURE VERIFICATION ==="
echo ""

# 1a. Crontab status
echo "--- Crontab Status ---"
CRON_OUTPUT=$(crontab -l 2>&1)
echo "$CRON_OUTPUT"
CRON_ENABLED="NO"
if echo "$CRON_OUTPUT" | grep -q "morphlex"; then
    CRON_ENABLED="YES"
fi
echo ""

# 1b. Flock verification (check if lock file exists)
echo "--- Flock Lock File ---"
if [ -f /tmp/morphlex_run.lock ]; then
    echo "Lock file exists: /tmp/morphlex_run.lock"
    ls -la /tmp/morphlex_run.lock
else
    echo "Lock file does not exist (will be created on next run)"
fi
echo ""

# 1c. Marker file for last task (a6911f5)
echo "--- Marker Files ---"
MARKER_DIR="/tmp/morphlex_markers"
if [ -d "$MARKER_DIR" ]; then
    echo "Marker directory contents:"
    ls -la "$MARKER_DIR"
    # Check specifically for a6911f5 task marker
    TASK_HASH=$(md5sum /mnt/pgdata/morphlex/next_task.sh 2>/dev/null | cut -d' ' -f1)
    echo ""
    echo "Current task hash: $TASK_HASH"
    if [ -f "$MARKER_DIR/done_$TASK_HASH" ]; then
        echo "Marker exists for current task: YES"
    else
        echo "Marker exists for current task: NO"
    fi
else
    echo "No marker directory yet"
fi
echo ""

# 1d. Zombie processes
echo "--- Process Check (zombies) ---"
ZOMBIES=$(ps aux | grep -E "(python.*morphlex|build_forward)" | grep -v grep | wc -l)
echo "Active morphlex/build processes: $ZOMBIES"
ps aux | grep -E "(python.*morphlex|build_forward)" | grep -v grep || echo "(none)"
echo ""

# 1e. Disk space
echo "--- Disk Space (/mnt/pgdata) ---"
df -h /mnt/pgdata
echo ""

# 1f. Memory usage
echo "--- Memory Usage ---"
free -h
echo ""

# Append Part 1 to report
cat >> "$REPORT" << EOF
## Part 1: Infrastructure Verification

### Crontab Status
\`\`\`
$CRON_OUTPUT
\`\`\`
**Cron enabled:** $CRON_ENABLED

### Flock Lock File
$(if [ -f /tmp/morphlex_run.lock ]; then echo "Lock file exists"; else echo "Lock file not present (created on demand)"; fi)

### Marker Files
$(ls -la "$MARKER_DIR" 2>&1 || echo "No marker directory")

### Running Processes
Active morphlex/build processes: $ZOMBIES

### Disk Space
\`\`\`
$(df -h /mnt/pgdata)
\`\`\`

### Memory
\`\`\`
$(free -h)
\`\`\`

---

EOF

echo "=== PART 2: PIPELINE END-TO-END VERIFICATION ==="
echo ""

# Run 10-word Arabic test and sample pkl keys
python3 << 'PYEOF'
import pickle
import os
import re
import random
import sys

PKL_PATH = '/mnt/pgdata/morphlex/data/forward_translations.pkl'
REPORT_PATH = '/mnt/pgdata/morphlex/health_check_report.md'
ARABIC_DIACRITICS = re.compile(r'[\u064B-\u065F\u0670]')

# 10 test words from S44
TEST_WORDS = ['ماء', 'نار', 'يد', 'عين', 'حجر', 'قلب', 'شمس', 'قمر', 'شجرة', 'دم']
LANGUAGES = ['ar', 'en', 'tr', 'de', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro']

if not os.path.exists(PKL_PATH):
    print(f"ERROR: PKL file not found at {PKL_PATH}")
    sys.exit(1)

with open(PKL_PATH, 'rb') as f:
    translations = pickle.load(f)

file_size = os.path.getsize(PKL_PATH)
print(f"PKL file size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
print(f"Total Arabic keys: {len(translations):,}")
print()

# Show 5 sample keys to prove diacritics are stripped
print("5 SAMPLE PKL KEYS (verify zero diacritics):")
random.seed(42)
sample_keys = random.sample(list(translations.keys()), min(5, len(translations)))
sample_lines = []
all_clean = True
for key in sample_keys:
    has_diacritics = bool(ARABIC_DIACRITICS.search(key))
    status = "HAS DIACRITICS!" if has_diacritics else "clean"
    if has_diacritics:
        all_clean = False
    line = f"  '{key}' - {status}"
    print(line)
    sample_lines.append(f"- `{key}` - {status}")
print()

# Count total keys with diacritics
keys_with_diacritics = sum(1 for k in translations.keys() if ARABIC_DIACRITICS.search(k))
print(f"Keys with diacritics: {keys_with_diacritics} / {len(translations)}")
diacritics_status = "PASS (zero diacritics)" if keys_with_diacritics == 0 else f"FAIL ({keys_with_diacritics} keys have diacritics)"
print(f"Diacritics check: {diacritics_status}")
print()

# Test 10 words across 11 languages
print("10-WORD ARABIC TEST:")
lang_results = {lang: 0 for lang in LANGUAGES}
total = 0
words_found = 0

for word in TEST_WORDS:
    trans = translations.get(word, {})
    if trans:
        words_found += 1
        lang_results['ar'] += 1
        total += 1
        for lang in LANGUAGES[1:]:  # skip 'ar'
            if lang in trans:
                lang_results[lang] += 1
                total += 1

print()
test_lines = []
ok_count = 0
for lang in LANGUAGES:
    count = lang_results[lang]
    status = "[OK]" if count > 0 else "[EMPTY]"
    if count > 0:
        ok_count += 1
    line = f"  {lang} : {count} results {status}"
    print(line)
    test_lines.append(f"| {lang} | {count} | {status} |")

print()
print(f"Languages with results: {ok_count}/11")
print(f"TOTAL: {total} results from 10 words x 11 languages")

# Expected: 10/11 OK, ine-pro EMPTY, ~90 results
expected_match = (ok_count >= 10 and lang_results['ine-pro'] == 0 and total >= 80)
match_status = "PASS" if expected_match else "CHECK"
print(f"Expected pattern (10/11 OK, ine-pro EMPTY, ~90): {match_status}")

# Write Part 2 to report
with open(REPORT_PATH, 'a') as f:
    f.write("## Part 2: Pipeline End-to-End Verification\n\n")
    f.write(f"### PKL File Status\n")
    f.write(f"- **File size:** {file_size:,} bytes ({file_size/1024/1024:.2f} MB)\n")
    f.write(f"- **Total Arabic keys:** {len(translations):,}\n")
    f.write(f"- **Keys with diacritics:** {keys_with_diacritics}\n")
    f.write(f"- **Diacritics check:** {diacritics_status}\n\n")
    f.write("### 5 Sample PKL Keys\n")
    for line in sample_lines:
        f.write(f"{line}\n")
    f.write("\n### 10-Word Arabic Test Results\n\n")
    f.write("| Language | Results | Status |\n")
    f.write("|----------|---------|--------|\n")
    for line in test_lines:
        f.write(f"{line}\n")
    f.write(f"\n**Total:** {total} results from 10 words x 11 languages\n")
    f.write(f"**Languages with results:** {ok_count}/11\n")
    f.write(f"**Expected pattern match:** {match_status}\n\n")
    f.write("---\n\n")

PYEOF
echo ""

echo "=== PART 3: PRODUCTION READINESS ANALYSIS ==="
echo ""

python3 << 'PYEOF'
import pickle
import os
import random
import psycopg2

PKL_PATH = '/mnt/pgdata/morphlex/data/forward_translations.pkl'
REPORT_PATH = '/mnt/pgdata/morphlex/health_check_report.md'
LANGUAGES = ['ar', 'en', 'tr', 'de', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro']

with open(PKL_PATH, 'rb') as f:
    translations = pickle.load(f)

total_keys = len(translations)
print(f"=== PRODUCTION READINESS: ~{total_keys:,} Arabic Concepts ===")
print()

# 10 sample Arabic keys with translation counts
print("10 SAMPLE ARABIC KEYS WITH TRANSLATION COVERAGE:")
random.seed(123)
sample_keys = random.sample(list(translations.keys()), min(10, total_keys))
sample_analysis = []
for key in sample_keys:
    trans = translations.get(key, {})
    lang_count = len(trans)
    langs = list(trans.keys())[:5]
    line = f"  '{key}': {lang_count} languages ({', '.join(langs)}{'...' if lang_count > 5 else ''})"
    print(line)
    sample_analysis.append(f"| `{key}` | {lang_count} | {', '.join(trans.keys())} |")
print()

# Estimate total rows
# Each Arabic key produces 1 row for Arabic + N rows for translations
total_translation_count = 0
for key, trans in translations.items():
    total_translation_count += 1  # Arabic itself
    total_translation_count += len(trans)  # all translations

avg_per_key = total_translation_count / total_keys if total_keys > 0 else 0
print(f"Total Arabic keys: {total_keys:,}")
print(f"Total translation pairs: {total_translation_count:,}")
print(f"Average translations per key: {avg_per_key:.2f}")
print(f"Estimated rows for full run: ~{total_translation_count:,}")
print()

# Database connectivity check
print("DATABASE CONNECTIVITY CHECK:")
db_accessible = False
schema_exists = False
table_exists = False
db_error = None

try:
    conn = psycopg2.connect(
        host='localhost',
        dbname='morphlex',
        user='morphlex_user',
        password='morphlex_2026'
    )
    db_accessible = True
    print("  Database connection: OK")

    cur = conn.cursor()

    # Check if lexicon schema exists
    cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'lexicon'")
    if cur.fetchone():
        schema_exists = True
        print("  Schema 'lexicon': EXISTS")
    else:
        print("  Schema 'lexicon': NOT FOUND")

    # Check if entries table exists
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'lexicon' AND table_name = 'entries'
    """)
    if cur.fetchone():
        table_exists = True
        print("  Table 'lexicon.entries': EXISTS")
        # Count existing rows
        cur.execute("SELECT COUNT(*) FROM lexicon.entries")
        row_count = cur.fetchone()[0]
        print(f"  Existing rows in lexicon.entries: {row_count:,}")
    else:
        print("  Table 'lexicon.entries': NOT FOUND")

    conn.close()
except Exception as e:
    db_error = str(e)
    print(f"  Database connection: FAILED - {e}")

print()

# Check orchestrator/run_pipeline
print("ORCHESTRATOR CHECK:")
orchestrator_path = '/mnt/pgdata/morphlex/pipeline/orchestrator.py'
run_pipeline_path = '/mnt/pgdata/morphlex/run_pipeline.py'

if os.path.exists(orchestrator_path):
    print(f"  {orchestrator_path}: EXISTS")
else:
    print(f"  {orchestrator_path}: NOT FOUND")

if os.path.exists(run_pipeline_path):
    print(f"  {run_pipeline_path}: EXISTS")
else:
    print(f"  {run_pipeline_path}: NOT FOUND (may need to be created)")

print()

# Blockers summary
print("=== BLOCKERS SUMMARY ===")
blockers = []
if not db_accessible:
    blockers.append(f"Database not accessible: {db_error}")
if not schema_exists:
    blockers.append("Schema 'lexicon' does not exist")
if not table_exists:
    blockers.append("Table 'lexicon.entries' does not exist")
if not os.path.exists(run_pipeline_path):
    blockers.append("run_pipeline.py does not exist (batch runner needed)")

if blockers:
    print("BLOCKERS FOUND:")
    for b in blockers:
        print(f"  - {b}")
else:
    print("NO BLOCKERS - Ready for production run")
print()

# Write Part 3 to report
with open(REPORT_PATH, 'a') as f:
    f.write("## Part 3: Production Readiness Analysis\n\n")
    f.write(f"### Dataset Size\n")
    f.write(f"- **Total Arabic keys:** {total_keys:,}\n")
    f.write(f"- **Total translation pairs:** {total_translation_count:,}\n")
    f.write(f"- **Average translations per key:** {avg_per_key:.2f}\n")
    f.write(f"- **Estimated rows for full run:** ~{total_translation_count:,}\n\n")

    f.write("### 10 Sample Arabic Keys\n\n")
    f.write("| Arabic Key | Lang Count | Languages |\n")
    f.write("|------------|------------|------------|\n")
    for line in sample_analysis:
        f.write(f"{line}\n")
    f.write("\n")

    f.write("### Database Status\n")
    f.write(f"- **Connection:** {'OK' if db_accessible else 'FAILED'}\n")
    if db_error:
        f.write(f"- **Error:** {db_error}\n")
    f.write(f"- **Schema 'lexicon':** {'EXISTS' if schema_exists else 'NOT FOUND'}\n")
    f.write(f"- **Table 'lexicon.entries':** {'EXISTS' if table_exists else 'NOT FOUND'}\n\n")

    f.write("### Orchestrator Status\n")
    f.write(f"- **orchestrator.py:** {'EXISTS' if os.path.exists(orchestrator_path) else 'NOT FOUND'}\n")
    f.write(f"- **run_pipeline.py:** {'EXISTS' if os.path.exists(run_pipeline_path) else 'NOT FOUND'}\n\n")

    f.write("### Blockers\n")
    if blockers:
        for b in blockers:
            f.write(f"- {b}\n")
    else:
        f.write("**NO BLOCKERS** - Ready for production run\n")
    f.write("\n---\n\n")

PYEOF

END_TIME=$(date -Iseconds)
echo ""
echo "End: $END_TIME"
echo ""

# Finalize report
cat >> "$REPORT" << EOF
## Summary

**Report generated:** $END_TIME
**Git HEAD:** \`$GIT_HEAD\`
**Report file:** \`$REPORT\`

EOF

echo "=== HEALTH CHECK COMPLETE ==="
echo "Full report written to: $REPORT"
echo ""

# Print compact summary for Slack
echo "=== SLACK SUMMARY ==="
echo "Git HEAD: $GIT_SHORT"
echo "Time: $START_TIME -> $END_TIME"
echo "Cron: $CRON_ENABLED | Zombies: $ZOMBIES"
echo "Full report: $REPORT"
