#!/bin/bash
set -e

if [ -f .env ]; then
  export $(cat .env | xargs)
else
  echo "No se encontró archivo .env"
  exit 1
fi

echo "🧹 Iniciando destrucción de zona $ZONE_ID..."

# 1. Borrar Spark Structured Streaming
echo "🗑️ Eliminando Spark Streaming..."
docker compose -f spark-streaming-app/docker-compose.yml -v -p "${ZONE_ID}-spark" down --remove-orphans || true

# 2. Borrar Apps de la malla
echo "🗑️ Eliminando aplicaciones de la malla..."
for app_dir in ./server-mesh/apps/*; do
    if [ -d "$app_dir" ]; then
        export APP_NAME=$(basename "$app_dir")
        echo " -> App: $APP_NAME"
        docker compose -f server-mesh/docker-compose.yml \
            -p "${ZONE_ID}-${APP_NAME}" \
            down --remove-orphans || true
    fi
done

# 3. Borrar Infra Kafka
echo "Eliminando infraestructura Kafka..."
docker compose -p "${ZONE_ID}-infra" -f streaming-kafka/docker-compose.yml down --remove-orphans || true

# 4. Borrar DataNode
echo "Eliminando DataNode $ZONE_ID..."
docker compose -v -f datanode/docker-compose.yml \
    -p "${ZONE_ID}-hdfs" \
    down --remove-orphans || true

# 5. Remover entradas de topología
CSV_FILE="../hadoop-config/topology-mapping.csv"
echo "Eliminando entradas de topología HDFS para $ZONE_ID..."

sed -i "/${ZONE_ID}-datanode/d" "$CSV_FILE"
sed -i "/${ZONE_ID}-spark-processor/d" "$CSV_FILE"

# 6. Remover red
echo "Eliminando red: $ZONE_NETWORK_NAME..."
docker network rm "$ZONE_NETWORK_NAME" 2>/dev/null || true

# 7. Actualizando NameNode
echo "Forzando al NameNode a actualizar la topología..."
docker exec namenode hdfs dfsadmin -refreshNodes

echo "Zona $ZONE_ID eliminada por completo."
