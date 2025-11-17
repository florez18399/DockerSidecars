#!/bin/bash

# Ruta al archivo de mapeo (está en la misma carpeta)
HADOOP_CONF_DIR=${HADOOP_CONF_DIR:-"/opt/hadoop/etc/hadoop"}
MAPPING_FILE="$HADOOP_CONF_DIR/topology-mapping.csv"

# Rack por defecto para cualquier host no encontrado (ej. el namenode)
DEFAULT_RACK="/default-rack"

# Hadoop puede pasar varios hostnames a la vez.
# Leemos cada uno de los argumentos ($@).
while [ $# -gt 0 ] ; do
  hostname=$1
  shift
  
  # Buscar el hostname en el archivo de mapeo
  # 1. Ignorar comentarios (#) y líneas vacías
  # 2. Buscar la línea que COMIENZA con el hostname + una coma
  # 3. Extraer el rack (la parte después de la coma)
  result=$(grep -v "^#" "$MAPPING_FILE" | grep -v "^$" | grep "^$hostname," | cut -d',' -f2)
  
  if [ -n "$result" ]; then
    # Encontrado: Imprime el rack
    echo "$result"
  else
    # No encontrado: Imprime el rack por defecto
    echo "$DEFAULT_RACK"
  fi
done