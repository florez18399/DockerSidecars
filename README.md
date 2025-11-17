# Pipeline de Análisis de Trazas de Aplicación con Big Data

Este proyecto implementa un pipeline de datos de extremo a extremo para la recolección, procesamiento, almacenamiento y consulta en tiempo real de trazas de solicitudes de una aplicación. La arquitectura está completamente contenerizada utilizando Docker y Docker Compose, demostrando la integración de tecnologías líderes en el ecosistema de Big Data.

## Arquitectura

El flujo de datos a través del sistema es el siguiente:

1.  **Productor de Trazas (`simple-server`)**: Una aplicación de servidor que, a través de un interceptor, captura cada solicitud HTTP y envía los detalles como un mensaje a un tema de Kafka.
2.  **Broker de Mensajería (`Kafka`)**: Actúa como un búfer centralizado y resiliente, recibiendo las trazas en el tópico `envoy-logs`. Desacopla al productor de los consumidores.
3.  **Procesamiento en Streaming (`Spark`)**: Una aplicación de Spark Structured Streaming se suscribe al tópico de Kafka, procesa los mensajes en micro-lotes y los escribe en formato Parquet en el sistema de archivos distribuido HDFS.
4.  **Almacenamiento Distribuido (`Hadoop HDFS`)**: HDFS proporciona un almacenamiento escalable y tolerante a fallos para los archivos Parquet, que contienen los datos de trazas estructurados. El clúster está configurado con `rack awareness` para mejorar la resiliencia de los datos.
5.  **Consulta Federada (`Trino` + `Hive Metastore`)**:
    *   **Hive Metastore**: Almacena los metadatos (esquema, ubicación de archivos) de las tablas que apuntan a los datos en HDFS. Utiliza una base de datos PostgreSQL para su persistencia.
    *   **Trino (antes PrestoSQL)**: Un motor de consultas SQL distribuido que se conecta al Hive Metastore para permitir a los usuarios finales ejecutar consultas interactivas y de alto rendimiento sobre los datos de trazas almacenados en HDFS.

## Componentes del Proyecto

El repositorio está organizado en directorios, cada uno conteniendo la configuración de `docker-compose` para un subsistema específico.

### 1. Servidor de Aplicación (`simple-producer`)

*   **Ubicación**: `/simple-producer`
*   **Descripción**: Contiene la configuración de Docker Compose para levantar el bróker de Kafka. Aunque el nombre del directorio es `simple-producer`, este `docker-compose.yml` también incluye un consumidor de consola (`kafka-consumer`) útil para depuración, que escucha el tópico `envoy-logs`. El servidor de la aplicación real (no mostrado en este archivo) se conectaría a este Kafka para enviar las trazas.

### 2. Clúster Hadoop (`hadoop-cluster`)

*   **Ubicación**: (Asumido) `/hadoop-cluster`
*   **Descripción**: Contiene la configuración para desplegar un clúster HDFS con NameNode, DataNodes y configuración de `rack awareness`. Aquí es donde se almacenarán a largo plazo los archivos Parquet.

### 3. Procesamiento con Spark (`spark-app`)

*   **Ubicación**: (Asumido) `/spark-app`
*   **Descripción**: Incluye la aplicación Spark Structured Streaming y su `docker-compose.yml`. Esta aplicación se conecta a Kafka para leer las trazas y a HDFS para escribirlas.

### 4. Plataforma de Consulta SQL (`trino-hive`)

*   **Ubicación**: (Asumido) `/trino-hive`
*   **Descripción**: Despliega Trino, el Hive Metastore y la base de datos de soporte PostgreSQL. Este stack proporciona la capa de consulta SQL sobre los datos en HDFS.

## Prerrequisitos

Asegúrate de tener instaladas las siguientes herramientas en tu sistema:

*   Docker
*   Docker Compose

Se recomienda asignar suficientes recursos a Docker (al menos 8 GB de RAM) ya que se ejecutarán múltiples servicios.

## Cómo Empezar

Para levantar todo el pipeline, sigue estos pasos en orden. Abre una terminal para cada paso.

### Paso 1: Iniciar Kafka

Navega al directorio del productor y levanta los servicios de Kafka.

```bash
cd /home/wandanauta/Documents/Labs/DockerSidecars/simple-producer/
docker-compose up -d
```

### Paso 2: Iniciar el Clúster Hadoop

En una nueva terminal, inicia el clúster HDFS.

```bash
# Navega al directorio correspondiente
cd ../hadoop-cluster/
docker-compose up -d
```

### Paso 3: Iniciar la Aplicación Spark

Una vez que Kafka y HDFS estén en funcionamiento, puedes iniciar la aplicación de Spark.

```bash
# Navega al directorio correspondiente
cd ../spark-app/
docker-compose up -d
```

### Paso 4: Iniciar Trino y Hive Metastore

Finalmente, levanta la capa de consulta.

```bash
# Navega al directorio correspondiente
cd ../trino-hive/
docker-compose up -d
```

## Uso del Pipeline

### 1. Generar Datos de Trazas

Para generar datos, envía solicitudes HTTP a tu `simple-server`. Por ejemplo, si el servidor está escuchando en el puerto `8080`:

```bash
curl http://localhost:8080/ruta/de/prueba
```

Cada solicitud debería generar un mensaje en el tópico `envoy-logs` de Kafka.

### 2. Verificar Mensajes en Kafka

Puedes usar el consumidor de consola incluido en `simple-producer/docker-compose.yml` para ver los mensajes en tiempo real.

```bash
docker logs -f kafka-consumer
```

### 3. Consultar los Datos con Trino

Una vez que la aplicación Spark haya procesado algunos datos y los haya escrito en HDFS, puedes consultarlos usando un cliente de Trino.

1.  Conéctate a Trino a través de su CLI o una herramienta de BI compatible (como DBeaver, Superset, etc.) usando el puerto `8080` (o el que hayas expuesto para Trino).
2.  Ejecuta consultas SQL sobre la tabla que Hive ha catalogado. El nombre del catálogo probablemente será `hive`.

```sql
-- Ejemplo de consulta en Trino
SELECT *
FROM hive.logs.envoy_logs
LIMIT 100;

-- Contar solicitudes por endpoint
SELECT request_path, COUNT(*) as total_requests
FROM hive.logs.envoy_logs
GROUP BY request_path
ORDER BY total_requests DESC;
```

## Detener el Entorno

Para detener y eliminar todos los contenedores, ejecuta el siguiente comando en cada uno de los directorios:

```bash
docker-compose down
```