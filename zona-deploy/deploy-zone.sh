#!/bin/bash
set -e 

if [ -f .env ]; then
  # Cargar variables del .env
  export $(grep -v '^#' .env | xargs)
else
  echo "❌ No se encontró archivo .env"
  exit 1
fi

# El primer argumento sobreescribe la ZONE_ID del .env
if [ ! -z "$1" ]; then
  export ZONE_ID=$1
  # Derivar ZONE_NETWORK_NAME del ZONE_ID (ej: zone1 -> zone_1_net)
  Z_NUM=$(echo $ZONE_ID | tr -dc '0-9')
  export ZONE_NETWORK_NAME="zone_${Z_NUM}_net"
fi

echo "🚀 Desplegando zona $ZONE_ID (Red: $ZONE_NETWORK_NAME)..."

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
echo "Desplegando Infraestructura para $ZONE_ID (Kafka: $KAFKA_PORT_EXT)"

# Asegurar que Redis Global esté arriba (desde la raíz del proyecto)
echo "Asegurando Redis Global..."
(cd .. && docker compose -f redis-streaming/docker-compose.yml up -d)

echo "Levantando Infraestructura (Kafka)..."
docker compose -p "${ZONE_ID}-infra" -f streaming-kafka/docker-compose.yml up -d

# 4. Creando malla de aplicaciones
echo "🚀 Desplegando Aplicaciones y configurando Gateway..."
Z_NUM=$(echo $ZONE_ID | tr -dc '0-9')
# Offset por zona para evitar colisiones de puertos (ej: zone1 -> 18100, zone2 -> 18200)
CURRENT_PORT=$((18000 + Z_NUM * 100))

# Configurar host de Kafka para los sidecars (Fluent Bit)
export KAFKA_BROKER_HOST="${ZONE_ID}-broker"

# Preparar archivo de configuración de Nginx de zona
ZONE_NGINX_CONF="zone-gateway/nginx.conf"
cat <<EOF > "$ZONE_NGINX_CONF"
events { worker_connections 1024; }
http {
    server {
        listen 80;
EOF

for app_dir in ./server-mesh/apps/*; do
    if [ -d "$app_dir" ]; then
        export APP_NAME=$(basename "$app_dir")
        export HOST_PORT=$CURRENT_PORT

        # Dinámicamente obtener el SCENARIO para esta app (ej: APP1_SCENARIO)
        APP_UPPER=$(echo "$APP_NAME" | tr '[:lower:]' '[:upper:]')
        VAR_NAME="${APP_UPPER}_SCENARIO"
        export SCENARIO="${!VAR_NAME:-NORMAL}"

        echo " -> App: $APP_NAME (Port: $HOST_PORT, Scenario: $SCENARIO)"

        docker compose -f server-mesh/docker-compose.yml \
            -p "${ZONE_ID}-${APP_NAME}" \
            up -d --build

        # Agregar ruta al Nginx de zona (apunta al sidecar Envoy)
        cat <<EOF >> "$ZONE_NGINX_CONF"
        location /${APP_NAME} {
            proxy_pass http://${ZONE_ID}-${APP_NAME}-envoy:8080;
            proxy_http_version 1.1;
        }
EOF
        CURRENT_PORT=$((CURRENT_PORT + 1))
    fi
done

# Cerrar configuración de Nginx de zona
cat <<EOF >> "$ZONE_NGINX_CONF"
    }
}
EOF

echo "🌐 Levantando API Gateway de Zona..."
docker compose -f zone-gateway/docker-compose.yml -p "${ZONE_ID}-gateway" up -d

# 5. Registrar zona en el Main Gateway
echo "📝 Registrando zona $ZONE_ID en el Gateway Principal..."
MAIN_CONF_DIR="../main-gateway/confs"
mkdir -p "$MAIN_CONF_DIR"

cat <<EOF > "${MAIN_CONF_DIR}/${ZONE_ID}.conf"
location /${ZONE_ID}/ {
    proxy_pass http://${ZONE_ID}-api-gateway:80/;
}
EOF

# Recargar Nginx Principal si está corriendo
docker exec main-api-gateway nginx -s reload 2>/dev/null || echo "⚠️ Main Gateway no detectado, asegúrate de levantarlo en la raíz."

# 6. Creando aplicación Spark Structured Streaming
echo "Levantando Spark Streaming..."
docker compose -f spark-streaming-app/docker-compose.yml -p "${ZONE_ID}-spark" up -d --build

echo "✅ Zona $ZONE_ID desplegada correctamente."
