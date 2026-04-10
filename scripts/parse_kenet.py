#!/usr/bin/env python3
"""Parse Turkish KeNet XML files and build PWN synset-to-Turkish word mapping.

REWRITTEN to explore actual XML structure first, then parse.

Output: data/open_wordnets/kenet_synset_map.pkl
Format: {synset_offset_pos: [turkish_word1, turkish_word2, ...], ...}

Zero error suppression. All exceptions logged visibly.
"""

import os
import pickle
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets/kenet")
OUTPUT_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets")
OUTPUT_FILE = OUTPUT_DIR / "kenet_synset_map.pkl"
CONCEPT_MAP_FILE = Path("/mnt/pgdata/morphlex/data/concept_wordnet_map.pkl")


def log(msg):
    print(msg, flush=True)


def parse_pwn_id(synset_str):
    """Extract PWN offset+pos from various synset ID formats."""
    if not synset_str:
        return None
    s = str(synset_str)

    # ENG30-00001740-n or eng-30-00001740-n
    m = re.search(r'ENG[-_]?30[-_](\d{8})[-_]([nvasr])', s, re.I)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # Plain 8-digit-pos
    m = re.search(r'(\d{8})[-_]([nvasr])', s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # TUR10-0001234-n (Turkish synset with PWN-style ID)
    m = re.search(r'TUR\d+-(\d+)-([nvasr])', s, re.I)
    if m:
        offset = m.group(1).zfill(8)
        return f"{offset}-{m.group(2)}"

    return None


def main():
    log("=" * 70)
    log("PARSE TURKISH KENET - BUILD PWN SYNSET MAP")
    log("=" * 70)

    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        log(f"Git HEAD: {git_head}")

    start_time = datetime.now()
    log(f"Start: {start_time.isoformat()}")
    log("")

    # Step 1: Explore directory
    log("=" * 70)
    log("STEP 1: EXPLORE KENET DIRECTORY")
    log("=" * 70)
    log("")

    if not DATA_DIR.exists():
        log(f"FATAL: Directory not found: {DATA_DIR}")
        sys.exit(1)

    log(f"Directory: {DATA_DIR}")
    log("")

    # Find all files
    all_files = list(DATA_DIR.rglob('*'))
    files = [f for f in all_files if f.is_file()]
    log(f"Total files: {len(files)}")

    xml_files = [f for f in files if f.suffix.lower() == '.xml']
    log(f"XML files: {len(xml_files)}")

    if not xml_files:
        log("FATAL: No XML files found")
        # Try other formats
        for ext in ['*.json', '*.tsv', '*.csv', '*.txt']:
            found = list(DATA_DIR.rglob(ext))
            if found:
                log(f"  Found {len(found)} {ext} files instead")
        sys.exit(1)

    # Show first few files
    log("")
    log("XML files found:")
    for f in xml_files[:10]:
        log(f"  {f.relative_to(DATA_DIR)} ({f.stat().st_size:,} bytes)")

    # Step 2: Explore XML structure
    log("")
    log("=" * 70)
    log("STEP 2: EXPLORE XML STRUCTURE")
    log("=" * 70)
    log("")

    sample_xml = xml_files[0]
    log(f"Analyzing: {sample_xml.name}")
    log("")

    # Print first 20 lines
    log("First 20 lines:")
    with open(sample_xml, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 20:
                break
            log(f"  {line.rstrip()[:100]}")
    log("")

    # Parse and explore structure
    tree = ET.parse(sample_xml)
    root = tree.getroot()
    log(f"Root tag: {root.tag}")
    log(f"Root attrs: {dict(root.attrib)}")

    # Find all unique tags
    all_tags = set()
    for elem in root.iter():
        all_tags.add(elem.tag)
    log(f"All tags: {sorted(all_tags)}")
    log("")

    # Look for synset-related elements
    synset_patterns = ['SYNSET', 'Synset', 'synset', 'LexicalEntry', 'Sense']
    found_pattern = None
    sample_elem = None

    for pattern in synset_patterns:
        elems = root.findall(f'.//{pattern}')
        if elems:
            log(f"Found {len(elems)} <{pattern}> elements")
            found_pattern = pattern
            sample_elem = elems[0]
            break

    if sample_elem is not None:
        log(f"")
        log(f"Sample <{found_pattern}> element:")
        log(f"  Attributes: {dict(sample_elem.attrib)}")
        log(f"  Children:")
        for child in sample_elem:
            text = child.text[:50] if child.text else None
            log(f"    <{child.tag}>: {text}")

    # Step 3: Parse all XML files
    log("")
    log("=" * 70)
    log("STEP 3: PARSE ALL XML FILES")
    log("=" * 70)
    log("")

    synset_map = {}
    total_synsets = 0
    mapped = 0
    skipped = 0
    parse_errors = 0

    for xml_file in xml_files:
        log(f"Processing: {xml_file.name}")

        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            # Strategy 1: <SYNSET> with <ID> and <LITERAL> children
            for synset in root.findall('.//SYNSET'):
                total_synsets += 1

                # Get synset ID
                id_elem = synset.find('ID')
                synset_id = id_elem.text.strip() if id_elem is not None and id_elem.text else None

                # Get words from LITERAL or SYNONYM
                words = []
                for lit in synset.findall('.//LITERAL'):
                    if lit.text:
                        words.append(lit.text.strip())
                for syn in synset.findall('.//SYNONYM'):
                    # SYNONYM may have LITERAL children
                    for lit in syn.findall('.//LITERAL'):
                        if lit.text:
                            words.append(lit.text.strip())
                    # Or direct text
                    if syn.text:
                        words.append(syn.text.strip())

                if synset_id and words:
                    pwn_id = parse_pwn_id(synset_id)
                    if pwn_id:
                        if pwn_id in synset_map:
                            for w in words:
                                if w and w not in synset_map[pwn_id]:
                                    synset_map[pwn_id].append(w)
                        else:
                            synset_map[pwn_id] = [w for w in words if w]
                        mapped += 1
                    else:
                        skipped += 1

            # Strategy 2: GWA/LMF format - <LexicalEntry> with <Lemma> and <Sense>
            for entry in root.findall('.//LexicalEntry'):
                lemma_elem = entry.find('.//Lemma')
                if lemma_elem is None:
                    continue

                word = lemma_elem.get('writtenForm') or lemma_elem.text
                if not word:
                    continue
                word = word.strip()

                for sense in entry.findall('.//Sense'):
                    total_synsets += 1
                    synset_id = sense.get('synset') or sense.get('ili') or sense.get('id')

                    if synset_id:
                        pwn_id = parse_pwn_id(synset_id)
                        if pwn_id:
                            if pwn_id in synset_map:
                                if word not in synset_map[pwn_id]:
                                    synset_map[pwn_id].append(word)
                            else:
                                synset_map[pwn_id] = [word]
                            mapped += 1
                        else:
                            skipped += 1

            # Strategy 3: lowercase <synset> with attributes
            for synset in root.findall('.//synset'):
                if synset.tag == 'SYNSET':
                    continue
                total_synsets += 1

                synset_id = synset.get('id') or synset.get('ili')
                words = []

                for lemma in synset.findall('.//lemma'):
                    w = lemma.get('writtenForm') or lemma.text
                    if w:
                        words.append(w.strip())

                if synset_id and words:
                    pwn_id = parse_pwn_id(synset_id)
                    if pwn_id:
                        if pwn_id in synset_map:
                            for w in words:
                                if w not in synset_map[pwn_id]:
                                    synset_map[pwn_id].append(w)
                        else:
                            synset_map[pwn_id] = words
                        mapped += 1
                    else:
                        skipped += 1

        except ET.ParseError as e:
            log(f"  XML parse error: {e}")
            parse_errors += 1
        except Exception as e:
            log(f"  ERROR: {type(e).__name__}: {e}")
            parse_errors += 1

    log("")
    log(f"Total synsets found: {total_synsets:,}")
    log(f"Mapped to PWN: {mapped:,}")
    log(f"Skipped (no PWN ID): {skipped:,}")
    log(f"Parse errors: {parse_errors}")
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
    log(f"Total Turkish words: {total_words:,}")
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
            log(f"KeNet synsets: {len(synset_map):,}")
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
