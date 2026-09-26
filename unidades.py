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
