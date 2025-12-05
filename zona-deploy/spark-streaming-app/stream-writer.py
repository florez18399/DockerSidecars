import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, year, month, dayofmonth, hour, lit, 
    from_json, to_timestamp  # ¡Ya no necesitamos regexp_extract!
)
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, IntegerType, TimestampType
)

# --- Configuración (sin cambios) ---
ZONA_ID = os.environ.get("ZONA_ID", "zona_desconocida")
HDFS_PATH = "hdfs://namenode:9000"
TABLE_NAME = "trazas_logs_v3"
OUTPUT_PATH_V3 = "hdfs://namenode:9000/data/trazas_v3"
CHECKPOINT_PATH_V3 = "hdfs://namenode:9000/checkpoints/trazas_v3"
KAFKA_BOOTSTRAP_SERVERS = "broker:29092" 
KAFKA_TOPIC = "envoy-logs"

# --- Esquema del Log INTERNO (El que ya teníamos) ---
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

# Esquema del Log EXTERIOR 
# {"@timestamp": "...", "log": "..."}
wrapper_schema = StructType([
    StructField("@timestamp", StringType(), True), 
    StructField("log", StringType(), True) 
])

def check_and_reset_checkpoint_if_needed(checkpoint_path):
    """Verifica si el checkpoint está corrupto y lo resetea si es necesario"""
    try:
        # Verificar si el checkpoint existe y tiene metadata válida
        test_df = spark.readStream.format("kafka") \
            .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
            .option("subscribe", KAFKA_TOPIC) \
            .option("startingOffsets", "latest") \
            .option("failOnDataLoss", "false") \
            .load()
        
        # Intentar una consulta simple para validar
        test_query = test_df.writeStream \
            .format("memory") \
            .queryName("test_query") \
            .outputMode("append") \
            .option("checkpointLocation", checkpoint_path) \
            .start()
        
        test_query.stop()
        return False  # Checkpoint está bien
        
    except Exception as e:
        print(f"Checkpoint corrupto detectado: {e}")
        print("Reseteando checkpoint...")
        
        # Eliminar checkpoint corrupto
        try:
            subprocess.run([
                "hdfs", "dfs", "-rm", "-r", checkpoint_path
            ], check=True)
        except:
            print(f"No se pudo eliminar checkpoint: {checkpoint_path}")
        
        return True 

def create_resilient_kafka_stream(spark, checkpoint_path):
    """Crea un stream de Kafka con recuperación automática"""
    
    # Verificar checkpoint antes de iniciar
    checkpoint_reset = check_and_reset_checkpoint_if_needed(checkpoint_path)
    
    df_kafka = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", "earliest" if checkpoint_reset else "latest")
        .option("failOnDataLoss", "false")
        # Configuraciones avanzadas de resiliencia
        .option("kafka.session.timeout.ms", "30000")
        .option("kafka.request.timeout.ms", "40000")
        .option("kafka.metadata.max.age.ms", "30000")
        .option("kafka.max.poll.records", "500")
        .option("kafka.retry.backoff.ms", "1000")
        .option("kafka.reconnect.backoff.ms", "1000")
        .option("kafka.reconnect.backoff.max.ms", "10000")
        .load()
    )
    
    return df_kafka

def main():
    print(f"Iniciando sesión de Spark en [ZONA: {ZONA_ID}]")

    spark = (
        SparkSession.builder.appName(f"StreamingTrazas-{ZONA_ID}")
        .enableHiveSupport()
        .config("spark.sql.hive.metastore.version", "3.1")
        .config("spark.sql.hive.metastore.jars", "/opt/spark/hive-3.1-libs/*")
        .config("spark.sql.warehouse.dir", "hdfs://namenode:9000/user/hive/warehouse")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    # 1. LEER STREAM DESDE KAFKA
    df_kafka = create_resilient_kafka_stream(spark, CHECKPOINT_PATH_V3)

    # 2. PROCESAR LOS DATOS DE KAFKA
  
    df_logs_str = df_kafka.selectExpr("CAST(value AS STRING) as value_str")

    # Parseo el JSON EXTERIOR
    df_outer_parsed = df_logs_str.withColumn(
        "data", 
        from_json(col("value_str"), wrapper_schema)
    )

    # Parseo del JSON INTERIOR 
    df_parsed = df_outer_parsed.withColumn(
        "log_data", 
        from_json(col("data.log"), log_schema) 
    )

    #Definición de particiones
    df_final = (
        df_parsed.select("log_data.*") 
        .withColumn("event_timestamp", to_timestamp(col("date_transaction"), "yyyy-MM-dd'T'HH:mm:ssZ"))
        .withColumn("year", year(col("event_timestamp")))
        .withColumn("month", month(col("event_timestamp")))
        .withColumn("day", dayofmonth(col("event_timestamp")))
        .withColumn("hour", hour(col("event_timestamp")))
        .withColumn("zona", lit(ZONA_ID))
    )

    try:
        spark.read.table(TABLE_NAME)
        print(f"La tabla {TABLE_NAME} ya existe. Continuando con el Stream...")
    except:
        print(f"La tabla {TABLE_NAME} NO existe. Inicializando estructura...")
        
        empty_df = spark.createDataFrame([], df_final.schema)
        
        empty_df.write \
            .format("parquet") \
            .mode("ignore") \
            .partitionBy("zona", "year", "month", "day", "hour") \
            .option("path", OUTPUT_PATH_V3) \
            .saveAsTable(TABLE_NAME)
            
        print(f"Tabla {TABLE_NAME} creada exitosamente.")

    # Escritura en HDFS
    print(f"\n[SINK-HIVE-EXTERNAL] Iniciando stream para [ZONA: {ZONA_ID}]")
    print(f"   -> Output: {OUTPUT_PATH_V3}")
    print(f"   -> Checkpoint: {CHECKPOINT_PATH_V3}")
    
    query_hdfs = (
        df_final.writeStream
        .format("parquet")
        .outputMode("append")
        .partitionBy("zona", "year", "month", "day", "hour")
        .option("path", OUTPUT_PATH_V3)
        .option("checkpointLocation", CHECKPOINT_PATH_V3)
        .option("parquet.block.size", 134217728)  # 128MB blocks
        .option("parquet.page.size", 1048576)     # 1MB pages
        .option("parquet.dictionary.enabled", "true")
        .trigger(processingTime="1 minute")
        .toTable(TABLE_NAME)
    )

    print(f"Stream para [ZONA: {ZONA_ID}] iniciado.")
    query_hdfs.awaitTermination()

if __name__ == "__main__":
    main()