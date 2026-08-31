MP3 Cutter - FFmpeg bundled

Col·loca aquí els binaris de FFmpeg per a Windows:

  resources/ffmpeg/ffmpeg.exe
  resources/ffmpeg/ffprobe.exe   (opcional però recomanat)
  resources/ffmpeg/ffplay.exe    (no necessari)

Descàrrega oficial:
  https://ffmpeg.org/download.html  -> Windows builds by gyan.dev o BtbN
  Exemple: ffmpeg-release-essentials.zip -> bin/ffmpeg.exe

Un cop copiats, l'aplicació els detectarà automàticament tant en mode
desenvolupament (python main.py) com en l'executable PyInstaller (onedir).

Si no hi són, l'app intentarà trobar ffmpeg al PATH del sistema.

Verificació:
  resources/ffmpeg/ffmpeg.exe -version
  resources/ffmpeg/ffprobe.exe -version
