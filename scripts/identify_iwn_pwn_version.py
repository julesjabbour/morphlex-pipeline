#!/usr/bin/env python3
"""Identify which PWN version IndoWordNet uses.

PROBLEM: IWN english_id values (like 532338 for "folk_dance") don't match PWN 3.0
offsets. Only 50 out of 11,082 IWN synsets match the PWN 3.0 -> OEWN bridge.

This suggests IWN uses an older PWN version (1.7, 2.0, or 2.1).

APPROACH:
1. Sample 20 IWN english_id values with their English synset words
2. Download all available PWN versions via wn package
3. For each version, look up the English words and check if offsets match
4. The version where offsets match is our target

Zero error suppression. All output visible.
"""

import csv
import os
import re
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets/iwn-en")
OUTPUT_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets")


def log(msg):
    print(msg, flush=True)


def main():
    log("=" * 70)
    log("IDENTIFY PWN VERSION USED BY INDOWORDNET")
    log("=" * 70)

    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        log(f"Git HEAD: {git_head}")

    start_time = datetime.now()
    log(f"Start: {start_time.isoformat()}")
    log("")

    # Step 1: Read IWN README for version info
    log("=" * 70)
    log("STEP 1: CHECK IWN DOCUMENTATION FOR PWN VERSION")
    log("=" * 70)
    log("")

    readme_path = DATA_DIR / "README.md"
    if readme_path.exists():
        log(f"Reading {readme_path}...")
        with open(readme_path, 'r', encoding='utf-8') as f:
            readme_text = f.read()
        log("")
        log("README CONTENT:")
        log("-" * 50)
        log(readme_text[:3000])
        if len(readme_text) > 3000:
            log(f"... ({len(readme_text) - 3000} more chars)")
        log("-" * 50)
        log("")

        # Search for version mentions
        version_patterns = [
            r'WordNet\s*(\d+\.\d+)',
            r'PWN\s*(\d+\.\d+)',
            r'Princeton\s+WordNet\s*(\d+\.\d+)',
            r'version\s*(\d+\.\d+)',
        ]
        log("Searching for version mentions...")
        for pattern in version_patterns:
            matches = re.findall(pattern, readme_text, re.IGNORECASE)
            if matches:
                log(f"  Pattern '{pattern}': {matches}")
    else:
        log(f"README not found: {readme_path}")
    log("")

    # Step 2: Check TSV header for version info
    log("=" * 70)
    log("STEP 2: CHECK TSV FILE HEADER")
    log("=" * 70)
    log("")

    tsv_path = DATA_DIR / "data" / "english-hindi-sanskrit-linked.tsv"
    if not tsv_path.exists():
        tsv_path = DATA_DIR / "english-hindi-sanskrit-linked.tsv"

    if tsv_path.exists():
        log(f"First line of {tsv_path.name}:")
        with open(tsv_path, 'r', encoding='utf-8') as f:
            first_line = f.readline()
            log(f"  {first_line.rstrip()}")
        log("")
    else:
        log(f"TSV not found at expected paths")
        log("")

    # Step 3: Sample IWN english_id values with English words
    log("=" * 70)
    log("STEP 3: SAMPLE IWN ENGLISH_ID VALUES")
    log("=" * 70)
    log("")

    if not tsv_path.exists():
        log(f"FATAL: TSV file not found: {tsv_path}")
        sys.exit(1)

    # Parse 20 unique samples (english_id, english_synset_words pairs)
    samples = []
    seen_ids = set()

    with open(tsv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        header = next(reader, None)

        log(f"Header: {header}")
        log("")

        # Column indices (from previous analysis)
        ENGLISH_ID_COL = 2
        POS_COL = 3
        ENGLISH_WORDS_COL = 4

        log(f"Using columns: english_id={ENGLISH_ID_COL}, POS={POS_COL}, english_words={ENGLISH_WORDS_COL}")
        log("")

        for row in reader:
            if len(row) <= ENGLISH_WORDS_COL:
                continue

            english_id = row[ENGLISH_ID_COL].strip()
            pos = row[POS_COL].strip()
            english_words = row[ENGLISH_WORDS_COL].strip()

            if not english_id or not english_words:
                continue

            # Skip if we've seen this ID already
            if english_id in seen_ids:
                continue

            seen_ids.add(english_id)

            # Extract first word (lemma)
            first_word = english_words.split(',')[0].strip()

            samples.append({
                'english_id': english_id,
                'pos': pos,
                'words': english_words,
                'first_word': first_word,
            })

            if len(samples) >= 30:  # Get 30 samples to have extras
                break

    log(f"Collected {len(samples)} unique samples")
    log("")
    log("SAMPLES (english_id -> first_word):")
    for i, s in enumerate(samples[:20]):
        padded = str(s['english_id']).zfill(8)
        log(f"  {i+1:2}. {s['english_id']:>10} (padded: {padded}) | {s['pos']:10} | {s['first_word']}")
    log("")

    # Step 4: Try to download all available PWN versions
    log("=" * 70)
    log("STEP 4: DOWNLOAD AVAILABLE WORDNET VERSIONS")
    log("=" * 70)
    log("")

    try:
        import wn
        log("wn package imported successfully")
    except ImportError as e:
        log(f"FATAL: Cannot import wn: {e}")
        sys.exit(1)

    # Try various wordnet specs
    wordnet_specs = [
        'omw-en:1.4',   # Open Multilingual Wordnet (based on PWN 3.0)
        'pwn:3.0',      # Princeton WordNet 3.0
        'pwn:3.1',      # Princeton WordNet 3.1
        'ewn:2020',     # English WordNet 2020 (OEWN)
        'oewn:2024',    # Open English WordNet 2024
        # Older versions - may not be available
        'pwn:2.1',
        'pwn:2.0',
        'pwn:1.7',
        'omw:1.4',
    ]

    downloaded = []
    for spec in wordnet_specs:
        log(f"Trying {spec}...")
        try:
            wn.download(spec, progress=False)
            log(f"  Downloaded: {spec}")
            downloaded.append(spec)
        except TypeError:
            try:
                wn.download(spec)
                log(f"  Downloaded (no progress): {spec}")
                downloaded.append(spec)
            except Exception as e:
                log(f"  Error: {e}")
        except Exception as e:
            if "already added" in str(e).lower() or "exists" in str(e).lower():
                log(f"  Already installed: {spec}")
                downloaded.append(spec)
            else:
                log(f"  Error: {e}")

    log("")
    log(f"Available: {downloaded}")
    log("")

    # List all installed lexicons
    log("All installed lexicons:")
    for lex in wn.lexicons():
        log(f"  {lex.id} - {lex.label} - lang: {lex.language}")
    log("")

    # Step 5: For each wordnet, look up sample words and check offsets
    log("=" * 70)
    log("STEP 5: MATCH IWN OFFSETS AGAINST WORDNET VERSIONS")
    log("=" * 70)
    log("")

    # Get unique wordnet names from lexicons
    wn_names = set()
    for lex in wn.lexicons():
        # Extract base name (e.g., 'omw-en', 'oewn', 'ewn')
        wn_names.add(lex.id.split(':')[0])

    log(f"Wordnet names to test: {sorted(wn_names)}")
    log("")

    results = {}

    for wn_name in sorted(wn_names):
        log(f"Testing wordnet: {wn_name}")
        log("-" * 50)

        try:
            wordnet = wn.Wordnet(wn_name)
        except Exception as e:
            log(f"  Could not load: {e}")
            log("")
            continue

        matches = 0
        tested = 0

        for s in samples[:20]:
            iwn_id = str(s['english_id']).zfill(8)
            pos_char = {'NOUN': 'n', 'VERB': 'v', 'ADJECTIVE': 'a', 'ADVERB': 'r'}.get(s['pos'].upper(), 'n')
            first_word = s['first_word'].lower().replace(' ', '_')

            # Look up word in this wordnet
            try:
                synsets = wordnet.synsets(first_word)
            except Exception as e:
                synsets = []

            # Check if any synset offset matches the IWN ID
            match_found = False
            wn_offsets = []

            for syn in synsets:
                # Extract offset from synset ID
                sid = syn.id
                m = re.search(r'(\d{8})-([nvasr])', sid)
                if m:
                    offset = m.group(1)
                    pos = m.group(2)
                    wn_offsets.append(f"{offset}-{pos}")

                    if offset == iwn_id:
                        match_found = True
                        matches += 1
                        break

            tested += 1

            if tested <= 5 or match_found:
                match_str = "MATCH!" if match_found else "no match"
                log(f"  '{first_word}' iwn={iwn_id}: {match_str}")
                if wn_offsets[:5]:
                    log(f"    wn offsets: {wn_offsets[:5]}")

        results[wn_name] = {'matches': matches, 'tested': tested}
        pct = 100 * matches / tested if tested > 0 else 0
        log(f"  RESULT: {matches}/{tested} matches ({pct:.1f}%)")
        log("")

    # Step 6: Summary
    log("=" * 70)
    log("STEP 6: SUMMARY - BEST MATCH")
    log("=" * 70)
    log("")

    log("Match rates by wordnet version:")
    for wn_name, r in sorted(results.items(), key=lambda x: -x[1]['matches']):
        pct = 100 * r['matches'] / r['tested'] if r['tested'] > 0 else 0
        stars = '*' * min(10, r['matches'] // 2)
        log(f"  {wn_name:15} : {r['matches']:3}/{r['tested']:3} ({pct:5.1f}%) {stars}")

    log("")

    # Find best match
    best = max(results.items(), key=lambda x: x[1]['matches']) if results else None
    if best:
        log(f"BEST MATCH: {best[0]} with {best[1]['matches']}/{best[1]['tested']} matches")
    else:
        log("No matches found in any wordnet version")

    log("")

    # Step 7: Deep dive - analyze offset patterns
    log("=" * 70)
    log("STEP 7: ANALYZE OFFSET PATTERNS")
    log("=" * 70)
    log("")

    # Check if IWN offsets look like they could be from an older format
    iwn_offsets = [str(s['english_id']) for s in samples[:20]]
    log("IWN offset patterns:")
    log(f"  Min length: {min(len(o) for o in iwn_offsets)}")
    log(f"  Max length: {max(len(o) for o in iwn_offsets)}")
    log(f"  Sample offsets: {iwn_offsets[:10]}")
    log("")

    # Check leading zeros when zero-padded to 8 digits
    padded = [o.zfill(8) for o in iwn_offsets]
    log("Zero-padded to 8 digits:")
    log(f"  {padded[:10]}")
    log("")

    # If there's a good wordnet match, try to identify exact version info
    if best and best[1]['matches'] > 5:
        log(f"Attempting detailed analysis with {best[0]}...")
        try:
            wordnet = wn.Wordnet(best[0])
            log(f"  Synset count: {len(list(wordnet.synsets()))}")

            # Check for ILI support
            test_synsets = list(wordnet.synsets())[:5]
            for syn in test_synsets:
                ili = syn.ili
                log(f"  Synset {syn.id} ILI: {ili}")
        except Exception as e:
            log(f"  Error during analysis: {e}")

    log("")
    log("=" * 70)
    log("CONCLUSION")
    log("=" * 70)
    log("")

    if best and best[1]['matches'] >= 15:
        log(f"IWN appears to use {best[0]} synset IDs.")
        log(f"Match rate: {best[1]['matches']}/{best[1]['tested']} ({100*best[1]['matches']/best[1]['tested']:.1f}%)")
        log("")
        log("NEXT STEP: Build bridge from this wordnet version to OEWN")
    else:
        log("No clear match found. IWN may use:")
        log("  1. A PWN version not available in the wn package (1.7, 2.0, 2.1)")
        log("  2. Custom/modified synset IDs")
        log("")
        log("INVESTIGATION NEEDED:")
        log("  - Check IWN documentation/papers for version info")
        log("  - Look for PWN 2.x mapping files")
        log("  - Consider downloading PWN from Princeton directly")

    log("")
    log(f"Duration: {datetime.now() - start_time}")
    log(f"End: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
