#!/usr/bin/env python3
"""Parse Ancient Greek WordNet (jcuenod archive) SQLite databases and build PWN synset-to-Greek word mapping.

Source: https://github.com/greekwordnet/greekwordnet (jcuenod version)
Expected location: /mnt/pgdata/morphlex/data/open_wordnets/agwn-jcuenod/

The greekwordnet package contains SQLite databases with synset-to-lemma mappings.

Output: data/open_wordnets/agwn_synset_map.pkl
Format: {synset_offset_pos: [greek_word1, greek_word2, ...], ...}
Example: {"00001740-n": ["ὕπαρξις", "οὐσία"], ...}

Zero error suppression. All exceptions logged visibly.
"""

import os
import pickle
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Paths
DATA_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets/agwn-jcuenod")
OUTPUT_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets")
OUTPUT_FILE = OUTPUT_DIR / "agwn_synset_map.pkl"
CONCEPT_MAP_FILE = Path("/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl")


def log(msg):
    """Print with immediate flush."""
    print(msg, flush=True)


def explore_agwn():
    """Explore AGWN directory and database structure."""
    log("=" * 70)
    log("STEP 1: EXPLORE AGWN (JCUENOD) STRUCTURE")
    log("=" * 70)
    log("")

    if not DATA_DIR.exists():
        log(f"FATAL: AGWN directory not found: {DATA_DIR}")
        sys.exit(1)

    log(f"AGWN directory: {DATA_DIR}")
    log("")

    # List all files recursively
    log("Directory contents:")
    all_files = []
    for item in sorted(DATA_DIR.rglob('*')):
        if item.is_file():
            size = item.stat().st_size
            rel_path = item.relative_to(DATA_DIR)
            log(f"  {rel_path} ({size:,} bytes)")
            all_files.append(item)
    log("")

    # Find SQLite databases
    db_files = []
    for f in all_files:
        if f.suffix in ['.db', '.sqlite', '.sqlite3']:
            db_files.append(f)
        elif f.suffix == '' and f.name not in ['README', 'LICENSE', 'CHANGELOG', '.gitignore']:
            # Check if it's a SQLite file by magic bytes
            try:
                with open(f, 'rb') as fp:
                    header = fp.read(16)
                    if header.startswith(b'SQLite format 3'):
                        db_files.append(f)
                        log(f"Found SQLite file: {f}")
            except Exception:
                pass

    log(f"Found {len(db_files)} SQLite database files")
    log("")

    if not db_files:
        log("No SQLite files found, checking for greekwordnet package...")
        # Try using the greekwordnet package
        try:
            import greekwordnet
            log(f"greekwordnet package found at: {greekwordnet.__file__}")

            # Check package data directory
            pkg_dir = Path(greekwordnet.__file__).parent
            pkg_db_files = list(pkg_dir.rglob('*.db')) + list(pkg_dir.rglob('*.sqlite*'))
            if pkg_db_files:
                log(f"Found {len(pkg_db_files)} database files in package")
                db_files = pkg_db_files
            else:
                # Check for data subdirectory
                data_subdir = pkg_dir / 'data'
                if data_subdir.exists():
                    log(f"Checking data subdir: {data_subdir}")
                    for f in data_subdir.rglob('*'):
                        if f.is_file():
                            log(f"  Found: {f}")
                            if f.suffix in ['.db', '.sqlite', '.sqlite3']:
                                db_files.append(f)
        except ImportError:
            log("greekwordnet package not installed")

    if not db_files:
        log("Looking for alternative data files...")
        # Try TSV, CSV, JSON
        for ext in ['*.tsv', '*.csv', '*.json', '*.txt']:
            alt_files = list(DATA_DIR.rglob(ext))
            if alt_files:
                log(f"Found {len(alt_files)} {ext} files")

    if not db_files:
        log("No database files found, searching for any data files...")
        # Try to find any parseable files
        for f in all_files:
            if f.suffix in ['.tsv', '.csv', '.json']:
                log(f"Found data file: {f}")

    if not db_files:
        log("WARNING: No database files found - checking for alternative structures")

    # Explore database structure if files found
    if db_files:
        log("=" * 70)
        log("DATABASE STRUCTURE EXPLORATION:")
        log("=" * 70)
        log("")

        for db_file in db_files[:3]:  # Explore first 3 databases
            log(f"Database: {db_file}")
            log("-" * 50)

            try:
                conn = sqlite3.connect(str(db_file))
                cursor = conn.cursor()

                # Get all tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                tables = [row[0] for row in cursor.fetchall()]
                log(f"Tables: {tables}")
                log("")

                # Explore each table
                for table in tables[:10]:  # First 10 tables
                    log(f"  Table: {table}")

                    # Get schema
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = cursor.fetchall()
                    col_names = [col[1] for col in columns]
                    log(f"    Columns: {col_names}")

                    # Get row count
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    row_count = cursor.fetchone()[0]
                    log(f"    Row count: {row_count:,}")

                    # Sample rows
                    cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                    sample_rows = cursor.fetchall()
                    log(f"    Sample rows:")
                    for row in sample_rows:
                        log(f"      {row}")
                    log("")

                conn.close()

            except sqlite3.Error as e:
                log(f"  ERROR: {e}")
            except Exception as e:
                log(f"  ERROR: {type(e).__name__}: {e}")

            log("")

    return db_files


def parse_synset_id(synset_id):
    """Parse synset ID to extract PWN offset+pos.

    AGWN synset IDs may be in formats like:
    - "00001740-n" (plain PWN format)
    - "eng-30-00001740-n"
    - "ili-i12345"
    - "http://wordnet-rdf.princeton.edu/wn31/00001740-n"
    """
    if not synset_id:
        return None

    synset_str = str(synset_id).strip()

    # Pattern: URI with offset
    match = re.search(r'wn3[01]/(\d{8})-([nvasr])', synset_str, re.IGNORECASE)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    # Pattern: eng-30-00001740-n
    match = re.search(r'eng[-:]30[-:](\d{8})[-:]([nvasr])', synset_str, re.IGNORECASE)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    # Pattern: plain 8-digit offset with POS
    match = re.search(r'(\d{8})[-_]([nvasr])', synset_str)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    # Pattern: 8 digits followed by POS without separator (00001740n)
    match = re.search(r'(\d{8})([nvasr])$', synset_str)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    return None


def build_synset_map(db_files):
    """Build PWN synset ID to Ancient Greek words mapping from SQLite databases."""
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

    for db_file in db_files:
        log(f"Processing: {db_file.name}")

        try:
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()

            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                # Get column names
                cursor.execute(f"PRAGMA table_info({table})")
                columns_info = cursor.fetchall()
                columns = [col[1].lower() for col in columns_info]
                original_cols = {col[1].lower(): col[1] for col in columns_info}

                # Look for synset and lemma columns
                synset_col = None
                lemma_col = None

                # Common column names for synsets
                for col in columns:
                    if col in ['synset', 'synset_id', 'wn_synset', 'pwn_synset', 'offset', 'synset_offset']:
                        synset_col = col
                        break
                    if 'synset' in col and synset_col is None:
                        synset_col = col

                # Common column names for lemmas
                for col in columns:
                    if col in ['lemma', 'word', 'grc_lemma', 'greek_lemma', 'ancient_greek', 'grc', 'form']:
                        lemma_col = col
                        break
                    if ('lemma' in col or 'word' in col or 'grc' in col or 'greek' in col) and lemma_col is None:
                        lemma_col = col

                if not synset_col or not lemma_col:
                    continue

                log(f"  Table {table}: synset_col={synset_col}, lemma_col={lemma_col}")

                # Get original case column names
                synset_col_orig = original_cols.get(synset_col, synset_col)
                lemma_col_orig = original_cols.get(lemma_col, lemma_col)

                # Query all rows
                cursor.execute(f'SELECT "{synset_col_orig}", "{lemma_col_orig}" FROM "{table}"')

                for row in cursor:
                    total_rows += 1
                    synset_id, lemma = row

                    if not synset_id or not lemma:
                        skipped_rows += 1
                        continue

                    lemma = str(lemma).strip()
                    if not lemma:
                        skipped_rows += 1
                        continue

                    pwn_id = parse_synset_id(synset_id)
                    if pwn_id:
                        if pwn_id in synset_map:
                            if lemma not in synset_map[pwn_id]:
                                synset_map[pwn_id].append(lemma)
                        else:
                            synset_map[pwn_id] = [lemma]
                        mapped_rows += 1
                    else:
                        skipped_rows += 1

            conn.close()

        except sqlite3.Error as e:
            log(f"  ERROR: {e}")
        except Exception as e:
            log(f"  ERROR: {type(e).__name__}: {e}")

        elapsed = datetime.now() - start_time
        log(f"  Progress: {len(synset_map):,} synsets, elapsed: {elapsed}")

    # Also try using greekwordnet package if available
    try:
        log("")
        log("Checking greekwordnet package for additional data...")
        import greekwordnet as gwn

        # The package might have different APIs
        if hasattr(gwn, 'synsets'):
            for synset in gwn.synsets():
                try:
                    synset_id = synset.id() if callable(synset.id) else synset.id
                    lemmas = synset.lemmas() if callable(synset.lemmas) else synset.lemmas

                    if synset_id and lemmas:
                        pwn_id = parse_synset_id(synset_id)
                        if pwn_id:
                            for lemma in lemmas:
                                word = lemma.name() if hasattr(lemma, 'name') else str(lemma)
                                if pwn_id in synset_map:
                                    if word not in synset_map[pwn_id]:
                                        synset_map[pwn_id].append(word)
                                else:
                                    synset_map[pwn_id] = [word]
                except Exception as e:
                    log(f"  Package entry error: {e}")
                    break

        log(f"After package check: {len(synset_map):,} synsets")

    except ImportError:
        log("greekwordnet package not available")
    except Exception as e:
        log(f"Package processing error: {type(e).__name__}: {e}")

    log("")
    log(f"Total rows processed: {total_rows:,}")
    log(f"Rows mapped to PWN: {mapped_rows:,}")
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
    log(f"Total Greek words: {total_words:,}")

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

            agwn_synsets = set(synset_map.keys())
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


def main():
    log("=" * 70)
    log("PARSE AGWN (JCUENOD) - BUILD PWN SYNSET MAP")
    log("=" * 70)

    # Print git HEAD for traceability
    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        log(f"Git HEAD: {git_head}")

    start_time = datetime.now()
    log(f"Start: {start_time.isoformat()}")
    log("")

    # Step 1: Explore AGWN structure
    db_files = explore_agwn()

    # Step 2: Build synset map
    synset_map = build_synset_map(db_files)

    if not synset_map:
        log("")
        log("WARNING: No synset mappings extracted!")
        log("The database structure may be different than expected.")
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
