# -*- coding: utf-8 -*-
"""
ui_qt.py
--------
Prueba de concepto de la interfaz gráfica con PySide6 (Qt), como alternativa a
ui.py (Tkinter). Por ahora solo porta la ventana principal (App): selección de
edificio, tabla de unidades, actualizar/abrir planilla de pagos y generar
recibos. El resto de las ventanas (administración, configuración, mailing,
historial...) siguen existiendo únicamente en la versión Tkinter.

No toca config.py, database.py, pagos.py, recibo.py, pdf_generator.py ni
unidades.py: esta ventana es solo una capa de presentación distinta sobre la
misma lógica de negocio.
"""

import logging
import os
from datetime import date

_DIR_RECURSOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recursos_qt").replace("\\", "/")

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QFont, QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import config
import database
import pagos
from utils import (
    fecha_hoy_es,
    format_currency_ar,
    nombre_archivo_recibo,
    obtener_periodos,
    parse_importe,
)
from pdf_generator import generar_pdf_recibo
from recibo import armar_datos as armar_datos_recibo
from unidades import (
    asociadas_que_pagan_junto,
    depto_de,
    descripcion_asociadas,
    etiqueta_unidad,
    incluida_en_total,
    indice_por_id,
    normalizar_tipo,
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

QCheckBox {{ background: transparent; spacing: 0px; }}
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
        accion_salir = QAction("Salir", self)
        accion_salir.triggered.connect(self.close)
        menu_archivo.addAction(accion_salir)

        for titulo, items in (
            ("Administrar", ("Administrar edificios/unidades", "Configuración de la inmobiliaria", "Mailing")),
            ("Ver", ("Historial de recibos", "Historial de mails")),
            ("Ayuda", ("Recibo expensas", "Acerca de")),
        ):
            menu = self.menuBar().addMenu(titulo)
            for nombre in items:
                accion = QAction(nombre, self)
                accion.triggered.connect(lambda _, n=nombre: self._pendiente(n))
                menu.addAction(accion)

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
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 20)
        sidebar_layout.setSpacing(10)

        titulo = QLabel("EDIFICIOS")
        titulo.setObjectName("tituloSidebar")
        sidebar_layout.addWidget(titulo)

        self.lista_edificios = QListWidget()
        self.lista_edificios.setFocusPolicy(Qt.NoFocus)
        self.lista_edificios.currentItemChanged.connect(lambda *_: self._cargar_unidades())
        sidebar_layout.addWidget(self.lista_edificios, 1)

        cuerpo.addWidget(sidebar)

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
        from utils import abrir_pdf
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
                    generados.append(etiqueta_unidad(u, por_id) + sufijo)
                except Exception as e:
                    errores.append(f"{etiqueta_unidad(u, por_id)}: {e}")

            self._recargar_unidades()

            mensaje = f"Se generaron {len(generados)} de {len(plan)} recibo(s)."
            if generados:
                mensaje += "\n\n" + "\n".join(f"  {g}" for g in generados)
            if errores:
                mensaje += "\n\nErrores:\n" + "\n".join(f"  {e}" for e in errores)
            QMessageBox.information(self, "Recibos generados", mensaje)
        except Exception as e:
            manejar_error("No se pudieron generar los recibos", e, self)


def main():
    import sys
    from logging_config import configurar_logging

    configurar_logging()
    app = QApplication(sys.argv)
    ventana = App()
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

