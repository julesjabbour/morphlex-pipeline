#!/bin/bash
# Run setup first (creates DB if not exists)
bash /mnt/pgdata/morphlex/setup_db.sh 2>&1

# Then apply schema
source /mnt/pgdata/morphlex/venv/bin/activate
sudo -u postgres psql -d morphlex -f /mnt/pgdata/morphlex/schema.sql 2>&1
echo "Pipeline run complete at $(date)" >> /tmp/pipeline.log
