# Pipeline de Análisis de Trazas de Aplicación con Big Data

Este proyecto implementa un pipeline de datos de extremo a extremo para la recolección, procesamiento, almacenamiento y consulta en tiempo real de trazas de solicitudes de una aplicación. La arquitectura está completamente contenerizada utilizando Docker y Docker Compose, demostrando la integración de tecnologías líderes en el ecosistema de Big Data.

## Arquitectura

El flujo de datos a través del sistema es el siguiente:

1.  **Generación de Trazas (`server-mesh`)**: Las aplicaciones (ej. `app1`, `app2`) se ejecutan junto a un sidecar de Envoy. Envoy intercepta todo el tráfico de red, genera logs de acceso y los reenvía.
2.  **Recolección de Logs (`Fluent-Bit`)**: Otro sidecar, Fluent Bit, recolecta los logs de Envoy y los envía a un tópico de Kafka.
3.  **Broker de Mensajería (`Kafka`)**: Actúa como un búfer centralizado y resiliente, recibiendo las trazas en el tópico `envoy-logs`. Desacopla a los productores de los consumidores.
4.  **Procesamiento en Streaming (`Spark`)**: Una aplicación de Spark Structured Streaming se suscribe al tópico de Kafka, procesa los mensajes en micro-lotes y los escribe en formato Parquet en el sistema de archivos distribuido HDFS.
5.  **Almacenamiento Distribuido (`Hadoop HDFS`)**: HDFS proporciona un almacenamiento escalable y tolerante a fallos para los archivos Parquet. El clúster consiste en un NameNode y DataNodes desplegados dinámicamente.
6.  **Consulta Federada (`Trino` + `Hive Metastore`)**:
    *   **Hive Metastore**: Almacena los metadatos (esquema, ubicación de archivos) de las tablas que apuntan a los datos en HDFS.
    *   **Sincronizador de Metadatos**: Un script se ejecuta periódicamente para que Hive reconozca las nuevas particiones de datos escritas por Spark.
    *   **Trino (antes PrestoSQL)**: Un motor de consultas SQL distribuido que se conecta al Hive Metastore para permitir a los usuarios ejecutar consultas interactivas sobre los datos.

## 🚀 Simulación de Comportamiento y Generación de Tráfico

El proyecto incluye una capa de simulación avanzada para probar patrones de observabilidad bajo diversas condiciones.

### Escenarios de Aplicación
Las aplicaciones pueden desplegarse con modos de `SCENARIO` específicos (configurados mediante variables de entorno en `deploy-zone.sh`):
- **NORMAL**: Rendimiento estándar (latencia de 100-300ms).
- **DEGRADED**: Simulación de alta latencia (+3s por solicitud).
- **CHAOS**: Alta tasa de fallos (50% de probabilidad de error 500).
- **BURSTY**: Picos de latencia intermitentes (retrasos aleatorios de 5s).

### Cliente de Tráfico Mock
Un componente dockerizado en Python (`tests/mock-client`) que:
1. **Auto-descubre** zonas activas escaneando las configuraciones de los gateways.
2. **Simula Personas**:
   - `user-stable`: Tráfico de navegación regular.
   - `user-heavy`: Solicitudes de alta frecuencia.
   - `user-malicious`: Activa endpoints de error y autenticación inválida.
   - `user-scanner`: Prueba rutas inexistentes (generación de 404).
3. **Trazabilidad de Extremo a Extremo**: Inyecta `X-CONSUMER-ID` para seguimiento en Trino/Grafana.

Para iniciar/detener el tráfico:
```bash
cd tests/mock-client
docker compose up -d  # Iniciar
docker compose down   # Detener
```

## Estructura del Proyecto

El repositorio está organizado en los siguientes directorios principales:

*   `zona-deploy/`: Contiene la lógica para desplegar "zonas" completas. Cada subdirectorio representa un componente de la infraestructura.
    *   `server-mesh/`: Define el patrón de sidecar con Envoy y Fluent-Bit para las aplicaciones.
    *   `streaming-kafka/`: Despliega el bróker de Kafka.
    *   `spark-streaming-app/`: Despliega la aplicación de procesamiento con Spark.
    *   `datanode/`: Plantilla para desplegar datanodes de HDFS.
    *   `deploy-zone.sh` y `destroy-zone.sh`: Scripts para crear y destruir una zona completa.
*   `hadoop-cluster/`: Define el servicio HDFS NameNode.
*   `trino-sql/`: Despliega el stack de consulta con Trino, Hive Metastore y el sincronizador de particiones.
*   `tests/mock-client/`: Cliente generador de tráfico sintético.

## Prerrequisitos

*   Docker y Docker Compose
*   Asegúrate de que Docker tenga asignados suficientes recursos (se recomiendan +8GB de RAM).

## Cómo Empezar

El despliegue está automatizado a través de scripts que gestionan "zonas".

### Paso 1: Levantar Infraestructura Base
Asegúrate de tener el `hadoop-cluster`, `main-gateway`, `redis-streaming` y `trino-sql` activos.

### Paso 2: Desplegar Zonas con Escenarios
Puedes desplegar múltiples zonas pasando el nombre de la zona como argumento y configurando los escenarios de las apps mediante variables de entorno:

```bash
cd zona-deploy/
# Zona 1 estable
APP1_SCENARIO=NORMAL APP2_SCENARIO=NORMAL ./deploy-zone.sh zone1
# Zona 2 inestable
APP1_SCENARIO=CHAOS APP2_SCENARIO=DEGRADED ./deploy-zone.sh zone2
```

## Detener el Entorno

Para detener una zona específica:
```bash
cd zona-deploy/
./destroy-zone.sh zone1
```
