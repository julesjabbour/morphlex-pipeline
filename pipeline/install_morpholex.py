#!/usr/bin/env python3
"""
Install MorphoLex for English and re-analyze English rows.

STEP 1: Download MorphoLex xlsx to /mnt/pgdata/morphlex/MorphoLex-en/
STEP 2: Test the English adapter with 5 words
STEP 3: Re-analyze all English rows in master_table.csv
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# Configuration
MORPHOLEX_URL = "https://github.com/hugomailhot/MorphoLex-en/raw/master/MorphoLEX_en.xlsx"
MORPHOLEX_DIR = Path("/mnt/pgdata/morphlex/MorphoLex-en")
MORPHOLEX_FILE = MORPHOLEX_DIR / "MorphoLEX_en.xlsx"
MASTER_TABLE = Path("/mnt/pgdata/morphlex/data/master_table.csv")

def step1_download_morpholex():
    """Download MorphoLex xlsx file."""
    print("=== STEP 1: DOWNLOAD MORPHOLEX ===")

    # Create directory
    MORPHOLEX_DIR.mkdir(parents=True, exist_ok=True)

    # Download with curl, redirect progress to /dev/null
    cmd = [
        "curl", "-L", "-s", "-o", str(MORPHOLEX_FILE), MORPHOLEX_URL
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERROR: Download failed: {result.stderr}")
        return False

    if not MORPHOLEX_FILE.exists():
        print(f"ERROR: File not created at {MORPHOLEX_FILE}")
        return False

    file_size = MORPHOLEX_FILE.stat().st_size
    print(f"Downloaded: {MORPHOLEX_FILE}")
    print(f"Size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")

    if file_size < 1000000:  # Less than 1MB is suspicious
        print(f"WARNING: File size seems too small")
        return False

    return True


def step2_test_adapter():
    """Test the English adapter with 5 words."""
    print("\n=== STEP 2: TEST ENGLISH ADAPTER ===")

    # Add project to path
    sys.path.insert(0, '/mnt/pgdata/morphlex')

    # Force reload to pick up new MorphoLex data
    from analyzers import english
    english._morpholex_cache = None  # Clear cache to force reload

    test_words = ['unhappiness', 'rethinking', 'uncomfortable', 'displacement', 'disagreement']

    results = []
    using_morpholex = False

    for word in test_words:
        analysis = english.analyze_english(word)
        if analysis:
            result = analysis[0]
            results.append({
                'word': word,
                'root': result.get('root'),
                'morph_type': result.get('morph_type'),
                'prefixes': result.get('morphological_features', {}).get('prefixes', []),
                'suffixes': result.get('morphological_features', {}).get('suffixes', []),
                'source': result.get('source_tool')
            })
            # Check if we're using MorphoLex (not just spaCy fallback)
            if 'morpholex' in result.get('source_tool', ''):
                using_morpholex = True

    # Print results
    print(f"\nTest Results ({len(results)} words):")
    for r in results:
        prefixes = ','.join(r['prefixes']) if r['prefixes'] else '-'
        suffixes = ','.join(r['suffixes']) if r['suffixes'] else '-'
        print(f"  {r['word']}: root={r['root']}, type={r['morph_type']}, prefix=[{prefixes}], suffix=[{suffixes}], source={r['source']}")

    if not using_morpholex:
        print("\nERROR: Adapter still using spaCy fallback!")
        print(f"Looking for MorphoLex at: {MORPHOLEX_DIR}")
        if MORPHOLEX_DIR.exists():
            files = list(MORPHOLEX_DIR.glob('*'))
            print(f"Files in directory: {[f.name for f in files]}")
        else:
            print("Directory does not exist!")
        return False

    print("\nSUCCESS: English adapter is using MorphoLex!")
    return True


def step3_reanalyze_english():
    """Re-analyze all English rows in master_table.csv."""
    print("\n=== STEP 3: RE-ANALYZE ENGLISH ROWS ===")

    import pandas as pd
    sys.path.insert(0, '/mnt/pgdata/morphlex')
    from analyzers import english

    # Ensure cache is loaded
    english._morpholex_cache = None

    print(f"Loading {MASTER_TABLE}...")
    df = pd.read_csv(MASTER_TABLE, dtype=str, keep_default_na=False)
    print(f"Loaded {len(df):,} rows")

    # Filter English rows
    en_mask = df['language'] == 'en'
    en_count = en_mask.sum()
    print(f"English rows: {en_count:,}")

    # Store before values for comparison
    before_samples = df[en_mask].head(20)[['word', 'root', 'morph_type', 'derivation_info', 'compound_components']].copy()

    # Track changes
    root_changed = 0
    type_changed = 0

    # Re-analyze each English row
    print("\nRe-analyzing...")

    for idx in df[en_mask].index:
        word = df.at[idx, 'word']
        old_root = df.at[idx, 'root']
        old_type = df.at[idx, 'morph_type']

        # Get new analysis
        results = english.analyze_english(word)
        if results:
            result = results[0]
            new_root = result.get('root') or word
            new_type = result.get('morph_type', 'UNKNOWN')

            # Get derivation info
            prefixes = result.get('morphological_features', {}).get('prefixes', [])
            suffixes = result.get('morphological_features', {}).get('suffixes', [])
            components = result.get('compound_components')

            # Build derivation_info from prefixes/suffixes
            deriv_parts = []
            if prefixes:
                deriv_parts.extend([f"prefix:{p}" for p in prefixes])
            if suffixes:
                deriv_parts.extend([f"suffix:{s}" for s in suffixes])
            derivation_info = '|'.join(deriv_parts) if deriv_parts else ''

            # Build compound_components
            compound_str = '|'.join(components) if components else ''

            # Update row (preserve wiktextract_match!)
            df.at[idx, 'root'] = new_root
            df.at[idx, 'morph_type'] = new_type
            df.at[idx, 'derivation_info'] = derivation_info
            df.at[idx, 'compound_components'] = compound_str

            if new_root != old_root:
                root_changed += 1
            if new_type != old_type:
                type_changed += 1

    # Get after values
    after_samples = df[en_mask].head(20)[['word', 'root', 'morph_type', 'derivation_info', 'compound_components']].copy()

    # Save
    print(f"\nSaving to {MASTER_TABLE}...")
    df.to_csv(MASTER_TABLE, index=False)
    print("Saved.")

    # Print summary
    print(f"\n=== RESULTS ===")
    print(f"English rows re-analyzed: {en_count:,}")
    print(f"Rows with root changed: {root_changed:,}")
    print(f"Rows with morph_type changed: {type_changed:,}")

    # New morph_type distribution for English
    en_df = df[en_mask]
    type_dist = en_df['morph_type'].value_counts()
    print(f"\nNew English morph_type distribution:")
    for t, c in type_dist.items():
        pct = 100 * c / len(en_df)
        print(f"  {t}: {c:,} ({pct:.1f}%)")

    # Print 10 before/after samples
    print(f"\n=== 10 SAMPLE BEFORE/AFTER ROWS ===")
    for i in range(min(10, len(before_samples))):
        b = before_samples.iloc[i]
        a = after_samples.iloc[i]
        print(f"[{i+1}] word: '{b['word']}'")
        print(f"    root: '{b['root']}' -> '{a['root']}'")
        print(f"    morph_type: '{b['morph_type']}' -> '{a['morph_type']}'")
        print(f"    derivation_info: '{b['derivation_info']}' -> '{a['derivation_info']}'")

    return True


def main():
    print(f"=== INSTALL MORPHOLEX FOR ENGLISH ===")
    print(f"Git HEAD: {subprocess.getoutput('git rev-parse HEAD')}")
    print(f"Start: {datetime.now().isoformat()}")
    print()

    # Step 1: Download
    if not step1_download_morpholex():
        print("\nFAILED at Step 1: Download")
        return 1

    # Step 2: Test
    if not step2_test_adapter():
        print("\nFAILED at Step 2: Test adapter")
        return 1

    # Step 3: Re-analyze
    if not step3_reanalyze_english():
        print("\nFAILED at Step 3: Re-analyze")
        return 1

    print(f"\nEnd: {datetime.now().isoformat()}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
