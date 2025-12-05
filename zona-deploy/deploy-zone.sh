#!/bin/bash
set -e 

if [ -f .env ]; then
  export $(cat .env | xargs)
else
  echo "❌ No se encontró archivo .env"
  exit 1
fi

# 1. Crear Red Base
docker network create $ZONE_NETWORK_NAME 2>/dev/null || true

# 2. Agregando Datanode
CSV_FILE="../hadoop-config/topology-mapping.csv"
echo "Registrando zona en topología HDFS..."
if ! grep -q "${ZONE_ID}-datanode" "$CSV_FILE"; then
  echo "${ZONE_ID}-datanode,/rack/${ZONE_ID}" >> "$CSV_FILE"
fi

if ! grep -q "${ZONE_ID}-spark-processor" "$CSV_FILE"; then
  echo "${ZONE_ID}-spark-processor,/rack/${ZONE_ID}" >> "$CSV_FILE"
fi

echo "🐘 Levantando DataNode para $ZONE_ID..."
docker compose -f datanode/docker-compose.yml \
    -p "${ZONE_ID}-hdfs" \
    up -d


# 3. Desplegando KAFKA

Z_NUM=$(echo $ZONE_ID | tr -dc '0-9')
export KAFKA_PORT_EXT=$((9090 + Z_NUM * 2))
echo "Desplegando Kafka para $ZONE_ID en puerto host: $KAFKA_PORT_EXT"

echo "Levantando Infraestructura (Kafka)..."
docker compose -p "${ZONE_ID}-infra" -f streaming-kafka/docker-compose.yml up -d

# 4. Creando malla de aplicaciones
echo "🚀 Desplegando Aplicaciones..."
CURRENT_PORT=$INITIAL_PORT

for app_dir in ./server-mesh/apps/*; do
    if [ -d "$app_dir" ]; then
        export APP_NAME=$(basename "$app_dir")
        export HOST_PORT=$CURRENT_PORT
        
        echo " -> App: $APP_NAME (Port: $HOST_PORT)"
        
        docker compose -f server-mesh/docker-compose.yml \
            -p "${ZONE_ID}-${APP_NAME}" \
            up -d --build

        CURRENT_PORT=$((CURRENT_PORT + 1))
    fi
done

# 5. Creando aplicación Spark Structured Streaming
echo "Levantando Spark Streaming..."
docker compose -f spark-streaming-app/docker-compose.yml -p "${ZONE_ID}-spark" up -d --build

echo "✅ Zona $ZONE_ID desplegada correctamente."