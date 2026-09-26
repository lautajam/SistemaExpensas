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
from datetime import date
from tkinter import ttk, messagebox, filedialog

import config
import database
from utils import (
    normalizar_cuit,
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
from recibo import armar_datos as armar_datos_recibo
import pagos
from unidades import (
    BAULERA, COCHERA, DEPTO, LOCAL, TIPOS, TIPOS_ASOCIABLES,
    depto_de, descripcion_asociadas, etiqueta_unidad, indice_por_id, nombre_tipo, normalizar_tipo,
    MODO_APARTE, MODO_JUNTO, MODO_TOTAL, asociadas_que_pagan_junto, incluida_en_total, modo_pago,
    ordenar_con_asociadas, ordenar_para_pantalla, paga_junto,
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


# Cómo paga una cochera/baulera de un depto: (código guardado, texto para elegir, texto corto de la lista)
MODOS_PAGO = [
    (MODO_APARTE, "Recibo aparte", "recibo aparte"),
    (MODO_JUNTO, "Paga junto con el depto (tiene su fila en la planilla)", "paga junto"),
    (MODO_TOTAL, "Incluida en el total del depto (sin fila ni celda propia)", "incluida en el total"),
]
_TEXTO_MODO = {cod: largo for cod, largo, _corto in MODOS_PAGO}
_CORTO_MODO = {cod: corto for cod, _largo, corto in MODOS_PAGO}
_CODIGO_MODO = {largo: cod for cod, largo, _corto in MODOS_PAGO}


def confirmar_modo_celdas(parent, edificio):
    """
    Si el edificio todavía no usa celdas, avisa lo que cambia al asignar la primera:
    la app deja de armar y tocar su planilla y solo la lee tal cual. True si sigue.
    """
    if pagos.modo_celdas(database.get_unidades_por_edificio(edificio)):
        return True
    return messagebox.askyesno(
        "Planilla con celdas",
        f"Al asignar una celda, la planilla de pagos de «{edificio}» pasa a usarse tal cual está: "
        "la app deja de modificarla y lee los montos de la celda de cada unidad.\n\n"
        f"El archivo tiene que estar en:\n{pagos.ruta_pagos_edificio(edificio)}\n\n"
        "Las unidades sin celda no van a poder generar recibo hasta que se les asigne una.\n\n"
        "¿Continuar?",
        icon="warning", parent=parent,
    )


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
        self.var_celda = tk.StringVar()
        campos = [
            ("Celda en la planilla (ej. B12):", self.var_celda),
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
            if i == 1:
                entry.focus_set()

        tk.Label(cont, text="El inquilino es el del depto.", font=("Segoe UI", 8), fg="#666666",
                 bg=COLOR_FONDO).grid(row=len(campos), column=0, columnspan=2, sticky="w")
        tk.Label(cont, text="Cómo paga:", font=FUENTE_NORMAL, bg=COLOR_FONDO).grid(
            row=len(campos) + 1, column=0, sticky="w", pady=(6, 0))
        self.var_modo = tk.StringVar(value=_TEXTO_MODO[MODO_APARTE])
        ttk.Combobox(cont, textvariable=self.var_modo, state="readonly", width=20, font=FUENTE_NORMAL,
                     values=[largo for _c, largo, _k in MODOS_PAGO]).grid(
            row=len(campos) + 1, column=1, pady=(6, 0), padx=(10, 0), sticky="w")
        botones = tk.Frame(cont, bg=COLOR_FONDO)
        botones.grid(row=len(campos) + 2, column=0, columnspan=2, pady=(14, 0))
        tk.Button(botones, text="Agregar", command=self._agregar, bg=COLOR_PRIMARIO,
                  fg="white", font=FUENTE_BOLD, padx=14, pady=4).pack(side="left", padx=6)
        tk.Button(botones, text="Cancelar", command=self.destroy, padx=14, pady=4).pack(side="left", padx=6)

    def _agregar(self):
        numero = self.var_unidad.get().strip()
        if not numero:
            messagebox.showwarning("Datos incompletos", "Completá el número.", parent=self)
            return
        try:
            celda = pagos.normalizar_celda(self.var_celda.get())
        except ValueError as e:
            messagebox.showwarning("Celda inválida", str(e), parent=self)
            return
        modo = _CODIGO_MODO[self.var_modo.get()]
        self.on_agregar({
            "tipo": self.tipo,
            "unidad": numero,
            "uf": self.var_uf.get().strip(),
            "piso": self.var_piso.get().strip(),
            "dueno": self.var_dueno.get().strip(),
            "importe": parse_importe(self.var_importe.get()),
            "paga_junto": modo,
            "celda": "" if modo == MODO_TOTAL else celda,
        })
        self.destroy()


class DialogoElegirAsociada(tk.Toplevel):
    """Lista de cocheras/bauleras ya creadas para sumarlas a un depto."""

    def __init__(self, parent, candidatas, on_elegir):
        super().__init__(parent)
        self.candidatas = candidatas
        self.on_elegir = on_elegir

        self.title("Vincular existente")
        self.configure(bg=COLOR_FONDO)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        cont = tk.Frame(self, bg=COLOR_FONDO, padx=20, pady=16)
        cont.pack(fill="both", expand=True)
        tk.Label(cont, text="Cocheras y bauleras sueltas (podés elegir varias):", font=FUENTE_BOLD,
                 bg=COLOR_FONDO).pack(anchor="w")
        self.lista = tk.Listbox(cont, height=min(10, max(3, len(candidatas))), width=34, font=FUENTE_NORMAL,
                                selectmode="extended", exportselection=False)
        for _id, nombre in candidatas:
            self.lista.insert("end", nombre)
        self.lista.pack(fill="x", pady=(6, 0))
        botones = tk.Frame(cont, bg=COLOR_FONDO)
        botones.pack(pady=(14, 0))
        tk.Button(botones, text="Vincular", command=self._elegir, bg=COLOR_PRIMARIO,
                  fg="white", font=FUENTE_BOLD, padx=14, pady=4).pack(side="left", padx=6)
        tk.Button(botones, text="Cancelar", command=self.destroy, padx=14, pady=4).pack(side="left", padx=6)

    def _elegir(self):
        seleccion = self.lista.curselection()
        if not seleccion:
            messagebox.showinfo("Vincular existente", "Elegí al menos una de la lista.", parent=self)
            return
        self.on_elegir([self.candidatas[i] for i in seleccion])
        self.destroy()

class DialogoUnidad(tk.Toplevel):
    def __init__(self, parent, edificio, unidad=None, on_guardar=None):
        super().__init__(parent)
        self.edificio = edificio
        self.unidad = unidad  # dict si es edición, None si es alta
        self.on_guardar = on_guardar
        self._items = []            # lo que muestra la lista de cocheras/bauleras (ver _agregar_item)
        self._a_desvincular = []    # ids de asociadas a soltar del depto al guardar
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
        self.var_celda = tk.StringVar(value=unidad["celda"] if unidad else "")
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

        etiqueta_fila(1, "Celda en la planilla (ej. B12):")
        entrada_fila(1, self.var_celda)

        etiqueta_fila(2, "Tipo de unidad:")
        self.combo_tipo = ttk.Combobox(cont, textvariable=self.var_tipo, state="readonly", width=26,
                                       values=[nombre_tipo(t) for t in TIPOS], font=FUENTE_NORMAL)
        self.combo_tipo.grid(row=2, column=1, pady=4, padx=(10, 0), sticky="w")
        self.combo_tipo.bind("<<ComboboxSelected>>", lambda e: self._actualizar_tipo())

        self.lbl_piso = etiqueta_fila(3, "")
        entrada_fila(3, self.var_piso)
        self.lbl_unidad = etiqueta_fila(4, "")
        entrada_fila(4, self.var_unidad)
        etiqueta_fila(5, "Unidad funcional (UF):")
        entrada_fila(5, self.var_uf)

        self.lbl_depto = etiqueta_fila(6, "Pertenece al depto:")
        self.combo_depto = ttk.Combobox(cont, textvariable=self.var_depto, state="readonly", width=26,
                                        values=list(self._ids_deptos), font=FUENTE_NORMAL)
        self.combo_depto.grid(row=6, column=1, pady=4, padx=(10, 0), sticky="w")
        self.combo_depto.bind("<<ComboboxSelected>>", lambda e: self._al_elegir_depto())

        etiqueta_fila(7, "Dueño:")
        entrada_fila(7, self.var_dueno)
        etiqueta_fila(8, "Inquilino:")
        entrada_fila(8, self.var_inquilino)
        etiqueta_fila(9, "Importe:")
        entrada_fila(9, self.var_importe)

        self.frame_asociadas = tk.Frame(cont, bg=COLOR_FONDO)
        self.frame_asociadas.grid(row=10, column=0, columnspan=2, sticky="we", pady=(10, 0))
        tk.Label(self.frame_asociadas, text="Cocheras y bauleras de este depto:", font=FUENTE_BOLD,
                 bg=COLOR_FONDO).pack(anchor="w")
        tk.Label(self.frame_asociadas, text="Elegí una y abajo cómo paga: aparte, junto con el depto (un solo recibo) "
                 "o incluida en su total.\nQuitar la suelta del depto, no la borra.", font=("Segoe UI", 8),
                 fg="#666666", bg=COLOR_FONDO, justify="left").pack(anchor="w")
        self.lista_asociadas = tk.Listbox(self.frame_asociadas, height=4, font=FUENTE_NORMAL, exportselection=False)
        self.lista_asociadas.pack(fill="x", pady=(4, 4))
        self.lista_asociadas.bind("<<ListboxSelect>>", lambda e: self._mostrar_modo_item())
        if unidad:
            for h, n in ordenar_con_asociadas(todas):
                if n == 1 and h["depto_id"] == unidad["id"]:
                    self._agregar_item("actual", etiqueta_unidad(h).split(" (")[0], modo=modo_pago(h), id=h["id"])
        barra = tk.Frame(self.frame_asociadas, bg=COLOR_FONDO)
        barra.pack(anchor="w")
        tk.Button(barra, text="Vincular existente", command=self._vincular_existente).pack(side="left")
        tk.Button(barra, text="+ Cochera nueva", command=lambda: self._nueva_asociada(COCHERA)).pack(side="left", padx=6)
        tk.Button(barra, text="+ Baulera nueva", command=lambda: self._nueva_asociada(BAULERA)).pack(side="left")
        tk.Button(barra, text="Quitar", command=self._quitar_asociada).pack(side="left", padx=6)
        fila_modo = tk.Frame(self.frame_asociadas, bg=COLOR_FONDO)
        fila_modo.pack(anchor="w", pady=(6, 0))
        tk.Label(fila_modo, text="Cómo paga la elegida:", font=FUENTE_NORMAL, bg=COLOR_FONDO).pack(side="left")
        self.var_modo_item = tk.StringVar()
        self.combo_modo_item = ttk.Combobox(fila_modo, textvariable=self.var_modo_item, state="readonly", width=48,
                                            font=FUENTE_NORMAL, values=[largo for _c, largo, _k in MODOS_PAGO])
        self.combo_modo_item.pack(side="left", padx=(8, 0))
        self.combo_modo_item.bind("<<ComboboxSelected>>", lambda e: self._fijar_modo_item(self.var_modo_item.get()))

        # Cochera/baulera: "cómo paga" propio (ocupa el lugar de la lista, que solo se ve en un depto)
        self.fila_modo_asoc = tk.Frame(cont, bg=COLOR_FONDO)
        self.fila_modo_asoc.grid(row=10, column=0, columnspan=2, sticky="w", pady=(6, 0))
        tk.Label(self.fila_modo_asoc, text="Cómo paga:", font=FUENTE_NORMAL, bg=COLOR_FONDO).pack(side="left")
        self.var_modo_asoc = tk.StringVar(value=_TEXTO_MODO[modo_pago(unidad) if unidad else MODO_APARTE])
        self.combo_modo_asoc = ttk.Combobox(self.fila_modo_asoc, textvariable=self.var_modo_asoc, state="readonly",
                                            width=48, font=FUENTE_NORMAL, values=[largo for _c, largo, _k in MODOS_PAGO])
        self.combo_modo_asoc.pack(side="left", padx=(8, 0))

        botones = tk.Frame(cont, bg=COLOR_FONDO)
        botones.grid(row=11, column=0, columnspan=2, pady=(16, 0))
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
        (self.fila_modo_asoc.grid if tipo in TIPOS_ASOCIABLES else self.fila_modo_asoc.grid_remove)()
        self._actualizar_junto_asoc()

    def _actualizar_junto_asoc(self):
        con_depto = bool(self._ids_deptos.get(self.var_depto.get(), ""))
        self.combo_modo_asoc.config(state="readonly" if con_depto else "disabled")
        if not con_depto:
            self.var_modo_asoc.set(_TEXTO_MODO[MODO_APARTE])

    def _al_elegir_depto(self):
        self._actualizar_junto_asoc()
        depto = self._por_id.get(self._ids_deptos.get(self.var_depto.get(), ""))
        if not depto:
            return
        actual = self.var_inquilino.get().strip()
        if not actual or actual == self._autoinquilino:
            self.var_inquilino.set(depto["inquilino"])
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
        self.lista_asociadas.insert("end", self._texto_item(self._items[-1]))

    def _mostrar_modo_item(self):
        seleccion = self.lista_asociadas.curselection()
        self.var_modo_item.set(_TEXTO_MODO[self._items[seleccion[0]]["modo"]] if seleccion else "")

    def _fijar_modo_item(self, texto):
        """Cambia cómo paga la cochera/baulera elegida en la lista (texto largo del combo)."""
        seleccion = self.lista_asociadas.curselection()
        if not seleccion:
            messagebox.showinfo("Cómo paga", "Elegí primero la cochera o baulera de la lista.", parent=self)
            self.var_modo_item.set("")
            return
        i = seleccion[0]
        self._items[i]["modo"] = _CODIGO_MODO[texto]
        self.lista_asociadas.delete(i)
        self.lista_asociadas.insert(i, self._texto_item(self._items[i]))
        self.lista_asociadas.selection_set(i)

    def _nueva_asociada(self, tipo):
        DialogoAsociada(self, tipo, self._agregar_asociada)

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
            messagebox.showinfo("Vincular existente", "No hay cocheras ni bauleras sueltas en este edificio.\n"
                                "Podés crear una con '+ Cochera nueva' o '+ Baulera nueva'.", parent=self)
            return
        DialogoElegirAsociada(self, candidatas, self._agregar_vinculadas)

    def _agregar_vinculadas(self, elegidas):
        for uid, nombre in elegidas:
            if uid in self._a_desvincular:      # la había soltado hace un rato: vuelve a quedar como estaba
                self._a_desvincular.remove(uid)
                self._agregar_item("actual", nombre, modo=modo_pago(self._por_id[uid]), id=uid)
            else:
                self._agregar_item("vincular", nombre, id=uid)

    def _quitar_asociada(self):
        seleccion = self.lista_asociadas.curselection()
        if not seleccion:
            messagebox.showinfo("Quitar", "Elegí primero la cochera o baulera de la lista.", parent=self)
            return
        item = self._items.pop(seleccion[0])
        self.lista_asociadas.delete(seleccion[0])
        if item["estado"] == "actual":
            self._a_desvincular.append(item["id"])
        self._mostrar_modo_item()

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

        try:
            celda = pagos.normalizar_celda(self.var_celda.get())
        except ValueError as e:
            messagebox.showwarning("Celda inválida", str(e), parent=self)
            return

        depto_id = self._ids_deptos.get(self.var_depto.get(), "") if tipo in TIPOS_ASOCIABLES else ""
        items = self._items if tipo == DEPTO else []
        asociadas = [dict(it["datos"], inquilino=inquilino, paga_junto=it["modo"]) for it in items if it["estado"] == "nueva"]
        a_vincular = [it for it in items if it["estado"] == "vincular"]
        a_cambiar = [it for it in items if it["estado"] == "actual" and it["modo"] != it["modo_orig"]]
        uf, dueno = self.var_uf.get().strip(), self.var_dueno.get().strip()
        # solo una cochera/baulera de un depto tiene "cómo paga"; una incluida en el total no lleva celda propia
        modo = _CODIGO_MODO[self.var_modo_asoc.get()] if depto_id else MODO_APARTE
        if modo == MODO_TOTAL:
            celda = ""

        nuevas_celdas = ([celda] if celda else []) + [a["celda"] for a in asociadas if a.get("celda")]
        if nuevas_celdas and not confirmar_modo_celdas(self, self.edificio):
            return

        try:
            if self.unidad:
                database.update_unidad(
                    self.unidad["id"],
                    piso=piso, tipo=tipo, unidad=unidad_txt, uf=uf, dueno=dueno,
                    inquilino=inquilino, importe=str(importe), depto_id=depto_id,
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
# Diálogo: datos del consorcio (nombre, dirección, CUIT y administrador)
# ===========================================================================

class DialogoDatosConsorcio(tk.Toplevel):
    def __init__(self, parent, nombre_edificio, on_guardar=None):
        super().__init__(parent)
        self.nombre_original = nombre_edificio
        self.on_guardar = on_guardar
        datos = database.get_edificio(nombre_edificio) or {}

        self.title("Datos del consorcio")
        self.configure(bg=COLOR_FONDO)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        cont = tk.Frame(self, bg=COLOR_FONDO, padx=20, pady=16)
        cont.pack(fill="both", expand=True)

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
        self.vars = {}
        fila = 0
        for titulo, campos in grupos:
            tk.Label(cont, text=titulo, font=FUENTE_BOLD, bg=COLOR_FONDO, fg=COLOR_PRIMARIO).grid(
                row=fila, column=0, columnspan=2, sticky="w", pady=(12 if fila else 0, 2))
            fila += 1
            for clave, etiqueta in campos:
                tk.Label(cont, text=etiqueta, font=FUENTE_NORMAL, bg=COLOR_FONDO).grid(
                    row=fila, column=0, sticky="w", pady=4)
                var = tk.StringVar(value=datos.get(clave, ""))
                tk.Entry(cont, textvariable=var, width=38, font=FUENTE_NORMAL).grid(
                    row=fila, column=1, pady=4, padx=(10, 0))
                self.vars[clave] = var
                fila += 1

        tk.Label(cont, text="Si cambiás el nombre, se actualiza en las unidades, el historial, la numeración,\n"
                            "la carpeta de recibos y la planilla de pagos.",
                 font=("Segoe UI", 8), fg="#666666", bg=COLOR_FONDO, justify="left").grid(
            row=fila, column=0, columnspan=2, sticky="w", pady=(8, 0))

        botones = tk.Frame(cont, bg=COLOR_FONDO)
        botones.grid(row=fila + 1, column=0, columnspan=2, pady=(14, 0))
        tk.Button(botones, text="Guardar", command=self._guardar, bg=COLOR_PRIMARIO,
                  fg="white", font=FUENTE_BOLD, padx=14, pady=4).pack(side="left", padx=6)
        tk.Button(botones, text="Cancelar", command=self.destroy, padx=14, pady=4).pack(side="left", padx=6)

    def _guardar(self):
        datos = {clave: var.get().strip() for clave, var in self.vars.items()}
        if not datos["nombre"]:
            messagebox.showwarning("Datos incompletos", "El nombre del consorcio no puede quedar vacío.", parent=self)
            return
        try:
            datos["cuit"] = normalizar_cuit(datos["cuit"])
            datos["admin_cuit"] = normalizar_cuit(datos["admin_cuit"])
        except ValueError as e:
            messagebox.showwarning("CUIT inválido", str(e), parent=self)
            return

        if datos["nombre"] != self.nombre_original and not messagebox.askyesno(
            "Cambiar el nombre del consorcio",
            f"Vas a cambiar el nombre de «{self.nombre_original}» a «{datos['nombre']}».\n\n"
            "Se actualiza en las unidades, el historial, la numeración de recibos, la carpeta de "
            "recibos y la planilla de pagos.\nCerrá la planilla de Excel y los PDF de este consorcio "
            "si están abiertos.\n\n¿Continuar?",
            parent=self,
        ):
            return

        try:
            nombre_final = database.update_edificio(self.nombre_original, **datos)
        except PermissionError:
            messagebox.showwarning(
                "Archivos abiertos",
                "No se pudo cambiar el nombre porque hay archivos abiertos de este consorcio "
                "(la planilla de pagos en Excel o algún PDF de sus recibos).\n\n"
                "Cerralos y probá de nuevo. No se modificó nada.",
                parent=self,
            )
            return
        except ValueError as e:
            messagebox.showwarning("No se pudo guardar", str(e), parent=self)
            return
        except Exception as e:
            manejar_error("No se pudieron guardar los datos del consorcio", e)
            return

        mostrar_avisos()
        if self.on_guardar:
            self.on_guardar(nombre_final)
        self.destroy()


# ===========================================================================
# Diálogo: borrar un edificio (se archiva, no se pierde)
# ===========================================================================

class DialogoBorrarEdificio(tk.Toplevel):
    """Muestra qué tiene el edificio y pide escribir su nombre para confirmar el borrado."""

    def __init__(self, parent, edificio, on_borrado=None):
        super().__init__(parent)
        self.edificio = edificio
        self.on_borrado = on_borrado
        self.title("Borrar edificio")
        self.configure(bg=COLOR_FONDO)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        r = database.resumen_edificio(edificio)
        cont = tk.Frame(self, bg=COLOR_FONDO, padx=20, pady=16)
        cont.pack(fill="both", expand=True)
        tk.Label(cont, text=f"Borrar «{edificio}»", font=FUENTE_BOLD, bg=COLOR_FONDO, fg="#b3261e").pack(anchor="w")
        tk.Label(
            cont, bg=COLOR_FONDO, font=FUENTE_NORMAL, justify="left", wraplength=430,
            text=f"Tiene {r['unidades']} unidad(es), {r['recibos']} recibo(s) en el historial y "
                 f"{r['pdfs']} PDF.\n\nDeja de aparecer en la app. Sus unidades, historial, numeración, carpeta de "
                 "recibos y planilla de pagos NO se pierden: se guardan en datos/edificios_borrados/ para "
                 "poder recuperarlos a mano.\n\nCerrá la planilla de Excel y los PDF de este edificio si están abiertos.",
        ).pack(anchor="w", pady=(8, 10))
        tk.Label(cont, text="Para confirmar, escribí el nombre del edificio:", font=FUENTE_NORMAL,
                 bg=COLOR_FONDO).pack(anchor="w")
        self.var_nombre = tk.StringVar()
        entrada = tk.Entry(cont, textvariable=self.var_nombre, width=44, font=FUENTE_NORMAL)
        entrada.pack(anchor="w", pady=(4, 12))
        entrada.focus_set()

        botones = tk.Frame(cont, bg=COLOR_FONDO)
        botones.pack()
        self.btn_borrar = tk.Button(botones, text="Borrar edificio", command=self._borrar, bg="#b3261e", fg="white",
                                    font=FUENTE_BOLD, padx=14, pady=4, state="disabled")
        self.btn_borrar.pack(side="left", padx=6)
        tk.Button(botones, text="Cancelar", command=self.destroy, padx=14, pady=4).pack(side="left", padx=6)
        self.var_nombre.trace_add("write", lambda *_: self.btn_borrar.config(
            state="normal" if self.var_nombre.get().strip() == self.edificio else "disabled"))

    def _borrar(self):
        if self.var_nombre.get().strip() != self.edificio:
            return
        try:
            destino = database.delete_edificio(self.edificio)
        except PermissionError:
            messagebox.showwarning(
                "Archivos abiertos",
                "No se pudo borrar porque hay archivos abiertos de este edificio (la planilla de pagos en "
                "Excel o algún PDF de sus recibos).\n\nCerralos y probá de nuevo. No se modificó nada.",
                parent=self)
            return
        except ValueError as e:
            messagebox.showwarning("No se pudo borrar", str(e), parent=self)
            return
        except Exception as e:
            manejar_error("No se pudo borrar el edificio", e)
            return
        self.destroy()
        if self.on_borrado:
            self.on_borrado(destino)


# ===========================================================================
# Ventana: asignar la celda de la planilla de pagos a cada unidad
# ===========================================================================

SIN_CELDA = "Sin celda"


class VentanaAsignarCeldas(tk.Toplevel):
    """Una fila por unidad del edificio con la celda donde figura en la planilla de pagos."""

    def __init__(self, parent, edificio, on_guardar=None):
        super().__init__(parent)
        self.edificio = edificio
        self.on_guardar = on_guardar
        self.title("Asignar celdas de la planilla")
        self.configure(bg=COLOR_FONDO)
        self.geometry("520x560")
        self.transient(parent)
        self.grab_set()

        tk.Label(self, text=f"Edificio: {edificio}", font=FUENTE_BOLD, bg=COLOR_FONDO).pack(
            anchor="w", padx=16, pady=(14, 2))
        tk.Label(
            self, bg=COLOR_FONDO, fg="#666666", font=("Segoe UI", 8), justify="left", wraplength=480,
            text="Escribí, para cada unidad, la celda donde está su nombre en la planilla (ej. B12). "
                 "Los montos se leen de las 4 celdas de la derecha: Total a pagar, Monto deuda, "
                 "Monto pagado y Tipo pago. Dejala vacía si la unidad no figura.\n"
                 f"Archivo: {pagos.ruta_pagos_edificio(edificio)}",
        ).pack(anchor="w", padx=16, pady=(0, 8))

        botones = tk.Frame(self, bg=COLOR_FONDO)
        botones.pack(side="bottom", pady=12)
        tk.Button(botones, text="Guardar", command=self._guardar, bg=COLOR_PRIMARIO,
                  fg="white", font=FUENTE_BOLD, padx=14, pady=4).pack(side="left", padx=6)
        tk.Button(botones, text="Cancelar", command=self.destroy, padx=14, pady=4).pack(side="left", padx=6)

        zona = tk.Frame(self, bg=COLOR_FONDO)
        zona.pack(fill="both", expand=True, padx=16)
        canvas = tk.Canvas(zona, bg=COLOR_FONDO, highlightthickness=0)
        barra = ttk.Scrollbar(zona, orient="vertical", command=canvas.yview)
        interior = tk.Frame(canvas, bg=COLOR_FONDO)
        interior.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=interior, anchor="nw")
        canvas.configure(yscrollcommand=barra.set)
        canvas.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(-1 * (ev.delta // 120), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        todas = database.get_unidades_por_edificio(edificio)
        por_id = indice_por_id(todas)
        self.vars = {}
        self._antes = {u["id"]: u["celda"] for u in todas}
        for i, (u, nivel) in enumerate([(u, n) for u, n in ordenar_con_asociadas(todas) if not incluida_en_total(u)]):
            texto = ("      " if nivel else "") + f"{nombre_tipo(normalizar_tipo(u['tipo']))} — {etiqueta_unidad(u, por_id)}"
            tk.Label(interior, text=texto, font=FUENTE_NORMAL, bg=COLOR_FONDO, anchor="w", width=42).grid(
                row=i, column=0, sticky="w", pady=2)
            var = tk.StringVar(value=u["celda"])
            tk.Entry(interior, textvariable=var, width=10, font=FUENTE_NORMAL).grid(row=i, column=1, padx=(8, 0), pady=2)
            self.vars[u["id"]] = var
        if not todas:
            tk.Label(interior, text="Este edificio todavía no tiene unidades.", bg=COLOR_FONDO,
                     font=FUENTE_NORMAL).grid(row=0, column=0, pady=10)

    def _guardar(self):
        try:
            celdas = {uid: pagos.normalizar_celda(var.get()) for uid, var in self.vars.items()}
        except ValueError as e:
            messagebox.showwarning("Celda inválida", str(e), parent=self)
            return
        habia, habra = any(self._antes.values()), any(celdas.values())
        if habra and not habia and not confirmar_modo_celdas(self, self.edificio):
            return
        if habia and not habra and not messagebox.askyesno(
            "Volver a la planilla automática",
            "Sin ninguna celda asignada, la app vuelve a armar su propia planilla de pagos en ese archivo "
            "(antes guarda una copia de tu Excel con el nombre «..._respaldo_...»).\n\n¿Continuar?",
            icon="warning", parent=self,
        ):
            return
        try:
            database.set_celdas(self.edificio, celdas)
        except ValueError as e:
            messagebox.showwarning("No se pudo guardar", str(e), parent=self)
            return
        except Exception as e:
            manejar_error("No se pudieron guardar las celdas", e)
            return
        if habia and not habra:
            try:
                database.sincronizar_pagos(self.edificio, reemplazar_ajena=True)
            except PermissionError:
                messagebox.showwarning(
                    "Planilla abierta",
                    "Se quitaron las celdas, pero la planilla está abierta en Excel y no se pudo rearmar.\n"
                    "Cerrala: se rearma sola la próxima vez que se guarde algo.", parent=self)
            except Exception as e:
                manejar_error("No se pudo rearmar la planilla de pagos", e)
        if self.on_guardar:
            self.on_guardar()
        self.destroy()


# ===========================================================================
# Ventana: administración de edificios / unidades
# ===========================================================================

class VentanaAdministracion(tk.Toplevel):
    def __init__(self, parent, edificio_inicial, on_cambios=None):
        super().__init__(parent)
        self.on_cambios = on_cambios
        self.title("Administrar edificios y unidades")
        self.configure(bg=COLOR_FONDO)
        self.geometry("1000x500")
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

        tk.Button(top, text="Datos del consorcio", command=self._datos_consorcio,
                  bg=COLOR_PRIMARIO, fg="white", font=FUENTE_BOLD).pack(side="left", padx=6)
        tk.Button(top, text="+ Nuevo edificio", command=self._nuevo_edificio).pack(side="left", padx=6)
        tk.Button(top, text="Borrar edificio", command=self._borrar_edificio, bg="#b3261e",
                  fg="white").pack(side="left", padx=6)
        tk.Button(top, text="+ Nueva unidad", command=self._nueva_unidad).pack(side="left", padx=6)
        tk.Button(top, text="Asignar celdas", command=self._asignar_celdas).pack(side="left", padx=6)
        tk.Button(top, text="Abrir carpeta del edificio", command=self._abrir_carpeta).pack(side="left", padx=6)

        columnas = ("piso", "tipo", "unidad", "uf", "depto", "dueno", "inquilino", "importe", "celda")
        self.tree = ttk.Treeview(self, columns=columnas, show="headings", height=16)
        titulos = {"piso": "PISO", "tipo": "TIPO", "unidad": "LETRA/N°", "uf": "UF", "depto": "PERTENECE A",
                   "dueno": "DUEÑO", "inquilino": "INQUILINO", "importe": "IMPORTE", "celda": "CELDA"}
        anchos = {"piso": 60, "tipo": 80, "unidad": 80, "uf": 50, "depto": 90, "dueno": 130, "inquilino": 130,
                  "importe": 100, "celda": 60}
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
                etiqueta_unidad(depto) if depto else "", u["dueno"], u["inquilino"], importe_fmt, u["celda"],
            ))
            self._unidades_por_iid[iid] = u

        if self.on_cambios:
            self.on_cambios(edificio)

    def _asignar_celdas(self):
        edificio = self.var_edificio.get()
        if not edificio:
            messagebox.showwarning("Atención", "Primero seleccioná o creá un edificio.")
            return
        VentanaAsignarCeldas(self, edificio, on_guardar=self._recargar)

    def _datos_consorcio(self):
        edificio = self.var_edificio.get()
        if not edificio:
            messagebox.showwarning("Atención", "Primero seleccioná o creá un edificio.")
            return

        def al_guardar(nombre_nuevo):
            self.combo_edificio["values"] = database.get_nombres_edificios()
            self.var_edificio.set(nombre_nuevo)
            self._recargar()

        DialogoDatosConsorcio(self, edificio, on_guardar=al_guardar)

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

    def _borrar_edificio(self):
        edificio = self.var_edificio.get()
        if not edificio:
            messagebox.showwarning("Atención", "Primero seleccioná un edificio.")
            return

        def al_borrar(destino):
            nombres = database.get_nombres_edificios()
            self.combo_edificio["values"] = nombres
            self.var_edificio.set(nombres[0] if nombres else "")
            self._recargar()
            messagebox.showinfo("Edificio borrado", f"Se borró «{edificio}».\n\nSus datos, recibos PDF y planilla "
                                f"quedaron guardados en:\n{destino}", parent=self)

        DialogoBorrarEdificio(self, edificio, on_borrado=al_borrar)

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
            ("subtitulo", "Subtítulo:"),
            ("direccion", "Dirección:"),
            ("telefono", "Teléfono:"),
            ("email", "Email:"),
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

        # Logo y firma digital. Los cambios se aplican al apretar "Guardar".
        self._imagenes = {}   # clave -> ruta elegida (str) o None si se quitó; ausente = sin cambios
        self._vistas = {}     # clave -> Label con la vista previa
        self._fotos = {}      # referencias a las imágenes de las vistas previas
        for j, (clave, titulo) in enumerate((("logo", "Logo:"), ("firma", "Firma digital:")), start=len(etiquetas)):
            tk.Label(cont, text=titulo, font=FUENTE_NORMAL, bg=COLOR_FONDO).grid(
                row=j, column=0, sticky="nw", pady=(10, 4))
            marco = tk.Frame(cont, bg=COLOR_FONDO)
            marco.grid(row=j, column=1, sticky="w", padx=(10, 0), pady=(10, 4))
            vista = tk.Label(marco, bg="white", relief="solid", bd=1, width=28, height=4,
                             font=("Segoe UI", 8), fg="#666666")
            vista.pack(side="left")
            self._vistas[clave] = vista
            barra = tk.Frame(marco, bg=COLOR_FONDO)
            barra.pack(side="left", padx=(8, 0))
            tk.Button(barra, text="Elegir imagen...", command=lambda c=clave: self._elegir_imagen(c)).pack(anchor="w")
            tk.Button(barra, text="Quitar", command=lambda c=clave: self._quitar_imagen(c)).pack(anchor="w", pady=(4, 0))
            self._mostrar_vista(clave, database.imagen_inmobiliaria(clave))

        tk.Label(cont, text="El logo y la firma se guardan, pero todavía no se usan en los recibos.",
                 font=("Segoe UI", 8), fg="#666666", bg=COLOR_FONDO).grid(
            row=len(etiquetas) + 2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        botones = tk.Frame(cont, bg=COLOR_FONDO)
        botones.grid(row=len(etiquetas) + 3, column=0, columnspan=2, pady=(16, 0))
        tk.Button(botones, text="Guardar", command=self._guardar, bg=COLOR_PRIMARIO,
                   fg="white", font=FUENTE_BOLD, padx=14, pady=4).pack(side="left", padx=6)
        tk.Button(botones, text="Cerrar", command=self.destroy, padx=14, pady=4).pack(side="left", padx=6)

    def _mostrar_vista(self, clave, ruta):
        """Muestra una miniatura de la imagen (o 'Sin imagen') en la vista previa."""
        vista = self._vistas[clave]
        self._fotos.pop(clave, None)
        if not ruta:
            vista.config(image="", text="Sin imagen", width=28, height=4)
            return
        try:
            from PIL import Image, ImageTk
            with Image.open(ruta) as img:
                miniatura = img.convert("RGBA")
            miniatura.thumbnail((200, 70))
            fondo = Image.new("RGBA", miniatura.size, "white")
            fondo.alpha_composite(miniatura)
            self._fotos[clave] = ImageTk.PhotoImage(fondo)
            vista.config(image=self._fotos[clave], text="", width=miniatura.width, height=miniatura.height)
        except Exception:
            vista.config(image="", text=os.path.basename(ruta), width=28, height=4)

    def _elegir_imagen(self, clave):
        ruta = filedialog.askopenfilename(
            parent=self, title="Elegir imagen",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Todos los archivos", "*.*")],
        )
        if not ruta:
            return
        try:
            from PIL import Image
            with Image.open(ruta) as img:
                img.verify()
        except Exception:
            messagebox.showwarning("Imagen no válida", "El archivo elegido no es una imagen válida (usá PNG o JPG).",
                                   parent=self)
            return
        self._imagenes[clave] = ruta
        self._mostrar_vista(clave, ruta)

    def _quitar_imagen(self, clave):
        self._imagenes[clave] = None
        self._mostrar_vista(clave, None)

    def _guardar(self):
        try:
            datos = {clave: var.get().strip() for clave, var in self.vars.items()}
            database.save_inmobiliaria(datos)
            for clave, ruta in self._imagenes.items():
                if ruta is None:
                    database.quitar_imagen_inmobiliaria(clave)
                else:
                    database.guardar_imagen_inmobiliaria(clave, ruta)
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

    @staticmethod
    def _crear_circulo(relleno, borde, tam=14):
        """Imagen de un círculo de color (los emojis de Tk en Windows salen en blanco y negro)."""
        img = tk.PhotoImage(width=tam, height=tam)
        c, radio = (tam - 1) / 2, tam / 2
        for x in range(tam):
            for y in range(tam):
                d = ((x - c) ** 2 + (y - c) ** 2) ** 0.5
                if d <= radio - 1.2:
                    img.put(relleno, to=(x, y))
                elif d <= radio:
                    img.put(borde, to=(x, y))
        return img

    def _crear_tabla(self):
        cont = tk.Frame(self, bg=COLOR_FONDO, padx=16, pady=8)
        cont.pack(fill="both", expand=True)

        columnas = ("sel", "piso", "tipo", "unidad", "uf", "depto", "dueno", "inquilino", "importe", "estado")
        # La columna #0 (a la izquierda) lleva el círculo verde/rojo de "recibo emitido"
        self.tree = ttk.Treeview(cont, columns=columnas, show=("tree", "headings"), selectmode="none")
        self.icono_emitido = self._crear_circulo("#2e9e4f", "#1b6b33")
        self.icono_pendiente = self._crear_circulo("#e0392b", "#9c2116")
        self.tree.heading("#0", text="RECIBO")
        self.tree.column("#0", width=64, minwidth=64, stretch=False, anchor="center")

        titulos = {"sel": "", "piso": "PISO", "tipo": "TIPO", "unidad": "LETRA/N°", "uf": "UF",
                   "depto": "RELACIÓN", "dueno": "DUEÑO", "inquilino": "INQUILINO",
                   "importe": "IMPORTE", "estado": "PAGO"}
        anchos = {"sel": 34, "piso": 50, "tipo": 78, "unidad": 65, "uf": 45, "depto": 190,
                  "dueno": 110, "inquilino": 110, "importe": 100, "estado": 80}
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
            text="Clic en la casilla para seleccionar/deseleccionar. Doble clic en el resto de la fila para editar la unidad. "
                 "RECIBO: círculo verde = ya se emitió el recibo de las expensas del período; rojo = todavía no.",
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
        """
        {id_unidad: estado de pago} según lo guardado en la planilla; vacío si no se puede leer.
        Con planilla por celdas, las unidades sin celda figuran como SIN_CELDA.
        """
        unidades = database.get_unidades_por_edificio(edificio)
        try:
            estados = {uid: d["estado"] for uid, d in pagos.leer_planilla(edificio, unidades).items()}
        except Exception:
            estados = {}
        if pagos.modo_celdas(unidades):
            estados.update({u["id"]: SIN_CELDA for u in unidades if not u["celda"] and not incluida_en_total(u)})
        return estados

    @staticmethod
    def _estado_fila(u, agrupadas, estados):
        """Estado de pago de una fila; si el depto paga todo junto, el del grupo completo."""
        if agrupadas:
            miembros = [estados.get(m["id"]) for m in [u] + list(agrupadas)]
            if SIN_CELDA in miembros:
                return SIN_CELDA
            return pagos.estado_agregado(miembros) or ""
        return estados.get(u["id"], "")

    def _valores_fila(self, u, nivel, por_id, estados, agrupadas=()):
        depto = depto_de(u, por_id)
        if agrupadas:
            relacion = "con " + descripcion_asociadas(agrupadas)
        elif depto:
            relacion = "de " + etiqueta_unidad(depto)
        else:
            relacion = ""
        importe = sum(parse_importe(m["importe"]) for m in [u] + list(agrupadas) if not incluida_en_total(m))
        return (
            MARCADO if u["id"] in self.seleccionadas else DESMARCADO,
            u["piso"], normalizar_tipo(u["tipo"]), ("↳ " if nivel else "") + u["unidad"], u["uf"],
            relacion, u["dueno"], u["inquilino"],
            format_currency_ar(importe), self._estado_fila(u, agrupadas, estados),
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
            emitidos = self._claves_emitidas(edificio)
            for u, nivel, agrupadas in ordenar_para_pantalla(todas):
                if u["id"] in previas:
                    self.seleccionadas.add(u["id"])
                tag = self._tag_estado(self._estado_fila(u, agrupadas, estados))
                emitido = (u["piso"], normalizar_tipo(u["tipo"]), u["unidad"]) in emitidos
                self.tree.insert("", "end", iid=u["id"],
                                 image=self.icono_emitido if emitido else self.icono_pendiente,
                                 values=self._valores_fila(u, nivel, por_id, estados, agrupadas),
                                 tags=(tag,) if tag else ())
                self._unidades_por_iid[u["id"]] = u
                depto = depto_de(u, por_id)
                if depto:
                    self._hijas_por_iid.setdefault(depto["id"], []).append(u["id"])
        except Exception as e:
            manejar_error("No se pudieron cargar las unidades", e)

    @staticmethod
    def _claves_emitidas(edificio):
        """
        {(piso, tipo, unidad)} de las unidades del edificio con recibo ya generado para las
        expensas del período actual (según el historial). Un grupo «A + Cochera 6» cuenta para «A».
        """
        expensas_de = obtener_periodos()[0]
        try:
            historial = database.get_historial()
        except Exception:
            return set()
        return {(r.get("piso") or "", r.get("tipo") or "", (r.get("unidad") or "").split(" + ")[0])
                for r in historial if r.get("edificio") == edificio and r.get("expensas_de") == expensas_de}

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
            unidades = database.get_unidades_por_edificio(edificio)
            planilla = pagos.leer_planilla(edificio, unidades)
            database.set_importes({u["id"]: planilla[u["id"]]["pagado"] for u in unidades if u["id"] in planilla})
        except Exception as e:
            manejar_error("No se pudieron actualizar los montos desde la planilla", e)
            return

        self._recargar_unidades()
        actualizadas = sum(1 for u in unidades if u["id"] in planilla)
        sin_fila = [etiqueta_unidad(u, indice_por_id(unidades)) for u in unidades
                    if u["id"] not in planilla and not incluida_en_total(u)]
        mensaje = f"Se actualizó el importe de {actualizadas} unidad(es) con el «Monto pagado» de la planilla."
        if sin_fila:
            mensaje += ("\n\nSin celda asignada: " if pagos.modo_celdas(unidades) else "\n\nNo figuran en la planilla: ") \
                + ", ".join(sin_fila)
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

        todas_edificio = database.get_unidades_por_edificio(edificio)
        try:
            planilla = pagos.leer_planilla(edificio, todas_edificio)
        except Exception as e:
            manejar_error("No se pudo leer la planilla de pagos del edificio", e)
            return
        estados_pagos = {uid: d["estado"] for uid, d in planilla.items()}

        por_id = indice_por_id(todas_edificio)
        con_celdas = pagos.modo_celdas(todas_edificio)
        unidades_actuales = {u["id"]: u for u in todas_edificio}
        hijas = asociadas_que_pagan_junto(todas_edificio)

        # Un depto que paga todo junto genera UN solo recibo (con su cochera y baulera).
        plan = []
        detalle = []
        sin_celda = []
        hay_diferencias = False
        for iid in seleccionadas:
            u = unidades_actuales.get(iid)
            if not u:
                continue
            agrupadas = hijas.get(iid, [])
            miembros = [u] + agrupadas
            if con_celdas and any(not m["celda"] for m in miembros if not incluida_en_total(m)):
                # Sin celda no se sabe cuánto pagó ni el tipo de pago: no se genera el recibo.
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

            etiqueta = etiqueta_unidad(u, por_id) + (
                f" (con {descripcion_asociadas(agrupadas)})" if agrupadas else "")
            nota = texto if estado else f"{texto}  (no figura en la planilla de pagos)"
            nota += f"  |  {format_currency_ar(importe)}"
            pagado = [planilla[m["id"]]["pagado"] for m in miembros if m["id"] in planilla]
            if pagado and abs(sum(pagado) - importe) > 0.005:
                nota += f"  ⚠ la planilla dice {format_currency_ar(sum(pagado))}"
                hay_diferencias = True
            detalle.append(f"  {etiqueta}: {nota}")

        if sin_celda and not plan:
            messagebox.showwarning(
                "Falta asignar celdas",
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

        if not messagebox.askyesno(
            "Confirmar generación",
            f"Se van a generar {len(plan)} recibo(s) para:\n\n{edificio}\n\n"
            f"Expensas de: {expensas_de}\nGastos de (según la planilla de pagos) e importe:\n{resumen}"
            f"{aviso_montos}{aviso_celdas}\n\n¿Confirmás?",
        ):
            return

        try:
            inmobiliaria = database.get_inmobiliaria()
            datos_edificio = database.get_edificio(edificio) or {}
            carpeta_destino = database.crear_carpeta_edificio(edificio)

            generados = []   # (registro del historial, etiqueta de la unidad)
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
                        "numero_recibo": numero_fmt,
                        "edificio": edificio,
                        "fecha": fecha_hoy_es(),
                        "expensas_de": expensas_de,
                        "gastos_de": gastos_de,
                        "piso": u["piso"],
                        "tipo": tipo,
                        "unidad": u["unidad"] + sufijo,
                        "inquilino": u["inquilino"],
                        "importe": f"{importe_valor:.2f}",
                        "archivo": os.path.relpath(ruta_pdf, config.BASE_DIR),
                    }
                    database.append_historial(registro)
                    generados.append((registro, etiqueta_unidad(u, por_id) + sufijo))
                except Exception as e:
                    errores.append(f"{etiqueta_unidad(u, por_id)}: {e}")

            self._recargar_unidades()      # los círculos de "recibo emitido" pasan a verde

            if generados and self.var_mostrar_lista.get():
                VentanaRecibosGenerados(self, generados, len(plan), errores)
                return

            mensaje = f"Se generaron {len(generados)} de {len(plan)} recibo(s).\n\nCarpeta:\n{carpeta_destino}"
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

    def _refrescar_edificios(self, edificio_preferido=None):
        """Recarga la lista de edificios; si el actual ya no existe (ej. lo renombraron), pasa al indicado."""
        nombres = database.get_nombres_edificios()
        actual = self.var_edificio.get()
        if actual not in nombres:
            actual = edificio_preferido if edificio_preferido in nombres else (nombres[0] if nombres else "")
        self.combo_edificio["values"] = nombres
        self.var_edificio.set(actual)
        self._cargar_unidades()

    def _abrir_administracion(self):
        VentanaAdministracion(self, self.var_edificio.get() or "", on_cambios=self._refrescar_edificios)

    def _abrir_configuracion(self):
        VentanaConfiguracion(self)

    def _abrir_editor_datos(self):
        VentanaEditorDatos(self, on_cambios=self._refrescar_edificios)

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
