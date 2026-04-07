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
