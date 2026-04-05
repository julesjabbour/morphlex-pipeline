#!/bin/bash
CONFIG="/mnt/pgdata/morphlex/.webhook_url"
if [ ! -f "$CONFIG" ]; then
  echo "ERROR: No webhook config at $CONFIG" >> /tmp/pipeline.log
  exit 1
fi
WEBHOOK_URL=$(cat "$CONFIG")
MESSAGE="$1"
curl -s -X POST "$WEBHOOK_URL" \
  -H 'Content-type: application/json' \
  --data "{\"text\": \"$MESSAGE\"}" > /dev/null 2>&1
