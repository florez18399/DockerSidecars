#!/bin/bash
set -e

# Configura HADOOP_CONF_DIR para que Hive encuentre hive-site.xml
export HADOOP_CONF_DIR=/opt/hive/conf

# Imprime la configuración para depurar
echo "=== [DEBUG] Checking hive-site.xml ==="
cat /opt/hive/conf/hive-site.xml
echo "======================================="

# --- LÓGICA DE INICIALIZACIÓN DINÁMICA ---
# Intentamos obtener información del esquema.
# Redirigimos stderr a /dev/null para ocultar el error esperado
if ! /opt/hive/bin/schematool -dbType postgres -info > /dev/null 2>&1; then
    echo "Metastore schema not initialized. Initializing..."
    /opt/hive/bin/schematool -dbType postgres -initSchema -verbose
    echo "Schema initialization complete."
else
    echo "Metastore schema already initialized. Skipping init."
fi
# -----------------------------------------

echo "=== Starting Hive Metastore ==="
# 'exec' reemplaza el proceso de bash con el de Java
exec /opt/hive/bin/hive --service metastore