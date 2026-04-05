#!/bin/bash
sudo -u postgres psql -c "CREATE DATABASE morphlex;" 2>/dev/null || echo "DB exists"
sudo -u postgres psql -c "CREATE USER morphlex_user WITH ENCRYPTED PASSWORD 'morphlex_2026';" 2>/dev/null || echo "User exists"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE morphlex TO morphlex_user;" 2>/dev/null || echo "Grants exist"
sudo -u postgres psql -d morphlex -c "CREATE SCHEMA IF NOT EXISTS lexicon AUTHORIZATION morphlex_user;" 2>/dev/null || echo "Schema exists"
echo "DB setup complete at $(date)"
