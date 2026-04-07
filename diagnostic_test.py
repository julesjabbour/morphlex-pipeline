#!/usr/bin/env python3
"""Comprehensive pipeline diagnostic for Arabic anchor language readiness."""

import datetime
import os
import pickle
import sys
import warnings

# Suppress all library warnings
warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import logging
logging.disable(logging.CRITICAL)

# Add pipeline to path - all code lives at /mnt/pgdata/morphlex
sys.path.insert(0, '/mnt/pgdata/morphlex')

START_TIME = datetime.datetime.now()

print(f"=== PIPELINE DIAGNOSTIC REPORT ===")
print(f"Start Time: {START_TIME.isoformat()}")
print()

# -----------------------------------------------------------------------------
# SECTION 1: forward_translations.pkl Analysis
# -----------------------------------------------------------------------------
print("=" * 70)
print("SECTION 1: forward_translations.pkl ANALYSIS")
print("=" * 70)

FWD_PATH = '/mnt/pgdata/morphlex/data/forward_translations.pkl'

if os.path.exists(FWD_PATH):
    with open(FWD_PATH, 'rb') as f:
        fwd_trans = pickle.load(f)

    print(f"File exists: {FWD_PATH}")
    print(f"Type: {type(fwd_trans)}")
    print(f"Number of entries (source words): {len(fwd_trans)}")

    # Examine structure
    sample_keys = list(fwd_trans.keys())[:5]
    print(f"\nSample source words: {sample_keys}")

    # Check what languages are covered
    all_target_langs = set()
    for key, value in fwd_trans.items():
        if isinstance(value, dict):
            all_target_langs.update(value.keys())

    print(f"\nTarget languages covered: {sorted(all_target_langs)}")
    print(f"Number of target languages: {len(all_target_langs)}")

    # Check if source words are English or Arabic
    print("\n--- Source Language Detection ---")
    english_pattern_count = 0
    arabic_pattern_count = 0
    other_count = 0

    for key in list(fwd_trans.keys())[:100]:
        if all(ord(c) < 128 for c in key.replace(' ', '')):
            english_pattern_count += 1
        elif any('\u0600' <= c <= '\u06FF' for c in key):
            arabic_pattern_count += 1
        else:
            other_count += 1

    print(f"First 100 keys - ASCII (English-like): {english_pattern_count}")
    print(f"First 100 keys - Arabic script: {arabic_pattern_count}")
    print(f"First 100 keys - Other: {other_count}")

    # Show actual sample entries
    print("\n--- Sample Entry Structure ---")
    for key in sample_keys[:3]:
        print(f"  '{key}': {fwd_trans[key]}")

    # Check if Arabic test words are in there
    print("\n--- Arabic Test Words in forward_translations? ---")
    arabic_words = ['ماء', 'نار', 'يد', 'عين', 'حجر', 'قلب', 'شمس', 'قمر', 'شجرة', 'دم']
    english_words = ['water', 'fire', 'hand', 'eye', 'stone', 'heart', 'sun', 'moon', 'tree', 'blood']

    for ar, en in zip(arabic_words, english_words):
        ar_entry = fwd_trans.get(ar)
        en_entry = fwd_trans.get(en)
        print(f"  '{ar}' ({en}): Arabic lookup={'YES' if ar_entry else 'NO'}, English lookup={'YES' if en_entry else 'NO'}")

else:
    print(f"FILE NOT FOUND: {FWD_PATH}")
    fwd_trans = {}

print()

# -----------------------------------------------------------------------------
# SECTION 2: Orchestrator Code Path Analysis
# -----------------------------------------------------------------------------
print("=" * 70)
print("SECTION 2: ORCHESTRATOR CODE PATH ANALYSIS")
print("=" * 70)
print()

print("Languages configured in orchestrator:")
print("  ar, tr, de, en, la, zh, grc, ja, he, sa, ine-pro")
print()

print("needs_translation set: {'he', 'sa', 'grc', 'la'}")
print()

print("CODE PATH BY LANGUAGE:")
print("-" * 70)
code_paths = {
    'ar': ('NO', 'Raw input passed directly to CAMeL analyzer'),
    'tr': ('NO', 'Raw input passed directly to Zeyrek analyzer'),
    'de': ('NO', 'Raw input passed directly to DWDSmor/CharSplit'),
    'en': ('NO', 'Raw input passed directly to spaCy/MorphoLex'),
    'la': ('YES', 'English->Latin via forward_translations.pkl, then strip_diacritics()'),
    'zh': ('NO', 'Raw input passed directly to pkuseg/CEDICT'),
    'ja': ('NO', 'Raw input passed directly to MeCab/fugashi'),
    'he': ('YES', 'English->Hebrew via forward_translations.pkl'),
    'sa': ('YES', 'English->Sanskrit via forward_translations.pkl'),
    'grc': ('YES', 'English->Greek via forward_translations.pkl'),
    'ine-pro': ('NO', 'English word used directly as lookup key in etymology_index'),
}

for lang, (translated, desc) in code_paths.items():
    print(f"  {lang:8s}: Translation={translated:3s} | {desc}")

print()
print("CRITICAL FINDING for Arabic Anchor:")
print("  Arabic (ar) is NOT in needs_translation set!")
print("  If Arabic words are passed as input, they go DIRECTLY to CAMeL analyzer.")
print("  CAMeL EXPECTS Arabic script, so this will WORK for Arabic input.")
print()
print("  BUT: Languages NOT in needs_translation receive input AS-IS:")
print("    - Turkish (tr): Will try to parse Arabic as Turkish -> FALSE POSITIVES")
print("    - German (de): Will try to parse Arabic as German -> FALSE POSITIVES")
print("    - English (en): Will try to parse Arabic as English -> FALSE POSITIVES")
print("    - Chinese (zh): Will try to segment Arabic as Chinese -> FALSE POSITIVES")
print("    - Japanese (ja): Will try to parse Arabic as Japanese -> FALSE POSITIVES")
print("    - PIE (ine-pro): Will look up Arabic word in English etymology index -> EMPTY")
print()

# -----------------------------------------------------------------------------
# SECTION 3: CAMeL Arabic Analyzer Test
# -----------------------------------------------------------------------------
print("=" * 70)
print("SECTION 3: CAMeL ARABIC ANALYZER TEST")
print("=" * 70)

try:
    from camel_tools.morphology.database import MorphologyDB
    from camel_tools.morphology.analyzer import Analyzer

    print("CAMeL Tools: INSTALLED")

    _db = MorphologyDB.builtin_db()
    _analyzer = Analyzer(_db)
    print("CAMeL Analyzer: INITIALIZED SUCCESSFULLY")
    print()

    print("Testing 10 Arabic words directly with CAMeL:")
    print("-" * 70)

    camel_results = {}
    for ar_word, en_word in zip(arabic_words, english_words):
        analyses = _analyzer.analyze(ar_word)
        camel_results[ar_word] = analyses

        print(f"\n{ar_word} ({en_word}): {len(analyses)} analyses")
        if analyses:
            for i, a in enumerate(analyses[:3]):  # Show first 3
                root = a.get('root', 'N/A')
                pos = a.get('pos', 'N/A')
                lex = a.get('lex', 'N/A')
                print(f"    [{i+1}] root={root}, pos={pos}, lemma={lex}")
            if len(analyses) > 3:
                print(f"    ... and {len(analyses)-3} more analyses")
        else:
            print("    NO ANALYSES FOUND")

except ImportError as e:
    print(f"CAMeL Tools: NOT INSTALLED - {e}")
except Exception as e:
    print(f"CAMeL Analyzer: ERROR - {e}")

print()

# -----------------------------------------------------------------------------
# SECTION 4: Orchestrator Test with 10 Arabic Words
# -----------------------------------------------------------------------------
print("=" * 70)
print("SECTION 4: ORCHESTRATOR TEST WITH 10 ARABIC WORDS")
print("=" * 70)

try:
    from pipeline.orchestrator import PipelineOrchestrator

    orch = PipelineOrchestrator()
    print("Orchestrator initialized successfully")
    print()

    languages = ['ar', 'tr', 'de', 'en', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro']

    print("Testing each Arabic word through orchestrator for all 11 languages:")
    print("-" * 70)

    full_results = {}

    for ar_word, en_word in zip(arabic_words, english_words):
        full_results[ar_word] = {}
        print(f"\n{ar_word} ({en_word}):")

        for lang in languages:
            results = orch.analyze(ar_word, lang)
            full_results[ar_word][lang] = results

            # Determine what word was actually passed to adapter
            if lang in orch.needs_translation:
                # Check if translation exists
                translated = orch._translate_word(ar_word, lang)
                if translated:
                    if lang == 'la':
                        actual_word = orch.strip_diacritics(translated) if hasattr(orch, 'strip_diacritics') else translated
                    else:
                        actual_word = translated
                    word_note = f"TRANSLATED to '{actual_word}'"
                else:
                    word_note = "NO TRANSLATION FOUND"
            else:
                actual_word = ar_word
                word_note = "PASSED AS-IS (no translation)"

            status = "[OK]" if results else "[EMPTY]"
            print(f"    {lang:8s}: {len(results):3d} results {status:7s} | {word_note}")

except Exception as e:
    import traceback
    print(f"Orchestrator test failed: {e}")
    traceback.print_exc()

print()

# -----------------------------------------------------------------------------
# SECTION 5: False Positive Analysis
# -----------------------------------------------------------------------------
print("=" * 70)
print("SECTION 5: FALSE POSITIVE ANALYSIS")
print("=" * 70)
print()

print("For each adapter, analyzing potential false positives when receiving")
print("untranslated words from the wrong language (Arabic input to non-Arabic analyzers):")
print("-" * 70)

false_positive_analysis = {
    'ar': {
        'risk': 'LOW',
        'reason': 'CAMeL expects Arabic script. Arabic input is CORRECT.',
        'example': 'ماء -> proper Arabic analysis'
    },
    'tr': {
        'risk': 'HIGH',
        'reason': 'Zeyrek accepts ANY string. Will try to parse as Turkish.',
        'example': '"sun" (English) -> parsed as Turkish verb "sunmak" (to present)',
        'arabic_test': 'Need to test Arabic script handling'
    },
    'de': {
        'risk': 'MEDIUM',
        'reason': 'DWDSmor will fail on non-German. CharSplit may still produce splits.',
        'example': 'Non-German input may get arbitrary compound splits'
    },
    'en': {
        'risk': 'MEDIUM',
        'reason': 'spaCy will try to lemmatize/tag anything. MorphoLex lookup will fail.',
        'example': 'Arabic text -> spaCy assigns POS tags even though meaningless'
    },
    'la': {
        'risk': 'LOW (with translation)',
        'reason': 'Requires English->Latin translation first. Arabic not in translation table.',
        'example': 'Arabic word -> no translation -> returns empty'
    },
    'zh': {
        'risk': 'LOW-MEDIUM',
        'reason': 'pkuseg designed for Chinese. Non-Chinese text treated as unknown segments.',
        'example': 'Arabic script -> each character may be treated as separate segment'
    },
    'ja': {
        'risk': 'MEDIUM',
        'reason': 'MeCab will attempt to parse anything. Arabic -> unknown tokens.',
        'example': 'Arabic text may be split arbitrarily'
    },
    'he': {
        'risk': 'LOW (with translation)',
        'reason': 'Requires English->Hebrew translation. Arabic not in translation table.',
        'example': 'Arabic word -> no translation -> returns empty'
    },
    'sa': {
        'risk': 'LOW (with translation)',
        'reason': 'Requires English->Sanskrit translation. Arabic not in translation table.',
        'example': 'Arabic word -> no translation -> returns empty'
    },
    'grc': {
        'risk': 'LOW (with translation)',
        'reason': 'Requires English->Greek translation. Arabic not in translation table.',
        'example': 'Arabic word -> no translation -> returns empty'
    },
    'ine-pro': {
        'risk': 'LOW',
        'reason': 'Looks up English word in etymology index. Arabic not in index.',
        'example': 'Arabic word -> no match -> returns empty'
    },
}

for lang, analysis in false_positive_analysis.items():
    print(f"\n{lang.upper()}:")
    print(f"  Risk Level: {analysis['risk']}")
    print(f"  Reason: {analysis['reason']}")
    print(f"  Example: {analysis['example']}")

print()

# Test Turkish false positives with Arabic
print("-" * 70)
print("TURKISH FALSE POSITIVE TEST with Arabic words:")
print("-" * 70)
try:
    import zeyrek
    zeyrek_analyzer = zeyrek.MorphAnalyzer()

    for ar_word, en_word in zip(arabic_words[:5], english_words[:5]):
        analyses = zeyrek_analyzer.analyze(ar_word)
        if analyses:
            print(f"  {ar_word} ({en_word}): {len(analyses)} Turkish analyses (FALSE POSITIVE)")
            # Show first analysis if any
            if analyses and analyses[0]:
                first = analyses[0][0] if isinstance(analyses[0], list) else analyses[0]
                print(f"      First parse: {first}")
        else:
            print(f"  {ar_word} ({en_word}): No Turkish analyses (CORRECT)")
except Exception as e:
    print(f"  Zeyrek test error: {e}")

print()

# -----------------------------------------------------------------------------
# SECTION 6: Summary Results Table
# -----------------------------------------------------------------------------
print("=" * 70)
print("SECTION 6: SUMMARY RESULTS TABLE")
print("=" * 70)
print()

if 'full_results' in dir():
    print("Results count by language and word:")
    print("-" * 100)

    # Header
    header = f"{'Word':<12}" + "".join(f"{lang:>8}" for lang in languages)
    print(header)
    print("-" * 100)

    totals = {lang: 0 for lang in languages}

    for ar_word, en_word in zip(arabic_words, english_words):
        if ar_word in full_results:
            row = f"{ar_word:<12}"
            for lang in languages:
                count = len(full_results[ar_word].get(lang, []))
                totals[lang] += count
                row += f"{count:>8}"
            print(row)

    print("-" * 100)
    total_row = f"{'TOTAL':<12}" + "".join(f"{totals[lang]:>8}" for lang in languages)
    print(total_row)

print()

# -----------------------------------------------------------------------------
# SECTION 7: Recommendations
# -----------------------------------------------------------------------------
print("=" * 70)
print("SECTION 7: RECOMMENDATIONS FOR ARABIC ANCHOR")
print("=" * 70)
print()

print("To make the pipeline work with Arabic as anchor language:")
print()
print("1. CRITICAL: Rebuild forward_translations.pkl")
print("   - Current structure: English -> {la, he, sa, grc} translations")
print("   - Needed structure: Arabic -> {tr, de, en, la, zh, ja, he, sa, grc, ine-pro}")
print()
print("2. MODIFY needs_translation in orchestrator.py:")
print("   - Current: {'he', 'sa', 'grc', 'la'}")
print("   - Needed: {'tr', 'de', 'en', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro'}")
print("   - Arabic (ar) should NOT be in this set (receives Arabic directly)")
print()
print("3. UPDATE _translate_word() method:")
print("   - Current: expects English as source, returns target language")
print("   - Needed: expects Arabic as source, returns target language")
print()
print("4. CREATE Arabic->X translation data:")
print("   - Need Arabic->English translations for en, PIE lookup")
print("   - Need Arabic->Turkish translations for tr")
print("   - Need Arabic->German translations for de")
print("   - etc.")
print()
print("5. HANDLE PIE (ine-pro) specially:")
print("   - Current: looks up English word in etymology_index")
print("   - Needed: First translate Arabic->English, then lookup")
print()

# End time
END_TIME = datetime.datetime.now()
DURATION = END_TIME - START_TIME

print("=" * 70)
print(f"End Time: {END_TIME.isoformat()}")
print(f"Duration: {DURATION}")
print("=" * 70)
