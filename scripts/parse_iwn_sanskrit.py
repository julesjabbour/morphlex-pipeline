#!/usr/bin/env python3
"""Parse Sanskrit data from IWN-En TSV files and build PWN synset-to-Sanskrit word mapping.

Source: https://github.com/cfiltnlp/IWN-En
Expected location: /mnt/pgdata/morphlex/data/open_wordnets/iwn-en/
Contains manually linked IndoWordNet synsets to English WordNet for 18 Indian languages.
Key file: english-hindi-sanskrit-linked.tsv

Output: data/open_wordnets/sanskrit_synset_map.pkl
Format: {synset_offset_pos: [sanskrit_word1, sanskrit_word2, ...], ...}
Example: {"00001740-n": ["वस्तु", "पदार्थ"], ...}

Zero error suppression. All exceptions logged visibly.
"""

import csv
import os
import pickle
import re
import sys
from datetime import datetime
from pathlib import Path

# Paths
DATA_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets/iwn-en")
OUTPUT_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets")
OUTPUT_FILE = OUTPUT_DIR / "sanskrit_synset_map.pkl"
CONCEPT_MAP_FILE = Path("/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl")

# Target file
SANSKRIT_TSV = DATA_DIR / "english-hindi-sanskrit-linked.tsv"


def log(msg):
    """Print with immediate flush."""
    print(msg, flush=True)


def explore_iwn_sanskrit():
    """Explore IWN-En directory structure and TSV format."""
    log("=" * 70)
    log("STEP 1: EXPLORE IWN-EN STRUCTURE")
    log("=" * 70)
    log("")

    if not DATA_DIR.exists():
        log(f"FATAL: IWN-En directory not found: {DATA_DIR}")
        sys.exit(1)

    log(f"IWN-En directory: {DATA_DIR}")
    log("")

    # List all files
    log("Directory contents:")
    all_files = []
    for item in sorted(DATA_DIR.rglob('*')):
        if item.is_file():
            size = item.stat().st_size
            rel_path = item.relative_to(DATA_DIR)
            log(f"  {rel_path} ({size:,} bytes)")
            all_files.append(item)
    log("")

    # Find TSV files
    tsv_files = list(DATA_DIR.rglob('*.tsv'))
    log(f"Total TSV files: {len(tsv_files)}")

    # Also check for CSV files
    csv_files = list(DATA_DIR.rglob('*.csv'))
    log(f"Total CSV files: {len(csv_files)}")
    log("")

    # Look for Sanskrit-specific files
    sanskrit_files = []
    for f in all_files:
        if 'sanskrit' in f.name.lower() or 'san' in f.name.lower():
            sanskrit_files.append(f)
            log(f"Sanskrit-related file: {f.name}")

    # Check for the specific target file
    if SANSKRIT_TSV.exists():
        log(f"Target file found: {SANSKRIT_TSV}")
        target_file = SANSKRIT_TSV
    elif sanskrit_files:
        target_file = sanskrit_files[0]
        log(f"Using alternative Sanskrit file: {target_file}")
    elif tsv_files:
        # Look for any file with linked/english in name
        for f in tsv_files:
            if 'link' in f.name.lower() or 'english' in f.name.lower():
                target_file = f
                log(f"Using linked file: {target_file}")
                break
        else:
            target_file = tsv_files[0]
            log(f"Using first TSV file: {target_file}")
    else:
        log("FATAL: No TSV/CSV files found")
        sys.exit(1)

    log("")

    # Explore file structure
    log("=" * 70)
    log("FILE STRUCTURE EXPLORATION:")
    log("=" * 70)
    log("")

    log(f"Analyzing: {target_file}")
    log("-" * 50)

    try:
        # Read first 30 lines to understand format
        log("First 30 lines:")
        with open(target_file, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= 30:
                    break
                line_preview = line.rstrip()[:200]
                log(f"  {i + 1}: {line_preview}")
        log("")

        # Try to detect delimiter
        with open(target_file, 'r', encoding='utf-8') as f:
            first_line = f.readline()

        tab_count = first_line.count('\t')
        comma_count = first_line.count(',')
        delimiter = '\t' if tab_count >= comma_count else ','
        delim_name = 'TAB' if delimiter == '\t' else delimiter
        log(f"Detected delimiter: {delim_name} (tabs: {tab_count}, commas: {comma_count})")

        # Parse header and sample data
        with open(target_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=delimiter)

            try:
                header = next(reader)
                log(f"Header columns: {header}")
                log(f"Column count: {len(header)}")
                log("")

                # Look for Sanskrit, English/PWN, and synset columns
                log("Column analysis:")
                for i, col in enumerate(header):
                    col_lower = col.lower()
                    indicators = []
                    if 'sanskrit' in col_lower or 'san' in col_lower:
                        indicators.append('SANSKRIT')
                    if 'english' in col_lower or 'eng' in col_lower or 'pwn' in col_lower or 'wn' in col_lower:
                        indicators.append('ENGLISH/PWN')
                    if 'hindi' in col_lower:
                        indicators.append('HINDI')
                    if 'synset' in col_lower or 'offset' in col_lower or 'id' in col_lower:
                        indicators.append('SYNSET_ID')
                    if 'lemma' in col_lower or 'word' in col_lower:
                        indicators.append('LEMMA')

                    indicator_str = f" <- {', '.join(indicators)}" if indicators else ""
                    log(f"  [{i}] {col}{indicator_str}")
                log("")

                # Sample rows
                log("Sample data rows:")
                for j, row in enumerate(reader):
                    if j >= 5:
                        break
                    log(f"  Row {j + 1}: {row}")

            except StopIteration:
                log("ERROR: File appears to be empty")

    except Exception as e:
        log(f"ERROR exploring file: {type(e).__name__}: {e}")

    return target_file


def parse_synset_id(synset_id):
    """Parse synset ID to extract PWN offset+pos.

    IWN-En synset IDs may be in formats like:
    - "00001740-n" (plain PWN format)
    - "eng-30-00001740-n"
    - "wn30:00001740n"
    """
    if not synset_id:
        return None

    synset_str = str(synset_id).strip()

    # Pattern: eng-30-00001740-n or eng:30:00001740:n
    match = re.search(r'eng[-:]30[-:](\d{8})[-:]([nvasr])', synset_str, re.IGNORECASE)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    # Pattern: plain 8-digit offset with POS
    match = re.search(r'(\d{8})[-_]?([nvasr])', synset_str)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    # Pattern: just 8 digits (will need POS from elsewhere)
    match = re.search(r'^(\d{8})$', synset_str)
    if match:
        return match.group(1)  # Return without POS for now

    return None


def build_synset_map(tsv_file):
    """Build PWN synset ID to Sanskrit words mapping from TSV file."""
    log("")
    log("=" * 70)
    log("STEP 2: BUILD SYNSET MAP")
    log("=" * 70)
    log("")

    synset_map = {}
    total_rows = 0
    mapped_rows = 0
    skipped_rows = 0

    start_time = datetime.now()

    log(f"Processing: {tsv_file}")

    try:
        # Detect delimiter
        with open(tsv_file, 'r', encoding='utf-8') as f:
            first_line = f.readline()
        delimiter = '\t' if first_line.count('\t') >= first_line.count(',') else ','

        with open(tsv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=delimiter)

            # Read header
            try:
                header = next(reader)
            except StopIteration:
                log("ERROR: Empty file")
                return synset_map

            header_lower = [h.lower().strip() for h in header]

            # Find relevant column indices
            sanskrit_col = None
            synset_col = None
            pos_col = None

            for i, col in enumerate(header_lower):
                # Sanskrit column
                if sanskrit_col is None:
                    if 'sanskrit' in col or col == 'san' or col == 'sa':
                        sanskrit_col = i
                    elif 'sanskrit_lemma' in col or 'sanskrit_word' in col:
                        sanskrit_col = i

                # Synset/PWN column
                if synset_col is None:
                    if 'english' in col and ('synset' in col or 'offset' in col or 'id' in col):
                        synset_col = i
                    elif col in ['pwn', 'wn', 'synset', 'offset', 'eng_synset', 'english_synset_id']:
                        synset_col = i
                    elif 'eng' in col and synset_col is None:
                        synset_col = i

                # POS column
                if pos_col is None:
                    if col == 'pos' or col == 'part_of_speech':
                        pos_col = i

            log(f"Detected columns: sanskrit={sanskrit_col}, synset={synset_col}, pos={pos_col}")

            if sanskrit_col is None:
                log("WARNING: Cannot find Sanskrit column")
                log(f"Header: {header}")
                # Try last column as Sanskrit (common pattern: eng, hindi, sanskrit)
                if len(header) >= 3:
                    sanskrit_col = len(header) - 1
                    log(f"Trying last column ({header[sanskrit_col]}) as Sanskrit")

            if synset_col is None:
                log("WARNING: Cannot find synset column")
                # Try first column
                synset_col = 0
                log(f"Trying first column ({header[synset_col]}) as synset")

            log("")
            log("Processing rows...")

            for row in reader:
                total_rows += 1

                if len(row) <= max(sanskrit_col or 0, synset_col or 0):
                    skipped_rows += 1
                    continue

                synset_id = row[synset_col] if synset_col is not None else None
                sanskrit_word = row[sanskrit_col] if sanskrit_col is not None else None

                if not synset_id or not sanskrit_word:
                    skipped_rows += 1
                    continue

                sanskrit_word = sanskrit_word.strip()
                if not sanskrit_word or sanskrit_word in ['-', 'NA', 'N/A', 'null', 'None']:
                    skipped_rows += 1
                    continue

                pwn_id = parse_synset_id(synset_id)
                if not pwn_id:
                    skipped_rows += 1
                    continue

                # If we only have offset without POS, try to get POS from pos_col
                if '-' not in pwn_id and pos_col is not None and len(row) > pos_col:
                    pos = row[pos_col].strip().lower()
                    if pos in ['n', 'v', 'a', 'r', 's', 'noun', 'verb', 'adj', 'adv']:
                        pos_char = pos[0]
                        pwn_id = f"{pwn_id}-{pos_char}"

                # Skip if still no POS
                if '-' not in pwn_id:
                    skipped_rows += 1
                    continue

                # Sanskrit words might be comma or semicolon separated
                words = []
                for sep in [';', ',', '|']:
                    if sep in sanskrit_word:
                        words = [w.strip() for w in sanskrit_word.split(sep) if w.strip()]
                        break
                if not words:
                    words = [sanskrit_word]

                for word in words:
                    if word and word not in ['-', 'NA', 'N/A', 'null', 'None']:
                        if pwn_id in synset_map:
                            if word not in synset_map[pwn_id]:
                                synset_map[pwn_id].append(word)
                        else:
                            synset_map[pwn_id] = [word]

                mapped_rows += 1

                # Progress
                if total_rows % 10000 == 0:
                    elapsed = datetime.now() - start_time
                    log(f"  Processed {total_rows:,} rows, {len(synset_map):,} synsets, elapsed: {elapsed}")

    except Exception as e:
        log(f"ERROR: {type(e).__name__}: {e}")

    log("")
    log(f"Total rows processed: {total_rows:,}")
    log(f"Rows mapped: {mapped_rows:,}")
    log(f"Rows skipped: {skipped_rows:,}")
    log(f"Unique PWN synsets: {len(synset_map):,}")

    return synset_map


def write_output(synset_map):
    """Write pickle file."""
    log("")
    log("=" * 70)
    log("STEP 3: WRITE OUTPUT")
    log("=" * 70)
    log("")

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log(f"Writing {len(synset_map):,} synset mappings to {OUTPUT_FILE}...")

    try:
        with open(OUTPUT_FILE, 'wb') as f:
            pickle.dump(synset_map, f, protocol=pickle.HIGHEST_PROTOCOL)

        output_size = OUTPUT_FILE.stat().st_size
        log(f"Output file written: {OUTPUT_FILE}")
        log(f"Output size: {output_size:,} bytes ({output_size / 1024:.1f} KB)")
        return output_size

    except OSError as e:
        log(f"FATAL: Cannot write output file: {e}")
        raise


def generate_report(synset_map, output_size):
    """Generate final report."""
    log("")
    log("=" * 70)
    log("REPORT")
    log("=" * 70)
    log("")

    # Total synsets mapped
    total_synsets = len(synset_map)
    log(f"Total synsets mapped: {total_synsets:,}")

    # Total words covered
    total_words = sum(len(v) for v in synset_map.values())
    log(f"Total Sanskrit words: {total_words:,}")

    # Average words per synset
    if total_synsets > 0:
        avg_words = total_words / total_synsets
        log(f"Average words per synset: {avg_words:.2f}")

    # 5 sample entries
    log("")
    log("5 sample entries:")
    sample_items = list(synset_map.items())[:5]
    for synset_id, words in sample_items:
        words_preview = ', '.join(words[:5])
        if len(words) > 5:
            words_preview += f" ... (+{len(words) - 5} more)"
        log(f"  {synset_id}: [{words_preview}]")

    # File size
    log("")
    log(f"Output file size: {output_size:,} bytes ({output_size / 1024:.1f} KB)")

    # Overlap with concept_wordnet_map.pkl
    log("")
    log("Checking overlap with concept_wordnet_map.pkl...")

    if CONCEPT_MAP_FILE.exists():
        try:
            with open(CONCEPT_MAP_FILE, 'rb') as f:
                concept_map = pickle.load(f)

            concept_synsets = set()
            for synset_id in concept_map.keys():
                match = re.search(r'(\d{8})-([nvasr])', str(synset_id))
                if match:
                    norm_id = f"{match.group(1)}-{match.group(2)}"
                    concept_synsets.add(norm_id)

            sanskrit_synsets = set(synset_map.keys())
            overlap = concept_synsets & sanskrit_synsets

            log(f"concept_wordnet_map.pkl synsets: {len(concept_synsets):,}")
            log(f"Sanskrit synsets: {len(sanskrit_synsets):,}")
            log(f"Overlap count: {len(overlap):,}")

            if concept_synsets:
                overlap_pct = 100.0 * len(overlap) / len(concept_synsets)
                log(f"Overlap percentage: {overlap_pct:.1f}% of concept_map synsets have Sanskrit coverage")

        except Exception as e:
            log(f"ERROR loading concept_wordnet_map.pkl: {type(e).__name__}: {e}")
    else:
        log(f"concept_wordnet_map.pkl not found at {CONCEPT_MAP_FILE}")


def main():
    log("=" * 70)
    log("PARSE IWN-EN SANSKRIT - BUILD PWN SYNSET MAP")
    log("=" * 70)

    # Print git HEAD for traceability
    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        log(f"Git HEAD: {git_head}")

    start_time = datetime.now()
    log(f"Start: {start_time.isoformat()}")
    log("")

    # Step 1: Explore IWN-En structure
    tsv_file = explore_iwn_sanskrit()

    # Step 2: Build synset map
    synset_map = build_synset_map(tsv_file)

    if not synset_map:
        log("")
        log("WARNING: No synset mappings extracted!")
        log("The file structure may be different than expected.")
        log("Check the exploration output above for clues.")

    # Step 3: Write output
    output_size = write_output(synset_map)

    # Generate report
    generate_report(synset_map, output_size)

    end_time = datetime.now()
    duration = end_time - start_time
    log("")
    log(f"Duration: {duration}")
    log(f"End: {end_time.isoformat()}")


if __name__ == "__main__":
    main()
