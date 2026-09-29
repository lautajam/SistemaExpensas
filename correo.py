# -*- coding: utf-8 -*-
"""
correo.py
---------
Envío de recibos por mail: direcciones de cada unidad (hasta 4: inquilino y dueño),
configuración SMTP y el registro de qué se mandó.

Como con maestro.py, cada cosa vive en su propio CSV (por ahora; están pensados para
poder pasar a una base de datos más adelante sin cambiar esta interfaz):

    datos/emails_unidades.csv   una fila por unidad (por su id), con sus 4 direcciones
    configuracion/smtp.csv      un solo registro con lo necesario para mandar mails:
                                 servidor, puerto, usuario, contraseña y seguridad
    datos/mails_enviados.csv    un renglón por cada envío (a quién, cuándo, resultado)

El mail se manda "de" el propio usuario SMTP (no hay nombre/mail de remitente aparte:
en la gran mayoría de los servidores, Gmail incluido, el remitente tiene que ser esa
misma cuenta). La contraseña se guarda tal cual (no se puede hashear como la maestra:
hace falta poder usarla para conectarse al servidor); el acceso a esta pantalla ya está
protegido por la contraseña maestra.
"""

import csv
import os
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage

import config
from recibo import abreviar_periodo

EMAILS_CAMPOS = ["unidad_id", "inquilino1", "inquilino2", "dueno1", "dueno2"]
SMTP_CAMPOS = ["servidor", "puerto", "usuario", "password", "tls"]
ENVIADOS_CAMPOS = ["fecha", "edificio", "numero_recibo", "unidad", "destinatario", "resultado", "detalle"]

_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# CSV: helpers propios (igual que maestro.py, para no depender de database.py
# y evitar una importación circular: database.py sí importa correo.py)
# ---------------------------------------------------------------------------

def _read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _write_csv(path, fieldnames, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def _append_csv(path, fieldnames, row):
    existe = os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not existe:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in fieldnames})


# ---------------------------------------------------------------------------
# Direcciones de cada unidad
# ---------------------------------------------------------------------------

def es_email_valido(texto):
    return bool(_RE_EMAIL.match((texto or "").strip()))


def get_emails_unidades(edificio=None):
    """{unidad_id: {inquilino1, inquilino2, dueno1, dueno2}}. 'edificio' no filtra acá: el CSV
    no sabe de edificios (va por id de unidad), se filtra afuera contra las unidades del edificio."""
    filas = _read_csv(config.EMAILS_UNIDADES_CSV)
    return {f["unidad_id"]: {c: (f.get(c) or "").strip() for c in EMAILS_CAMPOS[1:]} for f in filas if f.get("unidad_id")}


def get_emails_unidad(unidad_id):
    return get_emails_unidades().get(unidad_id, {c: "" for c in EMAILS_CAMPOS[1:]})


def direcciones_de(unidad_id):
    """Lista de las direcciones cargadas para una unidad (1 a 4), sin vacíos."""
    datos = get_emails_unidad(unidad_id)
    return [datos[c] for c in EMAILS_CAMPOS[1:] if datos.get(c)]


def set_emails_unidades(datos_por_unidad):
    """
    Guarda de una las direcciones de varias unidades: {unidad_id: {inquilino1, inquilino2,
    dueno1, dueno2}}. Las unidades que no vienen en 'datos_por_unidad' conservan lo que tenían.
    """
    actuales = get_emails_unidades()
    actuales.update({uid: {c: (v.get(c) or "").strip() for c in EMAILS_CAMPOS[1:]} for uid, v in datos_por_unidad.items()})
    filas = [dict(unidad_id=uid, **valores) for uid, valores in actuales.items() if any(valores.values())]
    _write_csv(config.EMAILS_UNIDADES_CSV, EMAILS_CAMPOS, filas)


def borrar_emails_unidades(unidad_ids):
    """Quita las direcciones guardadas de las unidades indicadas (ej. al borrarlas)."""
    unidad_ids = set(unidad_ids)
    actuales = get_emails_unidades()
    if not (actuales.keys() & unidad_ids):
        return
    filas = [dict(unidad_id=uid, **v) for uid, v in actuales.items() if uid not in unidad_ids]
    _write_csv(config.EMAILS_UNIDADES_CSV, EMAILS_CAMPOS, filas)


# ---------------------------------------------------------------------------
# Configuración SMTP (lo mínimo para poder mandar: servidor, puerto, usuario,
# contraseña y seguridad de la conexión)
# ---------------------------------------------------------------------------

def existe_smtp():
    return os.path.isfile(config.SMTP_CSV)


def get_smtp():
    filas = _read_csv(config.SMTP_CSV)
    fila = filas[0] if filas else {}
    return {campo: fila.get(campo) or "" for campo in SMTP_CAMPOS}


def guardar_smtp(datos):
    """Guarda la configuración SMTP. Lanza ValueError si falta algo imprescindible."""
    fila = {campo: str(datos.get(campo, "")).strip() for campo in SMTP_CAMPOS}
    if not fila["servidor"]:
        raise ValueError("Falta el servidor SMTP.")
    if not fila["puerto"].isdigit():
        raise ValueError("El puerto tiene que ser un número.")
    if not fila["usuario"] or not es_email_valido(fila["usuario"]):
        raise ValueError("El usuario tiene que ser un mail válido: es también la dirección que figura como remitente.")
    _write_csv(config.SMTP_CSV, SMTP_CAMPOS, [fila])


def _conectar(smtp):
    """Conecta y autentica contra el servidor SMTP de 'smtp'. El llamador la cierra."""
    puerto = int(smtp["puerto"])
    if smtp.get("tls") == "SSL":
        conexion = smtplib.SMTP_SSL(smtp["servidor"], puerto, timeout=20)
    else:
        conexion = smtplib.SMTP(smtp["servidor"], puerto, timeout=20)
        if smtp.get("tls") == "STARTTLS":
            conexion.starttls()
    if smtp.get("usuario"):
        conexion.login(smtp["usuario"], smtp.get("password", ""))
    return conexion


def probar_conexion(smtp):
    """Intenta conectar y autenticar sin mandar nada. Devuelve (ok, mensaje)."""
    try:
        conexion = _conectar(smtp)
        conexion.quit()
        return True, "Conexión correcta."
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Texto del mail
# ---------------------------------------------------------------------------

def _descripcion_unidad(fila_historial):
    """'1° A, Cochera 6 y Baulera 2' a partir de lo guardado en el historial (piso + unidad)."""
    piso = (fila_historial.get("piso") or "").strip()
    unidad = (fila_historial.get("unidad") or "").strip()      # ej. "A" o "A + Cochera 6 + Baulera 2"
    partes = [p.strip() for p in unidad.split(" + ") if p.strip()]
    if not partes:
        return piso
    principal = f"{piso} {partes[0]}".strip() if piso else partes[0]
    resto = partes[1:]
    if not resto:
        return principal
    return f"{principal}, " + " y ".join(resto) if len(resto) > 1 else f"{principal} y {resto[0]}"


def construir_mensaje(fila_historial, edificio):
    """(asunto, cuerpo) del mail para un renglón del historial."""
    unidad_txt = _descripcion_unidad(fila_historial)
    expensas_de = abreviar_periodo(fila_historial.get("expensas_de", ""))
    gastos_de = abreviar_periodo(fila_historial.get("gastos_de", ""))
    asunto = f"Recibo expensas {edificio} - {expensas_de}"
    cuerpo = (
        f"Enviamos el recibo del pago de las expensas de {unidad_txt} del edificio {edificio} "
        f"correspondientes al mes de {expensas_de} gasto de {gastos_de}.\n\n"
        "Ante cualquier consulta, quedamos a disposición."
    )
    return asunto, cuerpo


# ---------------------------------------------------------------------------
# Envío
# ---------------------------------------------------------------------------

def enviar_mail(smtp, destinatario, asunto, cuerpo, ruta_adjunto):
    """Manda un único mail con el PDF adjunto. Devuelve (ok, mensaje_de_error_o_None)."""
    msg = EmailMessage()
    msg["From"] = smtp["usuario"]
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.set_content(cuerpo)

    try:
        with open(ruta_adjunto, "rb") as f:
            msg.add_attachment(f.read(), maintype="application", subtype="pdf",
                               filename=os.path.basename(ruta_adjunto))
    except OSError as e:
        return False, f"No se pudo adjuntar el PDF: {e}"

    try:
        conexion = _conectar(smtp)
        try:
            conexion.send_message(msg)
        finally:
            conexion.quit()
        return True, None
    except Exception as e:
        return False, str(e)


def registrar_envio(edificio, fila_historial, destinatario, ok, detalle=""):
    _append_csv(config.MAILS_ENVIADOS_CSV, ENVIADOS_CAMPOS, {
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "edificio": edificio,
        "numero_recibo": fila_historial.get("numero_recibo", ""),
        "unidad": _descripcion_unidad(fila_historial),
        "destinatario": destinatario,
        "resultado": "OK" if ok else "ERROR",
        "detalle": "" if ok else detalle,
    })


def enviar_recibo(fila_historial):
    """
    Manda el recibo de un renglón del historial a todas las direcciones cargadas para su
    unidad. Devuelve una lista de (destinatario, ok, detalle) — una entrada por cada intento
    (o un único ("(sin datos)", False, motivo) si no se pudo intentar nada).
    """
    edificio = fila_historial.get("edificio", "")
    resultados = []

    if not existe_smtp():
        return [("(smtp)", False, "No hay una configuración SMTP cargada (Administrar → Mailing → Configuración SMTP).")]

    unidad_id = (fila_historial.get("unidad_id") or "").strip()
    if not unidad_id:
        return [("(unidad)", False, "Este recibo es de antes de tener esta función: no está vinculado a una unidad.")]

    destinos = direcciones_de(unidad_id)
    if not destinos:
        return [("(sin mails)", False, "Esta unidad no tiene ninguna dirección de mail cargada.")]

    ruta_adjunto = os.path.join(config.BASE_DIR, fila_historial.get("archivo", ""))
    if not os.path.isfile(ruta_adjunto):
        detalle = f"No se encontró el PDF: {ruta_adjunto}"
        for destinatario in destinos:
            registrar_envio(edificio, fila_historial, destinatario, False, detalle)
            resultados.append((destinatario, False, detalle))
        return resultados

    smtp = get_smtp()
    asunto, cuerpo = construir_mensaje(fila_historial, edificio)
    for destinatario in destinos:
        ok, detalle = enviar_mail(smtp, destinatario, asunto, cuerpo, ruta_adjunto)
        registrar_envio(edificio, fila_historial, destinatario, ok, detalle or "")
        resultados.append((destinatario, ok, detalle))
    return resultados
