# -*- coding: utf-8 -*-
"""
pdf_generator.py
----------------
Genera los PDF de los recibos a partir de la plantilla editable ubicada en:

    plantilla/recibo.html   (única plantilla, para todos los tipos de unidad)
    plantilla/estilo.css
    plantilla/fonts/        (tipografía Open Sans)

El motor de renderizado es xhtml2pdf (paquete "xhtml2pdf", módulo "pisa"),
elegido por ser 100% Python puro: no necesita instalar wkhtmltopdf ni
librerías del sistema operativo, y empaqueta sin problemas con PyInstaller.

Para modificar el diseño del recibo, basta con editar esos archivos con
cualquier editor de texto: NO hace falta tocar este archivo ni recompilar el
.exe. Cada "{{CLAVE}}" del HTML se reemplaza por el valor correspondiente del
diccionario "datos" (ver recibo.py, que arma ese diccionario).
"""

import html as html_lib
import os

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xhtml2pdf import default, pisa

import config


def _link_callback(uri, rel):
    """
    Resuelve rutas relativas (como href="estilo.css") a rutas absolutas
    en disco, para que xhtml2pdf pueda encontrar el archivo sin importar
    desde qué carpeta se ejecute el programa.
    """
    if uri.startswith("file://"):
        candidato = uri[len("file://"):]
        if len(candidato) > 2 and candidato[0] == "/" and candidato[2] == ":":   # file:///C:/...
            candidato = candidato[1:]
    elif os.path.isabs(uri):
        candidato = uri
    else:
        candidato = os.path.join(config.PLANTILLA_DIR, uri)

    if os.path.isfile(candidato):
        return candidato
    return uri


# Marcadores que ya traen HTML (el resto de los datos se escapa antes de insertarse)
CLAVES_HTML = {"LOGO", "FIRMA", "BLOQUE_CUIT"}

_FUENTES_REGISTRADAS = False


def _registrar_fuentes():
    """
    Registra Open Sans (plantilla/fonts) en ReportLab, que es quien dibuja el PDF. Se hace acá
    y no con @font-face porque xhtml2pdf falla al cargar fuentes por CSS en Windows. Si los
    archivos no están, el recibo se genera igual con la tipografía por defecto.
    """
    global _FUENTES_REGISTRADAS
    if _FUENTES_REGISTRADAS:
        return
    carpeta = os.path.join(config.PLANTILLA_DIR, "fonts")
    normal, negrita = (os.path.join(carpeta, f) for f in ("OpenSans-Regular.ttf", "OpenSans-Bold.ttf"))
    if os.path.isfile(normal) and os.path.isfile(negrita):
        # xhtml2pdf busca las fuentes por su nombre en minúsculas
        pdfmetrics.registerFont(TTFont("opensans", normal))
        pdfmetrics.registerFont(TTFont("opensansbold", negrita))
        pdfmetrics.registerFontFamily("opensans", normal="opensans", bold="opensansbold",
                                      italic="opensans", boldItalic="opensansbold")
        # ...y solo reconoce las que figuran en su tabla de fuentes por defecto
        default.DEFAULT_FONT.update({"opensans": "opensans", "opensansbold": "opensansbold"})
    _FUENTES_REGISTRADAS = True


def _cargar_plantilla_html():
    ruta = config.RECIBO_HTML
    if not os.path.exists(ruta):
        raise FileNotFoundError(
            f"No se encontró la plantilla del recibo en:\n{ruta}\n\n"
            "Verificá que la carpeta 'plantilla' esté al lado del ejecutable."
        )
    with open(ruta, "r", encoding="utf-8") as f:
        return f.read()


def imagen_html(ruta, ancho_max_pt, alto_max_pt):
    """
    Etiqueta <img> con la imagen ajustada (sin deformarla) a la caja indicada, en puntos.
    Devuelve "" si la imagen no existe o no se puede leer: el lugar queda en blanco.
    """
    if not ruta or not os.path.isfile(ruta):
        return ""
    try:
        from PIL import Image
        with Image.open(ruta) as img:
            ancho, alto = img.size
    except Exception:
        return ""
    escala = min(ancho_max_pt / ancho, alto_max_pt / alto)
    return f'<img src="{ruta.replace(chr(92), "/")}" width="{ancho * escala:.0f}pt" height="{alto * escala:.0f}pt" />'


def generar_pdf_recibo(datos, ruta_salida):
    """
    Genera un PDF a partir de plantilla/recibo.html, reemplazando cada "{{CLAVE}}" por el
    valor correspondiente en el diccionario "datos" (ver recibo.armar_datos). Además de esos
    datos, la plantilla dispone de {{LOGO}} y {{FIRMA}}: las imágenes cargadas en
    Configuración de la inmobiliaria (vacías si no hay imagen).

    ruta_salida: ruta completa (incluyendo nombre de archivo .pdf) donde
    se va a guardar el PDF generado.
    """
    _registrar_fuentes()
    html = _cargar_plantilla_html()

    datos = dict(datos)
    datos.setdefault("LOGO", imagen_html(config.IMAGENES_INMOBILIARIA["logo"], 185, 60))
    datos.setdefault("FIRMA", imagen_html(config.IMAGENES_INMOBILIARIA["firma"], 190, 62))

    for clave, valor in datos.items():
        texto = "" if valor is None else str(valor)
        if clave not in CLAVES_HTML:          # los datos de texto se escapan (ej. "Pérez & Hijos")
            texto = html_lib.escape(texto, quote=False)
        html = html.replace("{{" + clave + "}}", texto)

    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)

    with open(ruta_salida, "wb") as archivo_pdf:
        resultado = pisa.CreatePDF(
            src=html,
            dest=archivo_pdf,
            link_callback=_link_callback,
            encoding="utf-8",
        )

    if resultado.err:
        raise RuntimeError(f"xhtml2pdf reportó errores generando: {ruta_salida}")

    return ruta_salida
