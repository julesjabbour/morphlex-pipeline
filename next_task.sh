#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate && python3 scripts/parse_odenet.py && python3 scripts/parse_kenet.py && python3 scripts/parse_latin_wordnet.py && python3 scripts/parse_iwn_sanskrit.py && python3 scripts/parse_agwn_jcuenod.py
