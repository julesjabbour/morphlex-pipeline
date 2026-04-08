# Morphlex Pipeline - Project Memory

## PROJECT ARCHITECTURE

- **All code lives at `/mnt/pgdata/morphlex` on the VM.** Never use `/home/user/` for anything.
- **Venv:** `/mnt/pgdata/morphlex/venv` — always activate before running Python.
- **11 language adapters in `analyzers/`:** arabic.py, turkish.py, german.py, english.py, latin.py, chinese.py, japanese.py, hebrew.py, sanskrit.py, greek.py, pie.py
- **Pipeline scripts in `pipeline/`:** orchestrator.py, build_forward_translations.py, build_wiktextract_index.py, etymology_enricher.py, translator.py, wiktextract_loader.py
- **Data files in `data/`:** forward_translations.pkl, etymology_index.pkl, wiktextract_index.pkl, raw-wiktextract-data.jsonl.gz
- **PostgreSQL:** database `morphlex`, user `morphlex_user`, password `morphlex_2026`, always use `-h localhost` for TCP auth
- **Docker Morpheus container for Latin/Greek:** `http://localhost:1315/latin/{word}` and `/greek/{word}`

## ANCHOR LANGUAGE DECISION

- **Arabic is the anchor language.** Arabic concepts go in, get translated outward to 10 other languages via forward_translations.pkl.
- `forward_translations.pkl` must be Arabic-to-X (en, tr, de, la, zh, ja, he, sa, grc, ine-pro).
- All non-Arabic languages must be in the orchestrator's `needs_translation` set.
- The Arabic adapter (CAMeL) receives Arabic directly. Every other adapter receives a translated word in its own language.

## CODING CONVENTIONS

- All changes go directly to main branch. Do not create feature branches unless explicitly told to.
- Always run `bash -n` on all shell scripts before committing.
- `next_task.sh` must always start with `cd /mnt/pgdata/morphlex && source venv/bin/activate`.
- **DO NOT suppress any library warnings — warnings must always be visible in output.**
- Latin words from forward_translations.pkl have macrons — always strip diacritics before passing to Morpheus.
- Use `git fetch origin && git reset --hard origin/main` instead of `git pull --ff-only`.

## TEST FORMAT

- Per-language results with counts: `ar : 10 results [OK]`
- TOTAL line at end: `TOTAL: 146 results from 10 words x 11 languages`
- Include start/end timestamps for timing tests.
- All output to stdout — no file redirection, no JSON mode, no separate parsing scripts.

## SLACK REPORTING

- Results go to #bh-pipeline channel.
- Keep output concise — Slack truncates long messages.
- If output would be long, write to a .md file and mention the path.

## CRON AND INFRASTRUCTURE RULES

*Added after Session 44 — 9-hour zombie loop incident*

run.sh MUST have these three safeguards before the cron is re-enabled. All three are mandatory, no exceptions:

1. **flock lock file** — `flock -n /tmp/morphlex_run.lock` at the top. If locked, exit 0 silently. Prevents concurrent runs.

2. **Marker file** — after next_task.sh succeeds, create `/tmp/morphlex_markers/done_$(md5sum next_task.sh | cut -d' ' -f1)`. Before running next_task.sh, check if this marker exists. If it does, exit 0 silently. Prevents re-running the same task. NEVER use rename/delete of git-tracked files as a completion mechanism — `git reset --hard` restores them.

3. **Silent exit when no task** — if next_task.sh does not exist after git sync, exit 0 with no Slack message.

### Additional rules

- Always push directly to main. Never push to a branch unless explicitly told to. The cron only pulls main.
- Every bot message must include the git HEAD hash in stdout so we can verify what code actually ran.
- Check Start time vs current time in bot output. If the gap is more than 5 minutes, there is a process backlog. Stop and diagnose.
- The pkl rebuild reads 2.4GB into memory. Never run more than one instance at a time on this 8GB VM. The flock prevents this but be aware of the constraint.
- Claude Code cannot SSH into the VM or use gcloud. The only way to execute code on the VM is through next_task.sh via the cron. Plan accordingly.

## OUTPUT RULES

Never truncate Slack output. If output exceeds 3500 chars, split into multiple messages. Always write full output to /mnt/pgdata/morphlex/reports/ as timestamped .md file. Never suppress warnings or errors in any Python file or shell script — all errors must be visible in output.

## ANTI-FRAUD RULES

**ZERO HARDCODING RULE:** Never create dictionaries, lookup tables, sets, or lists that map specific words to specific results. Every result must come from a real tool (CAMeL, Zeyrek, Morpheus, Hspell, Vidyut, etc.) or from data files (pkl, wiktextract). If a tool is not installed, install it. If it cannot be installed, report the exact error with evidence. Returning correct answers for known test words while failing on unknown words is a critical failure.

**ZERO SHORTCUT RULE:** If a task requires installing a tool and you cannot install it from your sandbox, put the install commands in next_task.sh so the VM runs them. Do not substitute a hardcoded workaround. Do not substitute a rule-based heuristic. Do not substitute a dictionary. The tool either works or it doesn't.

**TESTING RULE:** All tests must include words that have never appeared in any previous message. If a test only passes on words from the original task description, the implementation is fraudulent.

**NO BROKEN PUSHES RULE:** Test in your session before pushing to main. If it segfaults, fix it before pushing. If it returns empty for everything, fix it before pushing. If it returns the same string for every word, fix it before pushing. Push to main ONLY when it works.

**MARKER RULE:** Every push to main that needs cron to run MUST include an updated next_task.sh with a new marker hash. If you forget, cron won't pick it up.
