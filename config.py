# -*- coding: utf-8 -*-
"""
config.py
---------
Define todas las rutas de la aplicación de forma RELATIVA a la ubicación
del ejecutable (o del script, si se corre con Python directamente).

Esto es clave para que, al compilar con PyInstaller, los datos NO queden
guardados dentro de la carpeta temporal (_MEIPASS) sino al lado del .exe.
"""

import os
import sys


def get_base_path():
    """
    Devuelve la carpeta donde vive el ejecutable (modo compilado)
    o la carpeta del proyecto (modo desarrollo con Python).
    """
    if getattr(sys, "frozen", False):
        # Ejecutándose como .exe compilado con PyInstaller
        return os.path.dirname(sys.executable)
    else:
        # Ejecutándose como script .py normal
        return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_base_path()

# Carpetas principales
DATOS_DIR = os.path.join(BASE_DIR, "datos")
CONFIG_DIR = os.path.join(BASE_DIR, "configuracion")
EDIFICIOS_DIR = os.path.join(BASE_DIR, "edificios")
PLANTILLA_DIR = os.path.join(BASE_DIR, "plantilla")

# Archivos CSV de datos
EDIFICIOS_CSV = os.path.join(DATOS_DIR, "edificios.csv")
UNIDADES_CSV = os.path.join(DATOS_DIR, "unidades.csv")
NUMERACION_CSV = os.path.join(DATOS_DIR, "numeracion.csv")
HISTORIAL_CSV = os.path.join(DATOS_DIR, "historial.csv")
PAGOS_DIR = os.path.join(DATOS_DIR, "pagos_edificios")
EDIFICIOS_BORRADOS_DIR = os.path.join(DATOS_DIR, "edificios_borrados")

# Configuración de la inmobiliaria
INMOBILIARIA_CSV = os.path.join(CONFIG_DIR, "inmobiliaria.csv")
PREFERENCIAS_CSV = os.path.join(CONFIG_DIR, "preferencias.csv")

# Contraseña maestra (hasheada) que protege las pantallas de administración
MAESTRO_CSV = os.path.join(CONFIG_DIR, "maestro.csv")

# Envío de recibos por mail (ver correo.py)
EMAILS_UNIDADES_CSV = os.path.join(DATOS_DIR, "emails_unidades.csv")
SMTP_CSV = os.path.join(CONFIG_DIR, "smtp.csv")
MAILS_ENVIADOS_CSV = os.path.join(DATOS_DIR, "mails_enviados.csv")

# Imágenes de la inmobiliaria (se guardan siempre como PNG en configuracion/)
IMAGENES_INMOBILIARIA = {
    "logo": os.path.join(CONFIG_DIR, "logo.png"),
    "firma": os.path.join(CONFIG_DIR, "firma.png"),
}

# Plantilla del recibo (HTML + CSS editables por el usuario)
RECIBO_HTML = os.path.join(PLANTILLA_DIR, "recibo.html")
RECIBO_CSS = os.path.join(PLANTILLA_DIR, "estilo.css")

# Meses en español (índice 0 = enero)
MESES_ES = [
    "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"
]

APP_TITULO = "Sistema de Expensas - Administración de Consorcios"
APP_VERSION = "1.0"
