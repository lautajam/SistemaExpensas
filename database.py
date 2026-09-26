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
import pagos
from unidades import DEPTO, TIPOS_ASOCIABLES, normalizar_tipo
from utils import sanitize_filename

# ---------------------------------------------------------------------------
# Planillas de pagos (un Excel por edificio, ver pagos.py)
# ---------------------------------------------------------------------------

_AVISOS = []


def sincronizar_pagos(nombre_edificio):
    """Deja la planilla de pagos del edificio con una fila por unidad, en orden."""
    return pagos.sincronizar_edificio(nombre_edificio, get_unidades_por_edificio(nombre_edificio))


def _sincronizar_pagos_seguro(nombre_edificio):
    """Igual que sincronizar_pagos, pero un fallo (ej. Excel abierto) no interrumpe: queda como aviso."""
    try:
        sincronizar_pagos(nombre_edificio)
    except PermissionError:
        _AVISOS.append(
            f"No se pudo actualizar la planilla de pagos de «{nombre_edificio}» porque está abierta.\n\n"
            "Cerrá el archivo de Excel: la próxima vez que se guarde algo se actualizará sola."
        )
    except Exception as e:
        _AVISOS.append(f"No se pudo actualizar la planilla de pagos de «{nombre_edificio}»:\n{e}")


def tomar_avisos():
    """Devuelve (y vacía) los avisos pendientes sobre las planillas de pagos."""
    avisos = list(_AVISOS)
    _AVISOS.clear()
    return avisos


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

UNIDADES_CAMPOS = ["id", "edificio", "piso", "tipo", "unidad", "uf", "inquilino", "dueno", "importe", "depto_id"]
EDIFICIOS_CAMPOS = ["id", "nombre"]
NUMERACION_CAMPOS = ["edificio", "ultimo_recibo"]
HISTORIAL_CAMPOS = [
    "numero_recibo", "edificio", "fecha", "expensas_de", "gastos_de",
    "piso", "tipo", "unidad", "inquilino", "importe", "archivo",
]
INMOBILIARIA_CAMPOS = ["nombre", "subtitulo", "direccion", "telefono", "email"]


def ensure_data_files():
    """Crea toda la estructura de carpetas/archivos si no existe todavía."""
    _ensure_dir(config.DATOS_DIR)
    _ensure_dir(config.CONFIG_DIR)
    _ensure_dir(config.EDIFICIOS_DIR)
    _ensure_dir(config.PLANTILLA_DIR)
    _ensure_dir(config.PAGOS_DIR)

    if not os.path.exists(config.EDIFICIOS_CSV):
        edificios_ejemplo = [
            {"id": "1", "nombre": "Edificio Alsina 123"},
            {"id": "2", "nombre": "Edificio Mitre 456"},
        ]
        _write_csv(config.EDIFICIOS_CSV, EDIFICIOS_CAMPOS, edificios_ejemplo)
        for e in edificios_ejemplo:
            crear_carpeta_edificio(e["nombre"])

    if not os.path.exists(config.UNIDADES_CSV):
        def _u(edificio, piso, tipo, unidad, inquilino, importe, depto_id=""):
            return {"id": uuid.uuid4().hex[:8], "edificio": edificio, "piso": piso, "tipo": tipo,
                    "unidad": unidad, "uf": "", "inquilino": inquilino, "dueno": "",
                    "importe": importe, "depto_id": depto_id}

        alsina, mitre = "Edificio Alsina 123", "Edificio Mitre 456"
        a_pb1 = _u(alsina, "PB", "DEPTO", "1", "Ana Pérez", "45000")
        a_1a = _u(alsina, "1°", "DEPTO", "A", "Carlos López", "45000")
        m_1a = _u(mitre, "1°", "DEPTO", "A", "Diego Álvarez", "40000")
        unidades_ejemplo = [
            a_pb1, a_1a,
            _u(alsina, "1°", "DEPTO", "B", "María García", "45000"),
            _u(alsina, "2°", "DEPTO", "A", "Pedro Rodríguez", "48000"),
            _u(alsina, "PB", "LOCAL", "1", "Kiosco Sur SRL", "60000"),
            _u(alsina, "", "COCHERA", "3", "Carlos López", "12000", a_1a["id"]),
            _u(mitre, "PB", "DEPTO", "1", "Laura Fernández", "38000"),
            m_1a,
            _u(mitre, "1°", "DEPTO", "B", "Silvia Ruiz", "40000"),
            _u(mitre, "", "BAULERA", "14", "Diego Álvarez", "8000", m_1a["id"]),
        ]
        _write_csv(config.UNIDADES_CSV, UNIDADES_CAMPOS, unidades_ejemplo)

    if not os.path.exists(config.NUMERACION_CSV):
        _write_csv(config.NUMERACION_CSV, NUMERACION_CAMPOS, [])

    if not os.path.exists(config.HISTORIAL_CSV):
        _write_csv(config.HISTORIAL_CSV, HISTORIAL_CAMPOS, [])

    if not os.path.exists(config.INMOBILIARIA_CSV):
        _write_csv(config.INMOBILIARIA_CSV, INMOBILIARIA_CAMPOS, [{
            "nombre": "MI INMOBILIARIA",
            "subtitulo": "ADMINISTRACIÓN DE CONSORCIOS",
            "direccion": "Av. Ejemplo 1234, CABA",
            "telefono": "011-4444-5555",
            "email": "contacto@miinmobiliaria.com",
        }])

    # Asegura que exista la carpeta de cada edificio ya cargado
    for e in get_edificios():
        crear_carpeta_edificio(e["nombre"])
        _sincronizar_pagos_seguro(e["nombre"])


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
    _sincronizar_pagos_seguro(nombre)
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
    filas = _read_csv(config.UNIDADES_CSV)
    for u in filas:
        for campo in UNIDADES_CAMPOS:
            if u.get(campo) is None:
                u[campo] = ""
    return filas


def get_unidades_por_edificio(nombre_edificio):
    return [u for u in get_all_unidades() if u["edificio"] == nombre_edificio]


def _depto_valido(todas, edificio, tipo, depto_id):
    """
    Devuelve el depto_id a guardar. Solo cochera y baulera pueden pertenecer a un
    depto (para el resto queda vacío); el depto debe existir en el mismo edificio.
    """
    if tipo not in TIPOS_ASOCIABLES or not depto_id:
        return ""
    depto = next((x for x in todas if x["id"] == depto_id), None)
    if depto is None or normalizar_tipo(depto["tipo"]) != DEPTO or depto["edificio"] != edificio:
        raise ValueError("El depto elegido no existe en este edificio.")
    return depto_id


def _filas_asociadas(depto, asociadas):
    filas = []
    for a in asociadas:
        tipo = normalizar_tipo(a.get("tipo"))
        if tipo not in TIPOS_ASOCIABLES:
            raise ValueError("A un depto solo se le pueden asociar cocheras y bauleras.")
        numero = str(a.get("unidad", "")).strip()
        if not numero:
            raise ValueError("Falta el número de la cochera o baulera.")
        filas.append({
            "id": uuid.uuid4().hex[:8],
            "edificio": depto["edificio"],
            "piso": str(a.get("piso", "")).strip(),
            "tipo": tipo,
            "unidad": numero,
            "uf": str(a.get("uf", "")).strip(),
            "inquilino": str(a.get("inquilino", depto["inquilino"])),
            "dueno": str(a.get("dueno", "")).strip(),
            "importe": str(a.get("importe", "0")),
            "depto_id": depto["id"],
        })
    return filas


def add_unidad(edificio, piso, tipo, unidad, inquilino, importe, depto_id="", asociadas=(), uf="", dueno=""):
    """
    Agrega una unidad. Si es cochera/baulera, 'depto_id' indica a qué depto pertenece
    (opcional). Si es un depto, 'asociadas' es una lista de dicts
    {tipo, piso, unidad, uf, dueno, importe} con cocheras/bauleras que se crean junto
    con él (heredan su inquilino). Devuelve el id de la unidad creada.
    """
    todas = get_all_unidades()
    tipo = normalizar_tipo(tipo)
    nueva = {
        "id": uuid.uuid4().hex[:8],
        "edificio": edificio,
        "piso": piso,
        "tipo": tipo,
        "unidad": unidad,
        "uf": str(uf).strip(),
        "inquilino": inquilino,
        "dueno": str(dueno).strip(),
        "importe": str(importe),
        "depto_id": _depto_valido(todas, edificio, tipo, depto_id),
    }
    todas.append(nueva)
    if asociadas:
        if tipo != DEPTO:
            raise ValueError("Solo un depto puede tener cocheras o bauleras asociadas.")
        todas.extend(_filas_asociadas(nueva, asociadas))
    _write_csv(config.UNIDADES_CSV, UNIDADES_CAMPOS, todas)
    _sincronizar_pagos_seguro(edificio)
    return nueva["id"]


def add_asociadas(depto_id, asociadas):
    """Agrega cocheras/bauleras nuevas a un depto ya existente."""
    todas = get_all_unidades()
    depto = next((x for x in todas if x["id"] == depto_id), None)
    if depto is None or normalizar_tipo(depto["tipo"]) != DEPTO:
        raise ValueError("El depto indicado no existe.")
    todas.extend(_filas_asociadas(depto, asociadas))
    _write_csv(config.UNIDADES_CSV, UNIDADES_CAMPOS, todas)
    _sincronizar_pagos_seguro(depto["edificio"])


def update_unidad(unidad_id, **campos):
    todas = get_all_unidades()
    u = next((x for x in todas if x["id"] == unidad_id), None)
    if u is None:
        raise ValueError("No se encontró la unidad indicada.")

    edificios_afectados = {u["edificio"]}
    inquilino_anterior = u["inquilino"]
    for k, v in campos.items():
        if k in UNIDADES_CAMPOS:
            u[k] = str(v)
    edificios_afectados.add(u["edificio"])

    u["tipo"] = normalizar_tipo(u["tipo"])
    if u["tipo"] != DEPTO and any(x["depto_id"] == unidad_id for x in todas):
        raise ValueError(
            "Este depto tiene cocheras o bauleras asociadas: pasalas a otro depto "
            "antes de cambiarle el tipo."
        )
    u["depto_id"] = _depto_valido(todas, u["edificio"], u["tipo"], u["depto_id"])

    # Si cambia el inquilino de un depto, lo heredan sus cocheras/bauleras que tenían el mismo.
    if u["tipo"] == DEPTO and u["inquilino"] != inquilino_anterior:
        for x in todas:
            if x["depto_id"] == unidad_id and x["inquilino"] == inquilino_anterior:
                x["inquilino"] = u["inquilino"]

    _write_csv(config.UNIDADES_CSV, UNIDADES_CAMPOS, todas)
    for nombre in edificios_afectados:
        _sincronizar_pagos_seguro(nombre)


def set_importes(importes_por_id):
    """Fija el importe de cada unidad indicada ({id: importe}), sin tocar el resto."""
    todas = get_all_unidades()
    for u in todas:
        if u["id"] in importes_por_id:
            u["importe"] = str(importes_por_id[u["id"]])
    _write_csv(config.UNIDADES_CSV, UNIDADES_CAMPOS, todas)


def unidades_a_borrar(unidad_id):
    """Devuelve la unidad indicada seguida de sus cocheras/bauleras (si es un depto). [] si no existe."""
    todas = get_all_unidades()
    u = next((x for x in todas if x["id"] == unidad_id), None)
    if u is None:
        return []
    return [u] + [x for x in todas if x["depto_id"] == unidad_id]


def delete_unidad(unidad_id):
    """
    Borra la unidad; si es un depto, también sus cocheras y bauleras. Las quita de
    la planilla de pagos del edificio. Los recibos ya generados y el historial no
    se tocan. Devuelve la lista de unidades borradas.
    """
    borradas = unidades_a_borrar(unidad_id)
    if not borradas:
        raise ValueError("No se encontró la unidad indicada.")
    ids = {u["id"] for u in borradas}
    restantes = [u for u in get_all_unidades() if u["id"] not in ids]
    _write_csv(config.UNIDADES_CSV, UNIDADES_CAMPOS, restantes)
    _sincronizar_pagos_seguro(borradas[0]["edificio"])
    return borradas


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
    fila = filas[0] if filas else {}
    return {campo: fila.get(campo) or "" for campo in INMOBILIARIA_CAMPOS}


def save_inmobiliaria(datos):
    fila = {campo: datos.get(campo, "") for campo in INMOBILIARIA_CAMPOS}
    _write_csv(config.INMOBILIARIA_CSV, INMOBILIARIA_CAMPOS, [fila])


# Logo y firma digital de la inmobiliaria: se guardan como configuracion/logo.png y
# configuracion/firma.png (todavía no se usan en ningún recibo).

MAX_LADO_IMAGEN = 1200


def imagen_inmobiliaria(clave):
    """Ruta de la imagen guardada ('logo' o 'firma'), o None si no hay."""
    ruta = config.IMAGENES_INMOBILIARIA[clave]
    return ruta if os.path.isfile(ruta) else None


def guardar_imagen_inmobiliaria(clave, ruta_origen):
    """
    Lee una imagen (PNG, JPG, GIF, BMP...), la achica si es enorme y la guarda
    como PNG en configuracion/. Conserva la transparencia si la tiene.
    Lanza ValueError si el archivo no es una imagen válida.
    """
    from PIL import Image, UnidentifiedImageError

    destino = config.IMAGENES_INMOBILIARIA[clave]
    try:
        with Image.open(ruta_origen) as original:
            imagen = original.convert("RGBA")
    except (UnidentifiedImageError, OSError) as e:
        raise ValueError("El archivo elegido no es una imagen válida (usá PNG o JPG).") from e

    imagen.thumbnail((MAX_LADO_IMAGEN, MAX_LADO_IMAGEN))
    if imagen.getchannel("A").getextrema()[0] == 255:
        imagen = imagen.convert("RGB")  # sin transparencia: archivo más liviano

    _ensure_dir(config.CONFIG_DIR)
    temporal = destino + ".tmp"
    imagen.save(temporal, format="PNG")
    os.replace(temporal, destino)
    return destino


def quitar_imagen_inmobiliaria(clave):
    ruta = config.IMAGENES_INMOBILIARIA[clave]
    if os.path.isfile(ruta):
        os.remove(ruta)


# ---------------------------------------------------------------------------
# Preferencias del usuario (configuracion/preferencias.csv: clave, valor)
# ---------------------------------------------------------------------------

PREFERENCIAS_CAMPOS = ["clave", "valor"]


def get_preferencia(clave, por_defecto=""):
    for fila in _read_csv(config.PREFERENCIAS_CSV):
        if fila.get("clave") == clave:
            return fila.get("valor") or por_defecto
    return por_defecto


def set_preferencia(clave, valor):
    filas = [f for f in _read_csv(config.PREFERENCIAS_CSV) if f.get("clave") != clave]
    filas.append({"clave": clave, "valor": str(valor)})
    _write_csv(config.PREFERENCIAS_CSV, PREFERENCIAS_CAMPOS, filas)


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
    if clave in ("edificios", "unidades"):
        for e in get_edificios():
            _sincronizar_pagos_seguro(e["nombre"])


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
