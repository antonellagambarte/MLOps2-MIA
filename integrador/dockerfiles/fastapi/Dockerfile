FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY dockerfiles/fastapi/requirements.txt /requirements.txt

# Los --trusted-host son por el antivirus
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    -r /requirements.txt

WORKDIR /app
COPY api/ /app/

# El mismo contrato y la misma traduccion de enums que compila el servidor gRPC.
COPY grpc_service/scoring.proto grpc_service/mapas.py /app/
RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. scoring.proto

EXPOSE 8800
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8800"]
