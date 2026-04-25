#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

python3 scripts/diagnose_concept_map_structure.py
