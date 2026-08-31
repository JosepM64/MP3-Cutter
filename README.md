# MP3 Cutter — Obrir → Reproduir → Dividir → Exportar

Aplicació d'escriptori **Windows** minimalista per tallar MP3 en múltiples fragments de forma ràpida. No és un editor complet — només **carrega, visualitza, divideix i exporta**.

![Python 3.13](https://img.shields.io/badge/Python-3.13-blue)
![PySide6 6.11](https://img.shields.io/badge/PySide6-6.11-green)
![FFmpeg essentials](https://img.shields.io/badge/FFmpeg-essentials-orange)
![License MIT](https://img.shields.io/badge/License-MIT-lightgrey)

> **Versió 0.1.0** — MVP

## Filosofia

> **Tallar un MP3 en diversos trossos de la manera més ràpida i senzilla possible.**

- Simplicitat, rapidesa, interfície clara
- Sense mesclador, efectes, pistes múltiples ni configuració complexa
- Flux: **Obrir → Escoltar → Dividir aquí → Exportar**

## Captura (disseny MVP)

```
[ Obrir MP3 ]  canço.mp3
┌─────────────────────────────────────┐
│ ▂▅████▇▅▃  ▂▃▅██████▇▅▃  (waveform)  │
│──────────────●──────────────────────│
└─────────────────────────────────────┘
00:02:34.250 / 00:05:48.000
[▶ Reproduir] [⏸ Pausar] [⏹ Aturar]  [✂ Dividir aquí]

FRAGMENTS
 1  00:00 → 01:25  [▶] [✕]
 2  01:25 → 02:48  [▶] [✕]
                          [ EXPORTAR FRAGMENTS ]
```

## Funcionalitats 0.1

- Obrir MP3/WAV/M4A/OGG/FLAC (+ drag & drop)
- Waveform lleugera (ffmpeg → PCM 8 kHz mono + peak aggregation NumPy)
- Reproducció QtMultimedia amb cursor, temps i seek per clic
- **Dividir aquí** al cursor (tecla `S` / `Space`)
- Llista fragments amb play/delete
- Exportació **stream copy** (`ffmpeg -c copy`, sense pèrdua) a `canço_01.mp3`, `canço_02.mp3`...

## Requisits

- Python 3.13 + entorn conda `jm_pyside_313` (PySide6 6.11, NumPy 2.5, PyInstaller 6.22)
- FFmpeg bundled a `resources/ffmpeg/ffmpeg.exe` + `ffprobe.exe` (Essentials 9.0.1)

## Instal·lació (desenvolupament)

```bat
:: 1. Clonar
git clone https://github.com/JosepM64/MP3-Cutter.git
cd MP3-Cutter

:: 2. FFmpeg bundled (descarrega Essentials ~196 MB)
get_ffmpeg.bat
:: o manual: copia ffmpeg.exe / ffprobe.exe a resources\ffmpeg\

:: 3. Executar
C:\Users\JM\miniconda3\envs\jm_pyside_313\python.exe main.py
:: o amb arrossegar: python main.py "C:\path\canço.mp3"
```

## Build Windows (portable onedir)

```bat
build.bat
:: → dist\MP3Cutter\MP3Cutter.exe  (~364 MB amb ffmpeg+ffprobe)
:: Per distribuir: comprimeix la carpeta dist\MP3Cutter sencera
```

- `PYTHONNOUSERSITE=1`, path directe sense `conda run`, fix `libexpat.dll`
- FFmpeg detectat a `_internal/ffmpeg/ffmpeg.exe` (PyInstaller 6) o `resources/ffmpeg/` (dev)

## Estructura

```
MP3-Cutter/
├── main.py
├── mp3_cutter/
│   ├── __init__.py          # __version__ = "0.1.0"
│   ├── models/segment.py
│   ├── audio/ffmpeg.py      # find_ffmpeg(), cut_copy(), probe_duration()
│   ├── audio/waveform.py    # generate_waveform()
│   ├── audio/playback.py    # QMediaPlayer wrapper
│   └── ui/
│       ├── main_window.py
│       └── waveform_widget.py
├── resources/ffmpeg/        # ffmpeg.exe + ffprobe.exe (gitignored)
├── build.bat
├── get_ffmpeg.bat / .py
└── requirements.txt
```

## Qualitat

Tall per defecte amb **stream copy** (`-c copy`) — ultra ràpid, sense recodificar ni pèrdua. Fallback re-encode (`libmp3lame`) disponible a `ffmpeg.py:222` però no exposat a la UI 0.1.

## Llicència

MIT — veure `LICENSE` (si escau).

## Roadmap

- 0.1 → MVP actual (Dividir aquí + Exportar)
- 0.2 → Zoom waveform, renombrar fragments, exportar selecció
- Futur → mode precís re-encode, fade in/out, guardar projecte de talls
