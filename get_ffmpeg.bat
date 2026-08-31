@echo off
setlocal
REM Descarrega FFmpeg portatil per MP3 Cutter (Bundled)
REM Requereix Python de l'entorn jm_pyside_313 amb internet

set "PY_EXE=C:\Users\JM\miniconda3\envs\jm_pyside_313\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=python"

echo [INFO] Descarregant FFmpeg (BtbN - gpl - win64, ~80 MB)...
echo [INFO] Python: %PY_EXE%
"%PY_EXE%" "%~dp0get_ffmpeg.py"
if %errorlevel% neq 0 (
    echo [ERROR] La descarrega ha fallat. Prova manual:
    echo   1) Ves a https://github.com/BtbN/FFmpeg-Builds/releases
    echo   2) Descarrega ffmpeg-master-latest-win64-gpl.zip
    echo   3) Extreu bin/ffmpeg.exe i bin/ffprobe.exe a resources\ffmpeg\
    exit /b 1
)
echo [OK] FFmpeg instal·lat a resources\ffmpeg\
dir resources\ffmpeg
echo.
echo Ara pots tornar a fer: build.bat
endlocal
