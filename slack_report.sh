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
import urllib.error
import sys
import traceback

msg = sys.argv[1]
webhook_url = sys.argv[2]
max_chars = 3500

def post_to_slack(text):
    try:
        data = json.dumps({'text': text}).encode()
        req = urllib.request.Request(webhook_url, data=data, headers={'Content-Type': 'application/json'})
        response = urllib.request.urlopen(req, timeout=30)
        return True
    except urllib.error.HTTPError as e:
        print(f'Slack HTTP error: {e.code} - {e.reason}', file=sys.stderr)
        print(f'Response body: {e.read().decode()}', file=sys.stderr)
        return False
    except urllib.error.URLError as e:
        print(f'Slack URL error: {e.reason}', file=sys.stderr)
        return False
    except Exception as e:
        print(f'Slack post error: {type(e).__name__}: {e}', file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return False

# Validate webhook URL
if not webhook_url or not webhook_url.startswith('https://'):
    print(f'Invalid webhook URL: {webhook_url[:50] if webhook_url else \"(empty)\"}...', file=sys.stderr)
    sys.exit(1)

success = True
if len(msg) <= max_chars:
    # Single message - no splitting needed
    success = post_to_slack(msg)
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
        if not post_to_slack(header + chunk):
            success = False
            print(f'Failed to post chunk {i}/{total}', file=sys.stderr)

if not success:
    sys.exit(1)
print(f'Successfully posted to Slack ({len(msg)} chars)')
" "$MESSAGE" "$WEBHOOK_URL" 2>&1

SLACK_EXIT=$?
if [ $SLACK_EXIT -ne 0 ]; then
    echo "ERROR: slack_report.sh failed with exit code $SLACK_EXIT" >> /tmp/morphlex_debug.log
fi
