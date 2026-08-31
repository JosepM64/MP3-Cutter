from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class AudioPlayer(QObject):
    positionChanged = Signal(int)  # ms
    durationChanged = Signal(int)  # ms
    playbackStateChanged = Signal(QMediaPlayer.PlaybackState)
    mediaStatusChanged = Signal(QMediaPlayer.MediaStatus)
    errorOccurred = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(0.85)

        self.player.positionChanged.connect(self.positionChanged.emit)
        self.player.durationChanged.connect(self.durationChanged.emit)
        self.player.playbackStateChanged.connect(self.playbackStateChanged.emit)
        self.player.mediaStatusChanged.connect(self.mediaStatusChanged.emit)
        self.player.errorOccurred.connect(self._on_error)

        self._source: Path | None = None

    def _on_error(self, error, errorString: str = ""):
        # Qt6 signature: errorOccurred(QMediaPlayer::Error, QString)
        # but we connected generic
        try:
            msg = self.player.errorString() or errorString or str(error)
        except Exception:
            msg = str(error)
        if msg:
            self.errorOccurred.emit(msg)

    def load(self, filepath: str | Path):
        fp = Path(filepath).resolve()
        self._source = fp
        self.player.setSource(QUrl.fromLocalFile(str(fp)))

    def play(self):
        self.player.play()

    def pause(self):
        self.player.pause()

    def stop(self):
        self.player.stop()

    def set_position_ms(self, ms: int):
        self.player.setPosition(int(ms))

    def set_position_sec(self, sec: float):
        self.player.setPosition(int(sec * 1000))

    def position_sec(self) -> float:
        return self.player.position() / 1000.0

    def duration_sec(self) -> float:
        d = self.player.duration()
        if d <= 0:
            return 0.0
        return d / 1000.0

    def is_playing(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def set_volume(self, vol01: float):
        self.audio.setVolume(max(0.0, min(1.0, vol01)))

    def play_segment(self, filepath: str | Path, start: float, end: float):
        """Load and play - seeking is handled by MainWindow with timer stop at end."""
        self.load(filepath)
        # Need to wait for media loaded before seeking? Qt will seek when playable.
        # We'll set position after a short delay via caller or immediate.
        self.player.setPosition(int(start * 1000))
        self.player.play()
