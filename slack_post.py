#!/usr/bin/env python3
"""
slack_post.py - Robust Slack message poster
Usage: python3 slack_post.py <webhook_url> <message_file>

Handles messages of any size by splitting at line boundaries.
All errors logged to stderr and /tmp/morphlex_debug.log
"""

import sys
import json
import urllib.request
import urllib.error
import traceback
from pathlib import Path
from datetime import datetime

DEBUG_LOG = Path("/tmp/morphlex_debug.log")
MAX_CHARS = 3500  # Slack limit with safety margin


def log(msg: str) -> None:
    """Log to debug file."""
    timestamp = datetime.now().isoformat()
    line = f"[{timestamp}] slack_post.py: {msg}\n"
    with open(DEBUG_LOG, "a") as f:
        f.write(line)


def post_chunk(webhook_url: str, text: str) -> bool:
    """Post a single chunk to Slack. Returns True on success."""
    try:
        data = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            log(f"Posted {len(text)} chars, response: {resp.status}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        log(f"HTTP error {e.code}: {e.reason} - {body}")
        print(f"Slack HTTP error {e.code}: {e.reason}", file=sys.stderr)
        return False
    except urllib.error.URLError as e:
        log(f"URL error: {e.reason}")
        print(f"Slack URL error: {e.reason}", file=sys.stderr)
        return False
    except Exception as e:
        log(f"Exception: {type(e).__name__}: {e}")
        traceback.print_exc(file=sys.stderr)
        return False


def split_message(text: str) -> list[str]:
    """Split message into chunks at line boundaries."""
    if len(text) <= MAX_CHARS:
        return [text]

    chunks = []
    lines = text.split("\n")
    current_chunk = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1  # +1 for newline

        if current_len + line_len > MAX_CHARS and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_len = 0

        # Handle single lines longer than MAX_CHARS
        if line_len > MAX_CHARS:
            # Split long line into fixed-size pieces
            for i in range(0, len(line), MAX_CHARS - 100):
                chunks.append(line[i:i + MAX_CHARS - 100])
        else:
            current_chunk.append(line)
            current_len += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


def main():
    if len(sys.argv) != 3:
        print("Usage: slack_post.py <webhook_url> <message_file>", file=sys.stderr)
        sys.exit(1)

    webhook_url = sys.argv[1]
    message_file = Path(sys.argv[2])

    log(f"Starting: file={message_file}")

    # Validate webhook URL
    if not webhook_url.startswith("https://"):
        log(f"Invalid webhook URL: {webhook_url[:50]}")
        print("ERROR: Invalid webhook URL", file=sys.stderr)
        sys.exit(1)

    # Read message file
    if not message_file.exists():
        log(f"File not found: {message_file}")
        print(f"ERROR: File not found: {message_file}", file=sys.stderr)
        sys.exit(1)

    try:
        text = message_file.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        log(f"Read error: {e}")
        print(f"ERROR reading file: {e}", file=sys.stderr)
        sys.exit(1)

    log(f"Read {len(text)} chars from {message_file}")

    if not text.strip():
        text = "(empty output)"
        log("Empty message, using placeholder")

    # Split and post
    chunks = split_message(text)
    total = len(chunks)
    log(f"Split into {total} chunks")

    all_success = True
    for i, chunk in enumerate(chunks, 1):
        if total > 1:
            header = f"[Part {i}/{total}]\n"
            chunk = header + chunk

        if not post_chunk(webhook_url, chunk):
            all_success = False
            log(f"Failed to post chunk {i}/{total}")

    if all_success:
        log(f"Success: posted {len(text)} chars in {total} chunks")
        print(f"Posted {len(text)} chars to Slack")
        sys.exit(0)
    else:
        log("Partial failure")
        print("ERROR: Some chunks failed to post", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
