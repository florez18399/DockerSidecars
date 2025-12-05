#!/bin/bash
set -e
export HADOOP_CONF_DIR=/opt/hive/conf

# Inicializa Postgres (Schema)
if ! /opt/hive/bin/schematool -dbType postgres -info > /dev/null 2>&1; then
    /opt/hive/bin/schematool -dbType postgres -initSchema
fi

echo "=== Starting Hive Metastore ==="
exec /opt/hive/bin/hive --service metastore