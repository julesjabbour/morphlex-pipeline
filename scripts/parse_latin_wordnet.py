#!/usr/bin/env python3
"""Parse Latin WordNet SQLite/data files and build PWN synset-to-Latin word mapping.

REWRITTEN to explore actual data structure first, then parse.

Output: data/open_wordnets/latin_synset_map.pkl
Format: {synset_offset_pos: [latin_word1, latin_word2, ...], ...}

Zero error suppression. All exceptions logged visibly.
"""

import os
import pickle
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets/latin-wordnet")
OUTPUT_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets")
OUTPUT_FILE = OUTPUT_DIR / "latin_synset_map.pkl"
CONCEPT_MAP_FILE = Path("/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl")


def log(msg):
    print(msg, flush=True)


def parse_pwn_id(synset_str):
    """Extract PWN offset+pos from various synset ID formats."""
    if not synset_str:
        return None
    s = str(synset_str)

    # eng-30-00001740-n
    m = re.search(r'eng[-_:]30[-_:](\d{8})[-_:]([nvasr])', s, re.I)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # Plain 8-digit-pos
    m = re.search(r'(\d{8})[-_]([nvasr])', s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # wn30:00001740n (no separator)
    m = re.search(r'wn\d+:(\d{8})([nvasr])', s, re.I)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # 00001740n (offset followed by pos, no separator)
    m = re.search(r'^(\d{8})([nvasr])$', s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    return None


def find_db_files(data_dir):
    """Find SQLite database files in directory."""
    db_files = []
    for f in data_dir.rglob('*'):
        if not f.is_file():
            continue
        if f.suffix in ['.db', '.sqlite', '.sqlite3']:
            db_files.append(f)
        else:
            try:
                with open(f, 'rb') as fp:
                    if fp.read(16).startswith(b'SQLite format 3'):
                        db_files.append(f)
            except Exception:
                pass
    return db_files


def main():
    log("=" * 70)
    log("PARSE LATIN WORDNET - BUILD PWN SYNSET MAP")
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

    for f in all_files[:20]:
        log(f"  {f.relative_to(DATA_DIR)} ({f.stat().st_size:,} bytes)")
    if len(all_files) > 20:
        log(f"  ... and {len(all_files)-20} more")

    # Find SQLite files
    db_files = find_db_files(DATA_DIR)
    log(f"")
    log(f"SQLite files: {len(db_files)}")

    # Also check for CSV/TSV
    csv_files = [f for f in all_files if f.suffix in ['.csv', '.tsv', '.txt']]
    log(f"CSV/TSV files: {len(csv_files)}")

    # Step 2: Explore database structure
    log("")
    log("=" * 70)
    log("STEP 2: EXPLORE DATA STRUCTURE")
    log("=" * 70)
    log("")

    synset_map = {}

    if db_files:
        for db_file in db_files[:3]:
            log(f"Database: {db_file.name}")
            log("-" * 50)

            try:
                conn = sqlite3.connect(str(db_file))
                cursor = conn.cursor()

                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in cursor.fetchall()]
                log(f"Tables: {tables}")

                for table in tables[:10]:
                    log(f"")
                    log(f"  Table: {table}")
                    cursor.execute(f"PRAGMA table_info('{table}')")
                    cols = cursor.fetchall()
                    col_names = [c[1] for c in cols]
                    log(f"    Columns: {col_names}")

                    cursor.execute(f"SELECT COUNT(*) FROM '{table}'")
                    row_count = cursor.fetchone()[0]
                    log(f"    Rows: {row_count:,}")

                    cursor.execute(f"SELECT * FROM '{table}' LIMIT 3")
                    for row in cursor.fetchall():
                        log(f"    Sample: {row}")

                conn.close()

            except Exception as e:
                log(f"  ERROR: {type(e).__name__}: {e}")
            log("")

    if csv_files:
        for csv_file in csv_files[:3]:
            log(f"CSV/TSV: {csv_file.name}")
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        if i >= 5:
                            break
                        log(f"  {line.rstrip()[:100]}")
            except Exception as e:
                log(f"  ERROR: {e}")
            log("")

    # Step 3: Parse data
    log("")
    log("=" * 70)
    log("STEP 3: PARSE DATA")
    log("=" * 70)
    log("")

    total_rows = 0
    mapped = 0
    skipped = 0

    # Parse SQLite databases
    for db_file in db_files:
        log(f"Processing: {db_file.name}")

        try:
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cursor.fetchall()]

            for table in tables:
                cursor.execute(f"PRAGMA table_info('{table}')")
                cols = [c[1].lower() for c in cursor.fetchall()]
                original_cols = {c.lower(): c for c in [r[1] for r in cursor.execute(f"PRAGMA table_info('{table}')").fetchall()]}

                # Find synset and lemma columns
                synset_col = None
                lemma_col = None

                for c in cols:
                    if synset_col is None:
                        if c in ['synset', 'synset_id', 'offset', 'wn_synset', 'pwn', 'wn30', 'id']:
                            synset_col = c
                        elif 'synset' in c or 'offset' in c:
                            synset_col = c

                for c in cols:
                    if lemma_col is None:
                        if c in ['lemma', 'word', 'form', 'literal', 'latin', 'la']:
                            lemma_col = c
                        elif 'lemma' in c or 'word' in c:
                            lemma_col = c

                if not synset_col or not lemma_col:
                    continue

                log(f"  Table {table}: synset={synset_col}, lemma={lemma_col}")

                sc = original_cols.get(synset_col, synset_col)
                lc = original_cols.get(lemma_col, lemma_col)

                cursor.execute(f'SELECT "{sc}", "{lc}" FROM "{table}"')
                for row in cursor:
                    total_rows += 1
                    synset_id, lemma = row

                    if not synset_id or not lemma:
                        skipped += 1
                        continue

                    lemma = str(lemma).strip()
                    if not lemma:
                        skipped += 1
                        continue

                    pwn_id = parse_pwn_id(synset_id)
                    if pwn_id:
                        if pwn_id in synset_map:
                            if lemma not in synset_map[pwn_id]:
                                synset_map[pwn_id].append(lemma)
                        else:
                            synset_map[pwn_id] = [lemma]
                        mapped += 1
                    else:
                        skipped += 1

            conn.close()

        except Exception as e:
            log(f"  ERROR: {type(e).__name__}: {e}")

    # Parse CSV/TSV files
    for csv_file in csv_files:
        log(f"Processing: {csv_file.name}")
        try:
            import csv
            with open(csv_file, 'r', encoding='utf-8') as f:
                first_line = f.readline()
            delim = '\t' if first_line.count('\t') > first_line.count(',') else ','

            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=delim)
                header = next(reader, None)
                if not header:
                    continue

                header_lower = [h.lower() for h in header]

                synset_col = None
                lemma_col = None

                for i, h in enumerate(header_lower):
                    if synset_col is None and ('synset' in h or 'offset' in h or h == 'pwn'):
                        synset_col = i
                    if lemma_col is None and ('lemma' in h or 'word' in h or 'latin' in h):
                        lemma_col = i

                if synset_col is None or lemma_col is None:
                    continue

                log(f"  Columns: synset={header[synset_col]}, lemma={header[lemma_col]}")

                for row in reader:
                    total_rows += 1
                    if len(row) <= max(synset_col, lemma_col):
                        skipped += 1
                        continue

                    synset_id = row[synset_col]
                    lemma = row[lemma_col].strip()

                    if not synset_id or not lemma:
                        skipped += 1
                        continue

                    pwn_id = parse_pwn_id(synset_id)
                    if pwn_id:
                        if pwn_id in synset_map:
                            if lemma not in synset_map[pwn_id]:
                                synset_map[pwn_id].append(lemma)
                        else:
                            synset_map[pwn_id] = [lemma]
                        mapped += 1
                    else:
                        skipped += 1

        except Exception as e:
            log(f"  ERROR: {type(e).__name__}: {e}")

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
    log(f"Total Latin words: {total_words:,}")
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
            log(f"Latin synsets: {len(synset_map):,}")
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
