Session Summary: Observability & Traffic Simulation


  1. Strategic Refactoring:
   * Intelligent Mock Apps: Refactored the Node.js
     applications (app1, app2) to support dynamic scenarios
     (NORMAL, DEGRADED, CHAOS, BURSTY) controlled via
     environment variables.
   * Elastic Orchestration: Updated deploy-zone.sh and
     destroy-zone.sh to accept ZONE_ID as an argument,
     allowing for the deployment of multiple independent zones
     with automatic port offsetting (100 ports per zone).


  2. Traffic Generation:
   * Mock Client: Built and dockerized a Python-based traffic
     generator (tests/mock-client) that automatically
     discovers active zones and generates diverse traffic
     patterns using different "user personas" (Normal, Heavy,
     Attacker, Scanner).
   * Tracing Integration: The client injects X-CONSUMER-ID
     headers, allowing for end-to-end tracing through Envoy,
     Kafka, Spark, and HDFS.


  3. Active Environment:
   * Zone 1: app1 (Normal) and app2 (Degraded) are running on
     ports 18100-18101.
   * Zone 2: app1 (Chaos) and app2 (Bursty) are running on
     ports 18200-18201.
   * Real-time Traffic: The mock-traffic-generator is
     currently running in the background, feeding data into
     your pipeline.


  To resume later:
   - Check the traffic logs: docker logs -f
     mock-traffic-generator
   - Analyze the data in Trino: The trazas_logs table should
     now contain a mix of 200, 404, and 500 status codes with
     varying response times.
   - Experiment with new zones: ./deploy-zone.sh zone3 will
     automatically spin up a new environment with its own
     infra.


  The project is now a fully dynamic laboratory for
  distributed systems observability!

---

Session Summary: Self-Healing & Pipeline Resilience (Updated)

  1. Spark Processor Stability (Self-Healing):
   * Runtime Recovery: Implemented a 'while True' loop in stream-writer.py that catches critical exceptions (like HDFS lease errors) and automatically restarts the query after 15 seconds.
   * Automated Cleanup: Added a startup routine to delete the HDFS '_temporary' folder and corrupt checkpoints, preventing the 'FileNotFoundException' and 'Holder does not have open files' errors from previous crashes.
   * Docker Resilience: Updated spark-streaming-app/docker-compose.yml with 'restart: unless-stopped' to handle full JVM crashes.

  2. HDFS Write Optimizations:
   * Robust Committer: Configured SQLHadoopMapReduceCommitProtocol with algorithm version 2 and disabled Parquet summary metadata to improve performance and reliability on HDFS writes.
   * Topology Fix: Resolved a 'Permission denied' issue in the Namenode by granting execution permissions to 'topology.sh' and fixing HDFS node resolution.

  3. Active Environment:
   * Zone 1 & 2: Spark processors are now active and self-healing, processing traffic from Kafka into Hive (trazas_logs_v5) and Redis.
   * Verification: The pipeline is processing data end-to-end and recovering automatically from transient HDFS lease conflicts.

  To resume later:
   - Monitor Spark health: docker logs -f zone1-spark-processor
   - Check HDFS contents: docker exec namenode hdfs dfs -ls /data/trazas_v5
   - Verify Redis real-time streams: Use 'XREAD' on the global-redis container to see live traffic flowing.

---

Session Summary: Trino Scalability & HDFS Optimization

  1. Multi-Node Trino Cluster (v448):
   * Architecture: Scaled from a single node to a 3-node cluster (1 Coordinator, 2 Workers) with ~7.5GB total RAM allocation.
   * Discovery Fix: Resolved a critical registration issue where workers weren't showing up by ensuring unique 'node.id' values across all containers.
   * JVM & Config Tuning: Optimized memory limits (1.5GB Heap for Coord, 2GB for Workers) and fixed deprecated/removed Trino 448 properties.

  2. HDFS Write Consolidation:
   * Small File Mitigation: Updated the Spark 'stream-writer.py' trigger interval from 10 seconds to 2 minutes. This targets ~128MB Parquet blocks, significantly reducing HDFS Namenode metadata pressure and Trino query latency.
   * Catalog Optimization: Enabled aggressive Hive metastore caching (10m TTL) and name-based column mapping in 'hive.properties' to speed up schema discovery.

  3. Active Environment:
   * Cluster Status: All 3 Trino nodes are 'active' and correctly registered in 'system.runtime.nodes'.
   * Data Pipeline: Zones 1 & 2 are now writing consolidated Parquet files to HDFS, ready for high-performance analytics.

  To resume later:
   - Verify Cluster: 'docker exec trino trino --execute "SELECT * FROM system.runtime.nodes;"'
   - Benchmark Latency: Run 'SELECT count(*) FROM hive.default.trazas_logs_v5;' to verify the speed improvement from consolidated files.
   - Connect Grafana: Re-point the Grafana Trino datasource to the new coordinator for multi-zone dashboards.
