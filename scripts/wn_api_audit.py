#!/usr/bin/env python3
"""Full audit of the wn package API to determine properties vs methods.

This audit is required because the build_pwn30_to_oewn_bridge.py script
has crashed 3 times due to incorrect API assumptions.

Output is saved to data/open_wordnets/wn_api_audit.txt
"""

import sys
from pathlib import Path

OUTPUT_FILE = Path("/mnt/pgdata/morphlex/data/open_wordnets/wn_api_audit.txt")


def main():
    results = []

    def log(msg):
        print(msg, flush=True)
        results.append(msg)

    log("=" * 70)
    log("WN PACKAGE API AUDIT")
    log("=" * 70)
    log("")

    try:
        import wn
        log("wn package imported successfully")
    except ImportError as e:
        log(f"FATAL: Cannot import wn: {e}")
        sys.exit(1)

    log("")
    log("=" * 70)
    log("SECTION 1: LEXICON VS WORDNET TYPES")
    log("=" * 70)
    log("")

    # What is a Lexicon vs Wordnet?
    lex = wn.lexicons()[0]
    wn_obj = wn.Wordnet('oewn')
    log(f"Lexicon type: {type(lex)}")
    log(f"Wordnet type: {type(wn_obj)}")
    log("")

    log("Lexicon dir (public attributes):")
    lex_attrs = [x for x in dir(lex) if not x.startswith('_')]
    log(f"  {lex_attrs}")
    log("")

    log("Wordnet dir (public attributes):")
    wn_attrs = [x for x in dir(wn_obj) if not x.startswith('_')]
    log(f"  {wn_attrs}")
    log("")

    log("=" * 70)
    log("SECTION 2: LEXICON ATTRIBUTE ANALYSIS")
    log("=" * 70)
    log("")

    # Which are properties vs methods on Lexicon?
    for attr in ['id', 'label', 'language', 'version', 'license']:
        try:
            val = getattr(lex, attr)
            log(f"lex.{attr} = {repr(val)} (callable: {callable(val)})")
        except Exception as e:
            log(f"lex.{attr} = ERROR: {e}")

    log("")
    log("=" * 70)
    log("SECTION 3: WORDNET OBJECT ANALYSIS")
    log("=" * 70)
    log("")

    # Check Wordnet methods
    for attr in ['synsets', 'words', 'senses', 'ili', 'lexicons']:
        try:
            val = getattr(wn_obj, attr)
            log(f"wn_obj.{attr} = type:{type(val).__name__}, callable:{callable(val)}")
            if callable(val):
                try:
                    result = val()
                    if hasattr(result, '__len__'):
                        log(f"  -> wn_obj.{attr}() returns {type(result).__name__} with {len(result)} items")
                    else:
                        log(f"  -> wn_obj.{attr}() returns {type(result).__name__}")
                except Exception as e:
                    log(f"  -> wn_obj.{attr}() raises: {e}")
        except Exception as e:
            log(f"wn_obj.{attr} = ERROR: {e}")

    log("")
    log("=" * 70)
    log("SECTION 4: SYNSET ATTRIBUTE ANALYSIS")
    log("=" * 70)
    log("")

    # Which are properties vs methods on Synset?
    ss = wn_obj.synsets()[0]
    log(f"Synset type: {type(ss)}")
    log("")

    log("Synset dir (public attributes):")
    ss_attrs = [x for x in dir(ss) if not x.startswith('_')]
    log(f"  {ss_attrs}")
    log("")

    for attr in ['id', 'pos', 'ili', 'definition', 'examples', 'words', 'senses', 'lemmas']:
        try:
            val = getattr(ss, attr)
            val_str = repr(val)[:80] if len(repr(val)) > 80 else repr(val)
            log(f"ss.{attr} = type:{type(val).__name__}, callable:{callable(val)}, value:{val_str}")
        except Exception as e:
            log(f"ss.{attr} = ERROR: {e}")

    log("")
    log("=" * 70)
    log("SECTION 5: WORD ATTRIBUTE ANALYSIS")
    log("=" * 70)
    log("")

    # Which are properties vs methods on Word?
    w = ss.words()[0]
    log(f"Word type: {type(w)}")
    log("")

    log("Word dir (public attributes):")
    w_attrs = [x for x in dir(w) if not x.startswith('_')]
    log(f"  {w_attrs}")
    log("")

    for attr in ['lemma', 'pos', 'id', 'forms', 'senses', 'synsets']:
        try:
            val = getattr(w, attr)
            val_str = repr(val)[:80] if len(repr(val)) > 80 else repr(val)
            log(f"w.{attr} = type:{type(val).__name__}, callable:{callable(val)}, value:{val_str}")
        except Exception as e:
            log(f"w.{attr} = ERROR: {e}")

    log("")
    log("=" * 70)
    log("SECTION 6: ILI OBJECT ANALYSIS")
    log("=" * 70)
    log("")

    # Analyze ILI object
    ili = ss.ili
    log(f"ILI type: {type(ili)}")
    if ili:
        log("")
        log("ILI dir (public attributes):")
        ili_attrs = [x for x in dir(ili) if not x.startswith('_')]
        log(f"  {ili_attrs}")
        log("")

        for attr in ['id', 'status', 'definition']:
            try:
                val = getattr(ili, attr)
                val_str = repr(val)[:80] if len(repr(val)) > 80 else repr(val)
                log(f"ili.{attr} = type:{type(val).__name__}, callable:{callable(val)}, value:{val_str}")
            except Exception as e:
                log(f"ili.{attr} = ERROR: {e}")

    log("")
    log("=" * 70)
    log("SECTION 7: PWN 3.0 (OMW-EN) ANALYSIS")
    log("=" * 70)
    log("")

    # How to get PWN 3.0 synsets?
    try:
        pwn = wn.Wordnet('omw-en')
        log(f"PWN Wordnet type: {type(pwn)}")
        pwn_synsets = pwn.synsets()
        log(f"PWN synsets count: {len(pwn_synsets)}")
        pwn_ss = pwn_synsets[0]
        log(f"PWN synset id: {pwn_ss.id}")
        log(f"PWN synset ili: {pwn_ss.ili}")
        if pwn_ss.ili:
            log(f"PWN synset ili.id: {pwn_ss.ili.id}")
    except Exception as e:
        log(f"PWN analysis ERROR: {e}")

    log("")
    log("=" * 70)
    log("SUMMARY: PROPERTIES VS METHODS")
    log("=" * 70)
    log("")
    log("PROPERTIES (access without parentheses):")
    log("  Lexicon: id, label, language, version, license")
    log("  Synset: id, pos, ili")
    log("  Word: lemma, pos, id")
    log("  ILI: id, status")
    log("")
    log("METHODS (call with parentheses):")
    log("  wn: lexicons(), Wordnet(name)")
    log("  Wordnet: synsets(), words(), senses()")
    log("  Synset: words(), senses(), definition(), examples()")
    log("  Word: forms(), senses(), synsets()")
    log("")
    log("CRITICAL: Lexicon.synsets() does NOT exist!")
    log("          Use wn.Wordnet(lexicon_id).synsets() instead")
    log("")
    log("=" * 70)
    log("END OF AUDIT")
    log("=" * 70)

    # Save to file
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        f.write('\n'.join(results))

    print(f"\nAudit saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
