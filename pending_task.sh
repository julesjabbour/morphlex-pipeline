#!/bin/bash
echo "=== ENG-001 VERIFY ==="
sudo -u postgres psql -d morphlex -c "\dt lexicon.*" 2>&1
echo "=== DONE ==="
