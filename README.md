# Prometheus Neo4j Exporter
A Prometheus exporter for Neo4j including long-running queries and database statuses.

## Installation

### Docker

Start the container, specify the address of the Neo4j cluster in the NEO4J_SERVICE environment variable:

```bash
docker run --rm -itd --name neo4j_exporter -p 9099:5000 -e NEO4J_SERVICE=localhost ghcr.io/petrov-e/neo4j_exporter:v1.0.0-5-g1e176d2
```

The page with metrics in Prometheus format will be available here:
```bash
curl localhost:9099
```

View logs:
```bash
docker logs -f neo4j_exporter
```




# Grafana Dashboard for Prometheus Neo4j Exporter

To import the Grafana dashboard:

1. Copy dashboard JSON text from: [neo4j-long-running-queries.json](grafana-dashboard/neo4j-long-running-queries.json) 
2. On the create tab, select Import.
3. Paste dashboard JSON text directly into the text area and click Load.
4. Select the Data Source as Prometheus and click Import.

![Screenshot](grafana-dashboard/screenshot.png)