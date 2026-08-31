@echo off
setlocal EnableDelayedExpansion
pushd "%~dp0"

REM MP3 Cutter - build amb PyInstaller (onedir) - entorn jm_pyside_313
REM Regles: path directe (espais username), PySide6 via pip, PYTHONNOUSERSITE=1

REM Troba conda base
where conda >nul 2>&1
if %errorlevel% neq 0 (
    if exist "C:\Users\JM\miniconda3\Scripts\conda.exe" (
        set "CONDA_EXE=C:\Users\JM\miniconda3\Scripts\conda.exe"
    ) else (
        echo [ERROR] No s'ha trobat conda al PATH i no existeix a C:\Users\JM\miniconda3
        exit /b 1
    )
) else (
    for /f "delims=" %%i in ('where conda') do set "CONDA_EXE=%%i"
)

REM Python de l'entorn jm_pyside_313 (path directe, evita conda run)
set "PY_EXE=C:\Users\JM\miniconda3\envs\jm_pyside_313\python.exe"
if not exist "%PY_EXE%" (
    echo [ERROR] No s'ha trobat %PY_EXE%
    exit /b 1
)

echo [INFO] Python: %PY_EXE%
"%PY_EXE%" --version
"%PY_EXE%" -c "import PySide6; print('PySide6', PySide6.__version__)"
if %errorlevel% neq 0 exit /b 1

REM Neteja builds anteriors
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

REM Verifica FFmpeg bundled (avisa pero no falla)
if not exist "resources\ffmpeg\ffmpeg.exe" (
    echo [WARN] No s'ha trobat resources\ffmpeg\ffmpeg.exe - l'exe funcionarà pero necessitarà ffmpeg al PATH
) else (
    echo [INFO] FFmpeg bundled trobat: resources\ffmpeg\ffmpeg.exe
)

set "PYTHONNOUSERSITE=1"

echo [INFO] Generant executable amb PyInstaller (onedir)...

REM Icon opcional
set "ICON_ARG="
if exist "resources\icon.ico" set "ICON_ARG=--icon resources\icon.ico"

REM Add-data nomes si existeix ffmpeg.exe (evita bundled buit)
REM Nomes 1 copia a ffmpeg/ (estaviem duplicant a resources/ffmpeg -> 205 MB extra)
set "FFMPEG_ARGS="
if exist "resources\ffmpeg\ffmpeg.exe" (
    set "FFMPEG_ARGS=--add-data resources\ffmpeg;ffmpeg"
) else (
    if exist "resources\ffmpeg" (
        echo [WARN] resources\ffmpeg existeix pero sense ffmpeg.exe - no s'incloura al bundle
    )
)

"%PY_EXE%" -m PyInstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "MP3Cutter" ^
    !ICON_ARG! ^
    !FFMPEG_ARGS! ^
    --exclude-module PySide6.Qt3DAnimation ^
    --exclude-module PySide6.Qt3DCore ^
    --exclude-module PySide6.Qt3DExtras ^
    --exclude-module PySide6.Qt3DInput ^
    --exclude-module PySide6.Qt3DLogic ^
    --exclude-module PySide6.Qt3DRender ^
    --exclude-module PySide6.QtCharts ^
    --exclude-module PySide6.QtDataVisualization ^
    --exclude-module PySide6.QtWebEngine ^
    --exclude-module PySide6.QtWebEngineCore ^
    --exclude-module PySide6.QtWebEngineWidgets ^
    --exclude-module PySide6.QtQml ^
    --exclude-module PySide6.QtQuick ^
    --exclude-module PySide6.QtQuickWidgets ^
    --exclude-module PySide6.QtQuickControls2 ^
    --exclude-module PySide6.QtPdf ^
    --exclude-module PySide6.QtPdfWidgets ^
    --exclude-module PySide6.QtNetworkAuth ^
    --exclude-module PySide6.QtStateMachine ^
    --exclude-module PySide6.QtSensors ^
    --exclude-module PySide6.QtSerialPort ^
    --exclude-module PySide6.QtTest ^
    --exclude-module PySide6.QtUiTools ^
    --exclude-module PySide6.QtHelp ^
    --exclude-module PySide6.QtSql ^
    --exclude-module PySide6.QtXml ^
    --exclude-module PySide6.QtSvg ^
    --exclude-module PySide6.QtSvgWidgets ^
    main.py

if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller ha fallat
    exit /b 1
)

REM Fix libexpat.dll (PySide6 + PyInstaller) si cal
if exist "dist\MP3Cutter\_internal\PySide6\libexpat.dll" (
    echo [INFO] libexpat.dll ja present
) else (
    REM intenta copiar de l'entorn si PyInstaller no l'ha inclòs
    if exist "C:\Users\JM\miniconda3\envs\jm_pyside_313\Library\bin\libexpat.dll" (
        echo [INFO] Copiant libexpat.dll de l'entorn...
        copy /y "C:\Users\JM\miniconda3\envs\jm_pyside_313\Library\bin\libexpat.dll" "dist\MP3Cutter\_internal\PySide6\" >nul 2>&1
        copy /y "C:\Users\JM\miniconda3\envs\jm_pyside_313\Library\bin\libexpat.dll" "dist\MP3Cutter\" >nul 2>&1
    )
)

REM Assegura ffmpeg al dist si existeix a resources (per si --add-data no l'ha posat on toca)
if exist "resources\ffmpeg\ffmpeg.exe" (
    if not exist "dist\MP3Cutter\_internal\ffmpeg\ffmpeg.exe" (
        echo [INFO] Copiant ffmpeg.exe al dist...
        mkdir "dist\MP3Cutter\_internal\ffmpeg" >nul 2>&1
        copy /y "resources\ffmpeg\ffmpeg.exe" "dist\MP3Cutter\_internal\ffmpeg\" >nul 2>&1
        copy /y "resources\ffmpeg\ffmpeg.exe" "dist\MP3Cutter\ffmpeg\" >nul 2>&1
    )
    if exist "resources\ffmpeg\ffprobe.exe" (
        copy /y "resources\ffmpeg\ffprobe.exe" "dist\MP3Cutter\_internal\ffmpeg\" >nul 2>&1
        copy /y "resources\ffmpeg\ffprobe.exe" "dist\MP3Cutter\ffmpeg\" >nul 2>&1
    )
)

echo.
echo [OK] Build completat: dist\MP3Cutter\MP3Cutter.exe
dir "dist\MP3Cutter" | findstr /i "MP3Cutter"
echo.
echo Per provar: dist\MP3Cutter\MP3Cutter.exe
echo Per distribuir: comprimeix la carpeta dist\MP3Cutter sencera (portable)
popd
endlocal
