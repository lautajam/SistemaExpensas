@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo ============================================================
echo   SISTEMA DE EXPENSAS - Compilacion del ejecutable (.exe)
echo ============================================================
echo.

REM ------------------------------------------------------------
REM 1) Comprobar que Python esta instalado
REM ------------------------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] No se encontro Python instalado o no esta en el PATH.
    echo.
    echo Instala Python 3.11 o superior desde https://www.python.org/downloads/
    echo IMPORTANTE: al instalar, tildar la opcion "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

echo [OK] Python encontrado:
python --version
echo.

REM ------------------------------------------------------------
REM 2) Instalar dependencias del proyecto
REM ------------------------------------------------------------
echo Instalando dependencias (requirements.txt)...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Fallo la instalacion de dependencias.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.
echo.

REM ------------------------------------------------------------
REM 3) Verificar/instalar PyInstaller (ya viene en requirements.txt,
REM    pero se vuelve a comprobar por las dudas)
REM ------------------------------------------------------------
python -m pyinstaller --version >nul 2>nul
if errorlevel 1 (
    echo Instalando PyInstaller...
    python -m pip install pyinstaller
)
echo [OK] PyInstaller listo.
echo.

REM ------------------------------------------------------------
REM 4) Compilar el ejecutable
REM ------------------------------------------------------------
echo Compilando SistemaExpensas.exe ...
echo (esto puede tardar uno o dos minutos)
echo.

python -m PyInstaller --noconfirm --onefile --windowed ^
    --name "SistemaExpensas" ^
    main.py

if errorlevel 1 (
    echo.
    echo [ERROR] La compilacion fallo. Revisa el detalle de arriba.
    pause
    exit /b 1
)

REM ------------------------------------------------------------
REM 5) Copiar la carpeta "plantilla" (HTML/CSS del recibo) junto
REM    al ejecutable generado. Esta carpeta NO se empaqueta dentro
REM    del .exe a proposito: asi el usuario puede editar el diseno
REM    del recibo sin tener que recompilar nada.
REM ------------------------------------------------------------
echo.
echo Copiando la carpeta "plantilla" junto al ejecutable...
xcopy /E /I /Y "plantilla" "dist\plantilla" >nul

echo.
echo ============================================================
echo   COMPILACION FINALIZADA CORRECTAMENTE
echo ============================================================
echo.
echo El ejecutable y su plantilla quedaron en:
echo   %cd%\dist\SistemaExpensas.exe
echo   %cd%\dist\plantilla\
echo.
echo PROXIMO PASO:
echo   Copia TODA la carpeta "dist" (renombrala si queres, por
echo   ejemplo a C:\SistemaExpensas) a la ubicacion definitiva.
echo   Al ejecutar el .exe por primera vez, se crearan
echo   automaticamente las carpetas datos, configuracion y
echo   edificios con datos de ejemplo.
echo.
pause
