import os
import redis
import json
import time
import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, year, month, dayofmonth, hour, lit, 
    from_json, to_timestamp, split
)
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, IntegerType, TimestampType
)

# --- Configuración (ajustada para aislamiento) ---
ZONA_ID = os.environ.get("ZONA_ID", "zona_desconocida")
HDFS_PATH = "hdfs://namenode:9000"
TABLE_NAME = "trazas_logs_v5"
OUTPUT_PATH_V3 = "hdfs://namenode:9000/data/trazas_v5"
CHECKPOINT_PATH_V3 = f"hdfs://namenode:9000/checkpoints/trazas_v5/{ZONA_ID}"
KAFKA_BOOTSTRAP_SERVERS = "broker:29092" 
KAFKA_TOPIC = "envoy-logs"

# Configuración Redis (Real-time) - Ahora Global
REDIS_HOST = "global-redis"  
REDIS_PORT = 6379
REDIS_STREAM_KEY = f"trazas:stream:{ZONA_ID}"
RETENTION_SECONDS = 15 * 60  # 15 minutos

# --- Esquema del Log INTERNO ---
log_schema = StructType([
    StructField("date_transaction", StringType(), True),
    StructField("endpoint", StringType(), True),
    StructField("id_consumer", StringType(), True),
    StructField("id_recurso", StringType(), True),
    StructField("id_transaccion", StringType(), True),
    StructField("ip_consumer", StringType(), True),
    StructField("ip_transaccion", StringType(), True),
    StructField("req_body_size", LongType(), True),
    StructField("resp_body_size", LongType(), True),
    StructField("status_response", IntegerType(), True),
    StructField("time_transaction", LongType(), True),
    StructField("tipo_operacion", StringType(), True),
])

wrapper_schema = StructType([
    StructField("@timestamp", StringType(), True), 
    StructField("log", StringType(), True) 
])

def get_redis_client():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def cleanup_hdfs_on_startup(spark, path, checkpoint_path):
    """Limpia carpetas temporales y resuelve conflictos de Lease/FileNotFound."""
    try:
        sc = spark.sparkContext
        Path = spark._jvm.org.apache.hadoop.fs.Path
        FileSystem = spark._jvm.org.apache.hadoop.fs.FileSystem
        conf = sc._jsc.hadoopConfiguration()
        fs = FileSystem.get(conf)

        # 1. Limpiar carpeta _temporary (Causa común de errores de Lease si hubo crash previo)
        temp_path = Path(f"{path}/_temporary")
        if fs.exists(temp_path):
            print(f"[*] Limpiando archivos temporales en HDFS: {temp_path}")
            fs.delete(temp_path, True)
        
        # 2. Asegurar que el path de salida existe
        out_path = Path(path)
        if not fs.exists(out_path):
            fs.mkdirs(out_path)

    except Exception as e:
        print(f"[!] Error durante la limpieza inicial: {e}")

def check_and_reset_checkpoint_if_needed(spark, checkpoint_path):
    """Verifica si el checkpoint está corrupto y lo resetea si es necesario."""
    try:
        # Intento rápido de lectura (simulado)
        Path = spark._jvm.org.apache.hadoop.fs.Path
        FileSystem = spark._jvm.org.apache.hadoop.fs.FileSystem
        fs = FileSystem.get(spark._jsc.hadoopConfiguration())
        cp_path = Path(checkpoint_path)
        
        if not fs.exists(cp_path):
            print(f"Checkpoint no existe, se creará uno nuevo en {checkpoint_path}")
            return True
            
        return False
    except Exception as e:
        print(f"Error al validar checkpoint: {e}")
        return True 

def create_resilient_kafka_stream(spark, checkpoint_path):
    checkpoint_reset = check_and_reset_checkpoint_if_needed(spark, checkpoint_path)
    df_kafka = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", "earliest" if checkpoint_reset else "latest")
        .option("failOnDataLoss", "false")
        .load()
    )
    return df_kafka

def process_batch(batch_df, batch_id):
    row_count = batch_df.count()
    if row_count > 0:
        print(f"--- Batch {batch_id} | Rows: {row_count} ---")
        
        # A. Escritura en HDFS (Histórico)
        batch_df.write \
            .format("parquet") \
            .mode("append") \
            .partitionBy("zona", "year", "month", "day", "hour") \
            .saveAsTable(TABLE_NAME)
        
        # B. Escritura en Redis (Tiempo Real)
        def send_to_redis(rows):
            try:
                r = get_redis_client()
                pipeline = r.pipeline()
                min_id = int((time.time() - RETENTION_SECONDS) * 1000)
                
                for row in rows:
                    data = row.asDict()
                    if data['event_timestamp']:
                        data['event_timestamp'] = data['event_timestamp'].isoformat()
                    pipeline.xadd(REDIS_STREAM_KEY, {"payload": json.dumps(data)}, minid=min_id, approximate=True)
                
                pipeline.execute()
            except Exception as e:
                print(f"Error enviando a Redis: {e}")

        batch_df.foreachPartition(send_to_redis)
        print(f"   -> Datos procesados y enviados a Redis Stream")

def main():
    print(f"Iniciando sesión de Spark en [ZONA: {ZONA_ID}]")

    spark = (
        SparkSession.builder.appName(f"StreamingTrazas-{ZONA_ID}")
        .enableHiveSupport()
        .config("spark.sql.hive.metastore.version", "3.1")
        .config("spark.sql.hive.metastore.jars", "/opt/spark/hive-3.1-libs/*")
        .config("spark.sql.warehouse.dir", "hdfs://namenode:9000/user/hive/warehouse")
        # Optimizaciones para resiliencia en HDFS (Estrategia Anti-Lease)
        .config("spark.sql.sources.commitProtocolClass", "org.apache.spark.sql.execution.datasources.SQLHadoopMapReduceCommitProtocol")
        .config("spark.sql.parquet.fs.optimized.committer.optimization-enabled", "true")
        .config("spark.hadoop.mapreduce.fileoutputcommitter.algorithm.version", "2")
        .config("spark.hadoop.mapreduce.fileoutputcommitter.cleanup-failures.ignored", "true")
        .config("parquet.enable.summary-metadata", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    while True:
        try:
            print(f"[*] [ZONA: {ZONA_ID}] Preparando ejecución del stream...")
            
            # Limpieza de seguridad antes de cada inicio/reinicio
            cleanup_hdfs_on_startup(spark, OUTPUT_PATH_V3, CHECKPOINT_PATH_V3)

            # 1. LEER STREAM
            df_kafka = create_resilient_kafka_stream(spark, CHECKPOINT_PATH_V3)

            # 2. PROCESAR
            df_logs_str = df_kafka.selectExpr("CAST(value AS STRING) as value_str")
            df_outer_parsed = df_logs_str.withColumn("data", from_json(col("value_str"), wrapper_schema))
            df_parsed = df_outer_parsed.withColumn("log_data", from_json(col("data.log"), log_schema))

            df_processed = (
                df_parsed.select("log_data.*") 
                .withColumn("full_endpoint", col("endpoint"))
                .withColumn("endpoint", split(col("full_endpoint"), "\\?").getItem(0))
                .withColumn("query_params", split(col("full_endpoint"), "\\?").getItem(1))
                .withColumn("event_timestamp", to_timestamp(col("date_transaction"), "yyyy-MM-dd'T'HH:mm:ssZ"))
                .withColumn("year", year(col("event_timestamp")))
                .withColumn("month", month(col("event_timestamp")))
                .withColumn("day", dayofmonth(col("event_timestamp")))
                .withColumn("hour", hour(col("event_timestamp")))
                .withColumn("zona", lit(ZONA_ID))
                .drop("full_endpoint")
            )

            # Inicializar Tabla Hive si no existe
            try:
                spark.read.table(TABLE_NAME)
            except:
                print(f"Inicializando tabla {TABLE_NAME}...")
                spark.createDataFrame([], df_processed.schema).write \
                    .format("parquet").mode("ignore") \
                    .partitionBy("zona", "year", "month", "day", "hour") \
                    .option("path", OUTPUT_PATH_V3).saveAsTable(TABLE_NAME)

            # 3. LANZAR QUERY
            print(f"[*] [ZONA: {ZONA_ID}] Stream activo. Esperando datos...")
            query = (
                df_processed.writeStream
                .foreachBatch(process_batch)
                .option("checkpointLocation", CHECKPOINT_PATH_V3)
                .trigger(processingTime="2 minutes")
                .start()
            )

            query.awaitTermination()

        except Exception as e:
            print(f"[!] ERROR CRÍTICO EN RUNTIME: {e}")
            print("[*] Reintentando en 15 segundos...")
            time.sleep(15)
            # El bucle while True reiniciará la query y la limpieza automática

if __name__ == "__main__":
    main()
