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
    obtener_periodos,
    fecha_hoy_es,
    nombre_archivo_recibo,
    abrir_carpeta_en_explorador,
    abrir_pdf,
    revelar_en_explorador,
)
from pdf_generator import generar_pdf_recibo
import pagos
from unidades import (
    BAULERA, COCHERA, DEPTO, LOCAL, TIPOS, TIPOS_ASOCIABLES,
    depto_de, etiqueta_unidad, indice_por_id, nombre_tipo, normalizar_tipo, ordenar_con_asociadas,
)

COLOR_FONDO = "#f4f6f8"
COLOR_PRIMARIO = "#1a3d5c"
FUENTE_TITULO = ("Segoe UI", 16, "bold")
FUENTE_NORMAL = ("Segoe UI", 10)
FUENTE_BOLD = ("Segoe UI", 10, "bold")

MARCADO = "☑"
DESMARCADO = "☐"

PREF_MOSTRAR_LISTA = "mostrar_lista_pdf"


def manejar_error(titulo, error):
    """Muestra un mensaje de error comprensible y registra el detalle en consola."""
    traceback.print_exc()
    messagebox.showerror(titulo, f"Ocurrió un problema:\n\n{error}")


def mostrar_avisos():
    """Muestra los avisos pendientes sobre las planillas de pagos (ej. Excel abierto)."""
    for aviso in database.tomar_avisos():
        messagebox.showwarning("Planilla de pagos", aviso)


# ===========================================================================
# Diálogo: alta / edición de unidad (depto, local, cochera o baulera)
# ===========================================================================

NINGUNO = "(ninguno)"


def confirmar_y_borrar(parent, unidad_id):
    """
    Muestra qué se va a borrar (la unidad y, si es un depto, sus cocheras y
    bauleras), pide confirmación y borra. Devuelve True si se borró.
    """
    afectadas = database.unidades_a_borrar(unidad_id)
    if not afectadas:
        return False
    por_id = indice_por_id(database.get_unidades_por_edificio(afectadas[0]["edificio"]))
    lineas = [
        f"  • {etiqueta_unidad(u, por_id)}" + (f" — {u['inquilino']}" if u["inquilino"] else "")
        for u in afectadas[:12]
    ]
    if len(afectadas) > 12:
        lineas.append(f"  … y {len(afectadas) - 12} más")

    if not messagebox.askyesno(
        "Borrar unidad",
        "Se va a BORRAR:\n\n" + "\n".join(lineas) + "\n\n"
        "También se quita de la planilla de pagos del edificio. Los recibos ya generados "
        "y el historial no se borran.\nEsta acción no se puede deshacer.\n\n¿Borrar?",
        icon="warning", parent=parent,
    ):
        return False
    try:
        database.delete_unidad(unidad_id)
    except Exception as e:
        manejar_error("No se pudo borrar la unidad", e)
        return False
    mostrar_avisos()
    return True


class DialogoAsociada(tk.Toplevel):
    """Mini formulario para sumar una cochera o baulera a un depto."""

    def __init__(self, parent, tipo, on_agregar):
        super().__init__(parent)
        self.tipo = tipo
        self.on_agregar = on_agregar

        self.title(f"Nueva {nombre_tipo(tipo).lower()}")
        self.configure(bg=COLOR_FONDO)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        cont = tk.Frame(self, bg=COLOR_FONDO, padx=20, pady=16)
        cont.pack(fill="both", expand=True)

        self.var_unidad = tk.StringVar()
        self.var_uf = tk.StringVar()
        self.var_piso = tk.StringVar()
        self.var_dueno = tk.StringVar()
        self.var_importe = tk.StringVar(value="0")
        campos = [
            ("Número (ej: 3):", self.var_unidad),
            ("Unidad funcional (UF):", self.var_uf),
            ("Piso (opcional):", self.var_piso),
            ("Dueño:", self.var_dueno),
            ("Importe:", self.var_importe),
        ]
        for i, (etiqueta, var) in enumerate(campos):
            tk.Label(cont, text=etiqueta, font=FUENTE_NORMAL, bg=COLOR_FONDO).grid(row=i, column=0, sticky="w", pady=4)
            entry = tk.Entry(cont, textvariable=var, width=22, font=FUENTE_NORMAL)
            entry.grid(row=i, column=1, pady=4, padx=(10, 0))
            if i == 0:
                entry.focus_set()

        tk.Label(cont, text="El inquilino es el del depto.", font=("Segoe UI", 8), fg="#666666",
                 bg=COLOR_FONDO).grid(row=len(campos), column=0, columnspan=2, sticky="w")
        botones = tk.Frame(cont, bg=COLOR_FONDO)
        botones.grid(row=len(campos) + 1, column=0, columnspan=2, pady=(14, 0))
        tk.Button(botones, text="Agregar", command=self._agregar, bg=COLOR_PRIMARIO,
                  fg="white", font=FUENTE_BOLD, padx=14, pady=4).pack(side="left", padx=6)
        tk.Button(botones, text="Cancelar", command=self.destroy, padx=14, pady=4).pack(side="left", padx=6)

    def _agregar(self):
        numero = self.var_unidad.get().strip()
        if not numero:
            messagebox.showwarning("Datos incompletos", "Completá el número.", parent=self)
            return
        self.on_agregar({
            "tipo": self.tipo,
            "unidad": numero,
            "uf": self.var_uf.get().strip(),
            "piso": self.var_piso.get().strip(),
            "dueno": self.var_dueno.get().strip(),
            "importe": parse_importe(self.var_importe.get()),
        })
        self.destroy()


class DialogoUnidad(tk.Toplevel):
    def __init__(self, parent, edificio, unidad=None, on_guardar=None):
        super().__init__(parent)
        self.edificio = edificio
        self.unidad = unidad  # dict si es edición, None si es alta
        self.on_guardar = on_guardar
        self._asociadas = []        # cocheras/bauleras a crear junto con este depto
        self._autoinquilino = ""    # último inquilino copiado automáticamente desde el depto

        self.title("Editar unidad" if unidad else "Nueva unidad")
        self.configure(bg=COLOR_FONDO)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

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

        cont = tk.Frame(self, bg=COLOR_FONDO, padx=20, pady=16)
        cont.pack(fill="both", expand=True)

        tk.Label(cont, text=f"Edificio: {edificio}", font=FUENTE_BOLD, bg=COLOR_FONDO).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )

        tipo_actual = normalizar_tipo(unidad["tipo"]) if unidad else DEPTO
        self.var_tipo = tk.StringVar(value=nombre_tipo(tipo_actual))
        self.var_piso = tk.StringVar(value=unidad["piso"] if unidad else "")
        self.var_unidad = tk.StringVar(value=unidad["unidad"] if unidad else "")
        self.var_uf = tk.StringVar(value=unidad["uf"] if unidad else "")
        self.var_dueno = tk.StringVar(value=unidad["dueno"] if unidad else "")
        self.var_inquilino = tk.StringVar(value=unidad["inquilino"] if unidad else "")
        self.var_importe = tk.StringVar(value=unidad["importe"] if unidad else "0")
        depto_actual = next((t for t, i in self._ids_deptos.items() if unidad and i and i == unidad["depto_id"]), NINGUNO)
        self.var_depto = tk.StringVar(value=depto_actual)

        def etiqueta_fila(fila_idx, texto):
            etiqueta = tk.Label(cont, text=texto, font=FUENTE_NORMAL, bg=COLOR_FONDO)
            etiqueta.grid(row=fila_idx, column=0, sticky="w", pady=4)
            return etiqueta

        def entrada_fila(fila_idx, var):
            tk.Entry(cont, textvariable=var, width=28, font=FUENTE_NORMAL).grid(
                row=fila_idx, column=1, pady=4, padx=(10, 0))

        etiqueta_fila(1, "Tipo de unidad:")
        self.combo_tipo = ttk.Combobox(cont, textvariable=self.var_tipo, state="readonly", width=26,
                                       values=[nombre_tipo(t) for t in TIPOS], font=FUENTE_NORMAL)
        self.combo_tipo.grid(row=1, column=1, pady=4, padx=(10, 0), sticky="w")
        self.combo_tipo.bind("<<ComboboxSelected>>", lambda e: self._actualizar_tipo())

        self.lbl_piso = etiqueta_fila(2, "")
        entrada_fila(2, self.var_piso)
        self.lbl_unidad = etiqueta_fila(3, "")
        entrada_fila(3, self.var_unidad)
        etiqueta_fila(4, "Unidad funcional (UF):")
        entrada_fila(4, self.var_uf)

        self.lbl_depto = etiqueta_fila(5, "Pertenece al depto:")
        self.combo_depto = ttk.Combobox(cont, textvariable=self.var_depto, state="readonly", width=26,
                                        values=list(self._ids_deptos), font=FUENTE_NORMAL)
        self.combo_depto.grid(row=5, column=1, pady=4, padx=(10, 0), sticky="w")
        self.combo_depto.bind("<<ComboboxSelected>>", lambda e: self._al_elegir_depto())

        etiqueta_fila(6, "Dueño:")
        entrada_fila(6, self.var_dueno)
        etiqueta_fila(7, "Inquilino:")
        entrada_fila(7, self.var_inquilino)
        etiqueta_fila(8, "Importe:")
        entrada_fila(8, self.var_importe)

        self.frame_asociadas = tk.Frame(cont, bg=COLOR_FONDO)
        self.frame_asociadas.grid(row=9, column=0, columnspan=2, sticky="we", pady=(10, 0))
        tk.Label(self.frame_asociadas, text="Cocheras y bauleras de este depto:", font=FUENTE_BOLD,
                 bg=COLOR_FONDO).pack(anchor="w")
        if unidad:
            existentes = [etiqueta_unidad(h).split(" (")[0] for h, n in ordenar_con_asociadas(todas)
                          if n == 1 and h["depto_id"] == unidad["id"]]
            texto = ("Ya tiene: " + ", ".join(existentes)) if existentes else "Todavía no tiene cocheras ni bauleras."
            tk.Label(self.frame_asociadas, text=texto, font=("Segoe UI", 8), fg="#666666",
                     bg=COLOR_FONDO, wraplength=380, justify="left").pack(anchor="w")
        self.lista_asociadas = tk.Listbox(self.frame_asociadas, height=3, font=FUENTE_NORMAL)
        self.lista_asociadas.pack(fill="x", pady=(4, 4))
        barra = tk.Frame(self.frame_asociadas, bg=COLOR_FONDO)
        barra.pack(anchor="w")
        tk.Button(barra, text="+ Cochera", command=lambda: self._nueva_asociada(COCHERA)).pack(side="left")
        tk.Button(barra, text="+ Baulera", command=lambda: self._nueva_asociada(BAULERA)).pack(side="left", padx=6)
        tk.Button(barra, text="Quitar", command=self._quitar_asociada).pack(side="left")

        botones = tk.Frame(cont, bg=COLOR_FONDO)
        botones.grid(row=10, column=0, columnspan=2, pady=(16, 0))
        tk.Button(botones, text="Guardar", command=self._guardar, bg=COLOR_PRIMARIO,
                  fg="white", font=FUENTE_BOLD, padx=14, pady=4).pack(side="left", padx=6)
        tk.Button(botones, text="Cancelar", command=self.destroy, padx=14, pady=4).pack(side="left", padx=6)
        if unidad:
            tk.Button(botones, text="Borrar unidad", command=self._borrar, bg="#b3261e",
                      fg="white", padx=14, pady=4).pack(side="left", padx=(24, 6))

        self._actualizar_tipo()

    def _tipo(self):
        indice = self.combo_tipo.current()
        return TIPOS[indice] if indice >= 0 else DEPTO

    def _actualizar_tipo(self):
        tipo = self._tipo()
        self.lbl_piso.config(text="Piso (ej: PB, 1°):" if tipo == DEPTO else "Piso (opcional):")
        self.lbl_unidad.config(text={
            DEPTO: "Letra o número del depto:", LOCAL: "Letra o número del local:",
            COCHERA: "Número de cochera:", BAULERA: "Número de baulera:",
        }[tipo])
        for w in (self.lbl_depto, self.combo_depto):
            (w.grid if tipo in TIPOS_ASOCIABLES else w.grid_remove)()
        (self.frame_asociadas.grid if tipo == DEPTO else self.frame_asociadas.grid_remove)()

    def _al_elegir_depto(self):
        depto = self._por_id.get(self._ids_deptos.get(self.var_depto.get(), ""))
        if not depto:
            return
        actual = self.var_inquilino.get().strip()
        if not actual or actual == self._autoinquilino:
            self.var_inquilino.set(depto["inquilino"])
        self._autoinquilino = depto["inquilino"]

    def _nueva_asociada(self, tipo):
        DialogoAsociada(self, tipo, self._agregar_asociada)

    def _agregar_asociada(self, datos):
        self._asociadas.append(datos)
        nombre = " ".join(p for p in (nombre_tipo(datos["tipo"]), datos["piso"], datos["unidad"]) if p)
        self.lista_asociadas.insert("end", f"{nombre} — {format_currency_ar(datos['importe'])}")

    def _quitar_asociada(self):
        seleccion = self.lista_asociadas.curselection()
        if seleccion:
            self.lista_asociadas.delete(seleccion[0])
            del self._asociadas[seleccion[0]]

    def _borrar(self):
        if confirmar_y_borrar(self, self.unidad["id"]):
            if self.on_guardar:
                self.on_guardar()
            self.destroy()

    def _guardar(self):
        tipo = self._tipo()
        piso = self.var_piso.get().strip()
        unidad_txt = self.var_unidad.get().strip()
        inquilino = self.var_inquilino.get().strip()
        importe = parse_importe(self.var_importe.get())

        if tipo == DEPTO and (not piso or not unidad_txt):
            messagebox.showwarning("Datos incompletos", "Completá al menos 'Piso' y la letra o número del depto.", parent=self)
            return
        if not unidad_txt:
            messagebox.showwarning("Datos incompletos", "Completá la letra o número de la unidad.", parent=self)
            return

        depto_id = self._ids_deptos.get(self.var_depto.get(), "") if tipo in TIPOS_ASOCIABLES else ""
        asociadas = [dict(a, inquilino=inquilino) for a in self._asociadas] if tipo == DEPTO else []
        uf, dueno = self.var_uf.get().strip(), self.var_dueno.get().strip()

        try:
            if self.unidad:
                database.update_unidad(
                    self.unidad["id"],
                    piso=piso, tipo=tipo, unidad=unidad_txt, uf=uf, dueno=dueno,
                    inquilino=inquilino, importe=str(importe), depto_id=depto_id,
                )
                if asociadas:
                    database.add_asociadas(self.unidad["id"], asociadas)
            else:
                database.add_unidad(self.edificio, piso, tipo, unidad_txt, inquilino, importe,
                                    depto_id=depto_id, asociadas=asociadas, uf=uf, dueno=dueno)

            mostrar_avisos()
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
            mostrar_avisos()
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

        columnas = ("piso", "tipo", "unidad", "uf", "depto", "dueno", "inquilino", "importe")
        self.tree = ttk.Treeview(self, columns=columnas, show="headings", height=16)
        titulos = {"piso": "PISO", "tipo": "TIPO", "unidad": "LETRA/N°", "uf": "UF", "depto": "PERTENECE A",
                   "dueno": "DUEÑO", "inquilino": "INQUILINO", "importe": "IMPORTE"}
        anchos = {"piso": 60, "tipo": 80, "unidad": 80, "uf": 50, "depto": 90, "dueno": 130, "inquilino": 130, "importe": 100}
        for c in columnas:
            self.tree.heading(c, text=titulos[c])
            self.tree.column(c, width=anchos[c], anchor="w" if c in ("dueno", "inquilino") else "center")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self.tree.bind("<Double-1>", lambda e: self._editar_seleccionada())

        pie = tk.Frame(self, bg=COLOR_FONDO, padx=16, pady=8)
        pie.pack(fill="x")
        tk.Button(pie, text="Editar unidad seleccionada", command=self._editar_seleccionada).pack(side="left")
        tk.Button(pie, text="Borrar unidad seleccionada", command=self._borrar_seleccionada,
                  bg="#b3261e", fg="white").pack(side="left", padx=(10, 0))
        tk.Label(pie, text="(doble clic sobre una fila también la edita)", bg=COLOR_FONDO,
                 fg="#666666", font=("Segoe UI", 8)).pack(side="left", padx=10)

        self._unidades_por_iid = {}
        self._recargar()

    def _recargar(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._unidades_por_iid = {}

        edificio = self.var_edificio.get()
        todas = database.get_unidades_por_edificio(edificio)
        por_id = indice_por_id(todas)
        for u, nivel in ordenar_con_asociadas(todas):
            importe_fmt = format_currency_ar(parse_importe(u["importe"]))
            depto = depto_de(u, por_id)
            iid = self.tree.insert("", "end", iid=u["id"], values=(
                u["piso"], normalizar_tipo(u["tipo"]), ("↳ " if nivel else "") + u["unidad"], u["uf"],
                etiqueta_unidad(depto) if depto else "", u["dueno"], u["inquilino"], importe_fmt,
            ))
            self._unidades_por_iid[iid] = u

        if self.on_cambios:
            self.on_cambios()

    def _borrar_seleccionada(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo("Borrar unidad", "Seleccioná primero una unidad de la lista.")
            return
        if confirmar_y_borrar(self, seleccion[0]):
            self._recargar()

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
        mostrar_avisos()
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

class _AbreRecibosMixin:
    """Abrir un PDF de la lista (self.tree / self._archivo_por_iid) o mostrarlo en su carpeta."""

    def _ruta_absoluta_seleccionada(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo("Recibos", "Seleccioná primero un recibo de la lista.")
            return None
        archivo_rel = self._archivo_por_iid.get(seleccion[0], "")
        if not archivo_rel:
            messagebox.showwarning("Recibos", "Este registro no tiene un archivo asociado.")
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


class VentanaHistorial(_AbreRecibosMixin, tk.Toplevel):
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

        columnas = ("numero_recibo", "edificio", "fecha", "expensas_de", "tipo", "piso", "unidad", "inquilino", "importe", "archivo")
        titulos = {
            "numero_recibo": "N°", "edificio": "Edificio", "fecha": "Fecha", "expensas_de": "Expensas de",
            "tipo": "Tipo", "piso": "Piso", "unidad": "Unidad", "inquilino": "Inquilino", "importe": "Importe",
            "archivo": "Archivo",
        }
        anchos = {
            "numero_recibo": 60, "edificio": 150, "fecha": 80, "expensas_de": 110,
            "tipo": 80, "piso": 55, "unidad": 55, "inquilino": 150, "importe": 90, "archivo": 260,
        }

        self.tree = ttk.Treeview(self, columns=columnas, show="headings", height=16)
        for c in columnas:
            self.tree.heading(c, text=titulos[c])
            self.tree.column(c, width=anchos[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(4, 8))
        self.tree.bind("<Double-1>", lambda e: self._abrir_pdf_seleccionado())

        pie = tk.Frame(self, bg=COLOR_FONDO, padx=16)
        pie.pack(fill="x", pady=(0, 12))
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
                r.get("expensas_de", ""), r.get("tipo", ""), r.get("piso", ""), r.get("unidad", ""),
                r.get("inquilino", ""), importe_fmt, r.get("archivo", ""),
            ))
            self._archivo_por_iid[iid] = r.get("archivo", "")


# ===========================================================================
# Ventana: recibos recién generados
# ===========================================================================

class VentanaRecibosGenerados(_AbreRecibosMixin, tk.Toplevel):
    """Lista de los PDF que se acaban de generar, para abrirlos desde ahí."""

    def __init__(self, parent, generados, total, errores=()):
        """generados: lista de (registro_historial, etiqueta_unidad)."""
        super().__init__(parent)
        self.title("Recibos generados")
        self.configure(bg=COLOR_FONDO)
        self.geometry("880x460")
        self.transient(parent)

        tk.Label(
            self, text=f"Se generaron {len(generados)} de {total} recibo(s).", font=FUENTE_BOLD,
            bg=COLOR_FONDO, anchor="w",
        ).pack(fill="x", padx=16, pady=(12, 4))

        columnas = ("numero_recibo", "tipo", "unidad", "inquilino", "importe", "gastos_de", "archivo")
        titulos = {"numero_recibo": "N°", "tipo": "Tipo", "unidad": "Unidad", "inquilino": "Inquilino",
                   "importe": "Importe", "gastos_de": "Gastos de", "archivo": "Archivo"}
        anchos = {"numero_recibo": 60, "tipo": 80, "unidad": 150, "inquilino": 130,
                  "importe": 90, "gastos_de": 110, "archivo": 250}
        self.tree = ttk.Treeview(self, columns=columnas, show="headings", height=12)
        for c in columnas:
            self.tree.heading(c, text=titulos[c])
            self.tree.column(c, width=anchos[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(4, 8))
        self.tree.bind("<Double-1>", lambda e: self._abrir_pdf_seleccionado())

        self._archivo_por_iid = {}
        for i, (r, etiqueta) in enumerate(generados):
            iid = str(i)
            self.tree.insert("", "end", iid=iid, values=(
                r["numero_recibo"], r["tipo"], etiqueta, r["inquilino"],
                format_currency_ar(parse_importe(r["importe"])), r["gastos_de"], r["archivo"],
            ))
            self._archivo_por_iid[iid] = r["archivo"]

        if errores:
            tk.Label(
                self, text="Unidades con error:\n" + "\n".join(errores), fg="#b3261e", bg=COLOR_FONDO,
                justify="left", anchor="w", wraplength=820,
            ).pack(fill="x", padx=16, pady=(0, 6))

        pie = tk.Frame(self, bg=COLOR_FONDO, padx=16)
        pie.pack(fill="x", pady=(0, 12))
        tk.Button(pie, text="Abrir PDF", command=self._abrir_pdf_seleccionado,
                  bg=COLOR_PRIMARIO, fg="white", font=FUENTE_BOLD, padx=12, pady=4).pack(side="left")
        tk.Button(pie, text="Mostrar en carpeta", command=self._mostrar_en_carpeta,
                  padx=12, pady=4).pack(side="left", padx=8)
        tk.Button(pie, text="Cerrar", command=self.destroy, padx=12, pady=4).pack(side="right")
        tk.Label(pie, text="(doble clic en una fila abre el PDF)", bg=COLOR_FONDO,
                 fg="#666666", font=("Segoe UI", 8)).pack(side="left", padx=10)

        if generados:
            self.tree.selection_set("0")


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
        self._hijas_por_iid = {}        # id de depto -> ids de sus cocheras/bauleras

        self._crear_menu()
        self._crear_encabezado()
        self._crear_panel_acciones()
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

    def _crear_panel_acciones(self):
        panel = tk.Frame(self, bg=COLOR_FONDO, padx=16, pady=6)
        panel.pack(fill="x")

        tk.Button(panel, text="Actualizar montos desde planilla", command=self._actualizar_desde_planilla,
                  bg=COLOR_PRIMARIO, fg="white", font=FUENTE_BOLD, padx=10, pady=3).pack(side="left")

    def _crear_tabla(self):
        cont = tk.Frame(self, bg=COLOR_FONDO, padx=16, pady=8)
        cont.pack(fill="both", expand=True)

        columnas = ("sel", "piso", "tipo", "unidad", "uf", "depto", "dueno", "inquilino", "importe", "estado")
        self.tree = ttk.Treeview(cont, columns=columnas, show="headings", selectmode="none")

        titulos = {"sel": "", "piso": "PISO", "tipo": "TIPO", "unidad": "LETRA/N°", "uf": "UF",
                   "depto": "PERTENECE A", "dueno": "DUEÑO", "inquilino": "INQUILINO",
                   "importe": "IMPORTE", "estado": "PAGO"}
        anchos = {"sel": 34, "piso": 50, "tipo": 82, "unidad": 70, "uf": 45, "depto": 85,
                  "dueno": 125, "inquilino": 125, "importe": 100, "estado": 85}
        for c in columnas:
            self.tree.heading(c, text=titulos[c])
            self.tree.column(c, width=anchos[c],
                              anchor="w" if c in ("dueno", "inquilino") else "center")
        for tag, color in (("total", "#1f7a3d"), ("parcial", "#b26a00"),
                           ("deuda", "#b3261e"), ("nopagado", "#666666")):
            self.tree.tag_configure(tag, foreground=color)

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

        tk.Button(pie, text="+ Nueva unidad", command=self._nueva_unidad).pack(side="left", padx=(0, 16))
        tk.Button(pie, text="Seleccionar todas", command=self._seleccionar_todas).pack(side="left")
        tk.Button(pie, text="Quitar todas", command=self._quitar_todas).pack(side="left", padx=8)
        tk.Button(pie, text="Abrir planilla de pagos", command=self._abrir_planilla_pagos).pack(side="left", padx=8)

        tk.Button(
            pie, text="GENERAR RECIBOS PDF", command=self._generar_recibos,
            bg="#1f7a3d", fg="white", font=("Segoe UI", 11, "bold"), padx=18, pady=8
        ).pack(side="right")

        self.var_mostrar_lista = tk.BooleanVar(value=database.get_preferencia(PREF_MOSTRAR_LISTA, "0") == "1")
        tk.Checkbutton(
            pie, text="Mostrar lista de PDF al terminar", variable=self.var_mostrar_lista,
            command=self._guardar_preferencia_lista, bg=COLOR_FONDO, activebackground=COLOR_FONDO,
            font=FUENTE_NORMAL,
        ).pack(side="right", padx=(0, 16))

    def _guardar_preferencia_lista(self):
        try:
            database.set_preferencia(PREF_MOSTRAR_LISTA, "1" if self.var_mostrar_lista.get() else "0")
        except Exception as e:
            manejar_error("No se pudo guardar la preferencia", e)

    # -----------------------------------------------------------------
    # Carga de datos en pantalla
    # -----------------------------------------------------------------

    def _cargar_edificios(self):
        try:
            database.ensure_data_files()
            mostrar_avisos()
            nombres = database.get_nombres_edificios()
            self.combo_edificio["values"] = nombres
            if nombres:
                self.var_edificio.set(nombres[0])
                self._cargar_unidades()
        except Exception as e:
            manejar_error("Error al iniciar", e)

    def _estados_planilla(self, edificio):
        """{id_unidad: estado de pago} según lo guardado en la planilla; vacío si no se puede leer."""
        try:
            return {uid: d["estado"] for uid, d in pagos.leer_planilla(edificio).items()}
        except Exception:
            return {}

    def _valores_fila(self, u, nivel, por_id, estados):
        depto = depto_de(u, por_id)
        return (
            MARCADO if u["id"] in self.seleccionadas else DESMARCADO,
            u["piso"], normalizar_tipo(u["tipo"]), ("↳ " if nivel else "") + u["unidad"], u["uf"],
            etiqueta_unidad(depto) if depto else "", u["dueno"], u["inquilino"],
            format_currency_ar(parse_importe(u["importe"])), estados.get(u["id"], ""),
        )

    @staticmethod
    def _tag_estado(estado):
        return {"total": "total", "parcial": "parcial", "deuda": "deuda", "no pagado": "nopagado"}.get(
            (estado or "").strip().lower(), "")

    def _cargar_unidades(self, mantener_seleccion=False):
        previas = set(self.seleccionadas) if mantener_seleccion else set()
        self.seleccionadas.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._unidades_por_iid = {}
        self._hijas_por_iid = {}

        edificio = self.var_edificio.get()
        if not edificio:
            return

        try:
            todas = database.get_unidades_por_edificio(edificio)
            por_id = indice_por_id(todas)
            estados = self._estados_planilla(edificio)
            for u, nivel in ordenar_con_asociadas(todas):
                if u["id"] in previas:
                    self.seleccionadas.add(u["id"])
                tag = self._tag_estado(estados.get(u["id"]))
                self.tree.insert("", "end", iid=u["id"], values=self._valores_fila(u, nivel, por_id, estados),
                                 tags=(tag,) if tag else ())
                self._unidades_por_iid[u["id"]] = u
                depto = depto_de(u, por_id)
                if depto:
                    self._hijas_por_iid.setdefault(depto["id"], []).append(u["id"])
        except Exception as e:
            manejar_error("No se pudieron cargar las unidades", e)

    def _recargar_unidades(self):
        self._cargar_unidades(mantener_seleccion=True)

    def _nueva_unidad(self):
        edificio = self.var_edificio.get()
        if not edificio:
            messagebox.showwarning("Atención", "Primero creá un edificio desde Administrar → Administrar edificios/unidades.")
            return
        DialogoUnidad(self, edificio, unidad=None, on_guardar=self._recargar_unidades)

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
            DialogoUnidad(self, self.var_edificio.get(), unidad=unidad, on_guardar=self._recargar_unidades)

    def _marcar(self, iid, marcar):
        (self.seleccionadas.add if marcar else self.seleccionadas.discard)(iid)
        valores = list(self.tree.item(iid, "values"))
        valores[0] = MARCADO if marcar else DESMARCADO
        self.tree.item(iid, values=valores)

    def _alternar_seleccion(self, iid):
        """Al tildar/destildar un depto, sus cocheras y bauleras lo acompañan (después se pueden cambiar una por una)."""
        marcar = iid not in self.seleccionadas
        for x in [iid] + self._hijas_por_iid.get(iid, []):
            self._marcar(x, marcar)

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
    # Planilla de pagos
    # -----------------------------------------------------------------

    def _confirmar_planilla_guardada(self, edificio):
        """Si la planilla está abierta en Excel, avisa que lo no guardado no se ve y pregunta si sigue."""
        if not pagos.planilla_abierta(edificio):
            return True
        return messagebox.askyesno(
            "Planilla de pagos abierta",
            "La planilla de pagos de este edificio está abierta en Excel.\n\n"
            "Lo que hayas escrito y NO guardado todavía no se tiene en cuenta. "
            "Guardala (Ctrl+G) y, si podés, cerrala.\n\n¿Querés continuar igual?",
            icon="warning",
        )

    def _actualizar_desde_planilla(self):
        """Toma 'Monto pagado' de la planilla como importe de cada unidad y refresca el estado de pago."""
        edificio = self.var_edificio.get()
        if not edificio:
            messagebox.showwarning("Atención", "Seleccioná un edificio.")
            return
        if not self._confirmar_planilla_guardada(edificio):
            return
        try:
            database.sincronizar_pagos(edificio)
        except PermissionError:
            pass  # planilla abierta: se lee tal como está guardada
        except Exception as e:
            manejar_error("No se pudo preparar la planilla de pagos", e)
            return
        try:
            planilla = pagos.leer_planilla(edificio)
            unidades = database.get_unidades_por_edificio(edificio)
            database.set_importes({u["id"]: planilla[u["id"]]["pagado"] for u in unidades if u["id"] in planilla})
        except Exception as e:
            manejar_error("No se pudieron actualizar los montos desde la planilla", e)
            return

        self._recargar_unidades()
        actualizadas = sum(1 for u in unidades if u["id"] in planilla)
        sin_fila = [etiqueta_unidad(u, indice_por_id(unidades)) for u in unidades if u["id"] not in planilla]
        mensaje = f"Se actualizó el importe de {actualizadas} unidad(es) con el «Monto pagado» de la planilla."
        if sin_fila:
            mensaje += "\n\nNo figuran en la planilla: " + ", ".join(sin_fila)
        messagebox.showinfo("Montos actualizados", mensaje)

    def _abrir_planilla_pagos(self):
        edificio = self.var_edificio.get()
        if not edificio:
            messagebox.showwarning("Atención", "Seleccioná un edificio.")
            return
        try:
            database.sincronizar_pagos(edificio)
        except PermissionError:
            pass  # ya está abierta: se abre/muestra tal como está
        except Exception as e:
            manejar_error("No se pudo preparar la planilla de pagos", e)
            return
        ok, mensaje = abrir_pdf(pagos.ruta_pagos_edificio(edificio))
        if not ok:
            messagebox.showinfo("Planilla de pagos", mensaje)

    # -----------------------------------------------------------------
    # Generación de recibos
    # -----------------------------------------------------------------

    def _generar_recibos(self):
        edificio = self.var_edificio.get()
        if not edificio:
            messagebox.showwarning("Atención", "Seleccioná un edificio.")
            return

        seleccionadas = [i for i in self.tree.get_children() if i in self.seleccionadas]
        if not seleccionadas:
            messagebox.showwarning("Atención", "No hay unidades seleccionadas para generar recibos.")
            return

        expensas_de, mes_anterior = obtener_periodos()

        if not self._confirmar_planilla_guardada(edificio):
            return

        try:
            database.sincronizar_pagos(edificio)
        except PermissionError:
            pass  # planilla abierta: se lee tal como está guardada
        except Exception as e:
            manejar_error("No se pudo preparar la planilla de pagos", e)
            return

        try:
            planilla = pagos.leer_planilla(edificio)
        except Exception as e:
            manejar_error("No se pudo leer la planilla de pagos del edificio", e)
            return
        estados_pagos = {uid: d["estado"] for uid, d in planilla.items()}

        todas_edificio = database.get_unidades_por_edificio(edificio)
        por_id = indice_por_id(todas_edificio)
        unidades_actuales = {u["id"]: u for u in todas_edificio}
        gastos_por_iid = {}
        detalle = []
        hay_diferencias = False
        for iid in seleccionadas:
            u = unidades_actuales.get(iid)
            if not u:
                continue
            texto, estado = pagos.gastos_de_unidad(estados_pagos, u, mes_anterior)
            gastos_por_iid[iid] = texto
            importe = parse_importe(u["importe"])
            nota = texto if estado else f"{texto}  (no figura en la planilla de pagos)"
            nota += f"  |  {format_currency_ar(importe)}"
            dato = planilla.get(iid)
            if dato and abs(dato["pagado"] - importe) > 0.005:
                nota += f"  ⚠ la planilla dice {format_currency_ar(dato['pagado'])}"
                hay_diferencias = True
            detalle.append(f"  {etiqueta_unidad(u, por_id)}: {nota}")

        max_lineas = 15
        resumen = "\n".join(detalle[:max_lineas])
        if len(detalle) > max_lineas:
            resumen += f"\n  ... y {len(detalle) - max_lineas} más"
        aviso_montos = (
            "\n\n⚠ Hay importes distintos al «Monto pagado» de la planilla. Si querés usar los de la "
            "planilla, cancelá y apretá «Actualizar montos desde planilla»."
        ) if hay_diferencias else ""

        if not messagebox.askyesno(
            "Confirmar generación",
            f"Se van a generar {len(seleccionadas)} recibo(s) para:\n\n{edificio}\n\n"
            f"Expensas de: {expensas_de}\nGastos de (según la planilla de pagos) e importe:\n{resumen}"
            f"{aviso_montos}\n\n¿Confirmás?",
        ):
            return

        try:
            inmobiliaria = database.get_inmobiliaria()
            carpeta_destino = database.crear_carpeta_edificio(edificio)

            generados = []   # (registro del historial, etiqueta de la unidad)
            errores = []

            for iid in seleccionadas:
                u = unidades_actuales.get(iid)
                if not u:
                    continue
                gastos_de = gastos_por_iid[iid]
                tipo = normalizar_tipo(u["tipo"])
                depto = depto_de(u, por_id)
                depto_etiqueta = etiqueta_unidad(depto) if depto else ""
                try:
                    numero = database.get_next_numero(edificio)
                    numero_fmt = f"{numero:05d}"
                    importe_valor = parse_importe(u["importe"])

                    ruta_pdf, _nombre = nombre_archivo_recibo(
                        edificio, u["piso"], u["unidad"], expensas_de, numero, carpeta_destino,
                        tipo=tipo, depto=depto_etiqueta,
                    )

                    datos_pdf = {
                        "NUMERO_RECIBO": numero_fmt,
                        "FECHA_EMISION": fecha_hoy_es(),
                        "EDIFICIO_NOMBRE": edificio,
                        "EXPENSAS_DE": expensas_de,
                        "GASTOS_DE": gastos_de,
                        "PISO": u["piso"],
                        "UNIDAD": u["unidad"],
                        "TIPO": tipo,
                        "DEPTO": depto_etiqueta,
                        "UF": u["uf"],
                        "DUENO": u["dueno"],
                        "INQUILINO": u["inquilino"],
                        "IMPORTE": format_currency_ar(importe_valor),
                        "INMOBILIARIA_NOMBRE": inmobiliaria.get("nombre", ""),
                        "INMOBILIARIA_DIRECCION": inmobiliaria.get("direccion", ""),
                        "INMOBILIARIA_TELEFONO": inmobiliaria.get("telefono", ""),
                        "INMOBILIARIA_EMAIL": inmobiliaria.get("email", ""),
                        "INMOBILIARIA_CUIT": inmobiliaria.get("cuit", ""),
                    }

                    generar_pdf_recibo(datos_pdf, ruta_pdf, tipo)

                    registro = {
                        "numero_recibo": numero_fmt,
                        "edificio": edificio,
                        "fecha": fecha_hoy_es(),
                        "expensas_de": expensas_de,
                        "gastos_de": gastos_de,
                        "piso": u["piso"],
                        "tipo": tipo,
                        "unidad": u["unidad"],
                        "inquilino": u["inquilino"],
                        "importe": f"{importe_valor:.2f}",
                        "archivo": os.path.relpath(ruta_pdf, config.BASE_DIR),
                    }
                    database.append_historial(registro)
                    generados.append((registro, etiqueta_unidad(u, por_id)))
                except Exception as e:
                    errores.append(f"{etiqueta_unidad(u, por_id)}: {e}")

            if generados and self.var_mostrar_lista.get():
                VentanaRecibosGenerados(self, generados, len(seleccionadas), errores)
                return

            mensaje = f"Se generaron {len(generados)} de {len(seleccionadas)} recibo(s).\n\nCarpeta:\n{carpeta_destino}"
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
