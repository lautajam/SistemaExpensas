# -*- coding: utf-8 -*-
"""
correo.py
---------
Envío de recibos por mail: direcciones de cada unidad (hasta 4: inquilino y dueño),
configuración SMTP y el registro de qué se mandó.

Los datos viven en la base de datos (ver db.py), en estas tablas:

    emails_unidades   una fila por unidad (por su id), con sus 4 direcciones
    smtp              un solo registro con lo necesario para mandar mails:
                       servidor, puerto, usuario, contraseña y seguridad
    copia_mail        un mail de copia (CC) para cada envío, que se puede activar o desactivar
    plantillas_mail   asunto y cuerpo del mail, personalizados por edificio
    mails_enviados    un renglón por cada envío (a quién, cuándo, resultado)

El mail se manda "de" el propio usuario SMTP (no hay nombre/mail de remitente aparte:
en la gran mayoría de los servidores, Gmail incluido, el remitente tiene que ser esa
misma cuenta). La contraseña se guarda tal cual (no se puede hashear como la maestra:
hace falta poder usarla para conectarse al servidor); el acceso a esta pantalla ya está
protegido por la contraseña maestra.
"""

import os
import re
import smtplib
import string
from datetime import datetime
from email.message import EmailMessage

import config
import db
from recibo import abreviar_periodo

EMAILS_CAMPOS = ["unidad_id", "inquilino1", "inquilino2", "dueno1", "dueno2"]
SMTP_CAMPOS = ["servidor", "puerto", "usuario", "password", "tls"]
ENVIADOS_CAMPOS = ["fecha", "edificio", "numero_recibo", "unidad", "destinatario", "resultado", "detalle"]
PLANTILLAS_CAMPOS = ["edificio", "asunto", "cuerpo"]

# Variables que se pueden usar en el asunto y el cuerpo del mail de cada edificio.
PLACEHOLDERS_PLANTILLA = ("edificio", "unidad", "expensas_de", "gastos_de")
ASUNTO_DEFECTO = "Recibo expensas {edificio} - {expensas_de}"
CUERPO_DEFECTO = (
    "Enviamos el recibo del pago de las expensas de {unidad} del edificio {edificio} "
    "correspondientes al mes de {expensas_de} gasto de {gastos_de}.\n\n"
    "Ante cualquier consulta, quedamos a disposición."
)

_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Direcciones de cada unidad
# ---------------------------------------------------------------------------

def es_email_valido(texto):
    return bool(_RE_EMAIL.match((texto or "").strip()))


def get_emails_unidades(edificio=None):
    """{unidad_id: {inquilino1, inquilino2, dueno1, dueno2}}. 'edificio' no filtra acá: el CSV
    no sabe de edificios (va por id de unidad), se filtra afuera contra las unidades del edificio."""
    filas = db.leer("emails_unidades")
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
    db.reemplazar("emails_unidades", filas)


def borrar_emails_unidades(unidad_ids):
    """Quita las direcciones guardadas de las unidades indicadas (ej. al borrarlas)."""
    unidad_ids = set(unidad_ids)
    actuales = get_emails_unidades()
    if not (actuales.keys() & unidad_ids):
        return
    filas = [dict(unidad_id=uid, **v) for uid, v in actuales.items() if uid not in unidad_ids]
    db.reemplazar("emails_unidades", filas)


# ---------------------------------------------------------------------------
# Configuración SMTP (lo mínimo para poder mandar: servidor, puerto, usuario,
# contraseña y seguridad de la conexión)
# ---------------------------------------------------------------------------

def existe_smtp():
    return bool(db.leer("smtp"))


def get_smtp():
    filas = db.leer("smtp")
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
    db.reemplazar("smtp", [fila])


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
# Copia (CC) en cada envío: un mail aparte, que se puede activar y desactivar
# ---------------------------------------------------------------------------

def get_copia():
    """{"email", "activa"}. 'activa' es "1" o "" (no se manda copia aunque haya un mail cargado)."""
    filas = db.leer("copia_mail")
    fila = filas[0] if filas else {}
    return {"email": fila.get("email") or "", "activa": fila.get("activa") or ""}


def guardar_copia(email, activa):
    """Guarda el mail de copia y si está activo. Lanza ValueError si se activa sin un mail válido."""
    email = (email or "").strip()
    if activa and not es_email_valido(email):
        raise ValueError("Para activar la copia hace falta un mail válido.")
    db.reemplazar("copia_mail", [{"email": email, "activa": "1" if activa else ""}])


def obtener_cc():
    """El mail a copiar en cada envío, o None si está desactivada o no hay ninguno cargado."""
    copia = get_copia()
    return copia["email"] if copia["activa"] and copia["email"] else None


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


def _validar_plantilla(texto):
    """Lanza ValueError si el texto usa una variable que no es una de PLACEHOLDERS_PLANTILLA."""
    if not texto:
        return
    try:
        nombres = [campo for _lit, campo, _spec, _conv in string.Formatter().parse(texto) if campo]
    except ValueError as e:   # ej. una "{" sin cerrar
        raise ValueError(f"El texto no es válido: {e}") from None
    desconocidas = sorted(set(nombres) - set(PLACEHOLDERS_PLANTILLA))
    if desconocidas:
        raise ValueError(
            "No se reconoce: {" + "}, {".join(desconocidas) + "}.\n"
            "Las variables disponibles son: {" + "}, {".join(PLACEHOLDERS_PLANTILLA) + "}.")


def get_plantilla(edificio):
    """(asunto, cuerpo) del edificio: lo que haya guardado, o el texto predeterminado si no se cargó nada."""
    fila = next((f for f in db.leer("plantillas_mail") if f["edificio"] == edificio), None)
    asunto = (fila.get("asunto") if fila else "") or ASUNTO_DEFECTO
    cuerpo = (fila.get("cuerpo") if fila else "") or CUERPO_DEFECTO
    return asunto, cuerpo


def set_plantilla(edificio, asunto, cuerpo):
    """
    Guarda el asunto y el cuerpo del mail de un edificio. Un campo vacío usa el predeterminado.
    Lanza ValueError si usan una variable que no existe.
    """
    asunto, cuerpo = (asunto or "").strip(), (cuerpo or "").strip()
    _validar_plantilla(asunto)
    _validar_plantilla(cuerpo)
    filas = [f for f in db.leer("plantillas_mail") if f["edificio"] != edificio]
    if asunto or cuerpo:
        filas.append({"edificio": edificio, "asunto": asunto, "cuerpo": cuerpo})
    db.reemplazar("plantillas_mail", filas)


def construir_mensaje(fila_historial, edificio):
    """(asunto, cuerpo) del mail para un renglón del historial, con la plantilla del edificio."""
    variables = {
        "edificio": edificio,
        "unidad": _descripcion_unidad(fila_historial),
        "expensas_de": abreviar_periodo(fila_historial.get("expensas_de", "")),
        "gastos_de": abreviar_periodo(fila_historial.get("gastos_de", "")),
    }
    asunto, cuerpo = get_plantilla(edificio)
    return asunto.format(**variables), cuerpo.format(**variables)


# ---------------------------------------------------------------------------
# Envío
# ---------------------------------------------------------------------------

def enviar_mail(smtp, destinatario, asunto, cuerpo, ruta_adjunto, cc=None):
    """Manda un único mail con el PDF adjunto, con copia a 'cc' si se pasa. Devuelve (ok, mensaje_de_error_o_None)."""
    msg = EmailMessage()
    msg["From"] = smtp["usuario"]
    msg["To"] = destinatario
    if cc and es_email_valido(cc) and cc.strip().lower() != destinatario.strip().lower():
        msg["Cc"] = cc.strip()
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
    db.agregar("mails_enviados", {
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "edificio": edificio,
        "numero_recibo": fila_historial.get("numero_recibo", ""),
        "unidad": _descripcion_unidad(fila_historial),
        "destinatario": destinatario,
        "resultado": "OK" if ok else "ERROR",
        "detalle": "" if ok else detalle,
    })


def enviar_recibo(fila_historial, cc=None):
    """
    Manda el recibo de un renglón del historial a todas las direcciones cargadas para su
    unidad, con copia a 'cc' si se pasa. Devuelve una lista de (destinatario, ok, detalle) —
    una entrada por cada intento (o un único ("(sin datos)", False, motivo) si no se pudo intentar nada).
    """
    if not existe_smtp():
        return [("(smtp)", False, "No hay una configuración SMTP cargada (Administrar → Mailing → Configuración SMTP).")]

    unidad_id = (fila_historial.get("unidad_id") or "").strip()
    if not unidad_id:
        return [("(unidad)", False, "Este recibo es de antes de tener esta función: no está vinculado a una unidad.")]

    destinos = direcciones_de(unidad_id)
    if not destinos:
        return [("(sin mails)", False, "Esta unidad no tiene ninguna dirección de mail cargada.")]

    resultados = []
    for destinatario in destinos:
        ok, detalle = reenviar(fila_historial, destinatario, cc=cc)
        resultados.append((destinatario, ok, detalle))
    return resultados


def reenviar(fila_historial, destinatario, cc=None):
    """
    Manda (o vuelve a mandar) el recibo de un renglón del historial a una única dirección, con
    copia a 'cc' si se pasa. Queda registrado en el historial de envíos como un envío más.
    Devuelve (ok, detalle).
    """
    edificio = fila_historial.get("edificio", "")
    if not existe_smtp():
        return False, "No hay una configuración SMTP cargada (Administrar → Mailing → Configuración SMTP)."

    ruta_adjunto = os.path.join(config.BASE_DIR, fila_historial.get("archivo", ""))
    if not os.path.isfile(ruta_adjunto):
        detalle = f"No se encontró el PDF: {ruta_adjunto}"
        registrar_envio(edificio, fila_historial, destinatario, False, detalle)
        return False, detalle

    smtp = get_smtp()
    asunto, cuerpo = construir_mensaje(fila_historial, edificio)
    ok, detalle = enviar_mail(smtp, destinatario, asunto, cuerpo, ruta_adjunto, cc=cc)
    registrar_envio(edificio, fila_historial, destinatario, ok, detalle or "")
    return ok, detalle


def get_mails_enviados(edificio=None):
    """Registro de envíos, del más nuevo al más viejo. Con 'edificio', solo los de ese edificio."""
    filas = db.leer("mails_enviados")
    if edificio:
        filas = [f for f in filas if f.get("edificio") == edificio]
    return list(reversed(filas))
