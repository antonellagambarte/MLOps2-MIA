FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY dockerfiles/streaming/requirements.txt /requirements.txt

# Los --trusted-host son por el antivirus
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    -r /requirements.txt

WORKDIR /app
COPY streaming/ /app/
COPY api/src/ /app/src/

CMD ["python", "worker.py"]
