#!/usr/bin/env python3
"""
Diagnostic: Sample entries with derivation/compound templates from Wiktextract dump.

Purpose: Show actual JSON structure BEFORE writing the full extraction script.
Samples 3 entries per language that contain affix/compound templates.

Target templates:
- Derivation: affix, af, prefix, suffix, confix, circumfix, infix
- Compound: compound, com

Output: Raw JSON structure for each sample so we can design the extraction parser.
"""
import gzip
import json
import sys
from collections import defaultdict
from datetime import datetime

DATA_FILE = '/mnt/pgdata/morphlex/data/raw-wiktextract-data.jsonl.gz'
TARGET_LANGS = {'en', 'ar', 'tr', 'de', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro'}
DERIVATION_TEMPLATES = {'affix', 'af', 'prefix', 'suffix', 'confix', 'circumfix', 'infix'}
COMPOUND_TEMPLATES = {'compound', 'com'}
MAX_SAMPLES = 3


def main():
    print(f"[{datetime.now().isoformat()}] Starting diagnostic scan")
    print(f"Input: {DATA_FILE}")
    print(f"Target languages: {sorted(TARGET_LANGS)}")
    print(f"Looking for templates: {sorted(DERIVATION_TEMPLATES | COMPOUND_TEMPLATES)}")
    print()

    samples = defaultdict(list)  # {lang: [entries]}
    line_count = 0

    try:
        with gzip.open(DATA_FILE, 'rt', encoding='utf-8') as f:
            for line in f:
                line_count += 1
                if line_count % 500000 == 0:
                    found = sum(len(v) for v in samples.values())
                    print(f"  Scanned {line_count:,} lines, found {found} samples...")

                try:
                    entry = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue

                lang = entry.get('lang_code', '')
                if lang not in TARGET_LANGS:
                    continue
                if len(samples[lang]) >= MAX_SAMPLES:
                    continue

                templates = entry.get('etymology_templates', [])
                if not templates:
                    continue

                # Check for derivation or compound templates
                template_names = {t.get('name', '') for t in templates if isinstance(t, dict)}
                has_deriv = bool(template_names & DERIVATION_TEMPLATES)
                has_compound = bool(template_names & COMPOUND_TEMPLATES)

                if has_deriv or has_compound:
                    samples[lang].append({
                        'word': entry.get('word', ''),
                        'pos': entry.get('pos', ''),
                        'etymology_templates': templates,
                        'etymology_text': (entry.get('etymology_text', '') or '')[:300]
                    })

                # Stop early if we have enough samples for all languages
                if all(len(samples[l]) >= MAX_SAMPLES for l in TARGET_LANGS):
                    print(f"  Found {MAX_SAMPLES} samples for all languages, stopping early")
                    break

    except FileNotFoundError:
        print(f"ERROR: File not found: {DATA_FILE}")
        sys.exit(1)

    print(f"\n[{datetime.now().isoformat()}] Scan complete")
    print(f"Total lines scanned: {line_count:,}")
    print()

    # Print samples for each language
    for lang in sorted(TARGET_LANGS):
        lang_samples = samples.get(lang, [])
        print(f"\n{'='*70}")
        print(f"=== {lang.upper()} ({len(lang_samples)} samples) ===")
        print(f"{'='*70}")

        if not lang_samples:
            print("  NO SAMPLES FOUND - this language may not have affix/compound templates")
            continue

        for i, entry in enumerate(lang_samples, 1):
            print(f"\n[{i}] word='{entry['word']}' pos='{entry['pos']}'")
            print(f"    etymology_text: {entry['etymology_text'][:150]}...")
            print(f"    etymology_templates ({len(entry['etymology_templates'])} total):")

            # Show all templates, highlight derivation/compound ones with ***
            for tmpl in entry['etymology_templates']:
                name = tmpl.get('name', '')
                args = tmpl.get('args', {})
                marker = '***' if name in (DERIVATION_TEMPLATES | COMPOUND_TEMPLATES) else '   '
                # Pretty print args for readability
                args_str = json.dumps(args, ensure_ascii=False, sort_keys=True)
                print(f"      {marker} name='{name}' args={args_str}")

    # Summary
    print(f"\n{'='*70}")
    print("=== SUMMARY ===")
    print(f"{'='*70}")
    for lang in sorted(TARGET_LANGS):
        count = len(samples.get(lang, []))
        status = '[OK]' if count >= MAX_SAMPLES else f'[{count}/{MAX_SAMPLES}]'
        print(f"  {lang}: {count} samples {status}")

    total = sum(len(v) for v in samples.values())
    print(f"\nTotal samples: {total}")

    # Report which languages are missing samples
    missing = [l for l in TARGET_LANGS if len(samples.get(l, [])) < MAX_SAMPLES]
    if missing:
        print(f"\nLanguages with fewer than {MAX_SAMPLES} samples: {sorted(missing)}")
        print("These may need different template extraction strategies.")


if __name__ == '__main__':
    main()
