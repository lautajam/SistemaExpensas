# -*- coding: utf-8 -*-
"""
ui.py
-----
Toda la interfaz gráfica (Tkinter/ttk) de Sistema de Expensas.

Contiene:
    - App: ventana principal.
    - DialogoUnidad: alta/edición de una unidad.
    - DialogoEdificioNuevo: alta de un edificio.
    - VentanaAdministracion: administrar edificios y unidades.
    - VentanaConfiguracion: datos de la inmobiliaria.
    - VentanaHistorial: consulta del historial de recibos generados.

Cualquier error inesperado se captura y se muestra como un mensaje
comprensible (messagebox), nunca como un traceback crudo de Python.
"""

import os
import traceback
import tkinter as tk
from tkinter import ttk, messagebox

import config
import database
from utils import (
    parse_importe,
    format_currency_ar,
    mes_actual_es,
    mes_anterior_es,
    fecha_hoy_es,
    nombre_archivo_recibo,
    abrir_carpeta_en_explorador,
    abrir_pdf,
    revelar_en_explorador,
)
from pdf_generator import generar_pdf_recibo

COLOR_FONDO = "#f4f6f8"
COLOR_PRIMARIO = "#1a3d5c"
FUENTE_TITULO = ("Segoe UI", 16, "bold")
FUENTE_NORMAL = ("Segoe UI", 10)
FUENTE_BOLD = ("Segoe UI", 10, "bold")

MARCADO = "☑"
DESMARCADO = "☐"


def manejar_error(titulo, error):
    """Muestra un mensaje de error comprensible y registra el detalle en consola."""
    traceback.print_exc()
    messagebox.showerror(titulo, f"Ocurrió un problema:\n\n{error}")


# ===========================================================================
# Diálogo: alta / edición de unidad
# ===========================================================================

class DialogoUnidad(tk.Toplevel):
    def __init__(self, parent, edificio, unidad=None, on_guardar=None):
        super().__init__(parent)
        self.edificio = edificio
        self.unidad = unidad  # dict si es edición, None si es alta
        self.on_guardar = on_guardar

        self.title("Editar unidad" if unidad else "Nueva unidad")
        self.configure(bg=COLOR_FONDO)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        cont = tk.Frame(self, bg=COLOR_FONDO, padx=20, pady=16)
        cont.pack(fill="both", expand=True)

        tk.Label(cont, text=f"Edificio: {edificio}", font=FUENTE_BOLD, bg=COLOR_FONDO).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )

        self.var_piso = tk.StringVar(value=unidad["piso"] if unidad else "")
        self.var_tipo = tk.StringVar(value=unidad["tipo"] if unidad else "DEPTO")
        self.var_unidad = tk.StringVar(value=unidad["unidad"] if unidad else "")
        self.var_inquilino = tk.StringVar(value=unidad["inquilino"] if unidad else "")
        self.var_importe = tk.StringVar(value=unidad["importe"] if unidad else "0")

        campos = [
            ("Piso (ej: PB, 1°, BAU):", self.var_piso),
            ("Tipo (ej: DEPTO, COCH, BAU):", self.var_tipo),
            ("Unidad (ej: A, 1, 3):", self.var_unidad),
            ("Inquilino:", self.var_inquilino),
            ("Importe:", self.var_importe),
        ]

        for i, (etiqueta, var) in enumerate(campos, start=1):
            tk.Label(cont, text=etiqueta, font=FUENTE_NORMAL, bg=COLOR_FONDO).grid(
                row=i, column=0, sticky="w", pady=4
            )
            tk.Entry(cont, textvariable=var, width=28, font=FUENTE_NORMAL).grid(
                row=i, column=1, pady=4, padx=(10, 0)
            )

        botones = tk.Frame(cont, bg=COLOR_FONDO)
        botones.grid(row=len(campos) + 1, column=0, columnspan=2, pady=(16, 0))

        tk.Button(botones, text="Guardar", command=self._guardar, bg=COLOR_PRIMARIO,
                   fg="white", font=FUENTE_BOLD, padx=14, pady=4).pack(side="left", padx=6)
        tk.Button(botones, text="Cancelar", command=self.destroy, padx=14, pady=4).pack(side="left", padx=6)

    def _guardar(self):
        piso = self.var_piso.get().strip()
        tipo = self.var_tipo.get().strip().upper()
        unidad_txt = self.var_unidad.get().strip()
        inquilino = self.var_inquilino.get().strip()
        importe = parse_importe(self.var_importe.get())

        if not piso or not unidad_txt:
            messagebox.showwarning("Datos incompletos", "Completá al menos 'Piso' y 'Unidad'.")
            return

        try:
            if self.unidad:
                database.update_unidad(
                    self.unidad["id"],
                    piso=piso, tipo=tipo, unidad=unidad_txt,
                    inquilino=inquilino, importe=str(importe),
                )
            else:
                database.add_unidad(self.edificio, piso, tipo, unidad_txt, inquilino, importe)

            if self.on_guardar:
                self.on_guardar()
            self.destroy()
        except Exception as e:
            manejar_error("No se pudo guardar la unidad", e)


# ===========================================================================
# Diálogo: alta de edificio
# ===========================================================================

class DialogoEdificioNuevo(tk.Toplevel):
    def __init__(self, parent, on_guardar=None):
        super().__init__(parent)
        self.on_guardar = on_guardar
        self.title("Nuevo edificio")
        self.configure(bg=COLOR_FONDO)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        cont = tk.Frame(self, bg=COLOR_FONDO, padx=20, pady=16)
        cont.pack(fill="both", expand=True)

        tk.Label(cont, text="Nombre del edificio:", font=FUENTE_NORMAL, bg=COLOR_FONDO).grid(
            row=0, column=0, sticky="w"
        )
        self.var_nombre = tk.StringVar()
        entry = tk.Entry(cont, textvariable=self.var_nombre, width=32, font=FUENTE_NORMAL)
        entry.grid(row=1, column=0, pady=(6, 14))
        entry.focus_set()

        botones = tk.Frame(cont, bg=COLOR_FONDO)
        botones.grid(row=2, column=0)
        tk.Button(botones, text="Crear", command=self._guardar, bg=COLOR_PRIMARIO,
                   fg="white", font=FUENTE_BOLD, padx=14, pady=4).pack(side="left", padx=6)
        tk.Button(botones, text="Cancelar", command=self.destroy, padx=14, pady=4).pack(side="left", padx=6)

    def _guardar(self):
        nombre = self.var_nombre.get().strip()
        if not nombre:
            messagebox.showwarning("Datos incompletos", "Ingresá un nombre de edificio.")
            return
        try:
            database.add_edificio(nombre)
            if self.on_guardar:
                self.on_guardar(nombre)
            self.destroy()
        except Exception as e:
            manejar_error("No se pudo crear el edificio", e)


# ===========================================================================
# Ventana: administración de edificios / unidades
# ===========================================================================

class VentanaAdministracion(tk.Toplevel):
    def __init__(self, parent, edificio_inicial, on_cambios=None):
        super().__init__(parent)
        self.on_cambios = on_cambios
        self.title("Administrar edificios y unidades")
        self.configure(bg=COLOR_FONDO)
        self.geometry("760x480")
        self.transient(parent)

        top = tk.Frame(self, bg=COLOR_FONDO, padx=16, pady=12)
        top.pack(fill="x")

        tk.Label(top, text="Edificio:", font=FUENTE_BOLD, bg=COLOR_FONDO).pack(side="left")
        self.var_edificio = tk.StringVar(value=edificio_inicial)
        self.combo_edificio = ttk.Combobox(
            top, textvariable=self.var_edificio, values=database.get_nombres_edificios(),
            state="readonly", width=30
        )
        self.combo_edificio.pack(side="left", padx=8)
        self.combo_edificio.bind("<<ComboboxSelected>>", lambda e: self._recargar())

        tk.Button(top, text="+ Nuevo edificio", command=self._nuevo_edificio).pack(side="left", padx=6)
        tk.Button(top, text="+ Nueva unidad", command=self._nueva_unidad).pack(side="left", padx=6)
        tk.Button(top, text="Abrir carpeta del edificio", command=self._abrir_carpeta).pack(side="left", padx=6)

        columnas = ("piso", "tipo", "unidad", "inquilino", "importe")
        self.tree = ttk.Treeview(self, columns=columnas, show="headings", height=16)
        titulos = {"piso": "PISO", "tipo": "TIPO", "unidad": "UNIDAD", "inquilino": "INQUILINO", "importe": "IMPORTE"}
        anchos = {"piso": 80, "tipo": 90, "unidad": 90, "inquilino": 220, "importe": 110}
        for c in columnas:
            self.tree.heading(c, text=titulos[c])
            self.tree.column(c, width=anchos[c], anchor="center" if c != "inquilino" else "w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self.tree.bind("<Double-1>", lambda e: self._editar_seleccionada())

        pie = tk.Frame(self, bg=COLOR_FONDO, padx=16, pady=8)
        pie.pack(fill="x")
        tk.Button(pie, text="Editar unidad seleccionada", command=self._editar_seleccionada).pack(side="left")
        tk.Label(pie, text="(doble clic sobre una fila también la edita)", bg=COLOR_FONDO,
                 fg="#666666", font=("Segoe UI", 8)).pack(side="left", padx=10)

        self._unidades_por_iid = {}
        self._recargar()

    def _recargar(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._unidades_por_iid = {}

        edificio = self.var_edificio.get()
        for u in database.get_unidades_por_edificio(edificio):
            importe_fmt = format_currency_ar(parse_importe(u["importe"]))
            iid = self.tree.insert("", "end", iid=u["id"],
                                    values=(u["piso"], u["tipo"], u["unidad"], u["inquilino"], importe_fmt))
            self._unidades_por_iid[iid] = u

        if self.on_cambios:
            self.on_cambios()

    def _nuevo_edificio(self):
        def al_guardar(nombre):
            self.combo_edificio["values"] = database.get_nombres_edificios()
            self.var_edificio.set(nombre)
            self._recargar()
        DialogoEdificioNuevo(self, on_guardar=al_guardar)

    def _nueva_unidad(self):
        edificio = self.var_edificio.get()
        if not edificio:
            messagebox.showwarning("Atención", "Primero seleccioná o creá un edificio.")
            return
        DialogoUnidad(self, edificio, unidad=None, on_guardar=self._recargar)

    def _editar_seleccionada(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo("Editar unidad", "Seleccioná primero una unidad de la lista.")
            return
        unidad = self._unidades_por_iid.get(seleccion[0])
        if unidad:
            DialogoUnidad(self, self.var_edificio.get(), unidad=unidad, on_guardar=self._recargar)

    def _abrir_carpeta(self):
        edificio = self.var_edificio.get()
        if not edificio:
            return
        carpeta = database.carpeta_edificio(edificio)
        if not abrir_carpeta_en_explorador(carpeta):
            messagebox.showinfo("Carpeta del edificio", f"La carpeta es:\n{carpeta}")


# ===========================================================================
# Diálogo genérico: alta / edición de una fila de cualquier tabla CSV
# ===========================================================================

class DialogoFilaGenerica(tk.Toplevel):
    """
    Formulario genérico que muestra un Entry por cada columna de la tabla
    (sin ningún formateo ni validación especial: es una edición "cruda",
    equivalente a editar la celda directamente en el CSV/Excel).
    """

    def __init__(self, parent, titulo, campos, valores=None, on_guardar=None,
                 campos_solo_lectura=None):
        super().__init__(parent)
        self.campos = campos
        self.valores = valores or {}
        self.on_guardar = on_guardar
        self.campos_solo_lectura = set(campos_solo_lectura or [])

        self.title(titulo)
        self.configure(bg=COLOR_FONDO)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        cont = tk.Frame(self, bg=COLOR_FONDO, padx=20, pady=16)
        cont.pack(fill="both", expand=True)

        self.vars = {}
        for i, campo in enumerate(campos):
            tk.Label(cont, text=campo.replace("_", " ").upper() + ":",
                     font=FUENTE_NORMAL, bg=COLOR_FONDO).grid(row=i, column=0, sticky="w", pady=4)
            var = tk.StringVar(value=str(self.valores.get(campo, "")))
            estado = "readonly" if campo in self.campos_solo_lectura else "normal"
            entry = tk.Entry(cont, textvariable=var, width=34, font=FUENTE_NORMAL, state=estado)
            entry.grid(row=i, column=1, pady=4, padx=(10, 0))
            self.vars[campo] = var

        botones = tk.Frame(cont, bg=COLOR_FONDO)
        botones.grid(row=len(campos), column=0, columnspan=2, pady=(16, 0))
        tk.Button(botones, text="Guardar", command=self._guardar, bg=COLOR_PRIMARIO,
                   fg="white", font=FUENTE_BOLD, padx=14, pady=4).pack(side="left", padx=6)
        tk.Button(botones, text="Cancelar", command=self.destroy, padx=14, pady=4).pack(side="left", padx=6)

    def _guardar(self):
        fila = {campo: var.get() for campo, var in self.vars.items()}
        if self.on_guardar:
            self.on_guardar(fila)
        self.destroy()


# ===========================================================================
# Ventana: editor de datos (CSV) genérico
# ===========================================================================

class VentanaEditorDatos(tk.Toplevel):
    """
    Pantalla para ver y modificar directamente las tablas CSV de:
    Edificios, Unidades, Inmobiliaria e Historial.

    A propósito NO incluye "numeracion.csv": ese archivo es de uso interno
    del programa (numeración correlativa de recibos) y no debe editarse
    a mano para evitar duplicar o saltear números de recibo.
    """

    def __init__(self, parent, on_cambios=None):
        super().__init__(parent)
        self.on_cambios = on_cambios
        self.title("Editor de datos (CSV)")
        self.configure(bg=COLOR_FONDO)
        self.geometry("920x520")
        self.transient(parent)

        self._campos_actuales = []
        self._filas_actuales = []

        top = tk.Frame(self, bg=COLOR_FONDO, padx=16, pady=10)
        top.pack(fill="x")

        tk.Label(top, text="Tabla:", font=FUENTE_BOLD, bg=COLOR_FONDO).pack(side="left")
        self._tablas = database.listar_tablas_editables()
        self.var_tabla = tk.StringVar(value=self._tablas[0][1])
        combo = ttk.Combobox(
            top, textvariable=self.var_tabla,
            values=[etiqueta for _clave, etiqueta in self._tablas],
            state="readonly", width=26,
        )
        combo.pack(side="left", padx=8)
        combo.bind("<<ComboboxSelected>>", lambda e: self._cargar_tabla())

        tk.Button(top, text="+ Agregar fila", command=self._agregar_fila).pack(side="left", padx=6)
        tk.Button(top, text="Editar fila", command=self._editar_fila).pack(side="left", padx=6)
        tk.Button(top, text="Eliminar fila", command=self._eliminar_fila).pack(side="left", padx=6)
        tk.Button(top, text="Recargar", command=self._cargar_tabla).pack(side="left", padx=6)

        aviso = tk.Label(
            self, bg="#fff6e0", fg="#7a5c00", font=("Segoe UI", 8), anchor="w", justify="left",
            text=("Los cambios se guardan al instante en el archivo CSV correspondiente. "
                  "Editá con cuidado: por ejemplo, el nombre de un edificio debe escribirse "
                  "exactamente igual en 'Edificios' y en 'Unidades' para que sigan relacionados."),
        )
        aviso.pack(fill="x", padx=16, pady=(0, 6))

        self.tree = ttk.Treeview(self, show="headings", height=18)
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.tree.bind("<Double-1>", lambda e: self._editar_fila())

        self._clave_actual = None
        self._cargar_tabla()

    def _clave_de_etiqueta(self, etiqueta):
        for clave, et in self._tablas:
            if et == etiqueta:
                return clave
        return self._tablas[0][0]

    def _cargar_tabla(self):
        clave = self._clave_de_etiqueta(self.var_tabla.get())
        self._clave_actual = clave
        try:
            campos, filas = database.leer_tabla(clave)
        except Exception as e:
            manejar_error("No se pudo leer la tabla", e)
            return

        self._campos_actuales = campos
        self._filas_actuales = filas

        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = campos
        for c in campos:
            self.tree.heading(c, text=c.upper())
            ancho = 260 if c in ("inquilino", "nombre", "direccion", "archivo") else 120
            self.tree.column(c, width=ancho, anchor="w")

        for idx, fila in enumerate(filas):
            valores = [fila.get(c, "") for c in campos]
            self.tree.insert("", "end", iid=str(idx), values=valores)

    def _fila_seleccionada_idx(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo("Editor de datos", "Seleccioná primero una fila de la lista.")
            return None
        return int(seleccion[0])

    def _guardar_y_refrescar(self):
        try:
            database.guardar_tabla(self._clave_actual, self._filas_actuales)
        except Exception as e:
            manejar_error("No se pudo guardar la tabla", e)
            return
        self._cargar_tabla()
        if self.on_cambios:
            self.on_cambios()

    def _agregar_fila(self):
        def al_guardar(fila_nueva):
            self._filas_actuales.append(fila_nueva)
            self._guardar_y_refrescar()

        DialogoFilaGenerica(
            self, f"Agregar fila – {self.var_tabla.get()}",
            self._campos_actuales, valores=None, on_guardar=al_guardar,
        )

    def _editar_fila(self):
        idx = self._fila_seleccionada_idx()
        if idx is None:
            return
        fila_actual = self._filas_actuales[idx]

        def al_guardar(fila_editada):
            self._filas_actuales[idx] = fila_editada
            self._guardar_y_refrescar()

        DialogoFilaGenerica(
            self, f"Editar fila – {self.var_tabla.get()}",
            self._campos_actuales, valores=fila_actual, on_guardar=al_guardar,
        )

    def _eliminar_fila(self):
        idx = self._fila_seleccionada_idx()
        if idx is None:
            return
        if not messagebox.askyesno("Confirmar eliminación",
                                    "¿Eliminar esta fila? Esta acción no se puede deshacer."):
            return
        try:
            del self._filas_actuales[idx]
            self._guardar_y_refrescar()
        except Exception as e:
            manejar_error("No se pudo eliminar la fila", e)


# ===========================================================================
# Ventana: configuración de la inmobiliaria
# ===========================================================================

class VentanaConfiguracion(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Configuración de la inmobiliaria")
        self.configure(bg=COLOR_FONDO)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        datos = database.get_inmobiliaria()

        cont = tk.Frame(self, bg=COLOR_FONDO, padx=20, pady=16)
        cont.pack(fill="both", expand=True)

        self.vars = {}
        etiquetas = [
            ("nombre", "Nombre de la inmobiliaria:"),
            ("direccion", "Dirección:"),
            ("telefono", "Teléfono:"),
            ("email", "Email:"),
            ("cuit", "CUIT:"),
        ]
        for i, (clave, etiqueta) in enumerate(etiquetas):
            tk.Label(cont, text=etiqueta, font=FUENTE_NORMAL, bg=COLOR_FONDO).grid(
                row=i, column=0, sticky="w", pady=4
            )
            var = tk.StringVar(value=datos.get(clave, ""))
            tk.Entry(cont, textvariable=var, width=36, font=FUENTE_NORMAL).grid(
                row=i, column=1, pady=4, padx=(10, 0)
            )
            self.vars[clave] = var

        botones = tk.Frame(cont, bg=COLOR_FONDO)
        botones.grid(row=len(etiquetas), column=0, columnspan=2, pady=(16, 0))
        tk.Button(botones, text="Guardar", command=self._guardar, bg=COLOR_PRIMARIO,
                   fg="white", font=FUENTE_BOLD, padx=14, pady=4).pack(side="left", padx=6)
        tk.Button(botones, text="Cerrar", command=self.destroy, padx=14, pady=4).pack(side="left", padx=6)

    def _guardar(self):
        try:
            datos = {clave: var.get().strip() for clave, var in self.vars.items()}
            database.save_inmobiliaria(datos)
            messagebox.showinfo("Configuración", "Los datos de la inmobiliaria se guardaron correctamente.")
            self.destroy()
        except Exception as e:
            manejar_error("No se pudo guardar la configuración", e)


# ===========================================================================
# Ventana: historial de recibos
# ===========================================================================

class VentanaHistorial(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Historial de recibos generados")
        self.configure(bg=COLOR_FONDO)
        self.geometry("900x480")
        self.transient(parent)

        top = tk.Frame(self, bg=COLOR_FONDO, padx=16, pady=10)
        top.pack(fill="x")

        tk.Label(top, text="Filtrar por edificio:", font=FUENTE_BOLD, bg=COLOR_FONDO).pack(side="left")
        self.var_filtro = tk.StringVar(value="(Todos)")
        combo = ttk.Combobox(
            top, textvariable=self.var_filtro,
            values=["(Todos)"] + database.get_nombres_edificios(),
            state="readonly", width=28
        )
        combo.pack(side="left", padx=8)
        combo.bind("<<ComboboxSelected>>", lambda e: self._recargar())

        columnas = ("numero_recibo", "edificio", "fecha", "expensas_de", "piso", "unidad", "inquilino", "importe", "archivo")
        titulos = {
            "numero_recibo": "N°", "edificio": "Edificio", "fecha": "Fecha", "expensas_de": "Expensas de",
            "piso": "Piso", "unidad": "Unidad", "inquilino": "Inquilino", "importe": "Importe", "archivo": "Archivo",
        }
        anchos = {
            "numero_recibo": 60, "edificio": 150, "fecha": 80, "expensas_de": 110,
            "piso": 55, "unidad": 55, "inquilino": 150, "importe": 90, "archivo": 260,
        }

        self.tree = ttk.Treeview(self, columns=columnas, show="headings", height=16)
        for c in columnas:
            self.tree.heading(c, text=titulos[c])
            self.tree.column(c, width=anchos[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(4, 8))
        self.tree.bind("<Double-1>", lambda e: self._abrir_pdf_seleccionado())

        pie = tk.Frame(self, bg=COLOR_FONDO, padx=16, pady=(0, 12))
        pie.pack(fill="x")
        tk.Button(pie, text="Abrir PDF", command=self._abrir_pdf_seleccionado,
                  bg=COLOR_PRIMARIO, fg="white", font=FUENTE_BOLD, padx=12, pady=4).pack(side="left")
        tk.Button(pie, text="Mostrar en carpeta", command=self._mostrar_en_carpeta,
                  padx=12, pady=4).pack(side="left", padx=8)
        tk.Label(pie, text="(doble clic en una fila también abre el PDF)", bg=COLOR_FONDO,
                 fg="#666666", font=("Segoe UI", 8)).pack(side="left", padx=10)

        self._archivo_por_iid = {}
        self._recargar()

    def _recargar(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._archivo_por_iid = {}

        filtro = self.var_filtro.get()
        historial = database.get_historial()
        historial.sort(key=lambda r: r.get("numero_recibo", ""), reverse=True)

        contador = 0
        for r in historial:
            if filtro != "(Todos)" and r.get("edificio") != filtro:
                continue
            importe_fmt = format_currency_ar(parse_importe(r.get("importe", "0")))
            iid = str(contador)
            contador += 1
            self.tree.insert("", "end", iid=iid, values=(
                r.get("numero_recibo", ""), r.get("edificio", ""), r.get("fecha", ""),
                r.get("expensas_de", ""), r.get("piso", ""), r.get("unidad", ""),
                r.get("inquilino", ""), importe_fmt, r.get("archivo", ""),
            ))
            self._archivo_por_iid[iid] = r.get("archivo", "")

    def _ruta_absoluta_seleccionada(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo("Historial", "Seleccioná primero un recibo de la lista.")
            return None
        archivo_rel = self._archivo_por_iid.get(seleccion[0], "")
        if not archivo_rel:
            messagebox.showwarning("Historial", "Este registro no tiene un archivo asociado.")
            return None
        return os.path.join(config.BASE_DIR, archivo_rel)

    def _abrir_pdf_seleccionado(self):
        ruta = self._ruta_absoluta_seleccionada()
        if not ruta:
            return
        ok, mensaje_error = abrir_pdf(ruta)
        if not ok:
            messagebox.showwarning("No se pudo abrir el PDF", mensaje_error)

    def _mostrar_en_carpeta(self):
        ruta = self._ruta_absoluta_seleccionada()
        if not ruta:
            return
        if not revelar_en_explorador(ruta):
            messagebox.showinfo("Ubicación del archivo", ruta)


# ===========================================================================
# Ventana principal
# ===========================================================================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(config.APP_TITULO)
        self.configure(bg=COLOR_FONDO)
        self.geometry("980x640")
        self.minsize(880, 560)

        self.seleccionadas = set()      # ids de unidades marcadas
        self._unidades_por_iid = {}     # iid (=id de unidad) -> dict de la unidad

        self._crear_menu()
        self._crear_encabezado()
        self._crear_panel_periodo_importe()
        self._crear_tabla()
        self._crear_pie()

        self._cargar_edificios()

    # -----------------------------------------------------------------
    # Construcción de la interfaz
    # -----------------------------------------------------------------

    def _crear_menu(self):
        menubar = tk.Menu(self)

        menu_archivo = tk.Menu(menubar, tearoff=0)
        menu_archivo.add_command(label="Copia de seguridad (backup)", command=self._hacer_backup)
        menu_archivo.add_separator()
        menu_archivo.add_command(label="Salir", command=self.destroy)
        menubar.add_cascade(label="Archivo", menu=menu_archivo)

        menu_admin = tk.Menu(menubar, tearoff=0)
        menu_admin.add_command(label="Administrar edificios/unidades", command=self._abrir_administracion)
        menu_admin.add_command(label="Configuración de la inmobiliaria", command=self._abrir_configuracion)
        menu_admin.add_separator()
        menu_admin.add_command(label="Editor de datos (CSV)", command=self._abrir_editor_datos)
        menubar.add_cascade(label="Administrar", menu=menu_admin)

        menu_ver = tk.Menu(menubar, tearoff=0)
        menu_ver.add_command(label="Historial de recibos", command=self._abrir_historial)
        menubar.add_cascade(label="Ver", menu=menu_ver)

        menu_ayuda = tk.Menu(menubar, tearoff=0)
        menu_ayuda.add_command(label="Acerca de", command=self._mostrar_acerca_de)
        menubar.add_cascade(label="Ayuda", menu=menu_ayuda)

        self.config(menu=menubar)

    def _crear_encabezado(self):
        header = tk.Frame(self, bg=COLOR_PRIMARIO, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="SISTEMA DE EXPENSAS", font=FUENTE_TITULO,
                 bg=COLOR_PRIMARIO, fg="white").pack()
        tk.Label(header, text="Administración de consorcios", font=("Segoe UI", 10),
                 bg=COLOR_PRIMARIO, fg="#dbe6ee").pack()

        seleccion = tk.Frame(self, bg=COLOR_FONDO, padx=16, pady=12)
        seleccion.pack(fill="x")

        tk.Label(seleccion, text="Edificio:", font=FUENTE_BOLD, bg=COLOR_FONDO).grid(row=0, column=0, sticky="w")
        self.var_edificio = tk.StringVar()
        self.combo_edificio = ttk.Combobox(seleccion, textvariable=self.var_edificio,
                                            state="readonly", width=32, font=FUENTE_NORMAL)
        self.combo_edificio.grid(row=0, column=1, padx=10, sticky="w")
        self.combo_edificio.bind("<<ComboboxSelected>>", lambda e: self._cargar_unidades())

    def _crear_panel_periodo_importe(self):
        panel = tk.Frame(self, bg=COLOR_FONDO, padx=16, pady=6)
        panel.pack(fill="x")

        tk.Label(panel, text="Expensas de:", font=FUENTE_BOLD, bg=COLOR_FONDO).grid(row=0, column=0, sticky="w")
        self.var_expensas_de = tk.StringVar(value=mes_actual_es())
        tk.Entry(panel, textvariable=self.var_expensas_de, width=20, font=FUENTE_NORMAL).grid(
            row=0, column=1, padx=(6, 24), sticky="w"
        )

        tk.Label(panel, text="Gastos de:", font=FUENTE_BOLD, bg=COLOR_FONDO).grid(row=0, column=2, sticky="w")
        self.var_gastos_de = tk.StringVar(value=mes_anterior_es())
        tk.Entry(panel, textvariable=self.var_gastos_de, width=20, font=FUENTE_NORMAL).grid(
            row=0, column=3, padx=(6, 24), sticky="w"
        )

        tk.Label(panel, text="Importe para selección:", font=FUENTE_BOLD, bg=COLOR_FONDO).grid(
            row=1, column=0, sticky="w", pady=(10, 0)
        )
        self.var_importe_general = tk.StringVar(value="0")
        tk.Entry(panel, textvariable=self.var_importe_general, width=18, font=FUENTE_NORMAL).grid(
            row=1, column=1, sticky="w", pady=(10, 0)
        )
        tk.Button(panel, text="Aplicar importe a seleccionadas", command=self._aplicar_importe_general).grid(
            row=1, column=2, columnspan=2, sticky="w", pady=(10, 0)
        )

    def _crear_tabla(self):
        cont = tk.Frame(self, bg=COLOR_FONDO, padx=16, pady=8)
        cont.pack(fill="both", expand=True)

        columnas = ("sel", "piso", "tipo", "unidad", "inquilino", "importe")
        self.tree = ttk.Treeview(cont, columns=columnas, show="headings", selectmode="none")

        titulos = {"sel": "", "piso": "PISO", "tipo": "TIPO", "unidad": "UNIDAD",
                   "inquilino": "INQUILINO", "importe": "IMPORTE"}
        anchos = {"sel": 36, "piso": 80, "tipo": 90, "unidad": 90, "inquilino": 240, "importe": 120}
        for c in columnas:
            self.tree.heading(c, text=titulos[c])
            self.tree.column(c, width=anchos[c],
                              anchor="center" if c != "inquilino" else "w")

        scrollbar = ttk.Scrollbar(cont, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<Button-1>", self._click_en_tabla)
        self.tree.bind("<Double-1>", self._doble_click_en_tabla)

        ayuda = tk.Label(
            self, bg=COLOR_FONDO, fg="#666666", font=("Segoe UI", 8),
            text="Clic en la primera columna para seleccionar/deseleccionar. Doble clic en el resto de la fila para editar la unidad.",
        )
        ayuda.pack(anchor="w", padx=18)

    def _crear_pie(self):
        pie = tk.Frame(self, bg=COLOR_FONDO, padx=16, pady=10)
        pie.pack(fill="x")

        tk.Button(pie, text="Seleccionar todas", command=self._seleccionar_todas).pack(side="left")
        tk.Button(pie, text="Quitar todas", command=self._quitar_todas).pack(side="left", padx=8)

        tk.Button(
            pie, text="GENERAR RECIBOS PDF", command=self._generar_recibos,
            bg="#1f7a3d", fg="white", font=("Segoe UI", 11, "bold"), padx=18, pady=8
        ).pack(side="right")

    # -----------------------------------------------------------------
    # Carga de datos en pantalla
    # -----------------------------------------------------------------

    def _cargar_edificios(self):
        try:
            database.ensure_data_files()
            nombres = database.get_nombres_edificios()
            self.combo_edificio["values"] = nombres
            if nombres:
                self.var_edificio.set(nombres[0])
                self._cargar_unidades()
        except Exception as e:
            manejar_error("Error al iniciar", e)

    def _cargar_unidades(self):
        self.seleccionadas.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._unidades_por_iid = {}

        edificio = self.var_edificio.get()
        if not edificio:
            return

        try:
            for u in database.get_unidades_por_edificio(edificio):
                importe_fmt = format_currency_ar(parse_importe(u["importe"]))
                self.tree.insert(
                    "", "end", iid=u["id"],
                    values=(DESMARCADO, u["piso"], u["tipo"], u["unidad"], u["inquilino"], importe_fmt),
                )
                self._unidades_por_iid[u["id"]] = u
        except Exception as e:
            manejar_error("No se pudieron cargar las unidades", e)

    def _refrescar_fila(self, iid):
        u = database.get_all_unidades()
        u = next((x for x in u if x["id"] == iid), None)
        if not u:
            return
        self._unidades_por_iid[iid] = u
        marca = MARCADO if iid in self.seleccionadas else DESMARCADO
        importe_fmt = format_currency_ar(parse_importe(u["importe"]))
        self.tree.item(iid, values=(marca, u["piso"], u["tipo"], u["unidad"], u["inquilino"], importe_fmt))

    # -----------------------------------------------------------------
    # Selección de filas
    # -----------------------------------------------------------------

    def _click_en_tabla(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        columna = self.tree.identify_column(event.x)
        fila = self.tree.identify_row(event.y)
        if not fila:
            return
        if columna == "#1":  # columna de selección
            self._alternar_seleccion(fila)

    def _doble_click_en_tabla(self, event):
        fila = self.tree.identify_row(event.y)
        columna = self.tree.identify_column(event.x)
        if not fila:
            return
        if columna == "#1":
            return  # ya se maneja como clic simple
        unidad = self._unidades_por_iid.get(fila)
        if unidad:
            DialogoUnidad(self, self.var_edificio.get(), unidad=unidad,
                          on_guardar=lambda: self._refrescar_fila(fila))

    def _alternar_seleccion(self, iid):
        if iid in self.seleccionadas:
            self.seleccionadas.remove(iid)
        else:
            self.seleccionadas.add(iid)
        valores = list(self.tree.item(iid, "values"))
        valores[0] = MARCADO if iid in self.seleccionadas else DESMARCADO
        self.tree.item(iid, values=valores)

    def _seleccionar_todas(self):
        for iid in self.tree.get_children():
            self.seleccionadas.add(iid)
            valores = list(self.tree.item(iid, "values"))
            valores[0] = MARCADO
            self.tree.item(iid, values=valores)

    def _quitar_todas(self):
        self.seleccionadas.clear()
        for iid in self.tree.get_children():
            valores = list(self.tree.item(iid, "values"))
            valores[0] = DESMARCADO
            self.tree.item(iid, values=valores)

    # -----------------------------------------------------------------
    # Importe general
    # -----------------------------------------------------------------

    def _aplicar_importe_general(self):
        if not self.seleccionadas:
            messagebox.showwarning("Atención", "No hay ninguna unidad seleccionada.")
            return
        importe = parse_importe(self.var_importe_general.get())
        try:
            database.update_importe_unidades(list(self.seleccionadas), importe)
            for iid in list(self.seleccionadas):
                self._refrescar_fila(iid)
        except Exception as e:
            manejar_error("No se pudo aplicar el importe", e)

    # -----------------------------------------------------------------
    # Generación de recibos
    # -----------------------------------------------------------------

    def _generar_recibos(self):
        edificio = self.var_edificio.get()
        if not edificio:
            messagebox.showwarning("Atención", "Seleccioná un edificio.")
            return

        seleccionadas = list(self.seleccionadas)
        if not seleccionadas:
            messagebox.showwarning("Atención", "No hay unidades seleccionadas para generar recibos.")
            return

        expensas_de = self.var_expensas_de.get().strip().upper()
        gastos_de = self.var_gastos_de.get().strip().upper()
        if not expensas_de or not gastos_de:
            messagebox.showwarning("Atención", "Completá los campos 'Expensas de' y 'Gastos de'.")
            return

        if not messagebox.askyesno(
            "Confirmar generación",
            f"Se van a generar {len(seleccionadas)} recibo(s) para:\n\n{edificio}\n\n¿Confirmás?",
        ):
            return

        try:
            inmobiliaria = database.get_inmobiliaria()
            carpeta_destino = database.crear_carpeta_edificio(edificio)
            unidades_actuales = {u["id"]: u for u in database.get_unidades_por_edificio(edificio)}

            generados = 0
            errores = []

            for iid in seleccionadas:
                u = unidades_actuales.get(iid)
                if not u:
                    continue
                try:
                    numero = database.get_next_numero(edificio)
                    numero_fmt = f"{numero:05d}"
                    importe_valor = parse_importe(u["importe"])

                    ruta_pdf, _nombre = nombre_archivo_recibo(
                        edificio, u["piso"], u["unidad"], expensas_de, numero, carpeta_destino
                    )

                    datos_pdf = {
                        "NUMERO_RECIBO": numero_fmt,
                        "FECHA_EMISION": fecha_hoy_es(),
                        "EDIFICIO_NOMBRE": edificio,
                        "EXPENSAS_DE": expensas_de,
                        "GASTOS_DE": gastos_de,
                        "PISO": u["piso"],
                        "UNIDAD": u["unidad"],
                        "TIPO": u["tipo"],
                        "INQUILINO": u["inquilino"],
                        "IMPORTE": format_currency_ar(importe_valor),
                        "INMOBILIARIA_NOMBRE": inmobiliaria.get("nombre", ""),
                        "INMOBILIARIA_DIRECCION": inmobiliaria.get("direccion", ""),
                        "INMOBILIARIA_TELEFONO": inmobiliaria.get("telefono", ""),
                        "INMOBILIARIA_EMAIL": inmobiliaria.get("email", ""),
                        "INMOBILIARIA_CUIT": inmobiliaria.get("cuit", ""),
                    }

                    generar_pdf_recibo(datos_pdf, ruta_pdf)

                    database.append_historial({
                        "numero_recibo": numero_fmt,
                        "edificio": edificio,
                        "fecha": fecha_hoy_es(),
                        "expensas_de": expensas_de,
                        "gastos_de": gastos_de,
                        "piso": u["piso"],
                        "tipo": u["tipo"],
                        "unidad": u["unidad"],
                        "inquilino": u["inquilino"],
                        "importe": f"{importe_valor:.2f}",
                        "archivo": os.path.relpath(ruta_pdf, config.BASE_DIR),
                    })
                    generados += 1
                except Exception as e:
                    errores.append(f"{u.get('piso', '?')} {u.get('unidad', '?')}: {e}")

            mensaje = f"Se generaron {generados} de {len(seleccionadas)} recibo(s).\n\nCarpeta:\n{carpeta_destino}"
            if errores:
                mensaje += "\n\nUnidades con error:\n" + "\n".join(errores)
                messagebox.showwarning("Generación con errores", mensaje)
            else:
                messagebox.showinfo("Recibos generados", mensaje)

        except Exception as e:
            manejar_error("No se pudieron generar los recibos", e)

    # -----------------------------------------------------------------
    # Ventanas auxiliares
    # -----------------------------------------------------------------

    def _abrir_administracion(self):
        def al_cambiar():
            edificio_actual = self.var_edificio.get()
            self.combo_edificio["values"] = database.get_nombres_edificios()
            if edificio_actual:
                self.var_edificio.set(edificio_actual)
            self._cargar_unidades()
        VentanaAdministracion(self, self.var_edificio.get() or "", on_cambios=al_cambiar)

    def _abrir_configuracion(self):
        VentanaConfiguracion(self)

    def _abrir_editor_datos(self):
        def al_cambiar():
            edificio_actual = self.var_edificio.get()
            self.combo_edificio["values"] = database.get_nombres_edificios()
            if edificio_actual:
                self.var_edificio.set(edificio_actual)
            self._cargar_unidades()
        VentanaEditorDatos(self, on_cambios=al_cambiar)

    def _abrir_historial(self):
        VentanaHistorial(self)

    def _hacer_backup(self):
        try:
            ruta = database.crear_backup()
            messagebox.showinfo("Copia de seguridad", f"Backup creado correctamente en:\n\n{ruta}")
        except Exception as e:
            manejar_error("No se pudo crear la copia de seguridad", e)

    def _mostrar_acerca_de(self):
        messagebox.showinfo(
            "Acerca de",
            f"{config.APP_TITULO}\nVersión {config.APP_VERSION}\n\n"
            "Aplicación de escritorio offline para la gestión de expensas.\n"
            f"Carpeta de datos:\n{config.BASE_DIR}",
        )
