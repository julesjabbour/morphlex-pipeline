#!/usr/bin/env python3
"""Download paginated lemma list from Harvard Greek WordNet API.

Downloads all 112,512 lemmas from http://greekwordnet.chs.harvard.edu/api/lemmas
with checkpointing and robust error handling.

Features:
- Checkpoint after every page (resumes from last completed page on restart)
- 5 retries per page with exponential backoff (2s, 4s, 8s, 16s, 32s)
- Skips failed pages after all retries (does not abort entire run)
- Progress logging every 10 pages
- 0.5s delay between requests
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

BASE_URL = "https://greekwordnet.chs.harvard.edu"
DELAY_BETWEEN_REQUESTS = 0.5  # 500ms between API calls
MAX_RETRIES = 5
INITIAL_BACKOFF = 2  # seconds, doubles each retry
PAGES_PER_PROGRESS = 10

# File paths
DATA_DIR = Path("/mnt/pgdata/morphlex/data/agwn")
CHECKPOINT_FILE = DATA_DIR / "harvard_agwn_checkpoint.json"
OUTPUT_FILE = DATA_DIR / "harvard_agwn_lemmas.json"
OLD_INCOMPLETE_FILE = DATA_DIR / "harvard_agwn.json"


def fetch_page(url: str) -> dict | None:
    """Fetch a single page from the API with retries and exponential backoff.

    Returns the JSON data on success, or None if all retries fail.
    Logs all errors visibly - no suppression.
    """
    backoff = INITIAL_BACKOFF
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 MorphlexPipeline/1.0'}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return data

        except urllib.error.HTTPError as e:
            last_error = f"HTTP Error {e.code}: {e.reason}"
            print(f"    Retry {attempt}/{MAX_RETRIES} after {backoff}s: {last_error}")

        except urllib.error.URLError as e:
            last_error = f"URL Error: {e.reason}"
            print(f"    Retry {attempt}/{MAX_RETRIES} after {backoff}s: {last_error}")

        except json.JSONDecodeError as e:
            last_error = f"JSON decode error: {e}"
            print(f"    Retry {attempt}/{MAX_RETRIES} after {backoff}s: {last_error}")

        except TimeoutError as e:
            last_error = f"Timeout: {e}"
            print(f"    Retry {attempt}/{MAX_RETRIES} after {backoff}s: {last_error}")

        if attempt < MAX_RETRIES:
            time.sleep(backoff)
            backoff *= 2

    return None


def load_checkpoint() -> dict:
    """Load checkpoint file if it exists.

    Returns dict with:
        - last_completed_page: int (0 if no checkpoint)
        - lemmas: list of lemma dicts collected so far
        - total_pages: int (estimated total)
        - failed_pages: list of (page_num, error_msg) tuples
    """
    if CHECKPOINT_FILE.exists():
        print(f"Found checkpoint file: {CHECKPOINT_FILE}")
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            checkpoint = json.load(f)
        print(f"  Resuming from page {checkpoint['last_completed_page'] + 1}")
        print(f"  Lemmas collected so far: {len(checkpoint['lemmas']):,}")
        if checkpoint.get('failed_pages'):
            print(f"  Failed pages so far: {len(checkpoint['failed_pages'])}")
        return checkpoint

    return {
        'last_completed_page': 0,
        'lemmas': [],
        'total_pages': 0,
        'failed_pages': []
    }


def save_checkpoint(checkpoint: dict) -> None:
    """Save checkpoint to file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(checkpoint, f, ensure_ascii=False)


def save_final_output(lemmas: list) -> None:
    """Save final lemmas list to output file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(lemmas, f, ensure_ascii=False, indent=2)


def main() -> int:
    print("=" * 70)
    print("DOWNLOAD HARVARD ANCIENT GREEK WORDNET LEMMAS")
    print("=" * 70)
    print(f"Git HEAD: {os.popen('git rev-parse HEAD').read().strip()}")
    start_time = datetime.now()
    print(f"Start: {start_time.isoformat()}")
    print()

    # Ensure output directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Delete old incomplete file if it exists
    if OLD_INCOMPLETE_FILE.exists():
        print(f"Deleting old incomplete file: {OLD_INCOMPLETE_FILE}")
        OLD_INCOMPLETE_FILE.unlink()
        print()

    # Load checkpoint or start fresh
    checkpoint = load_checkpoint()
    all_lemmas = checkpoint['lemmas']
    last_completed_page = checkpoint['last_completed_page']
    failed_pages = checkpoint.get('failed_pages', [])

    # Get first page to determine total count
    print()
    print("=" * 70)
    print("FETCHING LEMMA PAGES")
    print("=" * 70)

    if last_completed_page == 0:
        # First run - need to get total count
        first_url = f"{BASE_URL}/api/lemmas/?limit=100&offset=0"
        print(f"Fetching first page to get total count...")
        first_page_data = fetch_page(first_url)

        if first_page_data is None:
            print("ERROR: Failed to fetch first page after all retries")
            return 1

        total_count = first_page_data.get('count', 0)
        total_pages = (total_count + 99) // 100
        checkpoint['total_pages'] = total_pages

        print(f"Total lemmas: {total_count:,}")
        print(f"Total pages: {total_pages:,}")
        print()

        # Process first page
        for entry in first_page_data.get('results', []):
            all_lemmas.append({
                'lemma': entry.get('lemma', ''),
                'pos': entry.get('pos', ''),
                'uri': entry.get('uri', ''),
                'morpho': entry.get('morpho', ''),
            })

        last_completed_page = 1
        checkpoint['last_completed_page'] = last_completed_page
        checkpoint['lemmas'] = all_lemmas
        save_checkpoint(checkpoint)

        time.sleep(DELAY_BETWEEN_REQUESTS)
    else:
        total_pages = checkpoint['total_pages']
        print(f"Resuming from page {last_completed_page + 1}/{total_pages}")
        print(f"Lemmas collected so far: {len(all_lemmas):,}")
        print()

    # Paginate through remaining pages
    pages_fetched = last_completed_page
    pages_successful = last_completed_page

    for page_num in range(last_completed_page + 1, total_pages + 1):
        offset = (page_num - 1) * 100
        url = f"{BASE_URL}/api/lemmas/?limit=100&offset={offset}"

        page_data = fetch_page(url)

        if page_data is None:
            # All retries failed - log and skip
            error_msg = f"Page {page_num} failed after {MAX_RETRIES} retries"
            print(f"  SKIPPING {error_msg}")
            failed_pages.append({
                'page': page_num,
                'offset': offset,
                'error': error_msg
            })
        else:
            # Extract lemmas from this page
            for entry in page_data.get('results', []):
                all_lemmas.append({
                    'lemma': entry.get('lemma', ''),
                    'pos': entry.get('pos', ''),
                    'uri': entry.get('uri', ''),
                    'morpho': entry.get('morpho', ''),
                })
            pages_successful += 1

        pages_fetched += 1

        # Update checkpoint after every page
        checkpoint['last_completed_page'] = page_num
        checkpoint['lemmas'] = all_lemmas
        checkpoint['failed_pages'] = failed_pages
        save_checkpoint(checkpoint)

        # Progress logging every 10 pages
        if page_num % PAGES_PER_PROGRESS == 0:
            elapsed = datetime.now() - start_time
            print(f"  Page {page_num:,}/{total_pages:,}: "
                  f"{len(all_lemmas):,} lemmas collected, "
                  f"elapsed {elapsed}")

        # Delay between requests
        if page_num < total_pages:
            time.sleep(DELAY_BETWEEN_REQUESTS)

    # Final progress log
    elapsed = datetime.now() - start_time
    print()
    print(f"Pagination complete. Elapsed: {elapsed}")

    # Save final output
    print()
    print("=" * 70)
    print("SAVING FINAL OUTPUT")
    print("=" * 70)

    save_final_output(all_lemmas)
    output_size = OUTPUT_FILE.stat().st_size
    print(f"Saved: {OUTPUT_FILE}")
    print(f"File size: {output_size:,} bytes ({output_size/1024:.1f} KB)")

    # Print summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total pages: {total_pages:,}")
    print(f"Pages successfully fetched: {pages_successful:,}")
    print(f"Total lemmas collected: {len(all_lemmas):,}")

    if failed_pages:
        print()
        print(f"FAILED PAGES ({len(failed_pages)}):")
        for fp in failed_pages:
            print(f"  Page {fp['page']} (offset {fp['offset']}): {fp['error']}")
    else:
        print("Failed pages: None")

    print()
    end_time = datetime.now()
    duration = end_time - start_time
    print(f"Duration: {duration}")
    print(f"End: {end_time.isoformat()}")

    # Cleanup checkpoint on successful completion
    if CHECKPOINT_FILE.exists() and not failed_pages:
        print()
        print("Removing checkpoint file (download complete with no failures)")
        CHECKPOINT_FILE.unlink()

    return 0


if __name__ == "__main__":
    sys.exit(main())
