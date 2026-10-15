# -*- coding: utf-8 -*-
"""
main.py
-------
Punto de entrada de Sistema de Expensas.

Se encarga de:
    1. Asegurar que exista toda la estructura de datos necesaria.
    2. Lanzar la interfaz gráfica.
    3. Capturar cualquier error fatal para mostrarlo de forma comprensible
       en vez de dejar que la aplicación se cierre con un traceback crudo.
"""

import logging
import sys

# pdf_generator (xhtml2pdf -> pyhanko -> certifi) se importa ANTES que PySide6 a propósito:
# PySide6 instala un import hook (shibokensupport) para su sistema de "features" que
# intercepta todos los imports posteriores, y choca con esa cadena de módulos (se cuelga
# en certifi/core.py). Importándola primero, ya queda cacheada en sys.modules y el resto
# del código (ui.py incluido) la usa sin volver a disparar esa cadena de imports.
import pdf_generator  # noqa: F401

from PySide6.QtWidgets import QApplication, QMessageBox

import database
from logging_config import configurar_logging
from ui import App

logger = logging.getLogger(__name__)


def main():
    configurar_logging()
    app = QApplication(sys.argv)
    sys.excepthook = _loguear_error_no_manejado

    try:
        database.ensure_data_files()
    except Exception as e:
        logger.exception("No se pudo inicializar la carpeta de datos")
        _mostrar_error_fatal(
            "No se pudo inicializar la carpeta de datos.\n\n"
            f"Detalle: {e}"
        )
        sys.exit(1)

    try:
        ventana = App()
        ventana.show()
    except Exception as e:
        logger.exception("Error inesperado, la aplicación debe cerrarse")
        _mostrar_error_fatal(f"La aplicación encontró un error inesperado y debe cerrarse.\n\nDetalle: {e}")
        sys.exit(1)

    sys.exit(app.exec())


def _loguear_error_no_manejado(exc_type, exc, tb):
    """Qt no interrumpe la app si un callback (botón, evento, etc.) tira una excepción sin
    capturarla; por default solo se imprime a stderr y en el .exe eso se pierde."""
    logger.error("Error no manejado en un callback de la interfaz", exc_info=(exc_type, exc, tb))


def _mostrar_error_fatal(mensaje):
    try:
        QMessageBox.critical(None, "Sistema de Expensas - Error", mensaje)
    except Exception:
        # Si ni siquiera se puede mostrar una ventana, se imprime en consola.
        print(mensaje)


if __name__ == "__main__":
    main()
