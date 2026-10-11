# Member 3: Hadoop Streaming MapReduce Guide

## Responsibilities

Member 3 owns the Hadoop Streaming MapReduce portion of this repository:

- Read and validate transaction records from HDFS.
- Emit mapper key/value records compatible with Hadoop Streaming.
- Aggregate units sold by product and calculate the global top ten.
- Keep output deterministic and valid CSV for the dashboard and result file.
- Maintain automated tests and document the MapReduce contract and integration.

The producer, Kafka consumer, Compose services, image, and scheduler are owned
by the rest of the team and are dependencies of this contribution.

## Existing Architecture

The current pipeline is wired as follows:

1. `producer/producer.py` reads `data/sales.csv` and publishes each CSV row as
   a JSON Kafka message to `sales-transactions`.
2. `consumer/consumer.py` validates each message and writes it to HDFS below
   `/sales/input`.
3. `scheduler/run.sh` runs Hadoop Streaming against that HDFS directory,
   using `mapreduce/mapper.py` and `mapreduce/reducer.py`.
4. The scheduler copies the reducer part file to
   `results/top10_products.csv`.

Docker Compose runs Kafka, HDFS, and the pipeline image. The dashboard is not
part of the current Compose setup; it reads the generated results CSV when run
separately.

## Input Contract: HDFS JSON Lines

The consumer creates a distinct `.json` file for each Kafka topic, partition,
and offset. Each file contains one UTF-8 JSON object followed by a newline.
The consumer preserves transaction fields and normalizes `product_name` and
`units_sold`. For example:

```json
{"transaction_id":"TX-001","product_name":"Wireless Headphones","units_sold":900,"sold_at":"2026-10-01T09:15:00Z"}
```

The mapper requires:

- A JSON object with a non-empty string `product_name`.
- `units_sold` represented as a nonnegative JSON integer. Booleans and JSON
  floating-point values are rejected, including values such as `2.0`.
- A product name without tabs or line breaks, because tabs delimit the
  Streaming key/value record and line breaks delimit input records.

Other transaction fields are ignored by aggregation. The mapper does not
coerce names or quantities into valid values; malformed records fail with a
line-numbered diagnostic on standard error and a nonzero exit status.

## Mapper

`mapreduce/mapper.py` reads one JSON object per input line, validates the
required fields, trims surrounding whitespace from the product name, and emits
one record per transaction:

```text
product_name<TAB>units_sold
```

Example:

```text
Pear<TAB>4
Apple<TAB>3
Pear<TAB>5
```

Hadoop Streaming uses the text before the first tab as the map-output key, so
both Pear records are sent to the same reducer key.

## Reducer and Ranking

`mapreduce/reducer.py` validates each tab-delimited mapper record and sums its
nonnegative integer quantity by product. It then sorts all product totals by:

1. Total units sold, descending.
2. Product name, ascending, to make equal totals deterministic.

It keeps the first ten products, assigns ranks starting at 1, and writes CSV
using Python's `csv` module. CSV quoting correctly preserves commas and quotes
within product names. The output columns are exactly:

```text
rank,product_name,units_sold
```

With the example mapper records above, the reducer output is:

```csv
rank,product_name,units_sold
1,Pear,9
2,Apple,3
```

Fewer than ten distinct products are all returned. Empty reducer input produces
the header only.

## Run Locally

From the repository root, with Python 3 available, provide JSONL to the mapper
and pipe its tab-delimited output to the reducer:

```sh
python mapreduce/mapper.py < transactions.jsonl | python mapreduce/reducer.py
```

The result is CSV on standard output. A mapper or reducer validation error is
reported on standard error and exits nonzero. The scripts use only Python
standard-library modules.

## Automated Tests

Run the test suite from the repository root:

```sh
python -m unittest discover -s tests -v
```

`tests/test_mapreduce.py` uses `unittest` and launches the actual mapper and
reducer scripts as subprocesses. It covers valid transactions, required
fields, invalid JSON and record shapes, product-name validation, boolean,
fractional and negative quantities, aggregation, ranking and tie order, top-ten
truncation, fewer than ten products, empty input, malformed reducer records,
CSV escaping, and a complete mapper-to-reducer run.

**Verified result for this implementation:** 19 tests ran and passed; 0 failed.
Command: `python -m unittest discover -s tests -v`.

## Hadoop Streaming Integration

The existing `scheduler/run.sh` locates the Hadoop Streaming JAR under
`HADOOP_HOME`, submits `/sales/input`, and distributes the scripts with
`-file`. The command invokes them as `python3 mapper.py` and `python3
reducer.py`, writes to `/sales/output/top-products`, and concatenates the part
file into `/app/results/top10_products.csv`.

The scheduler sets `mapreduce.job.reduces=1`. **Keep one reducer** for this
implementation: each reducer independently sees only its assigned keys, so
multiple reducers would each produce a partial ranking and CSV header. A
single reducer receives all product keys, calculates the global totals and
top ten, and produces one correctly ranked CSV.

## Docker Compatibility

The pipeline image is based on `bde2020/hadoop-base:2.0.0-hadoop3.2.1-java8`,
installs Python 3 and `pipeline-requirements.txt`, and copies `mapreduce/` into
the image. The mapper and reducer themselves need only Python's standard
library. Hadoop Streaming must be able to find `python3` on its task PATH and
the scripts must remain compatible with the Python version provided by the
image. The test suite uses `subprocess.run` with `universal_newlines` for
compatibility with older Python 3 releases.

The tests validate script behavior locally; they do not start Docker, Kafka,
or Hadoop. A Compose run is a separate end-to-end integration check.

## Integration Dependencies and Known Risks

- **Member 1 producer:** supplies JSON objects containing `product_name` and
  `units_sold`. The current CSV has those fields and publishes one message per
  source row. Product names must remain single-line, and quantities must be
  whole, nonnegative integers.
- **Member 2 consumer:** writes the records in the JSONL format described
  above, preserving transaction fields. If its field names, normalization, or
  HDFS directory change, update and retest the mapper contract with the team.
- **Kafka offset commits (Member 2 dependency):** inspection found that the
  consumer calls `consumer.commit()` after individual writes/rejections. Since
  a consumer may have fetched additional records, committing its current
  position can advance past records not yet written to HDFS. This is outside
  Member 3 scope and needs owner review.
- **Repeated ingestion (pipeline dependency):** Compose preserves Kafka and
  HDFS volumes, while pipeline startup republishes the whole CSV. Repeated
  starts can therefore add duplicate transactions under new Kafka offsets and
  inflate aggregate totals. Deduplication or an explicit reset/replay policy
  is outside Member 3 scope.
- **Checked-in results:** the existing `results/top10_products.csv` totals do
  not match one pass over the current dataset. For example, Wireless
  Headphones totals 1,842 in the CSV but 5,526 in that artifact. This guide
  does not regenerate or modify the artifact.
- **Hadoop runtime:** only the local subprocess tests have been run for this
  contribution. Hadoop Streaming and Docker image compatibility still need an
  end-to-end run in the project environment.

## Viva Questions and Answers

**Why use JSON Lines for HDFS input?**
Each transaction is a self-contained JSON object on one line, so Hadoop
Streaming can process records line by line while retaining the producer's
transaction fields.

**Why is product name the mapper key?**
The ranking aggregates quantities per product. Using the product name as the
key lets Hadoop shuffle records for the same product to the same reducer.

**Why validate booleans separately from integers?**
In Python, `bool` is a subclass of `int`. Explicitly rejecting booleans ensures
JSON `true` and `false` cannot be interpreted as unit counts.

**Why reject floating-point values instead of converting them?**
Converting a fraction to an integer can silently change a sale quantity. This
contract accepts only whole JSON integer values and fails malformed input
clearly.

**Why must there be exactly one reducer?**
The global top ten requires totals for every product. Multiple reducers would
produce independent partial rankings; one reducer sees all product keys and
creates one global result.

**How are ties handled?**
Equal totals are ordered alphabetically by product name, which makes results
repeatable.

**How is a product name containing a comma kept valid in output?**
The reducer writes rows with Python's CSV writer, which quotes fields when
needed and escapes embedded quotes.

**What is the difference between mapper output and final output?**
Mapper output is tab-delimited key/value text for Hadoop's shuffle. Reducer
output is CSV intended for the result file and dashboard.

**What integration issues remain outside Member 3?**
The consumer's offset commit position and repeated publication of the source
CSV can lead to missed or duplicated records. Both require coordination with
the owning team members.

## Pull Request Instructions

After the team approves Git submission, verify the branch and stage only the
Member 3 files:

```sh
git status --short --branch
git add mapreduce/mapper.py mapreduce/reducer.py tests/test_mapreduce.py README.md MEMBER3_MAPREDUCE_GUIDE.md
git commit -m "Harden MapReduce ranking and add tests"
git push -u origin feature/mapreduce-ranking
```

Then create a GitHub Pull Request from `feature/mapreduce-ranking` into
`master`. Include the test command and result, summarize the JSONL-to-CSV
contract changes, and call out the consumer offset and repeated-ingestion
risks. Review the staged diff to ensure no producer, consumer, deployment,
dataset, or generated-result files are included. Do not merge until the team
has reviewed the integration dependencies.
