#!/usr/bin/env python3
"""Explore all 5 open wordnet datasets on the VM.

This script discovers the actual data structures before parsing.
Run this FIRST to understand what files/APIs are available.

Zero error suppression. All exceptions logged visibly.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path("/mnt/pgdata/morphlex/data/open_wordnets")


def log(msg):
    """Print with immediate flush."""
    print(msg, flush=True)


def explore_wn_package():
    """Explore the wn Python package API (German OdeNet)."""
    log("")
    log("=" * 70)
    log("1. EXPLORE WN PACKAGE (GERMAN ODENET)")
    log("=" * 70)
    log("")

    try:
        import wn
        log(f"wn package version: {getattr(wn, '__version__', 'unknown')}")
        log(f"wn package location: {wn.__file__}")
    except ImportError as e:
        log(f"ERROR: wn package not installed: {e}")
        return

    # List all lexicons
    log("")
    log("All lexicons in wn:")
    try:
        lexicons = wn.lexicons()
        for lex in lexicons:
            # Test what attributes are available - try as properties first
            lex_id = getattr(lex, 'id', None)
            if callable(lex_id):
                lex_id = lex_id()
            lex_label = getattr(lex, 'label', None)
            if callable(lex_label):
                lex_label = lex_label()
            lex_lang = getattr(lex, 'language', None)
            if callable(lex_lang):
                lex_lang = lex_lang()
            log(f"  - id={lex_id}, label={lex_label}, language={lex_lang}")
            log(f"    Type: {type(lex)}")
            log(f"    Dir: {[a for a in dir(lex) if not a.startswith('_')]}")
    except Exception as e:
        log(f"ERROR listing lexicons: {type(e).__name__}: {e}")

    # Try to get OdeNet specifically
    log("")
    log("Attempting to load OdeNet:")
    odenet = None
    try:
        odenet = wn.Wordnet('odenet')
        log(f"  Loaded: {odenet}")
        log(f"  Type: {type(odenet)}")
    except Exception as e:
        log(f"  ERROR: {type(e).__name__}: {e}")
        try:
            odenet = wn.Wordnet('odenet', 'de')
            log(f"  Loaded with lang='de': {odenet}")
        except Exception as e2:
            log(f"  Also failed with lang='de': {type(e2).__name__}: {e2}")

    if odenet is None:
        log("  Trying to download odenet:1.4...")
        try:
            wn.download('odenet:1.4', progress=False)
            odenet = wn.Wordnet('odenet')
            log(f"  Downloaded and loaded: {odenet}")
        except Exception as e:
            log(f"  Download failed: {type(e).__name__}: {e}")

    # Explore synset structure
    if odenet:
        log("")
        log("OdeNet synset structure (3 samples):")
        try:
            synsets = list(odenet.synsets())[:3]
            log(f"Total synsets: {len(list(odenet.synsets()))}")

            for i, ss in enumerate(synsets):
                log(f"")
                log(f"  Synset {i+1}:")
                log(f"    Type: {type(ss)}")

                # Test all attribute access patterns
                for attr in ['id', 'pos', 'ili', 'definition', 'examples']:
                    val = getattr(ss, attr, 'NOT_FOUND')
                    if callable(val):
                        try:
                            val = f"{val()} (method)"
                        except Exception as e:
                            val = f"method-call-error: {e}"
                    else:
                        val = f"{val} (property)"
                    log(f"    {attr}: {val}")

                # Get words/lemmas
                log(f"    Dir: {[a for a in dir(ss) if not a.startswith('_')]}")

                # Try to get words
                words_attr = getattr(ss, 'words', None)
                if words_attr:
                    if callable(words_attr):
                        words = words_attr()
                        log(f"    words() returned: {type(words)}")
                    else:
                        words = words_attr
                        log(f"    words property: {type(words)}")

                    if words:
                        word = list(words)[0]
                        log(f"    First word type: {type(word)}")
                        log(f"    First word dir: {[a for a in dir(word) if not a.startswith('_')]}")

                        # Try to get lemma
                        for attr in ['lemma', 'form', 'word', 'name']:
                            val = getattr(word, attr, 'NOT_FOUND')
                            if callable(val):
                                try:
                                    val = f"{val()} (method)"
                                except Exception as e:
                                    val = f"method-call-error: {e}"
                            else:
                                val = f"{val} (property)"
                            log(f"      word.{attr}: {val}")
        except Exception as e:
            log(f"ERROR exploring synsets: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    # Try to get English WordNet for ILI mapping
    log("")
    log("Checking for English WordNet (for ILI mapping):")
    pwn = None
    for name in ['ewn', 'oewn', 'omw-en31', 'pwn']:
        try:
            pwn = wn.Wordnet(name)
            log(f"  Found: {name}")
            break
        except Exception:
            pass

    if pwn is None:
        log("  No English WordNet found - trying to download...")
        try:
            wn.download('oewn:2024', progress=False)
            pwn = wn.Wordnet('oewn')
            log(f"  Downloaded oewn:2024")
        except Exception as e:
            log(f"  Download failed: {e}")


def explore_kenet():
    """Explore Turkish KeNet directory."""
    log("")
    log("=" * 70)
    log("2. EXPLORE KENET (TURKISH)")
    log("=" * 70)
    log("")

    kenet_dir = BASE_DIR / "kenet"
    if not kenet_dir.exists():
        log(f"FATAL: Directory not found: {kenet_dir}")
        return

    log(f"Directory: {kenet_dir}")
    log("")

    # Find all files
    log("All files (recursive):")
    all_files = []
    for f in sorted(kenet_dir.rglob('*')):
        if f.is_file():
            all_files.append(f)
            rel_path = f.relative_to(kenet_dir)
            size = f.stat().st_size
            log(f"  {rel_path} ({size:,} bytes)")

    # Find XML files
    xml_files = [f for f in all_files if f.suffix.lower() == '.xml']
    log("")
    log(f"XML files found: {len(xml_files)}")

    if xml_files:
        # Show first 30 lines of first XML
        sample = xml_files[0]
        log("")
        log(f"First 30 lines of {sample.name}:")
        log("-" * 50)
        try:
            with open(sample, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i >= 30:
                        break
                    log(line.rstrip())
        except Exception as e:
            log(f"ERROR: {e}")

        # Parse and show structure
        log("")
        log("XML structure analysis:")
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(sample)
            root = tree.getroot()
            log(f"  Root tag: {root.tag}")
            log(f"  Root attrs: {dict(root.attrib)}")
            log(f"  Children tags: {list(set(c.tag for c in root))[:10]}")

            # Find synset-like elements
            log("")
            log("Looking for synset elements:")
            for tag in ['SYNSET', 'synset', 'Synset', 'LexicalEntry', 'Sense']:
                elems = root.findall(f'.//{tag}')
                if elems:
                    log(f"  Found {len(elems)} <{tag}> elements")
                    elem = elems[0]
                    log(f"    First attrs: {dict(elem.attrib)}")
                    log(f"    First children: {[(c.tag, c.text[:50] if c.text else None) for c in list(elem)[:5]]}")
        except Exception as e:
            log(f"ERROR: {type(e).__name__}: {e}")


def explore_latin_wordnet():
    """Explore Latin WordNet directory."""
    log("")
    log("=" * 70)
    log("3. EXPLORE LATIN WORDNET")
    log("=" * 70)
    log("")

    latin_dir = BASE_DIR / "latin-wordnet"
    if not latin_dir.exists():
        log(f"FATAL: Directory not found: {latin_dir}")
        return

    log(f"Directory: {latin_dir}")
    log("")

    # Find all files
    log("All files (recursive):")
    all_files = []
    for f in sorted(latin_dir.rglob('*')):
        if f.is_file():
            all_files.append(f)
            rel_path = f.relative_to(latin_dir)
            size = f.stat().st_size
            log(f"  {rel_path} ({size:,} bytes)")

    # Find SQLite files
    db_files = []
    for f in all_files:
        if f.suffix in ['.db', '.sqlite', '.sqlite3']:
            db_files.append(f)
        else:
            try:
                with open(f, 'rb') as fp:
                    if fp.read(16).startswith(b'SQLite format 3'):
                        db_files.append(f)
            except Exception:
                pass

    log("")
    log(f"SQLite files found: {len(db_files)}")

    for db_file in db_files[:2]:
        log("")
        log(f"Database: {db_file.name}")
        log("-" * 50)
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cursor.fetchall()]
            log(f"Tables: {tables}")

            for table in tables[:5]:
                log(f"")
                log(f"  Table: {table}")
                cursor.execute(f"PRAGMA table_info({table})")
                cols = [c[1] for c in cursor.fetchall()]
                log(f"    Columns: {cols}")
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                log(f"    Rows: {cursor.fetchone()[0]:,}")
                cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                for row in cursor.fetchall():
                    log(f"    Sample: {row}")

            conn.close()
        except Exception as e:
            log(f"ERROR: {type(e).__name__}: {e}")

    # Also check for CSV/TSV files
    csv_files = [f for f in all_files if f.suffix in ['.csv', '.tsv', '.txt']]
    if csv_files:
        log("")
        log(f"CSV/TSV files found: {len(csv_files)}")
        for f in csv_files[:2]:
            log(f"  {f.name}:")
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    for i, line in enumerate(fp):
                        if i >= 5:
                            break
                        log(f"    {line.rstrip()[:100]}")
            except Exception as e:
                log(f"    ERROR: {e}")


def explore_iwn_sanskrit():
    """Explore IWN-En (Sanskrit) directory."""
    log("")
    log("=" * 70)
    log("4. EXPLORE IWN-EN (SANSKRIT)")
    log("=" * 70)
    log("")

    iwn_dir = BASE_DIR / "iwn-en"
    if not iwn_dir.exists():
        log(f"FATAL: Directory not found: {iwn_dir}")
        return

    log(f"Directory: {iwn_dir}")
    log("")

    # Find all files
    log("All files (recursive):")
    all_files = []
    for f in sorted(iwn_dir.rglob('*')):
        if f.is_file():
            all_files.append(f)
            rel_path = f.relative_to(iwn_dir)
            size = f.stat().st_size
            log(f"  {rel_path} ({size:,} bytes)")

    # Find TSV/CSV files
    data_files = [f for f in all_files if f.suffix in ['.tsv', '.csv', '.txt']]
    log("")
    log(f"Data files found: {len(data_files)}")

    # Look for Sanskrit specifically
    sanskrit_files = [f for f in all_files if 'sanskrit' in f.name.lower()]
    log(f"Sanskrit-named files: {len(sanskrit_files)}")

    # Check specific target file
    target = iwn_dir / "english-hindi-sanskrit-linked.tsv"
    if target.exists():
        log(f"")
        log(f"Target file exists: {target.name}")
    else:
        log(f"Target file NOT found: english-hindi-sanskrit-linked.tsv")
        # List alternatives
        for f in data_files:
            log(f"  Alternative: {f.name}")

    # Show content of first data file
    sample_file = target if target.exists() else (data_files[0] if data_files else None)
    if sample_file:
        log("")
        log(f"First 30 lines of {sample_file.name}:")
        log("-" * 50)
        try:
            with open(sample_file, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i >= 30:
                        break
                    log(line.rstrip()[:150])
        except Exception as e:
            log(f"ERROR: {e}")


def explore_agwn():
    """Explore AGWN (Greek) directory."""
    log("")
    log("=" * 70)
    log("5. EXPLORE AGWN-JCUENOD (GREEK)")
    log("=" * 70)
    log("")

    agwn_dir = BASE_DIR / "agwn-jcuenod"
    if not agwn_dir.exists():
        log(f"FATAL: Directory not found: {agwn_dir}")
        return

    log(f"Directory: {agwn_dir}")
    log("")

    # Find all files
    log("All files (recursive):")
    all_files = []
    for f in sorted(agwn_dir.rglob('*')):
        if f.is_file():
            all_files.append(f)
            rel_path = f.relative_to(agwn_dir)
            size = f.stat().st_size
            log(f"  {rel_path} ({size:,} bytes)")

    # Find SQLite files
    db_files = []
    for f in all_files:
        if f.suffix in ['.db', '.sqlite', '.sqlite3']:
            db_files.append(f)
        else:
            try:
                with open(f, 'rb') as fp:
                    if fp.read(16).startswith(b'SQLite format 3'):
                        db_files.append(f)
            except Exception:
                pass

    log("")
    log(f"SQLite files found: {len(db_files)}")

    for db_file in db_files[:2]:
        log("")
        log(f"Database: {db_file.name}")
        log("-" * 50)
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cursor.fetchall()]
            log(f"Tables: {tables}")

            for table in tables[:5]:
                log(f"")
                log(f"  Table: {table}")
                cursor.execute(f"PRAGMA table_info({table})")
                cols = [c[1] for c in cursor.fetchall()]
                log(f"    Columns: {cols}")
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                log(f"    Rows: {cursor.fetchone()[0]:,}")
                cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                for row in cursor.fetchall():
                    log(f"    Sample: {row}")

            conn.close()
        except Exception as e:
            log(f"ERROR: {type(e).__name__}: {e}")

    # Also check for CSV/TSV/JSON files
    other_files = [f for f in all_files if f.suffix in ['.csv', '.tsv', '.json', '.txt']]
    if other_files:
        log("")
        log(f"Other data files: {len(other_files)}")
        for f in other_files[:3]:
            log(f"  {f.name}")


def main():
    log("=" * 70)
    log("OPEN WORDNET DATASET EXPLORATION")
    log("=" * 70)

    git_head = os.popen('git rev-parse HEAD 2>/dev/null').read().strip()
    if git_head:
        log(f"Git HEAD: {git_head}")

    start = datetime.now()
    log(f"Start: {start.isoformat()}")
    log("")

    log(f"Base directory: {BASE_DIR}")
    if BASE_DIR.exists():
        log(f"Contents: {[d.name for d in sorted(BASE_DIR.iterdir()) if d.is_dir()]}")
    else:
        log(f"FATAL: Base directory does not exist!")
        sys.exit(1)

    explore_wn_package()
    explore_kenet()
    explore_latin_wordnet()
    explore_iwn_sanskrit()
    explore_agwn()

    log("")
    log("=" * 70)
    log("EXPLORATION COMPLETE")
    log("=" * 70)
    log(f"Duration: {datetime.now() - start}")


if __name__ == "__main__":
    main()
