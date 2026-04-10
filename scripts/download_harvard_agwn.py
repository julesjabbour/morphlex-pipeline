#!/usr/bin/env python3
"""Download all Ancient Greek lemmas from Harvard Greek WordNet API with checkpointing.

Paginates through /api/lemmas (112,512 lemmas, ~1,126 pages at 100 per page).
Saves checkpoint after every page. Resumes from last checkpoint on restart.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# Configuration
BASE_URL = "https://greekwordnet.chs.harvard.edu"
PAGE_SIZE = 100
DELAY_BETWEEN_REQUESTS = 0.5  # 500ms minimum between requests
MAX_RETRIES = 5
INITIAL_BACKOFF = 2  # seconds, doubles each retry

# Paths
DATA_DIR = Path("/mnt/pgdata/morphlex/data/agwn")
CHECKPOINT_FILE = DATA_DIR / "harvard_agwn_checkpoint.json"
OUTPUT_FILE = DATA_DIR / "harvard_agwn_lemmas.json"
OLD_FILE = DATA_DIR / "harvard_agwn.json"


def fetch_page(page_num: int, offset: int) -> dict:
    """Fetch a single page from the API with retries and exponential backoff.

    Returns the JSON response dict, or None if all retries failed.
    Also returns error info for logging.
    """
    url = f"{BASE_URL}/api/lemmas/?limit={PAGE_SIZE}&offset={offset}"

    last_error_status = None
    last_error_message = None

    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 MorphlexPipeline/1.0'}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return data, None, None

        except urllib.error.HTTPError as e:
            last_error_status = e.code
            last_error_message = str(e.reason)
            print(f"  [Page {page_num}] HTTPError {e.code}: {e.reason} (attempt {attempt + 1}/{MAX_RETRIES})")

        except urllib.error.URLError as e:
            last_error_status = None
            last_error_message = str(e.reason)
            print(f"  [Page {page_num}] URLError: {e.reason} (attempt {attempt + 1}/{MAX_RETRIES})")

        except json.JSONDecodeError as e:
            last_error_status = None
            last_error_message = f"JSONDecodeError: {e.msg}"
            print(f"  [Page {page_num}] JSONDecodeError: {e.msg} (attempt {attempt + 1}/{MAX_RETRIES})")

        except TimeoutError as e:
            last_error_status = None
            last_error_message = "Request timeout"
            print(f"  [Page {page_num}] TimeoutError (attempt {attempt + 1}/{MAX_RETRIES})")

        except OSError as e:
            last_error_status = None
            last_error_message = f"OSError: {e}"
            print(f"  [Page {page_num}] OSError: {e} (attempt {attempt + 1}/{MAX_RETRIES})")

        # Exponential backoff before retry
        if attempt < MAX_RETRIES - 1:
            backoff = INITIAL_BACKOFF * (2 ** attempt)
            print(f"  [Page {page_num}] Waiting {backoff}s before retry...")
            time.sleep(backoff)

    # All retries exhausted
    return None, last_error_status, last_error_message


def load_checkpoint() -> dict:
    """Load checkpoint file if it exists."""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            checkpoint = json.load(f)
            print(f"Loaded checkpoint: page {checkpoint['last_completed_page']}, "
                  f"{len(checkpoint['lemmas'])} lemmas, "
                  f"{len(checkpoint['failed_pages'])} failed pages")
            return checkpoint
    return None


def save_checkpoint(checkpoint: dict) -> None:
    """Save checkpoint file."""
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(checkpoint, f, ensure_ascii=False)


def main():
    print("=" * 70)
    print("HARVARD ANCIENT GREEK WORDNET - LEMMA DOWNLOAD")
    print("=" * 70)

    # Print git HEAD for traceability
    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        print(f"Git HEAD: {git_head}")

    start_time = datetime.now()
    print(f"Start: {start_time.isoformat()}")
    print()

    # Ensure output directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Delete old incomplete file if it exists
    if OLD_FILE.exists():
        print(f"Deleting old incomplete file: {OLD_FILE}")
        OLD_FILE.unlink()

    # Check for existing checkpoint
    checkpoint = load_checkpoint()

    if checkpoint:
        lemmas = checkpoint['lemmas']
        failed_pages = checkpoint['failed_pages']
        start_page = checkpoint['last_completed_page'] + 1
        total_pages = checkpoint['total_pages']
        print(f"Resuming from page {start_page}")
    else:
        # Fresh start - get total count first
        print("Fetching first page to get total count...")
        first_data, err_status, err_msg = fetch_page(1, 0)

        if first_data is None:
            print(f"FATAL: Cannot fetch first page. Status: {err_status}, Error: {err_msg}")
            sys.exit(1)

        total_count = first_data.get('count', 0)
        total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE

        print(f"Total lemmas: {total_count:,}")
        print(f"Total pages: {total_pages:,}")
        print()

        # Extract lemmas from first page
        lemmas = []
        for entry in first_data.get('results', []):
            lemmas.append({
                'id': entry.get('id'),
                'lemma': entry.get('lemma', ''),
                'pos': entry.get('pos', ''),
                'uri': entry.get('uri', ''),
                'morpho': entry.get('morpho', '')
            })

        failed_pages = []
        start_page = 2  # Already got page 1

        # Save initial checkpoint
        checkpoint = {
            'last_completed_page': 1,
            'total_pages': total_pages,
            'lemmas': lemmas,
            'failed_pages': failed_pages
        }
        save_checkpoint(checkpoint)
        print(f"Page 1/{total_pages}: {len(lemmas)} lemmas collected")

    # Main pagination loop
    for page in range(start_page, total_pages + 1):
        offset = (page - 1) * PAGE_SIZE

        # Delay between requests
        time.sleep(DELAY_BETWEEN_REQUESTS)

        # Fetch page
        data, err_status, err_msg = fetch_page(page, offset)

        if data is None:
            # All retries failed - log and skip
            failed_pages.append({
                'page': page,
                'offset': offset,
                'status': err_status,
                'error': err_msg
            })
            print(f"FAILED: Page {page} (offset {offset}) - Status: {err_status}, Error: {err_msg}")
        else:
            # Extract lemmas from this page
            for entry in data.get('results', []):
                lemmas.append({
                    'id': entry.get('id'),
                    'lemma': entry.get('lemma', ''),
                    'pos': entry.get('pos', ''),
                    'uri': entry.get('uri', ''),
                    'morpho': entry.get('morpho', '')
                })

        # Update and save checkpoint after every page
        checkpoint = {
            'last_completed_page': page,
            'total_pages': total_pages,
            'lemmas': lemmas,
            'failed_pages': failed_pages
        }
        save_checkpoint(checkpoint)

        # Progress every 10 pages
        if page % 10 == 0:
            elapsed = datetime.now() - start_time
            print(f"Page {page}/{total_pages}: {len(lemmas):,} lemmas collected, "
                  f"elapsed: {elapsed}")

    print()
    print("=" * 70)
    print("DOWNLOAD COMPLETE")
    print("=" * 70)

    # Save final output
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(lemmas, f, ensure_ascii=False, indent=2)

    output_size = OUTPUT_FILE.stat().st_size
    print(f"Output file: {OUTPUT_FILE}")
    print(f"Output size: {output_size:,} bytes ({output_size / 1024 / 1024:.2f} MB)")

    # Remove checkpoint on complete success (no failed pages)
    if not failed_pages:
        CHECKPOINT_FILE.unlink()
        print("Checkpoint removed (all pages succeeded)")
    else:
        print(f"Checkpoint retained (contains {len(failed_pages)} failed page records)")

    # Final summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total pages fetched: {total_pages}")
    print(f"Total lemmas: {len(lemmas):,}")
    print(f"Failed pages: {len(failed_pages)}")

    if failed_pages:
        print()
        print("Failed pages detail:")
        for fp in failed_pages:
            print(f"  Page {fp['page']} (offset {fp['offset']}): "
                  f"status={fp['status']}, error={fp['error']}")

    end_time = datetime.now()
    duration = end_time - start_time
    print()
    print(f"Duration: {duration}")
    print(f"End: {end_time.isoformat()}")


if __name__ == "__main__":
    main()
