# -*- coding: utf-8 -*-
"""
pagos.py
--------
Planillas de pagos: un Excel por edificio en datos/pagos_edificios/, llamado
"<Nombre_Edificio>_pagos.xlsx". La app lo crea y mantiene ordenado sola
(una fila por unidad); las personas solo cargan los montos de cada mes.

Diseño de la hoja:
    fila 2:  nombre del edificio
    fila 3:  Tipo unidad | Total a pagar | Monto deuda | Monto pagado | Tipo pago
    fila 4+: una fila por unidad (deptos, locales, cocheras, bauleras), en
             orden de piso y unidad, con cada depto seguido de sus cocheras
             y bauleras
    columna H (oculta): id interno de la unidad. Es lo que vincula cada fila
    con su unidad, aunque cambie el piso/letra o se reordenen las filas.

"Tipo pago" es una fórmula de Excel. Para cambiar qué texto se imprime en
"Gastos de" por cada estado, editar TEXTO_POR_ESTADO.
"""

import os
import re
import unicodedata

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, Side

import config
from unidades import etiqueta_unidad, indice_por_id, ordenar_con_asociadas
from utils import parse_importe, sanitize_filename

ENCABEZADOS = ["Tipo unidad", "Total a pagar", "Monto deuda", "Monto pagado", "Tipo pago"]
FILA_TITULO, FILA_ENCABEZADO, FILA_INICIO = 2, 3, 4
COL_ETIQUETA, COL_TOTAL, COL_DEUDA, COL_PAGADO, COL_ESTADO, COL_ID = 2, 3, 4, 5, 6, 8

# Estado (tal como lo calcula la fórmula del Excel) -> texto de "Gastos de".
# None significa "usar el mes anterior".
TEXTO_POR_ESTADO = {
    "total": None,
    "parcial": "PARCIAL",
    "deuda": "DEUDA",
    "no pagado": "NO PAGADO",
}


# ---------------------------------------------------------------------------
# Rutas, etiquetas y orden
# ---------------------------------------------------------------------------

def ruta_pagos_edificio(nombre_edificio):
    return os.path.join(config.PAGOS_DIR, f"{sanitize_filename(nombre_edificio)}_pagos.xlsx")


# ---------------------------------------------------------------------------
# Escritura de la planilla
# ---------------------------------------------------------------------------

def renombrar_planilla(nombre_viejo, nombre_nuevo):
    """
    Renombra el archivo de la planilla de un edificio y actualiza el título (B2).
    Devuelve (ruta_vieja, ruta_nueva), o None si no había planilla. Lanza
    PermissionError si el archivo está abierto en Excel.
    """
    origen, destino = ruta_pagos_edificio(nombre_viejo), ruta_pagos_edificio(nombre_nuevo)
    if not os.path.isfile(origen):
        return None
    if os.path.exists(destino) and os.path.normcase(destino) != os.path.normcase(origen):
        raise ValueError("Ya existe una planilla de pagos con ese nombre.")
    os.replace(origen, destino)
    try:
        wb = load_workbook(destino)
        try:
            wb.worksheets[0].cell(FILA_TITULO, 2).value = nombre_nuevo
            wb.save(destino)
        finally:
            wb.close()
    except Exception:
        os.replace(destino, origen)
        raise
    return origen, destino


def _borde(izq="thin", der="thin", arr="thin", aba="thin"):
    return Border(left=Side(style=izq), right=Side(style=der), top=Side(style=arr), bottom=Side(style=aba))


def _formula_estado(r):
    return f'=IF(E{r}=0,"No pagado",IF(E{r}=D{r},"Deuda",IF(E{r}=C{r}+D{r},"Total","Parcial")))'


def _leer_existente(ruta):
    """Devuelve (orden_ids, etiquetas, valores) de la planilla actual, o listas vacías."""
    wb = load_workbook(ruta, data_only=False)
    try:
        ws = wb.worksheets[0]
        orden, etiquetas, valores = [], [], {}
        for r in range(FILA_INICIO, ws.max_row + 1):
            uid = ws.cell(r, COL_ID).value
            if not uid or uid in valores:
                continue
            uid = str(uid)
            orden.append(uid)
            etiquetas.append(ws.cell(r, COL_ETIQUETA).value)
            valores[uid] = (ws.cell(r, COL_TOTAL).value, ws.cell(r, COL_DEUDA).value, ws.cell(r, COL_PAGADO).value)
        return orden, etiquetas, valores
    finally:
        wb.close()


def sincronizar_edificio(nombre_edificio, unidades):
    """
    Crea o actualiza la planilla del edificio para que tenga exactamente una
    fila por unidad, en orden, conservando los montos ya cargados.
    Devuelve True si escribió el archivo. Lanza PermissionError si el archivo
    está abierto en Excel.
    """
    ruta = ruta_pagos_edificio(nombre_edificio)
    os.makedirs(config.PAGOS_DIR, exist_ok=True)

    por_id = indice_por_id(unidades)
    deseadas = [u for u, _nivel in ordenar_con_asociadas(unidades)]
    ids = [u["id"] for u in deseadas]
    etiquetas = [etiqueta_unidad(u, por_id) for u in deseadas]

    valores = {}
    if os.path.isfile(ruta):
        orden_actual, etiquetas_actuales, valores = _leer_existente(ruta)
        if orden_actual == ids and etiquetas_actuales == etiquetas:
            return False

    wb = Workbook()
    ws = wb.active
    ws.title = "Hoja 1"
    fuente, fuente_b = Font(name="Arial"), Font(name="Arial", bold=True)
    centro = Alignment(horizontal="center", vertical="center")

    ws.merge_cells(start_row=FILA_TITULO, start_column=2, end_row=FILA_TITULO, end_column=6)
    for c in range(2, 7):
        celda = ws.cell(FILA_TITULO, c)
        celda.border = _borde("medium" if c == 2 else None, "medium" if c == 6 else None, "medium", "medium")
    ws.cell(FILA_TITULO, 2, nombre_edificio).font = fuente_b
    ws.cell(FILA_TITULO, 2).alignment = centro

    for i, titulo in enumerate(ENCABEZADOS):
        c = ws.cell(FILA_ENCABEZADO, 2 + i, titulo)
        c.font, c.alignment = fuente_b, centro
        c.border = _borde("medium" if i == 0 else "thin", "medium" if i == 4 else "thin", "medium", "medium")

    for i, u in enumerate(deseadas):
        r = FILA_INICIO + i
        ultima = i == len(deseadas) - 1
        anteriores = valores.get(u["id"], (None, None, None))
        contenido = [etiquetas[i], *anteriores, _formula_estado(r)]
        for j, valor in enumerate(contenido):
            c = ws.cell(r, 2 + j, valor)
            c.font, c.alignment = fuente, centro
            if 1 <= j <= 3:
                c.number_format = "#,##0.00"
            c.border = _borde("medium" if j == 0 else "thin", "medium" if j == 4 else "thin",
                              "medium" if i == 0 else "thin", "medium" if ultima else "thin")
        ws.cell(r, COL_ID, u["id"])

    ws.column_dimensions["A"].width = 3.5
    ws.column_dimensions["B"].width = 22
    for letra in "CDEF":
        ws.column_dimensions[letra].width = 17
    ws.column_dimensions["H"].hidden = True
    ws.freeze_panes = "A4"
    wb.calculation.fullCalcOnLoad = True

    temporal = ruta + ".tmp"
    wb.save(temporal)
    try:
        os.replace(temporal, ruta)
    except Exception:
        if os.path.exists(temporal):
            os.remove(temporal)
        raise
    return True


# ---------------------------------------------------------------------------
# Lectura para generar recibos
# ---------------------------------------------------------------------------

def _calcular_estado(total, deuda, pagado):
    """Misma lógica que la fórmula de la columna 'Tipo pago' del Excel."""
    total, deuda, pagado = parse_importe(total), parse_importe(deuda), parse_importe(pagado)
    if pagado == 0:
        return "No pagado"
    if pagado == deuda:
        return "Deuda"
    if pagado == total + deuda:
        return "Total"
    return "Parcial"


def planilla_abierta(nombre_edificio):
    """
    True si la planilla figura abierta en Excel o LibreOffice (existe su archivo de
    bloqueo). En ese caso lo que se escribió y no se guardó todavía no se ve desde la app.
    """
    ruta = ruta_pagos_edificio(nombre_edificio)
    carpeta, nombre = os.path.split(ruta)
    return os.path.exists(os.path.join(carpeta, "~$" + nombre)) or \
        os.path.exists(os.path.join(carpeta, ".~lock." + nombre + "#"))


def leer_planilla(nombre_edificio):
    """
    Devuelve {id_unidad: {"total", "deuda", "pagado", "estado"}} con lo que está
    GUARDADO en la planilla del edificio. Si el Excel no guardó el resultado de la
    fórmula "Tipo pago", el estado se calcula con la misma lógica. Lanza
    FileNotFoundError si la planilla no existe.
    """
    ruta = ruta_pagos_edificio(nombre_edificio)
    if not os.path.isfile(ruta):
        raise FileNotFoundError(f"No se encontró la planilla de pagos:\n{ruta}")

    wb = load_workbook(ruta, data_only=True)
    try:
        ws = wb.worksheets[0]
        datos = {}
        for r in range(FILA_INICIO, ws.max_row + 1):
            uid = ws.cell(r, COL_ID).value
            if not uid or str(uid) in datos:
                continue
            total, deuda, pagado = (ws.cell(r, c).value for c in (COL_TOTAL, COL_DEUDA, COL_PAGADO))
            estado = ws.cell(r, COL_ESTADO).value
            if estado in (None, "") or str(estado).startswith(("=", "#")):
                estado = _calcular_estado(total, deuda, pagado)
            datos[str(uid)] = {
                "total": parse_importe(total), "deuda": parse_importe(deuda),
                "pagado": parse_importe(pagado), "estado": str(estado).strip(),
            }
        return datos
    finally:
        wb.close()


def leer_estados(nombre_edificio):
    """Devuelve {id_unidad: estado} (ver leer_planilla)."""
    return {uid: d["estado"] for uid, d in leer_planilla(nombre_edificio).items()}


def _norm(texto):
    t = unicodedata.normalize("NFKD", str(texto or ""))
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in t if not unicodedata.combining(c)).lower()).strip()


def gastos_de_unidad(estados, unidad, mes_anterior):
    """
    Devuelve (texto_gastos_de, estado). 'estado' es el "Tipo pago" de la
    planilla, o None si la unidad no figura (en ese caso: mes anterior).
    """
    estado = estados.get(str(unidad["id"]))
    if estado is None:
        return mes_anterior, None
    texto = TEXTO_POR_ESTADO.get(_norm(estado), estado.upper())
    return (mes_anterior if texto is None else texto), estado
