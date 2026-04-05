#!/bin/bash
# Usage: bash slack_report.sh "Your message here"
WEBHOOK_URL="PLACEHOLDER_WEBHOOK"
MESSAGE="$1"
curl -s -X POST "$WEBHOOK_URL" \
  -H 'Content-type: application/json' \
  --data "{\"text\": \"$MESSAGE\"}" > /dev/null 2>&1
