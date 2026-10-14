FROM bde2020/hadoop-base:2.0.0-hadoop3.2.1-java8 AS pipeline

USER root
RUN sed -i \
    -e 's|deb.debian.org/debian|archive.debian.org/debian|g' \
    -e 's|security.debian.org/debian-security|archive.debian.org/debian-security|g' \
    -e '/stretch-updates/d' \
    /etc/apt/sources.list \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN python3 -m venv /opt/pipeline-venv
ENV PATH=/opt/pipeline-venv/bin:$PATH

COPY pipeline-requirements.txt ./pipeline-requirements.txt
RUN if grep -Eiq '^(streamlit|pandas|plotly)([<=>~! ]|$)' ./pipeline-requirements.txt; then \
        echo "Dashboard packages belong in dashboard/requirements.txt, not pipeline-requirements.txt." >&2; \
        exit 1; \
    fi \
    && python3 -m pip install --no-cache-dir -r pipeline-requirements.txt

COPY producer ./producer
COPY consumer ./consumer
COPY mapreduce ./mapreduce
COPY scheduler ./scheduler
RUN sed -i 's/\r$//' ./scheduler/*.sh
COPY data ./data

ENV HADOOP_HOME=/opt/hadoop-3.2.1 \
    KAFKA_BOOTSTRAP_SERVERS=kafka:9092 \
    KAFKA_TOPIC=sales-transactions \
    HDFS_URL=http://namenode:9870 \
    HDFS_INPUT_DIR=/sales/input \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

FROM python:3.12-slim AS dashboard

WORKDIR /app

COPY dashboard/requirements.txt ./dashboard/requirements.txt
RUN python -m pip install --no-cache-dir -r dashboard/requirements.txt
COPY dashboard/app.py ./dashboard/app.py

ENV PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true

EXPOSE 8501

CMD ["streamlit", "run", "/app/dashboard/app.py"]
