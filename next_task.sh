#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

python3 scripts/verify_sanskrit_turkish_overlap.py
