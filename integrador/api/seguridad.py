# -*- coding: utf-8 -*-
"""Puerta protegida sobre el mismo modelo, con los controles del mini-TP 7 de REST."""
import datetime
import hashlib
import json
import os
import time

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

import modelo
from contrato import Caracteristicas, Prediccion

JWT_SECRET = os.getenv("JWT_SECRET", "cambiar-en-produccion-con-32-bytes-o-mas")
API_KEY = os.getenv("API_KEY_TOKENS", "demo-key-123")
LIMITE_POR_MINUTO = int(os.getenv("LIMITE_POR_MINUTO", "5"))
MINUTOS_TOKEN = 15
ROLES_PERMITIDOS = {"analista", "admin"}

AUDITORIA = []

router = APIRouter(prefix="/v1/secure", tags=["Puerta protegida"])


# --- EMISIÓN DEL TOKEN ---

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def clave_valida(clave: str = Depends(api_key_header)):
    """Sin la clave de servicio nadie puede emitirse un token."""
    if clave != API_KEY:
        raise HTTPException(401, "Falta o no coincide la API key")
    return clave


class PedidoToken(BaseModel):
    usuario: str
    rol: str


class TokenEmitido(BaseModel):
    token: str
    expira_en: int


def crear_token(usuario: str, rol: str, minutos: int = MINUTOS_TOKEN) -> str:
    """Firma un token con el usuario, su rol y el vencimiento."""
    payload = {
        "sub": usuario,
        "rol": rol,
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(minutes=minutos),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


@router.post("/token", response_model=TokenEmitido)
def emitir_token(pedido: PedidoToken, _clave: str = Depends(clave_valida)):
    # Firma cualquier rol, incluso uno sin permiso: quién puede predecir lo
    # decide el endpoint, no el emisor. Así se puede probar el 403.
    return TokenEmitido(
        token=crear_token(pedido.usuario, pedido.rol),
        expira_en=MINUTOS_TOKEN * 60,
    )


# --- CONTROLES DE ACCESO ---

bearer = HTTPBearer(auto_error=False)


def requiere_rol(credenciales: HTTPAuthorizationCredentials = Depends(bearer)):
    """Verifica el token y exige un rol habilitado."""
    if credenciales is None:
        raise HTTPException(401, "Token requerido")

    try:
        payload = jwt.decode(credenciales.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token inválido o expirado")

    usuario = payload.get("sub")
    if not usuario:
        raise HTTPException(401, "Usuario no identificado")
    if payload.get("rol") not in ROLES_PERMITIDOS:
        raise HTTPException(403, "Permisos insuficientes")

    return {"usuario": usuario, "rol": payload["rol"]}


_golpes = {}


def limite_de_tasa(identidad: dict = Depends(requiere_rol)):
    """Ventana deslizante de un minuto por usuario.

    En memoria porque uvicorn corre con un solo worker. Con varios, cada uno
    tendría su propio contador; en producción iría en Redis o en el gateway.
    """
    ahora = time.time()
    ventana = _golpes.setdefault(identidad["usuario"], [])
    ventana[:] = [t for t in ventana if ahora - t < 60]
    if len(ventana) >= LIMITE_POR_MINUTO:
        raise HTTPException(429, "Demasiadas solicitudes")
    ventana.append(ahora)
    return identidad


def requiere_admin(identidad: dict = Depends(requiere_rol)):
    if identidad["rol"] != "admin":
        raise HTTPException(403, "Solo admin puede leer la auditoría")
    return identidad


# --- ENDPOINTS ---

@router.post("/predict", response_model=Prediccion)
def predecir_seguro(paciente: Caracteristicas, identidad: dict = Depends(limite_de_tasa)):
    if modelo.estado is None:
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo cargar {modelo.URI_MODELO}. {modelo.error_carga}",
        )

    datos = paciente.model_dump()
    clase, probabilidad, version, descripcion = modelo.predecir(datos)

    # Se guarda la huella de la consulta, no los datos del paciente: alcanza para
    # reconocer dos consultas iguales sin almacenar información clínica.
    huella = hashlib.sha256(
        json.dumps(datos, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    registro = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "usuario": identidad["usuario"],
        "hash_entrada": huella,
        "prediccion": clase,
        "version_modelo": version,
    }
    AUDITORIA.append(registro)
    print(
        f"AUDIT {registro['ts']} usuario={registro['usuario']} "
        f"hash={huella[:12]} pred={clase} v={version}",
        flush=True,
    )

    return Prediccion(
        prediccion=clase,
        probabilidad=probabilidad,
        version_modelo=version,
        descripcion=descripcion,
    )


@router.get("/auditoria")
def leer_auditoria(_identidad: dict = Depends(requiere_admin)):
    return AUDITORIA[-50:]
