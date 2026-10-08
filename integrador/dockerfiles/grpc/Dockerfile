FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY dockerfiles/grpc/requirements.txt /requirements.txt

RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    -r /requirements.txt

WORKDIR /app
COPY grpc_service/ /app/
COPY api/src/ /app/src/

RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. scoring.proto

EXPOSE 50051
CMD ["python", "server.py"]
