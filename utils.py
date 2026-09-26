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
import subprocess
import webbrowser
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


def normalizar_cuit(texto):
    """
    '30123456789' o '30-12345678-9' -> '30-12345678-9'. Vacío -> ''.
    Lanza ValueError si no tiene 11 dígitos.
    """
    digitos = re.sub(r"\D", "", str(texto or ""))
    if not digitos:
        return ""
    if len(digitos) != 11:
        raise ValueError("El CUIT debe tener 11 dígitos (ej: 30-12345678-9).")
    return f"{digitos[:2]}-{digitos[2:10]}-{digitos[10]}"


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


def mes_actual_es(hoy=None):
    hoy = hoy or date.today()
    return f"{config.MESES_ES[hoy.month - 1]} {hoy.year}"


def mes_anterior_es(hoy=None):
    hoy = hoy or date.today()
    mes = hoy.month - 1
    anio = hoy.year
    if mes == 0:
        mes = 12
        anio -= 1
    return f"{config.MESES_ES[mes - 1]} {anio}"


def obtener_periodos(hoy=None):
    """
    Único punto donde se decide qué períodos lleva el recibo.
    Devuelve (expensas_de, gastos_de). Hoy: mes corriente y mes anterior.
    """
    return mes_actual_es(hoy), mes_anterior_es(hoy)


def fecha_hoy_es():
    hoy = date.today()
    return hoy.strftime("%d/%m/%Y")


def primera_palabra(texto):
    """Devuelve la primera palabra de un string (útil para extraer 'SEPTIEMBRE' de 'SEPTIEMBRE 2026')."""
    texto = (texto or "").strip()
    return texto.split(" ")[0] if texto else "PERIODO"


def nombre_archivo_recibo(edificio, piso, unidad, periodo, numero_recibo, carpeta_destino,
                          tipo="DEPTO", depto=""):
    """
    Genera el nombre de archivo del recibo y resuelve conflictos de nombre.
    Los deptos mantienen el formato de siempre; para local/cochera/baulera se
    agrega el tipo, y para las que pertenecen a un depto, la etiqueta de ese depto.
    Si el archivo "natural" ya existe, se le agrega el número de recibo
    como sufijo para no sobrescribir ni perder el archivo anterior.
    Devuelve la ruta completa del archivo.
    """
    partes = ["recibo_expensas", sanitize_filename(edificio)]
    if str(tipo or "").strip().upper() not in ("", "DEPTO"):
        partes.append(sanitize_filename(str(tipo).capitalize()))
    for texto in (piso, unidad):
        if str(texto or "").strip():
            partes.append(sanitize_filename(texto))
    if str(depto or "").strip():
        partes += ["Depto", sanitize_filename(depto)]
    partes.append(sanitize_filename(primera_palabra(periodo)))
    base = "_".join(partes)
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


def abrir_pdf(ruta_absoluta):
    """
    Abre un PDF con el visor/navegador predeterminado de Windows para
    archivos .pdf (en la mayoría de las instalaciones actuales de Windows
    esto es el navegador: Edge, Chrome, etc., si está configurado como
    visor de PDF por defecto).

    Devuelve (True, None) si se pudo abrir, o (False, mensaje) si no,
    para que quien llama pueda mostrarle al usuario la ruta del archivo
    como alternativa.
    """
    if not ruta_absoluta or not os.path.isfile(ruta_absoluta):
        return False, f"No se encontró el archivo en:\n{ruta_absoluta}"
    try:
        os.startfile(ruta_absoluta)  # usa el programa predeterminado (Windows)
        return True, None
    except AttributeError:
        # No estamos en Windows: intentamos como último recurso con el navegador
        try:
            uri = "file:///" + ruta_absoluta.replace("\\", "/")
            if webbrowser.open(uri):
                return True, None
        except Exception:
            pass
        return False, f"No se pudo abrir automáticamente. Ruta del archivo:\n{ruta_absoluta}"
    except Exception as e:
        return False, f"{e}\n\nRuta del archivo:\n{ruta_absoluta}"


def revelar_en_explorador(ruta_absoluta):
    """
    Abre el Explorador de Windows mostrando (con el archivo ya
    seleccionado) la carpeta que lo contiene. Si no es Windows o falla,
    intenta simplemente abrir la carpeta contenedora.
    """
    if not ruta_absoluta:
        return False
    try:
        if os.name == "nt":
            subprocess.run(["explorer", "/select,", os.path.normpath(ruta_absoluta)])
            return True
        else:
            os.startfile(os.path.dirname(ruta_absoluta))
            return True
    except Exception:
        try:
            return abrir_carpeta_en_explorador(os.path.dirname(ruta_absoluta))
        except Exception:
            return False
