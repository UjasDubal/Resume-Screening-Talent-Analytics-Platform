FROM apache/airflow:2.10.4-python3.11

USER root

# System dependencies for PDF processing, reportlab, and psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Copy and install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Download spaCy model at build time
RUN python -m spacy download en_core_web_sm

# Copy project source code
COPY --chown=airflow:root . /opt/airflow/project/

# Add project to Python path
ENV PYTHONPATH="/opt/airflow/project:${PYTHONPATH}"

# Working directory
WORKDIR /opt/airflow
