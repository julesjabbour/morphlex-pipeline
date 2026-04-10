#!/usr/bin/env python3
"""Parse Turkish KeNet XML files and build PWN synset-to-Turkish word mapping.

KeNet is the Turkish WordNet from Starlang Software.
Source: https://github.com/StarlangSoftware/TurkishWordNet

Expected location: /mnt/pgdata/morphlex/data/open_wordnets/kenet/
The XML files contain synset IDs linked to PWN and Turkish lemmas.

Output: data/open_wordnets/kenet_synset_map.pkl
Format: {synset_offset_pos: [turkish_word1, turkish_word2, ...], ...}
Example: {"00001740-n": ["varlık", "nesne"], ...}

Zero error suppression. All exceptions logged visibly.
"""

import os
import pickle
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# Paths
DATA_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets/kenet")
OUTPUT_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets")
OUTPUT_FILE = OUTPUT_DIR / "kenet_synset_map.pkl"
CONCEPT_MAP_FILE = Path("/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl")


def log(msg):
    """Print with immediate flush."""
    print(msg, flush=True)


def explore_kenet():
    """Explore KeNet directory structure and XML format."""
    log("=" * 70)
    log("STEP 1: EXPLORE KENET STRUCTURE")
    log("=" * 70)
    log("")

    if not DATA_DIR.exists():
        log(f"FATAL: KeNet directory not found: {DATA_DIR}")
        sys.exit(1)

    log(f"KeNet directory: {DATA_DIR}")
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

    # Find XML files
    xml_files = list(DATA_DIR.rglob('*.xml'))
    log(f"Total XML files: {len(xml_files)}")
    log("")

    if not xml_files:
        log("WARNING: No XML files found, looking for alternative data files...")
        # Look for other file types
        for ext in ['*.json', '*.txt', '*.tsv', '*.csv']:
            alt_files = list(DATA_DIR.rglob(ext))
            if alt_files:
                log(f"Found {len(alt_files)} {ext} files")
                xml_files = alt_files
                break

    if not xml_files:
        log("FATAL: No parseable data files found in KeNet directory")
        sys.exit(1)

    # Inspect first XML file
    log("Inspecting first XML file structure:")
    sample_file = xml_files[0]
    log(f"File: {sample_file}")
    log("")

    try:
        # Print first 50 lines of the file
        log("First 50 lines:")
        with open(sample_file, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= 50:
                    break
                log(f"  {i + 1}: {line.rstrip()}")
        log("")

        # Parse and show structure
        log("XML structure analysis:")
        tree = ET.parse(sample_file)
        root = tree.getroot()
        log(f"  Root tag: {root.tag}")
        log(f"  Root attributes: {dict(root.attrib)}")
        log(f"  Direct children: {[child.tag for child in root][:10]}")
        log("")

        # Show first few synset entries
        log("First 3 synset-like entries:")
        count = 0
        for elem in root.iter():
            if 'synset' in elem.tag.lower() or 'sense' in elem.tag.lower() or 'literal' in elem.tag.lower():
                if count < 3:
                    log(f"  Tag: {elem.tag}")
                    log(f"    Attributes: {dict(elem.attrib)}")
                    log(f"    Text: {elem.text[:100] if elem.text else None}")
                    log(f"    Children: {[(c.tag, c.text[:50] if c.text else None) for c in elem][:5]}")
                    log("")
                count += 1

        # Look for PWN-related attributes/elements
        log("Searching for PWN-related content:")
        pwn_patterns = ['pwn', 'wn30', 'wn31', 'ili', 'offset', 'pos']
        found_pwn = False
        for elem in root.iter():
            for key, val in elem.attrib.items():
                for pattern in pwn_patterns:
                    if pattern in key.lower() or pattern in str(val).lower():
                        log(f"  Found in {elem.tag}.{key}: {val}")
                        found_pwn = True
                        break
            if elem.text:
                for pattern in pwn_patterns:
                    if pattern in elem.text.lower()[:100]:
                        log(f"  Found in {elem.tag} text: {elem.text[:100]}")
                        found_pwn = True
                        break

        if not found_pwn:
            log("  No explicit PWN references found - will examine synset IDs")

    except ET.ParseError as e:
        log(f"ERROR: XML parse error: {e}")
        log("Trying to read as plain text...")
    except Exception as e:
        log(f"ERROR inspecting file: {type(e).__name__}: {e}")

    return xml_files


def parse_synset_id(synset_id):
    """Parse KeNet synset ID to extract PWN offset+pos.

    KeNet synset IDs may be in formats like:
    - "TUR10-0000001-n" (Turkish synset with PWN-like structure)
    - "ENG30-00001740-n" (direct PWN reference)
    - "00001740-n" (plain PWN format)
    """
    if not synset_id:
        return None

    synset_str = str(synset_id)

    # Try to extract 8-digit offset + POS
    # Pattern: ENG30-00001740-n or similar
    match = re.search(r'ENG\d+-(\d{8})-([nvasr])', synset_str, re.IGNORECASE)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    # Pattern: plain 8-digit offset with POS
    match = re.search(r'(\d{8})-([nvasr])', synset_str)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    # Pattern: variable-length ID with POS (pad to 8 digits)
    match = re.search(r'[A-Z]{3}\d*-(\d+)-([nvasr])', synset_str, re.IGNORECASE)
    if match:
        offset = match.group(1).zfill(8)
        return f"{offset}-{match.group(2)}"

    return None


def build_synset_map(xml_files):
    """Build PWN synset ID to Turkish words mapping from XML files."""
    log("")
    log("=" * 70)
    log("STEP 2: BUILD SYNSET MAP")
    log("=" * 70)
    log("")

    synset_map = {}
    total_synsets = 0
    mapped_synsets = 0
    skipped_synsets = 0
    parse_errors = 0

    start_time = datetime.now()

    for file_idx, xml_file in enumerate(xml_files):
        log(f"Processing {file_idx + 1}/{len(xml_files)}: {xml_file.name}")

        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            # Strategy: Look for various XML structures used by Turkish WordNets
            # Common structures:
            # 1. <SYNSET><ID>...</ID><LITERAL>word</LITERAL></SYNSET>
            # 2. <synset id="..." ili="..."><lemma>...</lemma></synset>
            # 3. <LexicalEntry><Lemma writtenForm="..."/><Sense synset="..."/></LexicalEntry>

            # Try different parsing strategies based on XML structure

            # Strategy 1: SYNSET/ID/LITERAL structure
            for synset_elem in root.iter('SYNSET'):
                total_synsets += 1

                synset_id = None
                turkish_words = []

                # Get synset ID
                id_elem = synset_elem.find('ID')
                if id_elem is not None and id_elem.text:
                    synset_id = id_elem.text.strip()

                # Also check for ILI attribute
                ili = synset_elem.get('ili') or synset_elem.get('ILI')
                if ili and not synset_id:
                    synset_id = ili

                # Get Turkish words from LITERAL elements
                for literal in synset_elem.findall('.//LITERAL'):
                    if literal.text:
                        word = literal.text.strip()
                        if word and word not in turkish_words:
                            turkish_words.append(word)

                # Also check SYNONYM elements
                for synonym in synset_elem.findall('.//SYNONYM'):
                    if synonym.text:
                        word = synonym.text.strip()
                        if word and word not in turkish_words:
                            turkish_words.append(word)

                if synset_id and turkish_words:
                    pwn_id = parse_synset_id(synset_id)
                    if pwn_id:
                        if pwn_id in synset_map:
                            for word in turkish_words:
                                if word not in synset_map[pwn_id]:
                                    synset_map[pwn_id].append(word)
                        else:
                            synset_map[pwn_id] = turkish_words
                        mapped_synsets += 1
                    else:
                        skipped_synsets += 1

            # Strategy 2: synset with ili attribute (lowercase tags)
            for synset_elem in root.iter('synset'):
                if synset_elem.tag == 'SYNSET':
                    continue  # Already processed above

                total_synsets += 1

                synset_id = synset_elem.get('id') or synset_elem.get('ili')
                turkish_words = []

                for lemma in synset_elem.findall('.//lemma'):
                    word = lemma.text or lemma.get('writtenForm') or lemma.get('form')
                    if word:
                        word = word.strip()
                        if word and word not in turkish_words:
                            turkish_words.append(word)

                if synset_id and turkish_words:
                    pwn_id = parse_synset_id(synset_id)
                    if pwn_id:
                        if pwn_id in synset_map:
                            for word in turkish_words:
                                if word not in synset_map[pwn_id]:
                                    synset_map[pwn_id].append(word)
                        else:
                            synset_map[pwn_id] = turkish_words
                        mapped_synsets += 1
                    else:
                        skipped_synsets += 1

            # Strategy 3: LexicalEntry structure (GWA/LMF format)
            for entry in root.iter('LexicalEntry'):
                lemma_elem = entry.find('.//Lemma')
                if lemma_elem is None:
                    continue

                word = lemma_elem.get('writtenForm') or lemma_elem.text
                if not word:
                    continue
                word = word.strip()

                for sense in entry.findall('.//Sense'):
                    total_synsets += 1
                    synset_id = sense.get('synset') or sense.get('ili')

                    if synset_id:
                        pwn_id = parse_synset_id(synset_id)
                        if pwn_id:
                            if pwn_id in synset_map:
                                if word not in synset_map[pwn_id]:
                                    synset_map[pwn_id].append(word)
                            else:
                                synset_map[pwn_id] = [word]
                            mapped_synsets += 1
                        else:
                            skipped_synsets += 1

        except ET.ParseError as e:
            log(f"  ERROR: XML parse error: {e}")
            parse_errors += 1
        except Exception as e:
            log(f"  ERROR: {type(e).__name__}: {e}")
            parse_errors += 1

        # Progress
        if (file_idx + 1) % 10 == 0:
            elapsed = datetime.now() - start_time
            log(f"  Progress: {len(synset_map):,} synsets mapped, elapsed: {elapsed}")

    log("")
    log(f"Total synsets encountered: {total_synsets:,}")
    log(f"Synsets mapped to PWN: {mapped_synsets:,}")
    log(f"Synsets skipped (no PWN ID): {skipped_synsets:,}")
    log(f"Files with parse errors: {parse_errors}")
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
    log(f"Total Turkish words: {total_words:,}")

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

            kenet_synsets = set(synset_map.keys())
            overlap = concept_synsets & kenet_synsets

            log(f"concept_wordnet_map.pkl synsets: {len(concept_synsets):,}")
            log(f"KeNet synsets: {len(kenet_synsets):,}")
            log(f"Overlap count: {len(overlap):,}")

            if concept_synsets:
                overlap_pct = 100.0 * len(overlap) / len(concept_synsets)
                log(f"Overlap percentage: {overlap_pct:.1f}% of concept_map synsets have KeNet coverage")

        except Exception as e:
            log(f"ERROR loading concept_wordnet_map.pkl: {type(e).__name__}: {e}")
    else:
        log(f"concept_wordnet_map.pkl not found at {CONCEPT_MAP_FILE}")


def main():
    log("=" * 70)
    log("PARSE TURKISH KENET - BUILD PWN SYNSET MAP")
    log("=" * 70)

    # Print git HEAD for traceability
    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        log(f"Git HEAD: {git_head}")

    start_time = datetime.now()
    log(f"Start: {start_time.isoformat()}")
    log("")

    # Step 1: Explore KeNet structure
    xml_files = explore_kenet()

    # Step 2: Build synset map
    synset_map = build_synset_map(xml_files)

    if not synset_map:
        log("")
        log("WARNING: No synset mappings extracted!")
        log("The XML structure may be different than expected.")
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
