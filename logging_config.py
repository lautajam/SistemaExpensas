# -*- coding: utf-8 -*-
"""
logging_config.py
------------------
Logging centralizado de la app. Se inicializa una sola vez al arrancar
(ver main.py) y después cada módulo pide su logger con:

    import logging
    logger = logging.getLogger(__name__)

Guarda en datos/logs/app.log, con rotación para que no crezca sin límite.
Es clave sobre todo para el .exe compilado: ahí no hay consola visible,
así que sin esto un error se pierde sin dejar rastro.
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
