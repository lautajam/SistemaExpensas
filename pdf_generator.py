# -*- coding: utf-8 -*-
"""
pdf_generator.py
----------------
Genera los PDF de los recibos a partir de las plantillas editables ubicadas en:

    plantilla/recibo_depto.html
    plantilla/recibo_local.html
    plantilla/recibo_cochera.html
    plantilla/recibo_baulera.html
    plantilla/estilo.css   (compartido por las cuatro)

El motor de renderizado es xhtml2pdf (paquete "xhtml2pdf", módulo "pisa"),
elegido por ser 100% Python puro: no necesita instalar wkhtmltopdf ni
librerías del sistema operativo, y empaqueta sin problemas con PyInstaller.

Para modificar el diseño del recibo, basta con editar esos dos archivos
(recibo_*.html / estilo.css) con cualquier editor de texto: NO hace falta
tocar este archivo ni recompilar el .exe. Ver el placeholder "{{CLAVE}}"
dentro del HTML: cada uno se reemplaza por el valor correspondiente del
diccionario "datos" al generar el PDF.
"""

import os

from xhtml2pdf import pisa

import config
from unidades import normalizar_tipo


def _link_callback(uri, rel):
    """
    Resuelve rutas relativas (como href="estilo.css") a rutas absolutas
    en disco, para que xhtml2pdf pueda encontrar el archivo sin importar
    desde qué carpeta se ejecute el programa.
    """
    if uri.startswith("file://"):
        candidato = uri[len("file://"):]
    elif os.path.isabs(uri):
        candidato = uri
    else:
        candidato = os.path.join(config.PLANTILLA_DIR, uri)

    if os.path.isfile(candidato):
        return candidato
    return uri


def _cargar_plantilla_html(tipo):
    ruta = config.RECIBOS_HTML[normalizar_tipo(tipo)]
    if not os.path.exists(ruta):
        raise FileNotFoundError(
            f"No se encontró la plantilla del recibo en:\n{ruta}\n\n"
            "Verificá que la carpeta 'plantilla' esté al lado del ejecutable."
        )
    with open(ruta, "r", encoding="utf-8") as f:
        return f.read()


def generar_pdf_recibo(datos, ruta_salida, tipo="DEPTO"):
    """
    Genera un PDF a partir de la plantilla del tipo de unidad (recibo_depto,
    recibo_local, recibo_cochera o recibo_baulera), reemplazando cada
    "{{CLAVE}}" del HTML por el valor correspondiente en el diccionario "datos".

    datos: dict con, como mínimo, las claves usadas en las plantillas:
        NUMERO_RECIBO, FECHA_EMISION, EDIFICIO_NOMBRE,
        EXPENSAS_DE, GASTOS_DE, PISO, UNIDAD, TIPO,
        INQUILINO, IMPORTE,
        INMOBILIARIA_NOMBRE, INMOBILIARIA_SUBTITULO, INMOBILIARIA_DIRECCION,
        INMOBILIARIA_TELEFONO, INMOBILIARIA_EMAIL
    Opcionales: DEPTO (etiqueta del depto al que pertenece una cochera/baulera),
    UF (unidad funcional), DUENO y los datos del consorcio: EDIFICIO_DIRECCION,
    EDIFICIO_LOCALIDAD, EDIFICIO_CUIT, ADMIN_NOMBRE, ADMIN_CUIT y ADMIN_RPAC.

    ruta_salida: ruta completa (incluyendo nombre de archivo .pdf) donde
    se va a guardar el PDF generado.
    """
    html = _cargar_plantilla_html(tipo)

    for clave, valor in datos.items():
        html = html.replace("{{" + clave + "}}", "" if valor is None else str(valor))

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
