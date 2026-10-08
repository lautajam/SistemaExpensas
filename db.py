# -*- coding: utf-8 -*-
"""
db.py
-----
Base de datos SQLite (datos/expensas.db) que reemplaza, de a poco, los CSV de datos/ y configuracion/.

Decisiones:
- Todas las columnas se guardan como TEXTO, igual que en los CSV: la migración no convierte
  ni redondea ningún valor.
- Cada tabla tiene una columna `orden` autoincremental para conservar el orden original de las filas.
- La migración NO borra los CSV: quedan como respaldo. La base se escribe en un archivo temporal y
  solo se renombra cuando la verificación de cantidades cuadra; si algo falla, no queda una base a medias.
- La planilla de pagos (Excel) no es parte de esta base: sigue siendo el archivo de siempre.
"""

import csv
import os
import sqlite3

import config

RUTA_DB = os.path.join(config.DATOS_DIR, "expensas.db")

# Campos de cada CSV (deben coincidir con los de database.py, correo.py y maestro.py).
EDIFICIOS_CAMPOS = ["id", "nombre", "direccion", "localidad", "cuit", "admin_nombre", "admin_cuit", "admin_rpac"]
UNIDADES_CAMPOS = ["id", "edificio", "piso", "tipo", "unidad", "uf", "inquilino", "dueno", "importe",
                   "depto_id", "paga_junto", "celda"]
NUMERACION_CAMPOS = ["edificio", "ultimo_recibo"]
HISTORIAL_CAMPOS = [
    "numero_recibo", "edificio", "fecha", "expensas_de", "gastos_de",
    "piso", "tipo", "unidad", "inquilino", "importe", "archivo", "unidad_id",
    "datos_completos", "uf", "dueno", "asociadas", "estado",
    "edificio_direccion", "edificio_localidad", "edificio_cuit",
    "admin_nombre", "admin_cuit", "admin_rpac",
    "inmo_nombre", "inmo_subtitulo", "inmo_direccion", "inmo_telefono", "inmo_email",
]
INMOBILIARIA_CAMPOS = ["nombre", "subtitulo", "direccion", "telefono", "email"]
PREFERENCIAS_CAMPOS = ["clave", "valor"]
MAESTRO_CAMPOS = ["sal_password", "hash_password", "pregunta", "sal_respuesta", "hash_respuesta"]
SMTP_CAMPOS = ["servidor", "puerto", "usuario", "password", "tls"]
EMAILS_CAMPOS = ["unidad_id", "inquilino1", "inquilino2", "dueno1", "dueno2"]
ENVIADOS_CAMPOS = ["fecha", "edificio", "numero_recibo", "unidad", "destinatario", "resultado", "detalle"]
PLANTILLAS_CAMPOS = ["edificio", "asunto", "cuerpo"]
COPIA_CAMPOS = ["email", "activa"]

# tabla -> (CSV de origen, campos)
ESQUEMA = {
    "edificios": (config.EDIFICIOS_CSV, EDIFICIOS_CAMPOS),
    "unidades": (config.UNIDADES_CSV, UNIDADES_CAMPOS),
    "numeracion": (config.NUMERACION_CSV, NUMERACION_CAMPOS),
    "historial": (config.HISTORIAL_CSV, HISTORIAL_CAMPOS),
    "inmobiliaria": (config.INMOBILIARIA_CSV, INMOBILIARIA_CAMPOS),
    "preferencias": (config.PREFERENCIAS_CSV, PREFERENCIAS_CAMPOS),
    "maestro": (config.MAESTRO_CSV, MAESTRO_CAMPOS),
    "smtp": (config.SMTP_CSV, SMTP_CAMPOS),
    "emails_unidades": (config.EMAILS_UNIDADES_CSV, EMAILS_CAMPOS),
    "mails_enviados": (config.MAILS_ENVIADOS_CSV, ENVIADOS_CAMPOS),
    "plantillas_mail": (config.PLANTILLAS_MAIL_CSV, PLANTILLAS_CAMPOS),
    "copia_mail": (config.COPIA_MAIL_CSV, COPIA_CAMPOS),
}


al_crear = None   # función que database.py registra: se llama al crear la base de la app (ej. datos de ejemplo)


def abrir(ruta=None):
    """Conexión a la base. Si la base de la app todavía no existe, la crea (importando los CSV viejos)."""
    principal = _ruta_activa or RUTA_DB
    ruta = ruta or principal
    if ruta == principal and not os.path.isfile(ruta):
        migrar_desde_csv(ruta)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    conexion = sqlite3.connect(ruta)
    conexion.row_factory = sqlite3.Row
    _crear_esquema(conexion)   # por si la base es de una versión anterior y le falta alguna tabla
    conexion.commit()
    return conexion


def _crear_esquema(conexion):
    for tabla, (_csv, campos) in ESQUEMA.items():
        columnas = ", ".join(f'"{c}" TEXT' for c in campos)
        conexion.execute(
            f'CREATE TABLE IF NOT EXISTS "{tabla}" (orden INTEGER PRIMARY KEY AUTOINCREMENT, {columnas})')


def _leer_csv(ruta):
    if not os.path.isfile(ruta):
        return []
    with open(ruta, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def existe_base(ruta=None):
    return os.path.isfile(ruta or RUTA_DB)


# ---------------------------------------------------------------------------
# Acceso a las tablas (lo usa database.py, maestro.py y correo.py)
# ---------------------------------------------------------------------------

_ruta_activa = None         # ruta de la base en uso (la de RUTA_DB si no se cambió)
_transaccion = None         # conexión abierta mientras dura un bloque transaccion()


def _conexion():
    """Conexión para una operación: la de la transacción activa, o una nueva que se cierra al terminar."""
    return _transaccion if _transaccion is not None else abrir(_ruta_activa or RUTA_DB)


def _usar(conexion, operacion):
    if _transaccion is not None:
        return operacion(conexion)
    try:
        resultado = operacion(conexion)
        conexion.commit()
        return resultado
    finally:
        conexion.close()


def leer(tabla):
    """Filas de la tabla como dicts con los campos originales, en el orden en que se cargaron."""
    campos = ESQUEMA[tabla][1]

    def operacion(con):
        filas = con.execute(f'SELECT {", ".join(chr(34) + c + chr(34) for c in campos)} '
                            f'FROM "{tabla}" ORDER BY orden').fetchall()
        return [{c: fila[c] for c in campos} for fila in filas]
    return _usar(_conexion(), operacion)


def reemplazar(tabla, filas):
    """Reemplaza todo el contenido de la tabla por 'filas' (solo se guardan los campos de la tabla)."""
    campos = ESQUEMA[tabla][1]
    columnas = ", ".join(f'"{c}"' for c in campos)
    marcas = ", ".join("?" for _ in campos)

    def operacion(con):
        con.execute(f'DELETE FROM "{tabla}"')
        con.executemany(f'INSERT INTO "{tabla}" ({columnas}) VALUES ({marcas})',
                        [[f.get(c) or "" for c in campos] for f in filas])
    _usar(_conexion(), operacion)


def agregar(tabla, fila):
    """Agrega una fila al final de la tabla."""
    campos = ESQUEMA[tabla][1]
    columnas = ", ".join(f'"{c}"' for c in campos)
    marcas = ", ".join("?" for _ in campos)

    def operacion(con):
        con.execute(f'INSERT INTO "{tabla}" ({columnas}) VALUES ({marcas})',
                    [fila.get(c) or "" for c in campos])
    _usar(_conexion(), operacion)


class transaccion:
    """
    Agrupa varias operaciones en una sola transacción: si el bloque falla, no se guarda nada.
        with db.transaccion():
            ...
    """

    def __enter__(self):
        global _transaccion
        _transaccion = abrir(_ruta_activa or RUTA_DB)
        return self

    def __exit__(self, tipo, valor, tb):
        global _transaccion
        con, _transaccion = _transaccion, None
        try:
            if tipo is None:
                con.commit()
        finally:
            con.close()
        return False


def usar_ruta(ruta):
    """Cambia la base en uso (para pruebas y para restaurar un backup)."""
    global _ruta_activa
    _ruta_activa = ruta


# Tablas con contraseñas: nunca salen en un backup ni se pisan al restaurar.
TABLAS_SECRETAS = ("maestro", "smtp")


def copiar_sin_secretos(destino):
    """
    Copia la base (con la API de backup de SQLite, así queda consistente aunque la app esté usándola)
    a 'destino', y en esa copia vacía las tablas con contraseñas. La base real no se toca.
    """
    origen = abrir(_ruta_activa or RUTA_DB)
    copia = sqlite3.connect(destino)
    try:
        origen.backup(copia)
        for tabla in TABLAS_SECRETAS:
            copia.execute(f'DELETE FROM "{tabla}"')
        copia.commit()
        copia.execute("VACUUM")
    finally:
        copia.close()
        origen.close()


def reemplazar_base(ruta_nueva):
    """Pone 'ruta_nueva' como la base en uso (reemplazo atómico del archivo)."""
    os.replace(ruta_nueva, _ruta_activa or RUTA_DB)


def migrar_desde_csv(ruta=None, origen=None):
    """
    Crea la base e importa los CSV. 'origen' es {tabla: ruta del CSV}; por defecto, los de la app.
    Si la base ya existe, no hace nada. Devuelve {tabla: (filas_en_csv, filas_en_base)} si migró,
    o None si ya existía. Lanza RuntimeError si las cantidades no cuadran (no se crea la base).
    """
    ruta = ruta or RUTA_DB
    if os.path.isfile(ruta):
        return None
    origen = origen or {tabla: ruta_csv for tabla, (ruta_csv, _campos) in ESQUEMA.items()}

    temporal = ruta + ".tmp"
    if os.path.exists(temporal):
        os.remove(temporal)

    conexion = abrir(temporal)
    try:
        _crear_esquema(conexion)
        informe = {}
        for tabla, (_ruta_defecto, campos) in ESQUEMA.items():
            filas = _leer_csv(origen.get(tabla, ""))
            columnas = ", ".join(f'"{c}"' for c in campos)
            marcas = ", ".join("?" for _ in campos)
            conexion.executemany(
                f'INSERT INTO "{tabla}" ({columnas}) VALUES ({marcas})',
                [[f.get(c) or "" for c in campos] for f in filas])
            cantidad_base = conexion.execute(f'SELECT COUNT(*) FROM "{tabla}"').fetchone()[0]
            informe[tabla] = (len(filas), cantidad_base)
        malas = {t: v for t, v in informe.items() if v[0] != v[1]}
        if malas:
            raise RuntimeError(f"No cuadran las cantidades al migrar: {malas}")
        conexion.commit()
    except Exception:
        conexion.close()
        if os.path.exists(temporal):
            os.remove(temporal)
        raise
    conexion.close()
    os.replace(temporal, ruta)
    if al_crear and ruta == (_ruta_activa or RUTA_DB):
        al_crear()
    return informe
