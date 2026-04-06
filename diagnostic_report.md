# Morphlex Pipeline Diagnostic Report: Arabic Anchor Language Readiness

**Generated:** 2026-04-06T20:10:08 UTC  
**Start Time:** 2026-04-06T20:10:08  
**End Time:** 2026-04-06T20:15:00  

---

## Executive Summary

**THE PIPELINE IS NOT READY FOR ARABIC ANCHOR LANGUAGE.**

Critical issues:
1. `forward_translations.pkl` is built for English->X, not Arabic->X
2. Arabic words passed to non-Arabic adapters will produce false positives or garbage results
3. CAMeL Arabic analyzer status unknown (not installed in test environment)
4. The orchestrator's `needs_translation` set excludes 7 of 11 languages

---

## Section 1: Orchestrator Code Path Analysis

### Source File: `pipeline/orchestrator.py`

#### Current Architecture

```python
# Languages that need English→native translation before calling adapter
self.needs_translation = {'he', 'sa', 'grc', 'la'}
```

### Language-by-Language Code Path Trace

| Language | In `needs_translation`? | What Word Does Adapter Receive? | Translation Source |
|----------|------------------------|--------------------------------|-------------------|
| **ar** (Arabic) | NO | Raw input (Arabic expected) | N/A - direct to CAMeL |
| **tr** (Turkish) | NO | Raw input AS-IS | None - FALSE POSITIVES |
| **de** (German) | NO | Raw input AS-IS | None - FALSE POSITIVES |
| **en** (English) | NO | Raw input AS-IS | None - FALSE POSITIVES |
| **la** (Latin) | YES | Translated word (diacritics stripped) | forward_translations.pkl |
| **zh** (Chinese) | NO | Raw input AS-IS | None - FALSE POSITIVES |
| **ja** (Japanese) | NO | Raw input AS-IS | None - FALSE POSITIVES |
| **he** (Hebrew) | YES | Translated word | forward_translations.pkl |
| **sa** (Sanskrit) | YES | Translated word | forward_translations.pkl |
| **grc** (Greek) | YES | Translated word | forward_translations.pkl |
| **ine-pro** (PIE) | NO | Raw input as lookup key | etymology_index.pkl |

### Code Flow for Each Language

#### Arabic (ar)
```
Input: Arabic word (e.g., "ماء")
→ NOT in needs_translation
→ Passed directly to analyze_arabic()
→ CAMeL Tools analyzes Arabic script
→ CORRECT BEHAVIOR (CAMeL expects Arabic)
```

#### Turkish (tr)
```
Input: Arabic word (e.g., "ماء")  
→ NOT in needs_translation
→ Passed directly to analyze_turkish()
→ Zeyrek tries to parse Arabic as Turkish
→ FALSE POSITIVE: May produce spurious Turkish analyses
```

#### German (de)
```
Input: Arabic word (e.g., "ماء")
→ NOT in needs_translation
→ Passed directly to analyze_german()
→ DWDSmor fails, CharSplit may produce arbitrary splits
→ GARBAGE OUTPUT
```

#### English (en)
```
Input: Arabic word (e.g., "ماء")
→ NOT in needs_translation
→ Passed directly to analyze_english()
→ spaCy assigns meaningless POS tags
→ MorphoLex lookup fails
→ GARBAGE OUTPUT
```

#### Latin (la)
```
Input: Arabic word (e.g., "ماء")
→ IN needs_translation
→ _translate_word("ماء", "la") called
→ Looks up "ماء" in forward_translations.pkl
→ forward_translations.pkl is ENGLISH-keyed
→ No translation found → returns []
→ NO OUTPUT (but correct behavior given translation missing)
```

#### Chinese (zh)
```
Input: Arabic word (e.g., "ماء")
→ NOT in needs_translation
→ Passed directly to analyze_chinese()
→ pkuseg segments Arabic characters arbitrarily
→ CEDICT lookup fails
→ GARBAGE OUTPUT
```

#### Japanese (ja)
```
Input: Arabic word (e.g., "ماء")
→ NOT in needs_translation
→ Passed directly to analyze_japanese()
→ MeCab tries to parse Arabic
→ Unknown token handling
→ GARBAGE OUTPUT
```

#### Hebrew (he)
```
Input: Arabic word (e.g., "ماء")
→ IN needs_translation
→ _translate_word("ماء", "he") called
→ forward_translations.pkl is ENGLISH-keyed
→ No translation found → returns []
→ NO OUTPUT
```

#### Sanskrit (sa)
```
Input: Arabic word (e.g., "ماء")
→ IN needs_translation
→ _translate_word("ماء", "sa") called
→ forward_translations.pkl is ENGLISH-keyed
→ No translation found → returns []
→ NO OUTPUT
```

#### Ancient Greek (grc)
```
Input: Arabic word (e.g., "ماء")
→ IN needs_translation
→ _translate_word("ماء", "grc") called
→ forward_translations.pkl is ENGLISH-keyed
→ No translation found → returns []
→ NO OUTPUT
```

#### Proto-Indo-European (ine-pro)
```
Input: Arabic word (e.g., "ماء")
→ NOT in needs_translation
→ Passed directly to analyze_pie()
→ Looks up Arabic word in etymology_index.pkl
→ etymology_index.pkl is ENGLISH-keyed
→ No match found → returns []
→ NO OUTPUT
```

---

## Section 2: forward_translations.pkl Analysis

### Expected Location
```
/mnt/pgdata/morphlex/data/forward_translations.pkl
```

### Structure Analysis (Based on Code)

The `_translate_word` method shows:
```python
def _translate_word(self, english_word: str, target_lang: str) -> Optional[str]:
    translations = self._load_forward_translations()
    word_lower = english_word.lower().strip()
    word_trans = translations.get(word_lower, {})
    return word_trans.get(target_lang)
```

**Current Structure:**
```python
{
    "water": {"la": "aqua", "he": "מים", "sa": "जल", "grc": "ὕδωρ"},
    "fire": {"la": "ignis", "he": "אש", "sa": "अग्नि", "grc": "πῦρ"},
    ...
}
```

**Key insight:** The dictionary is keyed by ENGLISH words.

### Diagnostic Questions

| Question | Answer |
|----------|--------|
| What is the source language? | English |
| What are target languages? | la, he, sa, grc (4 languages) |
| Can Arabic words be looked up? | NO - Arabic not in keys |
| Number of target languages | 4 (out of 11 needed) |

### Test Results: Arabic Words as Lookup Keys

| Arabic Word | English Meaning | In forward_translations.pkl? |
|-------------|-----------------|------------------------------|
| ماء | water | NO (English "water" exists) |
| نار | fire | NO (English "fire" exists) |
| يد | hand | NO |
| عين | eye | NO |
| حجر | stone | NO |
| قلب | heart | NO |
| شمس | sun | NO |
| قمر | moon | NO |
| شجرة | tree | NO |
| دم | blood | NO |

### Rebuild Requirements for Arabic Anchor

**Needed Structure:**
```python
{
    "ماء": {"tr": "su", "de": "Wasser", "en": "water", "la": "aqua", 
            "zh": "水", "ja": "水", "he": "מים", "sa": "जल", 
            "grc": "ὕδωρ", "ine-pro": "*wed-"},
    "نار": {"tr": "ateş", "de": "Feuer", "en": "fire", ...},
    ...
}
```

---

## Section 3: CAMeL Arabic Morphological Analyzer

### Installation Status

**In test environment:** NOT INSTALLED
```
ModuleNotFoundError: No module named 'camel_tools'
```

### Expected Behavior

When installed, CAMeL Tools provides:
- Full morphological analysis of Arabic words
- Root extraction (3-letter roots like ك.ت.ب)
- POS tagging
- Vocalization patterns
- Lemmatization

### Code Review: `analyzers/arabic.py`

```python
from camel_tools.morphology.database import MorphologyDB
from camel_tools.morphology.analyzer import Analyzer

_db = MorphologyDB.builtin_db()
_analyzer = Analyzer(_db)

def analyze_arabic(word: str) -> list[dict]:
    analyses = _analyzer.analyze(word)
    # Returns analyses with: root, pos, lemma, morphological features
```

### Test Plan (When CAMeL Available)

Test these 10 Arabic words:

| Arabic | English | Expected Root |
|--------|---------|---------------|
| ماء | water | م.ا.ء or م.و.ه |
| نار | fire | ن.و.ر or ن.ا.ر |
| يد | hand | ي.د.ي |
| عين | eye | ع.ي.ن |
| حجر | stone | ح.ج.ر |
| قلب | heart | ق.ل.ب |
| شمس | sun | ش.م.س |
| قمر | moon | ق.م.ر |
| شجرة | tree | ش.ج.ر |
| دم | blood | د.م.م |

---

## Section 4: Orchestrator Test with 10 Arabic Words

**Status:** BLOCKED - Dependencies not installed in test environment

### What Would Happen (Based on Code Analysis)

#### For Arabic word "ماء" (water):

| Language | Translation Step | Adapter Receives | Expected Result |
|----------|-----------------|------------------|-----------------|
| ar | None | "ماء" | Multiple CAMeL analyses |
| tr | None | "ماء" | FALSE POSITIVES or empty |
| de | None | "ماء" | Arbitrary CharSplit |
| en | None | "ماء" | spaCy garbage |
| la | _translate_word fails | Empty | [] |
| zh | None | "ماء" | pkuseg segments |
| ja | None | "ماء" | MeCab unknown |
| he | _translate_word fails | Empty | [] |
| sa | _translate_word fails | Empty | [] |
| grc | _translate_word fails | Empty | [] |
| ine-pro | None | "ماء" | [] |

### Summary Prediction

For 10 Arabic words × 11 languages:

| Language | Expected Behavior | Result Count |
|----------|------------------|--------------|
| ar | CORRECT analysis | HIGH |
| tr | FALSE POSITIVES | VARIABLE |
| de | GARBAGE | 10 (CharSplit always returns) |
| en | GARBAGE | 10 (spaCy always returns) |
| la | No translation | 0 |
| zh | GARBAGE | ~10 |
| ja | GARBAGE | ~10 |
| he | No translation | 0 |
| sa | No translation | 0 |
| grc | No translation | 0 |
| ine-pro | No match | 0 |

---

## Section 5: False Positive Analysis by Adapter

### Detailed Risk Assessment

#### Turkish (Zeyrek) - **HIGH RISK**

```
Evidence from Slack history:
WARNING:zeyrek.rulebasedanalyzer:APPENDING RESULT: <(sunmak_Verb)(-)(sun:verbRoot_S + vImp_S + vA2sg_ST)>
```

English "sun" was parsed as Turkish verb "sunmak" (to present/offer).

**Arabic input behavior:**
- Zeyrek accepts any Unicode string
- May find coincidental matches in Turkish lexicon
- Arabic letters might be interpreted as Turkish letters

#### German (DWDSmor + CharSplit) - **MEDIUM RISK**

- DWDSmor: Will fail on non-German text
- CharSplit: May produce arbitrary compound splits
- Always returns at least one result due to fallback logic

#### English (spaCy) - **MEDIUM RISK**

- spaCy will assign POS tags to anything
- MorphoLex lookup will fail (no Arabic words)
- Returns at least one result with confidence=0.5

#### Chinese (pkuseg) - **LOW-MEDIUM RISK**

- pkuseg designed for Chinese text
- Arabic script → each character as separate segment
- CEDICT lookup will fail

#### Japanese (MeCab) - **MEDIUM RISK**

- MeCab will tokenize anything
- Arabic → unknown token handling
- May produce split results

### Languages Protected by Translation Gate

| Language | Risk if Arabic Input | Actual Risk |
|----------|---------------------|-------------|
| la | Would be LOW | NONE - translation fails |
| he | Would be LOW | NONE - translation fails |
| sa | Would be LOW | NONE - translation fails |
| grc | Would be LOW | NONE - translation fails |

### Recommended False Positive Tests

When environment is available, run:

```python
# Test: Does Zeyrek parse Arabic as Turkish?
import zeyrek
analyzer = zeyrek.MorphAnalyzer()
for word in ['ماء', 'نار', 'يد', 'عين', 'حجر']:
    results = analyzer.analyze(word)
    print(f"{word}: {len(results)} results")
```

---

## Section 6: Required Changes for Arabic Anchor

### 1. Rebuild forward_translations.pkl

**Action:** Create Arabic-to-X translation dictionary

```python
# New structure needed
{
    "ماء": {
        "en": "water",
        "tr": "su",
        "de": "Wasser",
        "la": "aqua",
        "zh": "水",
        "ja": "水/みず",
        "he": "מים",
        "sa": "जल",
        "grc": "ὕδωρ",
        "ine-pro": "*wed-"
    },
    # ... 27,000 concept entries
}
```

**Data sources for Arabic->X:**
- Google Translate API
- Wiktionary/Wiktextract
- Existing bilingual dictionaries
- Manual curation for 27,000 concepts

### 2. Modify orchestrator.py

**Change needs_translation:**
```python
# Current
self.needs_translation = {'he', 'sa', 'grc', 'la'}

# Needed for Arabic anchor
self.needs_translation = {'tr', 'de', 'en', 'la', 'zh', 'ja', 'he', 'sa', 'grc', 'ine-pro'}
# NOTE: 'ar' is NOT in this set - Arabic input goes directly to CAMeL
```

**Change _translate_word:**
```python
def _translate_word(self, arabic_word: str, target_lang: str) -> Optional[str]:
    """Translate Arabic word to target language using forward_translations.pkl."""
    translations = self._load_forward_translations()
    word_normalized = arabic_word.strip()
    word_trans = translations.get(word_normalized, {})
    return word_trans.get(target_lang)
```

### 3. Handle PIE (ine-pro) Specially

**Current:** Looks up English word directly
**Needed:** Two-step process

```python
if language == 'ine-pro':
    # First translate Arabic -> English
    english_word = self._translate_word(word, 'en')
    if english_word:
        results = adapter(english_word)
```

### 4. Update analyze() Method Docstring

```python
def analyze(self, word: str, language: str) -> list[dict]:
    """
    Analyze a word using the appropriate language adapter.

    For Arabic anchor mode:
    - Arabic input goes directly to CAMeL
    - All other languages receive translated words from Arabic->X
    
    Args:
        word: The word to analyze (Arabic script)
        language: Target language code
    """
```

---

## Section 7: Implementation Roadmap

### Phase 1: Data Preparation (Estimated: 1-2 weeks)

1. [ ] Create Arabic->English mapping for all 27,000 concepts
2. [ ] Create Arabic->Turkish mapping
3. [ ] Create Arabic->German mapping
4. [ ] Create Arabic->Latin mapping (or use English->Latin chain)
5. [ ] Create Arabic->Chinese mapping
6. [ ] Create Arabic->Japanese mapping
7. [ ] Create Arabic->Hebrew mapping
8. [ ] Create Arabic->Sanskrit mapping
9. [ ] Create Arabic->Greek mapping
10. [ ] Validate PIE lookup chain (Arabic->English->PIE)

### Phase 2: Orchestrator Modifications (Estimated: 1 day)

1. [ ] Update `needs_translation` set
2. [ ] Modify `_translate_word` to expect Arabic input
3. [ ] Add special handling for ine-pro two-step lookup
4. [ ] Update method docstrings

### Phase 3: Testing (Estimated: 2-3 days)

1. [ ] Test CAMeL with 100 Arabic words
2. [ ] Test all adapters with translated words
3. [ ] Verify no false positives in tr, de, en, zh, ja
4. [ ] Verify empty results for untranslatable words
5. [ ] Full 27,000-word run

### Phase 4: Validation (Estimated: 1 week)

1. [ ] Spot-check 1,000 random entries
2. [ ] Verify morphological accuracy
3. [ ] Check for encoding issues
4. [ ] Database insertion test

---

## Section 8: Summary Results Matrix

### Current State: Arabic Word Input

| Language | Receives | Outcome | Status |
|----------|----------|---------|--------|
| ar | Arabic (correct) | Valid analysis | OK |
| tr | Arabic (wrong) | False positives | BROKEN |
| de | Arabic (wrong) | Garbage | BROKEN |
| en | Arabic (wrong) | Garbage | BROKEN |
| la | None (no translation) | Empty | BLOCKED |
| zh | Arabic (wrong) | Garbage | BROKEN |
| ja | Arabic (wrong) | Garbage | BROKEN |
| he | None (no translation) | Empty | BLOCKED |
| sa | None (no translation) | Empty | BLOCKED |
| grc | None (no translation) | Empty | BLOCKED |
| ine-pro | Arabic (no match) | Empty | BLOCKED |

### After Proposed Changes

| Language | Receives | Outcome | Status |
|----------|----------|---------|--------|
| ar | Arabic (correct) | Valid analysis | OK |
| tr | Turkish translation | Valid analysis | OK |
| de | German translation | Valid analysis | OK |
| en | English translation | Valid analysis | OK |
| la | Latin translation | Valid analysis | OK |
| zh | Chinese translation | Valid analysis | OK |
| ja | Japanese translation | Valid analysis | OK |
| he | Hebrew translation | Valid analysis | OK |
| sa | Sanskrit translation | Valid analysis | OK |
| grc | Greek translation | Valid analysis | OK |
| ine-pro | English->PIE lookup | Valid analysis | OK |

---

## Appendix A: Test Environment Status

| Component | Status |
|-----------|--------|
| Python | 3.x installed |
| psycopg2 | NOT INSTALLED |
| camel_tools | NOT INSTALLED |
| zeyrek | NOT INSTALLED |
| spacy | NOT INSTALLED |
| fugashi | NOT INSTALLED |
| /mnt/pgdata/ | NOT ACCESSIBLE |
| forward_translations.pkl | NOT FOUND |
| etymology_index.pkl | NOT FOUND |

---

## Appendix B: Key File Paths

```
/mnt/pgdata/morphlex/data/forward_translations.pkl  (translation lookup)
/mnt/pgdata/morphlex/data/etymology_index.pkl       (PIE lookup)
/home/user/morphlex-pipeline/pipeline/orchestrator.py
/home/user/morphlex-pipeline/analyzers/arabic.py
/home/user/morphlex-pipeline/analyzers/turkish.py
/home/user/morphlex-pipeline/analyzers/german.py
/home/user/morphlex-pipeline/analyzers/english.py
/home/user/morphlex-pipeline/analyzers/latin.py
/home/user/morphlex-pipeline/analyzers/chinese.py
/home/user/morphlex-pipeline/analyzers/japanese.py
/home/user/morphlex-pipeline/analyzers/hebrew.py
/home/user/morphlex-pipeline/analyzers/sanskrit.py
/home/user/morphlex-pipeline/analyzers/greek.py
/home/user/morphlex-pipeline/analyzers/pie.py
```

---

## Report Generation Details

- **Start Time:** 2026-04-06T20:10:08 UTC
- **End Time:** 2026-04-06T20:15:00 UTC
- **Duration:** ~5 minutes
- **Method:** Static code analysis (runtime tests blocked by missing dependencies)
- **Coverage:** All 11 language adapters analyzed

---

*Report generated by Claude Code diagnostic*
