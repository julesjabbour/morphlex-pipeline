#!/usr/bin/env python3
"""Parse IWN-En TSV files to build PWN synset-to-Sanskrit word mapping.

REWRITTEN to explore actual file structure first, then parse.

Output: data/open_wordnets/sanskrit_synset_map.pkl
Format: {synset_offset_pos: [sanskrit_word1, sanskrit_word2, ...], ...}

Zero error suppression. All exceptions logged visibly.
"""

import csv
import os
import pickle
import re
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets/iwn-en")
OUTPUT_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets")
OUTPUT_FILE = OUTPUT_DIR / "sanskrit_synset_map.pkl"
CONCEPT_MAP_FILE = Path("/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl")


def log(msg):
    print(msg, flush=True)


def parse_pwn_id(synset_str):
    """Extract PWN offset+pos from various synset ID formats."""
    if not synset_str:
        return None
    s = str(synset_str).strip()

    # eng-30-00001740-n or eng:30:00001740:n
    m = re.search(r'eng[-_:]30[-_:](\d{8})[-_:]([nvasr])', s, re.I)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # Plain 8-digit-pos
    m = re.search(r'(\d{8})[-_]([nvasr])', s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # 8 digits followed immediately by pos
    m = re.search(r'^(\d{8})([nvasr])$', s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    return None


def main():
    log("=" * 70)
    log("PARSE IWN-EN SANSKRIT - BUILD PWN SYNSET MAP")
    log("=" * 70)

    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        log(f"Git HEAD: {git_head}")

    start_time = datetime.now()
    log(f"Start: {start_time.isoformat()}")
    log("")

    # Step 1: Explore directory
    log("=" * 70)
    log("STEP 1: EXPLORE DIRECTORY")
    log("=" * 70)
    log("")

    if not DATA_DIR.exists():
        log(f"FATAL: Directory not found: {DATA_DIR}")
        sys.exit(1)

    log(f"Directory: {DATA_DIR}")
    log("")

    # Find all files
    all_files = [f for f in DATA_DIR.rglob('*') if f.is_file()]
    log(f"Total files: {len(all_files)}")

    for f in all_files[:30]:
        log(f"  {f.relative_to(DATA_DIR)} ({f.stat().st_size:,} bytes)")
    if len(all_files) > 30:
        log(f"  ... and {len(all_files)-30} more")

    # Find data files
    data_files = [f for f in all_files if f.suffix in ['.tsv', '.csv', '.txt']]
    log(f"")
    log(f"Data files: {len(data_files)}")

    # Look for Sanskrit-related files
    sanskrit_files = [f for f in all_files if 'sanskrit' in f.name.lower() or 'san' in f.name.lower()]
    log(f"Sanskrit-named files: {len(sanskrit_files)}")
    for f in sanskrit_files:
        log(f"  {f.name}")

    # Check for specific target
    target = DATA_DIR / "english-hindi-sanskrit-linked.tsv"
    log("")
    if target.exists():
        log(f"Target file EXISTS: {target.name}")
        data_file = target
    elif sanskrit_files:
        data_file = sanskrit_files[0]
        log(f"Using Sanskrit file: {data_file.name}")
    elif data_files:
        data_file = data_files[0]
        log(f"Using first data file: {data_file.name}")
    else:
        log("FATAL: No data files found")
        sys.exit(1)

    # Step 2: Explore file structure
    log("")
    log("=" * 70)
    log("STEP 2: EXPLORE FILE STRUCTURE")
    log("=" * 70)
    log("")

    log(f"Analyzing: {data_file.name}")
    log("")

    # Print first 30 lines
    log("First 30 lines:")
    with open(data_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 30:
                break
            log(f"  {i}: {line.rstrip()[:120]}")
    log("")

    # Detect delimiter
    with open(data_file, 'r', encoding='utf-8') as f:
        first_line = f.readline()

    tab_count = first_line.count('\t')
    comma_count = first_line.count(',')
    delimiter = '\t' if tab_count >= comma_count else ','
    delim_name = 'TAB' if delimiter == '\t' else delimiter
    log(f"Delimiter: {delim_name} (tabs={tab_count}, commas={comma_count})")

    # Parse header
    with open(data_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=delimiter)
        header = next(reader, None)

    if header:
        log(f"Columns ({len(header)}):")
        for i, col in enumerate(header):
            indicators = []
            cl = col.lower()
            if 'sanskrit' in cl or cl in ['san', 'sa']:
                indicators.append('SANSKRIT')
            if 'english' in cl or 'eng' in cl or 'pwn' in cl or 'wn' in cl:
                indicators.append('ENGLISH/PWN')
            if 'hindi' in cl:
                indicators.append('HINDI')
            if 'synset' in cl or 'offset' in cl or cl == 'id':
                indicators.append('SYNSET_ID')
            ind_str = f" <- {', '.join(indicators)}" if indicators else ""
            log(f"  [{i}] {col}{ind_str}")

    # Step 3: Parse file
    log("")
    log("=" * 70)
    log("STEP 3: PARSE FILE")
    log("=" * 70)
    log("")

    synset_map = {}
    total_rows = 0
    mapped = 0
    skipped = 0

    with open(data_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=delimiter)
        header = next(reader, None)

        if not header:
            log("FATAL: Empty file")
            sys.exit(1)

        header_lower = [h.lower().strip() for h in header]

        # Find column indices
        synset_col = None
        sanskrit_col = None
        pos_col = None

        for i, h in enumerate(header_lower):
            # Synset column - look for English/PWN synset ID
            if synset_col is None:
                if 'english' in h and ('synset' in h or 'offset' in h or 'id' in h):
                    synset_col = i
                elif h in ['pwn', 'wn', 'synset', 'offset', 'eng_synset', 'english_synset_id', 'ewn']:
                    synset_col = i
                elif h.startswith('eng') and synset_col is None:
                    synset_col = i

            # Sanskrit column
            if sanskrit_col is None:
                if 'sanskrit' in h or h in ['san', 'sa', 'sanskrit_lemma', 'sanskrit_word']:
                    sanskrit_col = i

            # POS column
            if pos_col is None:
                if h in ['pos', 'part_of_speech', 'category']:
                    pos_col = i

        log(f"Column indices: synset={synset_col}, sanskrit={sanskrit_col}, pos={pos_col}")

        # Fallback: if we can't find Sanskrit, try last column
        if sanskrit_col is None and len(header) >= 3:
            sanskrit_col = len(header) - 1
            log(f"Fallback: using last column [{sanskrit_col}] = {header[sanskrit_col]} as Sanskrit")

        # Fallback: if we can't find synset, try first column
        if synset_col is None:
            synset_col = 0
            log(f"Fallback: using first column [{synset_col}] = {header[synset_col]} as synset")

        if synset_col is None or sanskrit_col is None:
            log("FATAL: Cannot determine column mapping")
            sys.exit(1)

        log("")
        log("Processing rows...")

        for row in reader:
            total_rows += 1

            if len(row) <= max(synset_col, sanskrit_col):
                skipped += 1
                continue

            synset_id = row[synset_col].strip()
            sanskrit_text = row[sanskrit_col].strip()

            # Skip empty or null values
            if not synset_id or not sanskrit_text:
                skipped += 1
                continue
            if sanskrit_text.lower() in ['', '-', 'na', 'n/a', 'null', 'none', 'nan']:
                skipped += 1
                continue

            # Parse PWN ID
            pwn_id = parse_pwn_id(synset_id)

            # If no POS in synset ID, try to get from pos_col
            if pwn_id is None and pos_col is not None and len(row) > pos_col:
                # Try with just the digits + pos from pos column
                m = re.search(r'(\d{8})', synset_id)
                if m:
                    pos = row[pos_col].strip().lower()
                    if pos and pos[0] in 'nvasr':
                        pwn_id = f"{m.group(1)}-{pos[0]}"

            if not pwn_id:
                skipped += 1
                continue

            # Sanskrit text might have multiple words separated by ; , or |
            words = []
            for sep in [';', ',', '|', '/']:
                if sep in sanskrit_text:
                    words = [w.strip() for w in sanskrit_text.split(sep)]
                    break
            if not words:
                words = [sanskrit_text]

            # Filter valid words
            words = [w for w in words if w and w.lower() not in ['', '-', 'na', 'n/a', 'null', 'none']]

            if not words:
                skipped += 1
                continue

            # Add to map
            for word in words:
                if pwn_id in synset_map:
                    if word not in synset_map[pwn_id]:
                        synset_map[pwn_id].append(word)
                else:
                    synset_map[pwn_id] = [word]

            mapped += 1

            if total_rows % 10000 == 0:
                log(f"  Processed {total_rows:,}, mapped {mapped:,}, synsets {len(synset_map):,}")

    log("")
    log(f"Total rows: {total_rows:,}")
    log(f"Mapped: {mapped:,}")
    log(f"Skipped: {skipped:,}")
    log(f"Unique PWN synsets: {len(synset_map):,}")

    # Step 4: Write output
    log("")
    log("=" * 70)
    log("STEP 4: WRITE OUTPUT")
    log("=" * 70)
    log("")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'wb') as f:
        pickle.dump(synset_map, f, protocol=pickle.HIGHEST_PROTOCOL)

    output_size = OUTPUT_FILE.stat().st_size
    log(f"Written: {OUTPUT_FILE}")
    log(f"Size: {output_size:,} bytes ({output_size/1024:.1f} KB)")

    # Step 5: Report
    log("")
    log("=" * 70)
    log("REPORT")
    log("=" * 70)
    log("")

    log(f"Synsets mapped: {len(synset_map):,}")
    total_words = sum(len(v) for v in synset_map.values())
    log(f"Total Sanskrit words: {total_words:,}")
    if synset_map:
        log(f"Avg words/synset: {total_words/len(synset_map):.2f}")

    log("")
    log("5 sample entries:")
    for sid, words in list(synset_map.items())[:5]:
        preview = ', '.join(words[:3])
        if len(words) > 3:
            preview += f"... (+{len(words)-3})"
        log(f"  {sid}: [{preview}]")

    # Check overlap
    log("")
    log("Checking overlap with concept_wordnet_map.pkl...")
    if CONCEPT_MAP_FILE.exists():
        try:
            with open(CONCEPT_MAP_FILE, 'rb') as f:
                concept_map = pickle.load(f)

            concept_synsets = set()
            for k in concept_map.keys():
                m = re.search(r'(\d{8})-([nvasr])', str(k))
                if m:
                    concept_synsets.add(f"{m.group(1)}-{m.group(2)}")

            overlap = concept_synsets & set(synset_map.keys())
            log(f"concept_map synsets: {len(concept_synsets):,}")
            log(f"Sanskrit synsets: {len(synset_map):,}")
            log(f"Overlap: {len(overlap):,}")
            if concept_synsets:
                log(f"Coverage: {100*len(overlap)/len(concept_synsets):.1f}%")
        except Exception as e:
            log(f"ERROR: {type(e).__name__}: {e}")
    else:
        log(f"Not found: {CONCEPT_MAP_FILE}")

    log("")
    log(f"Duration: {datetime.now() - start_time}")
    log(f"End: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
