#!/bin/bash
cd /mnt/pgdata/morphlex && source venv/bin/activate

# Ensure required packages are installed (silent)
pip install zeyrek compound-split > /dev/null 2>&1

# Run the merge script
python3 scripts/merge_pkls_to_master_v2.py
