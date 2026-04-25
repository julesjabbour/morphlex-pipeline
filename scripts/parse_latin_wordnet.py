#!/usr/bin/env python3
"""Parse Latin WordNet SQL INSERT files and build PWN synset-to-Latin word mapping.

SQL format: INSERT INTO latin_synonyms VALUES (id,'lemma','pos','PWN_offset',...);
  - Column 1 (index 0): id
  - Column 2 (index 1): lemma (Latin word)
  - Column 3 (index 2): pos
  - Column 4 (index 3): PWN offset (8-digit number)

Output: data/open_wordnets/latin_synset_map.pkl
Format: {oewn_synset_id: [latin_word1, latin_word2, ...], ...}

Zero error suppression. All exceptions logged visibly.
"""

import os
import pickle
import re
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets/latin-wordnet")
OUTPUT_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets")
OUTPUT_FILE = OUTPUT_DIR / "latin_synset_map.pkl"
PWN_BRIDGE_FILE = OUTPUT_DIR / "pwn30_to_oewn_map.pkl"
CONCEPT_MAP_FILE = Path("/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl")


def log(msg):
    print(msg, flush=True)


def load_pwn_bridge():
    """Load PWN30 to OEWN synset ID mapping."""
    if PWN_BRIDGE_FILE.exists():
        with open(PWN_BRIDGE_FILE, 'rb') as f:
            bridge = pickle.load(f)
        log(f"Loaded PWN bridge: {len(bridge):,} mappings")
        return bridge
    else:
        log(f"WARNING: PWN bridge not found: {PWN_BRIDGE_FILE}")
        return {}


def pwn_to_oewn(pwn_offset, pos, bridge):
    """Convert PWN30 offset+pos to OEWN synset ID."""
    if not pwn_offset or not pos:
        return None

    offset = str(pwn_offset).strip().zfill(8)
    pos_char = pos[0].lower() if pos else 'n'
    if pos_char not in 'nvasr':
        pos_char = 'n'

    pwn_id = f"{offset}-{pos_char}"

    if bridge:
        oewn_id = bridge.get(pwn_id)
        if oewn_id:
            return oewn_id

    return f"oewn-{offset}-{pos_char}"


def parse_values_from_line(line):
    """Extract VALUES rows from SQL INSERT statement.

    Uses regex: VALUES\s*\((.+?)\);
    Returns list of tuples.
    """
    results = []

    matches = re.findall(r"VALUES\s*\((.+?)\);", line, re.IGNORECASE)

    for match in matches:
        values = parse_csv_values(match)
        if values:
            results.append(tuple(values))

    if not results and 'INSERT' in line.upper() and 'VALUES' in line.upper():
        pattern = r'\(([^)]+)\)'
        for m in re.finditer(pattern, line):
            if 'VALUES' in line[:m.start()].upper():
                values = parse_csv_values(m.group(1))
                if values:
                    results.append(tuple(values))

    return results


def parse_csv_values(csv_str):
    """Parse comma-separated values, respecting quotes."""
    values = []
    current = ""
    in_quote = False
    quote_char = None

    for char in csv_str:
        if char in "'\"" and not in_quote:
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

    return values


def main():
    log("=" * 70)
    log("PARSE LATIN WORDNET - BUILD OEWN SYNSET MAP")
    log("=" * 70)

    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        log(f"Git HEAD: {git_head}")

    start_time = datetime.now()
    log(f"Start: {start_time.isoformat()}")
    log("")

    if not DATA_DIR.exists():
        log(f"FATAL: Directory not found: {DATA_DIR}")
        sys.exit(1)

    log(f"Directory: {DATA_DIR}")

    bridge = load_pwn_bridge()
    log("")

    sql_files = list(DATA_DIR.rglob('*.sql'))
    log(f"Total SQL files: {len(sql_files)}")

    synonym_files = sorted([f for f in sql_files if 'synonym' in f.name.lower()])
    log(f"Synonym files: {len(synonym_files)}")
    for f in synonym_files:
        log(f"  {f.name} ({f.stat().st_size:,} bytes)")
    log("")

    log("Sample SQL lines from first synonym file:")
    if synonym_files:
        with open(synonym_files[0], 'r', encoding='utf-8', errors='replace') as f:
            for i, line in enumerate(f):
                if i >= 5:
                    break
                log(f"  {line.rstrip()[:150]}")
    log("")

    log("=" * 70)
    log("PARSING SQL VALUES")
    log("=" * 70)
    log("")

    synset_map = {}
    total_rows = 0
    mapped = 0
    skipped_no_values = 0
    skipped_short_row = 0
    skipped_no_lemma = 0
    skipped_no_synset = 0

    for sql_file in synonym_files:
        log(f"Processing: {sql_file.name}")
        file_rows = 0
        file_mapped = 0

        with open(sql_file, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('--'):
                    continue

                rows = parse_values_from_line(line)

                for row in rows:
                    total_rows += 1
                    file_rows += 1

                    if len(row) < 4:
                        skipped_short_row += 1
                        continue

                    lemma = row[1].strip() if row[1] else None
                    pos = row[2].strip() if row[2] else None
                    pwn_offset = row[3].strip() if row[3] else None

                    if not lemma:
                        skipped_no_lemma += 1
                        continue

                    if not pwn_offset or not pwn_offset.isdigit():
                        skipped_no_synset += 1
                        continue

                    oewn_id = pwn_to_oewn(pwn_offset, pos, bridge)
                    if not oewn_id:
                        skipped_no_synset += 1
                        continue

                    if oewn_id in synset_map:
                        if lemma not in synset_map[oewn_id]:
                            synset_map[oewn_id].append(lemma)
                    else:
                        synset_map[oewn_id] = [lemma]

                    mapped += 1
                    file_mapped += 1

        log(f"  Rows: {file_rows:,}, mapped: {file_mapped:,}")

    log("")
    log(f"Total rows parsed: {total_rows:,}")
    log(f"Mapped to synsets: {mapped:,}")
    log(f"Skipped (short row): {skipped_short_row:,}")
    log(f"Skipped (no lemma): {skipped_no_lemma:,}")
    log(f"Skipped (no synset): {skipped_no_synset:,}")
    log(f"Unique OEWN synsets: {len(synset_map):,}")

    log("")
    log("=" * 70)
    log("WRITE OUTPUT")
    log("=" * 70)
    log("")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'wb') as f:
        pickle.dump(synset_map, f, protocol=pickle.HIGHEST_PROTOCOL)

    output_size = OUTPUT_FILE.stat().st_size
    log(f"Written: {OUTPUT_FILE}")
    log(f"Size: {output_size:,} bytes ({output_size/1024:.1f} KB)")

    log("")
    log("=" * 70)
    log("REPORT")
    log("=" * 70)
    log("")

    log(f"Synsets: {len(synset_map):,}")
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

    log("")
    log("Checking overlap with concept_wordnet_map.pkl...")
    if CONCEPT_MAP_FILE.exists():
        try:
            with open(CONCEPT_MAP_FILE, 'rb') as f:
                concept_map = pickle.load(f)

            concept_synsets = set()
            for k in concept_map.keys():
                if isinstance(k, str) and k.startswith('oewn-'):
                    concept_synsets.add(k)
                else:
                    m = re.search(r'(\d{8})-([nvasr])', str(k))
                    if m:
                        concept_synsets.add(f"oewn-{m.group(1)}-{m.group(2)}")

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
