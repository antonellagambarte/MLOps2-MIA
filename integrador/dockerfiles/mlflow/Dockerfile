FROM python:3.12-slim

# curl es solo para el healthcheck del compose
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /requirements.txt

# Los --trusted-host son por el antivirus (AVG)
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    -r /requirements.txt

EXPOSE 5000
