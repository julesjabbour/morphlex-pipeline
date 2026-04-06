#!/bin/bash
cd /mnt/pgdata/morphlex
python3 pipeline/orchestrator.py --words water fire hand eye stone heart sun moon tree blood --output-format json > /tmp/test_results.json 2>&1
echo "TEST COMPLETE"
python3 pipeline/summarize_test.py /tmp/test_results.json
