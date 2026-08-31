from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .ffmpeg import find_ffmpeg


@dataclass
class WaveformData:
    peaks: np.ndarray  # shape (N,) float32 0..1
    duration: float  # seconds
    sample_rate: int
    num_samples: int  # original decoded samples count


def generate_waveform(
    filepath: str | Path,
    target_width: int = 1200,
    sample_rate: int = 8000,
    duration: float | None = None,
) -> WaveformData:
    """
    Genera peaks per a waveform lleugera.
    - Decodifica via ffmpeg a pcm s16le mono 8kHz via pipe (sense carregar tot l'MP3 en RAM descomprimit a alta qualitat)
    - Agrupa amb peak aggregation (max abs per bloc) per tenir ~target_width punts
    - Retorna valors normalitzats 0..1

    Per fitxers llargs, això és O(N) però amb RAM baixa (8kHz mono).
    """
    fp = Path(filepath)
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        raise RuntimeError("FFmpeg no trobat per generar waveform")

    # Estimate duration if not provided - decode full anyway, but we need it for scaling
    # We'll just decode and infer duration from decoded size if not given

    cmd = [
        str(ffmpeg),
        "-v",
        "error",
        "-i",
        str(fp),
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-",
    ]

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

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=startupinfo,
        creationflags=creationflags,
    )
    raw, err = proc.communicate(timeout=60)

    if proc.returncode != 0:
        raise RuntimeError(
            f"FFmpeg waveform failed: {err.decode(errors='ignore')[:500]}"
        )

    if not raw or len(raw) < 2:
        # empty -> silence
        peaks = np.zeros(target_width, dtype=np.float32)
        dur = duration or 0.0
        return WaveformData(
            peaks=peaks, duration=dur, sample_rate=sample_rate, num_samples=0
        )

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0  # -1..1
    n = len(samples)
    if duration is None:
        duration = n / float(sample_rate)
    if duration <= 0:
        duration = n / float(sample_rate)

    # Peak aggregation to target_width
    if n <= target_width:
        # upsample via absolute value
        peaks = np.abs(samples)
        # pad if needed
        if len(peaks) < target_width:
            # stretch via interpolation-like repeat
            # simple: pad zeros
            padded = np.zeros(target_width, dtype=np.float32)
            padded[: len(peaks)] = peaks
            peaks = padded
        else:
            peaks = peaks.astype(np.float32)
    else:
        # block size
        block = n // target_width
        remainder = n % target_width
        peaks = np.empty(target_width, dtype=np.float32)
        idx = 0
        for i in range(target_width):
            sz = block + (1 if i < remainder else 0)
            chunk = samples[idx : idx + sz]
            peaks[i] = float(np.max(np.abs(chunk))) if len(chunk) else 0.0
            idx += sz
        # optional small smoothing via moving max? keep raw peak for visual fidelity
        # normalize 0..1 already, but ensure clip
        peaks = np.clip(peaks, 0, 1).astype(np.float32)

    # Light RMS boost for low volumes? Keep linear
    return WaveformData(
        peaks=peaks, duration=duration, sample_rate=sample_rate, num_samples=n
    )
