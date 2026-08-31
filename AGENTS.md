# AGENTS.md — MP3 Cutter

Projecte Windows portable per tallar MP3 amb precisió visual. Prioritat: **simplicitat > rapidesa > precisió**.

## Stack

- **Python** 3.13.14 (`jm_pyside_313` a `C:\Users\JM\miniconda3\envs\jm_pyside_313\python.exe`) — no usar `conda run`
- **PySide6** 6.11.2 (pip), **NumPy** 2.5.2, **PyInstaller** 6.22.2, **FFmpeg** 9.0.1 Essentials (`resources/ffmpeg/`)
- **SO**: Windows 10/11

## Comportament (agents)

- Màxim 5 bullets a la resposta final
- Validar amb `ruff format` + `py_compile` abans de commit
- Commits en català, versió semàntica (`0.3.0` actual)
- Push a `https://github.com/JosepM64/MP3-Cutter` amb tag `vX.Y.Z`

## Estructura

```
MP3-Cutter/
├── main.py                      # entry + dark palette + argv
├── mp3_cutter/
│   ├── __init__.py              # __version__ = "0.3.0"
│   ├── models/segment.py
│   ├── audio/ffmpeg.py          # find_ffmpeg(), cut_copy() (-c copy), _internal/ffmpeg
│   ├── audio/waveform.py        # ffmpeg pcm 8kHz → peaks 1600
│   ├── audio/playback.py        # QMediaPlayer wrapper
│   └── ui/
│       ├── main_window.py       # zoom + scroll + About + solo
│       └── waveform_widget.py   # zoom 0.5-8x, drag marques, segmentClicked
├── resources/ffmpeg/ffmpeg.exe + ffprobe.exe (gitignored, 196 MB)
├── build.bat                    # onedir, !FFMPEG_ARGS!, sense --collect-all, libexpat fix
├── get_ffmpeg.bat/.py           # descarrega Essentials via gyan.dev
└── requirements.txt             # PySide6, numpy
```

## Funcionalitats per versió

- **0.1.0**: MVP Obrir→Reproduir→Dividir→Exportar, waveform, stream copy
- **0.2.0**: Zoom 0.5–8x (Ctrl+Roda, slider, +/-/1:1), marques arrossegables, menú contextual, About (F1), dist 364 MB
- **0.3.0**: **Clic al número de fragment a la waveform → solo playback** (`segmentClicked` → `_play_segment`), hint actualitzat
- **0.3.1**: Fix solo playback — `seek_to(clear_segment=False)` + `_play_segment` preserva `idx`, `_poll_cursor` para exactament a `seg.end` (abans continuava per `seek_to` que esborrava `idx`)

## Build

```bat
get_ffmpeg.bat   # primer cop, descarrega Essentials
build.bat        # → dist\MP3Cutter\MP3Cutter.exe (364 MB)
python main.py   # dev:  C:\Users\JM\miniconda3\envs\jm_pyside_313\python.exe main.py
```

- `PYTHONNOUSERSITE=1`, path directe, `pushd "%~dp0"`, 1× `ffmpeg` (no duplicar), excloure QtQml/Quick/Pdf
- FFmpeg bundled a `_internal/ffmpeg/` (PyInstaller 6)

## Flux core

`Obrir MP3 / drag&drop → Waveform (zoom, marques grogues etiquetades MM:SS.mmm) → Clic número = solo fragment / ▶ a FRAGMENTS / S o Dividir aquí / doble clic afegeix / arrossegar mou / clic dret esborra → Exportar fragments (stream copy, sense pèrdua) → Ajuda → Sobre (F1) amb versions + autor Josep Maria Tapia https://www.posicionamientowebysem.com/`

## Qualitat

- Tall per defecte `ffmpeg -c copy` (sense re-encode)
- `ffprobe` opcional però recomanat per durada precisa (estalvi 98 MB si es treu)
- `libexpat.dll` duplicat a `dist\MP3Cutter\` i `_internal\PySide6\` és workaround PyInstaller

## Roadmap

- 0.3 → solo per clic, AGENTS.md
- 0.4 → exportar només seleccionats, renombrar fragments, normalització opcional
