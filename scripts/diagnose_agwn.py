#!/usr/bin/env python3
"""Diagnostic script for Ancient Greek WordNet data sources."""

import os
import json
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

print("=" * 70)
print("DIAGNOSE ANCIENT GREEK WORDNET DATA")
print("=" * 70)
print(f"Git HEAD: {os.popen('git rev-parse HEAD').read().strip()}")
print(f"Start: {datetime.now().isoformat()}")
print()

# STEP 1: Check downloaded files
print("=" * 70)
print("STEP 1: CHECK DOWNLOADED FILES IN /mnt/pgdata/morphlex/data/agwn/")
print("=" * 70)

agwn_dir = Path("/mnt/pgdata/morphlex/data/agwn")
if not agwn_dir.exists():
    print(f"Directory does not exist: {agwn_dir}")
else:
    files = list(agwn_dir.iterdir())
    if not files:
        print("Directory is empty")
    else:
        for f in sorted(files):
            size = f.stat().st_size
            print(f"\n--- {f.name} ({size:,} bytes) ---")
            try:
                content = f.read_text(encoding='utf-8', errors='replace')
                lines = content.split('\n')

                # Check if JSON
                if f.suffix == '.json' or content.strip().startswith('{') or content.strip().startswith('['):
                    try:
                        data = json.loads(content)
                        print(f"JSON structure: {type(data).__name__}")
                        if isinstance(data, dict):
                            print(f"Keys: {list(data.keys())[:10]}")
                            for k in list(data.keys())[:2]:
                                print(f"  [{k}]: {type(data[k]).__name__} = {str(data[k])[:200]}")
                        elif isinstance(data, list):
                            print(f"List length: {len(data)}")
                            for i, item in enumerate(data[:2]):
                                print(f"  [{i}]: {str(item)[:200]}")
                    except json.JSONDecodeError as e:
                        print(f"JSON parse error: {e}")
                        print("First 50 lines:")
                        for line in lines[:50]:
                            print(line)
                else:
                    print(f"First 50 lines:")
                    for line in lines[:50]:
                        print(line)
            except Exception as e:
                print(f"Error reading file: {e}")

# STEP 2: Try Harvard API
print("\n" + "=" * 70)
print("STEP 2: TRY HARVARD GREEK WORDNET API")
print("=" * 70)

endpoints = [
    "/api/synsets",
    "/api/lemmas",
    "/api/synsets?offset=00001740&pos=n",
    "/api/lemmas/%CE%BB%CF%8C%CE%B3%CE%BF%CF%82/n/synsets",  # URL-encoded λόγος
]

base_url = "https://greekwordnet.chs.harvard.edu"

for endpoint in endpoints:
    url = base_url + endpoint
    print(f"\n--- {endpoint} ---")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode('utf-8')
            print(f"Status: {resp.status}")
            print(f"Content-Type: {resp.headers.get('Content-Type')}")
            print(f"Length: {len(data)} bytes")
            print(f"First 500 chars: {data[:500]}")

            # Try to parse as JSON
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    print(f"JSON keys: {list(parsed.keys())[:10]}")
                elif isinstance(parsed, list):
                    print(f"JSON list length: {len(parsed)}")
            except:
                pass
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

# STEP 3: Try wn Python package
print("\n" + "=" * 70)
print("STEP 3: TRY WN PYTHON PACKAGE")
print("=" * 70)

try:
    import subprocess
    subprocess.run(['pip', 'install', 'wn'], capture_output=True)

    import wn

    # List available downloads
    print("\nSearching for Ancient Greek wordnets...")

    # Try to download and list what's available
    try:
        available = wn.download('ewn:2020', progress=False)
    except:
        pass

    # Check what lexicons are available
    print("\nInstalled lexicons:")
    for lex in wn.lexicons():
        print(f"  {lex.id()} - {lex.label()} ({lex.language()})")

    # Try specific Ancient Greek downloads
    grc_attempts = [
        'omw-grc:1.4',
        'grc',
        'omw:grc',
        'agwn',
        'ancient-greek',
    ]

    print("\nTrying Ancient Greek downloads:")
    for attempt in grc_attempts:
        try:
            print(f"  wn.download('{attempt}')...", end=" ")
            wn.download(attempt, progress=False)
            print("SUCCESS")
        except Exception as e:
            print(f"FAILED: {e}")

    # List all lexicons after attempts
    print("\nAll installed lexicons after attempts:")
    for lex in wn.lexicons():
        lang = lex.language()
        if 'gr' in lang.lower() or 'grc' in lang.lower() or 'el' in lang.lower():
            print(f"  * {lex.id()} - {lex.label()} ({lang})")
        else:
            print(f"    {lex.id()} - {lex.label()} ({lang})")

except ImportError as e:
    print(f"Could not import wn: {e}")
except Exception as e:
    print(f"Error with wn package: {type(e).__name__}: {e}")

# STEP 4: Try CLARIN-IT with ?sequence=1
print("\n" + "=" * 70)
print("STEP 4: TRY CLARIN-IT WITH ?sequence=1")
print("=" * 70)

clarin_urls = [
    "https://dspace-clarin-it.ilc.cnr.it/repository/xmlui/bitstream/handle/20.500.11752/ILC-56/wn-data-grc.tab?sequence=1",
    "https://dspace-clarin-it.ilc.cnr.it/repository/xmlui/bitstream/handle/20.500.11752/ILC-56/agwn.tsv?sequence=1",
    "https://dspace-clarin-it.ilc.cnr.it/repository/xmlui/bitstream/handle/20.500.11752/ILC-56/wn-data-grc.tab?sequence=2",
    "https://dspace-clarin-it.ilc.cnr.it/repository/xmlui/bitstream/handle/20.500.11752/ILC-56/wn-data-grc.tab?sequence=3",
]

for url in clarin_urls:
    short_url = url.split('/')[-1]
    print(f"\n--- {short_url} ---")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode('utf-8', errors='replace')
            print(f"Status: {resp.status}")
            print(f"Length: {len(data)} bytes")
            print(f"First 500 chars:\n{data[:500]}")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

# Also try the landing page to see what files are actually available
print("\n--- Checking CLARIN-IT landing page ---")
landing_url = "https://dspace-clarin-it.ilc.cnr.it/repository/xmlui/handle/20.500.11752/ILC-56"
try:
    req = urllib.request.Request(landing_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='replace')
        # Look for download links
        import re
        links = re.findall(r'href="([^"]*bitstream[^"]*)"', html)
        print(f"Found {len(links)} bitstream links:")
        for link in links[:10]:
            print(f"  {link}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")

print("\n" + "=" * 70)
print(f"End: {datetime.now().isoformat()}")
