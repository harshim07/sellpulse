# Sales pipeline

This repository's Docker setup runs the sales pipeline only:

1. The Python producer reads transactions from `data/sales.csv`.
2. It publishes each transaction to Kafka's `sales-transactions` topic.
3. The Python consumer writes each message to HDFS.
4. Hadoop Streaming runs the mapper and reducer and writes the ranked CSV to
   `results/top10_products.csv`.

Kafka, HDFS, and the pipeline run as Docker Compose services. Producer,
consumer, scheduler, and MapReduce scripts are packaged together into the one
pipeline image built by `Dockerfile`. No local Python or dependency installation
is required. The dashboard is not part of this pipeline-only Compose setup.

## Run

Install and start Docker Desktop, then run from this directory:

```sh
docker compose up --build
```

The pipeline reads the mounted `data/sales.csv` file and saves rankings to the
mounted `results/top10_products.csv`. Input CSV files must include
`product_name` and `units_sold` columns. The NameNode web interface is available
at [http://localhost:9870](http://localhost:9870).

Stop the services with `Ctrl+C` or `docker compose down`. Kafka and HDFS data
persist in Docker volumes; `docker compose down -v` removes those volumes and
their data.

## Member 3: MapReduce ranking

HDFS input is one transaction JSON object per line. The mapper emits
tab-separated product and unit pairs; the reducer aggregates products and
outputs CSV columns `rank,product_name,units_sold`, ranked by units sold
descending with product names alphabetically breaking ties. Run the automated
tests with `python -m unittest discover -s tests -v`. See
[MEMBER3_MAPREDUCE_GUIDE.md](MEMBER3_MAPREDUCE_GUIDE.md) for the data contract,
implementation, testing, and Hadoop Streaming details.
