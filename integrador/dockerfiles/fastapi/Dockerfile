FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY dockerfiles/fastapi/requirements.txt /requirements.txt

# Los --trusted-host son por el antivirus
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    -r /requirements.txt

WORKDIR /app
COPY api/ /app/

EXPOSE 8800
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8800"]
