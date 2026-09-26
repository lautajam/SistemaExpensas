# -*- coding: utf-8 -*-
"""
database.py
-----------
Toda la persistencia de la aplicación vive acá, usando archivos CSV planos
(elegido deliberadamente en vez de SQLite para que el usuario pueda abrir
y revisar los archivos directamente con Excel si lo necesita).

Se usa codificación UTF-8 con BOM ("utf-8-sig") al CREAR los archivos, para
que Excel en Windows interprete correctamente tildes y "ñ". Al ANEXAR filas
se usa UTF-8 sin BOM (el BOM ya quedó al principio del archivo; escribirlo
de nuevo en medio del archivo lo corrompería).
"""

import csv
import os
import uuid
import zipfile
from datetime import datetime

import config
from utils import sanitize_filename

# ---------------------------------------------------------------------------
# Helpers genéricos de CSV
# ---------------------------------------------------------------------------

def _ensure_dir(path):
    if path:
        os.makedirs(path, exist_ok=True)


def _read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def _write_csv(path, fieldnames, rows):
    _ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def _append_csv(path, fieldnames, row):
    existe = os.path.exists(path)
    _ensure_dir(os.path.dirname(path))
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not existe:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in fieldnames})


# ---------------------------------------------------------------------------
# Inicialización de datos (crea todo lo que falte, con datos de ejemplo)
# ---------------------------------------------------------------------------

UNIDADES_CAMPOS = ["id", "edificio", "piso", "tipo", "unidad", "inquilino", "importe"]
EDIFICIOS_CAMPOS = ["id", "nombre"]
NUMERACION_CAMPOS = ["edificio", "ultimo_recibo"]
HISTORIAL_CAMPOS = [
    "numero_recibo", "edificio", "fecha", "expensas_de", "gastos_de",
    "piso", "tipo", "unidad", "inquilino", "importe", "archivo",
]
INMOBILIARIA_CAMPOS = ["nombre", "direccion", "telefono", "email", "cuit"]


def ensure_data_files():
    """Crea toda la estructura de carpetas/archivos si no existe todavía."""
    _ensure_dir(config.DATOS_DIR)
    _ensure_dir(config.CONFIG_DIR)
    _ensure_dir(config.EDIFICIOS_DIR)
    _ensure_dir(config.PLANTILLA_DIR)

    if not os.path.exists(config.EDIFICIOS_CSV):
        edificios_ejemplo = [
            {"id": "1", "nombre": "Edificio Alsina 123"},
            {"id": "2", "nombre": "Edificio Mitre 456"},
        ]
        _write_csv(config.EDIFICIOS_CSV, EDIFICIOS_CAMPOS, edificios_ejemplo)
        for e in edificios_ejemplo:
            crear_carpeta_edificio(e["nombre"])

    if not os.path.exists(config.UNIDADES_CSV):
        unidades_ejemplo = [
            {"id": uuid.uuid4().hex[:8], "edificio": "Edificio Alsina 123", "piso": "PB", "tipo": "DEPTO", "unidad": "1", "inquilino": "Ana Pérez", "importe": "45000"},
            {"id": uuid.uuid4().hex[:8], "edificio": "Edificio Alsina 123", "piso": "1°", "tipo": "DEPTO", "unidad": "A", "inquilino": "Carlos López", "importe": "45000"},
            {"id": uuid.uuid4().hex[:8], "edificio": "Edificio Alsina 123", "piso": "1°", "tipo": "DEPTO", "unidad": "B", "inquilino": "María García", "importe": "45000"},
            {"id": uuid.uuid4().hex[:8], "edificio": "Edificio Alsina 123", "piso": "2°", "tipo": "DEPTO", "unidad": "A", "inquilino": "Pedro Rodríguez", "importe": "48000"},
            {"id": uuid.uuid4().hex[:8], "edificio": "Edificio Alsina 123", "piso": "PB", "tipo": "COCH", "unidad": "3", "inquilino": "Juan Gómez", "importe": "12000"},
            {"id": uuid.uuid4().hex[:8], "edificio": "Edificio Mitre 456", "piso": "PB", "tipo": "DEPTO", "unidad": "1", "inquilino": "Laura Fernández", "importe": "38000"},
            {"id": uuid.uuid4().hex[:8], "edificio": "Edificio Mitre 456", "piso": "1°", "tipo": "DEPTO", "unidad": "A", "inquilino": "Diego Álvarez", "importe": "40000"},
            {"id": uuid.uuid4().hex[:8], "edificio": "Edificio Mitre 456", "piso": "1°", "tipo": "DEPTO", "unidad": "B", "inquilino": "Silvia Ruiz", "importe": "40000"},
            {"id": uuid.uuid4().hex[:8], "edificio": "Edificio Mitre 456", "piso": "BAU", "tipo": "BAU", "unidad": "14", "inquilino": "Marcos Sosa", "importe": "8000"},
        ]
        _write_csv(config.UNIDADES_CSV, UNIDADES_CAMPOS, unidades_ejemplo)

    if not os.path.exists(config.NUMERACION_CSV):
        _write_csv(config.NUMERACION_CSV, NUMERACION_CAMPOS, [])

    if not os.path.exists(config.HISTORIAL_CSV):
        _write_csv(config.HISTORIAL_CSV, HISTORIAL_CAMPOS, [])

    if not os.path.exists(config.INMOBILIARIA_CSV):
        _write_csv(config.INMOBILIARIA_CSV, INMOBILIARIA_CAMPOS, [{
            "nombre": "MI INMOBILIARIA",
            "direccion": "Av. Ejemplo 1234, CABA",
            "telefono": "011-4444-5555",
            "email": "contacto@miinmobiliaria.com",
            "cuit": "30-12345678-9",
        }])

    # Asegura que exista la carpeta de cada edificio ya cargado
    for e in get_edificios():
        crear_carpeta_edificio(e["nombre"])


# ---------------------------------------------------------------------------
# Edificios
# ---------------------------------------------------------------------------

def get_edificios():
    return _read_csv(config.EDIFICIOS_CSV)


def get_nombres_edificios():
    return [e["nombre"] for e in get_edificios()]


def add_edificio(nombre):
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre del edificio no puede estar vacío.")

    edificios = get_edificios()
    if any(e["nombre"].strip().lower() == nombre.lower() for e in edificios):
        raise ValueError(f"Ya existe un edificio llamado «{nombre}».")

    ids_existentes = [int(e["id"]) for e in edificios if str(e["id"]).isdigit()]
    nuevo_id = str(max(ids_existentes, default=0) + 1)

    edificios.append({"id": nuevo_id, "nombre": nombre})
    _write_csv(config.EDIFICIOS_CSV, EDIFICIOS_CAMPOS, edificios)
    crear_carpeta_edificio(nombre)
    return nuevo_id


def carpeta_edificio(nombre_edificio):
    return os.path.join(config.EDIFICIOS_DIR, sanitize_filename(nombre_edificio))


def crear_carpeta_edificio(nombre_edificio):
    carpeta = carpeta_edificio(nombre_edificio)
    _ensure_dir(carpeta)
    return carpeta


# ---------------------------------------------------------------------------
# Unidades
# ---------------------------------------------------------------------------

def get_all_unidades():
    return _read_csv(config.UNIDADES_CSV)


def get_unidades_por_edificio(nombre_edificio):
    return [u for u in get_all_unidades() if u["edificio"] == nombre_edificio]


def add_unidad(edificio, piso, tipo, unidad, inquilino, importe):
    todas = get_all_unidades()
    nueva = {
        "id": uuid.uuid4().hex[:8],
        "edificio": edificio,
        "piso": piso,
        "tipo": tipo,
        "unidad": unidad,
        "inquilino": inquilino,
        "importe": str(importe),
    }
    todas.append(nueva)
    _write_csv(config.UNIDADES_CSV, UNIDADES_CAMPOS, todas)
    return nueva["id"]


def update_unidad(unidad_id, **campos):
    todas = get_all_unidades()
    encontrada = False
    for u in todas:
        if u["id"] == unidad_id:
            for k, v in campos.items():
                if k in u:
                    u[k] = str(v)
            encontrada = True
            break
    if not encontrada:
        raise ValueError("No se encontró la unidad indicada.")
    _write_csv(config.UNIDADES_CSV, UNIDADES_CAMPOS, todas)


def update_importe_unidades(unidad_ids, nuevo_importe):
    """Aplica el mismo importe a un conjunto de unidades (por id), sin tocar el resto."""
    ids_set = set(unidad_ids)
    todas = get_all_unidades()
    for u in todas:
        if u["id"] in ids_set:
            u["importe"] = str(nuevo_importe)
    _write_csv(config.UNIDADES_CSV, UNIDADES_CAMPOS, todas)


# ---------------------------------------------------------------------------
# Numeración de recibos (independiente por edificio)
# ---------------------------------------------------------------------------

def get_ultimo_numero(edificio_nombre):
    filas = _read_csv(config.NUMERACION_CSV)
    for f in filas:
        if f["edificio"] == edificio_nombre:
            return int(f["ultimo_recibo"])
    return 0


def get_next_numero(edificio_nombre):
    """
    Incrementa y PERSISTE de inmediato el número de recibo del edificio dado.
    Se debe llamar una vez por cada recibo efectivamente generado.
    """
    filas = _read_csv(config.NUMERACION_CSV)
    encontrado = None
    for f in filas:
        if f["edificio"] == edificio_nombre:
            encontrado = f
            break

    if encontrado is None:
        siguiente = 1
        filas.append({"edificio": edificio_nombre, "ultimo_recibo": "1"})
    else:
        siguiente = int(encontrado["ultimo_recibo"]) + 1
        encontrado["ultimo_recibo"] = str(siguiente)

    _write_csv(config.NUMERACION_CSV, NUMERACION_CAMPOS, filas)
    return siguiente


# ---------------------------------------------------------------------------
# Historial de recibos generados
# ---------------------------------------------------------------------------

def append_historial(registro):
    _append_csv(config.HISTORIAL_CSV, HISTORIAL_CAMPOS, registro)


def get_historial():
    return _read_csv(config.HISTORIAL_CSV)


# ---------------------------------------------------------------------------
# Configuración de la inmobiliaria
# ---------------------------------------------------------------------------

def get_inmobiliaria():
    filas = _read_csv(config.INMOBILIARIA_CSV)
    if filas:
        return filas[0]
    return {"nombre": "", "direccion": "", "telefono": "", "email": "", "cuit": ""}


def save_inmobiliaria(datos):
    fila = {campo: datos.get(campo, "") for campo in INMOBILIARIA_CAMPOS}
    _write_csv(config.INMOBILIARIA_CSV, INMOBILIARIA_CAMPOS, [fila])


# ---------------------------------------------------------------------------
# Editor de datos genérico (para la pantalla "Editor de datos (CSV)")
#
# A propósito NO incluye "numeracion.csv": ese archivo se administra solo
# desde get_next_numero() y no debe editarse a mano desde la interfaz.
# ---------------------------------------------------------------------------

def _tablas_editables():
    return {
        "edificios": (config.EDIFICIOS_CSV, EDIFICIOS_CAMPOS, "Edificios"),
        "unidades": (config.UNIDADES_CSV, UNIDADES_CAMPOS, "Unidades"),
        "inmobiliaria": (config.INMOBILIARIA_CSV, INMOBILIARIA_CAMPOS, "Inmobiliaria"),
        "historial": (config.HISTORIAL_CSV, HISTORIAL_CAMPOS, "Historial de recibos"),
    }


def listar_tablas_editables():
    """Devuelve [(clave_interna, etiqueta_visible), ...] en un orden fijo."""
    orden = ["edificios", "unidades", "inmobiliaria", "historial"]
    tablas = _tablas_editables()
    return [(clave, tablas[clave][2]) for clave in orden]


def get_campos_tabla(clave):
    return list(_tablas_editables()[clave][1])


def leer_tabla(clave):
    """Devuelve (campos, filas) de la tabla indicada, leída desde el CSV."""
    ruta, campos, _etiqueta = _tablas_editables()[clave]
    return list(campos), _read_csv(ruta)


def guardar_tabla(clave, filas):
    """Sobrescribe por completo el CSV de la tabla indicada con 'filas'."""
    ruta, campos, _etiqueta = _tablas_editables()[clave]
    _write_csv(ruta, campos, filas)


# ---------------------------------------------------------------------------
# Copia de seguridad
# ---------------------------------------------------------------------------

def crear_backup():
    """
    Genera un .zip con las carpetas datos/ y configuracion/ dentro de
    BASE_DIR/backups/. Devuelve la ruta del zip creado.
    """
    carpeta_backups = os.path.join(config.BASE_DIR, "backups")
    _ensure_dir(carpeta_backups)

    fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = os.path.join(carpeta_backups, f"backup_expensas_{fecha}.zip")

    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for carpeta in (config.DATOS_DIR, config.CONFIG_DIR):
            if not os.path.isdir(carpeta):
                continue
            for root, _dirs, files in os.walk(carpeta):
                for file in files:
                    ruta_completa = os.path.join(root, file)
                    ruta_relativa = os.path.relpath(ruta_completa, config.BASE_DIR)
                    z.write(ruta_completa, ruta_relativa)

    return destino
