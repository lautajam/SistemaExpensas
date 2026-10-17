# -*- coding: utf-8 -*-
"""
ui.py
-----
Toda la interfaz gráfica (PySide6/Qt) de Sistema de Expensas.

Contiene:
    - App: ventana principal.
    - DialogoUnidad: alta/edición de una unidad.
    - DialogoEdificioNuevo: alta de un edificio.
    - VentanaAdministracion: administrar edificios y unidades.
    - VentanaConfiguracion: datos de la inmobiliaria.
    - VentanaMails / DialogoConfiguracionSMTP / DialogoPlantillaMail / DialogoCopiaMail: mailing.
    - VentanaHistorial / VentanaRegistroEnvios: historial de recibos y de mails.
    - VentanaAyudaRecibos: guía de uso.
    - VentanaCargarBackup: restaurar un backup.

Cualquier error inesperado se captura y se muestra como un mensaje
comprensible (QMessageBox), nunca como un traceback crudo de Python.

No toca config.py, database.py, pagos.py, recibo.py, pdf_generator.py ni
unidades.py: esta ventana es solo una capa de presentación sobre la misma
lógica de negocio.
"""

import ctypes
import logging
import os
import shutil
import sys
from datetime import date, datetime

_DIR_RECURSOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recursos_qt").replace("\\", "/")

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QAction, QColor, QFont, QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import config
import correo
import database
import maestro
import pagos
from utils import (
    abrir_carpeta_en_explorador,
    abrir_pdf,
    fecha_hoy_es,
    format_currency_ar,
    nombre_archivo_recibo,
    normalizar_cuit,
    obtener_periodos,
    parse_importe,
    revelar_en_explorador,
)
from pdf_generator import generar_pdf_recibo
from recibo import armar_datos as armar_datos_recibo
from unidades import (
    BAULERA,
    COCHERA,
    DEPTO,
    LOCAL,
    TIPOS,
    TIPOS_ASOCIABLES,
    MODO_APARTE,
    MODO_JUNTO,
    MODO_TOTAL,
    asociadas_que_pagan_junto,
    depto_de,
    descripcion_asociadas,
    etiqueta_unidad,
    incluida_en_total,
    indice_por_id,
    modo_pago,
    nombre_tipo,
    normalizar_tipo,
    ordenar_con_asociadas,
    ordenar_para_pantalla,
)

logger = logging.getLogger(__name__)

# Paleta: modo oscuro con acentos naranja + azul, tarjetas apenas más claras que el
# fondo, y badges de color para estados en vez de texto plano.
COLOR_FONDO = "#0f1115"
COLOR_TARJETA = "#1a1d24"
COLOR_TARJETA_ALT = "#20242d"
COLOR_BORDE = "#2b2f3a"
COLOR_TEXTO = "#e6e8eb"
COLOR_TEXTO_SUAVE = "#8b92a0"
COLOR_ACENTO = "#3b82f6"
COLOR_ACENTO_HOVER = "#2563eb"
COLOR_PRIMARIA = "#f97316"
COLOR_PRIMARIA_HOVER = "#ea580c"

COLUMNAS = ("emitido", "tipo", "piso", "unidad", "uf", "depto", "dueno", "inquilino", "importe", "estado", "sel")
TITULOS = {
    "emitido": "EMITIDO", "tipo": "TIPO", "piso": "PISO", "unidad": "LETRA/N°", "uf": "UF",
    "depto": "RELACIÓN", "dueno": "DUEÑO", "inquilino": "INQUILINO", "importe": "IMPORTE",
    "estado": "PAGO", "sel": "EMITIR",
}
# (fondo del chip, texto del chip) por estado de pago normalizado.
CHIP_ESTADO = {
    "total": ("rgba(34, 197, 94, 0.16)", "#4ade80"),
    "a cta": ("rgba(245, 158, 11, 0.16)", "#fbbf24"),
    "parcial": ("rgba(245, 158, 11, 0.16)", "#fbbf24"),
    "deuda": ("rgba(239, 68, 68, 0.16)", "#f87171"),
    "no pagado": ("rgba(148, 163, 184, 0.16)", "#94a3b8"),
}
CHIP_ESTADO_DEFECTO = ("rgba(148, 163, 184, 0.16)", "#94a3b8")
CHIP_EMITIDO = ("rgba(34, 197, 94, 0.16)", "#4ade80")
CHIP_PENDIENTE = ("rgba(239, 68, 68, 0.16)", "#f87171")

ANCHOS = {
    "emitido": 96, "tipo": 80, "piso": 56, "unidad": 80, "uf": 50, "depto": 160,
    "dueno": 120, "inquilino": 120, "importe": 100, "estado": 100, "sel": 68,
}

ESTILO = f"""
QMainWindow {{ background-color: {COLOR_FONDO}; }}
QWidget {{ background-color: {COLOR_FONDO}; }}

QWidget#franjaColor {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {COLOR_PRIMARIA}, stop:1 {COLOR_ACENTO});
}}

QWidget#barraSuperior {{
    background-color: {COLOR_TARJETA};
    border-bottom: 1px solid {COLOR_BORDE};
}}
QLabel#titulo {{ color: {COLOR_TEXTO}; font-size: 26px; font-weight: 700; background: transparent; }}
QLabel#subtitulo {{ color: {COLOR_TEXTO_SUAVE}; font-size: 13px; background: transparent; }}

QWidget#tarjeta {{
    background-color: {COLOR_TARJETA};
    border: 1px solid {COLOR_BORDE};
    border-radius: 10px;
}}

QLabel {{ color: {COLOR_TEXTO}; font-size: 12px; background: transparent; }}
QLabel#error {{ color: #f87171; font-size: 11px; background: transparent; }}
QLabel#enlace {{ color: {COLOR_ACENTO}; font-size: 11px; text-decoration: underline; background: transparent; }}

QLineEdit {{
    background-color: {COLOR_TARJETA_ALT};
    border: 1px solid {COLOR_BORDE};
    border-radius: 6px;
    padding: 6px 10px;
    color: {COLOR_TEXTO};
    font-size: 12px;
}}
QLineEdit:focus {{ border-color: {COLOR_ACENTO}; }}

QPlainTextEdit {{
    background-color: {COLOR_TARJETA_ALT};
    border: 1px solid {COLOR_BORDE};
    border-radius: 6px;
    padding: 6px 10px;
    color: {COLOR_TEXTO};
    font-size: 12px;
}}
QPlainTextEdit:focus {{ border-color: {COLOR_ACENTO}; }}

QFrame#separador {{ background-color: {COLOR_BORDE}; max-height: 1px; min-height: 1px; border: none; }}

QComboBox {{
    background-color: {COLOR_TARJETA_ALT};
    border: 1px solid {COLOR_BORDE};
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 20px;
    font-size: 12px;
    color: {COLOR_TEXTO};
}}
QComboBox:hover {{ border-color: {COLOR_ACENTO}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: url({_DIR_RECURSOS}/flecha_abajo.png); width: 10px; height: 10px; }}
QComboBox:disabled {{ color: {COLOR_TEXTO_SUAVE}; background-color: {COLOR_TARJETA}; }}

QListWidget#listaSimple {{
    background-color: {COLOR_TARJETA_ALT};
    border: 1px solid {COLOR_BORDE};
    border-radius: 6px;
}}

QWidget#sidebar {{
    background-color: {COLOR_TARJETA};
    border-right: 1px solid {COLOR_BORDE};
}}
QLabel#tituloSidebar {{
    color: {COLOR_TEXTO_SUAVE}; font-size: 11px; font-weight: 700; background: transparent;
}}
QListWidget {{
    background-color: transparent;
    border: none;
    font-size: 13px;
    color: {COLOR_TEXTO};
    outline: none;
}}
QListWidget::item {{
    padding: 10px 12px;
    border-radius: 6px;
    margin-bottom: 2px;
}}
QListWidget::item:hover {{ background-color: rgba(59, 130, 246, 0.18); }}
QListWidget::item:selected {{ background-color: {COLOR_ACENTO}; color: white; }}

QMenuBar {{
    background-color: {COLOR_TARJETA};
    border-bottom: 1px solid {COLOR_BORDE};
    padding: 4px 8px;
    color: {COLOR_TEXTO};
}}
QMenuBar::item {{ padding: 6px 10px; border-radius: 6px; color: {COLOR_TEXTO}; background: transparent; }}
QMenuBar::item:selected {{ background-color: rgba(59, 130, 246, 0.18); }}
QMenu {{
    background-color: {COLOR_TARJETA_ALT};
    border: 1px solid {COLOR_BORDE};
    border-radius: 8px;
    padding: 6px;
    color: {COLOR_TEXTO};
}}
QMenu::item {{ padding: 6px 20px; border-radius: 6px; }}
QMenu::item:selected {{ background-color: rgba(59, 130, 246, 0.18); }}

QPushButton {{
    border-radius: 6px;
    padding: 8px 14px;
    font-size: 12px;
    background-color: {COLOR_TARJETA_ALT};
    color: {COLOR_TEXTO};
    border: 1px solid {COLOR_BORDE};
}}
QPushButton:hover {{ background-color: #262b35; border-color: #3a3f4c; }}
QPushButton:pressed {{ background-color: #1c2028; }}

QPushButton#botonAcento {{ background-color: {COLOR_ACENTO}; color: white; border: none; font-weight: 600; }}
QPushButton#botonAcento:hover {{ background-color: {COLOR_ACENTO_HOVER}; }}
QPushButton#botonAcento:pressed {{ background-color: #1d4ed8; }}

QPushButton#botonPrimario {{
    background-color: {COLOR_PRIMARIA}; color: white; border: none;
    font-size: 13px; font-weight: 700; padding: 10px 22px;
}}
QPushButton#botonPrimario:hover {{ background-color: {COLOR_PRIMARIA_HOVER}; }}
QPushButton#botonPrimario:pressed {{ background-color: #c2410c; }}

QCheckBox {{ background: transparent; color: {COLOR_TEXTO}; font-size: 12px; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {COLOR_BORDE};
    border-radius: 4px;
    background-color: {COLOR_TARJETA_ALT};
}}
QCheckBox::indicator:hover {{ border-color: {COLOR_ACENTO}; }}
QCheckBox::indicator:checked {{
    background-color: {COLOR_ACENTO};
    border-color: {COLOR_ACENTO};
    image: url({_DIR_RECURSOS}/check.png);
}}

QTableWidget {{
    background-color: {COLOR_TARJETA};
    border: 1px solid {COLOR_BORDE};
    gridline-color: transparent;
    font-size: 12px;
    color: {COLOR_TEXTO};
    alternate-background-color: {COLOR_TARJETA_ALT};
}}
QTableWidget::item {{ padding: 4px; border-bottom: 1px solid #23262e; background: transparent; }}
QHeaderView::section {{
    background-color: {COLOR_TARJETA};
    color: {COLOR_TEXTO_SUAVE};
    font-size: 10px;
    font-weight: 600;
    padding: 9px 6px;
    border: none;
    border-bottom: 1px solid {COLOR_BORDE};
}}

QMessageBox, QDialog {{ background-color: {COLOR_TARJETA}; }}

QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #3a3f4c; border-radius: 4px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: #4a505f; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #3a3f4c; border-radius: 4px; min-width: 24px; }}
QScrollBar::handle:horizontal:hover {{ background: #4a505f; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
"""


def manejar_error(titulo, error, parent=None):
    logger.exception(titulo)
    QMessageBox.critical(parent, titulo, f"Ocurrió un problema:\n\n{error}")


def mostrar_avisos(parent=None):
    for aviso in database.tomar_avisos():
        QMessageBox.warning(parent, "Planilla de pagos", aviso)


# ===========================================================================
# Contraseña maestra (ver maestro.py): protege abrir Administrar edificios/unidades,
# Mailing y Configuración de la inmobiliaria, y cada alta/edición/borrado dentro de ellas.
#
# Los diálogos son asincrónicos (on_ok, no bloquean), igual que en la versión Tkinter.
# ===========================================================================

def requerir_maestro(parent, on_ok, motivo=""):
    """
    Gate de una acción protegida por la contraseña maestra. Con el control maestro
    activo llama a on_ok() de una: no pregunta nada. Si todavía no hay contraseña
    creada, obliga a crear una. Si se cancela o se pone una contraseña incorrecta,
    no llama a on_ok(): quien invoca no tiene que hacer nada más.
    """
    if maestro.esta_activo():
        on_ok()
        return
    if not maestro.existe():
        DialogoCrearMaestro(parent, on_ok=on_ok).show()
        return
    DialogoPedirPassword(parent, on_ok=on_ok, motivo=motivo).show()


class DialogoCrearMaestro(QDialog):
    """Crea (o reemplaza) la contraseña maestra y su pregunta de seguridad."""

    def __init__(self, parent, on_ok=None, motivo=None):
        super().__init__(parent)
        self.on_ok = on_ok
        self.setWindowTitle("Crear contraseña maestra")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        texto = QLabel(motivo or "Esta contraseña se va a pedir para administrar edificios, "
                                  "unidades, la inmobiliaria y los datos.")
        texto.setWordWrap(True)
        layout.addWidget(texto)

        grilla = QGridLayout()
        grilla.setHorizontalSpacing(10)
        grilla.setVerticalSpacing(6)
        self.campo_pw = QLineEdit()
        self.campo_pw.setEchoMode(QLineEdit.Password)
        self.campo_pw2 = QLineEdit()
        self.campo_pw2.setEchoMode(QLineEdit.Password)
        self.campo_pregunta = QLineEdit()
        self.campo_respuesta = QLineEdit()
        for fila, (etiqueta, campo) in enumerate((
            ("Contraseña nueva:", self.campo_pw),
            ("Repetir contraseña:", self.campo_pw2),
            ("Pregunta de seguridad:", self.campo_pregunta),
            ("Respuesta:", self.campo_respuesta),
        )):
            grilla.addWidget(QLabel(etiqueta), fila, 0)
            grilla.addWidget(campo, fila, 1)
        layout.addLayout(grilla)
        self.campo_pw.setFocus()

        aviso = QLabel("Guardala bien: si la olvidás, se restablece con la pregunta de seguridad.")
        aviso.setStyleSheet(f"color: {COLOR_TEXTO_SUAVE}; font-size: 10px; background: transparent;")
        aviso.setWordWrap(True)
        layout.addWidget(aviso)

        botones = QHBoxLayout()
        boton_guardar = QPushButton("Guardar")
        boton_guardar.setObjectName("botonAcento")
        boton_guardar.clicked.connect(self._guardar)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        botones.addWidget(boton_guardar)
        botones.addWidget(boton_cancelar)
        botones.addStretch()
        layout.addLayout(botones)

    def _guardar(self):
        if self.campo_pw.text() != self.campo_pw2.text():
            QMessageBox.warning(self, "Contraseñas distintas", "Las dos contraseñas no coinciden.")
            return
        try:
            maestro.crear(self.campo_pw.text(), self.campo_pregunta.text(), self.campo_respuesta.text())
        except ValueError as e:
            QMessageBox.warning(self, "Datos incompletos", str(e))
            return
        self.accept()
        if self.on_ok:
            self.on_ok()


class DialogoPedirPassword(QDialog):
    """Pide la contraseña maestra para una sola acción (no activa el control maestro)."""

    def __init__(self, parent, on_ok=None, titulo="Contraseña maestra", motivo=""):
        super().__init__(parent)
        self.on_ok = on_ok
        self.motivo = motivo
        self.setWindowTitle(titulo)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        fila = QHBoxLayout()
        fila.addWidget(QLabel("Contraseña:"))
        self.campo_pw = QLineEdit()
        self.campo_pw.setEchoMode(QLineEdit.Password)
        self.campo_pw.returnPressed.connect(self._confirmar)
        fila.addWidget(self.campo_pw)
        layout.addLayout(fila)
        self.campo_pw.setFocus()

        self.lbl_error = QLabel("")
        self.lbl_error.setObjectName("error")
        layout.addWidget(self.lbl_error)

        enlace = QLabel("¿Olvidaste tu contraseña?")
        enlace.setObjectName("enlace")
        enlace.setCursor(Qt.PointingHandCursor)
        enlace.mousePressEvent = lambda e: self._olvidada()
        layout.addWidget(enlace)

        botones = QHBoxLayout()
        boton_confirmar = QPushButton("Confirmar")
        boton_confirmar.setObjectName("botonAcento")
        boton_confirmar.clicked.connect(self._confirmar)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        botones.addWidget(boton_confirmar)
        botones.addWidget(boton_cancelar)
        botones.addStretch()
        layout.addLayout(botones)

    def _confirmar(self):
        if maestro.verificar_password(self.campo_pw.text(), motivo=self.motivo):
            self.accept()
            if self.on_ok:
                self.on_ok()
            return
        self.lbl_error.setText("Contraseña incorrecta.")
        self.campo_pw.clear()

    def _olvidada(self):
        def al_recuperar():
            self.accept()
            if self.on_ok:
                self.on_ok()
        DialogoRecuperarMaestro(self, on_ok=al_recuperar).show()


class DialogoRecuperarMaestro(QDialog):
    """Restablece la contraseña maestra respondiendo la pregunta de seguridad."""

    def __init__(self, parent, on_ok=None):
        super().__init__(parent)
        self.on_ok = on_ok
        self.setWindowTitle("Restablecer contraseña maestra")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        pregunta = QLabel(maestro.obtener_pregunta() or "")
        pregunta.setWordWrap(True)
        pregunta.setStyleSheet(f"color: {COLOR_TEXTO}; font-weight: 700; background: transparent;")
        layout.addWidget(pregunta)

        fila = QHBoxLayout()
        fila.addWidget(QLabel("Respuesta:"))
        self.campo_resp = QLineEdit()
        self.campo_resp.returnPressed.connect(self._verificar)
        fila.addWidget(self.campo_resp)
        layout.addLayout(fila)
        self.campo_resp.setFocus()

        self.lbl_error = QLabel("")
        self.lbl_error.setObjectName("error")
        layout.addWidget(self.lbl_error)

        botones = QHBoxLayout()
        boton_verificar = QPushButton("Verificar")
        boton_verificar.setObjectName("botonAcento")
        boton_verificar.clicked.connect(self._verificar)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        botones.addWidget(boton_verificar)
        botones.addWidget(boton_cancelar)
        botones.addStretch()
        layout.addLayout(botones)

    def _verificar(self):
        if not maestro.verificar_respuesta(self.campo_resp.text()):
            self.lbl_error.setText("Respuesta incorrecta.")
            self.campo_resp.clear()
            return

        def al_crear():
            self.accept()
            if self.on_ok:
                self.on_ok()
        DialogoCrearMaestro(self, on_ok=al_crear, motivo="Respuesta correcta. Elegí una contraseña nueva:").show()


class VentanaControlMaestro(QDialog):
    """Menú Administrar → Control maestro: activar/bloquear la sesión y cambiar la contraseña."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Control maestro")
        self.setModal(True)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 16, 20, 16)
        self._layout.setSpacing(10)
        self._dibujar()

    def _limpiar(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _dibujar(self):
        self._limpiar()

        if not maestro.existe():
            texto = QLabel("Todavía no configuraste una contraseña maestra.\n"
                            "Mientras tanto, administrar edificios, unidades y la\n"
                            "inmobiliaria queda libre, sin pedir nada.")
            texto.setWordWrap(True)
            self._layout.addWidget(texto)
            boton = QPushButton("Crear contraseña maestra")
            boton.setObjectName("botonAcento")
            boton.clicked.connect(self._crear)
            self._layout.addWidget(boton)
            return

        if maestro.esta_activo():
            estado = QLabel("Control maestro ACTIVO.")
            estado.setStyleSheet("color: #4ade80; font-weight: 700; background: transparent;")
            self._layout.addWidget(estado)
            detalle = QLabel("No te va a pedir la contraseña hasta que lo bloquees\no cierres el programa.")
            detalle.setWordWrap(True)
            self._layout.addWidget(detalle)
            boton = QPushButton("Bloquear")
            boton.setStyleSheet("background-color: #dc2626; color: white; border: none;")
            boton.clicked.connect(self._bloquear)
            self._layout.addWidget(boton)
        else:
            estado = QLabel("Control maestro bloqueado.")
            estado.setStyleSheet("font-weight: 700; background: transparent;")
            self._layout.addWidget(estado)
            detalle = QLabel("Desbloquealo para administrar sin que te pida la\ncontraseña en cada acción.")
            detalle.setWordWrap(True)
            self._layout.addWidget(detalle)
            boton = QPushButton("Desbloquear")
            boton.setObjectName("botonAcento")
            boton.clicked.connect(self._desbloquear)
            self._layout.addWidget(boton)

        separador = QFrame()
        separador.setObjectName("separador")
        separador.setFrameShape(QFrame.HLine)
        self._layout.addWidget(separador)

        boton_cambiar = QPushButton("Cambiar contraseña / pregunta")
        boton_cambiar.clicked.connect(self._cambiar)
        self._layout.addWidget(boton_cambiar)

    def _crear(self):
        DialogoCrearMaestro(self, on_ok=self._dibujar).show()

    def _desbloquear(self):
        def al_confirmar():
            maestro.activar()
            self._dibujar()
        DialogoPedirPassword(self, on_ok=al_confirmar, motivo="activar el control maestro").show()

    def _bloquear(self):
        maestro.desactivar()
        self._dibujar()

    def _cambiar(self):
        def al_confirmar():
            DialogoCrearMaestro(self, on_ok=self._dibujar, motivo="Nueva contraseña maestra:").show()
        DialogoPedirPassword(
            self, on_ok=al_confirmar, titulo="Confirmá la contraseña actual",
            motivo="cambiar la contraseña o la pregunta de seguridad").show()


# ===========================================================================
# Helpers compartidos por los diálogos de unidades/edificios (se usan a medida
# que se van portando VentanaAdministracion, DialogoUnidad, etc.)
# ===========================================================================

NINGUNO = "(ninguno)"


def confirmar_y_borrar(parent, unidad_id, on_borrado=None):
    """
    Muestra qué se va a borrar (la unidad y, si es un depto, sus cocheras y bauleras),
    pide confirmación y la contraseña maestra, y borra. Si se borra, llama a on_borrado().
    """
    afectadas = database.unidades_a_borrar(unidad_id)
    if not afectadas:
        return
    por_id = indice_por_id(database.get_unidades_por_edificio(afectadas[0]["edificio"]))
    lineas = [
        f"  • {etiqueta_unidad(u, por_id)}" + (f" — {u['inquilino']}" if u["inquilino"] else "")
        for u in afectadas[:12]
    ]
    if len(afectadas) > 12:
        lineas.append(f"  … y {len(afectadas) - 12} más")

    confirmado = QMessageBox.question(
        parent, "Borrar unidad",
        "Se va a BORRAR:\n\n" + "\n".join(lineas) + "\n\n"
        "También se quita de la planilla de pagos del edificio. Los recibos ya generados "
        "y el historial no se borran.\nEsta acción no se puede deshacer.\n\n¿Borrar?",
    )
    if confirmado != QMessageBox.Yes:
        return

    def borrar_de_verdad():
        try:
            database.delete_unidad(unidad_id)
        except Exception as e:
            manejar_error("No se pudo borrar la unidad", e, parent)
            return
        mostrar_avisos(parent)
        if on_borrado:
            on_borrado()

    requerir_maestro(parent, borrar_de_verdad, motivo="borrar una unidad")


def confirmar_modo_celdas(parent, edificio):
    """
    Si el edificio todavía no usa celdas, avisa lo que cambia al asignar la primera:
    la app deja de armar y tocar su planilla y solo la lee tal cual. True si sigue.
    """
    if pagos.modo_celdas(database.get_unidades_por_edificio(edificio)):
        return True
    return QMessageBox.question(
        parent, "Planilla con celdas",
        f"Al asignar una celda, la planilla de pagos de «{edificio}» pasa a usarse tal cual está: "
        "la app deja de modificarla y lee los montos de la celda de cada unidad.\n\n"
        f"El archivo tiene que estar en:\n{pagos.ruta_pagos_edificio(edificio)}\n\n"
        "Las unidades sin celda no van a poder generar recibo hasta que se les asigne una.\n\n"
        "¿Continuar?",
    ) == QMessageBox.Yes


def _oscurecer_barra_titulo(widget):
    """En Windows, pinta la barra de título nativa (donde están minimizar/maximizar/cerrar)
    en oscuro, para que haga juego con el contenido de la ventana. Sin esto, Windows la
    dibuja blanca por default, aunque todo lo de adentro sea oscuro. No hace nada si falla
    (ej. versión de Windows vieja): la app sigue andando igual, solo queda la barra clara."""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())
        valor = ctypes.c_int(1)
        for atributo in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE: 20 desde Windows 10 20H1, 19 antes
            resultado = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, atributo, ctypes.byref(valor), ctypes.sizeof(valor))
            if resultado == 0:
                break
    except Exception:
        logger.debug("No se pudo oscurecer la barra de título de la ventana", exc_info=True)


class _OscurecedorBarraTitulo(QObject):
    """Filtro de eventos de toda la app: apenas se muestra una ventana nueva (la principal
    o cualquier diálogo), le oscurece la barra de título. Se instala una sola vez."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Show and isinstance(obj, QWidget) and obj.isWindow():
            _oscurecer_barra_titulo(obj)
        return False


def _estilizar_combo(combo):
    """Aplica el mismo estilo oscuro (con hover azul) al desplegable de cualquier QComboBox.
    Hace falta ponerlo por instancia: Fusion pinta el popup de un QComboBox con QPalette.Highlight
    y no respeta el ::item:hover del QSS global."""
    vista = combo.view()
    vista.setMouseTracking(True)
    vista.setStyleSheet(f"""
        QListView {{
            background-color: {COLOR_TARJETA_ALT};
            color: {COLOR_TEXTO};
            border: 1px solid {COLOR_BORDE};
            outline: none;
            padding: 4px;
        }}
        QListView::item {{
            background-color: {COLOR_TARJETA_ALT};
            color: {COLOR_TEXTO};
            padding: 8px 10px;
            border-radius: 4px;
            min-height: 20px;
        }}
        QListView::item:hover {{
            background-color: {COLOR_ACENTO};
            color: white;
        }}
        QListView::item:selected {{
            background-color: {COLOR_ACENTO_HOVER};
            color: white;
        }}
    """)


def _crear_sidebar_edificios(cuerpo, nombres, al_cambiar):
    """Panel lateral fijo con la lista de edificios (QListWidget) para elegir/filtrar por uno,
    igual que en la ventana principal: a diferencia de un QComboBox desplegable, el hover
    funciona de forma confiable."""
    sidebar = QWidget()
    sidebar.setObjectName("sidebar")
    sidebar.setFixedWidth(220)
    sidebar_layout = QVBoxLayout(sidebar)
    sidebar_layout.setContentsMargins(16, 20, 16, 20)
    sidebar_layout.setSpacing(10)

    titulo = QLabel("EDIFICIOS")
    titulo.setObjectName("tituloSidebar")
    sidebar_layout.addWidget(titulo)

    lista = QListWidget()
    lista.setFocusPolicy(Qt.NoFocus)
    lista.addItems(nombres)
    lista.currentItemChanged.connect(lambda *_: al_cambiar())
    sidebar_layout.addWidget(lista, 1)

    cuerpo.addWidget(sidebar)
    return lista


# Cómo paga una cochera/baulera de un depto: (código guardado, texto para elegir, texto corto de la lista)
MODOS_PAGO = [
    (MODO_APARTE, "Recibo aparte", "recibo aparte"),
    (MODO_JUNTO, "Paga junto con el depto (tiene su fila en la planilla)", "paga junto"),
    (MODO_TOTAL, "Incluida en el total del depto (sin fila ni celda propia)", "incluida en el total"),
]
_TEXTO_MODO = {cod: largo for cod, largo, _corto in MODOS_PAGO}
_CORTO_MODO = {cod: corto for cod, _largo, corto in MODOS_PAGO}
_CODIGO_MODO = {largo: cod for cod, largo, _corto in MODOS_PAGO}


# ===========================================================================
# Diálogo: alta / edición de unidad (depto, local, cochera o baulera)
# ===========================================================================

class DialogoAsociada(QDialog):
    """Mini formulario para sumar una cochera o baulera a un depto."""

    def __init__(self, parent, tipo, on_agregar):
        super().__init__(parent)
        self.tipo = tipo
        self.on_agregar = on_agregar
        self.setWindowTitle(f"Nueva {nombre_tipo(tipo).lower()}")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        grilla = QGridLayout()
        grilla.setHorizontalSpacing(10)
        grilla.setVerticalSpacing(6)
        self.campo_celda = QLineEdit()
        self.campo_unidad = QLineEdit()
        self.campo_uf = QLineEdit()
        self.campo_piso = QLineEdit()
        self.campo_dueno = QLineEdit()
        self.campo_importe = QLineEdit("0")
        for fila, (etiqueta, campo) in enumerate((
            ("Celda en la planilla (ej. B12):", self.campo_celda),
            ("Número (ej: 3):", self.campo_unidad),
            ("Unidad funcional (UF):", self.campo_uf),
            ("Piso (opcional):", self.campo_piso),
            ("Dueño:", self.campo_dueno),
            ("Importe:", self.campo_importe),
        )):
            grilla.addWidget(QLabel(etiqueta), fila, 0)
            grilla.addWidget(campo, fila, 1)
        layout.addLayout(grilla)
        self.campo_unidad.setFocus()

        nota = QLabel("El inquilino es el del depto.")
        nota.setStyleSheet(f"color: {COLOR_TEXTO_SUAVE}; font-size: 10px; background: transparent;")
        layout.addWidget(nota)

        fila_modo = QHBoxLayout()
        fila_modo.addWidget(QLabel("Cómo paga:"))
        self.combo_modo = QComboBox()
        self.combo_modo.addItems([largo for _c, largo, _k in MODOS_PAGO])
        _estilizar_combo(self.combo_modo)
        fila_modo.addWidget(self.combo_modo)
        layout.addLayout(fila_modo)

        botones = QHBoxLayout()
        boton_agregar = QPushButton("Agregar")
        boton_agregar.setObjectName("botonAcento")
        boton_agregar.clicked.connect(self._agregar)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        botones.addWidget(boton_agregar)
        botones.addWidget(boton_cancelar)
        botones.addStretch()
        layout.addLayout(botones)

    def _agregar(self):
        numero = self.campo_unidad.text().strip()
        if not numero:
            QMessageBox.warning(self, "Datos incompletos", "Completá el número.")
            return
        try:
            celda = pagos.normalizar_celda(self.campo_celda.text())
        except ValueError as e:
            QMessageBox.warning(self, "Celda inválida", str(e))
            return
        modo = _CODIGO_MODO[self.combo_modo.currentText()]
        self.on_agregar({
            "tipo": self.tipo,
            "unidad": numero,
            "uf": self.campo_uf.text().strip(),
            "piso": self.campo_piso.text().strip(),
            "dueno": self.campo_dueno.text().strip(),
            "importe": parse_importe(self.campo_importe.text()),
            "paga_junto": modo,
            "celda": "" if modo == MODO_TOTAL else celda,
        })
        self.accept()


class DialogoElegirAsociada(QDialog):
    """Lista de cocheras/bauleras ya creadas para sumarlas a un depto."""

    def __init__(self, parent, candidatas, on_elegir):
        super().__init__(parent)
        self.candidatas = candidatas
        self.on_elegir = on_elegir
        self.setWindowTitle("Vincular existente")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        titulo = QLabel("Cocheras y bauleras sueltas (podés elegir varias):")
        titulo.setStyleSheet(f"color: {COLOR_TEXTO}; font-weight: 700; background: transparent;")
        layout.addWidget(titulo)

        self.lista = QListWidget()
        self.lista.setObjectName("listaSimple")
        self.lista.setSelectionMode(QAbstractItemView.ExtendedSelection)
        for _id, nombre in candidatas:
            self.lista.addItem(nombre)
        layout.addWidget(self.lista)

        botones = QHBoxLayout()
        boton_vincular = QPushButton("Vincular")
        boton_vincular.setObjectName("botonAcento")
        boton_vincular.clicked.connect(self._elegir)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        botones.addWidget(boton_vincular)
        botones.addWidget(boton_cancelar)
        botones.addStretch()
        layout.addLayout(botones)

    def _elegir(self):
        filas = [self.lista.row(i) for i in self.lista.selectedItems()]
        if not filas:
            QMessageBox.information(self, "Vincular existente", "Elegí al menos una de la lista.")
            return
        self.on_elegir([self.candidatas[i] for i in filas])
        self.accept()


class DialogoUnidad(QDialog):
    def __init__(self, parent, edificio, unidad=None, on_guardar=None):
        super().__init__(parent)
        self.edificio = edificio
        self.unidad = unidad  # dict si es edición, None si es alta
        self.on_guardar = on_guardar
        self._items = []            # lo que muestra la lista de cocheras/bauleras (ver _agregar_item)
        self._a_desvincular = []    # ids de asociadas a soltar del depto al guardar
        self._autoinquilino = ""    # último inquilino copiado automáticamente desde el depto

        self.setWindowTitle("Editar unidad" if unidad else "Nueva unidad")
        self.setModal(True)

        todas = database.get_unidades_por_edificio(edificio)
        self._por_id = indice_por_id(todas)
        propio_id = unidad["id"] if unidad else None
        self._ids_deptos = {NINGUNO: ""}
        for d, _nivel in ordenar_con_asociadas(todas):
            if normalizar_tipo(d["tipo"]) != DEPTO or d["id"] == propio_id:
                continue
            base = etiqueta_unidad(d) + (f" — {d['inquilino']}" if d["inquilino"] else "")
            texto, n = base, 2
            while texto in self._ids_deptos:
                texto, n = f"{base} #{n}", n + 1
            self._ids_deptos[texto] = d["id"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        titulo = QLabel(f"Edificio: {edificio}")
        titulo.setStyleSheet(f"color: {COLOR_TEXTO}; font-weight: 700; background: transparent;")
        layout.addWidget(titulo)

        self._grilla = QGridLayout()
        self._grilla.setHorizontalSpacing(10)
        self._grilla.setVerticalSpacing(6)
        layout.addLayout(self._grilla)

        tipo_actual = normalizar_tipo(unidad["tipo"]) if unidad else DEPTO
        self.campo_celda = QLineEdit(unidad["celda"] if unidad else "")
        self.campo_piso = QLineEdit(unidad["piso"] if unidad else "")
        self.campo_unidad = QLineEdit(unidad["unidad"] if unidad else "")
        self.campo_uf = QLineEdit(unidad["uf"] if unidad else "")
        self.campo_dueno = QLineEdit(unidad["dueno"] if unidad else "")
        self.campo_inquilino = QLineEdit(unidad["inquilino"] if unidad else "")
        self.campo_importe = QLineEdit(unidad["importe"] if unidad else "0")
        depto_actual = next((t for t, i in self._ids_deptos.items() if unidad and i and i == unidad["depto_id"]), NINGUNO)

        self._grilla.addWidget(QLabel("Celda en la planilla (ej. B12):"), 0, 0)
        self._grilla.addWidget(self.campo_celda, 0, 1)

        self._grilla.addWidget(QLabel("Tipo de unidad:"), 1, 0)
        self.combo_tipo = QComboBox()
        self.combo_tipo.addItems([nombre_tipo(t) for t in TIPOS])
        self.combo_tipo.setCurrentText(nombre_tipo(tipo_actual))
        _estilizar_combo(self.combo_tipo)
        self.combo_tipo.currentIndexChanged.connect(self._actualizar_tipo)
        self._grilla.addWidget(self.combo_tipo, 1, 1)

        self.lbl_piso = QLabel("")
        self._grilla.addWidget(self.lbl_piso, 2, 0)
        self._grilla.addWidget(self.campo_piso, 2, 1)
        self.lbl_unidad = QLabel("")
        self._grilla.addWidget(self.lbl_unidad, 3, 0)
        self._grilla.addWidget(self.campo_unidad, 3, 1)
        self._grilla.addWidget(QLabel("Unidad funcional (UF):"), 4, 0)
        self._grilla.addWidget(self.campo_uf, 4, 1)

        self.lbl_depto = QLabel("Pertenece al depto:")
        self._grilla.addWidget(self.lbl_depto, 5, 0)
        self.combo_depto = QComboBox()
        self.combo_depto.addItems(list(self._ids_deptos))
        self.combo_depto.setCurrentText(depto_actual)
        _estilizar_combo(self.combo_depto)
        self.combo_depto.currentIndexChanged.connect(self._al_elegir_depto)
        self._grilla.addWidget(self.combo_depto, 5, 1)

        self._grilla.addWidget(QLabel("Dueño:"), 6, 0)
        self._grilla.addWidget(self.campo_dueno, 6, 1)
        self._grilla.addWidget(QLabel("Inquilino:"), 7, 0)
        self._grilla.addWidget(self.campo_inquilino, 7, 1)
        self.lbl_importe = QLabel("Importe:")
        self._grilla.addWidget(self.lbl_importe, 8, 0)
        self._grilla.addWidget(self.campo_importe, 8, 1)
        if self.unidad:   # al editar, el importe no se toca acá: se carga desde la planilla de pagos
            self.lbl_importe.hide()
            self.campo_importe.hide()

        # --- depto: lista de cocheras/bauleras asociadas ---
        self.frame_asociadas = QWidget()
        frame_layout = QVBoxLayout(self.frame_asociadas)
        frame_layout.setContentsMargins(0, 8, 0, 0)
        frame_layout.setSpacing(4)
        titulo_asoc = QLabel("Cocheras y bauleras de este depto:")
        titulo_asoc.setStyleSheet(f"color: {COLOR_TEXTO}; font-weight: 700; background: transparent;")
        frame_layout.addWidget(titulo_asoc)
        nota_asoc = QLabel("Elegí una y abajo cómo paga: aparte, junto con el depto (un solo recibo) "
                           "o incluida en su total.\nQuitar la suelta del depto, no la borra.")
        nota_asoc.setStyleSheet(f"color: {COLOR_TEXTO_SUAVE}; font-size: 10px; background: transparent;")
        nota_asoc.setWordWrap(True)
        frame_layout.addWidget(nota_asoc)
        self.lista_asociadas = QListWidget()
        self.lista_asociadas.setObjectName("listaSimple")
        self.lista_asociadas.setFixedHeight(90)
        self.lista_asociadas.currentRowChanged.connect(lambda _f: self._mostrar_modo_item())
        frame_layout.addWidget(self.lista_asociadas)
        if unidad:
            for h, n in ordenar_con_asociadas(todas):
                if n == 1 and h["depto_id"] == unidad["id"]:
                    self._agregar_item("actual", etiqueta_unidad(h).split(" (")[0], modo=modo_pago(h), id=h["id"])
        barra = QHBoxLayout()
        boton_vincular = QPushButton("Vincular existente")
        boton_vincular.clicked.connect(self._vincular_existente)
        boton_cochera = QPushButton("+ Cochera nueva")
        boton_cochera.clicked.connect(lambda: self._nueva_asociada(COCHERA))
        boton_baulera = QPushButton("+ Baulera nueva")
        boton_baulera.clicked.connect(lambda: self._nueva_asociada(BAULERA))
        boton_quitar = QPushButton("Quitar")
        boton_quitar.clicked.connect(self._quitar_asociada)
        barra.addWidget(boton_vincular)
        barra.addWidget(boton_cochera)
        barra.addWidget(boton_baulera)
        barra.addWidget(boton_quitar)
        barra.addStretch()
        frame_layout.addLayout(barra)
        fila_modo = QHBoxLayout()
        fila_modo.addWidget(QLabel("Cómo paga la elegida:"))
        self.combo_modo_item = QComboBox()
        self.combo_modo_item.addItem("")
        self.combo_modo_item.addItems([largo for _c, largo, _k in MODOS_PAGO])
        _estilizar_combo(self.combo_modo_item)
        self.combo_modo_item.currentIndexChanged.connect(self._fijar_modo_item)
        fila_modo.addWidget(self.combo_modo_item)
        frame_layout.addLayout(fila_modo)
        layout.addWidget(self.frame_asociadas)

        # Cochera/baulera: "cómo paga" propio (ocupa el lugar de la lista, que solo se ve en un depto)
        self.fila_modo_asoc = QWidget()
        fila_modo_asoc_layout = QHBoxLayout(self.fila_modo_asoc)
        fila_modo_asoc_layout.setContentsMargins(0, 8, 0, 0)
        fila_modo_asoc_layout.addWidget(QLabel("Cómo paga:"))
        self.combo_modo_asoc = QComboBox()
        self.combo_modo_asoc.addItems([largo for _c, largo, _k in MODOS_PAGO])
        self.combo_modo_asoc.setCurrentText(_TEXTO_MODO[modo_pago(unidad) if unidad else MODO_APARTE])
        _estilizar_combo(self.combo_modo_asoc)
        fila_modo_asoc_layout.addWidget(self.combo_modo_asoc)
        fila_modo_asoc_layout.addStretch()
        layout.addWidget(self.fila_modo_asoc)

        botones = QHBoxLayout()
        boton_guardar = QPushButton("Guardar")
        boton_guardar.setObjectName("botonAcento")
        boton_guardar.clicked.connect(self._guardar)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        botones.addWidget(boton_guardar)
        botones.addWidget(boton_cancelar)
        if unidad:
            boton_borrar = QPushButton("Borrar unidad")
            boton_borrar.setStyleSheet("background-color: #dc2626; color: white; border: none;")
            boton_borrar.clicked.connect(self._borrar)
            botones.addSpacing(18)
            botones.addWidget(boton_borrar)
        botones.addStretch()
        layout.addLayout(botones)

        self._actualizar_tipo()

    def _tipo(self):
        indice = self.combo_tipo.currentIndex()
        return TIPOS[indice] if indice >= 0 else DEPTO

    def _actualizar_tipo(self):
        tipo = self._tipo()
        self.lbl_piso.setText("Piso (ej: PB, 1°):" if tipo == DEPTO else "Piso (opcional):")
        self.lbl_unidad.setText({
            DEPTO: "Letra o número del depto:", LOCAL: "Letra o número del local:",
            COCHERA: "Número de cochera:", BAULERA: "Número de baulera:",
        }[tipo])
        asociable = tipo in TIPOS_ASOCIABLES
        self.lbl_depto.setVisible(asociable)
        self.combo_depto.setVisible(asociable)
        self.frame_asociadas.setVisible(tipo == DEPTO)
        self.fila_modo_asoc.setVisible(asociable)
        self._actualizar_junto_asoc()

    def _actualizar_junto_asoc(self):
        con_depto = bool(self._ids_deptos.get(self.combo_depto.currentText(), ""))
        self.combo_modo_asoc.setEnabled(con_depto)
        if not con_depto:
            self.combo_modo_asoc.setCurrentText(_TEXTO_MODO[MODO_APARTE])

    def _al_elegir_depto(self):
        self._actualizar_junto_asoc()
        depto = self._por_id.get(self._ids_deptos.get(self.combo_depto.currentText(), ""))
        if not depto:
            return
        actual = self.campo_inquilino.text().strip()
        if not actual or actual == self._autoinquilino:
            self.campo_inquilino.setText(depto["inquilino"])
        self._autoinquilino = depto["inquilino"]

    @staticmethod
    def _texto_item(it):
        estado = {"actual": "", "vincular": "  (existente)", "nueva": "  (nueva)"}[it["estado"]]
        return f"{it['nombre']}{estado}   ·   {_CORTO_MODO[it['modo']]}"

    def _agregar_item(self, estado, nombre, modo=MODO_APARTE, **extra):
        """
        estado: 'actual' (ya es del depto), 'vincular' (existente que se suma) o 'nueva' (se crea al guardar).
        modo: cómo paga (MODO_APARTE / MODO_JUNTO / MODO_TOTAL); 'modo_orig' es cómo estaba guardada.
        """
        self._items.append(dict(extra, estado=estado, nombre=nombre, modo=modo, modo_orig=modo))
        self.lista_asociadas.addItem(self._texto_item(self._items[-1]))

    def _mostrar_modo_item(self):
        fila = self.lista_asociadas.currentRow()
        self.combo_modo_item.blockSignals(True)
        self.combo_modo_item.setCurrentText(_TEXTO_MODO[self._items[fila]["modo"]] if fila >= 0 else "")
        self.combo_modo_item.blockSignals(False)

    def _fijar_modo_item(self):
        """Cambia cómo paga la cochera/baulera elegida en la lista (texto largo del combo)."""
        texto = self.combo_modo_item.currentText()
        if not texto:
            return
        fila = self.lista_asociadas.currentRow()
        if fila < 0:
            QMessageBox.information(self, "Cómo paga", "Elegí primero la cochera o baulera de la lista.")
            self.combo_modo_item.setCurrentText("")
            return
        self._items[fila]["modo"] = _CODIGO_MODO[texto]
        self.lista_asociadas.item(fila).setText(self._texto_item(self._items[fila]))

    def _nueva_asociada(self, tipo):
        DialogoAsociada(self, tipo, self._agregar_asociada).show()

    def _agregar_asociada(self, datos):
        nombre = " ".join(p for p in (nombre_tipo(datos["tipo"]), datos["piso"], datos["unidad"]) if p)
        self._agregar_item("nueva", f"{nombre} — {format_currency_ar(datos['importe'])}",
                           modo=datos.get("paga_junto") or MODO_APARTE, datos=datos)

    def _vincular_existente(self):
        en_lista = {it["id"] for it in self._items if "id" in it}
        propio = self.unidad["id"] if self.unidad else None
        candidatas = [
            (u["id"], etiqueta_unidad(u)) for u, _n in ordenar_con_asociadas(database.get_unidades_por_edificio(self.edificio))
            if normalizar_tipo(u["tipo"]) in TIPOS_ASOCIABLES and u["id"] not in en_lista
            and (not u["depto_id"] or u["id"] in self._a_desvincular) and u["id"] != propio
        ]
        if not candidatas:
            QMessageBox.information(
                self, "Vincular existente",
                "No hay cocheras ni bauleras sueltas en este edificio.\n"
                "Podés crear una con '+ Cochera nueva' o '+ Baulera nueva'.")
            return
        DialogoElegirAsociada(self, candidatas, self._agregar_vinculadas).show()

    def _agregar_vinculadas(self, elegidas):
        for uid, nombre in elegidas:
            if uid in self._a_desvincular:      # la había soltado hace un rato: vuelve a quedar como estaba
                self._a_desvincular.remove(uid)
                self._agregar_item("actual", nombre, modo=modo_pago(self._por_id[uid]), id=uid)
            else:
                self._agregar_item("vincular", nombre, id=uid)

    def _quitar_asociada(self):
        fila = self.lista_asociadas.currentRow()
        if fila < 0:
            QMessageBox.information(self, "Quitar", "Elegí primero la cochera o baulera de la lista.")
            return
        item = self._items.pop(fila)
        self.lista_asociadas.takeItem(fila)
        if item["estado"] == "actual":
            self._a_desvincular.append(item["id"])
        self._mostrar_modo_item()

    def _borrar(self):
        def al_borrar():
            if self.on_guardar:
                self.on_guardar()
            self.accept()
        confirmar_y_borrar(self, self.unidad["id"], on_borrado=al_borrar)

    def _guardar(self):
        tipo = self._tipo()
        piso = self.campo_piso.text().strip()
        unidad_txt = self.campo_unidad.text().strip()
        inquilino = self.campo_inquilino.text().strip()
        importe = parse_importe(self.campo_importe.text())

        if tipo == DEPTO and (not piso or not unidad_txt):
            QMessageBox.warning(self, "Datos incompletos", "Completá al menos 'Piso' y la letra o número del depto.")
            return
        if not unidad_txt:
            QMessageBox.warning(self, "Datos incompletos", "Completá la letra o número de la unidad.")
            return

        try:
            celda = pagos.normalizar_celda(self.campo_celda.text())
        except ValueError as e:
            QMessageBox.warning(self, "Celda inválida", str(e))
            return

        depto_id = self._ids_deptos.get(self.combo_depto.currentText(), "") if tipo in TIPOS_ASOCIABLES else ""
        items = self._items if tipo == DEPTO else []
        asociadas = [dict(it["datos"], inquilino=inquilino, paga_junto=it["modo"]) for it in items if it["estado"] == "nueva"]
        a_vincular = [it for it in items if it["estado"] == "vincular"]
        a_cambiar = [it for it in items if it["estado"] == "actual" and it["modo"] != it["modo_orig"]]
        uf, dueno = self.campo_uf.text().strip(), self.campo_dueno.text().strip()
        # solo una cochera/baulera de un depto tiene "cómo paga"; una incluida en el total no lleva celda propia
        modo = _CODIGO_MODO[self.combo_modo_asoc.currentText()] if depto_id else MODO_APARTE
        if modo == MODO_TOTAL:
            celda = ""

        nuevas_celdas = ([celda] if celda else []) + [a["celda"] for a in asociadas if a.get("celda")]
        if nuevas_celdas and not confirmar_modo_celdas(self, self.edificio):
            return

        def guardar_de_verdad():
            try:
                if self.unidad:
                    database.update_unidad(
                        self.unidad["id"],
                        piso=piso, tipo=tipo, unidad=unidad_txt, uf=uf, dueno=dueno,
                        inquilino=inquilino, depto_id=depto_id,
                        paga_junto=modo, celda=celda,
                    )
                    depto_propio = self.unidad["id"]
                    for asociada_id in self._a_desvincular:
                        database.update_unidad(asociada_id, depto_id="")
                    if asociadas:
                        database.add_asociadas(depto_propio, asociadas)
                else:
                    depto_propio = database.add_unidad(self.edificio, piso, tipo, unidad_txt, inquilino, importe,
                                                       depto_id=depto_id, asociadas=asociadas, uf=uf, dueno=dueno,
                                                       paga_junto=modo, celda=celda)
                for it in a_vincular:
                    campos = {"depto_id": depto_propio, "paga_junto": it["modo"]}
                    if not self._por_id[it["id"]]["inquilino"]:
                        campos["inquilino"] = inquilino
                    database.update_unidad(it["id"], **campos)
                for it in a_cambiar:
                    database.update_unidad(it["id"], paga_junto=it["modo"])

                mostrar_avisos(self)
                if self.on_guardar:
                    self.on_guardar()
                self.accept()
            except Exception as e:
                manejar_error("No se pudo guardar la unidad", e, self)

        requerir_maestro(self, guardar_de_verdad, motivo="guardar una unidad")


# ===========================================================================
# Diálogo: alta de edificio
# ===========================================================================

class DialogoEdificioNuevo(QDialog):
    def __init__(self, parent, on_guardar=None):
        super().__init__(parent)
        self.on_guardar = on_guardar
        self.setWindowTitle("Nuevo edificio")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Nombre del edificio:"))
        self.campo_nombre = QLineEdit()
        layout.addWidget(self.campo_nombre)
        self.campo_nombre.setFocus()

        botones = QHBoxLayout()
        boton_crear = QPushButton("Crear")
        boton_crear.setObjectName("botonAcento")
        boton_crear.clicked.connect(self._guardar)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        botones.addWidget(boton_crear)
        botones.addWidget(boton_cancelar)
        botones.addStretch()
        layout.addLayout(botones)

    def _guardar(self):
        nombre = self.campo_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Datos incompletos", "Ingresá un nombre de edificio.")
            return

        def guardar_de_verdad():
            try:
                database.add_edificio(nombre)
                mostrar_avisos(self)
                if self.on_guardar:
                    self.on_guardar(nombre)
                self.accept()
            except Exception as e:
                manejar_error("No se pudo crear el edificio", e, self)

        requerir_maestro(self, guardar_de_verdad, motivo="crear un edificio")


# ===========================================================================
# Diálogo: datos del consorcio (nombre, dirección, CUIT y administrador)
# ===========================================================================

class DialogoDatosConsorcio(QDialog):
    def __init__(self, parent, nombre_edificio, on_guardar=None):
        super().__init__(parent)
        self.nombre_original = nombre_edificio
        self.on_guardar = on_guardar
        datos = database.get_edificio(nombre_edificio) or {}

        self.setWindowTitle("Datos del consorcio")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        grupos = [
            ("Consorcio", [
                ("nombre", "Nombre:"), ("direccion", "Dirección:"),
                ("localidad", "Localidad:"), ("cuit", "CUIT del consorcio:"),
            ]),
            ("Administrador", [
                ("admin_nombre", "Nombre del administrador:"),
                ("admin_cuit", "CUIT del administrador:"), ("admin_rpac", "RPAC:"),
            ]),
        ]
        self.campos = {}
        for titulo, campos in grupos:
            etiqueta_grupo = QLabel(titulo)
            etiqueta_grupo.setStyleSheet(f"color: {COLOR_ACENTO}; font-weight: 700; background: transparent;")
            layout.addWidget(etiqueta_grupo)
            grilla = QGridLayout()
            grilla.setHorizontalSpacing(10)
            grilla.setVerticalSpacing(6)
            for fila, (clave, etiqueta) in enumerate(campos):
                grilla.addWidget(QLabel(etiqueta), fila, 0)
                campo = QLineEdit(datos.get(clave, ""))
                grilla.addWidget(campo, fila, 1)
                self.campos[clave] = campo
            layout.addLayout(grilla)

        nota = QLabel("Si cambiás el nombre, se actualiza en las unidades, el historial, la numeración,\n"
                      "la carpeta de recibos y la planilla de pagos.")
        nota.setStyleSheet(f"color: {COLOR_TEXTO_SUAVE}; font-size: 10px; background: transparent;")
        layout.addWidget(nota)

        botones = QHBoxLayout()
        boton_guardar = QPushButton("Guardar")
        boton_guardar.setObjectName("botonAcento")
        boton_guardar.clicked.connect(self._guardar)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        botones.addWidget(boton_guardar)
        botones.addWidget(boton_cancelar)
        botones.addStretch()
        layout.addLayout(botones)

    def _guardar(self):
        datos = {clave: campo.text().strip() for clave, campo in self.campos.items()}
        if not datos["nombre"]:
            QMessageBox.warning(self, "Datos incompletos", "El nombre del consorcio no puede quedar vacío.")
            return
        try:
            datos["cuit"] = normalizar_cuit(datos["cuit"])
            datos["admin_cuit"] = normalizar_cuit(datos["admin_cuit"])
        except ValueError as e:
            QMessageBox.warning(self, "CUIT inválido", str(e))
            return

        if datos["nombre"] != self.nombre_original:
            confirmado = QMessageBox.question(
                self, "Cambiar el nombre del consorcio",
                f"Vas a cambiar el nombre de «{self.nombre_original}» a «{datos['nombre']}».\n\n"
                "Se actualiza en las unidades, el historial, la numeración de recibos, la carpeta de "
                "recibos y la planilla de pagos.\nCerrá la planilla de Excel y los PDF de este consorcio "
                "si están abiertos.\n\n¿Continuar?",
            )
            if confirmado != QMessageBox.Yes:
                return

        def guardar_de_verdad():
            try:
                nombre_final = database.update_edificio(self.nombre_original, **datos)
            except PermissionError:
                QMessageBox.warning(
                    self, "Archivos abiertos",
                    "No se pudo cambiar el nombre porque hay archivos abiertos de este consorcio "
                    "(la planilla de pagos en Excel o algún PDF de sus recibos).\n\n"
                    "Cerralos y probá de nuevo. No se modificó nada.")
                return
            except ValueError as e:
                QMessageBox.warning(self, "No se pudo guardar", str(e))
                return
            except Exception as e:
                manejar_error("No se pudieron guardar los datos del consorcio", e, self)
                return

            mostrar_avisos(self)
            if self.on_guardar:
                self.on_guardar(nombre_final)
            self.accept()

        requerir_maestro(self, guardar_de_verdad, motivo="editar los datos del consorcio")


# ===========================================================================
# Diálogo: borrar un edificio (se archiva, no se pierde)
# ===========================================================================

class DialogoBorrarEdificio(QDialog):
    """Muestra qué tiene el edificio y pide escribir su nombre para confirmar el borrado."""

    def __init__(self, parent, edificio, on_borrado=None):
        super().__init__(parent)
        self.edificio = edificio
        self.on_borrado = on_borrado
        self.setWindowTitle("Borrar edificio")
        self.setModal(True)

        r = database.resumen_edificio(edificio)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        titulo = QLabel(f"Borrar «{edificio}»")
        titulo.setStyleSheet("color: #f87171; font-weight: 700; background: transparent;")
        layout.addWidget(titulo)

        detalle = QLabel(
            f"Tiene {r['unidades']} unidad(es), {r['recibos']} recibo(s) en el historial y "
            f"{r['pdfs']} PDF.\n\nDeja de aparecer en la app. Sus unidades, historial, numeración, carpeta de "
            "recibos y planilla de pagos NO se pierden: se guardan en datos/edificios_borrados/ para "
            "poder recuperarlos a mano.\n\nCerrá la planilla de Excel y los PDF de este edificio si están abiertos.")
        detalle.setWordWrap(True)
        layout.addWidget(detalle)

        layout.addWidget(QLabel("Para confirmar, escribí el nombre del edificio:"))
        self.campo_nombre = QLineEdit()
        self.campo_nombre.textChanged.connect(self._validar)
        layout.addWidget(self.campo_nombre)
        self.campo_nombre.setFocus()

        botones = QHBoxLayout()
        self.boton_borrar = QPushButton("Borrar edificio")
        self.boton_borrar.setStyleSheet("background-color: #dc2626; color: white; border: none;")
        self.boton_borrar.setEnabled(False)
        self.boton_borrar.clicked.connect(self._borrar)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        botones.addWidget(self.boton_borrar)
        botones.addWidget(boton_cancelar)
        botones.addStretch()
        layout.addLayout(botones)

    def _validar(self):
        self.boton_borrar.setEnabled(self.campo_nombre.text().strip() == self.edificio)

    def _borrar(self):
        if self.campo_nombre.text().strip() != self.edificio:
            return

        def borrar_de_verdad():
            try:
                destino = database.delete_edificio(self.edificio)
            except PermissionError:
                QMessageBox.warning(
                    self, "Archivos abiertos",
                    "No se pudo borrar porque hay archivos abiertos de este edificio (la planilla de pagos en "
                    "Excel o algún PDF de sus recibos).\n\nCerralos y probá de nuevo. No se modificó nada.")
                return
            except ValueError as e:
                QMessageBox.warning(self, "No se pudo borrar", str(e))
                return
            except Exception as e:
                manejar_error("No se pudo borrar el edificio", e, self)
                return
            self.accept()
            if self.on_borrado:
                self.on_borrado(destino)

        requerir_maestro(self, borrar_de_verdad, motivo="borrar un edificio")


# ===========================================================================
# Ventana: asignar la celda de la planilla de pagos a cada unidad
# ===========================================================================

SIN_CELDA = "Sin celda"


class VentanaAsignarCeldas(QDialog):
    """Una fila por unidad del edificio con la celda donde figura en la planilla de pagos."""

    def __init__(self, parent, edificio, on_guardar=None):
        super().__init__(parent)
        self.edificio = edificio
        self.on_guardar = on_guardar
        self.setWindowTitle("Asignar celdas de la planilla")
        self.setModal(True)
        self.resize(520, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        titulo = QLabel(f"Edificio: {edificio}")
        titulo.setStyleSheet(f"color: {COLOR_TEXTO}; font-weight: 700; background: transparent;")
        layout.addWidget(titulo)

        nota = QLabel(
            "Escribí, para cada unidad, la celda donde está su nombre en la planilla (ej. B12).\n"
            "Los montos se leen de las 4 celdas de la derecha: Total a pagar, Monto deuda, Monto pagado y Tipo pago.\n"
            "Dejala vacía si la unidad no figura.")
        nota.setStyleSheet(f"color: {COLOR_TEXTO_SUAVE}; font-size: 10px; background: transparent;")
        nota.setWordWrap(True)
        layout.addWidget(nota)

        tabla = QTableWidget(0, 2)
        tabla.setObjectName("listaSimple")
        tabla.horizontalHeader().hide()
        tabla.verticalHeader().hide()
        tabla.verticalHeader().setDefaultSectionSize(36)
        tabla.setShowGrid(False)
        tabla.setEditTriggers(QAbstractItemView.AllEditTriggers)
        tabla.setSelectionMode(QAbstractItemView.NoSelection)
        layout.addWidget(tabla, 1)

        todas = database.get_unidades_por_edificio(edificio)
        por_id = indice_por_id(todas)
        self._antes = {u["id"]: u["celda"] for u in todas}
        filas = [(u, n) for u, n in ordenar_con_asociadas(todas) if not incluida_en_total(u)]
        tabla.setRowCount(len(filas))
        self._campos_celda = {}
        for fila, (u, nivel) in enumerate(filas):
            texto = ("      " if nivel else "") + f"{nombre_tipo(normalizar_tipo(u['tipo']))} — {etiqueta_unidad(u, por_id)}"
            item = QTableWidgetItem(texto)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            tabla.setItem(fila, 0, item)
            campo = QLineEdit(u["celda"])
            tabla.setCellWidget(fila, 1, campo)
            self._campos_celda[u["id"]] = campo
        tabla.resizeColumnToContents(0)
        tabla.resizeRowsToContents()
        if not filas:
            layout.addWidget(QLabel("Este edificio todavía no tiene unidades."))

        botones = QHBoxLayout()
        boton_guardar = QPushButton("Guardar")
        boton_guardar.setObjectName("botonAcento")
        boton_guardar.clicked.connect(self._guardar)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        botones.addWidget(boton_guardar)
        botones.addWidget(boton_cancelar)
        botones.addStretch()
        layout.addLayout(botones)

    def _guardar(self):
        try:
            celdas = {uid: pagos.normalizar_celda(campo.text()) for uid, campo in self._campos_celda.items()}
        except ValueError as e:
            QMessageBox.warning(self, "Celda inválida", str(e))
            return
        habia, habra = any(self._antes.values()), any(celdas.values())
        if habra and not habia and not confirmar_modo_celdas(self, self.edificio):
            return
        if habia and not habra:
            confirmado = QMessageBox.question(
                self, "Volver a la planilla automática",
                "Sin ninguna celda asignada, la app vuelve a armar su propia planilla de pagos en ese archivo "
                "(antes guarda una copia de tu Excel con el nombre «..._respaldo_...»).\n\n¿Continuar?",
            )
            if confirmado != QMessageBox.Yes:
                return

        def guardar_de_verdad():
            try:
                database.set_celdas(self.edificio, celdas)
            except ValueError as e:
                QMessageBox.warning(self, "No se pudo guardar", str(e))
                return
            except Exception as e:
                manejar_error("No se pudieron guardar las celdas", e, self)
                return
            if habia and not habra:
                try:
                    database.sincronizar_pagos(self.edificio, reemplazar_ajena=True)
                except PermissionError:
                    QMessageBox.warning(
                        self, "Planilla abierta",
                        "Se quitaron las celdas, pero la planilla está abierta en Excel y no se pudo rearmar.\n"
                        "Cerrala: se rearma sola la próxima vez que se guarde algo.")
                except Exception as e:
                    manejar_error("No se pudo rearmar la planilla de pagos", e, self)
            if self.on_guardar:
                self.on_guardar()
            self.accept()

        requerir_maestro(self, guardar_de_verdad, motivo="asignar celdas de la planilla")


# ===========================================================================
# Ventana: administración de edificios / unidades
# ===========================================================================

COLUMNAS_ADMIN = ("piso", "tipo", "unidad", "uf", "depto", "dueno", "inquilino", "importe", "celda")
TITULOS_ADMIN = {"piso": "PISO", "tipo": "TIPO", "unidad": "LETRA/N°", "uf": "UF", "depto": "PERTENECE A",
                 "dueno": "DUEÑO", "inquilino": "INQUILINO", "importe": "IMPORTE", "celda": "CELDA"}
ANCHOS_ADMIN = {"piso": 60, "tipo": 80, "unidad": 80, "uf": 50, "depto": 110, "dueno": 130, "inquilino": 130,
                "importe": 100, "celda": 70}


class VentanaAdministracion(QDialog):
    def __init__(self, parent, edificio_inicial, on_cambios=None):
        super().__init__(parent)
        self.on_cambios = on_cambios
        self.setWindowTitle("Administrar edificios y unidades")
        self.setModal(True)
        self.resize(1300, 560)

        layout_externo = QVBoxLayout(self)
        layout_externo.setContentsMargins(0, 0, 0, 0)
        layout_externo.setSpacing(0)

        cuerpo = QHBoxLayout()
        cuerpo.setContentsMargins(0, 0, 0, 0)
        cuerpo.setSpacing(0)
        layout_externo.addLayout(cuerpo, 1)

        self.lista_edificios = _crear_sidebar_edificios(
            cuerpo, database.get_nombres_edificios(), self._recargar)

        contenedor = QWidget()
        layout = QVBoxLayout(contenedor)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        cuerpo.addWidget(contenedor, 1)

        top = QHBoxLayout()
        top.setSpacing(8)
        boton_datos = QPushButton("Datos del consorcio")
        boton_datos.setObjectName("botonAcento")
        boton_datos.clicked.connect(self._datos_consorcio)
        boton_nuevo_ed = QPushButton("+ Nuevo edificio")
        boton_nuevo_ed.clicked.connect(self._nuevo_edificio)
        boton_borrar_ed = QPushButton("Borrar edificio")
        boton_borrar_ed.setStyleSheet("background-color: #dc2626; color: white; border: none;")
        boton_borrar_ed.clicked.connect(self._borrar_edificio)
        boton_nueva_un = QPushButton("+ Nueva unidad")
        boton_nueva_un.clicked.connect(self._nueva_unidad)
        boton_celdas = QPushButton("Asignar celdas")
        boton_celdas.clicked.connect(self._asignar_celdas)
        boton_carpeta = QPushButton("Abrir carpeta del edificio")
        boton_carpeta.clicked.connect(self._abrir_carpeta)
        for b in (boton_datos, boton_nuevo_ed, boton_borrar_ed, boton_nueva_un, boton_celdas, boton_carpeta):
            top.addWidget(b)
        top.addStretch()
        layout.addLayout(top)

        self.tabla = QTableWidget(0, len(COLUMNAS_ADMIN))
        self.tabla.setHorizontalHeaderLabels([TITULOS_ADMIN[c] for c in COLUMNAS_ADMIN])
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setShowGrid(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(30)
        self.tabla.horizontalHeader().setFixedHeight(32)
        for col, clave in enumerate(COLUMNAS_ADMIN):
            self.tabla.setColumnWidth(col, ANCHOS_ADMIN[clave])
        for clave in ("dueno", "inquilino"):
            self.tabla.horizontalHeader().setSectionResizeMode(COLUMNAS_ADMIN.index(clave), QHeaderView.Stretch)
        self.tabla.doubleClicked.connect(lambda _i: self._editar_seleccionada())
        layout.addWidget(self.tabla, 1)

        pie = QHBoxLayout()
        boton_editar = QPushButton("Editar unidad seleccionada")
        boton_editar.clicked.connect(self._editar_seleccionada)
        boton_borrar_un = QPushButton("Borrar unidad seleccionada")
        boton_borrar_un.setStyleSheet("background-color: #dc2626; color: white; border: none;")
        boton_borrar_un.clicked.connect(self._borrar_seleccionada)
        nota = QLabel("(doble clic sobre una fila también la edita)")
        nota.setStyleSheet(f"color: {COLOR_TEXTO_SUAVE}; font-size: 10px; background: transparent;")
        pie.addWidget(boton_editar)
        pie.addWidget(boton_borrar_un)
        pie.addWidget(nota)
        pie.addStretch()
        layout.addLayout(pie)

        self._unidades_por_fila = {}
        coincidencias = self.lista_edificios.findItems(edificio_inicial, Qt.MatchExactly)
        self.lista_edificios.blockSignals(True)
        if coincidencias:
            self.lista_edificios.setCurrentItem(coincidencias[0])
        elif self.lista_edificios.count():
            self.lista_edificios.setCurrentRow(0)
        self.lista_edificios.blockSignals(False)
        self._recargar()

    def _edificio_actual(self):
        item = self.lista_edificios.currentItem()
        return item.text() if item else ""

    def _recargar(self):
        self.tabla.setRowCount(0)
        self._unidades_por_fila = {}

        edificio = self._edificio_actual()
        todas = database.get_unidades_por_edificio(edificio)
        por_id = indice_por_id(todas)
        filas = ordenar_con_asociadas(todas)
        self.tabla.setRowCount(len(filas))
        for fila, (u, nivel) in enumerate(filas):
            importe_fmt = format_currency_ar(parse_importe(u["importe"]))
            depto = depto_de(u, por_id)
            valores = {
                "piso": u["piso"], "tipo": normalizar_tipo(u["tipo"]),
                "unidad": ("↳ " if nivel else "") + u["unidad"], "uf": u["uf"],
                "depto": etiqueta_unidad(depto) if depto else "", "dueno": u["dueno"],
                "inquilino": u["inquilino"], "importe": importe_fmt, "celda": u["celda"],
            }
            for col, clave in enumerate(COLUMNAS_ADMIN):
                item = QTableWidgetItem(valores[clave])
                item.setTextAlignment(Qt.AlignCenter if clave not in ("dueno", "inquilino") else Qt.AlignVCenter)
                self.tabla.setItem(fila, col, item)
            self._unidades_por_fila[fila] = u

        if self.on_cambios:
            self.on_cambios(edificio)

    def _seleccionada(self):
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._unidades_por_fila.get(filas[0].row())

    def _asignar_celdas(self):
        edificio = self._edificio_actual()
        if not edificio:
            QMessageBox.warning(self, "Atención", "Primero seleccioná o creá un edificio.")
            return
        VentanaAsignarCeldas(self, edificio, on_guardar=self._recargar).show()

    def _datos_consorcio(self):
        edificio = self._edificio_actual()
        if not edificio:
            QMessageBox.warning(self, "Atención", "Primero seleccioná o creá un edificio.")
            return

        def al_guardar(nombre_nuevo):
            self._refrescar_lista_edificios(nombre_nuevo)

        DialogoDatosConsorcio(self, edificio, on_guardar=al_guardar).show()

    def _borrar_seleccionada(self):
        unidad = self._seleccionada()
        if not unidad:
            QMessageBox.information(self, "Borrar unidad", "Seleccioná primero una unidad de la lista.")
            return
        confirmar_y_borrar(self, unidad["id"], on_borrado=self._recargar)

    def _nuevo_edificio(self):
        def al_guardar(nombre):
            self._refrescar_lista_edificios(nombre)
        DialogoEdificioNuevo(self, on_guardar=al_guardar).show()

    def _refrescar_lista_edificios(self, nombre_a_elegir):
        self.lista_edificios.blockSignals(True)
        self.lista_edificios.clear()
        self.lista_edificios.addItems(database.get_nombres_edificios())
        coincidencias = self.lista_edificios.findItems(nombre_a_elegir, Qt.MatchExactly)
        if coincidencias:
            self.lista_edificios.setCurrentItem(coincidencias[0])
        self.lista_edificios.blockSignals(False)
        self._recargar()

    def _borrar_edificio(self):
        edificio = self._edificio_actual()
        if not edificio:
            QMessageBox.warning(self, "Atención", "Primero seleccioná un edificio.")
            return

        def al_borrar(destino):
            self.lista_edificios.blockSignals(True)
            self.lista_edificios.clear()
            self.lista_edificios.addItems(database.get_nombres_edificios())
            if self.lista_edificios.count():
                self.lista_edificios.setCurrentRow(0)
            self.lista_edificios.blockSignals(False)
            self._recargar()
            QMessageBox.information(
                self, "Edificio borrado",
                f"Se borró «{edificio}».\n\nSus datos, recibos PDF y planilla quedaron guardados en:\n{destino}")

        DialogoBorrarEdificio(self, edificio, on_borrado=al_borrar).show()

    def _nueva_unidad(self):
        edificio = self._edificio_actual()
        if not edificio:
            QMessageBox.warning(self, "Atención", "Primero seleccioná o creá un edificio.")
            return
        DialogoUnidad(self, edificio, unidad=None, on_guardar=self._recargar).show()

    def _editar_seleccionada(self):
        unidad = self._seleccionada()
        if not unidad:
            QMessageBox.information(self, "Editar unidad", "Seleccioná primero una unidad de la lista.")
            return
        DialogoUnidad(self, self._edificio_actual(), unidad=unidad, on_guardar=self._recargar).show()

    def _abrir_carpeta(self):
        edificio = self._edificio_actual()
        if not edificio:
            return
        carpeta = database.carpeta_edificio(edificio)
        if not abrir_carpeta_en_explorador(carpeta):
            QMessageBox.information(self, "Carpeta del edificio", f"La carpeta es:\n{carpeta}")


# ===========================================================================
# Ventana: configuración de la inmobiliaria
# ===========================================================================

class VentanaConfiguracion(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Configuración de la inmobiliaria")
        self.setModal(True)

        datos = database.get_inmobiliaria()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        grilla = QGridLayout()
        grilla.setHorizontalSpacing(10)
        grilla.setVerticalSpacing(6)
        self.campos = {}
        for fila, (clave, etiqueta) in enumerate((
            ("nombre", "Nombre de la inmobiliaria:"),
            ("subtitulo", "Subtítulo:"),
            ("direccion", "Dirección:"),
            ("telefono", "Teléfono:"),
            ("email", "Email:"),
        )):
            grilla.addWidget(QLabel(etiqueta), fila, 0)
            campo = QLineEdit(datos.get(clave, ""))
            grilla.addWidget(campo, fila, 1)
            self.campos[clave] = campo
        layout.addLayout(grilla)

        # Logo y firma digital. Los cambios se aplican al apretar "Guardar".
        self._imagenes = {}   # clave -> ruta elegida (str) o None si se quitó; ausente = sin cambios
        self._vistas = {}     # clave -> QLabel con la vista previa
        for clave, titulo in (("logo", "Logo:"), ("firma", "Firma digital:")):
            fila_img = QHBoxLayout()
            etiqueta = QLabel(titulo)
            etiqueta.setFixedWidth(130)
            fila_img.addWidget(etiqueta)

            vista = QLabel()
            vista.setFixedSize(200, 70)
            vista.setAlignment(Qt.AlignCenter)
            vista.setStyleSheet(
                f"background-color: white; border: 1px solid {COLOR_BORDE}; "
                f"border-radius: 6px; color: #666; font-size: 10px;")
            fila_img.addWidget(vista)
            self._vistas[clave] = vista

            columna_botones = QVBoxLayout()
            boton_elegir = QPushButton("Elegir imagen...")
            boton_elegir.clicked.connect(lambda _, c=clave: self._elegir_imagen(c))
            boton_quitar = QPushButton("Quitar")
            boton_quitar.clicked.connect(lambda _, c=clave: self._quitar_imagen(c))
            columna_botones.addWidget(boton_elegir)
            columna_botones.addWidget(boton_quitar)
            fila_img.addLayout(columna_botones)
            fila_img.addStretch()
            layout.addLayout(fila_img)
            self._mostrar_vista(clave, database.imagen_inmobiliaria(clave))

        botones = QHBoxLayout()
        boton_guardar = QPushButton("Guardar")
        boton_guardar.setObjectName("botonAcento")
        boton_guardar.clicked.connect(self._guardar)
        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.clicked.connect(self.reject)
        botones.addWidget(boton_guardar)
        botones.addWidget(boton_cerrar)
        botones.addStretch()
        layout.addLayout(botones)

    def _mostrar_vista(self, clave, ruta):
        """Muestra una miniatura de la imagen (o 'Sin imagen') en la vista previa."""
        vista = self._vistas[clave]
        if not ruta:
            vista.setPixmap(QPixmap())
            vista.setText("Sin imagen")
            return
        pixmap = QPixmap(ruta)
        if pixmap.isNull():
            vista.setPixmap(QPixmap())
            vista.setText(os.path.basename(ruta))
            return
        vista.setText("")
        vista.setPixmap(pixmap.scaled(190, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _elegir_imagen(self, clave):
        ruta, _filtro = QFileDialog.getOpenFileName(
            self, "Elegir imagen", "",
            "Imágenes (*.png *.jpg *.jpeg *.gif *.bmp);;Todos los archivos (*.*)")
        if not ruta:
            return
        try:
            from PIL import Image
            with Image.open(ruta) as img:
                img.verify()
        except Exception:
            QMessageBox.warning(self, "Imagen no válida", "El archivo elegido no es una imagen válida (usá PNG o JPG).")
            return
        self._imagenes[clave] = ruta
        self._mostrar_vista(clave, ruta)

    def _quitar_imagen(self, clave):
        self._imagenes[clave] = None
        self._mostrar_vista(clave, None)

    def _guardar(self):
        def guardar_de_verdad():
            try:
                datos = {clave: campo.text().strip() for clave, campo in self.campos.items()}
                database.save_inmobiliaria(datos)
                for clave, ruta in self._imagenes.items():
                    if ruta is None:
                        database.quitar_imagen_inmobiliaria(clave)
                    else:
                        database.guardar_imagen_inmobiliaria(clave, ruta)
                QMessageBox.information(self, "Configuración", "Los datos de la inmobiliaria se guardaron correctamente.")
                self.accept()
            except Exception as e:
                manejar_error("No se pudo guardar la configuración", e, self)

        requerir_maestro(self, guardar_de_verdad, motivo="guardar la configuración de la inmobiliaria")


# ===========================================================================
# Ventanas: envío de recibos por mail (SMTP, plantilla, copia CC y direcciones)
# ===========================================================================

class DialogoConfiguracionSMTP(QDialog):
    """Lo mínimo para poder mandar los recibos por mail: servidor, puerto, usuario y contraseña."""

    def __init__(self, parent, on_guardado=None):
        super().__init__(parent)
        self.on_guardado = on_guardado
        self.setWindowTitle("Configuración SMTP")
        self.setModal(True)

        datos = correo.get_smtp()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        grilla = QGridLayout()
        grilla.setHorizontalSpacing(10)
        grilla.setVerticalSpacing(6)
        self.campos = {}
        for fila, (clave, etiqueta, oculto) in enumerate((
            ("servidor", "Servidor SMTP:", False),
            ("puerto", "Puerto:", False),
            ("usuario", "Usuario (mail):", False),
            ("password", "Contraseña:", True),
        )):
            grilla.addWidget(QLabel(etiqueta), fila, 0)
            campo = QLineEdit(datos.get(clave, ""))
            if oculto:
                campo.setEchoMode(QLineEdit.Password)
            grilla.addWidget(campo, fila, 1)
            self.campos[clave] = campo
        layout.addLayout(grilla)

        fila_tls = QHBoxLayout()
        fila_tls.addWidget(QLabel("Seguridad de la conexión:"))
        self.combo_tls = QComboBox()
        self.combo_tls.addItems(["STARTTLS", "SSL", "Ninguna"])
        self.combo_tls.setCurrentText(datos.get("tls") or "STARTTLS")
        _estilizar_combo(self.combo_tls)
        fila_tls.addWidget(self.combo_tls)
        layout.addLayout(fila_tls)

        self.lbl_estado = QLabel("")
        self.lbl_estado.setWordWrap(True)
        layout.addWidget(self.lbl_estado)

        botones = QHBoxLayout()
        boton_probar = QPushButton("Probar conexión")
        boton_probar.clicked.connect(self._probar)
        boton_guardar = QPushButton("Guardar")
        boton_guardar.setObjectName("botonAcento")
        boton_guardar.clicked.connect(self._guardar)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        botones.addWidget(boton_probar)
        botones.addWidget(boton_guardar)
        botones.addWidget(boton_cancelar)
        botones.addStretch()
        layout.addLayout(botones)

    def _leer(self):
        datos = {clave: campo.text().strip() for clave, campo in self.campos.items()}
        datos["tls"] = self.combo_tls.currentText()
        return datos

    def _probar(self):
        datos = self._leer()
        if not datos["puerto"].isdigit():
            self.lbl_estado.setStyleSheet("color: #f87171; font-size: 11px; background: transparent;")
            self.lbl_estado.setText("El puerto tiene que ser un número.")
            return
        self.lbl_estado.setStyleSheet(f"color: {COLOR_TEXTO_SUAVE}; font-size: 11px; background: transparent;")
        self.lbl_estado.setText("Probando...")
        QApplication.processEvents()
        ok, mensaje = correo.probar_conexion(datos)
        color = "#4ade80" if ok else "#f87171"
        self.lbl_estado.setStyleSheet(f"color: {color}; font-size: 11px; background: transparent;")
        self.lbl_estado.setText(mensaje)

    def _guardar(self):
        def guardar_de_verdad():
            try:
                correo.guardar_smtp(self._leer())
            except ValueError as e:
                QMessageBox.warning(self, "Datos incompletos", str(e))
                return
            self.accept()
            if self.on_guardado:
                self.on_guardado()

        requerir_maestro(self, guardar_de_verdad, motivo="guardar la configuración SMTP")


class DialogoPlantillaMail(QDialog):
    """Asunto y cuerpo del mail de un edificio. Vacío = usa el predeterminado."""

    def __init__(self, parent, edificio, on_guardado=None):
        super().__init__(parent)
        self.edificio = edificio
        self.on_guardado = on_guardado
        self.setWindowTitle(f"Asunto y cuerpo del mail - {edificio}")
        self.setModal(True)
        self.resize(520, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        layout.addWidget(QLabel("Asunto:"))
        self.campo_asunto = QLineEdit()
        layout.addWidget(self.campo_asunto)

        layout.addWidget(QLabel("Cuerpo:"))
        self.texto_cuerpo = QPlainTextEdit()
        layout.addWidget(self.texto_cuerpo, 1)

        nota = QLabel(
            "Variables disponibles: {edificio}, {unidad}, {expensas_de}, {gastos_de}.\n"
            "«unidad» es lo que se pagó (ej. «1 A y Cochera 6»); los períodos van abreviados, "
            "igual que en el recibo.")
        nota.setStyleSheet(f"color: {COLOR_TEXTO_SUAVE}; font-size: 10px; background: transparent;")
        nota.setWordWrap(True)
        layout.addWidget(nota)

        self.lbl_estado = QLabel("")
        self.lbl_estado.setObjectName("error")
        self.lbl_estado.setWordWrap(True)
        layout.addWidget(self.lbl_estado)

        botones = QHBoxLayout()
        boton_restablecer = QPushButton("Restablecer predeterminado")
        boton_restablecer.clicked.connect(self._restablecer)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        boton_guardar = QPushButton("Guardar")
        boton_guardar.setObjectName("botonAcento")
        boton_guardar.clicked.connect(self._guardar)
        botones.addWidget(boton_restablecer)
        botones.addStretch()
        botones.addWidget(boton_cancelar)
        botones.addWidget(boton_guardar)
        layout.addLayout(botones)

        self._cargar()

    def _cargar(self):
        asunto, cuerpo = correo.get_plantilla(self.edificio)
        self.campo_asunto.setText(asunto)
        self.texto_cuerpo.setPlainText(cuerpo)

    def _restablecer(self):
        self.campo_asunto.setText(correo.ASUNTO_DEFECTO)
        self.texto_cuerpo.setPlainText(correo.CUERPO_DEFECTO)

    def _guardar(self):
        asunto = self.campo_asunto.text().strip()
        cuerpo = self.texto_cuerpo.toPlainText().strip()

        def guardar_de_verdad():
            try:
                correo.set_plantilla(self.edificio, asunto, cuerpo)
            except ValueError as e:
                self.lbl_estado.setText(str(e))
                return
            self.accept()
            if self.on_guardado:
                self.on_guardado()

        requerir_maestro(self, guardar_de_verdad, motivo="guardar la plantilla del mail")


class DialogoCopiaMail(QDialog):
    """Un mail de copia (CC) para cada envío, que se puede activar o desactivar sin borrarlo."""

    def __init__(self, parent, on_guardado=None):
        super().__init__(parent)
        self.on_guardado = on_guardado
        self.setWindowTitle("Copia (CC)")
        self.setModal(True)

        datos = correo.get_copia()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        fila = QHBoxLayout()
        fila.addWidget(QLabel("Mail de copia:"))
        self.campo_email = QLineEdit(datos["email"])
        fila.addWidget(self.campo_email)
        layout.addLayout(fila)

        self.check_activa = QCheckBox("Mandar copia a este mail en cada envío")
        self.check_activa.setChecked(bool(datos["activa"]))
        layout.addWidget(self.check_activa)

        self.lbl_estado = QLabel("")
        self.lbl_estado.setObjectName("error")
        self.lbl_estado.setWordWrap(True)
        layout.addWidget(self.lbl_estado)

        botones = QHBoxLayout()
        boton_guardar = QPushButton("Guardar")
        boton_guardar.setObjectName("botonAcento")
        boton_guardar.clicked.connect(self._guardar)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        botones.addWidget(boton_guardar)
        botones.addWidget(boton_cancelar)
        botones.addStretch()
        layout.addLayout(botones)

    def _guardar(self):
        email, activa = self.campo_email.text().strip(), self.check_activa.isChecked()

        def guardar_de_verdad():
            try:
                correo.guardar_copia(email, activa)
            except ValueError as e:
                self.lbl_estado.setText(str(e))
                return
            self.accept()
            if self.on_guardado:
                self.on_guardado()

        requerir_maestro(self, guardar_de_verdad, motivo="guardar la copia (CC) del mail")


class VentanaMails(QDialog):
    """Direcciones de mail (inquilino y dueño) de cada unidad de un edificio, para enviar recibos."""

    def __init__(self, parent, edificio_inicial=""):
        super().__init__(parent)
        self.setWindowTitle("Mailing")
        self.setModal(True)
        self.resize(1480, 560)

        layout_externo = QVBoxLayout(self)
        layout_externo.setContentsMargins(0, 0, 0, 0)
        layout_externo.setSpacing(0)

        cuerpo = QHBoxLayout()
        cuerpo.setContentsMargins(0, 0, 0, 0)
        cuerpo.setSpacing(0)
        layout_externo.addLayout(cuerpo, 1)

        self.lista_edificios = _crear_sidebar_edificios(
            cuerpo, database.get_nombres_edificios(), self._cargar)

        contenedor = QWidget()
        layout = QVBoxLayout(contenedor)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)
        cuerpo.addWidget(contenedor, 1)

        top = QHBoxLayout()
        top.setSpacing(8)
        top.addStretch()
        boton_plantilla = QPushButton("Asunto y cuerpo del mail")
        boton_plantilla.clicked.connect(self._editar_plantilla)
        boton_copia = QPushButton("Copia (CC)")
        boton_copia.clicked.connect(self._editar_copia)
        boton_smtp = QPushButton("Configuración SMTP")
        boton_smtp.clicked.connect(self._config_smtp)
        top.addWidget(boton_plantilla)
        top.addWidget(boton_copia)
        top.addWidget(boton_smtp)
        layout.addLayout(top)

        nota = QLabel(
            "Al enviar un recibo se manda a todos los inquilinos y dueños que estén cargados.\n"
            "Un depto que paga junto con su cochera/baulera usa los mails del depto.")
        nota.setStyleSheet(f"color: {COLOR_TEXTO_SUAVE}; font-size: 10px; background: transparent;")
        layout.addWidget(nota)

        self.tabla = QTableWidget(0, 5)
        self.tabla.setObjectName("listaSimple")
        self.tabla.setHorizontalHeaderLabels(["Unidad", "Inquilino 1", "Inquilino 2", "Dueño 1", "Dueño 2"])
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(36)
        self.tabla.horizontalHeader().setFixedHeight(32)
        self.tabla.setShowGrid(False)
        self.tabla.setSelectionMode(QAbstractItemView.NoSelection)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for col in range(1, 5):
            self.tabla.horizontalHeader().setSectionResizeMode(col, QHeaderView.Stretch)
        layout.addWidget(self.tabla, 1)

        botones = QHBoxLayout()
        boton_guardar = QPushButton("Guardar")
        boton_guardar.setObjectName("botonAcento")
        boton_guardar.clicked.connect(self._guardar)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        botones.addWidget(boton_guardar)
        botones.addWidget(boton_cancelar)
        botones.addStretch()
        layout.addLayout(botones)

        self._campos_por_unidad = {}
        coincidencias = self.lista_edificios.findItems(edificio_inicial, Qt.MatchExactly)
        self.lista_edificios.blockSignals(True)
        if coincidencias:
            self.lista_edificios.setCurrentItem(coincidencias[0])
        elif self.lista_edificios.count():
            self.lista_edificios.setCurrentRow(0)
        self.lista_edificios.blockSignals(False)
        self._cargar()

    def _edificio_actual(self):
        item = self.lista_edificios.currentItem()
        return item.text() if item else ""

    def _config_smtp(self):
        DialogoConfiguracionSMTP(self).show()

    def _editar_copia(self):
        DialogoCopiaMail(self).show()

    def _editar_plantilla(self):
        edificio = self._edificio_actual()
        if not edificio:
            QMessageBox.warning(self, "Atención", "Elegí primero un edificio.")
            return
        DialogoPlantillaMail(self, edificio).show()

    def _cargar(self):
        self.tabla.setRowCount(0)
        self._campos_por_unidad = {}

        edificio = self._edificio_actual()
        if not edificio:
            return
        todas = database.get_unidades_por_edificio(edificio)
        por_id = indice_por_id(todas)
        guardados = correo.get_emails_unidades()

        filas = [(u, n) for u, n in ordenar_con_asociadas(todas) if not (n == 1 and incluida_en_total(u))]
        self.tabla.setRowCount(len(filas))
        for fila, (u, nivel) in enumerate(filas):
            texto = ("      " if nivel else "") + f"{nombre_tipo(normalizar_tipo(u['tipo']))} — {etiqueta_unidad(u, por_id)}"
            item = QTableWidgetItem(texto)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.tabla.setItem(fila, 0, item)
            existentes = guardados.get(u["id"], {})
            variables = {}
            for col, campo in enumerate(correo.EMAILS_CAMPOS[1:], start=1):
                entrada = QLineEdit(existentes.get(campo, ""))
                entrada.setCursorPosition(0)   # si el mail es largo, que se vea desde el principio
                self.tabla.setCellWidget(fila, col, entrada)
                variables[campo] = entrada
            self._campos_por_unidad[u["id"]] = variables
        if not todas:
            self.tabla.setRowCount(1)
            self.tabla.setItem(0, 0, QTableWidgetItem("Este edificio todavía no tiene unidades."))

        # Un alto de fila fijo a veces queda corto según la fuente/escala de pantalla real;
        # esto mide el alto que necesita cada QLineEdit ya puesto y ajusta la fila a eso.
        self.tabla.resizeRowsToContents()

    def _guardar(self):
        invalidas = []
        datos_por_unidad = {}
        for unidad_id, variables in self._campos_por_unidad.items():
            valores = {campo: entrada.text().strip() for campo, entrada in variables.items()}
            for valor in valores.values():
                if valor and not correo.es_email_valido(valor):
                    invalidas.append(valor)
            datos_por_unidad[unidad_id] = valores
        if invalidas:
            QMessageBox.warning(
                self, "Mails inválidos",
                "Estos mails no tienen un formato válido:\n\n" + "\n".join(invalidas[:10]))
            return

        def guardar_de_verdad():
            correo.set_emails_unidades(datos_por_unidad)
            QMessageBox.information(self, "Mails", "Las direcciones se guardaron correctamente.")
            self.accept()

        requerir_maestro(self, guardar_de_verdad, motivo="guardar las direcciones de mail")


# ===========================================================================
# Ventana: historial de mails enviados
# ===========================================================================

COLUMNAS_ENVIOS = ("fecha", "edificio", "numero_recibo", "unidad", "destinatario", "resultado", "detalle")
TITULOS_ENVIOS = {"fecha": "Fecha", "edificio": "Edificio", "numero_recibo": "N°", "unidad": "Unidad",
                  "destinatario": "Destinatario", "resultado": "Resultado", "detalle": "Detalle"}
ANCHOS_ENVIOS = {"fecha": 110, "edificio": 140, "numero_recibo": 55, "unidad": 140,
                 "destinatario": 180, "resultado": 80, "detalle": 220}


class VentanaRegistroEnvios(QDialog):
    """Lista de mails enviados, con filtro por edificio y reenvío a una dirección puntual."""

    def __init__(self, parent, edificio_inicial=""):
        super().__init__(parent)
        self.setWindowTitle("Historial de mails")
        self.setModal(True)
        self.resize(1160, 500)

        layout_externo = QVBoxLayout(self)
        layout_externo.setContentsMargins(0, 0, 0, 0)
        layout_externo.setSpacing(0)

        cuerpo = QHBoxLayout()
        cuerpo.setContentsMargins(0, 0, 0, 0)
        cuerpo.setSpacing(0)
        layout_externo.addLayout(cuerpo, 1)

        self._nombres_sidebar = ["(Todos)"] + database.get_nombres_edificios()
        self.lista_edificios = _crear_sidebar_edificios(cuerpo, self._nombres_sidebar, self._recargar)

        contenedor = QWidget()
        layout = QVBoxLayout(contenedor)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)
        cuerpo.addWidget(contenedor, 1)

        self.tabla = QTableWidget(0, len(COLUMNAS_ENVIOS))
        self.tabla.setObjectName("listaSimple")
        self.tabla.setHorizontalHeaderLabels([TITULOS_ENVIOS[c] for c in COLUMNAS_ENVIOS])
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setShowGrid(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(28)
        self.tabla.horizontalHeader().setFixedHeight(32)
        for col, clave in enumerate(COLUMNAS_ENVIOS):
            self.tabla.setColumnWidth(col, ANCHOS_ENVIOS[clave])
        self.tabla.horizontalHeader().setSectionResizeMode(COLUMNAS_ENVIOS.index("detalle"), QHeaderView.Stretch)
        layout.addWidget(self.tabla, 1)

        pie = QHBoxLayout()
        boton_reenviar = QPushButton("Reenviar")
        boton_reenviar.setStyleSheet("background-color: #16a34a; color: white; border: none;")
        boton_reenviar.clicked.connect(self._reenviar)
        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.clicked.connect(self.reject)
        pie.addWidget(boton_reenviar)
        pie.addStretch()
        pie.addWidget(boton_cerrar)
        layout.addLayout(pie)

        self._filas_por_fila = {}
        self.lista_edificios.blockSignals(True)
        self.lista_edificios.setCurrentRow(0)   # siempre arranca en "(Todos)"
        self.lista_edificios.blockSignals(False)
        self._recargar()

    def _filtro_actual(self):
        item = self.lista_edificios.currentItem()
        return item.text() if item else "(Todos)"

    def _recargar(self):
        self.tabla.setRowCount(0)
        self._filas_por_fila = {}
        filtro = self._filtro_actual()
        registro = correo.get_mails_enviados(None if filtro in ("", "(Todos)") else filtro)
        self.tabla.setRowCount(len(registro))
        for fila, r in enumerate(registro):
            valores = (r.get("fecha", ""), r.get("edificio", ""), r.get("numero_recibo", ""), r.get("unidad", ""),
                       r.get("destinatario", ""), r.get("resultado", ""), r.get("detalle", ""))
            es_error = r.get("resultado") != "OK"
            for col, valor in enumerate(valores):
                item = QTableWidgetItem(valor)
                if col in (2, 5):
                    item.setTextAlignment(Qt.AlignCenter)
                if es_error:
                    item.setForeground(QColor("#f87171"))
                self.tabla.setItem(fila, col, item)
            self._filas_por_fila[fila] = r

    def _reenviar(self):
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            QMessageBox.information(self, "Reenviar", "Seleccioná primero un envío de la lista.")
            return
        r = self._filas_por_fila[filas[0].row()]
        fila_historial = next(
            (h for h in database.get_historial()
             if h.get("edificio") == r.get("edificio") and h.get("numero_recibo") == r.get("numero_recibo")), None)
        if fila_historial is None:
            QMessageBox.warning(
                self, "Reenviar", "No encuentro el recibo de este envío en el historial (¿se borró el edificio?).")
            return
        confirmado = QMessageBox.question(
            self, "Reenviar", f"¿Reenviar el recibo N° {r['numero_recibo']} a {r['destinatario']}?")
        if confirmado != QMessageBox.Yes:
            return
        ok, detalle = correo.reenviar(fila_historial, r["destinatario"], cc=correo.obtener_cc())
        if ok:
            QMessageBox.information(self, "Reenviar", "Reenviado correctamente.")
        else:
            QMessageBox.warning(self, "Reenviar", f"No se pudo reenviar: {detalle}")
        self._recargar()


# ===========================================================================
# Ventana: historial de recibos
# ===========================================================================

# Estado de pago según "Gastos de" (el historial no guarda el estado, pero el texto lo dice)
_ESTADO_POR_GASTOS = {"A CTA.": "A cta.", "DEUDA": "Deuda", "NO PAGADO": "No pagado"}


def tiene_datos_completos(r):
    """True si el renglón del historial guardó todos los datos del PDF (recibos emitidos desde esta versión)."""
    return r.get("datos_completos") == "1"


def _datos_pdf_guardados(r):
    """Arma los datos del PDF solo con las columnas del historial: no depende de la unidad, el edificio
    ni la inmobiliaria actuales, así que sale igual aunque después cambien o se borren."""
    principal = {"tipo": r["tipo"], "piso": r["piso"], "unidad": r["unidad"].split(" + ")[0].strip(),
                 "uf": r["uf"], "dueno": r["dueno"], "inquilino": r["inquilino"]}
    agrupadas = []
    for item in (r["asociadas"] or "").split(";"):
        if item.strip():
            tipo, piso, numero = (p.strip() for p in item.split("|"))
            agrupadas.append({"tipo": tipo, "piso": piso, "unidad": numero})
    datos_edificio = {"direccion": r["edificio_direccion"], "localidad": r["edificio_localidad"],
                      "cuit": r["edificio_cuit"], "admin_nombre": r["admin_nombre"],
                      "admin_cuit": r["admin_cuit"], "admin_rpac": r["admin_rpac"]}
    inmobiliaria = {"nombre": r["inmo_nombre"], "subtitulo": r["inmo_subtitulo"], "direccion": r["inmo_direccion"],
                    "telefono": r["inmo_telefono"], "email": r["inmo_email"]}
    return armar_datos_recibo(
        numero=int(r["numero_recibo"]),
        fecha=datetime.strptime(r["fecha"], "%d/%m/%Y").date(),
        edificio=r["edificio"], datos_edificio=datos_edificio,
        unidad=principal, agrupadas=agrupadas,
        expensas_de=r["expensas_de"], gastos_de=r["gastos_de"],
        estado=r["estado"] or None, importe=float(r["importe"]), inmobiliaria=inmobiliaria,
    )


def datos_pdf_desde_historial(r):
    """
    Devuelve los mismos datos con que se armó el PDF. Si el renglón guardó sus datos completos, salen
    exactos de sus columnas. Si es un recibo anterior, se reconstruye: lo que guarda el historial sale
    tal cual y el resto (dueño, UF, CUIT y direcciones del edificio, inmobiliaria) sale de los datos
    actuales. Lanza ValueError si en la reconstrucción la unidad ya no existe con ese nombre.
    """
    if tiene_datos_completos(r):
        return _datos_pdf_guardados(r)
    return _reconstruir_datos_pdf(r)


def _reconstruir_datos_pdf(r):
    edificio = r["edificio"]
    todas = database.get_unidades_por_edificio(edificio)
    por_id = indice_por_id(todas)
    partes = [p.strip() for p in (r.get("unidad") or "").split(" + ") if p.strip()]
    if not partes:
        raise ValueError("El registro del historial no tiene unidad.")

    principal = por_id.get(r.get("unidad_id") or "")
    if principal is None:   # registros anteriores a unidad_id: se busca por piso, tipo y letra
        tipo = normalizar_tipo(r.get("tipo"))
        principal = next((u for u in todas if normalizar_tipo(u["tipo"]) == tipo
                          and (u.get("piso") or "").strip() == (r.get("piso") or "").strip()
                          and (u.get("unidad") or "").strip() == partes[0]), None)
    if principal is None:
        raise ValueError(f"No encuentro la unidad «{partes[0]}» en {edificio} (¿se borró o se renombró?).")
    principal = dict(principal, inquilino=r.get("inquilino", ""))   # el inquilino de cuando se emitió

    agrupadas = []
    for etiqueta in partes[1:]:   # mismo texto que se guardó al emitir (sin por_id)
        h = next((u for u in todas if etiqueta_unidad(u) == etiqueta), None)
        if h is None:
            raise ValueError(f"No encuentro «{etiqueta}» en {edificio} (¿se borró o se renombró?).")
        agrupadas.append(h)

    gastos_de = r.get("gastos_de", "")
    return armar_datos_recibo(
        numero=int(r["numero_recibo"]),
        fecha=datetime.strptime(r["fecha"], "%d/%m/%Y").date(),
        edificio=edificio,
        datos_edificio=database.get_edificio(edificio) or {},
        unidad=principal, agrupadas=agrupadas,
        expensas_de=r.get("expensas_de", ""), gastos_de=gastos_de,
        estado=_ESTADO_POR_GASTOS.get(gastos_de.strip().upper(), "Total"),
        importe=float(r.get("importe") or 0),
        inmobiliaria=database.get_inmobiliaria(),
    )


class _AbreRecibosMixin:
    """Abrir el PDF de la fila seleccionada (self.tabla / self._archivo_por_fila) o mostrarlo en su carpeta."""

    def _fila_seleccionada(self):
        filas = self.tabla.selectionModel().selectedRows()
        return filas[0].row() if filas else None

    def _ruta_absoluta_seleccionada(self):
        fila = self._fila_seleccionada()
        if fila is None:
            QMessageBox.information(self, "Recibos", "Seleccioná primero un recibo de la lista.")
            return None
        archivo_rel = self._archivo_por_fila.get(fila, "")
        if not archivo_rel:
            QMessageBox.warning(self, "Recibos", "Este registro no tiene un archivo asociado.")
            return None
        return os.path.join(config.BASE_DIR, archivo_rel)

    def _abrir_pdf_seleccionado(self):
        ruta = self._ruta_absoluta_seleccionada()
        if not ruta:
            return
        ok, mensaje_error = abrir_pdf(ruta)
        if not ok:
            QMessageBox.warning(self, "No se pudo abrir el PDF", mensaje_error)

    def _mostrar_en_carpeta(self):
        ruta = self._ruta_absoluta_seleccionada()
        if not ruta:
            return
        if not revelar_en_explorador(ruta):
            QMessageBox.information(self, "Ubicación del archivo", ruta)

    def _regenerar_pdf(self):
        """Vuelve a armar el PDF de un recibo ya emitido, con su mismo número, a partir del historial."""
        fila = self._fila_seleccionada()
        if fila is None:
            QMessageBox.information(self, "Regenerar PDF", "Seleccioná primero un recibo de la lista.")
            return
        registro = self._filas_por_fila.get(fila)
        if not registro or not registro.get("archivo"):
            QMessageBox.warning(self, "Regenerar PDF", "Este registro no tiene un archivo asociado.")
            return

        ruta = os.path.join(config.BASE_DIR, registro["archivo"])
        if os.path.isfile(ruta):
            confirmado = QMessageBox.question(
                self, "Regenerar PDF",
                "Este PDF todavía existe.\n\n¿Reemplazarlo por uno nuevo armado con los mismos datos?")
            if confirmado != QMessageBox.Yes:
                return
        if not tiene_datos_completos(registro):
            confirmado = QMessageBox.question(
                self, "Regenerar PDF",
                "Este recibo es de antes de guardar todos sus datos. Se va a armar con los datos ACTUALES "
                "de la unidad y del edificio: si cambiaron el dueño, la UF o los datos del consorcio, "
                "el PDF va a salir distinto.\n\n¿Seguir?")
            if confirmado != QMessageBox.Yes:
                return

        try:
            datos = datos_pdf_desde_historial(registro)
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            generar_pdf_recibo(datos, ruta)
        except ValueError as e:
            QMessageBox.warning(self, "No se pudo regenerar el PDF", str(e))
            return
        except Exception as e:
            manejar_error("No se pudo regenerar el PDF", e, self)
            return
        QMessageBox.information(
            self, "Regenerar PDF", f"Recibo N° {registro['numero_recibo']} regenerado en:\n\n{ruta}")


class _EnviarPorMailMixin:
    """
    Checkbox de selección (columna 'sel') + Seleccionar todas/Quitar todas + Enviar por mail,
    para una tabla del historial. Necesita self.tabla, self._casillas_por_fila (fila -> QCheckBox)
    y self._filas_por_fila (fila -> fila del historial, tal como la devuelve database.get_historial()).
    """

    def _seleccionar_todas_mail(self):
        for casilla in self._casillas_por_fila.values():
            casilla.setChecked(True)

    def _quitar_todas_mail(self):
        for casilla in self._casillas_por_fila.values():
            casilla.setChecked(False)

    def _enviar_por_mail(self):
        elegidas = [fila for fila, casilla in self._casillas_por_fila.items() if casilla.isChecked()]
        if not elegidas:
            QMessageBox.information(self, "Enviar por mail", "Tildá primero los recibos que querés mandar.")
            return
        if not correo.existe_smtp():
            QMessageBox.warning(
                self, "Enviar por mail",
                "Todavía no cargaste la configuración SMTP (Administrar → Mailing → Configuración SMTP).")
            return

        cc = correo.obtener_cc()
        detalle, enviados, fallidos = [], 0, 0
        for fila in elegidas:
            registro = self._filas_por_fila[fila]
            resultados = correo.enviar_recibo(registro, cc=cc)
            etiqueta = f"{registro.get('piso', '')} {registro.get('unidad', '')}".strip()
            for destinatario, ok, error in resultados:
                if ok:
                    enviados += 1
                else:
                    fallidos += 1
                    detalle.append(f"{etiqueta} → {destinatario}: {error}")

        mensaje = f"Se enviaron {enviados} mail(s)."
        if fallidos:
            mensaje += f"\n\n{fallidos} con error:\n" + "\n".join(detalle[:15])
            if len(detalle) > 15:
                mensaje += f"\n… y {len(detalle) - 15} más."
            QMessageBox.warning(self, "Enviar por mail", mensaje)
        else:
            QMessageBox.information(self, "Enviar por mail", mensaje)


COLUMNAS_HISTORIAL = ("sel", "numero_recibo", "edificio", "fecha", "expensas_de", "tipo", "piso",
                      "unidad", "inquilino", "importe", "archivo")
TITULOS_HISTORIAL = {
    "sel": "ENVIAR", "numero_recibo": "N°", "edificio": "Edificio", "fecha": "Fecha", "expensas_de": "Expensas de",
    "tipo": "Tipo", "piso": "Piso", "unidad": "Unidad", "inquilino": "Inquilino", "importe": "Importe",
    "archivo": "Archivo",
}
ANCHOS_HISTORIAL = {
    "sel": 65, "numero_recibo": 55, "edificio": 150, "fecha": 80, "expensas_de": 110,
    "tipo": 80, "piso": 55, "unidad": 65, "inquilino": 150, "importe": 90, "archivo": 240,
}


class VentanaHistorial(_AbreRecibosMixin, _EnviarPorMailMixin, QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Historial de recibos generados")
        self.setModal(True)
        self.resize(1280, 560)

        layout_externo = QVBoxLayout(self)
        layout_externo.setContentsMargins(0, 0, 0, 0)
        layout_externo.setSpacing(0)

        cuerpo = QHBoxLayout()
        cuerpo.setContentsMargins(0, 0, 0, 0)
        cuerpo.setSpacing(0)
        layout_externo.addLayout(cuerpo, 1)

        self.lista_edificios = _crear_sidebar_edificios(
            cuerpo, ["(Todos)"] + database.get_nombres_edificios(), self._recargar)

        contenedor = QWidget()
        layout = QVBoxLayout(contenedor)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)
        cuerpo.addWidget(contenedor, 1)

        self.tabla = QTableWidget(0, len(COLUMNAS_HISTORIAL))
        self.tabla.setObjectName("listaSimple")
        self.tabla.setHorizontalHeaderLabels([TITULOS_HISTORIAL[c] for c in COLUMNAS_HISTORIAL])
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setShowGrid(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(30)
        self.tabla.horizontalHeader().setFixedHeight(32)
        for col, clave in enumerate(COLUMNAS_HISTORIAL):
            self.tabla.setColumnWidth(col, ANCHOS_HISTORIAL[clave])
        self.tabla.horizontalHeader().setSectionResizeMode(COLUMNAS_HISTORIAL.index("archivo"), QHeaderView.Stretch)
        self.tabla.doubleClicked.connect(lambda _i: self._abrir_pdf_seleccionado())
        layout.addWidget(self.tabla, 1)

        pie = QHBoxLayout()
        boton_abrir = QPushButton("Abrir PDF")
        boton_abrir.setObjectName("botonAcento")
        boton_abrir.clicked.connect(self._abrir_pdf_seleccionado)
        boton_carpeta = QPushButton("Mostrar en carpeta")
        boton_carpeta.clicked.connect(self._mostrar_en_carpeta)
        boton_todas = QPushButton("Seleccionar todas")
        boton_todas.clicked.connect(self._seleccionar_todas_mail)
        boton_ninguna = QPushButton("Quitar todas")
        boton_ninguna.clicked.connect(self._quitar_todas_mail)
        boton_enviar = QPushButton("Enviar por mail")
        boton_enviar.setStyleSheet("background-color: #16a34a; color: white; border: none;")
        boton_enviar.clicked.connect(self._enviar_por_mail)
        boton_regenerar = QPushButton("Regenerar PDF")
        boton_regenerar.clicked.connect(self._regenerar_pdf)
        for b in (boton_abrir, boton_carpeta, boton_todas, boton_ninguna, boton_enviar, boton_regenerar):
            pie.addWidget(b)
        pie.addStretch()
        layout.addLayout(pie)

        self._archivo_por_fila = {}
        self._filas_por_fila = {}
        self._casillas_por_fila = {}
        self.lista_edificios.blockSignals(True)
        self.lista_edificios.setCurrentRow(0)
        self.lista_edificios.blockSignals(False)
        self._recargar()

    def _filtro_actual(self):
        item = self.lista_edificios.currentItem()
        return item.text() if item else "(Todos)"

    def _crear_casilla_mail(self):
        contenedor = QWidget()
        contenedor.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(contenedor)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch()
        casilla = QCheckBox()
        casilla.setCursor(Qt.PointingHandCursor)
        lay.addWidget(casilla)
        lay.addStretch()
        return contenedor, casilla

    def _recargar(self):
        self.tabla.setRowCount(0)
        self._archivo_por_fila = {}
        self._filas_por_fila = {}
        self._casillas_por_fila = {}

        filtro = self._filtro_actual()
        historial = database.get_historial()
        historial.sort(key=lambda r: r.get("numero_recibo", ""), reverse=True)
        historial = [r for r in historial if filtro in ("", "(Todos)") or r.get("edificio") == filtro]

        self.tabla.setRowCount(len(historial))
        for fila, r in enumerate(historial):
            importe_fmt = format_currency_ar(parse_importe(r.get("importe", "0")))
            valores = {
                "numero_recibo": r.get("numero_recibo", ""), "edificio": r.get("edificio", ""),
                "fecha": r.get("fecha", ""), "expensas_de": r.get("expensas_de", ""), "tipo": r.get("tipo", ""),
                "piso": r.get("piso", ""), "unidad": r.get("unidad", ""), "inquilino": r.get("inquilino", ""),
                "importe": importe_fmt, "archivo": r.get("archivo", ""),
            }
            for col, clave in enumerate(COLUMNAS_HISTORIAL):
                if clave == "sel":
                    contenedor, casilla = self._crear_casilla_mail()
                    self.tabla.setCellWidget(fila, col, contenedor)
                    self._casillas_por_fila[fila] = casilla
                else:
                    item = QTableWidgetItem(valores[clave])
                    centrado = clave in ("numero_recibo", "piso", "unidad", "importe")
                    item.setTextAlignment(Qt.AlignCenter if centrado else Qt.AlignVCenter)
                    self.tabla.setItem(fila, col, item)
            self._archivo_por_fila[fila] = r.get("archivo", "")
            self._filas_por_fila[fila] = r
        self.tabla.resizeRowsToContents()


# ===========================================================================
# Ventana: recibos recién generados
# ===========================================================================

COLUMNAS_GENERADOS = ("sel", "numero_recibo", "tipo", "unidad", "inquilino", "importe", "gastos_de", "archivo")
TITULOS_GENERADOS = {"sel": "ENVIAR", "numero_recibo": "N°", "tipo": "Tipo", "unidad": "Unidad", "inquilino": "Inquilino",
                     "importe": "Importe", "gastos_de": "Gastos de", "archivo": "Archivo"}
ANCHOS_GENERADOS = {"sel": 65, "numero_recibo": 55, "tipo": 80, "unidad": 150, "inquilino": 130,
                    "importe": 90, "gastos_de": 110, "archivo": 220}


class VentanaRecibosGenerados(_AbreRecibosMixin, _EnviarPorMailMixin, QDialog):
    """Lista de los PDF que se acaban de generar, para abrirlos o mandarlos por mail desde ahí."""

    def __init__(self, parent, generados, total, errores=()):
        """generados: lista de (registro_historial, etiqueta_unidad)."""
        super().__init__(parent)
        self.setWindowTitle("Recibos generados")
        self.setModal(True)
        self.resize(960, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        titulo = QLabel(f"Se generaron {len(generados)} de {total} recibo(s).")
        titulo.setStyleSheet(f"color: {COLOR_TEXTO}; font-weight: 700; background: transparent;")
        layout.addWidget(titulo)

        self.tabla = QTableWidget(0, len(COLUMNAS_GENERADOS))
        self.tabla.setObjectName("listaSimple")
        self.tabla.setHorizontalHeaderLabels([TITULOS_GENERADOS[c] for c in COLUMNAS_GENERADOS])
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setShowGrid(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(30)
        self.tabla.horizontalHeader().setFixedHeight(32)
        for col, clave in enumerate(COLUMNAS_GENERADOS):
            self.tabla.setColumnWidth(col, ANCHOS_GENERADOS[clave])
        self.tabla.horizontalHeader().setSectionResizeMode(COLUMNAS_GENERADOS.index("archivo"), QHeaderView.Stretch)
        self.tabla.doubleClicked.connect(lambda _i: self._abrir_pdf_seleccionado())
        layout.addWidget(self.tabla, 1)

        self._archivo_por_fila = {}
        self._filas_por_fila = {}
        self._casillas_por_fila = {}
        self.tabla.setRowCount(len(generados))
        for fila, (r, etiqueta) in enumerate(generados):
            valores = {
                "numero_recibo": r["numero_recibo"], "tipo": r["tipo"], "unidad": etiqueta,
                "inquilino": r["inquilino"], "importe": format_currency_ar(parse_importe(r["importe"])),
                "gastos_de": r["gastos_de"], "archivo": r["archivo"],
            }
            for col, clave in enumerate(COLUMNAS_GENERADOS):
                if clave == "sel":
                    contenedor, casilla = self._crear_casilla_mail()
                    self.tabla.setCellWidget(fila, col, contenedor)
                    self._casillas_por_fila[fila] = casilla
                else:
                    item = QTableWidgetItem(valores[clave])
                    centrado = clave in ("numero_recibo", "importe")
                    item.setTextAlignment(Qt.AlignCenter if centrado else Qt.AlignVCenter)
                    self.tabla.setItem(fila, col, item)
            self._archivo_por_fila[fila] = r["archivo"]
            self._filas_por_fila[fila] = r
        self.tabla.resizeRowsToContents()

        if errores:
            lbl_errores = QLabel("Unidades con error:\n" + "\n".join(errores))
            lbl_errores.setStyleSheet("color: #f87171; font-size: 11px; background: transparent;")
            lbl_errores.setWordWrap(True)
            layout.addWidget(lbl_errores)

        pie = QHBoxLayout()
        boton_abrir = QPushButton("Abrir PDF")
        boton_abrir.setObjectName("botonAcento")
        boton_abrir.clicked.connect(self._abrir_pdf_seleccionado)
        boton_carpeta = QPushButton("Mostrar en carpeta")
        boton_carpeta.clicked.connect(self._mostrar_en_carpeta)
        boton_todas = QPushButton("Seleccionar todas")
        boton_todas.clicked.connect(self._seleccionar_todas_mail)
        boton_ninguna = QPushButton("Quitar todas")
        boton_ninguna.clicked.connect(self._quitar_todas_mail)
        boton_enviar = QPushButton("Enviar por mail")
        boton_enviar.setStyleSheet("background-color: #16a34a; color: white; border: none;")
        boton_enviar.clicked.connect(self._enviar_por_mail)
        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.clicked.connect(self.reject)
        for b in (boton_abrir, boton_carpeta, boton_todas, boton_ninguna, boton_enviar):
            pie.addWidget(b)
        pie.addStretch()
        pie.addWidget(boton_cerrar)
        layout.addLayout(pie)

        if generados:
            self.tabla.selectRow(0)

    def _crear_casilla_mail(self):
        contenedor = QWidget()
        contenedor.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(contenedor)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch()
        casilla = QCheckBox()
        casilla.setCursor(Qt.PointingHandCursor)
        lay.addWidget(casilla)
        lay.addStretch()
        return contenedor, casilla


# ===========================================================================
# Ventana: ayuda para generar recibos
# ===========================================================================

class VentanaAyudaRecibos(QDialog):
    """Guía de cómo usar el programa para generar los recibos y enviarlos por mail (día a día,
    no incluye la parte de Administrar). Con ejemplos armados como se verían en pantalla: la
    tabla de la pantalla principal y la planilla de pagos."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Ayuda - Recibo de expensas")
        self.setModal(True)
        self.resize(820, 680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        contenedor = QWidget()
        self._cont = QVBoxLayout(contenedor)
        self._cont.setContentsMargins(24, 20, 24, 20)
        self._cont.setSpacing(2)
        area.setWidget(contenedor)
        layout.addWidget(area, 1)

        self._armar_contenido()

        pie = QHBoxLayout()
        pie.setContentsMargins(20, 10, 20, 16)
        pie.addStretch()
        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.clicked.connect(self.reject)
        pie.addWidget(boton_cerrar)
        layout.addLayout(pie)

    # -----------------------------------------------------------------
    # Helpers de texto
    # -----------------------------------------------------------------

    def _titulo(self, texto):
        lbl = QLabel(texto)
        lbl.setStyleSheet(f"color: {COLOR_ACENTO}; font-size: 18px; font-weight: 700; background: transparent;")
        self._cont.addWidget(lbl)
        self._cont.addSpacing(6)

    def _seccion(self, texto):
        lbl = QLabel(texto)
        lbl.setStyleSheet(f"color: {COLOR_ACENTO}; font-size: 13px; font-weight: 700; background: transparent;")
        self._cont.addSpacing(12)
        self._cont.addWidget(lbl)

    def _parrafo(self, texto):
        lbl = QLabel(texto)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {COLOR_TEXTO}; font-size: 12px; background: transparent;")
        self._cont.addWidget(lbl)

    # -----------------------------------------------------------------
    # Ejemplos armados con widgets reales (no solo texto)
    # -----------------------------------------------------------------

    def _ejemplo_pantalla(self):
        """Una fila como la de la pantalla principal, con datos de ejemplo."""
        tabla = QTableWidget(1, len(COLUMNAS))
        tabla.setObjectName("listaSimple")
        tabla.setHorizontalHeaderLabels([TITULOS[c] for c in COLUMNAS])
        tabla.setSelectionMode(QAbstractItemView.NoSelection)
        tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tabla.setFocusPolicy(Qt.NoFocus)
        tabla.verticalHeader().setVisible(False)
        tabla.verticalHeader().setDefaultSectionSize(34)
        tabla.horizontalHeader().setFixedHeight(28)
        tabla.setFixedHeight(28 + 34 + 4)
        for col, clave in enumerate(COLUMNAS):
            tabla.setColumnWidth(col, ANCHOS[clave])

        valores = {
            "tipo": "DEPTO", "piso": "1°", "unidad": "A", "uf": "12", "depto": "con Cochera 6",
            "dueno": "Pedro Gómez", "inquilino": "María Ruiz", "importe": format_currency_ar(45000),
        }
        for col, clave in enumerate(COLUMNAS):
            if clave == "sel":
                _contenedor, casilla = App._crear_casilla_demo()
                casilla.setChecked(True)
                tabla.setCellWidget(0, col, _contenedor)
            elif clave == "emitido":
                bg, fg = CHIP_EMITIDO
                tabla.setCellWidget(0, col, App._crear_chip("Emitido", bg, fg))
            elif clave == "estado":
                bg, fg = CHIP_ESTADO["total"]
                tabla.setCellWidget(0, col, App._crear_chip("Total", bg, fg))
            else:
                item = QTableWidgetItem(valores.get(clave, ""))
                item.setTextAlignment(Qt.AlignCenter if clave not in ("dueno", "inquilino") else Qt.AlignVCenter)
                tabla.setItem(0, col, item)
        self._cont.addWidget(tabla)
        self._cont.addSpacing(10)

    def _tabla_leyenda(self, filas):
        """Tabla de dos columnas: nombre de columna -> qué significa."""
        marco = QGridLayout()
        marco.setHorizontalSpacing(0)
        marco.setVerticalSpacing(0)
        for fila, (nombre, explicacion) in enumerate(filas):
            lbl_nombre = QLabel(nombre)
            lbl_nombre.setWordWrap(True)
            lbl_nombre.setStyleSheet(
                f"background-color: {COLOR_TARJETA_ALT}; color: {COLOR_ACENTO}; font-weight: 700; "
                f"border: 1px solid {COLOR_BORDE}; padding: 6px 8px;")
            lbl_explicacion = QLabel(explicacion)
            lbl_explicacion.setWordWrap(True)
            lbl_explicacion.setStyleSheet(
                f"background-color: {COLOR_TARJETA_ALT}; color: {COLOR_TEXTO}; "
                f"border: 1px solid {COLOR_BORDE}; padding: 6px 8px;")
            marco.addWidget(lbl_nombre, fila, 0)
            marco.addWidget(lbl_explicacion, fila, 1)
        marco.setColumnStretch(0, 0)
        marco.setColumnStretch(1, 1)
        marco.setColumnMinimumWidth(0, 150)
        self._cont.addLayout(marco)
        self._cont.addSpacing(12)

    def _ejemplo_planilla(self):
        """La planilla de pagos de un edificio, con una fila de ejemplo por cada estado posible."""
        encabezados = ("Unidad", "Total a pagar", "Monto deuda", "Monto pagado", "Tipo pago")
        filas = [
            ("1° A", "45.000", "0", "45.000", "total"),
            ("1° B", "40.000", "5.000", "30.000", "a cta"),
            ("PB A", "38.000", "38.000", "38.000", "deuda"),
            ("2° A", "42.000", "0", "0", "no pagado"),
        ]
        marco = QGridLayout()
        marco.setSpacing(0)
        for c, texto in enumerate(encabezados):
            lbl = QLabel(texto)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                f"background-color: {COLOR_ACENTO}; color: white; font-weight: 700; "
                f"border: 1px solid {COLOR_BORDE}; padding: 6px 10px;")
            marco.addWidget(lbl, 0, c)
        for f, (unidad, total, deuda, pagado, tipo) in enumerate(filas, start=1):
            _bg, fg = CHIP_ESTADO.get(tipo, CHIP_ESTADO_DEFECTO)
            valores = (unidad, f"$ {total}", f"$ {deuda}", f"$ {pagado}", tipo.upper())
            for c, valor in enumerate(valores):
                lbl = QLabel(valor)
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setStyleSheet(
                    f"background-color: {COLOR_TARJETA_ALT}; color: {fg if c == 4 else COLOR_TEXTO}; "
                    f"border: 1px solid {COLOR_BORDE}; padding: 6px 10px;")
                marco.addWidget(lbl, f, c)
        for c in range(5):
            marco.setColumnStretch(c, 1)
        self._cont.addLayout(marco)
        self._cont.addSpacing(6)

    # -----------------------------------------------------------------
    # Contenido
    # -----------------------------------------------------------------

    def _armar_contenido(self):
        self._titulo("Recibo de expensas: guía rápida")
        self._parrafo("Estos son los pasos para generar los recibos en PDF de un edificio ya "
                      "cargado, y mandarlos por mail.")

        self._seccion("1. Elegir el edificio")
        self._parrafo("La lista «Edificios», a la izquierda de la pantalla principal, lista los "
                      "edificios ya cargados. Al elegir uno, la tabla de al lado se llena sola "
                      "con todas sus unidades.")

        self._seccion("2. La pantalla principal: un ejemplo")
        self._parrafo("Cada fila es una unidad. Esta es una fila de ejemplo: un departamento "
                      "1° A que ya emitió su recibo, con su cochera incluida en el mismo importe.")
        self._ejemplo_pantalla()
        self._tabla_leyenda([
            ("EMITIDO", "El chip de la izquierda de todo: verde si el recibo de esa unidad ya se "
                        "generó para el período actual, rojo si todavía no."),
            ("TIPO / PISO /\nLETRA-N° / UF", "Identifican la unidad."),
            ("RELACIÓN", "En una cochera o baulera de un depto, de qué depto es (de 1° A). En un "
                         "depto que incluye alguna en su recibo, cuáles (con Cochera 6)."),
            ("DUEÑO / INQUILINO /\nIMPORTE", "Datos de la unidad y monto del recibo."),
            ("PAGO", "El estado según la planilla de pagos: Total, A cta., Deuda, No pagado, o Sin "
                     "celda si esa unidad todavía no tiene asignada una celda en la planilla."),
            ("EMITIR", "La casilla, al final de todo: para tildar qué unidades generar."),
        ])

        self._seccion("3. La planilla de pagos: un ejemplo")
        self._parrafo("Cada edificio tiene su propia planilla en Excel («Abrir planilla de "
                      "pagos»). Se completan, por unidad, Total a pagar, Monto deuda y Monto "
                      "pagado; el Tipo pago sale solo, según cuánto se pagó:")
        self._ejemplo_planilla()
        self._parrafo("Total: lo pagado cubre el total más la deuda. A cta.: pagó una parte. "
                      "Deuda: pagó justo la deuda que traía (nada del mes actual). No pagado: "
                      "no pagó nada. Después de completar la planilla hay que guardarla "
                      "(Ctrl+G) y cerrarla, para que el programa pueda leerla.")

        self._seccion("4. Generar los recibos")
        self._parrafo("Con el edificio elegido y la planilla ya cargada:\n"
                      "• Tildar las unidades en la columna EMITIR (o «Seleccionar todas»).\n"
                      "• «Actualizar montos desde planilla», para traer lo que se cargó en el Excel.\n"
                      "• «Generar recibos PDF». Se genera un PDF por cada unidad tildada.")

        self._seccion("5. Ver y abrir los recibos generados")
        self._parrafo("Al terminar se abre una lista con los recibos recién hechos: «Abrir "
                      "PDF» (o doble clic) y «Mostrar en carpeta». Cualquier recibo generado "
                      "antes, de otro día, está en Ver → Historial de recibos.")

        self._seccion("6. Enviar los recibos por mail")
        self._parrafo("Tanto en esa lista como en el Historial, cada fila tiene una casilla en "
                      "la columna ENVIAR.\n"
                      "• Tildar los recibos a enviar (o «Seleccionar todas» / «Quitar todas»).\n"
                      "• «Enviar por mail»: manda cada recibo, en PDF, a las direcciones "
                      "cargadas para esa unidad. Al terminar muestra cuántos se enviaron y el "
                      "detalle de los que fallaron.")


# ===========================================================================
# Ventana: cargar desde backup
# ===========================================================================

class VentanaCargarBackup(QDialog):
    """Elige un backup (de backups/ o cualquier .zip) y lo carga, reemplazando los datos actuales."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Cargar desde backup")
        self.setModal(True)
        self.resize(660, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Backups guardados:"))

        self.tabla = QTableWidget(0, 3)
        self.tabla.setObjectName("listaSimple")
        self.tabla.setHorizontalHeaderLabels(["Archivo", "Fecha", "Tamaño"])
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setShowGrid(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabla.setColumnWidth(1, 150)
        self.tabla.setColumnWidth(2, 90)

        self._rutas_por_fila = {}
        backups = database.listar_backups()
        self.tabla.setRowCount(len(backups))
        for fila, ruta in enumerate(backups):
            info = os.stat(ruta)
            valores = (
                os.path.basename(ruta),
                datetime.fromtimestamp(info.st_mtime).strftime("%d/%m/%Y %H:%M"),
                f"{info.st_size // 1024} KB",
            )
            for col, valor in enumerate(valores):
                self.tabla.setItem(fila, col, QTableWidgetItem(valor))
            self._rutas_por_fila[fila] = ruta
        layout.addWidget(self.tabla, 1)

        if not backups:
            nota = QLabel("Todavía no hay backups en la carpeta backups/.")
            nota.setStyleSheet(f"color: {COLOR_TEXTO_SUAVE}; font-size: 11px; background: transparent;")
            layout.addWidget(nota)

        pie = QHBoxLayout()
        boton_cargar = QPushButton("Cargar seleccionado")
        boton_cargar.setObjectName("botonAcento")
        boton_cargar.clicked.connect(self._cargar_seleccionado)
        boton_elegir = QPushButton("Elegir otro archivo...")
        boton_elegir.clicked.connect(self._elegir_archivo)
        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.clicked.connect(self.reject)
        pie.addWidget(boton_cargar)
        pie.addWidget(boton_elegir)
        pie.addStretch()
        pie.addWidget(boton_cerrar)
        layout.addLayout(pie)

    def _cargar_seleccionado(self):
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            QMessageBox.warning(self, "Cargar backup", "Elegí un backup de la lista.")
            return
        self._confirmar_y_cargar(self._rutas_por_fila[filas[0].row()])

    def _elegir_archivo(self):
        ruta, _filtro = QFileDialog.getOpenFileName(
            self, "Elegir backup", "", "Backup de expensas (*.zip);;Todos los archivos (*.*)")
        if ruta:
            self._confirmar_y_cargar(ruta)

    def _confirmar_y_cargar(self, ruta):
        pregunta = ("Esto reemplaza los edificios, unidades, historial y demás datos actuales por los del backup.\n\n"
                    "Antes se guarda una copia de los datos actuales, por si hace falta volver atrás.\n\n"
                    "La contraseña maestra y la configuración SMTP NO se tocan.\n\n"
                    "¿Cargar este backup?")
        if QMessageBox.question(self, "Cargar backup", pregunta) != QMessageBox.Yes:
            return

        try:
            copia_previa = database.crear_backup()
        except Exception as e:
            manejar_error("No se pudo guardar la copia previa; no se cargó nada", e, self)
            return

        try:
            cantidad = database.restaurar_backup(ruta)
        except ValueError as e:
            QMessageBox.critical(self, "Cargar backup", str(e))
            return
        except Exception as e:
            manejar_error("No se pudo cargar el backup", e, self)
            return

        QMessageBox.information(
            self, "Cargar backup",
            f"Se cargaron {cantidad} archivos del backup.\n\n"
            f"La copia de los datos anteriores quedó en:\n{copia_previa}")
        self.parent()._cargar_edificios()
        self.accept()


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        # Con el estilo nativo de Windows, controles como la flechita del combo se dibujan
        # con bitmaps oscuros fijos que quedan invisibles sobre un fondo oscuro. Fusion los
        # dibuja con los colores de la paleta/QSS, así que se ven bien en modo oscuro.
        QApplication.setStyle("Fusion")
        # Fusion pinta el resaltado de hover/selección de listas con QPalette.Highlight,
        # ignorando el color que le pongamos por QSS a ::item:hover - hay que cambiar la
        # paleta directamente para que ese resaltado salga azul en vez de gris.
        paleta = QApplication.palette()
        paleta.setColor(QPalette.Highlight, QColor(COLOR_ACENTO))
        paleta.setColor(QPalette.HighlightedText, QColor("white"))
        QApplication.setPalette(paleta)
        # Oscurece la barra de título nativa de esta ventana y de cualquier diálogo que se
        # abra después (Administrar, Configuración, etc.), para que no quede blanca arriba
        # de todo el contenido oscuro. Hay que guardar la referencia: si no, Python la
        # destruye enseguida y el filtro deja de funcionar.
        self._oscurecedor_barra_titulo = _OscurecedorBarraTitulo(self)
        QApplication.instance().installEventFilter(self._oscurecedor_barra_titulo)
        self.setWindowTitle(config.APP_TITULO)
        self.resize(1260, 680)
        self.setMinimumSize(1100, 580)
        self.setFont(QFont("Segoe UI", 10))
        self.setStyleSheet(ESTILO)

        self.seleccionadas = set()       # ids de unidades marcadas
        self._unidades_por_id = {}       # id de unidad -> dict de la unidad
        self._fila_por_id = {}           # id de unidad -> índice de fila en la tabla
        self._casillas_por_id = {}       # id de unidad -> QCheckBox de la columna EMITIR

        self._crear_menu()
        self._crear_widgets()
        self._cargar_edificios()

    # -----------------------------------------------------------------
    # Construcción de la interfaz
    # -----------------------------------------------------------------

    def _crear_menu(self):
        menu_archivo = self.menuBar().addMenu("Archivo")
        accion_backup = QAction("Copia de seguridad (backup)", self)
        accion_backup.triggered.connect(self._hacer_backup)
        menu_archivo.addAction(accion_backup)
        accion_cargar_backup = QAction("Cargar desde backup...", self)
        accion_cargar_backup.triggered.connect(self._abrir_cargar_backup)
        menu_archivo.addAction(accion_cargar_backup)
        menu_archivo.addSeparator()
        accion_salir = QAction("Salir", self)
        accion_salir.triggered.connect(self.close)
        menu_archivo.addAction(accion_salir)

        menu_admin = self.menuBar().addMenu("Administrar")
        accion_administrar = QAction("Administrar edificios/unidades", self)
        accion_administrar.triggered.connect(self._abrir_administracion)
        menu_admin.addAction(accion_administrar)
        accion_config = QAction("Configuración de la inmobiliaria", self)
        accion_config.triggered.connect(self._abrir_configuracion)
        menu_admin.addAction(accion_config)
        accion_mailing = QAction("Mailing", self)
        accion_mailing.triggered.connect(self._abrir_mails)
        menu_admin.addAction(accion_mailing)
        menu_admin.addSeparator()
        accion_maestro = QAction("Control maestro", self)
        accion_maestro.triggered.connect(self._abrir_control_maestro)
        menu_admin.addAction(accion_maestro)

        menu_ver = self.menuBar().addMenu("Ver")
        accion_hist_recibos = QAction("Historial de recibos", self)
        accion_hist_recibos.triggered.connect(self._abrir_historial)
        menu_ver.addAction(accion_hist_recibos)
        accion_hist_mails = QAction("Historial de mails", self)
        accion_hist_mails.triggered.connect(self._abrir_historial_mails)
        menu_ver.addAction(accion_hist_mails)

        menu_ayuda = self.menuBar().addMenu("Ayuda")
        accion_ayuda_recibos = QAction("Recibo expensas", self)
        accion_ayuda_recibos.triggered.connect(self._mostrar_ayuda_recibos)
        menu_ayuda.addAction(accion_ayuda_recibos)
        accion_acerca_de = QAction("Acerca de", self)
        accion_acerca_de.triggered.connect(self._mostrar_acerca_de)
        menu_ayuda.addAction(accion_acerca_de)

    def _abrir_control_maestro(self):
        VentanaControlMaestro(self).show()

    def _abrir_administracion(self):
        def al_cambiar(edificio):
            self._cargar_edificios()
            coincidencias = self.lista_edificios.findItems(edificio, Qt.MatchExactly)
            if coincidencias:
                self.lista_edificios.setCurrentItem(coincidencias[0])

        def abrir():
            VentanaAdministracion(self, self._edificio_actual(), on_cambios=al_cambiar).show()

        requerir_maestro(self, abrir, motivo="abrir Administrar edificios y unidades")

    def _abrir_configuracion(self):
        def abrir():
            dialogo = VentanaConfiguracion(self)
            dialogo.accepted.connect(self._cargar_logo_inmobiliaria)
            dialogo.show()

        requerir_maestro(self, abrir, motivo="abrir la Configuración de la inmobiliaria")

    def _abrir_mails(self):
        requerir_maestro(
            self, lambda: VentanaMails(self, self._edificio_actual()).show(), motivo="abrir Mailing")

    def _abrir_historial(self):
        VentanaHistorial(self).show()

    def _abrir_historial_mails(self):
        VentanaRegistroEnvios(self, self._edificio_actual()).show()

    def _abrir_cargar_backup(self):
        requerir_maestro(self, lambda: VentanaCargarBackup(self).show(), motivo="cargar un backup")

    def _hacer_backup(self):
        try:
            ruta = database.crear_backup()
        except Exception as e:
            manejar_error("No se pudo crear la copia de seguridad", e, self)
            return

        QMessageBox.information(
            self, "Copia de seguridad",
            f"Backup creado correctamente en:\n\n{ruta}\n\n"
            "No incluye la contraseña maestra, la configuración SMTP ni los PDF de los recibos.")

        confirmado = QMessageBox.question(
            self, "Copia de seguridad",
            "¿Guardar también una copia en otro lugar (un pendrive, una carpeta en la nube, etc.)?")
        if confirmado != QMessageBox.Yes:
            return
        destino, _filtro = QFileDialog.getSaveFileName(
            self, "Guardar copia del backup", os.path.basename(ruta), "Backup (*.zip)")
        if not destino:
            return
        try:
            shutil.copy(ruta, destino)
            QMessageBox.information(self, "Copia de seguridad", f"Copia guardada en:\n\n{destino}")
        except Exception as e:
            manejar_error("No se pudo guardar la copia en ese lugar", e, self)

    def _mostrar_ayuda_recibos(self):
        VentanaAyudaRecibos(self).show()

    def _mostrar_acerca_de(self):
        QMessageBox.information(
            self, "Acerca de",
            f"{config.APP_TITULO}\nVersión {config.APP_VERSION}\n\n"
            "Aplicación de escritorio offline para la gestión de expensas.\n"
            f"Carpeta de datos:\n{config.BASE_DIR}")

    def closeEvent(self, event):
        """Al cerrar (la X o Archivo → Salir): backup automático y silencioso, sin preguntar nada."""
        try:
            database.crear_backup(automatico=True)
        except Exception as e:
            logger.exception("No se pudo hacer la copia de seguridad automática al cerrar")
            confirmado = QMessageBox.question(
                self, "Copia de seguridad automática",
                f"No se pudo hacer la copia de seguridad automática al cerrar:\n\n{e}\n\n"
                "¿Cerrar igual, sin esa copia?")
            if confirmado != QMessageBox.Yes:
                event.ignore()
                return
        event.accept()

    def _pendiente(self, nombre):
        QMessageBox.information(self, nombre, "Todavía no está portado a esta versión de prueba (PySide6).")

    def _crear_widgets(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        franja = QWidget()
        franja.setObjectName("franjaColor")
        franja.setFixedHeight(3)
        layout.addWidget(franja)

        # --- barra superior: título + subtítulo a la izquierda, logo de la inmobiliaria a la derecha ---
        barra = QWidget()
        barra.setObjectName("barraSuperior")
        barra_layout = QHBoxLayout(barra)
        barra_layout.setContentsMargins(24, 16, 24, 16)

        textos = QVBoxLayout()
        textos.setSpacing(2)
        titulo = QLabel("Sistema de Expensas")
        titulo.setObjectName("titulo")
        subtitulo = QLabel("Administración de consorcios")
        subtitulo.setObjectName("subtitulo")
        textos.addWidget(titulo)
        textos.addWidget(subtitulo)
        barra_layout.addLayout(textos)
        barra_layout.addStretch()

        self.logo_inmobiliaria = QLabel()
        self.logo_inmobiliaria.setFixedHeight(48)
        barra_layout.addWidget(self.logo_inmobiliaria)
        self._cargar_logo_inmobiliaria()

        layout.addWidget(barra)

        cuerpo = QHBoxLayout()
        cuerpo.setContentsMargins(0, 0, 0, 0)
        cuerpo.setSpacing(0)
        layout.addLayout(cuerpo, 1)

        self._crear_sidebar(cuerpo)
        self._crear_contenido(cuerpo)

    def _crear_sidebar(self, cuerpo):
        self.lista_edificios = _crear_sidebar_edificios(cuerpo, [], self._cargar_unidades)

    def _edificio_actual(self):
        item = self.lista_edificios.currentItem()
        return item.text() if item else ""

    def _cargar_logo_inmobiliaria(self):
        """Logo de la inmobiliaria (Configuración de la inmobiliaria) arriba a la derecha, si hay uno cargado."""
        ruta = database.imagen_inmobiliaria("logo")
        if not ruta:
            self.logo_inmobiliaria.clear()
            return
        pixmap = QPixmap(ruta)
        if not pixmap.isNull():
            self.logo_inmobiliaria.setPixmap(
                pixmap.scaledToHeight(48, Qt.SmoothTransformation))

    def _crear_contenido(self, cuerpo):
        contenedor = QWidget()
        contenido = QVBoxLayout(contenedor)
        contenido.setContentsMargins(24, 20, 24, 20)
        contenido.setSpacing(16)
        cuerpo.addWidget(contenedor, 1)

        # --- fila superior: nombre del edificio elegido + acción secundaria ---
        fila_superior = QHBoxLayout()
        fila_superior.setSpacing(10)
        self.titulo_edificio = QLabel("")
        self.titulo_edificio.setStyleSheet(f"color: {COLOR_TEXTO}; font-size: 18px; font-weight: 700; background: transparent;")
        fila_superior.addWidget(self.titulo_edificio)
        fila_superior.addStretch()
        boton_actualizar = QPushButton("Actualizar montos desde planilla")
        boton_actualizar.setObjectName("botonAcento")
        boton_actualizar.setCursor(Qt.PointingHandCursor)
        boton_actualizar.clicked.connect(self._actualizar_desde_planilla)
        fila_superior.addWidget(boton_actualizar)
        contenido.addLayout(fila_superior)

        # --- tabla de unidades ---
        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels([TITULOS[c] for c in COLUMNAS])
        self.tabla.setSelectionMode(QAbstractItemView.NoSelection)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setFocusPolicy(Qt.NoFocus)
        self.tabla.setShowGrid(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(34)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tabla.horizontalHeader().setStretchLastSection(False)
        self.tabla.horizontalHeader().setFixedHeight(34)
        for columna, clave in enumerate(COLUMNAS):
            self.tabla.setColumnWidth(columna, ANCHOS[clave])
        for clave in ("dueno", "inquilino"):
            self.tabla.horizontalHeader().setSectionResizeMode(COLUMNAS.index(clave), QHeaderView.Stretch)
        contenido.addWidget(self.tabla, 1)

        # --- pie: acciones secundarias a la izquierda, acción principal a la derecha ---
        pie = QHBoxLayout()
        pie.setSpacing(10)
        boton_todas = QPushButton("Seleccionar todas")
        boton_todas.setCursor(Qt.PointingHandCursor)
        boton_todas.clicked.connect(self._seleccionar_todas)
        boton_ninguna = QPushButton("Quitar todas")
        boton_ninguna.setCursor(Qt.PointingHandCursor)
        boton_ninguna.clicked.connect(self._quitar_todas)
        boton_planilla = QPushButton("Abrir planilla de pagos")
        boton_planilla.setCursor(Qt.PointingHandCursor)
        boton_planilla.clicked.connect(self._abrir_planilla_pagos)
        pie.addWidget(boton_todas)
        pie.addWidget(boton_ninguna)
        pie.addWidget(boton_planilla)
        pie.addStretch()
        boton_generar = QPushButton("Generar recibos PDF")
        boton_generar.setObjectName("botonPrimario")
        boton_generar.setCursor(Qt.PointingHandCursor)
        boton_generar.clicked.connect(self._generar_recibos)
        pie.addWidget(boton_generar)
        contenido.addLayout(pie)

    # -----------------------------------------------------------------
    # Carga de datos en pantalla
    # -----------------------------------------------------------------

    def _cargar_edificios(self):
        try:
            database.ensure_data_files()
            mostrar_avisos(self)
            nombres = database.get_nombres_edificios()
            self.lista_edificios.blockSignals(True)
            self.lista_edificios.clear()
            self.lista_edificios.addItems(nombres)
            self.lista_edificios.blockSignals(False)
            if nombres:
                self.lista_edificios.setCurrentRow(0)
                self._cargar_unidades()
        except Exception as e:
            manejar_error("Error al iniciar", e, self)

    def _estados_planilla(self, edificio):
        unidades = database.get_unidades_por_edificio(edificio)
        try:
            estados = {uid: d["estado"] for uid, d in pagos.leer_planilla(edificio, unidades).items()}
        except Exception:
            estados = {}
        if pagos.modo_celdas(unidades):
            estados.update({u["id"]: "SIN_CELDA" for u in unidades if not u["celda"] and not incluida_en_total(u)})
        return estados

    @staticmethod
    def _estado_fila(u, agrupadas, estados):
        if agrupadas:
            miembros = [estados.get(m["id"]) for m in [u] + list(agrupadas)]
            if "SIN_CELDA" in miembros:
                return "SIN_CELDA"
            return pagos.estado_agregado(miembros) or ""
        return estados.get(u["id"], "")

    def _claves_emitidas(self, edificio):
        expensas_de = obtener_periodos()[0]
        try:
            historial = database.get_historial()
        except Exception:
            return set()
        return {(r.get("piso") or "", r.get("tipo") or "", (r.get("unidad") or "").split(" + ")[0])
                for r in historial if r.get("edificio") == edificio and r.get("expensas_de") == expensas_de}

    def _crear_item(self, texto, color=None, centrado=True, negrita=False):
        item = QTableWidgetItem(texto)
        if centrado:
            item.setTextAlignment(Qt.AlignCenter)
        if color:
            item.setForeground(QColor(color))
        if negrita:
            fuente = item.font()
            fuente.setBold(True)
            item.setFont(fuente)
        return item

    @staticmethod
    def _crear_chip(texto, bg, fg):
        """Badge coloreado y redondeado (ej. 'Total', 'Emitido') centrado en la celda."""
        contenedor = QWidget()
        contenedor.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        chip = QLabel(texto)
        chip.setAlignment(Qt.AlignCenter)
        chip.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border-radius: 9px; "
            f"padding: 3px 10px; font-size: 11px; font-weight: 600;"
        )
        layout.addWidget(chip)
        layout.addStretch()
        return contenedor

    @staticmethod
    def _crear_casilla_demo():
        """Checkbox centrado, sin conectar a nada (para los ejemplos de VentanaAyudaRecibos)."""
        contenedor = QWidget()
        contenedor.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        casilla = QCheckBox()
        layout.addWidget(casilla)
        layout.addStretch()
        return contenedor, casilla

    def _crear_casilla(self, uid):
        """Checkbox centrado en la celda (el checkbox de un QTableWidgetItem se dibuja
        siempre pegado a la izquierda, así que se envuelve en un contenedor propio)."""
        contenedor = QWidget()
        contenedor.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        casilla = QCheckBox()
        casilla.setCursor(Qt.PointingHandCursor)
        casilla.stateChanged.connect(lambda _, u=uid, c=casilla: self._casilla_cambiada(u, c.isChecked()))
        layout.addWidget(casilla)
        layout.addStretch()
        self._casillas_por_id[uid] = casilla
        return contenedor

    def _casilla_cambiada(self, uid, marcado):
        (self.seleccionadas.add if marcado else self.seleccionadas.discard)(uid)

    def _cargar_unidades(self):
        self.tabla.setRowCount(0)
        self.seleccionadas.clear()
        self._unidades_por_id = {}
        self._fila_por_id = {}
        self._casillas_por_id = {}

        edificio = self._edificio_actual()
        self.titulo_edificio.setText(edificio)
        if not edificio:
            return

        try:
            todas = database.get_unidades_por_edificio(edificio)
            por_id = indice_por_id(todas)
            estados = self._estados_planilla(edificio)
            emitidos = self._claves_emitidas(edificio)
            filas = ordenar_para_pantalla(todas)
            self.tabla.setRowCount(len(filas))
            for fila, (u, nivel, agrupadas) in enumerate(filas):
                depto = depto_de(u, por_id)
                relacion = ("con " + descripcion_asociadas(agrupadas)) if agrupadas else \
                           (("de " + etiqueta_unidad(depto)) if depto else "")
                importe = sum(parse_importe(m["importe"]) for m in [u] + list(agrupadas) if not incluida_en_total(m))
                estado = self._estado_fila(u, agrupadas, estados)
                bg_estado, fg_estado = CHIP_ESTADO.get(pagos._norm(estado), CHIP_ESTADO_DEFECTO)
                emitido = (u["piso"], normalizar_tipo(u["tipo"]), u["unidad"]) in emitidos

                valores = {
                    "tipo": normalizar_tipo(u["tipo"]), "piso": u["piso"],
                    "unidad": ("↳ " if nivel else "") + u["unidad"], "uf": u["uf"], "depto": relacion,
                    "dueno": u["dueno"], "inquilino": u["inquilino"], "importe": format_currency_ar(importe),
                }
                for col, clave in enumerate(COLUMNAS):
                    if clave == "sel":
                        self.tabla.setCellWidget(fila, col, self._crear_casilla(u["id"]))
                    elif clave == "emitido":
                        bg, fg = CHIP_EMITIDO if emitido else CHIP_PENDIENTE
                        self.tabla.setCellWidget(fila, col, self._crear_chip("Emitido" if emitido else "Pendiente", bg, fg))
                    elif clave == "estado":
                        self.tabla.setCellWidget(fila, col, self._crear_chip(estado or "—", bg_estado, fg_estado))
                    else:
                        item = self._crear_item(valores[clave], None, centrado=clave not in ("dueno", "inquilino"))
                        self.tabla.setItem(fila, col, item)

                self._unidades_por_id[u["id"]] = u
                self._fila_por_id[u["id"]] = fila
            self.tabla.resizeRowsToContents()
        except Exception as e:
            manejar_error("No se pudieron cargar las unidades", e, self)

    def _recargar_unidades(self):
        previas = set(self.seleccionadas)
        self._cargar_unidades()
        for uid in previas:
            casilla = self._casillas_por_id.get(uid)
            if casilla is not None:
                casilla.setChecked(True)

    # -----------------------------------------------------------------
    # Selección de filas
    # -----------------------------------------------------------------

    def _seleccionar_todas(self):
        for casilla in self._casillas_por_id.values():
            casilla.setChecked(True)

    def _quitar_todas(self):
        for casilla in self._casillas_por_id.values():
            casilla.setChecked(False)

    # -----------------------------------------------------------------
    # Planilla de pagos
    # -----------------------------------------------------------------

    def _confirmar_planilla_guardada(self, edificio):
        if not pagos.planilla_abierta(edificio):
            return True
        return QMessageBox.question(
            self, "Planilla de pagos abierta",
            "La planilla de pagos de este edificio está abierta en Excel.\n\n"
            "Lo que hayas escrito y NO guardado todavía no se tiene en cuenta. "
            "Guardala (Ctrl+G) y, si podés, cerrala.\n\n¿Querés continuar igual?",
        ) == QMessageBox.Yes

    def _actualizar_desde_planilla(self):
        edificio = self._edificio_actual()
        if not edificio:
            QMessageBox.warning(self, "Atención", "Seleccioná un edificio.")
            return
        if not self._confirmar_planilla_guardada(edificio):
            return
        try:
            database.sincronizar_pagos(edificio)
        except PermissionError:
            pass
        except Exception as e:
            manejar_error("No se pudo preparar la planilla de pagos", e, self)
            return
        try:
            unidades = database.get_unidades_por_edificio(edificio)
            planilla = pagos.leer_planilla(edificio, unidades)
            database.set_importes({u["id"]: planilla[u["id"]]["pagado"] for u in unidades if u["id"] in planilla})
        except Exception as e:
            manejar_error("No se pudieron actualizar los montos desde la planilla", e, self)
            return

        self._recargar_unidades()
        actualizadas = sum(1 for u in unidades if u["id"] in planilla)
        sin_fila = [etiqueta_unidad(u, indice_por_id(unidades)) for u in unidades
                    if u["id"] not in planilla and not incluida_en_total(u)]
        mensaje = f"Se actualizó el importe de {actualizadas} unidad(es) con el «Monto pagado» de la planilla."
        if sin_fila:
            mensaje += ("\n\nSin celda asignada: " if pagos.modo_celdas(unidades) else "\n\nNo figuran en la planilla: ") \
                + ", ".join(sin_fila)
        QMessageBox.information(self, "Montos actualizados", mensaje)

    def _abrir_planilla_pagos(self):
        edificio = self._edificio_actual()
        if not edificio:
            QMessageBox.warning(self, "Atención", "Seleccioná un edificio.")
            return
        ruta = pagos.ruta_pagos_edificio(edificio)
        unidades = database.get_unidades_por_edificio(edificio)
        faltaba = not os.path.isfile(ruta)
        try:
            if faltaba and pagos.modo_celdas(unidades):
                pagos.crear_planilla_en_blanco(edificio, unidades)
            else:
                database.sincronizar_pagos(edificio)
        except PermissionError:
            pass
        except Exception as e:
            manejar_error("No se pudo preparar la planilla de pagos", e, self)
            return
        if faltaba and os.path.isfile(ruta):
            QMessageBox.information(
                self, "Planilla de pagos",
                f"La planilla de «{edificio}» faltaba: se rearmó en blanco.\n\n"
                "Los montos anteriores no están: hay que cargarlos de nuevo.")
        ok, mensaje = abrir_pdf(ruta)
        if not ok:
            QMessageBox.information(self, "Planilla de pagos", mensaje)

    # -----------------------------------------------------------------
    # Generación de recibos
    # -----------------------------------------------------------------

    def _generar_recibos(self):
        edificio = self._edificio_actual()
        if not edificio:
            QMessageBox.warning(self, "Atención", "Seleccioná un edificio.")
            return

        seleccionadas = list(self.seleccionadas)
        if not seleccionadas:
            QMessageBox.warning(self, "Atención", "No hay unidades seleccionadas para generar recibos.")
            return

        expensas_de, mes_anterior = obtener_periodos()

        if not self._confirmar_planilla_guardada(edificio):
            return

        try:
            database.sincronizar_pagos(edificio)
        except PermissionError:
            pass
        except Exception as e:
            manejar_error("No se pudo preparar la planilla de pagos", e, self)
            return

        todas_edificio = database.get_unidades_por_edificio(edificio)
        try:
            planilla = pagos.leer_planilla(edificio, todas_edificio)
        except Exception as e:
            manejar_error("No se pudo leer la planilla de pagos del edificio", e, self)
            return
        estados_pagos = {uid: d["estado"] for uid, d in planilla.items()}

        por_id = indice_por_id(todas_edificio)
        con_celdas = pagos.modo_celdas(todas_edificio)
        unidades_actuales = {u["id"]: u for u in todas_edificio}
        hijas = asociadas_que_pagan_junto(todas_edificio)

        plan = []
        detalle = []
        sin_celda = []
        hay_diferencias = False
        for uid in seleccionadas:
            u = unidades_actuales.get(uid)
            if not u:
                continue
            agrupadas = hijas.get(uid, [])
            miembros = [u] + agrupadas
            if con_celdas and any(not m["celda"] for m in miembros if not incluida_en_total(m)):
                sin_celda.append(etiqueta_unidad(u, por_id) + (
                    f" (con {descripcion_asociadas(agrupadas)})" if agrupadas else ""))
                continue
            if agrupadas:
                estado = pagos.estado_agregado([estados_pagos.get(m["id"]) for m in miembros])
                texto = pagos.gastos_de_estado(estado, mes_anterior)
            else:
                texto, estado = pagos.gastos_de_unidad(estados_pagos, u, mes_anterior)
            importe = sum(parse_importe(m["importe"]) for m in miembros if not incluida_en_total(m))
            plan.append({"u": u, "agrupadas": agrupadas, "gastos_de": texto, "importe": importe, "estado": estado})

            etiqueta = etiqueta_unidad(u, por_id) + (f" (con {descripcion_asociadas(agrupadas)})" if agrupadas else "")
            nota = texto if estado else f"{texto}  (no figura en la planilla de pagos)"
            nota += f"  |  {format_currency_ar(importe)}"
            pagado = [planilla[m["id"]]["pagado"] for m in miembros if m["id"] in planilla]
            if pagado and abs(sum(pagado) - importe) > 0.005:
                nota += f"  ⚠ la planilla dice {format_currency_ar(sum(pagado))}"
                hay_diferencias = True
            detalle.append(f"  {etiqueta}: {nota}")

        if sin_celda and not plan:
            QMessageBox.warning(
                self, "Falta asignar celdas",
                "No se puede generar el recibo porque no se sabe cuánto pagó ni el tipo de pago: "
                "no tienen celda asignada en la planilla.\n\n  " + "\n  ".join(sin_celda[:15]) +
                "\n\nAsignala en Administrar → «Asignar celdas» (o editando la unidad).",
            )
            return

        max_lineas = 15
        resumen = "\n".join(detalle[:max_lineas])
        if len(detalle) > max_lineas:
            resumen += f"\n  ... y {len(detalle) - max_lineas} más"
        aviso_celdas = (
            "\n\nNO se generan (sin celda asignada en la planilla): " + ", ".join(sin_celda[:10])
            + (f" y {len(sin_celda) - 10} más" if len(sin_celda) > 10 else "")
        ) if sin_celda else ""
        aviso_montos = (
            "\n\n⚠ Hay importes distintos al «Monto pagado» de la planilla. Si querés usar los de la "
            "planilla, cancelá y apretá «Actualizar montos desde planilla»."
        ) if hay_diferencias else ""

        confirmar = QMessageBox.question(
            self, "Confirmar generación",
            f"Se van a generar {len(plan)} recibo(s) para:\n\n{edificio}\n\n"
            f"Expensas de: {expensas_de}\nGastos de (según la planilla de pagos) e importe:\n{resumen}"
            f"{aviso_montos}{aviso_celdas}\n\n¿Confirmás?",
        )
        if confirmar != QMessageBox.Yes:
            return

        try:
            inmobiliaria = database.get_inmobiliaria()
            datos_edificio = database.get_edificio(edificio) or {}
            carpeta_destino = database.crear_carpeta_edificio(edificio)

            generados = []
            errores = []

            for item in plan:
                u, agrupadas = item["u"], item["agrupadas"]
                gastos_de, importe_valor = item["gastos_de"], item["importe"]
                tipo = normalizar_tipo(u["tipo"])
                depto = depto_de(u, por_id)
                depto_etiqueta = etiqueta_unidad(depto) if depto else ""
                sufijo = "".join(f" + {etiqueta_unidad(h)}" for h in agrupadas)
                try:
                    numero = database.get_next_numero(edificio)
                    numero_fmt = f"{numero:03d}"

                    ruta_pdf, _nombre = nombre_archivo_recibo(
                        edificio, u["piso"], u["unidad"], expensas_de, numero, carpeta_destino,
                        tipo=tipo, depto=depto_etiqueta,
                    )

                    datos_pdf = armar_datos_recibo(
                        numero=numero, fecha=date.today(), edificio=edificio, datos_edificio=datos_edificio,
                        unidad=u, agrupadas=agrupadas, expensas_de=expensas_de, gastos_de=gastos_de,
                        estado=item["estado"], importe=importe_valor, inmobiliaria=inmobiliaria,
                    )

                    generar_pdf_recibo(datos_pdf, ruta_pdf)

                    registro = {
                        "numero_recibo": numero_fmt, "edificio": edificio, "fecha": fecha_hoy_es(),
                        "expensas_de": expensas_de, "gastos_de": gastos_de, "piso": u["piso"], "tipo": tipo,
                        "unidad": u["unidad"] + sufijo, "inquilino": u["inquilino"], "importe": f"{importe_valor:.2f}",
                        "archivo": os.path.relpath(ruta_pdf, config.BASE_DIR), "unidad_id": u["id"],
                        "datos_completos": "1", "uf": u.get("uf", ""), "dueno": u.get("dueno", ""),
                        "asociadas": "; ".join(f"{normalizar_tipo(h['tipo'])}|{h['piso']}|{h['unidad']}" for h in agrupadas),
                        "estado": item["estado"] or "",
                        "edificio_direccion": datos_edificio.get("direccion", ""),
                        "edificio_localidad": datos_edificio.get("localidad", ""),
                        "edificio_cuit": datos_edificio.get("cuit", ""),
                        "admin_nombre": datos_edificio.get("admin_nombre", ""),
                        "admin_cuit": datos_edificio.get("admin_cuit", ""),
                        "admin_rpac": datos_edificio.get("admin_rpac", ""),
                        "inmo_nombre": inmobiliaria.get("nombre", ""),
                        "inmo_subtitulo": inmobiliaria.get("subtitulo", ""),
                        "inmo_direccion": inmobiliaria.get("direccion", ""),
                        "inmo_telefono": inmobiliaria.get("telefono", ""),
                        "inmo_email": inmobiliaria.get("email", ""),
                    }
                    database.append_historial(registro)
                    generados.append((registro, etiqueta_unidad(u, por_id) + sufijo))
                except Exception as e:
                    errores.append(f"{etiqueta_unidad(u, por_id)}: {e}")

            self._recargar_unidades()      # los círculos de "recibo emitido" pasan a verde

            if generados:
                VentanaRecibosGenerados(self, generados, len(plan), errores).show()
                return

            mensaje = f"Se generaron {len(generados)} de {len(plan)} recibo(s).\n\nCarpeta:\n{carpeta_destino}"
            if errores:
                mensaje += "\n\nUnidades con error:\n" + "\n".join(errores)
                QMessageBox.warning(self, "Generación con errores", mensaje)
            else:
                QMessageBox.information(self, "Recibos generados", mensaje)
        except Exception as e:
            manejar_error("No se pudieron generar los recibos", e, self)

