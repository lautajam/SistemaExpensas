# -*- coding: utf-8 -*-
"""
logging_config.py
------------------
Configuración centralizada de logging. Se inicializa una única vez al
arrancar la aplicación (ver main.py); cada módulo obtiene su logger con
logging.getLogger(__name__).

Registra en datos/logs/app.log, con rotación de tamaño.
"""

import logging
import logging.handlers
import os

import config

LOG_DIR = os.path.join(config.DATOS_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")


def configurar_logging():
    os.makedirs(LOG_DIR, exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"))

    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.addHandler(handler)
