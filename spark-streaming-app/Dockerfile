# ------------------------------------------------------------------
# Imagen Custom de PySpark (Ubuntu 22.04 + Java 11 + Spark 3.2.1)
# ------------------------------------------------------------------

# 1. Usamos una base de Ubuntu 22.04 (Jammy)
FROM ubuntu:22.04

# Argumentos para las versiones
ARG SPARK_VERSION=3.2.1
ARG HADOOP_PROFILE=3.2
ARG SPARK_TGZ="spark-${SPARK_VERSION}-bin-hadoop${HADOOP_PROFILE}.tgz"
ARG SPARK_URL="https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/${SPARK_TGZ}"

# Variables de entorno para que todo funcione
ENV DEBIAN_FRONTEND=noninteractive
ENV SPARK_HOME=/opt/spark
ENV PATH=$PATH:$SPARK_HOME/bin
ENV HADOOP_CONF_DIR=/opt/hadoop-config

# Dependencias:
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    python3 \
    python3-pip \
    openjdk-11-jdk && \
    rm -rf /var/lib/apt/lists/*

# Instalación de Spark
RUN curl -fSL ${SPARK_URL} -o /tmp/spark.tgz && \
    tar -xzf /tmp/spark.tgz -C /opt/ && \
    mv /opt/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_PROFILE} ${SPARK_HOME} && \
    rm /tmp/spark.tgz

#Dependencia de kafka
RUN curl -fSL https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/${SPARK_VERSION}/spark-sql-kafka-0-10_2.12-${SPARK_VERSION}.jar -o ${SPARK_HOME}/jars/spark-sql-kafka-0-10.jar && \
    \
    # Cliente Kafka
    curl -fSL https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/2.8.1/kafka-clients-2.8.1.jar -o ${SPARK_HOME}/jars/kafka-clients.jar && \
    \
    # Tokens
    curl -fSL https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/${SPARK_VERSION}/spark-token-provider-kafka-0-10_2.12-${SPARK_VERSION}.jar -o ${SPARK_HOME}/jars/spark-token-provider-kafka-0-10.jar && \
    \
    # dependencias commons para kafka 
    curl -fSL https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.6.2/commons-pool2-2.6.2.jar -o ${SPARK_HOME}/jars/commons-pool2.jar

# Instalación de la librería PySpark
RUN pip3 install pyspark==${SPARK_VERSION}

# 6. Preparamos el directorio de la app y el de la config
WORKDIR /app
COPY stream-writer.py .
RUN mkdir -p ${HADOOP_CONF_DIR}