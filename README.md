# Sistema de Expensas — Instrucciones

Aplicación de escritorio offline (Windows) para generar recibos de expensas
de edificios administrados. Guarda todo en archivos CSV editables con Excel
y genera los recibos en PDF a partir de una plantilla HTML/CSS editable.

---

## 1. Estructura del proyecto

```
SistemaExpensas/
├── main.py                 → punto de entrada
├── config.py                → rutas (relativas al .exe)
├── database.py               → toda la persistencia (CSV)
├── utils.py                  → sanitización, importes, fechas
├── unidades.py               → tipos de unidad (depto/local/cochera/baulera), etiquetas y orden
├── pagos.py                  → planillas de pagos (un Excel por edificio)
├── pdf_generator.py           → arma el PDF a partir de la plantilla del tipo de unidad
├── ui.py                       → toda la interfaz gráfica
├── requirements.txt
├── construir_exe.bat
│
├── datos/
│   ├── edificios.csv
│   ├── unidades.csv
│   ├── numeracion.csv
│   └── historial.csv
│
├── configuracion/
│   └── inmobiliaria.csv
│
├── plantilla/                ← EDITABLE, define el diseño del recibo
│   ├── recibo_depto.html
│   ├── recibo_local.html
│   ├── recibo_cochera.html
│   ├── recibo_baulera.html
│   └── estilo.css            (compartido por las cuatro)
│
└── edificios/                ← se crea una subcarpeta por edificio
    ├── Edificio_Alsina_123/
    └── Edificio_Mitre_456/
```

Los archivos `datos/*.csv` y `configuracion/inmobiliaria.csv` **se crean
solos, con datos de ejemplo, la primera vez que ejecutás el programa** si
no existen. No hace falta crearlos a mano.

---

## 2. Instalar y probar en modo desarrollo (con Python instalado)

1. Instalá **Python 3.11 o superior** desde https://www.python.org/downloads/
   (al instalar, tildá "Add Python to PATH").
2. Abrí una consola (CMD o PowerShell) dentro de la carpeta `SistemaExpensas`.
3. Instalá las dependencias:
   ```
   python -m pip install -r requirements.txt
   ```
4. Ejecutá la aplicación:
   ```
   python main.py
   ```

La primera vez vas a ver 2 edificios de ejemplo (Alsina 123 y Mitre 456)
con unidades de prueba ya cargadas, listas para generar recibos.

---

## 3. Compilar el .exe

1. Con Python y las dependencias ya instaladas (paso anterior), hacé
   **doble clic en `construir_exe.bat`** (o ejecutalo desde la consola).
2. El script:
   - Verifica que Python esté instalado.
   - Instala/actualiza las dependencias necesarias.
   - Compila con PyInstaller en modo `--onefile --windowed`
     (un solo .exe, sin consola negra de fondo).
   - Copia automáticamente la carpeta `plantilla/` junto al .exe generado.
3. Al terminar, vas a encontrar todo listo dentro de la carpeta `dist`:
   ```
   dist/
   ├── SistemaExpensas.exe
   └── plantilla/
       ├── recibo_depto.html
       ├── recibo_local.html
       ├── recibo_cochera.html
       ├── recibo_baulera.html
       └── estilo.css
   ```

**Por qué `plantilla/` no se empaqueta dentro del .exe:** se hizo así
a propósito, para que puedas editar el diseño del recibo (HTML/CSS) sin
tener que volver a compilar nada. Si `plantilla/` se empaquetara dentro
del .exe, cualquier cambio de diseño requeriría recompilar.

---

## 4. Trasladar el programa a otra PC con Windows

Esa PC **no necesita tener Python instalado**: el .exe ya incluye todo
lo necesario para funcionar.

1. Copiá la carpeta `dist` completa (podés renombrarla, por ejemplo a
   `C:\SistemaExpensas`).
2. Asegurate de que, junto al .exe, esté la carpeta `plantilla/`.
3. Ejecutá `SistemaExpensas.exe`. La primera vez se crearán
   automáticamente las carpetas `datos/`, `configuracion/` y `edificios/`
   con los edificios de ejemplo.
4. Si no querés los datos de ejemplo en la PC definitiva, simplemente
   borrá esos edificios de prueba desde "Administrar edificios/unidades"
   y cargá los reales (ver sección 6), o directamente reemplazá el
   contenido de `datos/edificios.csv` y `datos/unidades.csv` antes del
   primer uso.

---

## 5. Dónde quedan los datos

Todo se guarda **al lado del .exe**, nunca en carpetas temporales ni
ocultas del sistema. Si el ejecutable está en:

```
C:\SistemaExpensas\SistemaExpensas.exe
```

los datos van a estar en:

```
C:\SistemaExpensas\datos\edificios.csv
C:\SistemaExpensas\datos\unidades.csv
C:\SistemaExpensas\datos\numeracion.csv
C:\SistemaExpensas\datos\historial.csv
C:\SistemaExpensas\configuracion\inmobiliaria.csv
C:\SistemaExpensas\edificios\<Edificio>\recibo_...pdf
```

Podés abrir cualquiera de esos CSV con Excel para revisar o corregir
datos manualmente si alguna vez lo necesitás (se guardan en UTF-8 con
BOM para que Excel muestre bien tildes y "ñ").

---

## 6. Uso diario

1. **Elegí el edificio** en el combo de arriba. Las unidades aparecen solas.
2. Los períodos del recibo se completan solos al generar: **"Expensas
   de"** = mes corriente y **"Gastos de"** = mes anterior, salvo que
   la planilla de pagos del edificio indique otra cosa (ver más abajo).
   La regla de los meses vive en `obtener_periodos()` de `utils.py`.
3. Tildá las unidades que van a recibir recibo haciendo clic en la
   primera columna (☐ / ☑). También podés usar
   **"Seleccionar todas"** / **"Quitar todas"**.
4. Los importes salen de la planilla de pagos: apretá **"Actualizar montos
   desde planilla"** (ver más abajo). Para un importe puntual distinto en
   una sola unidad: **doble clic** sobre esa fila (fuera de la columna de
   tilde) y editalo en el diálogo que se abre. Esto no afecta a las demás
   unidades.
5. Apretá **"GENERAR RECIBOS PDF"**. Se pide confirmación y luego se
   genera un PDF por cada unidad seleccionada, dentro de
   `edificios/<Edificio>/`.
6. Al terminar aparece un mensaje con el resultado. Si tildás **"Mostrar
   lista de PDF al terminar"** (casilla junto al botón de generar), en su
   lugar se abre una pantalla con los PDF recién generados, para abrirlos
   con **"Abrir PDF"** (o doble clic) o verlos en su carpeta con
   **"Mostrar en carpeta"**. La opción queda guardada para la próxima vez
   (`configuracion/preferencias.csv`) y viene desactivada de fábrica.

### Planilla de pagos de cada edificio (`datos/pagos_edificios/`)
Cada edificio tiene su propio Excel, `<Nombre_Edificio>_pagos.xlsx`, que
**la app crea y mantiene sola**: se crea al crear el edificio y cada
unidad nueva (o editada) se agrega/actualiza en orden (PB, 1° A, 1° B,
2° A...), sin perder los montos ya cargados. Para abrirla, usá el botón
**"Abrir planilla de pagos"** de la pantalla principal.

Cada mes, quien administra solo completa las columnas *Total a pagar,
Monto deuda* y *Monto pagado*; *Tipo pago* es una fórmula que se calcula
sola. No hace falta tocar nada más (no agregar ni borrar filas a mano: las
filas las gestiona la app). Para que dé **"Total"**, *Monto pagado* debe
ser igual a *Total a pagar* + *Monto deuda*.

**IMPORTANTE: guardá el Excel (Ctrl+G) antes de volver a la app.** La app
lee lo que está guardado en el archivo, no lo que está escrito en pantalla
sin guardar. Si la planilla sigue abierta, la app te avisa antes de generar
recibos o de actualizar montos. Cerrala también antes de agregar o borrar
unidades, para que la app pueda actualizarla.

**Botón "Actualizar montos desde planilla"** (pantalla principal): toma el
*Monto pagado* de cada unidad como su **importe** (el del recibo) y
refresca la columna **PAGO**. Al generar recibos, el cuadro de confirmación
marca con ⚠ las unidades cuyo importe difiere del de la planilla.

Al generar los recibos, el campo **"Gastos de"** de cada unidad sale de
"Tipo pago":

| Tipo pago | "Gastos de" en el recibo |
|---|---|
| Total | el mes anterior (ej. AGOSTO 2026) |
| Parcial | PARCIAL |
| Deuda | DEUDA |
| No pagado | NO PAGADO |

Una unidad nueva, con los montos todavía sin cargar, figura como "No
pagado". El cuadro de confirmación muestra qué va a decir cada recibo
antes de generarlo. Los textos se cambian en `TEXTO_POR_ESTADO` de
`pagos.py`.

**Cómo se sabe qué fila es de qué unidad:** cada archivo pertenece a un
solo edificio (por su nombre), y cada fila guarda el id interno de su
unidad en una columna oculta (H). Así el vínculo es exacto: no depende de
cómo esté escrito el piso o la letra, y sobrevive a cambios de nombre y a
reordenar filas.

### Datos de cada unidad
Piso, **letra o número** (el identificador del depto en ese piso, ej. `A`
o `2`), **UF** (unidad funcional), **dueño**, inquilino e importe. El dueño
y la UF se cargan a mano en cada unidad (una cochera no hereda el dueño de
su depto). En la pantalla principal se ven todas las columnas, más **PAGO**
(Total / Parcial / Deuda / No pagado, según la planilla de pagos).

**Borrar una unidad:** doble clic sobre la unidad y botón **"Borrar
unidad"** (o desde Administrar → Administrar edificios/unidades). Si es un
depto, se borran también sus cocheras y bauleras: antes te muestra la
lista y pide confirmación. Se quitan de la planilla de pagos del edificio;
los recibos ya generados y el historial no se borran.

### Tipos de unidad
Hay 4 tipos: **Depto, Local, Cochera y Baulera**. Cada uno genera su
recibo con su propia plantilla (ver sección 9).

- Una **cochera o baulera puede pertenecer a un depto** (o ser
  independiente). Un depto puede tener varias, una o ninguna de cada una.
- Al **crear un depto** (botón **"+ Nueva unidad"**, tipo Depto) podés
  sumarle en el mismo paso sus cocheras y bauleras con **"+ Cochera"** /
  **"+ Baulera"**. También podés hacerlo después, editando el depto.
- Al crear una **cochera o baulera** aparece el selector **"Pertenece al
  depto"** con los deptos del edificio. Si elegís uno, toma su inquilino
  (se puede cambiar) y tiene su **propio importe**.
- Si cambiás el inquilino de un depto, sus cocheras y bauleras que tenían
  ese mismo inquilino se actualizan solas.
- En la pantalla principal cada cochera/baulera aparece justo debajo de su
  depto (con "↳") y la columna **DEPTO** dice a cuál pertenece. Al tildar
  un depto se tildan solas sus cocheras y bauleras; después podés destildar
  cualquiera por separado. Se genera **un recibo por cada unidad tildada**.
- Un depto que tiene cocheras o bauleras no puede cambiarse a otro tipo
  hasta que se pasen a otro depto.
- En la planilla de pagos cada unidad tiene su fila (ej. `1° A`,
  `Cochera 3 (1° A)`), con las cocheras y bauleras debajo de su depto.
- En `unidades.csv` el vínculo se guarda en la columna `depto_id` (el `id`
  del depto).

### Administrar edificios y unidades
Menú **Administrar → Administrar edificios/unidades**: permite crear
edificios nuevos, agregar unidades, editar piso/tipo/unidad/inquilino/
importe, y abrir la carpeta de recibos del edificio.

### Configuración de la inmobiliaria
Menú **Administrar → Configuración de la inmobiliaria**: nombre,
dirección, teléfono, email y CUIT que aparecen en todos los recibos.

### Editor de datos (CSV)
Menú **Administrar → Editor de datos (CSV)**: pantalla para ver y
modificar directamente, fila por fila, las tablas de **Edificios**,
**Unidades**, **Inmobiliaria** e **Historial**. Permite agregar,
editar y eliminar filas sin salir del programa ni abrir Excel.
Los cambios se guardan al instante en el CSV correspondiente.

**A propósito, `numeracion.csv` NO aparece acá**: ese archivo lo
administra el programa solo (numeración correlativa de recibos) y
editarlo a mano podría duplicar o saltear números de recibo. Si
necesitás corregirlo, hacelo directamente en
`datos/numeracion.csv` con Excel, con el programa cerrado.

### Historial
Menú **Ver → Historial de recibos**: lista completa de todos los
recibos generados, con filtro por edificio. Desde ahí podés:
- **Abrir PDF** (o doble clic sobre una fila): abre el recibo con el
  programa predeterminado de Windows para archivos PDF — en la mayoría
  de las instalaciones modernas de Windows esto es el navegador (Edge,
  Chrome, etc.), según lo que el usuario tenga configurado como visor
  de PDF por defecto.
- **Mostrar en carpeta**: abre el Explorador de Windows con el archivo
  ya seleccionado, para poder copiarlo, moverlo o adjuntarlo a mano.
- Si el archivo no se puede abrir automáticamente (por ejemplo, si se
  movió o se borró), el programa te muestra la ruta completa para que
  lo ubiques manualmente.

### Copia de seguridad
Menú **Archivo → Copia de seguridad (backup)**: genera un `.zip` con
las carpetas `datos/` y `configuracion/` dentro de una carpeta
`backups/` al lado del .exe. Hacelo regularmente, sobre todo antes de
editar los CSV a mano.

---

## 7. Numeración de recibos

Cada edificio tiene su propio contador, guardado en
`datos/numeracion.csv`:

```csv
edificio,ultimo_recibo
Edificio Alsina 123,4
Edificio Mitre 456,3
```

Cada vez que se genera un recibo, el número se incrementa y se guarda
**inmediatamente** en el CSV (no espera a que termine todo el lote), así
que si cerrás el programa a mitad de una tanda de recibos, o si se corta
la luz, la numeración no se pierde ni se repite al volver a abrir el
programa. Como contracara de esta robustez: si un recibo puntual falla
al generarse (por ejemplo, un error de permisos de la carpeta), su
número ya fue consumido y no se reutiliza — igual que en un talonario de
recibos en papel, donde un número anulado no se vuelve a usar.

---

## 8. Conflictos de nombre de archivo

Si el nombre "natural" del PDF ya existe (por ejemplo, porque ya
generaste el recibo de esa unidad para ese mes), el archivo existente
**nunca se sobrescribe**. El nuevo PDF se guarda agregando el número de
recibo como sufijo:

```
recibo_expensas_Edificio_Alsina_123_1_A_SEPTIEMBRE.pdf              (ya existía)
recibo_expensas_Edificio_Alsina_123_1_A_SEPTIEMBRE_00039.pdf        (nuevo)
```

Los deptos usan ese formato. Para local, cochera y baulera se agrega el
tipo y, si pertenecen a un depto, cuál es:

```
recibo_expensas_Edificio_Alsina_123_Local_PB_1_SEPTIEMBRE.pdf
recibo_expensas_Edificio_Alsina_123_Cochera_3_Depto_1°_A_SEPTIEMBRE.pdf
```

Los nombres se sanitizan automáticamente quitando caracteres inválidos
en Windows (`\ / : * ? " < > |`) y reemplazando espacios por guiones
bajos. Las tildes y la "ñ" se conservan porque son válidas en NTFS.

---

## 9. Cómo modificar el diseño del PDF más adelante

El recibo se genera a partir de archivos de texto plano, sin tocar
código Python. Hay una plantilla por tipo de unidad (hoy son iguales) y un
estilo compartido:

```
plantilla/recibo_depto.html     → recibos de deptos
plantilla/recibo_local.html     → recibos de locales
plantilla/recibo_cochera.html   → recibos de cocheras
plantilla/recibo_baulera.html   → recibos de bauleras
plantilla/estilo.css            → colores, tipografías, tamaños, layout
```

Dentro de cada `recibo_*.html` vas a ver marcadores como `{{IMPORTE}}` o
`{{INQUILINO}}`: el programa los reemplaza automáticamente por el dato
real de cada recibo al generarlo. Además de los datos de siempre, están
disponibles `{{TIPO}}` (DEPTO, LOCAL, COCHERA o BAULERA), `{{DEPTO}}` (el
depto al que pertenece una cochera/baulera, ej. `1° A`; vacío si no
tiene), `{{UF}}` (unidad funcional) y `{{DUENO}}`. Podés:

- Cambiar textos fijos (por ejemplo "ADMINISTRACIÓN DE CONSORCIOS").
- Reordenar secciones, agregar un logo (`<img src="logo.png">`,
  guardando `logo.png` dentro de la carpeta `plantilla/`).
- Cambiar colores, fuentes y espaciados en `estilo.css`.

**Importante:** el motor que convierte el HTML en PDF (`xhtml2pdf`)
soporta un subconjunto de CSS 2.1: anda perfecto con `float`, `table`,
bordes, colores y tipografías, pero **no soporta `flexbox` ni `grid`**.
Si vas a rediseñar el layout, usá `float`/`table` como en el ejemplo
que ya viene armado. Después de editar estos archivos, simplemente
volvé a generar un recibo de prueba — no hace falta recompilar el .exe.

---

## 10. Robustez y casos especiales ya contemplados

- Importes admitidos: `45000`, `45000,50`, `45.000,50`, `$45.000`,
  `$ 45.000,50` (formato argentino, con o sin símbolo $).
- CSV vacíos o inexistentes: se recrean automáticamente con sus
  encabezados correctos.
- Nombres de edificios/inquilinos con espacios y tildes: soportado.
- Unidades de cualquier formato (`PB 1`, cochera `21`, baulera `14`...):
  se guardan con columnas separadas `piso`, `tipo`, `unidad`, sin asumir
  el formato "piso + letra". El piso es opcional para local, cochera y
  baulera.
- Ningún error de Python se muestra como traceback: siempre aparece un
  cuadro de diálogo con un mensaje entendible.
- Antes de generar recibos se pide confirmación explícita.

---

## 11. Decisiones de diseño que tomé por vos

- **xhtml2pdf en vez de ReportLab directo**: permite mantener el diseño
  del recibo en HTML/CSS editable en una carpeta `plantilla/` separada,
  tal como pediste, sin depender de binarios externos (como
  `wkhtmltopdf`) que complicarían el .exe final.
- **Identificador interno (`id`) por unidad** en `unidades.csv`: además
  de piso/tipo/unidad, cada fila tiene un id corto único. Esto permite
  editar con seguridad una unidad puntual (por ejemplo, si cambiás el
  piso de "1°" a "2°") sin perder la referencia ni afectar a otras filas
  con datos parecidos.
- **Eliminación de unidades**: se puede borrar una unidad (y las cocheras
  y bauleras de un depto). El historial y los PDF ya generados no se
  tocan, así que siguen mostrando los datos tal como eran al emitirse.
- **Checkbox de selección**: en vez de una librería adicional para
  checkboxes reales en la tabla, se usa una columna con ☑ / ☐ que se
  alterna al hacer clic — mismo resultado visual, cero dependencias
  extra.

---

## 12. Datos de ejemplo incluidos

- **Edificio Alsina 123**: PB 1, 1° A, 1° B, 2° A (deptos), un local
  (PB 1) y la cochera 3, que pertenece al 1° A.
- **Edificio Mitre 456**: PB 1, 1° A, 1° B (deptos) y la baulera 14, que
  pertenece al 1° A.

Podés borrarlos o editarlos libremente desde "Administrar
edificios/unidades" una vez que verifiques que todo funciona.
