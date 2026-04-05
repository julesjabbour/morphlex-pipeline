#!/bin/bash
REPORT=""

# Run setup first
SETUP_OUT=$(bash /mnt/pgdata/morphlex/setup_db.sh 2>&1)
REPORT="*Setup:* $SETUP_OUT"

# Apply schema
source /mnt/pgdata/morphlex/venv/bin/activate
SCHEMA_OUT=$(sudo -u postgres psql -d morphlex -f /mnt/pgdata/morphlex/schema.sql 2>&1)
REPORT="$REPORT\n*Schema:* $SCHEMA_OUT"

# Verify
VERIFY_OUT=$(sudo -u postgres psql -d morphlex -c "\dt lexicon.*" 2>&1)
REPORT="$REPORT\n*Tables:* $VERIFY_OUT"

echo "Pipeline run complete at $(date)" >> /tmp/pipeline.log

# Report to Slack
bash /mnt/pgdata/morphlex/slack_report.sh "$(echo -e "$REPORT")"
