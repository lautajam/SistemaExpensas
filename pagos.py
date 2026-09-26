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
    fila 4+: una fila por unidad, ordenadas por piso y unidad
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


def etiqueta_unidad(u):
    """Texto que se ve en la columna 'Tipo unidad', ej.: '1° A', 'PB COCH 3'."""
    piso = (u.get("piso") or "").strip()
    tipo = (u.get("tipo") or "").strip()
    unidad = (u.get("unidad") or "").strip()
    partes = [piso]
    if tipo and tipo.upper() not in ("DEPTO", piso.upper(), unidad.upper()):
        partes.append(tipo)
    partes.append(unidad)
    return " ".join(p for p in partes if p)


def _natural(texto):
    return [(0, int(p), "") if p.isdigit() else (1, 0, p.lower())
            for p in re.findall(r"\d+|\D+", str(texto or "")) if p.strip()]


def _clave_piso(piso):
    p = str(piso or "").replace("°", "").replace("º", "").strip()
    if p.upper() in ("PB", "P B", "PLANTA BAJA"):
        return (0, 0, "")
    m = re.match(r"\d+", p)
    if m:
        return (1, int(m.group()), "")
    return (2, 0, p.lower())


def _clave_orden(u):
    tipo = (u.get("tipo") or "").strip().upper()
    return (_clave_piso(u.get("piso")), 0 if tipo in ("", "DEPTO") else 1, tipo, _natural(u.get("unidad")))


# ---------------------------------------------------------------------------
# Escritura de la planilla
# ---------------------------------------------------------------------------

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

    deseadas = sorted(unidades, key=_clave_orden)
    ids = [u["id"] for u in deseadas]
    etiquetas = [etiqueta_unidad(u) for u in deseadas]

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


def leer_estados(nombre_edificio):
    """
    Devuelve {id_unidad: estado} leyendo el 'Tipo pago' de la planilla del
    edificio. Si el Excel no guardó el resultado de la fórmula, se calcula
    con la misma lógica. Lanza FileNotFoundError si la planilla no existe.
    """
    ruta = ruta_pagos_edificio(nombre_edificio)
    if not os.path.isfile(ruta):
        raise FileNotFoundError(f"No se encontró la planilla de pagos:\n{ruta}")

    wb = load_workbook(ruta, data_only=True)
    try:
        ws = wb.worksheets[0]
        estados = {}
        for r in range(FILA_INICIO, ws.max_row + 1):
            uid = ws.cell(r, COL_ID).value
            if not uid or str(uid) in estados:
                continue
            estado = ws.cell(r, COL_ESTADO).value
            if estado in (None, "") or str(estado).startswith(("=", "#")):
                estado = _calcular_estado(
                    ws.cell(r, COL_TOTAL).value, ws.cell(r, COL_DEUDA).value, ws.cell(r, COL_PAGADO).value
                )
            estados[str(uid)] = str(estado).strip()
        return estados
    finally:
        wb.close()


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
