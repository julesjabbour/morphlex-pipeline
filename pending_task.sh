#!/bin/bash
# ENG-001: Create database and apply schema
sudo -u postgres psql -c "CREATE DATABASE morphlex;" 2>/dev/null || echo "DB already exists"
sudo -u postgres psql -c "CREATE USER morphlex_user WITH ENCRYPTED PASSWORD 'morphlex_2026';" 2>/dev/null || echo "User already exists"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE morphlex TO morphlex_user;" 2>/dev/null || echo "Grants already exist"
sudo -u postgres psql -d morphlex -c "CREATE SCHEMA IF NOT EXISTS lexicon AUTHORIZATION morphlex_user;" 2>/dev/null || echo "Schema already exists"
sudo -u postgres psql -d morphlex -f /mnt/pgdata/morphlex/schema.sql 2>&1
echo "--- VERIFICATION ---"
sudo -u postgres psql -d morphlex -c "\dt lexicon.*" 2>&1
