#!/usr/bin/env python3
"""Download Princeton WordNet 2.1, verify IWN match, and build full bridge.

TASK: Download PWN 2.1 from Princeton, match IWN Sanskrit offsets, build
the bridge chain: IWN offset -> PWN 2.1 -> PWN 3.0 -> OEWN.

STEPS:
1. Download PWN 2.1 from Princeton
2. Parse data.noun, data.verb, data.adj, data.adv to extract all synset offsets
3. Test if sample IWN offsets match PWN 2.1
4. If not, try PWN 2.0
5. Download Princeton's official sense mapping files (2.1 to 3.0)
6. Build full bridge: IWN -> PWN 2.1 -> PWN 3.0 -> OEWN
7. Save as iwn_to_oewn_bridge.pkl

Zero error suppression. All output visible.
"""

import csv
import os
import pickle
import re
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path

BASE_DIR = Path("/mnt/pgdata/morphlex")
DATA_DIR = BASE_DIR / "data" / "open_wordnets"
IWN_TSV = DATA_DIR / "iwn-en" / "data" / "english-hindi-sanskrit-linked.tsv"
PWN_TO_OEWN_BRIDGE = DATA_DIR / "pwn30_to_oewn_map.pkl"
OUTPUT_BRIDGE = DATA_DIR / "iwn_to_oewn_bridge.pkl"

# Princeton URLs
PWN21_URL_PRIMARY = "https://wordnetcode.princeton.edu/2.1/WordNet-2.1.tar.gz"
PWN21_URL_FALLBACK = "https://wordnetcode.princeton.edu/wn2.1.dict.tar.gz"
PWN20_URL = "https://wordnetcode.princeton.edu/2.0/WordNet-2.0.tar.gz"
SNSMAP_URL = "https://wordnetcode.princeton.edu/3.0/WNsnsmap-3.0.tar.gz"


def log(msg):
    print(msg, flush=True)


def run_cmd(cmd, check=True):
    """Run shell command and return output."""
    log(f"  CMD: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"  STDERR: {result.stderr}")
        if check:
            raise RuntimeError(f"Command failed: {cmd}")
    return result.stdout, result.stderr, result.returncode


def download_file(url, dest_dir):
    """Download a file using wget."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    filename = url.split('/')[-1]
    dest_path = dest_dir / filename

    if dest_path.exists():
        log(f"  Already exists: {dest_path}")
        return dest_path

    stdout, stderr, rc = run_cmd(f"wget -q '{url}' -O '{dest_path}'", check=False)
    if rc != 0:
        log(f"  Download failed: {url}")
        if dest_path.exists():
            dest_path.unlink()
        return None

    log(f"  Downloaded: {dest_path} ({dest_path.stat().st_size:,} bytes)")
    return dest_path


def extract_tarball(tarball_path, dest_dir):
    """Extract a tar.gz file."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    log(f"  Extracting: {tarball_path}")
    with tarfile.open(tarball_path, 'r:gz') as tar:
        tar.extractall(dest_dir)
    log(f"  Extracted to: {dest_dir}")


def parse_pwn_data_file(data_file):
    """Parse a PWN data file and return set of synset offsets.

    PWN data files have lines like:
    00001740 03 n 01 entity 0 003 ~ 00001930 n 0000 ~ 00002137 n 0000 ~ 04424418 n 0000 | ...

    The synset_offset is the first 8-digit number.
    """
    offsets = set()
    data_file = Path(data_file)

    if not data_file.exists():
        log(f"  File not found: {data_file}")
        return offsets

    with open(data_file, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            # Skip copyright header lines (start with space)
            if line.startswith('  '):
                continue

            # First field is the synset offset
            parts = line.split()
            if parts and parts[0].isdigit():
                offsets.add(parts[0])

    return offsets


def get_iwn_sample_offsets(tsv_file, count=20):
    """Get sample english_id values from IWN TSV file.

    Returns list of tuples: (raw_id, padded_id, pos_char, english_word)
    """
    samples = []
    seen = set()

    with open(tsv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        header = next(reader)

        # Columns: hindi_id, hindi_category_x, english_id, english_category_x, english_synset_words, ...
        for row in reader:
            if len(row) < 5:
                continue

            english_id = row[2].strip()
            pos_str = row[3].strip().upper()
            english_words = row[4].strip()

            if not english_id or not english_id.isdigit():
                continue

            # Zero-pad to 8 digits
            padded = english_id.zfill(8)

            # Convert POS
            if pos_str == 'NOUN':
                pos_char = 'n'
            elif pos_str == 'VERB':
                pos_char = 'v'
            elif pos_str == 'ADJECTIVE':
                pos_char = 'a'
            elif pos_str == 'ADVERB':
                pos_char = 'r'
            else:
                continue

            key = (padded, pos_char)
            if key in seen:
                continue
            seen.add(key)

            first_word = english_words.split(',')[0].strip() if english_words else 'unknown'
            samples.append((english_id, padded, pos_char, first_word))

            if len(samples) >= count:
                break

    return samples


def get_all_iwn_offsets(tsv_file):
    """Get ALL english_id values from IWN TSV file.

    Returns dict: {(padded_offset, pos_char): english_word, ...}
    """
    offsets = {}

    with open(tsv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        header = next(reader)

        for row in reader:
            if len(row) < 5:
                continue

            english_id = row[2].strip()
            pos_str = row[3].strip().upper()
            english_words = row[4].strip()

            if not english_id or not english_id.isdigit():
                continue

            padded = english_id.zfill(8)

            if pos_str == 'NOUN':
                pos_char = 'n'
            elif pos_str == 'VERB':
                pos_char = 'v'
            elif pos_str == 'ADJECTIVE':
                pos_char = 'a'
            elif pos_str == 'ADVERB':
                pos_char = 'r'
            else:
                continue

            first_word = english_words.split(',')[0].strip() if english_words else 'unknown'
            offsets[(padded, pos_char)] = first_word

    return offsets


def test_pwn_version(pwn_dict_dir, iwn_samples):
    """Test if IWN samples match a PWN version.

    Returns (match_count, total, details_list)
    """
    pwn_dict_dir = Path(pwn_dict_dir)

    # POS to data file mapping
    pos_files = {
        'n': 'data.noun',
        'v': 'data.verb',
        'a': 'data.adj',
        's': 'data.adj',  # Satellite adjectives also in data.adj
        'r': 'data.adv'
    }

    # Load all offsets per POS
    pos_offsets = {}
    for pos_char, filename in [('n', 'data.noun'), ('v', 'data.verb'), ('a', 'data.adj'), ('r', 'data.adv')]:
        data_file = pwn_dict_dir / filename
        if data_file.exists():
            pos_offsets[pos_char] = parse_pwn_data_file(data_file)
            log(f"  Loaded {len(pos_offsets[pos_char]):,} offsets from {filename}")

    # Test samples
    matches = 0
    details = []

    for raw_id, padded, pos_char, word in iwn_samples:
        offsets = pos_offsets.get(pos_char, set())

        # Also try satellite adjective set for adjectives
        if pos_char == 'a' or pos_char == 's':
            offsets = pos_offsets.get('a', set())

        matched = padded in offsets
        if matched:
            matches += 1

        details.append((raw_id, padded, pos_char, word, matched))

    return matches, len(iwn_samples), details


def parse_snsmap_file(map_file):
    """Parse Princeton sense mapping file.

    Format: old_offset%pos new_offset%pos
    Example: 00001740%1 00001740%1

    Returns dict: {(old_offset, pos_char): (new_offset, pos_char), ...}
    """
    mapping = {}
    map_file = Path(map_file)

    if not map_file.exists():
        log(f"  File not found: {map_file}")
        return mapping

    # POS number to char
    pos_num_to_char = {'1': 'n', '2': 'v', '3': 'a', '4': 'r', '5': 's'}

    with open(map_file, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            old_part = parts[0]
            new_part = parts[1]

            # Parse old_offset%pos
            if '%' in old_part:
                old_offset, old_pos_num = old_part.split('%')
                old_pos = pos_num_to_char.get(old_pos_num, 'n')
            else:
                continue

            # Parse new_offset%pos
            if '%' in new_part:
                new_offset, new_pos_num = new_part.split('%')
                new_pos = pos_num_to_char.get(new_pos_num, 'n')
            else:
                continue

            # Store mapping
            mapping[(old_offset.zfill(8), old_pos)] = (new_offset.zfill(8), new_pos)

    return mapping


def build_pwn21_to_30_mapping(snsmap_dir):
    """Build complete PWN 2.1 -> 3.0 mapping from Princeton files.

    Uses both .mono (monosemous) and .poly (polysemous) files for all POS.
    Returns dict: {pwn21_synset_id: pwn30_synset_id, ...}
    """
    mapping = {}
    snsmap_dir = Path(snsmap_dir)

    # Files to process
    map_files = [
        '2.1to3.0/noun.mono',
        '2.1to3.0/noun.poly',
        '2.1to3.0/verb.mono',
        '2.1to3.0/verb.poly',
        '2.1to3.0/adj.mono',
        '2.1to3.0/adj.poly',
        '2.1to3.0/adv.mono',
        '2.1to3.0/adv.poly',
    ]

    # POS based on filename
    def get_pos(filename):
        if 'noun' in filename:
            return 'n'
        elif 'verb' in filename:
            return 'v'
        elif 'adj' in filename:
            return 'a'
        elif 'adv' in filename:
            return 'r'
        return 'n'

    for map_file in map_files:
        full_path = snsmap_dir / map_file
        if not full_path.exists():
            log(f"  Warning: {full_path} not found")
            continue

        pos = get_pos(map_file)
        count = 0

        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split()
                if len(parts) < 2:
                    continue

                old_offset = parts[0].zfill(8)
                new_offset = parts[1].zfill(8)

                # Create synset IDs
                pwn21_id = f"{old_offset}-{pos}"
                pwn30_id = f"{new_offset}-{pos}"

                mapping[pwn21_id] = pwn30_id
                count += 1

        log(f"  Loaded {count:,} mappings from {map_file}")

    return mapping


def main():
    log("=" * 70)
    log("DOWNLOAD PRINCETON WORDNET AND BUILD IWN -> OEWN BRIDGE")
    log("=" * 70)
    log("")

    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        log(f"Git HEAD: {git_head}")

    start_time = datetime.now()
    log(f"Start: {start_time.isoformat()}")
    log("")

    # Ensure directories exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # =====================================================================
    # STEP 1: Download PWN 2.1
    # =====================================================================
    log("=" * 70)
    log("STEP 1: DOWNLOAD PRINCETON WORDNET 2.1")
    log("=" * 70)
    log("")

    pwn21_dir = DATA_DIR / "WordNet-2.1"
    pwn21_dict_dir = pwn21_dir / "dict"

    if pwn21_dict_dir.exists() and (pwn21_dict_dir / "data.noun").exists():
        log(f"PWN 2.1 already extracted: {pwn21_dict_dir}")
    else:
        # Try primary URL
        log(f"Downloading from: {PWN21_URL_PRIMARY}")
        tarball = download_file(PWN21_URL_PRIMARY, DATA_DIR)

        if not tarball:
            # Try fallback URL
            log(f"Primary URL failed, trying fallback: {PWN21_URL_FALLBACK}")
            tarball = download_file(PWN21_URL_FALLBACK, DATA_DIR)

        if not tarball:
            log("FATAL: Could not download PWN 2.1")
            sys.exit(1)

        # Extract
        extract_tarball(tarball, DATA_DIR)

        # Check for dict directory (might be in different locations)
        if not pwn21_dict_dir.exists():
            # Try to find it
            for d in DATA_DIR.rglob('dict'):
                if (d / 'data.noun').exists():
                    pwn21_dict_dir = d
                    break

    log(f"PWN 2.1 dict directory: {pwn21_dict_dir}")

    # List files
    if pwn21_dict_dir.exists():
        log("Files in dict/:")
        for f in sorted(pwn21_dict_dir.iterdir()):
            log(f"  {f.name} ({f.stat().st_size:,} bytes)")
    log("")

    # =====================================================================
    # STEP 2: Get IWN sample offsets
    # =====================================================================
    log("=" * 70)
    log("STEP 2: GET IWN SAMPLE OFFSETS")
    log("=" * 70)
    log("")

    if not IWN_TSV.exists():
        log(f"FATAL: IWN TSV not found: {IWN_TSV}")
        sys.exit(1)

    iwn_samples = get_iwn_sample_offsets(IWN_TSV, count=20)
    log(f"Loaded {len(iwn_samples)} sample IWN offsets:")
    for raw_id, padded, pos_char, word in iwn_samples:
        log(f"  {raw_id:>10} -> {padded}-{pos_char} | {word}")
    log("")

    # =====================================================================
    # STEP 3: Test PWN 2.1 match
    # =====================================================================
    log("=" * 70)
    log("STEP 3: TEST IWN OFFSETS AGAINST PWN 2.1")
    log("=" * 70)
    log("")

    matches, total, details = test_pwn_version(pwn21_dict_dir, iwn_samples)
    log(f"Match rate: {matches}/{total} ({100*matches/total:.1f}%)")
    log("")
    log("Details:")
    for raw_id, padded, pos_char, word, matched in details:
        status = "MATCH" if matched else "NO MATCH"
        log(f"  {padded}-{pos_char} ({word}): {status}")
    log("")

    pwn_version = None
    pwn_dict_dir = None

    if matches >= 15:  # At least 75% match
        log("SUCCESS: IWN offsets match PWN 2.1!")
        pwn_version = "2.1"
        pwn_dict_dir = pwn21_dict_dir
    else:
        log("PWN 2.1 does not match. Trying PWN 2.0...")
        log("")

        # =====================================================================
        # STEP 4: Try PWN 2.0
        # =====================================================================
        log("=" * 70)
        log("STEP 4: DOWNLOAD AND TEST PWN 2.0")
        log("=" * 70)
        log("")

        pwn20_dir = DATA_DIR / "WordNet-2.0"
        pwn20_dict_dir = pwn20_dir / "dict"

        if pwn20_dict_dir.exists() and (pwn20_dict_dir / "data.noun").exists():
            log(f"PWN 2.0 already extracted: {pwn20_dict_dir}")
        else:
            log(f"Downloading from: {PWN20_URL}")
            tarball = download_file(PWN20_URL, DATA_DIR)

            if not tarball:
                log("WARNING: Could not download PWN 2.0")
            else:
                extract_tarball(tarball, DATA_DIR)

                if not pwn20_dict_dir.exists():
                    for d in DATA_DIR.rglob('dict'):
                        if (d / 'data.noun').exists():
                            pwn20_dict_dir = d
                            break

        if pwn20_dict_dir and pwn20_dict_dir.exists():
            matches20, total20, details20 = test_pwn_version(pwn20_dict_dir, iwn_samples)
            log(f"Match rate: {matches20}/{total20} ({100*matches20/total20:.1f}%)")
            log("")

            if matches20 >= 15:
                log("SUCCESS: IWN offsets match PWN 2.0!")
                pwn_version = "2.0"
                pwn_dict_dir = pwn20_dict_dir
            else:
                log("PWN 2.0 also does not match.")

    if not pwn_version:
        log("FATAL: Could not find matching PWN version for IWN offsets")
        sys.exit(1)

    log(f"")
    log(f"CONFIRMED: IWN uses PWN {pwn_version}")
    log("")

    # =====================================================================
    # STEP 5: Download Princeton sense mapping files
    # =====================================================================
    log("=" * 70)
    log("STEP 5: DOWNLOAD PRINCETON SENSE MAPPING FILES")
    log("=" * 70)
    log("")

    snsmap_dir = DATA_DIR / "WNsnsmap-3.0"

    if snsmap_dir.exists() and (snsmap_dir / "2.1to3.0").exists():
        log(f"Sense maps already extracted: {snsmap_dir}")
    else:
        log(f"Downloading from: {SNSMAP_URL}")
        tarball = download_file(SNSMAP_URL, DATA_DIR)

        if not tarball:
            log("FATAL: Could not download sense mapping files")
            sys.exit(1)

        extract_tarball(tarball, DATA_DIR)

    # List mapping files
    mapping_dir = snsmap_dir / "2.1to3.0"
    if mapping_dir.exists():
        log(f"Mapping files in {mapping_dir}:")
        for f in sorted(mapping_dir.iterdir()):
            log(f"  {f.name} ({f.stat().st_size:,} bytes)")
    log("")

    # =====================================================================
    # STEP 6: Build PWN 2.1 -> PWN 3.0 mapping
    # =====================================================================
    log("=" * 70)
    log("STEP 6: BUILD PWN 2.1 -> PWN 3.0 MAPPING")
    log("=" * 70)
    log("")

    pwn21_to_30 = build_pwn21_to_30_mapping(snsmap_dir)
    log(f"Total PWN 2.1 -> 3.0 mappings: {len(pwn21_to_30):,}")
    log("")

    # Show samples
    log("5 sample mappings:")
    for old_id, new_id in list(pwn21_to_30.items())[:5]:
        log(f"  {old_id} -> {new_id}")
    log("")

    # =====================================================================
    # STEP 7: Load PWN 3.0 -> OEWN bridge
    # =====================================================================
    log("=" * 70)
    log("STEP 7: LOAD PWN 3.0 -> OEWN BRIDGE")
    log("=" * 70)
    log("")

    if not PWN_TO_OEWN_BRIDGE.exists():
        log(f"FATAL: PWN 3.0 -> OEWN bridge not found: {PWN_TO_OEWN_BRIDGE}")
        sys.exit(1)

    with open(PWN_TO_OEWN_BRIDGE, 'rb') as f:
        pwn30_to_oewn = pickle.load(f)

    log(f"Loaded {len(pwn30_to_oewn):,} PWN 3.0 -> OEWN mappings")

    # Show samples
    log("5 sample mappings:")
    for pwn_id, oewn_id in list(pwn30_to_oewn.items())[:5]:
        log(f"  {pwn_id} -> {oewn_id}")
    log("")

    # =====================================================================
    # STEP 8: Build full IWN -> OEWN bridge
    # =====================================================================
    log("=" * 70)
    log("STEP 8: BUILD FULL IWN -> OEWN BRIDGE")
    log("=" * 70)
    log("")

    # Get all IWN offsets
    all_iwn = get_all_iwn_offsets(IWN_TSV)
    log(f"Total IWN synsets: {len(all_iwn):,}")
    log("")

    # Build bridge: IWN offset -> PWN 2.1 -> PWN 3.0 -> OEWN
    iwn_to_oewn = {}
    stats = {
        'direct_match': 0,
        'via_21_to_30': 0,
        'no_30_mapping': 0,
        'no_oewn_mapping': 0,
    }

    for (padded_offset, pos_char), word in all_iwn.items():
        iwn_id = f"{padded_offset}-{pos_char}"

        # IWN uses PWN 2.1 offsets, so we need 2.1 -> 3.0 -> OEWN
        pwn30_id = pwn21_to_30.get(iwn_id)

        if pwn30_id:
            stats['via_21_to_30'] += 1
            oewn_id = pwn30_to_oewn.get(pwn30_id)

            if oewn_id:
                iwn_to_oewn[iwn_id] = oewn_id
            else:
                stats['no_oewn_mapping'] += 1
        else:
            # No 2.1->3.0 mapping, try direct 3.0->OEWN (in case some IDs are already 3.0)
            oewn_id = pwn30_to_oewn.get(iwn_id)
            if oewn_id:
                iwn_to_oewn[iwn_id] = oewn_id
                stats['direct_match'] += 1
            else:
                stats['no_30_mapping'] += 1

    log(f"Bridge statistics:")
    log(f"  Total IWN synsets: {len(all_iwn):,}")
    log(f"  Mapped via 2.1->3.0->OEWN: {stats['via_21_to_30']:,}")
    log(f"  Direct matches (already 3.0): {stats['direct_match']:,}")
    log(f"  No 2.1->3.0 mapping: {stats['no_30_mapping']:,}")
    log(f"  No 3.0->OEWN mapping: {stats['no_oewn_mapping']:,}")
    log(f"  TOTAL BRIDGED: {len(iwn_to_oewn):,}")
    log(f"  Coverage: {100*len(iwn_to_oewn)/len(all_iwn):.1f}%")
    log("")

    # Show sample bridges
    log("10 sample bridges:")
    for iwn_id, oewn_id in list(iwn_to_oewn.items())[:10]:
        word = all_iwn.get((iwn_id.split('-')[0], iwn_id.split('-')[1]), 'unknown')
        log(f"  IWN:{iwn_id} -> OEWN:{oewn_id} ({word})")
    log("")

    # =====================================================================
    # STEP 9: Save bridge
    # =====================================================================
    log("=" * 70)
    log("STEP 9: SAVE IWN -> OEWN BRIDGE")
    log("=" * 70)
    log("")

    with open(OUTPUT_BRIDGE, 'wb') as f:
        pickle.dump(iwn_to_oewn, f, protocol=pickle.HIGHEST_PROTOCOL)

    log(f"Saved: {OUTPUT_BRIDGE}")
    log(f"Size: {OUTPUT_BRIDGE.stat().st_size:,} bytes")
    log("")

    # =====================================================================
    # STEP 10: Test sample offsets through bridge
    # =====================================================================
    log("=" * 70)
    log("STEP 10: TEST SAMPLE OFFSETS THROUGH BRIDGE")
    log("=" * 70)
    log("")

    test_offsets = [
        ('01796323', 'a', 'unborn'),
        ('00532338', 'n', 'folk_dancing'),
        ('00975187', 'a', 'experienced'),
        ('00576770', 'n', 'welfare_work'),
        ('00580235', 'n', 'public_service'),
    ]

    for offset, pos, word in test_offsets:
        iwn_id = f"{offset}-{pos}"
        oewn_id = iwn_to_oewn.get(iwn_id, "NOT FOUND")
        log(f"  {word}: IWN:{iwn_id} -> OEWN:{oewn_id}")
    log("")

    # =====================================================================
    # SUMMARY
    # =====================================================================
    log("=" * 70)
    log("SUMMARY")
    log("=" * 70)
    log("")
    log(f"IWN uses: Princeton WordNet {pwn_version}")
    log(f"Bridge chain: IWN (PWN 2.1) -> PWN 3.0 -> OEWN")
    log(f"Total bridged synsets: {len(iwn_to_oewn):,}")
    log(f"Bridge file: {OUTPUT_BRIDGE}")
    log("")
    log(f"Duration: {datetime.now() - start_time}")
    log(f"End: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
