# -*- coding: utf-8 -*-
"""
utils.py
--------
Funciones auxiliares reutilizadas en todo el proyecto:
- Sanitización de nombres de archivo para Windows.
- Parseo robusto de importes en formato argentino.
- Formato de moneda argentina.
- Cálculo de meses (actual / anterior) en español.
"""

import os
import re
from datetime import date

import config

CARACTERES_INVALIDOS = r'[\\/:*?"<>|]'


def sanitize_filename(nombre):
    """
    Elimina caracteres inválidos para nombres de archivo/carpeta en Windows
    y reemplaza espacios por guiones bajos. Conserva acentos (válidos en NTFS).
    """
    if nombre is None:
        nombre = ""
    nombre = str(nombre).strip()
    nombre = re.sub(CARACTERES_INVALIDOS, "", nombre)
    nombre = nombre.replace(" ", "_")
    nombre = re.sub(r"_+", "_", nombre)
    nombre = nombre.strip("_.")
    return nombre or "SIN_NOMBRE"


def parse_importe(valor):
    """
    Convierte un importe expresado en distintos formatos comunes en Argentina
    a un float. Admite:
        45000
        45000.5
        45000,50
        45.000,50
        $45.000
        $ 45.000,50
    Ante un valor imposible de interpretar, devuelve 0.0 en lugar de lanzar
    una excepción (para no romper la carga de datos).
    """
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)

    s = str(valor).strip()
    if not s:
        return 0.0

    s = s.replace("$", "").replace(" ", "")
    if not s:
        return 0.0

    tiene_punto = "." in s
    tiene_coma = "," in s

    try:
        if tiene_punto and tiene_coma:
            # Formato argentino: punto = miles, coma = decimales
            s = s.replace(".", "").replace(",", ".")
        elif tiene_coma:
            # Solo coma -> es el separador decimal
            s = s.replace(",", ".")
        elif tiene_punto:
            # Solo punto: puede ser separador de miles (45.000) o decimal (45.5)
            partes = s.split(".")
            ultima = partes[-1]
            if len(partes) > 1 and len(ultima) == 3 and all(p.isdigit() for p in partes):
                # Parece separador de miles -> lo quitamos
                s = s.replace(".", "")
            # si no, lo dejamos como separador decimal normal (45.5 -> 45.5)
        return float(s)
    except ValueError:
        return 0.0


def format_currency_ar(valor):
    """
    Formatea un número como moneda argentina: $ 45.000,00
    """
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        valor = 0.0

    negativo = valor < 0
    valor = abs(valor)

    entero = int(valor)
    decimales = int(round((valor - entero) * 100))
    if decimales == 100:
        entero += 1
        decimales = 0

    entero_str = f"{entero:,}".replace(",", ".")
    signo = "-" if negativo else ""
    return f"{signo}$ {entero_str},{decimales:02d}"


def mes_actual_es():
    hoy = date.today()
    return f"{config.MESES_ES[hoy.month - 1]} {hoy.year}"


def mes_anterior_es():
    hoy = date.today()
    mes = hoy.month - 1
    anio = hoy.year
    if mes == 0:
        mes = 12
        anio -= 1
    return f"{config.MESES_ES[mes - 1]} {anio}"


def fecha_hoy_es():
    hoy = date.today()
    return hoy.strftime("%d/%m/%Y")


def primera_palabra(texto):
    """Devuelve la primera palabra de un string (útil para extraer 'SEPTIEMBRE' de 'SEPTIEMBRE 2026')."""
    texto = (texto or "").strip()
    return texto.split(" ")[0] if texto else "PERIODO"


def nombre_archivo_recibo(edificio, piso, unidad, periodo, numero_recibo, carpeta_destino):
    """
    Genera el nombre de archivo del recibo y resuelve conflictos de nombre.
    Si el archivo "natural" ya existe, se le agrega el número de recibo
    como sufijo para no sobrescribir ni perder el archivo anterior.
    Devuelve la ruta completa del archivo.
    """
    base = "recibo_expensas_{}_{}_{}_{}".format(
        sanitize_filename(edificio),
        sanitize_filename(piso),
        sanitize_filename(unidad),
        sanitize_filename(primera_palabra(periodo)),
    )
    nombre = base + ".pdf"
    ruta = os.path.join(carpeta_destino, nombre)

    if os.path.exists(ruta):
        nombre = f"{base}_{int(numero_recibo):05d}.pdf"
        ruta = os.path.join(carpeta_destino, nombre)

    return ruta, nombre


def abrir_carpeta_en_explorador(ruta):
    """Abre una carpeta en el explorador de Windows. No falla si no es Windows."""
    try:
        os.makedirs(ruta, exist_ok=True)
        os.startfile(ruta)  # disponible solo en Windows
        return True
    except AttributeError:
        return False
    except Exception:
        return False
