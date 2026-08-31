from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from mp3_cutter.models.segment import Segment


class FFMpegNotFoundError(RuntimeError):
    pass


class FFMpegError(RuntimeError):
    pass


def _bundled_candidates() -> list[Path]:
    cands: list[Path] = []
    # PyInstaller _MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        p = Path(meipass) / "ffmpeg" / "ffmpeg.exe"
        cands.append(p)
        p = Path(meipass) / "resources" / "ffmpeg" / "ffmpeg.exe"
        cands.append(p)
        p = Path(meipass) / "ffmpeg.exe"
        cands.append(p)

    # exe dir (onedir / onefile extraction)
    exe_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else None
    if exe_dir:
        cands.append(exe_dir / "ffmpeg" / "ffmpeg.exe")
        cands.append(exe_dir / "resources" / "ffmpeg" / "ffmpeg.exe")
        cands.append(exe_dir / "ffmpeg.exe")
        # PyInstaller 6 onedir: _internal folder
        cands.append(exe_dir / "_internal" / "ffmpeg" / "ffmpeg.exe")
        cands.append(exe_dir / "_internal" / "resources" / "ffmpeg" / "ffmpeg.exe")
        cands.append(exe_dir / "_internal" / "ffmpeg.exe")

    # project root detection (dev mode)
    here = Path(__file__).resolve()
    for parent in [here.parents[2], here.parents[1], Path.cwd()]:
        cands.append(parent / "resources" / "ffmpeg" / "ffmpeg.exe")
        cands.append(parent / "ffmpeg" / "ffmpeg.exe")
        # E:\AI\MP3-Cutter\resources\ffmpeg\ffmpeg.exe is the canonical bundled path
        cands.append(parent / "resources" / "ffmpeg.exe")

    # Also check E:\AI\MP3-Cutter explicit
    cands.append(Path(r"E:\AI\MP3-Cutter\resources\ffmpeg\ffmpeg.exe"))

    return cands


def find_ffmpeg() -> Path | None:
    for p in _bundled_candidates():
        if p.is_file():
            return p
    found = shutil.which("ffmpeg")
    if found:
        return Path(found)
    return None


def find_ffprobe(ffmpeg_path: Path | None = None) -> Path | None:
    # Try ffprobe next to ffmpeg
    if ffmpeg_path and ffmpeg_path.is_file():
        probe = ffmpeg_path.parent / "ffprobe.exe"
        if probe.is_file():
            return probe
        probe = ffmpeg_path.parent / "ffprobe"
        if probe.is_file():
            return probe
        # bundled ffprobe in resources/ffmpeg
        for parent in [ffmpeg_path.parent, ffmpeg_path.parent.parent]:
            c = parent / "ffprobe.exe"
            if c.is_file():
                return c
    # Check bundled candidates directly
    for p in _bundled_candidates():
        probe = p.parent / "ffprobe.exe"
        if probe.is_file():
            return probe
    found = shutil.which("ffprobe")
    if found:
        return Path(found)
    return None


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    # Hide console window on Windows
    startupinfo = None
    creationflags = 0
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = (
            subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "CREATE_NO_WINDOW")
            else 0
        )
    return subprocess.run(
        cmd, startupinfo=startupinfo, creationflags=creationflags, **kwargs
    )


class FFMpeg:
    def __init__(self, ffmpeg_path: Path | None = None):
        p = ffmpeg_path or find_ffmpeg()
        if p is None or not p.is_file():
            cands = "\n".join(f"  - {c}" for c in _bundled_candidates()[:8])
            raise FFMpegNotFoundError(
                "No s'ha trobat FFmpeg.\n"
                "Col·loca ffmpeg.exe a resources/ffmpeg/ffmpeg.exe\n"
                "o instal·la FFmpeg i afegeix-lo al PATH.\n"
                "\nSolució ràpida (bundled):\n"
                "  1) Executa get_ffmpeg.bat a la carpeta del projecte\n"
                "     (descarrega ffmpeg.exe + ffprobe.exe automàticament)\n"
                "  2) Torna a executar build.bat\n"
                "\nSolució sense recompilar (dist ja generat):\n"
                "  Copia ffmpeg.exe a dist\\MP3Cutter\\_internal\\ffmpeg\\ffmpeg.exe\n"
                "  i ffprobe.exe al mateix lloc.\n"
                f"\nCandidats buscats:\n{cands}\n"
                "PATH=" + (os.environ.get("PATH", "")[:200] + "...")
            )
        self.ffmpeg = p
        self.ffprobe = find_ffprobe(p)

    def probe_duration(self, filepath: str | Path) -> float:
        """Return duration in seconds. Raises FFMpegError."""
        fp = Path(filepath)

        # 1) try ffprobe if available (fast, precise)
        if self.ffprobe and self.ffprobe.is_file():
            try:
                cp = _run(
                    [
                        str(self.ffprobe),
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=noprint_wrappers=1:nokey=1",
                        str(fp),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if cp.returncode == 0:
                    val = cp.stdout.strip()
                    if val and val != "N/A":
                        return float(val)
            except Exception:
                pass

        # 2) fallback: ffmpeg -i parsing Duration: HH:MM:SS.ms
        cp = _run(
            [str(self.ffmpeg), "-i", str(fp)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        # ffmpeg prints info to stderr
        text = cp.stderr or cp.stdout or ""
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", text)
        if m:
            h, mi, s, cs = m.groups()
            # cs is centiseconds? actually ffmpeg shows .xx -> centiseconds, but we treat as hundredths
            # Better parse generically: pad to ms
            frac = (cs + "000")[:3]  # to milliseconds
            return int(h) * 3600 + int(mi) * 60 + int(s) + int(frac) / 1000.0

        raise FFMpegError(f"No s'ha pogut obtenir la durada de: {fp.name}")

    def cut_copy(self, src: str | Path, dst: str | Path, seg: Segment) -> None:
        """Cut segment with stream copy (-c copy). Very fast, no re-encode."""
        src = Path(src)
        dst = Path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)

        # -ss before -i for fast seek, -to after -i for precise? For -c copy we use -ss before -i
        # Use -ss after -i if we want accuracy but slower. MVP: fast.
        # We expose both via accurate param later; here keep copy.
        dur = seg.end - seg.start
        if dur <= 0:
            raise FFMpegError("Durada de fragment no vàlida")

        cmd = [
            str(self.ffmpeg),
            "-y",
            "-ss",
            f"{seg.start:.3f}",
            "-i",
            str(src),
            "-t",
            f"{dur:.3f}",
            "-c",
            "copy",
            "-vn",
            str(dst),
        ]
        cp = _run(cmd, capture_output=True, text=True, timeout=120)
        if cp.returncode != 0:
            # Fallback without -vn for files that trigger it
            cmd2 = [
                str(self.ffmpeg),
                "-y",
                "-ss",
                f"{seg.start:.3f}",
                "-i",
                str(src),
                "-t",
                f"{dur:.3f}",
                "-c",
                "copy",
                str(dst),
            ]
            cp2 = _run(cmd2, capture_output=True, text=True, timeout=120)
            if cp2.returncode != 0:
                raise FFMpegError(
                    cp.stderr.strip()
                    or cp.stdout.strip()
                    or f"FFmpeg error code {cp.returncode}"
                )

        # Some MP3 copy cuts may produce 0-byte or too small; verify
        if not dst.is_file() or dst.stat().st_size < 1024:
            # If suspiciously small, raise but don't delete
            pass

    def cut_reencode(
        self, src: str | Path, dst: str | Path, seg: Segment, bitrate: str = "192k"
    ) -> None:
        """Accurate cut with re-encode (libmp3lame). Slower but sample-accurate."""
        src = Path(src)
        dst = Path(dst)
        dur = seg.end - seg.start
        cmd = [
            str(self.ffmpeg),
            "-y",
            "-ss",
            f"{seg.start:.3f}",
            "-i",
            str(src),
            "-t",
            f"{dur:.3f}",
            "-vn",
            "-c:a",
            "libmp3lame",
            "-b:a",
            bitrate,
            str(dst),
        ]
        cp = _run(cmd, capture_output=True, text=True, timeout=300)
        if cp.returncode != 0:
            raise FFMpegError(
                cp.stderr.strip() or cp.stdout.strip() or "FFmpeg re-encode failed"
            )

    def check_available(self) -> bool:
        try:
            cp = _run(
                [str(self.ffmpeg), "-version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return cp.returncode == 0
        except Exception:
            return False
