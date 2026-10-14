# Sales pipeline

This repository's Docker Compose setup runs a sales pipeline and interactive
Streamlit dashboard:

1. The Python producer reads transactions from `data/sales.csv`.
2. It publishes each transaction to Kafka's `sales-transactions` topic.
3. The Python consumer writes each message to HDFS.
4. Hadoop Streaming runs the mapper and reducer and writes the ranked CSV to
   `results/top10_products.csv`.
5. The dashboard reads the results file and presents the product rankings and
   sales analysis in a browser.

Kafka, HDFS, and the pipeline run as Docker Compose services. Producer,
consumer, scheduler, and MapReduce scripts are packaged in the pipeline image;
the dashboard runs in a separate, lightweight Python image built from the same
`Dockerfile`. No local Python, Kafka, Hadoop, or dashboard dependency
installation is required. Pipeline dependencies are kept in
`pipeline-requirements.txt`; Streamlit dashboard dependencies are installed
only from `dashboard/requirements.txt`.

## Run

Install and start Docker Desktop, then run from this directory:

```sh
docker compose up --build
```

The pipeline reads the mounted `data/sales.csv` file and saves rankings to the
mounted `results/top10_products.csv`. Input CSV files must include
`product_name` and `units_sold` columns. Compose waits for Kafka, the NameNode,
and the DataNode health checks before starting the pipeline. The scheduler
waits for all CSV transactions to reach HDFS, then writes the ranked CSV
atomically and recalculates every 10 minutes by default. Set
`SCHEDULER_INTERVAL_SECONDS` to change the calculation interval. The dashboard
automatically refreshes every 10 minutes and can also be refreshed manually.
It is available at [http://localhost:8502](http://localhost:8502) by default;
set `DASHBOARD_PORT` to use a different available host port. The NameNode UI is
available at [http://localhost:9870](http://localhost:9870).

Stop the services with `Ctrl+C` or `docker compose down`. Kafka and HDFS data
persist in Docker volumes; `docker compose down -v` removes those volumes and
their data.

## MapReduce ranking

HDFS input is one transaction JSON object per line. The mapper emits
tab-separated product and unit pairs; the reducer aggregates products and
outputs CSV columns `rank,product_name,units_sold`, ranked by units sold
descending with product names alphabetically breaking ties. Run the automated
tests with `python -m unittest discover -s tests -v`. See
[MEMBER3_MAPREDUCE_GUIDE.md](MEMBER3_MAPREDUCE_GUIDE.md) for the data contract,
implementation, testing, and Hadoop Streaming details.
