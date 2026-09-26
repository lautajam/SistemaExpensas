# -*- coding: utf-8 -*-
"""
unidades.py
-----------
Tipos de unidad (depto, local, cochera, baulera), cómo se nombran y cómo se
ordenan. Son funciones puras: no leen ni escriben archivos.

Relación: un DEPTO puede tener varias (o ninguna) COCHERA y varias (o
ninguna) BAULERA. Cada cochera/baulera guarda en la columna "depto_id" el id
del depto al que pertenece (vacío si es independiente). Los LOCALES y los
deptos nunca pertenecen a otra unidad.
"""

import re

DEPTO, LOCAL, COCHERA, BAULERA = "DEPTO", "LOCAL", "COCHERA", "BAULERA"
TIPOS = [DEPTO, LOCAL, COCHERA, BAULERA]
TIPOS_ASOCIABLES = (COCHERA, BAULERA)

_ALIAS = {"COCH": COCHERA, "COC": COCHERA, "BAU": BAULERA, "DPTO": DEPTO, "DEPARTAMENTO": DEPTO}
_ORDEN_TIPO = {DEPTO: 0, LOCAL: 1, COCHERA: 2, BAULERA: 3}


def normalizar_tipo(tipo):
    """Devuelve uno de TIPOS. Alias viejos (COCH, BAU) se convierten; lo desconocido cuenta como DEPTO."""
    t = str(tipo or "").strip().upper()
    if t in TIPOS:
        return t
    return _ALIAS.get(t, DEPTO)


def nombre_tipo(tipo):
    """Nombre para mostrar: 'Depto', 'Local', 'Cochera', 'Baulera'."""
    return normalizar_tipo(tipo).capitalize()


def indice_por_id(unidades):
    return {u["id"]: u for u in unidades}


def depto_de(unidad, por_id):
    """Devuelve el depto al que pertenece una cochera/baulera, o None."""
    if normalizar_tipo(unidad.get("tipo")) not in TIPOS_ASOCIABLES:
        return None
    depto = por_id.get(unidad.get("depto_id") or "")
    if depto is not None and normalizar_tipo(depto.get("tipo")) == DEPTO:
        return depto
    return None


def etiqueta_unidad(u, por_id=None):
    """
    Texto corto que identifica la unidad: '1° A' (depto), 'Local PB 1',
    'Cochera 3 (1° A)' (cochera de un depto), 'Baulera 2'.
    """
    tipo = normalizar_tipo(u.get("tipo"))
    piso = (u.get("piso") or "").strip()
    unidad = (u.get("unidad") or "").strip()
    if tipo == DEPTO:
        return " ".join(p for p in (piso, unidad) if p)
    base = " ".join(p for p in (nombre_tipo(tipo), piso, unidad) if p)
    depto = depto_de(u, por_id or {})
    return f"{base} ({etiqueta_unidad(depto)})" if depto else base


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


def _clave_principal(u):
    return (_clave_piso(u.get("piso")), _ORDEN_TIPO[normalizar_tipo(u.get("tipo"))], _natural(u.get("unidad")))


def _clave_asociada(u):
    return (_ORDEN_TIPO[normalizar_tipo(u.get("tipo"))], _clave_piso(u.get("piso")), _natural(u.get("unidad")))


# Cómo paga una cochera/baulera que pertenece a un depto (columna paga_junto de unidades.csv)
MODO_APARTE, MODO_JUNTO, MODO_TOTAL = "", "1", "T"


def normalizar_modo(valor):
    """Devuelve MODO_TOTAL, MODO_JUNTO o MODO_APARTE a partir de lo guardado (o de un True/False)."""
    v = str(valor if valor is not None else "").strip().upper()
    return MODO_TOTAL if v == "T" else MODO_JUNTO if v in ("1", "TRUE") else MODO_APARTE


def modo_pago(u):
    """
    'recibo aparte' (MODO_APARTE), 'paga junto con su depto' (MODO_JUNTO: un solo recibo, pero tiene
    su propia fila en la planilla) o 'incluida en el total del depto' (MODO_TOTAL: un solo recibo y sin
    fila propia, porque su monto ya viene en el total del depto). Solo una cochera/baulera con depto.
    """
    if normalizar_tipo(u.get("tipo")) not in TIPOS_ASOCIABLES or not u.get("depto_id"):
        return MODO_APARTE
    return normalizar_modo(u.get("paga_junto"))


def paga_junto(u):
    """True si la cochera/baulera va en el mismo recibo que su depto (paga junto o incluida en el total)."""
    return modo_pago(u) != MODO_APARTE


def incluida_en_total(u):
    """True si su monto ya viene en el total del depto: no tiene fila propia en la planilla."""
    return modo_pago(u) == MODO_TOTAL


def descripcion_asociadas(asociadas):
    """'Cochera 6 y Baulera 2' / 'Cochera 6, Cochera 7 y Baulera 2' (vacío si no hay)."""
    textos = [etiqueta_unidad(h) for h in asociadas]
    if len(textos) <= 1:
        return "".join(textos)
    return ", ".join(textos[:-1]) + " y " + textos[-1]


def ordenar_para_pantalla(unidades):
    """
    Como ordenar_con_asociadas, pero las cocheras y bauleras marcadas como 'paga junto con
    su depto' no aparecen sueltas: van en la fila de su depto. Devuelve
    [(unidad, nivel, agrupadas)], donde 'agrupadas' son las que ese depto paga junto.
    """
    ordenadas = ordenar_con_asociadas(unidades)
    hijas = asociadas_que_pagan_junto(unidades)
    return [(u, nivel, hijas.get(u["id"], [])) for u, nivel in ordenadas
            if not (nivel == 1 and paga_junto(u))]


def asociadas_que_pagan_junto(unidades):
    """{id_depto: [cocheras/bauleras que paga junto con él]}, en el orden de ordenar_con_asociadas."""
    hijas = {}
    for u, nivel in ordenar_con_asociadas(unidades):
        if nivel == 1 and paga_junto(u):
            hijas.setdefault(u["depto_id"], []).append(u)
    return hijas


def ordenar_con_asociadas(unidades):
    """
    Devuelve [(unidad, nivel)] en orden: por piso y unidad, con cada depto
    seguido de sus cocheras y bauleras (nivel 1). Las cocheras/bauleras sin
    depto van con el resto (nivel 0).
    """
    por_id = indice_por_id(unidades)
    hijas, principales = {}, []
    for u in unidades:
        depto = depto_de(u, por_id)
        if depto is not None:
            hijas.setdefault(depto["id"], []).append(u)
        else:
            principales.append(u)

    resultado = []
    for u in sorted(principales, key=_clave_principal):
        resultado.append((u, 0))
        for h in sorted(hijas.get(u["id"], []), key=_clave_asociada):
            resultado.append((h, 1))
    return resultado
