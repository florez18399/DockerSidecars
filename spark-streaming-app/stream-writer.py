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
OUTPUT_PATH = f"{HDFS_PATH}/data/trazas_parquet" # Ajusté tu ruta de /data/log_centralizer
CHECKPOINT_PATH = f"{HDFS_PATH}/checkpoints/trazas_{ZONA_ID}"
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

def main():
    print(f"Iniciando sesión de Spark en [ZONA: {ZONA_ID}]")
    spark = (
        SparkSession.builder.appName(f"StreamingTrazas-{ZONA_ID}")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    # 1. LEER STREAM DESDE KAFKA
    df_kafka = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", "latest")
        .load()
    )

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

    # Escritura en HDFS
    print(f"\n[SINK-HDFS] Iniciando stream principal para [ZONA: {ZONA_ID}]")
    print(f"   -> Output: {OUTPUT_PATH}")
    print(f"   -> Checkpoint: {CHECKPOINT_PATH}")
    
    query_hdfs = (
        df_final.writeStream
        .format("parquet")
        .outputMode("append")
        .partitionBy("year", "month", "day", "hour", "zona")
        .option("path", OUTPUT_PATH) 
        .trigger(processingTime="1 minute")
        .option("checkpointLocation", CHECKPOINT_PATH)
        .start()
    )

    print(f"Stream para [ZONA: {ZONA_ID}] iniciado.")
    query_hdfs.awaitTermination()

if __name__ == "__main__":
    main()