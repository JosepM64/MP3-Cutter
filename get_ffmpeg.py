"""Descarrega ffmpeg.exe + ffprobe.exe per a MP3 Cutter (bundled).

Intenta en ordre:
  1) descarrega zip BtbN/gyan.dev (build estàtic portable, recomanat)
  2) conda install ffmpeg (fallback, no portable sense DLLs)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "resources" / "ffmpeg"
DEST.mkdir(parents=True, exist_ok=True)

# Essentials = ideal per tallar MP3 amb -c copy (sense re-encode, sense pèrdua)
# GPL master = fallback més gran (145 MB per exe)
URLS = [
    # gyan.dev essentials (98 MB per exe, total ~196 MB) - recomanat per MP3 Cutter
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    # fallback - BtbN GPL (145 MB per exe, total ~291 MB)
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
]

CONDA_EXE_CANDIDATES = [
    r"C:\Users\JM\miniconda3\Scripts\conda.exe",
    r"C:\Users\JM\miniconda3\condabin\conda.bat",
]


def try_conda() -> bool:
    conda = None
    for c in CONDA_EXE_CANDIDATES:
        if Path(c).exists():
            conda = c
            break
    if not conda:
        found = shutil.which("conda")
        if found:
            conda = found
    if not conda:
        return False

    print(f"[INFO] Provant conda: {conda} install ffmpeg ...")
    # Instal·la ffmpeg al env jm_pyside_313 si existeix, si no al base
    env = r"C:\Users\JM\miniconda3\envs\jm_pyside_313"
    target_env = "jm_pyside_313" if Path(env).exists() else "base"
    # --yes evita prompt
    cmd = [
        conda,
        "install",
        "-n",
        target_env,
        "-c",
        "conda-forge",
        "ffmpeg",
        "-y",
        "--no-update-deps",
    ]
    try:
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        # timeout 5 min
        print(" ".join(cmd))
        cp = subprocess.run(
            cmd, startupinfo=startupinfo, creationflags=creationflags, timeout=300
        )
        if cp.returncode != 0:
            print(f"[WARN] conda install ha retornat {cp.returncode}")
            return False
    except Exception as e:
        print(f"[WARN] conda install error: {e}")
        return False

    # Busca ffmpeg.exe instal·lat per conda
    candidates = []
    if target_env != "base":
        candidates.append(Path(env) / "Library" / "bin" / "ffmpeg.exe")
        candidates.append(Path(env) / "bin" / "ffmpeg.exe")
        candidates.append(Path(env) / "ffmpeg.exe")
    # base també
    candidates.append(Path(r"C:\Users\JM\miniconda3\Library\bin\ffmpeg.exe"))
    for p in candidates:
        if p.is_file():
            print(f"[INFO] Trobat conda ffmpeg: {p}")
            return copy_from(p.parent)
    print("[WARN] conda diu instal·lat pero no s'ha trobat ffmpeg.exe")
    return False


def copy_from(bin_dir: Path) -> bool:
    ok = False
    for name in ("ffmpeg.exe", "ffprobe.exe", "ffplay.exe"):
        src = bin_dir / name
        if src.is_file():
            dst = DEST / name
            shutil.copy2(src, dst)
            print(f"[OK] Copiat {src} -> {dst}")
            ok = True
    return ok


def download_zip() -> bool:
    tmpdir = Path(tempfile.mkdtemp(prefix="mp3cutter_ffmpeg_"))
    zip_path = tmpdir / "ffmpeg.zip"
    for url in URLS:
        try:
            print(f"[INFO] Descarregant {url} ...")
            print(f"      -> {zip_path} (pot trigar 1-2 min, ~30-80 MB)")

            # User-Agent per evitar 403 GitHub
            opener = urllib.request.build_opener()
            opener.addheaders = [("User-Agent", "MP3Cutter/1.0")]
            urllib.request.install_opener(opener)
            urllib.request.urlretrieve(url, zip_path)
            print(f"[INFO] Descarregat {zip_path.stat().st_size / 1024 / 1024:.1f} MB")
            # extreu
            with zipfile.ZipFile(zip_path, "r") as zf:
                # busca bin/ffmpeg.exe dins el zip
                for member in zf.namelist():
                    low = member.lower()
                    if low.endswith("bin/ffmpeg.exe") or low.endswith(
                        "bin/ffprobe.exe"
                    ):
                        # extreu només aquest fitxer
                        # normalitza dest name
                        fname = Path(member).name
                        target = DEST / fname
                        with zf.open(member) as src, open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        print(f"[OK] Extret {member} -> {target}")
            # verifica
            if (DEST / "ffmpeg.exe").is_file():
                print(f"[OK] FFmpeg llest a {DEST / 'ffmpeg.exe'}")
                if (DEST / "ffprobe.exe").is_file():
                    print(f"[OK] ffprobe llest a {DEST / 'ffprobe.exe'}")
                try:
                    shutil.rmtree(tmpdir, ignore_errors=True)
                except Exception:
                    pass
                return True
            else:
                print("[WARN] No s'ha trobat bin/ffmpeg.exe dins el zip")
                continue
        except Exception as e:
            print(f"[WARN] Error descarregant {url}: {e}")
            continue
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass
    return False


def main() -> int:
    print(f"[INFO] Destí: {DEST}")
    if (DEST / "ffmpeg.exe").is_file():
        print(f"[INFO] Ja existeix {DEST / 'ffmpeg.exe'} - el sobreescric...")

    # 1) preferim build estàtic (portable, sense DLLs)
    if download_zip():
        print("\n[OK] FFmpeg descarregat i instal·lat correctament.")
        print("Ara executa  build.bat  per regenerar l'executable amb FFmpeg inclòs.")
        print(
            "O copia manualment resources/ffmpeg/ffmpeg.exe al costat de l'exe ja compilat:"
        )
        print(
            r"  copy resources\ffmpeg\ffmpeg.exe dist\MP3Cutter\_internal\ffmpeg\ffmpeg.exe"
        )
        print(
            r"  copy resources\ffmpeg\ffprobe.exe dist\MP3Cutter\_internal\ffmpeg\ffprobe.exe"
        )
        return 0

    print(
        "[INFO] Descarrega directa ha fallat, provant conda (fallback no portable)..."
    )
    if try_conda():
        print("\n[OK] FFmpeg instal·lat via conda i copiat a resources/ffmpeg/")
        print(
            "[WARN] El build conda depèn de DLLs del entorn; preferible usa el build estàtic."
        )
        return 0

    print("\n[ERROR] No s'ha pogut obtenir FFmpeg automàticament.")
    print("Solució manual:")
    print(
        "  1) https://github.com/BtbN/FFmpeg-Builds/releases -> descarrega ffmpeg-master-latest-win64-gpl.zip"
    )
    print("  2) Extreu bin/ffmpeg.exe i bin/ffprobe.exe")
    print(f"  3) Copia'ls a {DEST}\\")
    return 1


if __name__ == "__main__":
    sys.exit(main())
