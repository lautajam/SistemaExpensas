# Sistema de Expensas

Aplicación de escritorio para Windows que genera los recibos de expensas de
consorcios administrados. Funciona sin conexión: los datos se guardan en
archivos CSV editables con Excel, los pagos se toman de una planilla Excel por
edificio y los recibos se emiten en PDF a partir de una plantilla HTML/CSS
editables.

## Contenido

1. [Características](#1-características)
2. [Requisitos](#2-requisitos)
3. [Instalación y ejecución](#3-instalación-y-ejecución)
4. [Compilación y distribución](#4-compilación-y-distribución)
5. [Estructura del proyecto](#5-estructura-del-proyecto)
6. [Almacenamiento de datos](#6-almacenamiento-de-datos)
7. [Guía de uso](#7-guía-de-uso)
8. [Planilla de pagos](#8-planilla-de-pagos)
9. [Unidades](#9-unidades)
10. [Administración](#10-administración)
11. [Recibos: numeración y nombres de archivo](#11-recibos-numeración-y-nombres-de-archivo)
12. [Plantilla del recibo](#12-plantilla-del-recibo)
13. [Modelo de datos](#13-modelo-de-datos)
14. [Robustez y decisiones de diseño](#14-robustez-y-decisiones-de-diseño)
15. [Datos de ejemplo](#15-datos-de-ejemplo)

---

## 1. Características

- Alta de edificios (consorcios) y de sus unidades: departamentos, locales,
  cocheras y bauleras, con dueño, inquilino, unidad funcional (UF) e importe.
- Cocheras y bauleras asociadas a un departamento, con tres formas de pago:
  recibo aparte, junto con el departamento o incluidas en su total.
- Una planilla de pagos en Excel por edificio, generada y mantenida por la
  aplicación, o bien una planilla propia con orden fijo leída por celdas.
- Campo «Gastos de» del recibo calculado automáticamente según el estado de
  pago (Total, A cta., Deuda o No pagado).
- Períodos «Expensas de» y «Gastos de» completados solos según el mes
  corriente.
- Generación de recibos en PDF por lote, con numeración correlativa por
  edificio e indicador de recibo emitido en la pantalla principal.
- Una única plantilla de recibo (HTML/CSS) para todos los tipos de unidad,
  editable sin recompilar, con el importe también en letras.
- Datos del consorcio y del administrador (CUIT, RPAC), datos de la
  inmobiliaria, logo y firma digital.
- Historial de recibos, editor de tablas, copia de seguridad y archivado de
  edificios dados de baja.

## 2. Requisitos

| Uso | Requisito |
|---|---|
| Ejecutable compilado (`.exe`) | Windows. No requiere Python. |
| Desarrollo | Windows, Python 3.11 o superior |

Dependencias de Python (`requirements.txt`): `xhtml2pdf`, `openpyxl`,
`pillow` y `pyinstaller`. La interfaz utiliza Tkinter, incluido en la
instalación estándar de Python.

## 3. Instalación y ejecución

Modo desarrollo, con Python instalado (https://www.python.org/downloads/,
habilitando «Add Python to PATH»):

```
python -m pip install -r requirements.txt
python main.py
```

En la primera ejecución se crean automáticamente las carpetas y archivos de
datos, con los edificios de ejemplo descritos en la sección 15.

## 4. Compilación y distribución

### Compilar el ejecutable

Con las dependencias instaladas, ejecutar `construir_exe.bat` (doble clic o
desde la consola). El script verifica Python, instala las dependencias,
compila con PyInstaller (`--onefile --windowed`, un único `.exe` sin consola)
y copia la carpeta `plantilla/` junto al ejecutable. El resultado queda en
`dist/`:

```
dist/
├── SistemaExpensas.exe
└── plantilla/
    ├── recibo.html
    ├── estilo.css
    ├── marco.png
    └── fonts/
```

La carpeta `plantilla/` **no se empaqueta dentro del ejecutable** a propósito:
así el diseño del recibo puede modificarse sin recompilar.

### Instalar en otra PC

El equipo de destino no necesita Python. Basta con copiar la carpeta `dist/`
completa (puede renombrarse, por ejemplo a `C:\SistemaExpensas`), verificar
que `plantilla/` esté junto al `.exe` y ejecutar `SistemaExpensas.exe`. En el
primer inicio se crean las carpetas `datos/`, `configuracion/` y `edificios/`.

Para no partir de los datos de ejemplo, se pueden borrar esos edificios desde
**Administrar → Administrar edificios/unidades** (ver sección 10) o reemplazar
`datos/edificios.csv` y `datos/unidades.csv` antes del primer uso.

## 5. Estructura del proyecto

```
SistemaExpensas/
├── main.py                 Punto de entrada
├── config.py               Rutas (relativas al ejecutable)
├── database.py             Persistencia en CSV
├── unidades.py             Tipos de unidad, etiquetas, orden y modos de pago
├── pagos.py                Planillas de pagos (Excel por edificio)
├── utils.py                Importes, fechas, nombres de archivo, CUIT
├── recibo.py               Datos del recibo: formatos, importe en letras, ajuste de textos
├── pdf_generator.py        Generación del PDF desde la plantilla
├── ui.py                   Interfaz gráfica (Tkinter)
├── requirements.txt
├── construir_exe.bat
│
├── plantilla/              Diseño del recibo (editable)
│   ├── recibo.html         Plantilla única del recibo
│   ├── estilo.css          Colores, tipografías y disposición
│   ├── marco.png           Marco azul de la hoja (fondo de la página)
│   └── fonts/              Tipografía Open Sans (licencia OFL)
│
├── datos/                  Se crea al iniciar
│   ├── edificios.csv
│   ├── unidades.csv
│   ├── numeracion.csv
│   ├── historial.csv
│   ├── pagos_edificios/    Una planilla Excel por edificio
│   └── edificios_borrados/ Edificios archivados
├── configuracion/          Inmobiliaria, preferencias, logo y firma
├── edificios/              Una subcarpeta con los PDF de cada edificio
└── backups/                Copias de seguridad (.zip)
```

## 6. Almacenamiento de datos

Toda la información se guarda **junto al ejecutable**, nunca en carpetas
temporales ni ocultas del sistema. Para un ejecutable en
`C:\SistemaExpensas\SistemaExpensas.exe`:

| Ruta | Contenido |
|---|---|
| `datos/edificios.csv` | Edificios y datos del consorcio |
| `datos/unidades.csv` | Unidades de todos los edificios |
| `datos/numeracion.csv` | Último número de recibo por edificio |
| `datos/historial.csv` | Recibos generados |
| `datos/pagos_edificios/<Edificio>_pagos.xlsx` | Planilla de pagos del edificio |
| `configuracion/inmobiliaria.csv` | Datos de la inmobiliaria |
| `configuracion/preferencias.csv` | Preferencias de la interfaz |
| `configuracion/logo.png`, `firma.png` | Imágenes de la inmobiliaria |
| `edificios/<Edificio>/` | PDF de los recibos |

Los CSV se guardan en UTF-8 con BOM, de modo que Excel muestra correctamente
tildes y «ñ». Si un archivo falta o está vacío, se recrea con sus encabezados.

## 7. Guía de uso

### Generar recibos

1. Elegir el edificio en el selector superior. Sus unidades se listan solas.
2. Los períodos se completan automáticamente: **Expensas de** es el mes
   corriente y **Gastos de** el mes anterior, salvo que la planilla de pagos
   indique otra cosa (sección 8). La regla de los meses está en
   `obtener_periodos()` de `utils.py`.
3. Marcar las unidades con la casilla de la primera columna (☐ / ☑), o usar
   **Seleccionar todas** / **Quitar todas**.
4. Cargar los importes con **Actualizar montos desde planilla**. Para un
   importe puntual distinto, se edita la unidad con doble clic sobre su fila.
5. Pulsar **GENERAR RECIBOS PDF**. Tras la confirmación se genera un PDF por
   cada recibo en `edificios/<Edificio>/`.
6. Al terminar se muestra el resultado. Con la casilla **Mostrar lista de PDF
   al terminar** activada, se abre en su lugar una ventana con los recibos
   generados, desde la que pueden abrirse (**Abrir PDF** o doble clic) o
   ubicarse en su carpeta (**Mostrar en carpeta**). La opción se conserva en
   `configuracion/preferencias.csv` y viene desactivada de fábrica.

### Columnas de la pantalla principal

| Columna | Descripción |
|---|---|
| RECIBO | Círculo **verde** si el recibo de la unidad ya se generó para las expensas del período actual; **rojo** si no. Se calcula a partir del historial y se actualiza al generar. Un grupo que paga junto se marca según el recibo del departamento. |
| Casilla | Selección para generar. |
| PISO, TIPO, LETRA/N°, UF | Identificación de la unidad. |
| RELACIÓN | Departamento al que pertenece una cochera o baulera (`de 1° A`), o sus asociadas incluidas en el recibo (`con Cochera 6`). |
| DUEÑO, INQUILINO | Datos de la unidad. |
| IMPORTE | Monto del recibo. |
| PAGO | Estado según la planilla: Total, A cta., Deuda, No pagado o Sin celda. |

## 8. Planilla de pagos

Cada edificio tiene una planilla `datos/pagos_edificios/<Edificio>_pagos.xlsx`.
Existen dos modos de funcionamiento, que se determinan por edificio.

### 8.1 Planilla automática (modo predeterminado)

La aplicación crea la planilla al crear el edificio y la mantiene ordenada
(PB, 1° A, 1° B, 2° A, …), con una fila por unidad y sin perder los montos
cargados. Cada departamento va seguido de sus cocheras y bauleras. Se abre con
el botón **Abrir planilla de pagos**.

Cada mes se completan únicamente las columnas *Total a pagar*, *Monto deuda*
y *Monto pagado*. *Tipo pago* es una fórmula:

```
=SI(E4=0;"No pagado";SI(E4=D4;"Deuda";SI(E4>=C4+D4;"Total";"A cta.")))
```

*Total* requiere que *Monto pagado* sea **mayor o igual** a *Total a pagar* +
*Monto deuda*. Una planilla sin unidades incluye igualmente la fórmula en la
primera fila, para poder copiarla a otro archivo. Las filas las gestiona la
aplicación y no deben agregarse ni borrarse a mano.

Cada fila guarda el identificador interno de su unidad en la columna oculta
`H`. El vínculo es exacto: no depende del texto del piso o la letra y
sobrevive a renombrados y a cambios de orden.

> **Importante:** la aplicación lee lo que está **guardado** en el archivo.
> Antes de generar recibos o actualizar montos debe guardarse el Excel
> (Ctrl+G). Si la planilla figura abierta, la aplicación lo advierte. También
> debe cerrarse antes de agregar o borrar unidades, para que pueda
> actualizarse.

### 8.2 Estado de pago y «Gastos de»

**Actualizar montos desde planilla** toma el *Monto pagado* de cada unidad
como su importe y refresca la columna PAGO. Al generar, el cuadro de
confirmación marca con ⚠ las unidades cuyo importe difiere del de la planilla.

El campo «Gastos de» del recibo surge de «Tipo pago»:

| Tipo pago | «Gastos de» en el recibo |
|---|---|
| Total | Mes anterior (ej. `AGOSTO 2026`) |
| A cta. | `A CTA.` |
| Deuda | `DEUDA` |
| No pagado | `NO PAGADO` |

Una unidad sin montos cargados figura como «No pagado». Los textos se
modifican en `TEXTO_POR_ESTADO` de `pagos.py`.

### 8.3 Planilla propia con orden fijo (celdas)

Cuando la planilla ya existe con un orden que no debe alterarse, se indica en
qué celda está cada unidad:

1. Copiar el Excel a `datos/pagos_edificios/<Edificio>_pagos.xlsx` (se utiliza
   la primera hoja).
2. Completar **Celda en la planilla** (ej. `B12`) en cada unidad, o cargar
   todas juntas en **Administrar → Asignar celdas**. La celda corresponde al
   **nombre de la unidad**; a su derecha, en este orden, deben estar *Total a
   pagar*, *Monto deuda*, *Monto pagado* y *Tipo pago*. Si *Tipo pago* está
   vacío o es una fórmula sin resultado guardado, se calcula con la misma
   regla anterior.
3. Desde que un edificio tiene al menos una celda asignada, la aplicación
   **solo lee** ese archivo: no lo crea, no lo reordena ni lo modifica. Al
   renombrar el consorcio solo cambia el nombre del archivo.
4. Las unidades **sin celda** figuran como «Sin celda» y **no permiten generar
   su recibo**, ya que no se conoce lo pagado ni el estado.
5. Dos unidades del mismo edificio no pueden compartir celda.

Un Excel que no fue creado por la aplicación y todavía no tiene celdas
asignadas no se modifica; la aplicación lo advierte. Si se quitan todas las
celdas, la aplicación vuelve a generar su planilla automática y antes guarda
una copia del archivo como `<Edificio>_pagos_respaldo_<fecha>.xlsx`.

## 9. Unidades

### Datos de cada unidad

Piso, **letra o número** (identificador dentro del piso, ej. `A` o `2`), **UF**
(unidad funcional), dueño, inquilino, importe y, opcionalmente, la celda de la
planilla. El dueño y la UF se cargan por unidad; una cochera no hereda el dueño
de su departamento. El piso es opcional para locales, cocheras y bauleras.

### Tipos

Existen cuatro tipos: **Depto, Local, Cochera y Baulera**. Cada uno genera su
recibo con su propia plantilla (sección 12).

- Una cochera o baulera puede pertenecer a un departamento o ser
  independiente. Un departamento puede tener varias, una o ninguna de cada una.
- Al crear un departamento pueden agregarse en el mismo paso sus cocheras y
  bauleras. Al crear una cochera o baulera, el selector **Pertenece al depto**
  permite asociarla; en ese caso toma el inquilino del departamento (editable)
  y conserva su propio importe.
- Si cambia el inquilino de un departamento, sus cocheras y bauleras que
  tenían ese mismo inquilino se actualizan automáticamente.
- Un departamento con cocheras o bauleras asociadas no puede cambiar de tipo
  hasta que se trasladen a otro departamento.

### Cocheras y bauleras de un departamento

En la ventana de edición del departamento (doble clic) se administra la lista
de sus cocheras y bauleras:

- **Vincular existente:** asocia cocheras o bauleras sueltas del edificio.
- **+ Cochera nueva / + Baulera nueva:** crea y asocia una unidad nueva.
- **Quitar:** desvincula la unidad del departamento sin borrarla.

Los cambios se aplican al guardar.

### Forma de pago de cada cochera o baulera

Se elige por unidad, en la ventana del departamento (**Cómo paga la elegida**)
o en la de la propia cochera o baulera (**Cómo paga**):

| Modo | Recibo | Fila y celda en la planilla |
|---|---|---|
| Recibo aparte | Propio | Propias |
| Paga junto con el depto | El del departamento | Propias |
| Incluida en el total del depto | El del departamento | Ninguna |

En **Incluida en el total** el monto ya está contenido en el total de la
expensa del departamento: no tiene importe propio, no figura como «Sin celda»
y su estado es el del departamento.

Las cocheras y bauleras que van en el recibo del departamento (paga junto o
incluidas):

- Aparecen en la fila de su departamento (`1° A … con Cochera 6 y Baulera 2`),
  con el importe sumado y un único estado. Se editan desde el departamento o
  desde Administrar. Las que pagan aparte siguen apareciendo debajo.
- Generan **un solo recibo**, con la plantilla de departamento y el importe
  total. En el historial figura como `A + Cochera 6 + Baulera 2`.
- **Estado del grupo:** se evalúan las filas del departamento y de las que
  pagan junto. Es *Total* solo si todas son Total, *No pagado* si todas son
  No pagado, *Deuda* si todas son Deuda, y *A cta.* en cualquier otra
  combinación. Ese estado determina el «Gastos de» del recibo.

### Selección y borrado

Al marcar un departamento se marcan también sus cocheras y bauleras visibles,
que luego pueden desmarcarse individualmente. Se genera un recibo por cada
fila marcada.

Para borrar una unidad: doble clic sobre ella y **Borrar unidad** (o desde
Administrar). Al borrar un departamento se borran también sus cocheras y
bauleras, previa confirmación con la lista completa. Las unidades se quitan de
la planilla de pagos; los recibos ya generados y el historial no se modifican.

## 10. Administración

### Administrar edificios y unidades

**Administrar → Administrar edificios/unidades**: alta de edificios y unidades,
edición de sus datos, asignación de celdas, borrado y acceso a la carpeta de
recibos del edificio.

### Datos del consorcio

El botón **Datos del consorcio** guarda, por edificio: nombre, dirección,
localidad y CUIT del consorcio, y nombre, CUIT y RPAC del administrador. Cada
edificio tiene los suyos, por lo que el administrador puede diferir entre
ellos. Los CUIT se normalizan al formato `30-12345678-9`.

Cambiar el nombre actualiza en cascada las unidades, el historial, la
numeración, la carpeta de recibos y la planilla de pagos (que se renombra
conservando los montos). Debe cerrarse antes la planilla en Excel y los PDF del
consorcio: si hay archivos abiertos, la operación se cancela sin modificar
nada. Los PDF ya generados conservan su nombre original.

### Borrar un edificio

El botón **Borrar edificio** da de baja un consorcio. Muestra la cantidad de
unidades, recibos y PDF, y requiere escribir el nombre exacto del edificio para
confirmar.

El borrado **no destruye información**: el edificio deja de aparecer y todo lo
suyo se mueve a `datos/edificios_borrados/<Edificio>_<fecha>/`:

```
edificio.csv  unidades.csv  historial.csv  numeracion.csv  LEEME.txt
recibos/      (PDF)
planilla/     (Excel de pagos y sus respaldos)
```

La recuperación es manual, copiando esos datos de vuelta. Si hay archivos
abiertos, la operación se cancela sin modificar nada. Puede crearse luego un
edificio con el mismo nombre, que comienza limpio (numeración desde 1).

### Configuración de la inmobiliaria

**Administrar → Configuración de la inmobiliaria**: nombre, subtítulo (texto
bajo el nombre en el recibo), dirección, teléfono y correo electrónico, que
aparecen en todos los recibos.

También permite cargar el **logo** y la **firma digital** (PNG o JPG, con vista
previa) y quitarlos. Se guardan como `configuracion/logo.png` y
`configuracion/firma.png`, se incluyen en la copia de seguridad y se reducen
a 1200 px si son muy grandes. El **logo** se imprime arriba a la derecha del
recibo y la **firma** sobre la línea «Firma»; si no hay imagen
cargada, ese lugar queda en blanco.

### Editor de datos (CSV)

**Administrar → Editor de datos (CSV)** permite ver, agregar, editar y eliminar
filas de las tablas de Edificios, Unidades, Inmobiliaria e Historial sin salir
del programa. Los cambios se guardan de inmediato.

`numeracion.csv` no aparece en el editor a propósito: lo administra el
programa y su edición manual podría duplicar o saltear números de recibo. Si
es necesario corregirlo, debe hacerse directamente en `datos/numeracion.csv`,
con el programa cerrado.

### Historial

**Ver → Historial de recibos** lista todos los recibos generados, con filtro
por edificio. Permite **Abrir PDF** (o doble clic), que utiliza el visor de PDF
predeterminado de Windows, y **Mostrar en carpeta**, que abre el Explorador con
el archivo seleccionado. Si el archivo no puede abrirse (por ejemplo, porque
se movió o borró), se muestra su ruta completa.

### Copia de seguridad

**Archivo → Copia de seguridad (backup)** genera un `.zip` con las carpetas
`datos/` y `configuracion/` dentro de `backups/`. Se recomienda realizarla con
regularidad y siempre antes de editar los CSV a mano.

## 11. Recibos: numeración y nombres de archivo

### Numeración

Cada edificio tiene su propio contador en `datos/numeracion.csv`:

```csv
edificio,ultimo_recibo
Edificio Alsina 123,4
Edificio Mitre 456,3
```

El número se incrementa y se guarda **inmediatamente** en cada recibo, sin
esperar el final del lote, por lo que un cierre o corte de energía no
provoca pérdidas ni repeticiones. En consecuencia, si un recibo falla al
generarse, su número queda consumido y no se reutiliza, como en un talonario
en papel.

### Nombres de archivo

Los PDF de departamentos siguen el formato:

```
recibo_expensas_<Edificio>_<Piso>_<Unidad>_<MES>.pdf
recibo_expensas_Edificio_Alsina_123_1_A_SEPTIEMBRE.pdf
```

Para locales, cocheras y bauleras se agrega el tipo y, si pertenecen a un
departamento, cuál es:

```
recibo_expensas_Edificio_Alsina_123_Local_PB_1_SEPTIEMBRE.pdf
recibo_expensas_Edificio_Alsina_123_Cochera_3_Depto_1°_A_SEPTIEMBRE.pdf
```

Se eliminan los caracteres inválidos en Windows (`\ / : * ? " < > |`) y los
espacios se reemplazan por guiones bajos; tildes y «ñ» se conservan.

Un archivo existente **nunca se sobrescribe**: si el nombre ya existe, el
nuevo PDF agrega el número de recibo como sufijo:

```
recibo_expensas_Edificio_Alsina_123_1_A_SEPTIEMBRE.pdf          (existente)
recibo_expensas_Edificio_Alsina_123_1_A_SEPTIEMBRE_00039.pdf    (nuevo)
```

## 12. Plantilla del recibo

Hay **una única plantilla** para todos los tipos de unidad (departamento, local,
cochera y baulera). El recibo es una hoja A4 con marco azul, generada a partir
de archivos de texto plano, sin tocar código Python:

| Archivo | Contenido |
|---|---|
| `plantilla/recibo.html` | Estructura y textos fijos del recibo |
| `plantilla/estilo.css` | Colores, tipografías, tamaños y disposición |
| `plantilla/marco.png` | Marco de la hoja (imagen de fondo de la página, A4) |
| `plantilla/fonts/` | Tipografía Open Sans (regular y negrita) |

### Qué va en cada lugar

Todo el texto del recibo es negro. Lo que cambia en cada recibo sale de los datos del
sistema; el resto es texto fijo.

| Lugar del recibo | Contenido |
|---|---|
| Encabezado izquierdo | «Consorcio de Propietarios sitio en la calle» + **dirección y localidad** del consorcio; «C.U.I.T.:» + **CUIT del consorcio**. Si el edificio **no tiene CUIT**, esa línea se quita y el texto del consorcio se agranda y queda centrado verticalmente |
| Encabezado derecho | **Logo** de la inmobiliaria, su **nombre** y su **subtítulo**, centrados verticalmente |
| EXPENSAS / GASTO DE | Mes de las expensas y mes de los gastos, abreviados (`SEPT. 26`, `AGO. 26`); «Gasto de» muestra `A CTA.`, `DEUDA` o `NO PAGADO` según el estado de pago |
| RECIBO DE EXPENSAS N° / FECHA | **Número** de recibo (mínimo 3 dígitos, `001`) y **fecha de emisión** (`24/09/26`) |
| Tabla «Depto-Coch-Local» | La unidad y, si van en el mismo recibo, sus cocheras y bauleras separadas por `\|`: `1ero A`, `1ero A \| Coch. 67`, `1ero A \| Baul 12`, `1ero A \| Coch. 67 \| Baul 12`, `Coch. 67`, `Baul 12`… Solo aparecen las que existen |
| Tabla «Unidad Funcional» | La **UF** de la unidad (la del departamento; las cocheras y bauleras que van con él no se muestran) |
| Tabla «Propietario» | El **dueño** de la unidad |
| Recibí de | El **inquilino**; si la unidad no tiene inquilino cargado, el propietario |
| Frase sobre el importe | Depende del estado de pago (ver abajo) |
| Importe abonado | **Importe** sin decimales si es entero (`$67.000.-`) o con coma (`$67.000,50.-`); en un grupo que paga junto, el total sumado |
| (Pesos …) | El **importe en letras** (`SESENTA Y SIETE MIL`, con centavos `… CON 50/100`) |
| Firma | La **firma digital** de la inmobiliaria sobre la línea |
| Pie | **Administrador** del consorcio (nombre, CUIT, RPAC) y **teléfono** y **correo** de la inmobiliaria |

Los textos largos (nombres, direcciones, unidades) reducen automáticamente su
tamaño de letra para entrar en su lugar. Los datos se insertan como texto: los
caracteres como `&` o `<` no rompen el PDF.

**Frase sobre el importe** (`FRASE_PAGO_POR_ESTADO` en `recibo.py`):

| Estado de pago | Frase |
|---|---|
| Total (o sin estado) | El pago total de las expensas indicadas para el mes correspondiente: |
| A cta. | El pago a cuenta de las expensas indicadas para el mes correspondiente: |
| Deuda | El pago de la deuda de expensas de meses anteriores: |
| No pagado | Expensas indicadas para el mes correspondiente, pendientes de pago: |

### Marcadores

`recibo.html` contiene marcadores entre llaves dobles que se reemplazan por los
datos de cada recibo (los arma `recibo.py`):

| Marcador | Contenido |
|---|---|
| `{{NUMERO_RECIBO}}`, `{{FECHA_EMISION}}` | Número y fecha de emisión |
| `{{EXPENSAS_DE}}`, `{{GASTOS_DE}}` | Períodos, abreviados |
| `{{EDIFICIO_UBICACION}}` | Dirección y localidad del consorcio |
| `{{BLOQUE_CUIT}}` | Línea completa «C.U.I.T.: …» del consorcio; vacía si el edificio no tiene CUIT |
| `{{EDIFICIO_NOMBRE}}`, `{{EDIFICIO_DIRECCION}}`, `{{EDIFICIO_LOCALIDAD}}`, `{{EDIFICIO_CUIT}}` | Datos del consorcio |
| `{{ADMIN_NOMBRE}}`, `{{ADMIN_CUIT}}`, `{{ADMIN_RPAC}}` | Datos del administrador |
| `{{INMOBILIARIA_NOMBRE}}`, `{{INMOBILIARIA_SUBTITULO}}`, `{{INMOBILIARIA_DIRECCION}}`, `{{INMOBILIARIA_TELEFONO}}`, `{{INMOBILIARIA_EMAIL}}` | Datos de la inmobiliaria |
| `{{LOGO}}`, `{{FIRMA}}` | Imágenes de la inmobiliaria (vacías si no están cargadas) |
| `{{UNIDADES}}`, `{{UF}}`, `{{PROPIETARIO}}` | Contenido de la tabla de la unidad |
| `{{RECIBI_DE}}` | Inquilino (o propietario si no hay inquilino) |
| `{{FRASE_PAGO}}` | Frase según el estado de pago |
| `{{IMPORTE}}`, `{{IMPORTE_LETRAS}}` | Importe (sin el signo `$`) y su texto en letras |
| `{{TAM_CONSORCIO}}`, `{{INTERLINEADO_CONSORCIO}}`, `{{TAM_INMOBILIARIA}}`, `{{TAM_SUBTITULO}}`, `{{TAM_UNIDADES}}`, `{{TAM_UF}}`, `{{TAM_PROPIETARIO}}`, `{{TAM_RECIBI_DE}}`, `{{TAM_IMPORTE}}`, `{{TAM_IMPORTE_LETRAS}}` | Tamaño de letra (pt) ajustado al espacio disponible |
| `{{TIPO}}`, `{{PISO}}`, `{{UNIDAD}}`, `{{INQUILINO}}`, `{{DUENO}}` | Datos sueltos de la unidad, disponibles si una plantilla nueva los necesita |

Pueden modificarse los textos fijos, los colores, las tipografías y los
espaciados. No hace falta recompilar: basta con generar un recibo de prueba.

> **Limitaciones:** el motor de PDF (`xhtml2pdf`) admite un subconjunto de CSS
> 2.1. Funciona con `table`, bordes, colores y tipografías, pero **no con
> `flexbox` ni `grid`**; los rediseños deben basarse en tablas. Además, no
> conviene fijar alturas grandes en celdas de tabla: `xhtml2pdf` achica todo el
> contenido si no entra. El marco azul es la imagen `marco.png`; para
> cambiar su color o grosor hay que reemplazarla por otra imagen A4.

## 13. Modelo de datos

| Archivo | Columnas |
|---|---|
| `edificios.csv` | `id`, `nombre`, `direccion`, `localidad`, `cuit`, `admin_nombre`, `admin_cuit`, `admin_rpac` |
| `unidades.csv` | `id`, `edificio`, `piso`, `tipo`, `unidad`, `uf`, `inquilino`, `dueno`, `importe`, `depto_id`, `paga_junto`, `celda` |
| `numeracion.csv` | `edificio`, `ultimo_recibo` |
| `historial.csv` | `numero_recibo`, `edificio`, `fecha`, `expensas_de`, `gastos_de`, `piso`, `tipo`, `unidad`, `inquilino`, `importe`, `archivo` |
| `inmobiliaria.csv` | `nombre`, `subtitulo`, `direccion`, `telefono`, `email` |

Detalles de `unidades.csv`:

- `id`: identificador corto único de la unidad.
- `tipo`: `DEPTO`, `LOCAL`, `COCHERA` o `BAULERA`.
- `depto_id`: `id` del departamento al que pertenece una cochera o baulera.
- `paga_junto`: vacío (recibo aparte), `1` (paga junto) o `T` (incluida en el
  total del departamento). Solo aplica a cocheras y bauleras con departamento.
- `celda`: celda de la planilla propia (ej. `B12`); vacía en modo automático.

Los importes admiten los formatos `45000`, `45000,50`, `45.000,50`, `$45.000` y
`$ 45.000,50`.

## 14. Robustez y decisiones de diseño

**Robustez**

- Los CSV inexistentes o vacíos se recrean con sus encabezados.
- Los nombres con espacios y tildes están soportados.
- Las unidades se guardan con columnas separadas (`piso`, `tipo`, `unidad`), sin
  suponer el formato «piso + letra» (`PB 1`, cochera `21`, baulera `14`, …).
- Los errores se informan siempre en un cuadro de diálogo con un mensaje
  comprensible, nunca como traza de Python.
- La generación de recibos requiere confirmación explícita.
- Las operaciones que modifican varios archivos a la vez (renombrar o borrar un
  edificio) se revierten por completo si algo falla.

**Decisiones de diseño**

- **`xhtml2pdf` en lugar de ReportLab directo:** mantiene el diseño en
  HTML/CSS editable dentro de `plantilla/`, sin depender de binarios externos
  (como `wkhtmltopdf`) que complicarían el ejecutable.
- **Identificador interno por unidad:** permite editar una unidad (por
  ejemplo, cambiarle el piso) sin perder referencias ni afectar filas
  parecidas; también vincula cada fila de la planilla con su unidad.
- **Borrado no destructivo de edificios:** se archivan en lugar de eliminarse.
  El borrado de unidades no altera el historial ni los PDF ya emitidos, que
  conservan los datos de su emisión.
- **Selección con ☑ / ☐:** una columna de la tabla que alterna con un clic,
  sin dependencias adicionales para casillas reales.
- **Círculos de estado como imágenes:** los emojis se muestran en blanco y
  negro en Tk sobre Windows, por lo que el indicador de recibo emitido usa
  imágenes de color.

## 15. Datos de ejemplo

En el primer inicio se crean dos edificios de prueba:

- **Edificio Alsina 123:** deptos PB 1, 1° A, 1° B y 2° A; un local (PB 1) y la
  cochera 3, asociada al 1° A.
- **Edificio Mitre 456:** deptos PB 1, 1° A y 1° B; y la baulera 14, asociada al
  1° A.

Pueden editarse o borrarse desde **Administrar edificios/unidades**.
