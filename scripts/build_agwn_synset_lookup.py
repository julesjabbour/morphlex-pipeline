#!/usr/bin/env python3
"""Build AGWN synset-to-lemma lookup from Harvard Greek WordNet API.

Strategy decision:
1. First try to fetch page 1 of /api/synsets and inspect structure
2. If synsets endpoint fails (timeout, error), fall back to per-lemma queries
3. If lemmas ARE included in synset entries: paginate through /api/synsets (1,078 pages)
4. If lemmas are NOT included: query /api/lemmas/{lemma}/{pos}/synsets for each lemma (112K calls)

Output: data/agwn/agwn_synset_lookup.pkl
Format: {synset_offset_pos: [lemma1, lemma2, ...], ...}
Example: {"00001740-n": ["ὕπαρξις", "οὐσία"], ...}

Zero error suppression. All exceptions logged visibly.
"""

import json
import os
import pickle
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

# Configuration
BASE_URL = "https://greekwordnet.chs.harvard.edu"
PAGE_SIZE = 100
DELAY_BETWEEN_REQUESTS = 1.0  # 1 second between requests (rate limit protection)
REQUEST_TIMEOUT = 60  # 60 second timeout per request
MAX_RETRIES = 5
INITIAL_BACKOFF = 2  # seconds, doubles each retry
LEMMA_BATCH_SIZE = 1000  # For per-lemma approach

# Paths
DATA_DIR = Path("/mnt/pgdata/morphlex/data/agwn")
LEMMAS_FILE = DATA_DIR / "harvard_agwn_lemmas.json"
CHECKPOINT_FILE = DATA_DIR / "agwn_synset_checkpoint.json"
OUTPUT_FILE = DATA_DIR / "agwn_synset_lookup.pkl"
CONCEPT_MAP_FILE = Path("/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl")


def log(msg):
    """Print with immediate flush."""
    print(msg, flush=True)


def fetch_url(url: str, description: str) -> tuple:
    """Fetch a URL with retries and exponential backoff.

    Returns (data, error_status, error_message) tuple.
    data is the JSON response, or None if all retries failed.
    """
    last_error_status = None
    last_error_message = None

    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 MorphlexPipeline/1.0'}
            )
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return data, None, None

        except urllib.error.HTTPError as e:
            last_error_status = e.code
            last_error_message = str(e.reason)
            log(f"  [{description}] HTTPError {e.code}: {e.reason} (attempt {attempt + 1}/{MAX_RETRIES})")

        except urllib.error.URLError as e:
            last_error_status = None
            last_error_message = str(e.reason)
            log(f"  [{description}] URLError: {e.reason} (attempt {attempt + 1}/{MAX_RETRIES})")

        except json.JSONDecodeError as e:
            last_error_status = None
            last_error_message = f"JSONDecodeError: {e.msg}"
            log(f"  [{description}] JSONDecodeError: {e.msg} (attempt {attempt + 1}/{MAX_RETRIES})")

        except TimeoutError:
            last_error_status = None
            last_error_message = "Request timeout"
            log(f"  [{description}] TimeoutError (attempt {attempt + 1}/{MAX_RETRIES})")

        except OSError as e:
            last_error_status = None
            last_error_message = f"OSError: {e}"
            log(f"  [{description}] OSError: {e} (attempt {attempt + 1}/{MAX_RETRIES})")

        # Exponential backoff before retry
        if attempt < MAX_RETRIES - 1:
            backoff = INITIAL_BACKOFF * (2 ** attempt)
            log(f"  [{description}] Waiting {backoff}s before retry...")
            time.sleep(backoff)

    return None, last_error_status, last_error_message


def load_checkpoint() -> dict:
    """Load checkpoint file if it exists."""
    if not CHECKPOINT_FILE.exists():
        return None

    try:
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            checkpoint = json.load(f)

        # Validate structure
        required_fields = ['mode', 'synset_lookup', 'completed_items', 'total_items', 'failed_items']
        for field in required_fields:
            if field not in checkpoint:
                log(f"WARNING: Checkpoint missing field '{field}', starting fresh")
                return None

        log(f"Loaded checkpoint: mode={checkpoint['mode']}, "
            f"{checkpoint['completed_items']}/{checkpoint['total_items']} completed, "
            f"{len(checkpoint['synset_lookup'])} synsets, "
            f"{len(checkpoint['failed_items'])} failed")
        return checkpoint

    except json.JSONDecodeError as e:
        log(f"ERROR: Checkpoint file is corrupt: {e}")
        return None
    except OSError as e:
        log(f"ERROR: Cannot read checkpoint: {e}")
        return None


def save_checkpoint(checkpoint: dict) -> None:
    """Save checkpoint file."""
    try:
        with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, ensure_ascii=False)
    except OSError as e:
        log(f"ERROR: Failed to save checkpoint: {e}")
        raise


def extract_synset_offset(synset_data: dict) -> str:
    """Extract PWN synset offset+pos from API synset data.

    Expected format in API: offset like "00001740" and pos like "n"
    Output format: "00001740-n"
    """
    offset = synset_data.get('offset', '')
    pos = synset_data.get('pos', '')

    # Handle various API formats
    if offset and pos:
        # Ensure offset is 8 digits
        offset_clean = str(offset).zfill(8)
        return f"{offset_clean}-{pos}"

    # Try to extract from uri if present
    uri = synset_data.get('uri', '')
    if uri:
        # URI might be like "http://wordnet-rdf.princeton.edu/wn31/00001740-n"
        # or "https://greekwordnet.chs.harvard.edu/synset/00001740-n"
        match = re.search(r'(\d{8})-([nvasr])', uri)
        if match:
            return f"{match.group(1)}-{match.group(2)}"

    return None


def inspect_synsets_structure():
    """Fetch page 1 of /api/synsets and print structure of first 2 entries.

    Returns (lemmas_included, total_pages, total_count, endpoint_failed).
    If the endpoint fails after all retries, returns (False, 0, 0, True) to trigger fallback.
    """
    log("=" * 70)
    log("STEP 1: INSPECT /api/synsets STRUCTURE")
    log("=" * 70)
    log("")
    log("Fetching page 1 of /api/synsets...")

    url = f"{BASE_URL}/api/synsets/?limit={PAGE_SIZE}&offset=0"
    data, err_status, err_msg = fetch_url(url, "synsets-page-1")

    if data is None:
        log(f"WARNING: Cannot fetch /api/synsets. Status: {err_status}, Error: {err_msg}")
        log("")
        log("Synsets endpoint failed, falling back to per-lemma queries")
        return False, 0, 0, True  # endpoint_failed = True

    total_count = data.get('count', 0)
    total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE
    results = data.get('results', [])

    log(f"Total synsets: {total_count:,}")
    log(f"Total pages: {total_pages:,}")
    log(f"Results on page 1: {len(results)}")
    log("")

    # Print FULL structure of first 2 results
    log("=" * 70)
    log("FULL STRUCTURE OF FIRST 2 SYNSET ENTRIES:")
    log("=" * 70)

    lemmas_included = False

    for i, entry in enumerate(results[:2]):
        log(f"\n--- Entry {i + 1} ---")
        log(json.dumps(entry, indent=2, ensure_ascii=False))

        # Check if lemmas are included
        if 'lemmas' in entry or 'words' in entry or 'senses' in entry:
            lemmas_included = True
            log("  ^ Contains lemma data")

    log("")
    log("=" * 70)

    if lemmas_included:
        log("DECISION: Lemmas ARE included in synset entries")
        log(f"Strategy: Paginate through /api/synsets ({total_pages:,} pages)")
    else:
        log("DECISION: Lemmas are NOT included in synset entries")
        log("Strategy: Fall back to per-lemma queries")

    return lemmas_included, total_pages, total_count, False  # endpoint_failed = False


def build_via_synsets(total_pages: int):
    """Build lookup by paginating through /api/synsets."""
    log("")
    log("=" * 70)
    log("STEP 2: BUILD LOOKUP VIA /api/synsets PAGINATION")
    log("=" * 70)

    start_time = datetime.now()

    # Check for checkpoint
    checkpoint = load_checkpoint()

    if checkpoint and checkpoint.get('mode') == 'synsets':
        synset_lookup = checkpoint['synset_lookup']
        failed_pages = checkpoint['failed_items']
        start_page = checkpoint['completed_items'] + 1
        log(f"Resuming from page {start_page}")
    else:
        synset_lookup = {}
        failed_pages = []
        start_page = 1

        # Initialize checkpoint
        checkpoint = {
            'mode': 'synsets',
            'synset_lookup': synset_lookup,
            'completed_items': 0,
            'total_items': total_pages,
            'failed_items': failed_pages
        }
        save_checkpoint(checkpoint)

    # Pagination loop
    for page in range(start_page, total_pages + 1):
        offset = (page - 1) * PAGE_SIZE

        # Delay between requests
        time.sleep(DELAY_BETWEEN_REQUESTS)

        url = f"{BASE_URL}/api/synsets/?limit={PAGE_SIZE}&offset={offset}"
        data, err_status, err_msg = fetch_url(url, f"Page {page}")

        if data is None:
            failed_pages.append({
                'page': page,
                'offset': offset,
                'status': err_status,
                'error': err_msg
            })
            log(f"FAILED: Page {page} (offset {offset}) - Status: {err_status}, Error: {err_msg}")
        else:
            # Extract synset -> lemmas mappings
            for synset_data in data.get('results', []):
                synset_id = extract_synset_offset(synset_data)
                if not synset_id:
                    continue

                # Try various possible fields for lemmas
                lemmas = []

                # Check 'lemmas' field (list of lemma objects or strings)
                if 'lemmas' in synset_data:
                    lemma_data = synset_data['lemmas']
                    if isinstance(lemma_data, list):
                        for item in lemma_data:
                            if isinstance(item, str):
                                lemmas.append(item)
                            elif isinstance(item, dict):
                                if 'lemma' in item:
                                    lemmas.append(item['lemma'])
                                elif 'word' in item:
                                    lemmas.append(item['word'])

                # Check 'words' field
                if 'words' in synset_data:
                    words_data = synset_data['words']
                    if isinstance(words_data, list):
                        for item in words_data:
                            if isinstance(item, str):
                                if item not in lemmas:
                                    lemmas.append(item)
                            elif isinstance(item, dict) and 'lemma' in item:
                                if item['lemma'] not in lemmas:
                                    lemmas.append(item['lemma'])

                # Check 'senses' field
                if 'senses' in synset_data:
                    senses_data = synset_data['senses']
                    if isinstance(senses_data, list):
                        for sense in senses_data:
                            if isinstance(sense, dict):
                                if 'lemma' in sense and sense['lemma'] not in lemmas:
                                    lemmas.append(sense['lemma'])
                                if 'word' in sense and sense['word'] not in lemmas:
                                    lemmas.append(sense['word'])

                if lemmas:
                    if synset_id in synset_lookup:
                        # Merge with existing lemmas
                        for lemma in lemmas:
                            if lemma not in synset_lookup[synset_id]:
                                synset_lookup[synset_id].append(lemma)
                    else:
                        synset_lookup[synset_id] = lemmas

        # Update checkpoint after every page
        checkpoint = {
            'mode': 'synsets',
            'synset_lookup': synset_lookup,
            'completed_items': page,
            'total_items': total_pages,
            'failed_items': failed_pages
        }
        save_checkpoint(checkpoint)

        # Progress every 10 pages
        if page % 10 == 0:
            elapsed = datetime.now() - start_time
            log(f"Page {page}/{total_pages}: {len(synset_lookup):,} synsets, elapsed: {elapsed}")

    return synset_lookup, failed_pages


def build_via_lemmas():
    """Build lookup by querying synsets for each lemma from harvard_agwn_lemmas.json."""
    log("")
    log("=" * 70)
    log("STEP 2: BUILD LOOKUP VIA PER-LEMMA QUERIES")
    log("=" * 70)

    # Load lemmas file
    if not LEMMAS_FILE.exists():
        log(f"FATAL: Lemmas file not found: {LEMMAS_FILE}")
        sys.exit(1)

    log(f"Loading lemmas from {LEMMAS_FILE}...")
    with open(LEMMAS_FILE, 'r', encoding='utf-8') as f:
        all_lemmas = json.load(f)

    log(f"Loaded {len(all_lemmas):,} lemmas")

    # Build unique (lemma, pos) pairs
    unique_pairs = []
    seen = set()
    for entry in all_lemmas:
        lemma = entry.get('lemma', '')
        pos = entry.get('pos', '')
        if lemma and pos:
            key = (lemma, pos)
            if key not in seen:
                seen.add(key)
                unique_pairs.append((lemma, pos))

    log(f"Unique (lemma, pos) pairs: {len(unique_pairs):,}")

    total_pairs = len(unique_pairs)
    total_batches = (total_pairs + LEMMA_BATCH_SIZE - 1) // LEMMA_BATCH_SIZE

    log(f"Total batches ({LEMMA_BATCH_SIZE} per batch): {total_batches:,}")

    start_time = datetime.now()

    # Check for checkpoint
    checkpoint = load_checkpoint()

    if checkpoint and checkpoint.get('mode') == 'lemmas':
        synset_lookup = checkpoint['synset_lookup']
        failed_items = checkpoint['failed_items']
        completed_items = checkpoint['completed_items']
        log(f"Resuming from lemma {completed_items + 1}")
    else:
        synset_lookup = {}
        failed_items = []
        completed_items = 0

        # Initialize checkpoint
        checkpoint = {
            'mode': 'lemmas',
            'synset_lookup': synset_lookup,
            'completed_items': 0,
            'total_items': total_pairs,
            'failed_items': failed_items
        }
        save_checkpoint(checkpoint)

    # Process in batches
    batch_num = completed_items // LEMMA_BATCH_SIZE

    for i in range(completed_items, total_pairs):
        lemma, pos = unique_pairs[i]

        # Delay between requests
        time.sleep(DELAY_BETWEEN_REQUESTS)

        # URL-encode the lemma (Greek characters)
        encoded_lemma = urllib.parse.quote(lemma, safe='')
        url = f"{BASE_URL}/api/lemmas/{encoded_lemma}/{pos}/synsets"

        data, err_status, err_msg = fetch_url(url, f"Lemma {i + 1}")

        if data is None:
            failed_items.append({
                'index': i,
                'lemma': lemma,
                'pos': pos,
                'status': err_status,
                'error': err_msg
            })
            if len(failed_items) <= 10 or len(failed_items) % 100 == 0:
                log(f"FAILED: Lemma '{lemma}' ({pos}) - Status: {err_status}, Error: {err_msg}")
        else:
            # Extract synsets for this lemma
            synsets_data = data.get('results', data) if isinstance(data, dict) else data
            if isinstance(synsets_data, list):
                for synset_data in synsets_data:
                    synset_id = extract_synset_offset(synset_data)
                    if synset_id:
                        if synset_id in synset_lookup:
                            if lemma not in synset_lookup[synset_id]:
                                synset_lookup[synset_id].append(lemma)
                        else:
                            synset_lookup[synset_id] = [lemma]

        completed_items = i + 1

        # Checkpoint and progress at batch boundaries
        current_batch = completed_items // LEMMA_BATCH_SIZE
        if current_batch > batch_num or completed_items == total_pairs:
            batch_num = current_batch
            elapsed = datetime.now() - start_time

            # Save checkpoint
            checkpoint = {
                'mode': 'lemmas',
                'synset_lookup': synset_lookup,
                'completed_items': completed_items,
                'total_items': total_pairs,
                'failed_items': failed_items
            }
            save_checkpoint(checkpoint)

            # Calculate ETA after first batch
            if current_batch == 1:
                time_per_item = elapsed.total_seconds() / completed_items
                remaining_items = total_pairs - completed_items
                eta_seconds = time_per_item * remaining_items
                eta_hours = eta_seconds / 3600
                log(f"Batch {current_batch}/{total_batches}: {completed_items:,}/{total_pairs:,} lemmas, "
                    f"{len(synset_lookup):,} synsets, elapsed: {elapsed}")
                log(f"ESTIMATED TOTAL TIME: {eta_hours:.1f} hours ({eta_seconds / 60:.0f} minutes)")
            else:
                log(f"Batch {current_batch}/{total_batches}: {completed_items:,}/{total_pairs:,} lemmas, "
                    f"{len(synset_lookup):,} synsets, elapsed: {elapsed}")

    return synset_lookup, failed_items


def write_output(synset_lookup: dict):
    """Write the final pickle file."""
    log("")
    log("=" * 70)
    log("STEP 3: WRITE OUTPUT")
    log("=" * 70)

    log(f"Writing {len(synset_lookup):,} synset mappings to {OUTPUT_FILE}...")

    try:
        with open(OUTPUT_FILE, 'wb') as f:
            pickle.dump(synset_lookup, f, protocol=pickle.HIGHEST_PROTOCOL)

        output_size = OUTPUT_FILE.stat().st_size
        log(f"Output file written: {OUTPUT_FILE}")
        log(f"Output size: {output_size:,} bytes ({output_size / 1024 / 1024:.2f} MB)")
        return output_size

    except OSError as e:
        log(f"FATAL: Cannot write output file: {e}")
        raise


def generate_report(synset_lookup: dict, failed_items: list, output_size: int):
    """Generate final report with stats."""
    log("")
    log("=" * 70)
    log("REPORT")
    log("=" * 70)

    # Total synsets mapped
    total_synsets = len(synset_lookup)
    log(f"Total synsets mapped: {total_synsets:,}")

    # Total lemmas covered
    total_lemmas = sum(len(v) for v in synset_lookup.values())
    log(f"Total lemmas covered: {total_lemmas:,}")

    # Average lemmas per synset
    if total_synsets > 0:
        avg_lemmas = total_lemmas / total_synsets
        log(f"Average lemmas per synset: {avg_lemmas:.2f}")

    # Overlap with concept_wordnet_map.pkl
    log("")
    log("Checking overlap with concept_wordnet_map.pkl...")

    if CONCEPT_MAP_FILE.exists():
        try:
            with open(CONCEPT_MAP_FILE, 'rb') as f:
                concept_map = pickle.load(f)

            concept_synsets = set()
            for synset_id in concept_map.keys():
                # Normalize synset ID format
                match = re.search(r'(\d{8})-([nvasr])', synset_id)
                if match:
                    norm_id = f"{match.group(1)}-{match.group(2)}"
                    concept_synsets.add(norm_id)

            agwn_synsets = set(synset_lookup.keys())
            overlap = concept_synsets & agwn_synsets

            log(f"concept_wordnet_map.pkl synsets: {len(concept_synsets):,}")
            log(f"AGWN synsets: {len(agwn_synsets):,}")
            log(f"Overlap count: {len(overlap):,}")

            if concept_synsets:
                overlap_pct = 100.0 * len(overlap) / len(concept_synsets)
                log(f"Overlap percentage: {overlap_pct:.1f}% of concept_map synsets have AGWN coverage")

        except Exception as e:
            log(f"ERROR loading concept_wordnet_map.pkl: {type(e).__name__}: {e}")
    else:
        log(f"concept_wordnet_map.pkl not found at {CONCEPT_MAP_FILE}")

    # 10 sample entries
    log("")
    log("10 sample entries:")
    sample_items = list(synset_lookup.items())[:10]
    for synset_id, lemmas in sample_items:
        lemmas_preview = ', '.join(lemmas[:5])
        if len(lemmas) > 5:
            lemmas_preview += f" ... (+{len(lemmas) - 5} more)"
        log(f"  {synset_id}: [{lemmas_preview}]")

    # File size
    log("")
    log(f"Output file size: {output_size:,} bytes ({output_size / 1024 / 1024:.2f} MB)")

    # Failed items
    if failed_items:
        log("")
        log(f"Failed items: {len(failed_items):,}")
        log("First 5 failures:")
        for item in failed_items[:5]:
            if 'page' in item:
                log(f"  Page {item['page']} (offset {item['offset']}): status={item.get('status')}, error={item.get('error')}")
            else:
                log(f"  Lemma '{item.get('lemma')}' ({item.get('pos')}): status={item.get('status')}, error={item.get('error')}")


def main():
    log("=" * 70)
    log("BUILD AGWN SYNSET-TO-LEMMA LOOKUP")
    log("=" * 70)

    # Print git HEAD for traceability
    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        log(f"Git HEAD: {git_head}")

    start_time = datetime.now()
    log(f"Start: {start_time.isoformat()}")
    log("")

    # Ensure output directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Check if checkpoint exists and is complete
    checkpoint = load_checkpoint()
    if checkpoint:
        if checkpoint['completed_items'] >= checkpoint['total_items']:
            log("")
            log("Checkpoint shows work complete - loading from checkpoint...")
            synset_lookup = checkpoint['synset_lookup']
            failed_items = checkpoint['failed_items']

            # Write output
            output_size = write_output(synset_lookup)

            # Generate report
            generate_report(synset_lookup, failed_items, output_size)

            # Clean up checkpoint if no failures
            if not failed_items:
                CHECKPOINT_FILE.unlink()
                log("")
                log("Checkpoint removed (all items succeeded)")
            else:
                log("")
                log("Checkpoint retained (contains failed item records)")

            end_time = datetime.now()
            duration = end_time - start_time
            log("")
            log(f"Duration: {duration}")
            log(f"End: {end_time.isoformat()}")
            return

    # Step 1: Inspect synsets structure (with fallback on failure)
    lemmas_included, total_pages, total_synsets, endpoint_failed = inspect_synsets_structure()

    # Step 2: Build lookup using appropriate strategy
    # If synsets endpoint failed or lemmas not included, use per-lemma approach
    if endpoint_failed or not lemmas_included:
        synset_lookup, failed_items = build_via_lemmas()
    else:
        synset_lookup, failed_items = build_via_synsets(total_pages)

    # Step 3: Write output
    output_size = write_output(synset_lookup)

    # Generate report
    generate_report(synset_lookup, failed_items, output_size)

    # Clean up checkpoint
    if not failed_items:
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()
        log("")
        log("Checkpoint removed (all items succeeded)")
    else:
        log("")
        log("Checkpoint retained (contains failed item records)")

    end_time = datetime.now()
    duration = end_time - start_time
    log("")
    log(f"Duration: {duration}")
    log(f"End: {end_time.isoformat()}")


if __name__ == "__main__":
    main()
