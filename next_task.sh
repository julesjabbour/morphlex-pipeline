#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

# Run the synset mismatch diagnostic
python3 scripts/diagnose_synset_mismatch.py
