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
import tkinter as tk
from tkinter import messagebox

import database
from logging_config import configurar_logging
from ui import App

logger = logging.getLogger(__name__)


def main():
    configurar_logging()

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
        app = App()
        app.report_callback_exception = _loguear_error_callback
        app.mainloop()
    except Exception as e:
        logger.exception("Error inesperado, la aplicación debe cerrarse")
        _mostrar_error_fatal(f"La aplicación encontró un error inesperado y debe cerrarse.\n\nDetalle: {e}")
        sys.exit(1)


def _loguear_error_callback(exc, val, tb):
    """Tkinter llama a esto cuando un callback (botón, evento, etc.) tira una excepción
    sin capturarla; por default solo se imprime a stderr y en el .exe eso se pierde."""
    logger.error("Error no manejado en un callback de la interfaz", exc_info=(exc, val, tb))


def _mostrar_error_fatal(mensaje):
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Sistema de Expensas - Error", mensaje)
        root.destroy()
    except Exception:
        # Si ni siquiera se puede mostrar una ventana, se imprime en consola.
        print(mensaje)

if __name__ == "__main__":
    main()
