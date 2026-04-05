#!/bin/bash
source /mnt/pgdata/morphlex/venv/bin/activate
cd /mnt/pgdata/morphlex

echo "=== ADAPTER TEST (Session 39 fixes) ==="

echo "--- Arabic ---"
python3 -c "
from analyzers.arabic import analyze_arabic
r = analyze_arabic('kitab')
print(f'AR: {len(r)} results')
if r: print(f'  Sample: {r[0]}')
" 2>&1

echo "--- Turkish ---"
python3 -c "
from analyzers.turkish import analyze_turkish
r = analyze_turkish('okudum')
print(f'TR: {len(r)} results')
if r: print(f'  Sample: {r[0]}')
" 2>&1

echo "--- German ---"
python3 -c "
from analyzers.german import analyze_german
r = analyze_german('Handschuh')
print(f'DE: {len(r)} results')
if r: print(f'  Sample: {r[0]}')
" 2>&1

echo "--- English ---"
python3 -c "
from analyzers.english import analyze_english
r = analyze_english('unhappiness')
print(f'EN: {len(r)} results')
if r: print(f'  Sample: {r[0]}')
" 2>&1

echo "--- Latin ---"
python3 -c "
from analyzers.latin import analyze_latin
r = analyze_latin('laudat')
print(f'LA: {len(r)} results')
if r: print(f'  Sample: {r[0]}')
" 2>&1

echo "--- Chinese ---"
python3 -c "
from analyzers.chinese import analyze_chinese
r = analyze_chinese('学习')
print(f'ZH: {len(r)} results')
if r: print(f'  Sample: {r[0]}')
" 2>&1

echo "=== TEST COMPLETE ==="
