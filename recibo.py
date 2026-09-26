# -*- coding: utf-8 -*-
"""
recibo.py
---------
Arma los datos que lleva cada recibo (los valores de los marcadores {{CLAVE}} de
plantilla/recibo.html). Son funciones puras: no leen ni escriben archivos, salvo
la tipografía que se usa para medir textos.

Qué va en cada lugar del recibo (lo que varía en cada recibo sale de un marcador; el resto es texto fijo):

    Encabezado izquierdo   Consorcio de Propietarios sitio en la calle {EDIFICIO_UBICACION}
                           C.U.I.T.: {EDIFICIO_CUIT}.-  (si el edificio no tiene CUIT, esa línea se
                           quita y el texto del consorcio se agranda y queda centrado)
    Encabezado derecho     {LOGO} / {INMOBILIARIA_NOMBRE} / {INMOBILIARIA_SUBTITULO}
    Títulos                EXPENSAS: {EXPENSAS_DE}      RECIBO DE EXPENSAS N° {NUMERO_RECIBO}
                           GASTO DE: {GASTOS_DE}        FECHA: {FECHA_EMISION}
    Tabla                  Depto-Coch-Local {UNIDADES} | Unidad Funcional {UF} (solo la del depto) | Propietario {PROPIETARIO}
    Recibí de              {RECIBI_DE}.-
    Frase                  {FRASE_PAGO}
    Importe                Importe abonado: ${IMPORTE}.-      (Pesos {IMPORTE_LETRAS})
    Firma                  {FIRMA} sobre la línea «Firma»
    Pie                    {ADMIN_NOMBRE} | C.U.I.T.: {ADMIN_CUIT} | RPAC: {ADMIN_RPAC}
                           Tel: {INMOBILIARIA_TELEFONO} | Email: {INMOBILIARIA_EMAIL}
"""

import html
import os
import re
import unicodedata

import config
from unidades import BAULERA, COCHERA, etiqueta_unidad, normalizar_tipo

# ---------------------------------------------------------------------------
# Períodos y fechas
# ---------------------------------------------------------------------------

MESES_ABREVIADOS = ["ENE.", "FEB.", "MAR.", "ABR.", "MAY.", "JUN.", "JUL.", "AGO.", "SEPT.", "OCT.", "NOV.", "DIC."]


def abreviar_periodo(texto):
    """'SEPTIEMBRE 2026' -> 'SEPT. 26'. Lo que no es un mes y año (ej. 'A CTA.') queda igual."""
    m = re.fullmatch(r"\s*([A-Za-zÁÉÍÓÚáéíóú]+)\s+(\d{4})\s*", str(texto or ""))
    if m and m.group(1).upper() in config.MESES_ES:
        return f"{MESES_ABREVIADOS[config.MESES_ES.index(m.group(1).upper())]} {m.group(2)[2:]}"
    return str(texto or "")


def fecha_corta(fecha):
    """24/09/26"""
    return fecha.strftime("%d/%m/%y")


# ---------------------------------------------------------------------------
# Importe
# ---------------------------------------------------------------------------

def _centavos(valor):
    try:
        return int(round(abs(float(valor)) * 100))
    except (TypeError, ValueError):
        return 0


def formato_importe(valor):
    """67000 -> '67.000'; 67000.5 -> '67.000,50' (sin el signo $: la plantilla lo agrega)."""
    total = _centavos(valor)
    entero, cent = divmod(total, 100)
    texto = f"{entero:,}".replace(",", ".")
    return f"{texto},{cent:02d}" if cent else texto


_UNIDADES = ["", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE", "DIEZ", "ONCE", "DOCE",
             "TRECE", "CATORCE", "QUINCE", "DIECISÉIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE", "VEINTE",
             "VEINTIÚN", "VEINTIDÓS", "VEINTITRÉS", "VEINTICUATRO", "VEINTICINCO", "VEINTISÉIS", "VEINTISIETE",
             "VEINTIOCHO", "VEINTINUEVE"]
_DECENAS = ["", "", "", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
_CENTENAS = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS",
             "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]


def _menor_de_mil(n):
    """1..999 en letras (con 'UN' delante de mil/millón, que es como se apocopa)."""
    if n == 100:
        return "CIEN"
    partes = [_CENTENAS[n // 100]]
    resto = n % 100
    if resto < 30:
        partes.append(_UNIDADES[resto])
    else:
        d, u = divmod(resto, 10)
        partes.append(_DECENAS[d] + (f" Y {_UNIDADES[u]}" if u else ""))
    return " ".join(p for p in partes if p)


def numero_a_letras(n, _apocopar=False):
    """
    Entero (0 a 999.999.999.999) en letras mayúsculas: 67000 -> 'SESENTA Y SIETE MIL',
    21 -> 'VEINTIUNO', 21000 -> 'VEINTIÚN MIL'.
    """
    n = int(n)
    if n == 0:
        return "CERO"
    if n < 0 or n >= 10 ** 12:
        raise ValueError("Importe fuera de rango")
    millones, resto = divmod(n, 10 ** 6)
    miles, unidades = divmod(resto, 1000)
    partes = []
    if millones:
        partes.append("UN MILLÓN" if millones == 1 else numero_a_letras(millones, True) + " MILLONES")
    if miles:
        partes.append("MIL" if miles == 1 else _menor_de_mil(miles) + " MIL")
    if unidades:
        partes.append(_menor_de_mil(unidades))
    texto = " ".join(partes)
    if unidades and not _apocopar:      # al final va 'UNO' / 'VEINTIUNO', no 'UN' / 'VEINTIÚN'
        texto = re.sub(r"VEINTIÚN$", "VEINTIUNO", re.sub(r"\bUN$", "UNO", texto))
    return texto


def importe_en_letras(valor):
    """67000 -> 'SESENTA Y SIETE MIL'; 67000.5 -> 'SESENTA Y SIETE MIL CON 50/100'."""
    entero, cent = divmod(_centavos(valor), 100)
    texto = numero_a_letras(entero)
    return f"{texto} CON {cent:02d}/100" if cent else texto


# ---------------------------------------------------------------------------
# Unidades
# ---------------------------------------------------------------------------

def _parte_unidad(u):
    """Cómo se nombra una unidad dentro del recuadro: '1ero A', 'Coch. 67', 'Baul 12', 'Local PB 1'."""
    tipo = normalizar_tipo(u.get("tipo"))
    piso = (u.get("piso") or "").strip()
    numero = (u.get("unidad") or "").strip()
    if tipo == COCHERA:
        return " ".join(p for p in ("Coch.", piso, numero) if p)
    if tipo == BAULERA:
        return " ".join(p for p in ("Baul", piso, numero) if p)
    return etiqueta_unidad(u)


def texto_unidades(u, agrupadas=()):
    """'1ero A | Coch. 67 | Baul 12': la unidad y, si van en el mismo recibo, sus cocheras y bauleras."""
    return " | ".join(_parte_unidad(x) for x in [u, *agrupadas])


def texto_uf(u, agrupadas=()):
    """Unidad funcional de la unidad del recibo (la del depto; las cocheras y bauleras que van con él no se muestran)."""
    return (u.get("uf") or "").strip()


# ---------------------------------------------------------------------------
# Frase de pago según el estado
# ---------------------------------------------------------------------------

# Estado de la planilla (en minúsculas) -> frase que va sobre el importe.
FRASE_PAGO_POR_ESTADO = {
    "total": "El pago total de las expensas indicadas para el mes correspondiente:",
    "a cta": "El pago a cuenta de las expensas indicadas para el mes correspondiente:",
    "parcial": "El pago a cuenta de las expensas indicadas para el mes correspondiente:",
    "deuda": "El pago de la deuda de expensas de meses anteriores:",
    "no pagado": "Expensas indicadas para el mes correspondiente, pendientes de pago:",
}


def _norm(texto):
    t = unicodedata.normalize("NFKD", str(texto or ""))
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in t if not unicodedata.combining(c)).lower()).strip()


def frase_pago(estado):
    """Frase según el estado de pago; sin estado (unidad que no figura en la planilla) es la del pago total."""
    return FRASE_PAGO_POR_ESTADO.get(_norm(estado), FRASE_PAGO_POR_ESTADO["total"])


# ---------------------------------------------------------------------------
# Ajuste del tamaño de letra al ancho disponible
# ---------------------------------------------------------------------------

def _ruta_fuente(negrita):
    return os.path.join(config.PLANTILLA_DIR, "fonts", "OpenSans-Bold.ttf" if negrita else "OpenSans-Regular.ttf")


def ancho_texto(texto, tam_pt, negrita=True):
    """Ancho en puntos del texto con la tipografía del recibo (Open Sans); si no está, una estimación."""
    try:
        from PIL import ImageFont
        fuente = ImageFont.truetype(_ruta_fuente(negrita), 100)
        return fuente.getlength(texto) * tam_pt / 100
    except Exception:
        return len(texto) * tam_pt * 0.6


def _lineas(texto, ancho_pt, tam_pt, negrita):
    """Cantidad de renglones que ocupa el texto (corte por palabras) en ancho_pt."""
    n, actual = 0, ""
    for palabra in str(texto).split():
        prueba = f"{actual} {palabra}".strip()
        if actual and ancho_texto(prueba, tam_pt, negrita) > ancho_pt:
            n, actual = n + 1, palabra
        else:
            actual = prueba
    return n + (1 if actual else 0)


def ajustar_bloque(primera, resto, ancho_pt, max_pt, max_lineas, min_pt=8, negrita=True):
    """
    Tamaño de letra (pt) más grande, hasta max_pt, con el que un texto de varios renglones entra en
    max_lineas: 'primera' es un renglón fijo (corte forzado) y 'resto' se corta por palabras.
    """
    tam = float(max_pt)
    while tam > min_pt:
        if ancho_texto(primera, tam, negrita) <= ancho_pt and 1 + _lineas(resto, ancho_pt, tam, negrita) <= max_lineas:
            break
        tam -= 0.5
    return round(max(tam, min_pt), 1)


def ajustar_fuente(texto, ancho_pt, max_pt, min_pt=8, negrita=True):
    """Tamaño de letra (pt, con un decimal) más grande, hasta max_pt, con el que el texto entra en ancho_pt."""
    texto = str(texto or "")
    if not texto:
        return max_pt
    ancho = ancho_texto(texto, max_pt, negrita)
    tam = max_pt if ancho <= ancho_pt else max_pt * ancho_pt / ancho
    return round(max(min_pt, min(max_pt, tam)) - 0.05, 1) if tam < max_pt else max_pt


# ---------------------------------------------------------------------------
# Datos completos del recibo
# ---------------------------------------------------------------------------

# Ancho útil (pt) de cada lugar de la plantilla y tamaño máximo de letra (los que aparecen en recibo.html)
_ANCHO_CELDA, _MAX_CELDA = 164, 22
_ANCHO_RECIBI, _MAX_RECIBI = 318, 29.7
_ANCHO_LETRAS, _MAX_LETRAS = 528, 17.8
_ANCHO_IMPORTE, _MAX_IMPORTE = 528, 32.5
_ANCHO_CONSORCIO = 230          # renglón del texto del consorcio (encabezado izquierdo)
_ANCHO_INMOBILIARIA = 212       # nombre y subtítulo de la inmobiliaria (encabezado derecho)
_PRIMERA_LINEA_CONSORCIO = "Consorcio de Propietarios sitio"
_ANCHO_TITULO, _MAX_TITULO = 236, 22.3         # "EXPENSAS: ..." y "GASTO DE: ..." (columna izquierda de los títulos)


def armar_datos(*, numero, fecha, edificio, datos_edificio, unidad, agrupadas, expensas_de, gastos_de, estado,
                importe, inmobiliaria):
    """
    Devuelve el diccionario de marcadores del recibo.
    numero: N° de recibo; fecha: date; edificio: nombre; datos_edificio: fila de edificios.csv;
    unidad / agrupadas: la unidad del recibo y las cocheras/bauleras que van en el mismo;
    expensas_de / gastos_de: períodos tal como los devuelve obtener_periodos() (o A CTA., DEUDA...);
    estado: estado de pago de la planilla (Total, A cta., Deuda, No pagado o None);
    importe: total del recibo (suma del grupo); inmobiliaria: fila de inmobiliaria.csv.
    """
    unidades_txt = texto_unidades(unidad, agrupadas)
    uf_txt = texto_uf(unidad, agrupadas)
    dueno = (unidad.get("dueno") or "").strip()
    inquilino = (unidad.get("inquilino") or "").strip()
    recibi_de = inquilino or dueno          # sin inquilino cargado, paga el propietario
    letras = importe_en_letras(importe)
    ubicacion = ", ".join(p for p in (datos_edificio.get("direccion", ""), datos_edificio.get("localidad", "")) if p)
    cuit = (datos_edificio.get("cuit") or "").strip()
    # Con CUIT: texto del consorcio + línea del CUIT. Sin CUIT: sin esa línea y el texto más grande.
    tam_consorcio = ajustar_bloque(_PRIMERA_LINEA_CONSORCIO, f"en la calle {ubicacion}.-", _ANCHO_CONSORCIO,
                                   12.5 if cuit else 17, 3 if cuit else 4)
    bloque_cuit = (f'<p class="cuit">C.U.I.T.: <span class="dato">{html.escape(cuit)}</span>.-</p>' if cuit else "")
    nombre_inmo = (inmobiliaria.get("nombre") or "").strip()
    subtitulo_inmo = (inmobiliaria.get("subtitulo") or "").strip()

    return {
        "NUMERO_RECIBO": f"{int(numero):03d}",
        "FECHA_EMISION": fecha_corta(fecha),
        "EXPENSAS_DE": abreviar_periodo(expensas_de),
        "GASTOS_DE": abreviar_periodo(gastos_de),
        "TAM_EXPENSAS": ajustar_fuente(f"EXPENSAS: {abreviar_periodo(expensas_de)}", _ANCHO_TITULO, _MAX_TITULO),
        "TAM_GASTOS": ajustar_fuente(f"GASTO DE: {abreviar_periodo(gastos_de)}", _ANCHO_TITULO, _MAX_TITULO),
        "EDIFICIO_NOMBRE": edificio,
        "EDIFICIO_DIRECCION": datos_edificio.get("direccion", ""),
        "EDIFICIO_LOCALIDAD": datos_edificio.get("localidad", ""),
        "EDIFICIO_UBICACION": ubicacion,
        "EDIFICIO_CUIT": cuit,
        "BLOQUE_CUIT": bloque_cuit,
        "TAM_CONSORCIO": tam_consorcio,
        "INTERLINEADO_CONSORCIO": round(tam_consorcio * 1.36, 1),
        "TAM_INMOBILIARIA": ajustar_fuente(nombre_inmo, _ANCHO_INMOBILIARIA, 12.5, negrita=False),
        "TAM_SUBTITULO": ajustar_fuente(subtitulo_inmo, _ANCHO_INMOBILIARIA, 11.5, negrita=False),
        "ADMIN_NOMBRE": datos_edificio.get("admin_nombre", ""),
        "ADMIN_CUIT": datos_edificio.get("admin_cuit", ""),
        "ADMIN_RPAC": datos_edificio.get("admin_rpac", ""),
        "UNIDADES": unidades_txt,
        "TAM_UNIDADES": ajustar_fuente(unidades_txt, _ANCHO_CELDA, _MAX_CELDA),
        "UF": uf_txt,
        "TAM_UF": ajustar_fuente(uf_txt, _ANCHO_CELDA, _MAX_CELDA),
        "PROPIETARIO": dueno,
        "TAM_PROPIETARIO": ajustar_fuente(dueno, _ANCHO_CELDA, _MAX_CELDA),
        "RECIBI_DE": recibi_de,
        "TAM_RECIBI_DE": ajustar_fuente(recibi_de, _ANCHO_RECIBI, _MAX_RECIBI),
        "FRASE_PAGO": frase_pago(estado),
        "IMPORTE": formato_importe(importe),
        "TAM_IMPORTE": ajustar_fuente(f"Importe abonado: ${formato_importe(importe)}.-", _ANCHO_IMPORTE, _MAX_IMPORTE),
        "IMPORTE_LETRAS": letras,
        "TAM_IMPORTE_LETRAS": ajustar_fuente(f"(Pesos {letras})", _ANCHO_LETRAS, _MAX_LETRAS),
        "INMOBILIARIA_NOMBRE": inmobiliaria.get("nombre", ""),
        "INMOBILIARIA_SUBTITULO": inmobiliaria.get("subtitulo", ""),
        "INMOBILIARIA_DIRECCION": inmobiliaria.get("direccion", ""),
        "INMOBILIARIA_TELEFONO": inmobiliaria.get("telefono", ""),
        "INMOBILIARIA_EMAIL": inmobiliaria.get("email", ""),
        # Datos sueltos de la unidad, por si una plantilla los necesita
        "TIPO": normalizar_tipo(unidad.get("tipo")),
        "PISO": unidad.get("piso", ""),
        "UNIDAD": unidad.get("unidad", ""),
        "INQUILINO": inquilino,
        "DUENO": dueno,
    }
