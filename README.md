# MLOps II — MIA/FIUBA

## Entorno

Desde la raíz del repo:

```bash
uv venv --python 3.11
uv pip install -r requirements.txt
```

## Estructura del repo

- `mini-tps/` — resolución individual de cada mini-TP semanal (uno por sesión).
- `integrador/` — trabajo integrador (arquitectura Airflow + MLflow + FastAPI + MinIO/S3 sobre Docker), armado de a partes a medida que se van resolviendo los mini-tps.

## Contenido

- [Mini-TP 1](mini-tps/tp1/README.md) — API REST con FastAPI
