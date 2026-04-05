#!/bin/bash
CONFIG="/mnt/pgdata/morphlex/.webhook_url"
if [ ! -f "$CONFIG" ]; then
  echo "ERROR: No webhook config at $CONFIG" >> /tmp/pipeline.log
  exit 1
fi
WEBHOOK_URL=$(cat "$CONFIG")
MESSAGE="$1"
python3 -c "
import json, urllib.request, sys
msg = sys.argv[1][:3000]
data = json.dumps({'text': msg}).encode()
req = urllib.request.Request(sys.argv[2], data=data, headers={'Content-Type': 'application/json'})
urllib.request.urlopen(req)
" "$MESSAGE" "$WEBHOOK_URL"
