from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Segment:
    start: float  # seconds
    end: float  # seconds
    name: str = ""

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def fmt_range(self) -> str:
        return f"{_fmt(self.start)} → {_fmt(self.end)}"

    def fmt_duration(self) -> str:
        return _fmt(self.duration)


def _fmt(seconds: float) -> str:
    """00:00.000 or 00:00:00.000 if >= 1h"""
    seconds = max(seconds, 0)
    total_ms = round(seconds * 1000)
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
    return f"{m:02d}:{s:02d}.{ms:03d}"


def fmt_time(seconds: float) -> str:
    return _fmt(seconds)


def parse_time(text: str) -> float:
    """Parse MM:SS.mmm or HH:MM:SS.mmm or SS.mmm -> seconds. Raises ValueError."""
    text = text.strip()
    if not text:
        raise ValueError("temps buit")
    # allow comma as decimal
    text = text.replace(",", ".")
    parts = text.split(":")
    try:
        if len(parts) == 1:
            return float(parts[0])
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        elif len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        else:
            raise ValueError
    except ValueError:
        raise ValueError(f"format de temps no vàlid: {text}")
