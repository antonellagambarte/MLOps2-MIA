# 3.11 para que coincida con el Python que serializó el pipeline del modelo.
FROM python:3.11-slim

# libgomp1 lo necesita xgboost; curl es para el healthcheck del compose.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY dockerfiles/fastapi/requirements.txt /requirements.txt

# Los --trusted-host son por el antivirus de la máquina de desarrollo:
# con el escaneo de HTTPS activado, intercepta la conexión a PyPI y la vuelve a
# firmar con un certificado propio.
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    -r /requirements.txt

WORKDIR /app
COPY api/ /app/

EXPOSE 8800
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8800"]
