#!/bin/bash
# slack_report.sh - Posts output to Slack, handles long messages by splitting
# Never truncates - splits into multiple messages if needed
# Always saves full output to /mnt/pgdata/morphlex/reports/

CONFIG="/mnt/pgdata/morphlex/.webhook_url"
if [ ! -f "$CONFIG" ]; then
  echo "ERROR: No webhook config at $CONFIG" >> /tmp/pipeline.log
  exit 1
fi
WEBHOOK_URL=$(cat "$CONFIG")
MESSAGE="$1"

# Save full untruncated output to reports directory
REPORTS_DIR="/mnt/pgdata/morphlex/reports"
mkdir -p "$REPORTS_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="$REPORTS_DIR/task_output_${TIMESTAMP}.md"
echo "$MESSAGE" > "$REPORT_FILE"
echo "Full output saved to: $REPORT_FILE"

# Post to Slack - split into chunks if over 3500 chars
python3 -c "
import json
import urllib.request
import sys
import math

msg = sys.argv[1]
webhook_url = sys.argv[2]
max_chars = 3500

def post_to_slack(text):
    data = json.dumps({'text': text}).encode()
    req = urllib.request.Request(webhook_url, data=data, headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req)

if len(msg) <= max_chars:
    # Single message - no splitting needed
    post_to_slack(msg)
else:
    # Split into chunks at line boundaries
    lines = msg.split('\n')
    chunks = []
    current_chunk = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1  # +1 for newline
        if current_len + line_len > max_chars and current_chunk:
            chunks.append('\n'.join(current_chunk))
            current_chunk = [line]
            current_len = line_len
        else:
            current_chunk.append(line)
            current_len += line_len

    if current_chunk:
        chunks.append('\n'.join(current_chunk))

    # Post each chunk with part indicator
    total = len(chunks)
    for i, chunk in enumerate(chunks, 1):
        header = f'[Part {i}/{total}]\n' if total > 1 else ''
        post_to_slack(header + chunk)
" "$MESSAGE" "$WEBHOOK_URL"
