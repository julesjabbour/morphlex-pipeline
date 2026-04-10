#!/usr/bin/env python3
"""Parse Ancient Greek WordNet (jcuenod) SQL INSERT files and build PWN synset-to-Greek word mapping.

Data is in .sql files containing INSERT statements, NOT SQLite databases.
Key files:
  - greek_lemma_1.sql, greek_lemma_2.sql (lemma definitions)
  - greek_synset.sql (synset to PWN offset mapping)
  - greek_synonyms_1.sql through greek_synonyms_5.sql (synset to lemma mappings)

Output: data/open_wordnets/agwn_synset_map.pkl
Format: {synset_offset_pos: [greek_word1, greek_word2, ...], ...}

Zero error suppression. All exceptions logged visibly.
"""

import os
import pickle
import re
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets/agwn-jcuenod")
OUTPUT_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets")
OUTPUT_FILE = OUTPUT_DIR / "agwn_synset_map.pkl"
CONCEPT_MAP_FILE = Path("/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl")


def log(msg):
    print(msg, flush=True)


def parse_pwn_id(synset_str, pos=None):
    """Extract PWN offset+pos from various synset ID formats."""
    if not synset_str:
        return None
    s = str(synset_str).strip()

    # URI format: http://wordnet-rdf.princeton.edu/wn31/00001740-n
    m = re.search(r'wn3[01]/(\d{8})-([nvasr])', s, re.I)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # eng-30-00001740-n or eng:30:00001740:n
    m = re.search(r'eng[-_:]30[-_:](\d{8})[-_:]([nvasr])', s, re.I)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # Plain 8-digit-pos
    m = re.search(r'(\d{8})[-_]([nvasr])', s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # 8 digits followed by pos no separator (00001740n)
    m = re.search(r'^(\d{8})([nvasr])$', s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # Just 8 digits, use provided pos
    if pos:
        m = re.search(r'^(\d{8})$', s)
        if m:
            pos_char = pos[0].lower() if pos else None
            if pos_char in 'nvasr':
                return f"{m.group(1)}-{pos_char}"

    return None


def parse_sql_insert_values(line):
    """Parse VALUES from a SQL INSERT statement.

    Handles: INSERT INTO table (cols) VALUES (val1, val2, ...);
    Returns list of tuples of values.
    """
    # Find VALUES clause
    values_match = re.search(r'VALUES\s*(.+)$', line, re.I)
    if not values_match:
        return []

    values_str = values_match.group(1)

    # Extract individual value tuples
    result = []
    # Match (val1, val2, ...) patterns
    pattern = r'\(([^)]+)\)'

    for match in re.finditer(pattern, values_str):
        values_content = match.group(1)
        # Parse comma-separated values, respecting quotes
        values = []
        current = ""
        in_quote = False
        quote_char = None

        for char in values_content:
            if char in "'" '"' and not in_quote:
                in_quote = True
                quote_char = char
            elif char == quote_char and in_quote:
                in_quote = False
                quote_char = None
            elif char == ',' and not in_quote:
                values.append(current.strip().strip("'\""))
                current = ""
                continue
            current += char

        if current.strip():
            values.append(current.strip().strip("'\""))

        if values:
            result.append(tuple(values))

    return result


def parse_sql_file_streaming(filepath, callback):
    """Parse SQL file line by line, calling callback for each row of values.

    This avoids loading entire file into memory for large files.
    """
    count = 0
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('--'):
                continue

            # Parse values
            values = parse_sql_insert_values(line)
            for row in values:
                count += 1
                callback(row)

    return count


def extract_columns_from_file(filepath):
    """Extract column names from first INSERT statement."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('--'):
                continue

            # Try to extract column names from INSERT INTO table (col1, col2, ...)
            col_match = re.search(r'INSERT\s+INTO\s+\w+\s*\(([^)]+)\)', line, re.I)
            if col_match:
                return [c.strip().strip('`"[]') for c in col_match.group(1).split(',')]

    return None


def main():
    log("=" * 70)
    log("PARSE AGWN (JCUENOD) - BUILD PWN SYNSET MAP")
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

    # Find all SQL files
    sql_files = list(DATA_DIR.rglob('*.sql'))
    log(f"Total SQL files: {len(sql_files)}")
    for f in sorted(sql_files, key=lambda x: x.stat().st_size, reverse=True)[:15]:
        log(f"  {f.relative_to(DATA_DIR)} ({f.stat().st_size:,} bytes)")
    if len(sql_files) > 15:
        log(f"  ... and {len(sql_files)-15} more")

    # Find key Greek files
    greek_sql = [f for f in sql_files if 'greek' in f.name.lower()]
    log(f"")
    log(f"Greek SQL files: {len(greek_sql)}")
    for f in greek_sql:
        log(f"  {f.name} ({f.stat().st_size:,} bytes)")

    # Step 2: Explore SQL structure
    log("")
    log("=" * 70)
    log("STEP 2: EXPLORE SQL STRUCTURE")
    log("=" * 70)
    log("")

    # Show first 20 lines of key files
    key_files = ['greek_lemma_1.sql', 'greek_synset.sql', 'greek_synonyms_1.sql']
    for key_name in key_files:
        matches = [f for f in sql_files if f.name == key_name]
        if matches:
            sql_file = matches[0]
            log(f"File: {sql_file.name}")
            log("-" * 50)
            with open(sql_file, 'r', encoding='utf-8', errors='replace') as f:
                for i, line in enumerate(f):
                    if i >= 20:
                        break
                    log(f"  {line.rstrip()[:120]}")
            log("")

    # Step 3: Parse SQL files
    log("")
    log("=" * 70)
    log("STEP 3: PARSE SQL DATA")
    log("=" * 70)
    log("")

    synset_map = {}

    # Build lemma_id -> lemma word mapping from greek_lemma_*.sql
    lemma_dict = {}
    lemma_files = sorted([f for f in sql_files if 'lemma' in f.name.lower() and 'greek' in f.name.lower()])

    log(f"Building lemma dictionary from {len(lemma_files)} files...")
    for sql_file in lemma_files:
        log(f"  Processing: {sql_file.name}")
        columns = extract_columns_from_file(sql_file)
        log(f"    Columns: {columns}")

        if columns:
            # Find lemma_id and lemma columns
            id_idx = None
            lemma_idx = None
            for i, col in enumerate(columns):
                col_lower = col.lower()
                if 'id' in col_lower and id_idx is None:
                    id_idx = i
                if col_lower in ['lemma', 'word', 'form', 'written_form', 'lemma_written']:
                    lemma_idx = i

            if id_idx is not None and lemma_idx is not None:
                def add_lemma(row):
                    if len(row) > max(id_idx, lemma_idx):
                        lemma_id = row[id_idx]
                        lemma = row[lemma_idx]
                        if lemma_id and lemma:
                            lemma_dict[lemma_id] = lemma

                count = parse_sql_file_streaming(sql_file, add_lemma)
                log(f"    Processed {count:,} rows")

                # Show sample
                sample_keys = list(lemma_dict.keys())[:3]
                for k in sample_keys:
                    log(f"    Sample: {k} -> {lemma_dict[k]}")

    log(f"  Lemma dictionary: {len(lemma_dict):,} entries")
    log("")

    # Build synset_id -> offset mapping from greek_synset.sql
    synset_offset_map = {}
    synset_pos_map = {}
    synset_files = [f for f in sql_files if 'synset' in f.name.lower() and 'greek' in f.name.lower()]

    log(f"Building synset offset map from {len(synset_files)} files...")
    for sql_file in synset_files:
        log(f"  Processing: {sql_file.name}")
        columns = extract_columns_from_file(sql_file)
        log(f"    Columns: {columns}")

        if columns:
            # Find synset_id, offset, pos columns
            id_idx = None
            offset_idx = None
            pos_idx = None

            for i, col in enumerate(columns):
                col_lower = col.lower()
                if col_lower in ['id', 'synset_id'] and id_idx is None:
                    id_idx = i
                if col_lower in ['offset', 'wn_offset', 'pwn_offset', 'synset_offset']:
                    offset_idx = i
                if col_lower in ['pos', 'part_of_speech']:
                    pos_idx = i

            if id_idx is not None and offset_idx is not None:
                def add_synset(row):
                    if len(row) > max(id_idx, offset_idx):
                        synset_id = row[id_idx]
                        offset = row[offset_idx]
                        pos = row[pos_idx] if pos_idx is not None and len(row) > pos_idx else None
                        if synset_id and offset:
                            synset_offset_map[synset_id] = offset
                            if pos:
                                synset_pos_map[synset_id] = pos

                count = parse_sql_file_streaming(sql_file, add_synset)
                log(f"    Processed {count:,} rows")

                # Show sample
                sample_keys = list(synset_offset_map.keys())[:3]
                for k in sample_keys:
                    log(f"    Sample: {k} -> {synset_offset_map[k]}")

    log(f"  Synset offset map: {len(synset_offset_map):,} entries")
    log("")

    # Parse greek_synonyms_*.sql to get synset_id -> lemma_id mappings
    synonym_files = sorted([f for f in sql_files if 'synonym' in f.name.lower() and 'greek' in f.name.lower()])
    total_rows = 0
    mapped = 0
    skipped = 0

    log(f"Processing synonyms from {len(synonym_files)} files...")
    for sql_file in synonym_files:
        log(f"  Processing: {sql_file.name}")
        columns = extract_columns_from_file(sql_file)
        log(f"    Columns: {columns}")

        if not columns:
            log(f"    SKIP: No columns found")
            continue

        # Find synset_id and lemma_id columns
        synset_idx = None
        lemma_id_idx = None

        for i, col in enumerate(columns):
            col_lower = col.lower()
            if 'synset' in col_lower and synset_idx is None:
                synset_idx = i
            if 'lemma' in col_lower and lemma_id_idx is None:
                lemma_id_idx = i

        if synset_idx is None or lemma_id_idx is None:
            log(f"    SKIP: Could not find synset/lemma columns")
            continue

        log(f"    Using: synset_idx={synset_idx}, lemma_id_idx={lemma_id_idx}")

        file_rows = 0
        file_mapped = 0

        def process_synonym(row):
            nonlocal total_rows, mapped, skipped, file_rows, file_mapped

            file_rows += 1
            total_rows += 1

            if len(row) <= max(synset_idx, lemma_id_idx):
                skipped += 1
                return

            synset_id = row[synset_idx]
            lemma_id = row[lemma_id_idx]

            if not synset_id or not lemma_id:
                skipped += 1
                return

            # Get lemma word
            lemma = lemma_dict.get(lemma_id)
            if not lemma:
                skipped += 1
                return

            # Get PWN offset
            offset = synset_offset_map.get(synset_id)
            pos = synset_pos_map.get(synset_id)

            if offset:
                pwn_id = parse_pwn_id(offset, pos)
            else:
                pwn_id = parse_pwn_id(synset_id, pos)

            if not pwn_id:
                skipped += 1
                return

            if pwn_id in synset_map:
                if lemma not in synset_map[pwn_id]:
                    synset_map[pwn_id].append(lemma)
            else:
                synset_map[pwn_id] = [lemma]

            mapped += 1
            file_mapped += 1

        parse_sql_file_streaming(sql_file, process_synonym)
        log(f"    Rows: {file_rows:,}, mapped: {file_mapped:,}")

    log("")
    log(f"Total synonym rows: {total_rows:,}")
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
    log(f"Total Greek words: {total_words:,}")
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
            log(f"AGWN synsets: {len(synset_map):,}")
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
