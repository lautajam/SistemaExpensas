# -*- coding: utf-8 -*-
"""
maestro.py
----------
Contraseña maestra que protege las pantallas de administración (Administrar
edificios/unidades, Configuración de la inmobiliaria y Editor de datos CSV):
abrirlas, y cada alta/edición/borrado dentro de ellas, la piden — salvo que el
"control maestro" esté activo (se activa una vez, desde el menú Administrar, y
dura hasta que se bloquee o se cierre el programa).

Se guarda hasheada (PBKDF2-SHA256 con sal aleatoria, sin depender de librerías
externas) en configuracion/maestro.csv, junto con una pregunta de seguridad para
poder restablecerla si se olvida. Por ahora es un solo registro en un CSV; está
pensado para pasar a una base de datos más adelante sin cambiar esta interfaz
(crear/verificar_password/verificar_respuesta/etc.), así que el resto de la app
no debería necesitar cambios cuando eso pase.
"""

import csv
import os
import re
import unicodedata
from hashlib import pbkdf2_hmac

import config

_CAMPOS = ["sal_password", "hash_password", "pregunta", "sal_respuesta", "hash_respuesta"]
_ITERACIONES = 200_000

# Control maestro: True mientras la sesión lo mantenga desbloqueado (no se guarda en disco:
# arranca en False cada vez que se abre el programa).
_activo = False


def _hash(texto, sal=None):
    sal = sal if sal is not None else os.urandom(16)
    derivado = pbkdf2_hmac("sha256", str(texto).encode("utf-8"), sal, _ITERACIONES)
    return sal.hex(), derivado.hex()


def _normalizar(texto):
    """Para comparar la respuesta de seguridad sin importar mayúsculas, tildes o espacios de más."""
    t = unicodedata.normalize("NFKD", str(texto or "").strip())
    return re.sub(r"\s+", " ", "".join(c for c in t if not unicodedata.combining(c)).lower())


def existe():
    """True si ya se configuró una contraseña maestra."""
    return os.path.isfile(config.MAESTRO_CSV)


def _leer():
    if not existe():
        return None
    with open(config.MAESTRO_CSV, "r", encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))
    return filas[0] if filas else None


def crear(password, pregunta, respuesta):
    """
    Crea o reemplaza la contraseña maestra y su pregunta de seguridad.
    Lanza ValueError si falta algún dato.
    """
    password = str(password or "")
    pregunta = str(pregunta or "").strip()
    respuesta = str(respuesta or "").strip()
    if len(password) < 4:
        raise ValueError("La contraseña tiene que tener al menos 4 caracteres.")
    if not pregunta or not respuesta:
        raise ValueError("Completá la pregunta y la respuesta de seguridad.")

    sal_pw, hash_pw = _hash(password)
    sal_resp, hash_resp = _hash(_normalizar(respuesta))
    os.makedirs(os.path.dirname(config.MAESTRO_CSV), exist_ok=True)
    temporal = config.MAESTRO_CSV + ".tmp"
    with open(temporal, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_CAMPOS)
        w.writeheader()
        w.writerow({"sal_password": sal_pw, "hash_password": hash_pw, "pregunta": pregunta,
                    "sal_respuesta": sal_resp, "hash_respuesta": hash_resp})
    os.replace(temporal, config.MAESTRO_CSV)


def verificar_password(password):
    """True si 'password' es la contraseña maestra vigente (False si todavía no hay ninguna)."""
    fila = _leer()
    if not fila:
        return False
    _, hash_pw = _hash(password or "", bytes.fromhex(fila["sal_password"]))
    return hash_pw == fila["hash_password"]


def obtener_pregunta():
    """La pregunta de seguridad guardada, o None si no hay contraseña maestra."""
    fila = _leer()
    return fila["pregunta"] if fila else None


def verificar_respuesta(respuesta):
    """True si 'respuesta' coincide con la respuesta de seguridad guardada."""
    fila = _leer()
    if not fila:
        return False
    _, hash_resp = _hash(_normalizar(respuesta), bytes.fromhex(fila["sal_respuesta"]))
    return hash_resp == fila["hash_respuesta"]


def esta_activo():
    """True mientras el 'control maestro' esté desbloqueado en esta sesión."""
    return _activo


def activar():
    global _activo
    _activo = True


def desactivar():
    global _activo
    _activo = False
