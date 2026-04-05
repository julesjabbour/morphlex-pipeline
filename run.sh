#!/bin/bash
source /mnt/pgdata/morphlex/venv/bin/activate
sudo -u postgres psql -d morphlex -f /mnt/pgdata/morphlex/schema.sql 2>&1
echo "Schema applied at $(date)" >> /tmp/pipeline.log
