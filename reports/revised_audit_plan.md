# Morphlex Pipeline Adapter Audit - Revised Plan

**Date:** 2026-04-07  
**Status:** Approved with Phase 1.3 correction

---

## Context

The v2 1,000-word batch produced 11,475 rows with 0 errors, but the `root` column is empty for 9/11 languages. The pipeline correctly extracts roots for Arabic (CAMeL) and Turkish (Zeyrek), but other adapters return the normalized word as the root - a fallback, not true morphological analysis.

---

## Phase 1: Quick Wins (Blocking Issues)

### 1.1 PIE Bug Fix
**File:** `analyzers/pie.py:46`  
**Issue:** Function processes `src_word` into `word` (stripping asterisks) but returns `src_word` unchanged.

```python
# Current (buggy) - lines 41 and 46:
word = src_word.lstrip('*')
...
return src_word  # BUG: Returns unprocessed form

# Fixed:
word = src_word.lstrip('*')
...
return word  # Returns processed form
```

### 1.2 Schema Fix (BLOCKING)
**File:** `schema.sql`  
**Issue:** `morph_type`, `derived_from_root`, and `derivation_mode` columns missing from `lexicon.entries`. Adapters generate these fields but they're silently dropped on INSERT.

**Action:** Add columns before any batch run:
```sql
ALTER TABLE lexicon.entries ADD COLUMN IF NOT EXISTS morph_type VARCHAR(20);
ALTER TABLE lexicon.entries ADD COLUMN IF NOT EXISTS derived_from_root TEXT;
ALTER TABLE lexicon.entries ADD COLUMN IF NOT EXISTS derivation_mode VARCHAR(50);
```

Update `orchestrator.py` INSERT statement (lines 304-314) to include these columns.

### 1.3 Empty-String Fallbacks for he/sa/grc (CRITICAL)
**Issue:** When etymology lookup fails on a valid word, these adapters return the normalized word as "root" instead of empty string.

**Exact problematic lines:**

**hebrew.py:47-48:**
```python
# Fallback: use normalized word as root approximation
return _normalize_hebrew(word)
```

**sanskrit.py:48-49:**
```python
# Fallback: use normalized word
return _normalize_sanskrit(word)
```

**greek.py:20-21:**
```python
# Fallback to word itself
return word
```

**Fix:** Change all three to return `''` when etymology lookup fails:
```python
# Return empty string when root is unknown
return ''
```

---

## Phase 2: Wiktextract Root Template Extraction

**Purpose:** Extract `{{root|lang|...}}` templates from Wiktextract as the PRIMARY root source for Hebrew (he), Sanskrit (sa), and Ancient Greek (grc).

**File to create:** `pipeline/extract_wiktextract_roots.py`

### Implementation
1. Stream `raw-wiktextract-data.jsonl.gz` (2.4GB)
2. For each entry, scan `etymology_templates` for:
   - `name == 'root'` with `args['1']` = language code
   - Extract root value from `args['2']` or `args['3']`
3. Build index: `{lang_code: {word: [roots]}}`
4. Save to `data/wiktextract_roots.pkl`

### Adapter Integration
Modify `hebrew.py`, `sanskrit.py`, `greek.py` to:
1. First check `wiktextract_roots.pkl` for the word
2. If found, use that root (high confidence: 0.9)
3. If not found, return `''` (root unknown)

---

## Phase 3: Greek Adapter - Wire to Morpheus

**File:** `analyzers/greek.py`

**Issue:** Greek adapter only uses Wiktextract etymology templates. Morpheus is running at `http://localhost:1315/greek/{word}` but not wired.

**Action:** Add Morpheus lookup similar to `latin.py`:
```python
def _query_morpheus_greek(word: str) -> list[dict]:
    url = f"http://localhost:1315/greek/{word}"
    # ... HTTP request, parse JSON response
```

Morpheus provides lemma and morphological analysis. Use as fallback when Wiktextract root not found.

---

## Phase 4: Assess Hebrew/Sanskrit Coverage

After Phase 2 completes, run coverage analysis:
- If Wiktextract `{{root|he|...}}` covers >70% of test words: ship as-is
- If <70%: research and propose proven morphological analyzers (NOT naive strippers)

**Rejected approaches:**
- Hebrew prefix/suffix stripping (non-concatenative morphology)
- Sanskrit dhatu stripping (sandhi transformations)

---

## Phase 5: Batch Infrastructure

### 5.1 Per-Word Error Handling
**File:** `orchestrator.py`

Modify `batch_analyze()` to catch exceptions per word:
```python
for word, language in word_list:
    try:
        results = self.analyze(word, language)
        all_results.extend(results)
    except Exception as e:
        logger.error(f"Adapter crash on '{word}' ({language}): {e}")
        # Continue processing - don't abort entire batch
        continue
```

### 5.2 File-Not-Found Guards
**Files:** `chinese.py`, `english.py`

Add graceful handling for missing data files:
- Chinese: CEDICT/IDS paths
- English: MorphoLex database

Log warning and return empty results instead of crashing.

### 5.3 German Adapter Verification
**File:** `analyzers/german.py`

Confirm DWDSmor availability. The audit report noted a contradiction ("works" vs "may not be available"). Test and document actual status.

---

## Phase 6: Validation

### 6.1 Accuracy Sampling (50 words per language)
Manual review of 50-word sample for each of 11 languages:
- Is the extracted root correct?
- Is the morph_type classification accurate?

Report both **coverage rate** AND **accuracy rate**.

### 6.2 1,000-Word Validation Batch
Run 1,000 Arabic words through all 11 adapters with:
- Schema columns present
- Error handling active
- Progress logging

### 6.3 Full 18,807-Word Batch
After validation passes, run the complete word list.

---

## Summary of Changes from Original Plan

| Original | Revised |
|----------|---------|
| Phase 1.3: Tested empty input | Phase 1.3: Fix root=word fallback on valid words |
| Hebrew/Sanskrit strippers | REJECTED - use Wiktextract roots only |
| Greek heuristic stripping | Use Morpheus (already running) |
| Coverage-only validation | Coverage + manual accuracy sampling |
| Schema fix rated LOW | Schema fix is BLOCKING (Phase 1.2) |
| Wiktextract roots in Phase 5 | Moved to Phase 2 (primary source) |
