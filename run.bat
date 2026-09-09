
@echo off
setlocal enabledelayedexpansion
 
echo ============================================
echo   Evaluador de Riesgo Crediticio
echo ============================================
echo.
 
REM Ubicarse en la carpeta de este script, sin importar desde donde se ejecute
cd /d "%~dp0"
 
if not exist ".venv\Scripts\activate.bat" (
    echo No se encontro el entorno virtual. Creando uno nuevo...
    python -m venv .venv 2>nul
    if not exist ".venv\Scripts\activate.bat" (
        py -m venv .venv 2>nul
    )
    if not exist ".venv\Scripts\activate.bat" (
        echo.
        echo ERROR: no se pudo crear el entorno virtual.
        echo Verifica que Python este instalado y agregado al PATH.
        echo.
        pause
        exit /b 1
    )
    set NEEDS_INSTALL=1
) else (
    set NEEDS_INSTALL=0
)
 
call .venv\Scripts\activate.bat
 
if "!NEEDS_INSTALL!"=="1" (
    echo Instalando dependencias, esto puede tardar unos minutos...
    python -m pip install --upgrade pip >nul
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR al instalar dependencias. Revisa requirements.txt
        echo.
        pause
        exit /b 1
    )
)
 
echo.
echo Iniciando la aplicacion...
echo Para cerrarla, volve a esta ventana y presiona Ctrl+C
echo.
streamlit run app.py
 
pause
