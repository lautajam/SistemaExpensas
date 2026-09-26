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
import shutil
import uuid
import zipfile
from datetime import datetime

import config
import pagos
from unidades import (DEPTO, MODO_TOTAL, TIPOS_ASOCIABLES, etiqueta_unidad, indice_por_id, normalizar_modo,
                      normalizar_tipo)
from utils import sanitize_filename

# ---------------------------------------------------------------------------
# Planillas de pagos (un Excel por edificio, ver pagos.py)
# ---------------------------------------------------------------------------

_AVISOS = []


def sincronizar_pagos(nombre_edificio, reemplazar_ajena=False):
    """
    Deja la planilla de pagos del edificio con una fila por unidad, en orden. Si alguna
    unidad tiene celda asignada (planilla propia), no toca el archivo y devuelve False.
    Un Excel propio sin celdas asignadas tampoco se toca (ver pagos.sincronizar_edificio).
    """
    unidades = get_unidades_por_edificio(nombre_edificio)
    if pagos.modo_celdas(unidades):
        return False
    return pagos.sincronizar_edificio(nombre_edificio, unidades, reemplazar_ajena=reemplazar_ajena)


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

UNIDADES_CAMPOS = ["id", "edificio", "piso", "tipo", "unidad", "uf", "inquilino", "dueno", "importe",
                   "depto_id", "paga_junto", "celda"]
EDIFICIOS_CAMPOS = ["id", "nombre", "direccion", "localidad", "cuit",
                    "admin_nombre", "admin_cuit", "admin_rpac"]
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
    filas = _read_csv(config.EDIFICIOS_CSV)
    for e in filas:
        for campo in EDIFICIOS_CAMPOS:
            if e.get(campo) is None:
                e[campo] = ""
    return filas


def get_edificio(nombre):
    """Devuelve el dict del edificio con ese nombre, o None."""
    return next((e for e in get_edificios() if e["nombre"] == nombre), None)


def get_nombres_edificios():
    return [e["nombre"] for e in get_edificios()]


def _reemplazar_prefijo_archivo(archivo, carpeta_vieja, carpeta_nueva):
    """Reubica la ruta relativa de un PDF del historial si estaba dentro de la carpeta renombrada."""
    prefijo = os.path.relpath(carpeta_vieja, config.BASE_DIR) + os.sep
    if archivo.startswith(prefijo):
        return os.path.relpath(carpeta_nueva, config.BASE_DIR) + os.sep + archivo[len(prefijo):]
    return archivo


def update_edificio(nombre_actual, **datos):
    """
    Guarda los datos del consorcio (nombre, dirección, localidad, cuit y datos del
    administrador). Si cambia el nombre, actualiza en cascada las unidades, la
    numeración y el historial de recibos, y renombra la carpeta de recibos y la
    planilla de pagos. Si algo falla, deja todo como estaba.
    Devuelve el nombre resultante. Lanza ValueError (datos inválidos) o
    PermissionError (hay archivos abiertos que impiden el cambio de nombre).
    """
    edificios = get_edificios()
    edificio = next((e for e in edificios if e["nombre"] == nombre_actual), None)
    if edificio is None:
        raise ValueError("No se encontró el consorcio indicado.")

    nuevo = str(datos.get("nombre", nombre_actual)).strip()
    if not nuevo:
        raise ValueError("El nombre del consorcio no puede estar vacío.")
    if any(o is not edificio and o["nombre"].strip().lower() == nuevo.lower() for o in edificios):
        raise ValueError(f"Ya existe un consorcio llamado «{nuevo}».")

    for campo in EDIFICIOS_CAMPOS:
        if campo not in ("id", "nombre") and campo in datos:
            edificio[campo] = str(datos[campo]).strip()

    if nuevo == nombre_actual:
        _write_csv(config.EDIFICIOS_CSV, EDIFICIOS_CAMPOS, edificios)
        return nombre_actual

    carpeta_vieja, carpeta_nueva = carpeta_edificio(nombre_actual), carpeta_edificio(nuevo)
    if carpeta_vieja != carpeta_nueva and os.path.exists(carpeta_nueva) \
            and os.path.normcase(carpeta_nueva) != os.path.normcase(carpeta_vieja):
        raise ValueError("Ya existe una carpeta de recibos con ese nombre. Elegí otro nombre.")

    csvs = (config.EDIFICIOS_CSV, config.UNIDADES_CSV, config.NUMERACION_CSV, config.HISTORIAL_CSV)
    respaldo = {ruta: open(ruta, "rb").read() for ruta in csvs if os.path.exists(ruta)}
    renombrados = []   # (origen, destino) a deshacer si algo falla
    try:
        if carpeta_vieja != carpeta_nueva and os.path.isdir(carpeta_vieja):
            os.rename(carpeta_vieja, carpeta_nueva)
            renombrados.append((carpeta_vieja, carpeta_nueva))
        cambio = pagos.renombrar_planilla(nombre_actual, nuevo,
                                          actualizar_titulo=not pagos.modo_celdas(get_unidades_por_edificio(nombre_actual)))
        if cambio:
            renombrados.append(cambio)

        unidades = get_all_unidades()
        for u in unidades:
            if u["edificio"] == nombre_actual:
                u["edificio"] = nuevo
        _write_csv(config.UNIDADES_CSV, UNIDADES_CAMPOS, unidades)

        numeracion = _read_csv(config.NUMERACION_CSV)
        for f in numeracion:
            if f["edificio"] == nombre_actual:
                f["edificio"] = nuevo
        _write_csv(config.NUMERACION_CSV, NUMERACION_CAMPOS, numeracion)

        historial = _read_csv(config.HISTORIAL_CSV)
        for r in historial:
            if r["edificio"] == nombre_actual:
                r["edificio"] = nuevo
                r["archivo"] = _reemplazar_prefijo_archivo(r.get("archivo") or "", carpeta_vieja, carpeta_nueva)
        _write_csv(config.HISTORIAL_CSV, HISTORIAL_CAMPOS, historial)

        edificio["nombre"] = nuevo
        _write_csv(config.EDIFICIOS_CSV, EDIFICIOS_CAMPOS, edificios)
    except Exception:
        for origen, destino in reversed(renombrados):
            try:
                os.replace(destino, origen)
            except OSError:
                pass
        for ruta, contenido in respaldo.items():
            with open(ruta, "wb") as f:
                f.write(contenido)
        raise

    _sincronizar_pagos_seguro(nuevo)
    return nuevo


def resumen_edificio(nombre):
    """Cuánto tiene un edificio: {"unidades", "recibos" (en el historial), "pdfs" (en su carpeta), "planilla"}."""
    carpeta = carpeta_edificio(nombre)
    pdfs = sum(1 for _r, _d, archivos in os.walk(carpeta) for a in archivos if a.lower().endswith(".pdf")) \
        if os.path.isdir(carpeta) else 0
    return {
        "unidades": len(get_unidades_por_edificio(nombre)),
        "recibos": sum(1 for r in _read_csv(config.HISTORIAL_CSV) if r.get("edificio") == nombre),
        "pdfs": pdfs,
        "planilla": os.path.isfile(pagos.ruta_pagos_edificio(nombre)),
    }


def _archivos_planilla(nombre):
    """Planilla de pagos del edificio y sus copias de respaldo (rutas completas)."""
    if not os.path.isdir(config.PAGOS_DIR):
        return []
    base = f"{sanitize_filename(nombre)}_pagos"
    return [os.path.join(config.PAGOS_DIR, f) for f in sorted(os.listdir(config.PAGOS_DIR))
            if f.startswith(base) and f.lower().endswith(".xlsx") and not f.startswith("~$")]


def delete_edificio(nombre):
    """
    Borra un edificio de la app SIN perder nada: sus unidades, numeración, historial, la
    carpeta de recibos PDF y la planilla de pagos se guardan en
    datos/edificios_borrados/<nombre>_<fecha>/ (para recuperarlos a mano).
    Devuelve la carpeta de archivo. Lanza ValueError si no existe y PermissionError si hay
    archivos abiertos (planilla en Excel o algún PDF); en cualquier fallo deja todo como estaba.
    """
    edificio = get_edificio(nombre)
    if edificio is None:
        raise ValueError("No se encontró el edificio indicado.")

    destino = os.path.join(config.EDIFICIOS_BORRADOS_DIR, f"{sanitize_filename(nombre)}_{datetime.now():%Y%m%d_%H%M%S}")
    base_destino, n = destino, 2
    while os.path.exists(destino):
        destino, n = f"{base_destino}_{n}", n + 1

    csvs = (config.EDIFICIOS_CSV, config.UNIDADES_CSV, config.NUMERACION_CSV, config.HISTORIAL_CSV)
    respaldo = {ruta: open(ruta, "rb").read() for ruta in csvs if os.path.exists(ruta)}
    movidos = []   # (origen, destino) a deshacer si algo falla
    try:
        os.makedirs(destino)
        _write_csv(os.path.join(destino, "edificio.csv"), EDIFICIOS_CAMPOS, [edificio])
        _write_csv(os.path.join(destino, "unidades.csv"), UNIDADES_CAMPOS,
                   [u for u in get_all_unidades() if u["edificio"] == nombre])
        _write_csv(os.path.join(destino, "historial.csv"), HISTORIAL_CAMPOS,
                   [r for r in _read_csv(config.HISTORIAL_CSV) if r.get("edificio") == nombre])
        _write_csv(os.path.join(destino, "numeracion.csv"), NUMERACION_CAMPOS,
                   [r for r in _read_csv(config.NUMERACION_CSV) if r.get("edificio") == nombre])
        with open(os.path.join(destino, "LEEME.txt"), "w", encoding="utf-8") as f:
            f.write(f"Edificio «{nombre}» borrado el {datetime.now():%d/%m/%Y %H:%M}.\n"
                    "Acá quedaron sus datos: edificio.csv, unidades.csv, historial.csv, numeracion.csv,\n"
                    "la carpeta «recibos» (PDF) y la carpeta «planilla» (Excel de pagos).\n")

        carpeta = carpeta_edificio(nombre)
        if os.path.isdir(carpeta):
            shutil.move(carpeta, os.path.join(destino, "recibos"))
            movidos.append((carpeta, os.path.join(destino, "recibos")))
        for ruta in _archivos_planilla(nombre):
            os.makedirs(os.path.join(destino, "planilla"), exist_ok=True)
            nuevo = os.path.join(destino, "planilla", os.path.basename(ruta))
            shutil.move(ruta, nuevo)
            movidos.append((ruta, nuevo))

        _write_csv(config.EDIFICIOS_CSV, EDIFICIOS_CAMPOS, [e for e in get_edificios() if e["nombre"] != nombre])
        _write_csv(config.UNIDADES_CSV, UNIDADES_CAMPOS, [u for u in get_all_unidades() if u["edificio"] != nombre])
        _write_csv(config.NUMERACION_CSV, NUMERACION_CAMPOS,
                   [r for r in _read_csv(config.NUMERACION_CSV) if r.get("edificio") != nombre])
        _write_csv(config.HISTORIAL_CSV, HISTORIAL_CAMPOS,
                   [r for r in _read_csv(config.HISTORIAL_CSV) if r.get("edificio") != nombre])
    except Exception:
        for origen, nuevo in reversed(movidos):
            try:
                shutil.move(nuevo, origen)
            except OSError:
                pass
        for ruta, contenido in respaldo.items():
            with open(ruta, "wb") as f:
                f.write(contenido)
        if not any(os.path.exists(nuevo) for _origen, nuevo in movidos):   # todo volvió a su lugar: no dejar restos
            shutil.rmtree(destino, ignore_errors=True)
        raise
    return destino


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
    # Versión anterior: la marca "paga todo junto" estaba en el depto y valía para todas
    # sus cocheras/bauleras. Ahora está en cada cochera/baulera (se guarda en la próxima escritura).
    juntos = {u["id"] for u in filas if normalizar_tipo(u["tipo"]) == DEPTO and str(u["paga_junto"]).strip() == "1"}
    if juntos:
        for u in filas:
            if u["id"] in juntos:
                u["paga_junto"] = ""
            elif u["depto_id"] in juntos:
                u["paga_junto"] = "1"
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
            "paga_junto": normalizar_modo(a.get("paga_junto")),
            "celda": pagos.normalizar_celda(a.get("celda")),
        })
        if filas[-1]["paga_junto"] == MODO_TOTAL:   # viene en el total del depto: sin monto ni celda propios
            filas[-1]["importe"], filas[-1]["celda"] = "0", ""
    return filas


def _validar_celdas(unidades, edificio):
    """Dos unidades del mismo edificio no pueden tener la misma celda de la planilla."""
    usadas = {}
    for u in unidades:
        if u["edificio"] != edificio or not u["celda"]:
            continue
        if u["celda"] in usadas:
            raise ValueError(f"La celda {u['celda']} está asignada a dos unidades: "
                             f"{etiqueta_unidad(usadas[u['celda']], indice_por_id(unidades))} y "
                             f"{etiqueta_unidad(u, indice_por_id(unidades))}.")
        usadas[u["celda"]] = u


def add_unidad(edificio, piso, tipo, unidad, inquilino, importe, depto_id="", asociadas=(), uf="", dueno="",
               paga_junto=False, celda=""):
    """
    Agrega una unidad. Si es cochera/baulera, 'depto_id' indica a qué depto pertenece
    (opcional). Si es un depto, 'asociadas' es una lista de dicts
    {tipo, piso, unidad, uf, dueno, importe, celda} con cocheras/bauleras que se crean
    junto con él (heredan su inquilino). 'celda' es la celda de la planilla de pagos
    donde figura la unidad (opcional, ej. B12). Devuelve el id de la unidad creada.
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
        "paga_junto": normalizar_modo(paga_junto) if tipo in TIPOS_ASOCIABLES and depto_id else "",
        "celda": pagos.normalizar_celda(celda),
    }
    if nueva["paga_junto"] == MODO_TOTAL:
        nueva["importe"], nueva["celda"] = "0", ""
    todas.append(nueva)
    if asociadas:
        if tipo != DEPTO:
            raise ValueError("Solo un depto puede tener cocheras o bauleras asociadas.")
        todas.extend(_filas_asociadas(nueva, asociadas))
    _validar_celdas(todas, edificio)
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
    _validar_celdas(todas, depto["edificio"])
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
    # "Paga junto con su depto": solo tiene sentido en una cochera/baulera que pertenece a un depto.
    u["paga_junto"] = normalizar_modo(u["paga_junto"]) if u["depto_id"] else ""
    u["celda"] = pagos.normalizar_celda(u["celda"])
    if u["paga_junto"] == MODO_TOTAL:   # viene en el total del depto: sin monto ni celda propios
        u["importe"], u["celda"] = "0", ""
    _validar_celdas(todas, u["edificio"])

    # Si cambia el inquilino de un depto, lo heredan sus cocheras/bauleras que tenían el mismo.
    if u["tipo"] == DEPTO and u["inquilino"] != inquilino_anterior:
        for x in todas:
            if x["depto_id"] == unidad_id and x["inquilino"] == inquilino_anterior:
                x["inquilino"] = u["inquilino"]

    _write_csv(config.UNIDADES_CSV, UNIDADES_CAMPOS, todas)
    for nombre in edificios_afectados:
        _sincronizar_pagos_seguro(nombre)


def set_celdas(edificio, celdas_por_id):
    """
    Fija la celda de la planilla de pagos de cada unidad indicada ({id: celda}; vacío la
    quita), sin tocar el resto. Lanza ValueError si una celda es inválida o está repetida.
    Nunca modifica el archivo de la planilla.
    """
    todas = get_all_unidades()
    for u in todas:
        if u["edificio"] == edificio and u["id"] in celdas_por_id:
            u["celda"] = "" if normalizar_modo(u["paga_junto"]) == MODO_TOTAL and u["depto_id"] \
                else pagos.normalizar_celda(celdas_por_id[u["id"]])
    _validar_celdas(todas, edificio)
    _write_csv(config.UNIDADES_CSV, UNIDADES_CAMPOS, todas)


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
