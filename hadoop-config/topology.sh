#!/bin/bash

HADOOP_CONF_DIR=${HADOOP_CONF_DIR:-"/opt/hadoop/etc/hadoop"}
MAPPING_FILE="$HADOOP_CONF_DIR/topology-mapping.csv"

# Rack por defecto para cualquier host no encontrado (ej. el namenode)
DEFAULT_RACK="/default-rack"

while [ $# -gt 0 ] ; do
  hostname=$1
  shift
  
  result=$(grep -v "^#" "$MAPPING_FILE" | grep -v "^$" | grep "^$hostname," | cut -d',' -f2)
  
  if [ -n "$result" ]; then
    echo "$result"
  else
    echo "$DEFAULT_RACK"
  fi
done