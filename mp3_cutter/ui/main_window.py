from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, QTimer, Signal
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSlider,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from mp3_cutter.audio.ffmpeg import (
    FFMpeg,
    FFMpegError,
    FFMpegNotFoundError,
    find_ffmpeg,
)
from mp3_cutter.audio.playback import AudioPlayer
from mp3_cutter.audio.waveform import WaveformData, generate_waveform
from mp3_cutter.models.segment import Segment, fmt_time
from mp3_cutter.ui.waveform_widget import WaveformWidget


# --- Worker for waveform generation (avoid blocking UI) ---
class WaveformWorker(QThread):
    done = Signal(object)  # WaveformData or None
    error = Signal(str)

    def __init__(self, filepath: str, duration: float | None, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.duration = duration

    def run(self):
        try:
            # adapt target_width to widget approx; fixed 1600 for hi-dpi crisp
            data = generate_waveform(
                self.filepath,
                target_width=1600,
                sample_rate=8000,
                duration=self.duration,
            )
            self.done.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class SegmentItemWidget(QWidget):
    playRequested = Signal(int)
    deleteRequested = Signal(int)

    def __init__(self, idx: int, seg: Segment, parent=None):
        super().__init__(parent)
        self.idx = idx
        self.seg = seg
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)

        self.lbl_idx = QLabel(f"{idx + 1:02d}")
        self.lbl_idx.setFixedWidth(28)
        self.lbl_idx.setStyleSheet("color:#90caf9; font-weight:700;")
        self.lbl_range = QLabel(seg.fmt_range())
        self.lbl_range.setStyleSheet("color:#eee; font-family: Consolas, monospace;")
        self.lbl_dur = QLabel(f"({seg.fmt_duration()})")
        self.lbl_dur.setStyleSheet("color:#999; font-size:11px;")

        lay.addWidget(self.lbl_idx)
        lay.addWidget(self.lbl_range)
        lay.addWidget(self.lbl_dur)
        lay.addStretch()

        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedSize(28, 26)
        self.btn_play.setToolTip("Reproduir fragment")
        self.btn_play.setStyleSheet(_btn_small_style())
        self.btn_play.clicked.connect(lambda: self.playRequested.emit(self.idx))

        self.btn_del = QPushButton("✕")
        self.btn_del.setFixedSize(28, 26)
        self.btn_del.setToolTip("Eliminar fragment")
        self.btn_del.setStyleSheet(_btn_small_style(danger=True))
        self.btn_del.clicked.connect(lambda: self.deleteRequested.emit(self.idx))

        lay.addWidget(self.btn_play)
        lay.addWidget(self.btn_del)


def _btn_small_style(danger=False) -> str:
    if danger:
        return """
        QPushButton { background:#3a2323; color:#ef9a9a; border:1px solid #5d2e2e; border-radius:6px; font-weight:700; }
        QPushButton:hover { background:#5d2e2e; color:white; }
        QPushButton:pressed { background:#3a1a1a; }
        """
    return """
    QPushButton { background:#2a3a4a; color:#90caf9; border:1px solid #3a4a5a; border-radius:6px; font-weight:700; }
    QPushButton:hover { background:#344a5e; color:white; }
    QPushButton:pressed { background:#223344; }
    """


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MP3 Cutter  —  Obrir → Reproduir → Dividir → Exportar")
        self.resize(960, 620)
        self.setAcceptDrops(True)

        # state
        self.filepath: Path | None = None
        self.duration: float = 0.0
        self.cursor_sec: float = 0.0
        self.segments: list[Segment] = []
        self.split_points: list[float] = []  # sorted
        self._playing_segment_idx: int | None = None
        self._segment_end_timer: QTimer | None = None
        self._wave_worker: WaveformWorker | None = None
        self._ffmpeg: FFMpeg | None = None
        try:
            self._ffmpeg = FFMpeg()
        except FFMpegNotFoundError:
            self._ffmpeg = None

        self.player = AudioPlayer(self)
        self.player.positionChanged.connect(self._on_player_pos)
        self.player.durationChanged.connect(self._on_player_duration)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.errorOccurred.connect(self._on_player_error)

        self._build_ui()
        self._update_ui_state()
        self._check_ffmpeg()

        # timer for cursor follow while playing (if duration unknown)
        self._cursor_timer = QTimer(self)
        self._cursor_timer.setInterval(80)
        self._cursor_timer.timeout.connect(self._poll_cursor)

    # --- UI ---
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Top bar: Obrir + filename + ffmpeg status
        top = QHBoxLayout()
        top.setSpacing(10)

        self.btn_open = QPushButton("  Obrir MP3")
        try:
            self.btn_open.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
            )
        except Exception:
            pass
        self.btn_open.setFixedHeight(38)
        self.btn_open.setStyleSheet(_primary_btn())
        self.btn_open.clicked.connect(self.open_file)

        self.lbl_file = QLabel("Cap fitxer obert  —  arrossega un MP3 aquí")
        self.lbl_file.setStyleSheet("color:#aaa; font-size:12px; padding-left:8px;")
        self.lbl_file.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.lbl_ffmpeg = QLabel()
        self.lbl_ffmpeg.setStyleSheet("color:#888; font-size:10px;")
        self.lbl_ffmpeg.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        top.addWidget(self.btn_open)
        top.addWidget(self.lbl_file, 1)
        top.addWidget(self.lbl_ffmpeg)
        root.addLayout(top)

        # Waveform with zoom + scroll
        self.wave = WaveformWidget()
        self.wave.setStyleSheet("border-radius:8px;")
        self.wave.clickedAt.connect(self.seek_to)
        self.wave.splitRequested.connect(self._on_wave_split_request)
        self.wave.splitsChanged.connect(self._on_wave_splits_changed)
        self.wave.zoomChanged.connect(self._on_wave_zoom_changed)
        self.wave.segmentClicked.connect(self._play_segment)

        self.wave_scroll = QScrollArea()
        self.wave_scroll.setWidgetResizable(False)
        self.wave_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.wave_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.wave_scroll.setFixedHeight(168)
        self.wave_scroll.setStyleSheet(
            "QScrollArea { background:#1e1e1e; border:1px solid #2e2e2e; border-radius:8px; }"
            "QScrollBar:horizontal { height:10px; background:#1a1a1a; border-radius:4px; }"
            "QScrollBar::handle:horizontal { background:#3a4a5a; border-radius:4px; min-width:40px; }"
            "QScrollBar::handle:horizontal:hover { background:#4a6a8a; }"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }"
        )
        self.wave_scroll.setWidget(self.wave)
        # context menu for marker delete
        self.wave.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.wave.customContextMenuRequested.connect(self._on_wave_context_menu)
        root.addWidget(self.wave_scroll)

        # Zoom bar
        zoom_row = QHBoxLayout()
        zoom_row.setSpacing(6)
        zoom_label = QLabel("🔍 Zoom:")
        zoom_label.setStyleSheet("color:#999; font-size:11px;")
        self.btn_zoom_out = QPushButton("−")
        self.btn_zoom_out.setFixedSize(28, 22)
        self.btn_zoom_out.setToolTip("Allunyar (Ctrl + Roda avall)")
        self.btn_zoom_out.setStyleSheet(_btn_small_style())
        self.btn_zoom_out.clicked.connect(self.wave.zoom_out)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(0, len(WaveformWidget.ZOOM_LEVELS) - 1)
        self.zoom_slider.setValue(1)  # 1.0x
        self.zoom_slider.setFixedWidth(120)
        self.zoom_slider.setStyleSheet(_slider_style(small=True))
        self.zoom_slider.setToolTip(
            "Arrossega per canviar zoom (o Ctrl+Roda sobre la waveform)"
        )
        self.zoom_slider.valueChanged.connect(self._on_zoom_slider)

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setFixedSize(28, 22)
        self.btn_zoom_in.setToolTip("Apropar (Ctrl + Roda amunt)")
        self.btn_zoom_in.setStyleSheet(_btn_small_style())
        self.btn_zoom_in.clicked.connect(self.wave.zoom_in)

        self.btn_zoom_reset = QPushButton("1:1")
        self.btn_zoom_reset.setFixedSize(38, 22)
        self.btn_zoom_reset.setToolTip("Zoom 1:1 (Ctrl+0)")
        self.btn_zoom_reset.setStyleSheet(_btn_small_style())
        self.btn_zoom_reset.clicked.connect(self.wave.reset_zoom)

        self.btn_zoom_fit = QPushButton("Ajustar")
        self.btn_zoom_fit.setFixedSize(58, 22)
        self.btn_zoom_fit.setToolTip("Ajusta tota la cançó a la finestra")
        self.btn_zoom_fit.setStyleSheet(_btn_small_style())
        self.btn_zoom_fit.clicked.connect(self._zoom_fit)

        self.lbl_zoom = QLabel("1.0x")
        self.lbl_zoom.setFixedWidth(40)
        self.lbl_zoom.setStyleSheet("color:#90caf9; font-weight:700; font-size:11px;")
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_zoom_hint = QLabel(
            "Ctrl+Roda zoom • Doble clic afegeix • Clic numero = solo • Arrossega groc"
        )
        self.lbl_zoom_hint.setStyleSheet("color:#666; font-size:10px;")
        self.lbl_zoom_hint.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        zoom_row.addWidget(zoom_label)
        zoom_row.addWidget(self.btn_zoom_out)
        zoom_row.addWidget(self.zoom_slider)
        zoom_row.addWidget(self.btn_zoom_in)
        zoom_row.addWidget(self.btn_zoom_reset)
        zoom_row.addWidget(self.btn_zoom_fit)
        zoom_row.addWidget(self.lbl_zoom)
        zoom_row.addSpacing(10)
        zoom_row.addWidget(self.lbl_zoom_hint, 1)
        root.addLayout(zoom_row)

        # Time + slider row
        time_row = QHBoxLayout()
        self.lbl_time = QLabel("00:00.000 / 00:00.000")
        self.lbl_time.setStyleSheet(
            "color:#ccc; font-family: Consolas, monospace; font-size:13px; font-weight:600;"
        )
        self.lbl_time.setMinimumWidth(190)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.setEnabled(False)
        self.slider.setStyleSheet(_slider_style())
        self.slider.sliderPressed.connect(self._on_slider_pressed)
        self.slider.sliderReleased.connect(self._on_slider_released)
        self.slider.sliderMoved.connect(self._on_slider_moved)
        self._slider_dragging = False

        time_row.addWidget(self.lbl_time)
        time_row.addWidget(self.slider, 1)
        root.addLayout(time_row)

        # Transport
        transport = QHBoxLayout()
        transport.setSpacing(8)

        self.btn_play = QPushButton("▶ Reproduir")
        self.btn_pause = QPushButton("⏸ Pausar")
        self.btn_stop = QPushButton("⏹ Aturar")
        for b in (self.btn_play, self.btn_pause, self.btn_stop):
            b.setFixedHeight(34)
            b.setStyleSheet(_transport_btn())
        self.btn_play.clicked.connect(self.play)
        self.btn_pause.clicked.connect(self.pause)
        self.btn_stop.clicked.connect(self.stop)

        self.btn_split = QPushButton("✂ Dividir aquí")
        self.btn_split.setFixedHeight(34)
        self.btn_split.setToolTip(
            "Crea un punt de tall a la posició del cursor (també: tecla S)"
        )
        self.btn_split.setStyleSheet(_split_btn())
        self.btn_split.clicked.connect(self.split_here)

        transport.addWidget(self.btn_play)
        transport.addWidget(self.btn_pause)
        transport.addWidget(self.btn_stop)
        transport.addSpacing(12)
        transport.addWidget(self.btn_split)
        transport.addStretch()

        # volume small
        vol_lbl = QLabel("🔊")
        vol_lbl.setStyleSheet("color:#888;")
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(85)
        self.vol_slider.setFixedWidth(110)
        self.vol_slider.setStyleSheet(_slider_style(small=True))
        self.vol_slider.valueChanged.connect(
            lambda v: self.player.set_volume(v / 100.0)
        )
        transport.addWidget(vol_lbl)
        transport.addWidget(self.vol_slider)

        root.addLayout(transport)

        # Fragments header + list
        frag_header = QHBoxLayout()
        self.lbl_frag_title = QLabel("FRAGMENTS")
        self.lbl_frag_title.setStyleSheet(
            "color:#90caf9; font-weight:800; letter-spacing:1px; font-size:11px;"
        )
        self.lbl_frag_count = QLabel("0 fragments")
        self.lbl_frag_count.setStyleSheet("color:#777; font-size:11px;")
        self.btn_clear = QPushButton("Netejar")
        self.btn_clear.setFixedSize(70, 24)
        self.btn_clear.setStyleSheet(_btn_small_style())
        self.btn_clear.clicked.connect(self.clear_splits)
        frag_header.addWidget(self.lbl_frag_title)
        frag_header.addWidget(self.lbl_frag_count)
        frag_header.addStretch()
        frag_header.addWidget(QLabel("cuts:"))
        self.lbl_cuts = QLabel("0")
        self.lbl_cuts.setStyleSheet("color:#ffea00; font-weight:700;")
        frag_header.addWidget(self.lbl_cuts)
        frag_header.addSpacing(10)
        frag_header.addWidget(self.btn_clear)
        root.addLayout(frag_header)

        self.list = QListWidget()
        self.list.setStyleSheet(_list_style())
        self.list.setAlternatingRowColors(False)
        self.list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.list.setFixedHeight(160)
        root.addWidget(self.list)

        # Bottom: export
        bottom = QHBoxLayout()
        bottom.addStretch()
        self.btn_export = QPushButton("⬇  EXPORTAR FRAGMENTS")
        self.btn_export.setFixedHeight(42)
        self.btn_export.setMinimumWidth(240)
        self.btn_export.setStyleSheet(_export_btn())
        self.btn_export.clicked.connect(self.export_segments)
        bottom.addWidget(self.btn_export)
        root.addLayout(bottom)

        # Menu Ajuda -> Sobre
        menubar = self.menuBar()
        menubar.setStyleSheet(
            "QMenuBar { background:#1e1e1e; color:#ccc; } QMenuBar::item:selected { background:#2a3a4a; } QMenu { background:#222; color:#ddd; border:1px solid #333; } QMenu::item:selected { background:#2a6cb6; }"
        )
        help_menu = menubar.addMenu("Ajuda")
        act_about = help_menu.addAction("Sobre MP3 Cutter…")
        act_about.setShortcut("F1")
        act_about.triggered.connect(self._show_about)

        # Status bar
        self.statusBar().setStyleSheet("color:#999; font-size:11px;")
        self.statusBar().showMessage("Llestos. Obre un MP3 per començar.  •  F1 Sobre")

        # Shortcuts
        from PySide6.QtGui import QKeySequence, QShortcut

        QShortcut(QKeySequence("Space"), self, activated=self.toggle_play)
        QShortcut(QKeySequence("S"), self, activated=self.split_here)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.open_file)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.export_segments)
        QShortcut(QKeySequence("Delete"), self, activated=self._delete_last_split)
        QShortcut(QKeySequence("Ctrl++"), self, activated=self.wave.zoom_in)
        QShortcut(QKeySequence("Ctrl+="), self, activated=self.wave.zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, activated=self.wave.zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self.wave.reset_zoom)

    # --- ffmpeg check ---
    def _check_ffmpeg(self):
        ff = find_ffmpeg()
        if ff:
            self.lbl_ffmpeg.setText(f"FFmpeg ✓  {ff.parent.name}/{ff.name}")
            self.lbl_ffmpeg.setStyleSheet("color:#66bb6a; font-size:10px;")
            self.statusBar().showMessage(f"FFmpeg trobat: {ff}", 4000)
        else:
            self.lbl_ffmpeg.setText("FFmpeg ✗  — posa ffmpeg.exe a resources/ffmpeg/")
            self.lbl_ffmpeg.setStyleSheet(
                "color:#ef5350; font-size:10px; font-weight:600;"
            )
            self.statusBar().showMessage(
                "⚠ FFmpeg no trobat — la waveform i exportació no funcionaran fins que el col·loquis a resources/ffmpeg/",
                8000,
            )

    # --- File loading ---
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Obrir MP3",
            "",
            "Àudio (*.mp3 *.wav *.m4a *.ogg *.flac);;MP3 (*.mp3);;Tots (*.*)",
        )
        if path:
            self.load_file(Path(path))

    def load_file(self, path: Path):
        if not path.is_file():
            QMessageBox.warning(self, "Error", f"Fitxer no trobat:\n{path}")
            return
        if path.suffix.lower() not in (".mp3", ".wav", ".m4a", ".ogg", ".flac"):
            # allow anyway but warn
            pass

        # ensure ffmpeg
        if self._ffmpeg is None:
            try:
                self._ffmpeg = FFMpeg()
            except FFMpegNotFoundError as e:
                QMessageBox.warning(self, "FFmpeg no trobat", str(e))
                self._check_ffmpeg()
                # still allow loading for playback via Qt, but waveform/export disabled

        self.filepath = path
        self.lbl_file.setText(path.name)
        self.lbl_file.setToolTip(str(path))
        self.split_points.clear()
        self.segments.clear()
        self.cursor_sec = 0.0
        self._playing_segment_idx = None
        self._rebuild_segments()
        self.list.clear()
        self.wave.set_splits([])
        self.wave.set_cursor(0)

        # Probe duration
        self.duration = 0.0
        if self._ffmpeg:
            try:
                self.duration = self._ffmpeg.probe_duration(path)
            except Exception as e:
                self.statusBar().showMessage(f"No s'ha pogut obtenir durada: {e}", 5000)
                # fallback to Qt duration later
                self.duration = 0.0
        else:
            # try Qt duration after load
            self.duration = 0.0

        # Load into player (for playback + duration fallback)
        self.player.load(path)
        self.player.player.play()  # trick to get duration? No, better pause
        self.player.player.pause()

        # If duration still 0, poll Qt duration
        if self.duration <= 0:
            # wait a bit for Qt to know duration
            QTimer.singleShot(400, self._poll_qt_duration)
        else:
            self._on_duration_ready(self.duration)

        # Generate waveform async
        if self._ffmpeg and find_ffmpeg():
            self.statusBar().showMessage("Generant waveform…", 2000)
            self.wave.set_waveform(None, 0)  # placeholder loading
            self._start_waveform_worker(
                path, self.duration if self.duration > 0 else None
            )
        else:
            self.wave.set_waveform(None, 0)

        self._update_ui_state()

    def _poll_qt_duration(self):
        d = self.player.duration_sec()
        if d > 0.1:
            self.duration = d
            self._on_duration_ready(d)
        else:
            # retry a few times
            if not hasattr(self, "_poll_count"):
                self._poll_count = 0
            self._poll_count += 1
            if self._poll_count < 8:
                QTimer.singleShot(300, self._poll_qt_duration)
            else:
                self._poll_count = 0
                # give up, set slider disabled
                self.statusBar().showMessage(
                    "No s'ha pogut determinar la durada.", 4000
                )

    def _on_duration_ready(self, dur: float):
        self.duration = dur
        self.slider.setEnabled(True)
        self.slider.setRange(0, int(dur * 1000))
        self.slider.setValue(0)
        self.lbl_time.setText(f"00:00.000 / {fmt_time(dur)}")
        self._update_ui_state()
        # rebuild segments if we already have splits but duration was 0
        self._rebuild_segments()
        self._refresh_list()

    def _start_waveform_worker(self, path: Path, dur: float | None):
        if self._wave_worker and self._wave_worker.isRunning():
            self._wave_worker.terminate()
            self._wave_worker.wait(500)
        self._wave_worker = WaveformWorker(str(path), dur)
        self._wave_worker.done.connect(self._on_waveform_done)
        self._wave_worker.error.connect(self._on_waveform_error)
        self._wave_worker.start()

    def _on_waveform_done(self, data: WaveformData):
        if self.filepath is None:
            return
        # duration may be more accurate from waveform (decoded size)
        if self.duration <= 0 and data.duration > 0:
            self._on_duration_ready(data.duration)
        elif data.duration > 0:
            # prefer ffmpeg probe if close, but keep waveform duration for sync
            pass
        self.wave.set_waveform(
            data.peaks, data.duration if data.duration > 0 else self.duration
        )
        self.statusBar().showMessage(
            f"Waveform llesta — {data.duration:.1f}s, {len(data.peaks)} punts", 3000
        )

    def _on_waveform_error(self, msg: str):
        self.statusBar().showMessage(f"Error waveform: {msg}", 6000)
        QMessageBox.warning(
            self,
            "Waveform",
            f"No s'ha pogut generar la waveform:\n{msg}\n\nVerifica que FFmpeg estigui a resources/ffmpeg/ffmpeg.exe",
        )

    # --- Playback control ---
    def play(self):
        if not self.filepath:
            self.statusBar().showMessage("Obre primer un MP3.", 2000)
            return
        self.player.play()
        self._cursor_timer.start()
        self._update_transport()

    def pause(self):
        self.player.pause()
        self._cursor_timer.stop()
        self._update_transport()

    def stop(self):
        self.player.stop()
        self._cursor_timer.stop()
        self._playing_segment_idx = None
        # keep cursor where it is? spec says stop -> maybe reset to 0? keep
        self._update_transport()

    def toggle_play(self):
        if self.player.is_playing():
            self.pause()
        else:
            self.play()

    def seek_to(self, sec: float):
        if not self.filepath:
            return
        sec = max(0.0, min(sec, self.duration if self.duration > 0 else sec))
        self.cursor_sec = sec
        self.player.set_position_sec(sec)
        self.wave.set_cursor(sec)
        self.slider.setValue(int(sec * 1000))
        self.lbl_time.setText(f"{fmt_time(sec)} / {fmt_time(self.duration)}")
        self._playing_segment_idx = None
        self._scroll_to_cursor()

    def _poll_cursor(self):
        if self.player.is_playing() and not self._slider_dragging:
            pos = self.player.position_sec()
            self.cursor_sec = pos
            self.wave.set_cursor(pos)
            self.slider.setValue(int(pos * 1000))
            self.lbl_time.setText(f"{fmt_time(pos)} / {fmt_time(self.duration)}")
            if self.wave.zoom() > 1.0:
                self._scroll_to_cursor()
            # check segment end
            if self._playing_segment_idx is not None:
                seg = self.segments[self._playing_segment_idx]
                if pos >= seg.end - 0.08:  # small tolerance for Qt seek granularity
                    self.pause()
                    self.seek_to(seg.end)
                    self._playing_segment_idx = None
                    self.statusBar().showMessage(
                        f"Fragment {self._playing_segment_idx + 1 if self._playing_segment_idx is not None else ''} finalitzat.",
                        2000,
                    )

    def _on_player_pos(self, ms: int):
        if self._slider_dragging:
            return
        sec = ms / 1000.0
        self.cursor_sec = sec
        self.wave.set_cursor(sec)
        self.slider.setValue(ms)
        self.lbl_time.setText(f"{fmt_time(sec)} / {fmt_time(self.duration)}")
        if self.wave.zoom() > 1.0 and self.player.is_playing():
            self._scroll_to_cursor()
        if self._playing_segment_idx is not None:
            seg = self.segments[self._playing_segment_idx]
            if sec >= seg.end - 0.05:
                self.pause()
                self._playing_segment_idx = None

    def _on_player_duration(self, ms: int):
        if ms > 0 and self.duration <= 0:
            self._on_duration_ready(ms / 1000.0)
        elif ms > 0:
            # keep slider range in sync
            self.slider.setRange(0, ms)

    def _on_state_changed(self, state):
        self._update_transport()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._cursor_timer.start()
        else:
            self._cursor_timer.stop()

    def _on_player_error(self, msg: str):
        if msg and "No error" not in msg:
            self.statusBar().showMessage(f"Reproducció: {msg}", 5000)

    def _update_transport(self):
        playing = self.player.is_playing()
        self.btn_play.setEnabled(not playing and self.filepath is not None)
        self.btn_pause.setEnabled(playing)
        self.btn_stop.setEnabled(self.filepath is not None)

    # slider dragging
    def _on_slider_pressed(self):
        self._slider_dragging = True

    def _on_slider_released(self):
        self._slider_dragging = False
        val = self.slider.value()
        self.seek_to(val / 1000.0)

    def _on_slider_moved(self, val: int):
        if self._slider_dragging:
            sec = val / 1000.0
            self.lbl_time.setText(f"{fmt_time(sec)} / {fmt_time(self.duration)}")
            self.wave.set_cursor(sec)

    # --- Splits / Segments ---
    def split_here(self):
        if not self.filepath or self.duration <= 0:
            self.statusBar().showMessage("Obre un MP3 i espera a que carregui.", 2000)
            return
        # use current cursor (player pos if playing else stored)
        sec = (
            self.player.position_sec() if self.player.is_playing() else self.cursor_sec
        )
        # if player duration unknown, fallback to cursor
        if sec <= 0.05:
            sec = self.cursor_sec
        # quantize to 10ms to avoid micro splits?
        sec = round(sec, 3)
        if sec <= 0.2 or sec >= self.duration - 0.2:
            self.statusBar().showMessage(
                "El tall ha d'estar dins l'àudio (no als extrems).", 2500
            )
            return
        # avoid duplicate close splits (<0.15s)
        for s in self.split_points:
            if abs(s - sec) < 0.15:
                self.statusBar().showMessage(
                    f"Ja hi ha un tall a {fmt_time(s)} (massa a prop).", 2500
                )
                return
        self.split_points.append(sec)
        self.split_points.sort()
        self._rebuild_segments()
        self.wave.set_splits(self.split_points)
        self._refresh_list()
        self.statusBar().showMessage(
            f"Tall afegit a {fmt_time(sec)}  —  {len(self.segments)} fragments", 3000
        )
        self._update_ui_state()

    def _delete_last_split(self):
        if self.split_points:
            sec = self.split_points.pop()
            self._rebuild_segments()
            self.wave.set_splits(self.split_points)
            self._refresh_list()
            self.statusBar().showMessage(f"Tall eliminat {fmt_time(sec)}", 2000)

    def clear_splits(self):
        if not self.split_points and not self.segments:
            return
        self.split_points.clear()
        self._rebuild_segments()
        self.wave.set_splits([])
        self._refresh_list()
        self.statusBar().showMessage("Talls netejats.", 2000)
        self._update_ui_state()

    def _rebuild_segments(self):
        dur = self.duration
        if dur <= 0:
            # no duration yet -> single segment placeholder
            self.segments = []
            return
        pts = [0.0] + sorted(self.split_points) + [dur]
        # remove duplicates / clamp
        pts = [max(0.0, min(p, dur)) for p in pts]
        pts = sorted({round(p, 3) for p in pts})
        # edge: ensure 0 and dur
        if pts[0] != 0.0:
            pts = [0.0] + pts
        if pts[-1] != dur:
            pts.append(dur)
        segs: list[Segment] = []
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            if b - a < 0.05:  # ignore tiny slivers
                continue
            segs.append(Segment(start=a, end=b))
        self.segments = segs
        self.lbl_cuts.setText(str(len(self.split_points)))
        self.lbl_frag_count.setText(
            f"{len(segs)} fragment{'s' if len(segs) != 1 else ''}"
        )

    def _refresh_list(self):
        self.list.clear()
        if not self.segments:
            # show placeholder item if file loaded but no splits -> one segment whole file
            if self.filepath and self.duration > 0:
                # whole file as single segment (exportable)
                seg = Segment(0, self.duration)
                self.segments = [seg]
            else:
                return

        for idx, seg in enumerate(self.segments):
            item = QListWidgetItem(self.list)
            w = SegmentItemWidget(idx, seg)
            w.playRequested.connect(self._play_segment)
            w.deleteRequested.connect(self._delete_segment)
            item.setSizeHint(QSize(0, 38))
            self.list.addItem(item)
            self.list.setItemWidget(item, w)

        self._update_ui_state()

    def _play_segment(self, idx: int):
        if idx < 0 or idx >= len(self.segments):
            return
        seg = self.segments[idx]
        self._playing_segment_idx = idx
        self.seek_to(seg.start)
        # small delay to ensure seek before play (Qt needs media ready)
        QTimer.singleShot(80, self.play)
        self.statusBar().showMessage(
            f"Reproduint fragment {idx + 1}: {seg.fmt_range()}", 3000
        )

    def _delete_segment(self, idx: int):
        """Eliminar fragment -> fusiona: elimina el punt de tall corresponent."""
        if idx < 0 or idx >= len(self.segments):
            return
        if len(self.segments) <= 1:
            self.statusBar().showMessage("No es pot eliminar l'únic fragment.", 2000)
            return
        # segment idx corresponds to split idx either at start or end
        # segments are between pts = [0, s1, s2, ..., dur]
        # removing segment idx means removing either pts[idx] or pts[idx+1] (except edges)
        # Better: remove the split point at pts[idx+1] if not last, else pts[idx]
        pts = [0.0] + self.split_points + [self.duration]
        sorted(pts)
        # find split to remove: the boundary after this segment, unless it's last segment
        if idx < len(self.segments) - 1:
            # boundary = end of this segment
            boundary = self.segments[idx].end
        else:
            boundary = self.segments[idx].start
        # find closest split point
        best = None
        best_dist = 1e9
        for s in self.split_points:
            d = abs(s - boundary)
            if d < best_dist:
                best_dist = d
                best = s
        if best is not None and best_dist < 0.01:
            self.split_points.remove(best)
            self._rebuild_segments()
            self.wave.set_splits(self.split_points)
            self._refresh_list()
            self.statusBar().showMessage(
                f"Fragment {idx + 1} eliminat (fusionat).", 2000
            )

    # --- Export ---
    def export_segments(self):
        if not self.filepath:
            QMessageBox.information(self, "Exportar", "Obre primer un MP3.")
            return
        if not self.segments:
            QMessageBox.information(
                self,
                "Exportar",
                "No hi ha fragments per exportar.\nFes algun tall amb «Dividir aquí» o s'exportarà el fitxer sencer.",
            )
            return
        if self._ffmpeg is None:
            try:
                self._ffmpeg = FFMpeg()
            except FFMpegNotFoundError as e:
                QMessageBox.warning(self, "FFmpeg no trobat", str(e))
                return

        out_dir = QFileDialog.getExistingDirectory(self, "Tria carpeta de destinació")
        if not out_dir:
            return
        out_dir = Path(out_dir)
        stem = self.filepath.stem

        # Check overwrite
        existing = []
        for i, seg in enumerate(self.segments):
            name = f"{stem}_{i + 1:02d}.mp3"
            if (out_dir / name).exists():
                existing.append(name)
        if existing:
            ret = QMessageBox.question(
                self,
                "Fitxers existents",
                f"Ja existeixen {len(existing)} fitxers:\n"
                + "\n".join(existing[:5])
                + ("\n…" if len(existing) > 5 else "")
                + "\n\nVols sobreescriure'ls?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ret != QMessageBox.StandardButton.Yes:
                return

        # Progress dialog
        progress = QProgressDialog(
            f"Exportant {len(self.segments)} fragments…",
            "Cancel·lar",
            0,
            len(self.segments),
            self,
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(200)
        progress.setValue(0)

        errors: list[str] = []
        for i, seg in enumerate(self.segments):
            if progress.wasCanceled():
                break
            progress.setValue(i)
            progress.setLabelText(
                f"Exportant {i + 1}/{len(self.segments)}  {seg.fmt_range()}"
            )
            # process events to keep UI responsive
            from PySide6.QtWidgets import QApplication

            QApplication.processEvents()

            dst = out_dir / f"{stem}_{i + 1:02d}.mp3"
            try:
                self._ffmpeg.cut_copy(self.filepath, dst, seg)
            except FFMpegError as e:
                # try re-encode fallback for this segment?
                try:
                    self._ffmpeg.cut_reencode(self.filepath, dst, seg)
                except Exception as e2:
                    errors.append(f"{dst.name}: {e} / {e2}")
            except Exception as e:
                errors.append(f"{dst.name}: {e}")

        progress.setValue(len(self.segments))

        if errors:
            QMessageBox.warning(
                self,
                "Exportació amb errors",
                "Alguns fragments han fallat:\n\n" + "\n".join(errors),
            )
        elif not progress.wasCanceled():
            QMessageBox.information(
                self,
                "Exportació completada",
                f"S'han exportat {len(self.segments)} fragments a:\n{out_dir}",
            )

        if not progress.wasCanceled() and not errors:
            # reveal folder?
            try:
                os.startfile(out_dir)  # type: ignore[attr-defined]
            except Exception:
                pass

    # --- Drag & drop ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith(
                    (".mp3", ".wav", ".m4a", ".ogg", ".flac")
                ):
                    event.acceptProposedAction()
                    self.wave.setStyleSheet(
                        "border: 2px dashed #4fc3f7; border-radius:8px; background:#1a2a3a;"
                    )
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.wave.setStyleSheet("border-radius:8px;")
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.wave.setStyleSheet("border-radius:8px;")
        urls = event.mimeData().urls()
        if urls:
            fp = Path(urls[0].toLocalFile())
            if fp.is_file():
                self.load_file(fp)
                event.acceptProposedAction()
                return
        event.ignore()

    # --- Zoom & marker helpers ---
    def _on_wave_split_request(self, sec: float):
        # double click on wave -> add split
        self.cursor_sec = sec
        self.player.set_position_sec(sec)
        self.wave.set_cursor(sec)
        self.slider.setValue(int(sec * 1000))
        self.split_here()

    def _on_wave_splits_changed(self, splits: list[float]):
        self.split_points = sorted(splits)
        self._rebuild_segments()
        self._refresh_list()
        self.statusBar().showMessage(
            f"Marques actualitzades — {len(self.split_points)} talls", 2000
        )

    def _on_wave_zoom_changed(self, factor: float):
        self.lbl_zoom.setText(f"{factor:.1f}x")
        # sync slider without recursion
        try:
            idx = WaveformWidget.ZOOM_LEVELS.index(factor)
        except ValueError:
            idx = 1
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(idx)
        self.zoom_slider.blockSignals(False)
        self.btn_zoom_reset.setEnabled(factor != 1.0)
        # keep cursor visible
        self._scroll_to_cursor()

    def _on_zoom_slider(self, idx: int):
        if 0 <= idx < len(WaveformWidget.ZOOM_LEVELS):
            self.wave.set_zoom(WaveformWidget.ZOOM_LEVELS[idx])

    def _zoom_fit(self):
        self.wave.reset_zoom()
        # ensure scroll at 0
        self.wave_scroll.horizontalScrollBar().setValue(0)

    def _scroll_to_cursor(self):
        if self.duration <= 0 or self.wave.zoom() <= 1.0:
            return
        # x of cursor in wave coordinates -> scroll to center it
        x = self.wave._sec_to_x(self.cursor_sec)
        viewport_w = self.wave_scroll.viewport().width()
        hbar = self.wave_scroll.horizontalScrollBar()
        target = int(x - viewport_w / 2)
        # smooth
        hbar.setValue(max(0, min(target, hbar.maximum())))

    def _on_wave_context_menu(self, pos):
        # pos is in wave widget coords
        global_pos = self.wave.mapToGlobal(pos)
        # find nearest split
        x = pos.x()
        idx = self.wave._find_split_at_x(x)
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        if idx is not None:
            sec = self.wave._splits[idx]
            act_del = menu.addAction(f"✕ Esborrar tall  {fmt_time(sec)}")
            act_del_all = menu.addAction("Netejar tots els talls")
            menu.addSeparator()
            act_play = menu.addAction("▶ Reproduir fragment anterior")
            chosen = menu.exec(global_pos)
            if chosen == act_del:
                self.split_points.remove(sec)
                self._rebuild_segments()
                self.wave.set_splits(self.split_points)
                self._refresh_list()
            elif chosen == act_del_all:
                self.clear_splits()
            elif chosen == act_play:
                # play segment before this split
                for i, seg in enumerate(self.segments):
                    if abs(seg.end - sec) < 0.01:
                        self._play_segment(max(0, i - 1) if i > 0 else 0)
                        break
        else:
            sec = self.wave._x_to_sec(x)
            act_add = menu.addAction(f"✂ Afegir tall a {fmt_time(sec)}")
            act_add.setEnabled(0.2 < sec < self.duration - 0.2)
            chosen = menu.exec(global_pos)
            if chosen == act_add:
                self.seek_to(sec)
                self.split_here()

    # --- UI state ---
    def _update_ui_state(self):
        has_file = self.filepath is not None
        has_dur = self.duration > 0
        self.btn_split.setEnabled(has_file and has_dur)
        self.btn_export.setEnabled(has_file and len(self.segments) > 0)
        self.btn_play.setEnabled(has_file)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(has_file)
        # zoom enabled only with file
        for w in (
            self.btn_zoom_in,
            self.btn_zoom_out,
            self.btn_zoom_reset,
            self.btn_zoom_fit,
            self.zoom_slider,
        ):
            w.setEnabled(has_file and has_dur)

    def _show_about(self):
        import sys

        import numpy
        import PySide6

        from mp3_cutter import __app_name__, __version__

        ff_ver = "no trobat"
        ff_path = find_ffmpeg()
        if ff_path:
            try:
                import subprocess

                cp = subprocess.run(
                    [str(ff_path), "-version"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if cp.returncode == 0:
                    ff_ver = cp.stdout.splitlines()[0].strip()[:90]
                else:
                    ff_ver = str(ff_path)
            except Exception:
                ff_ver = str(ff_path)

        try:
            import PyInstaller

            pi_ver = PyInstaller.__version__
        except Exception:
            pi_ver = "—"

        html = f"""
        <div style='font-family:Segoe UI; font-size:11pt;'>
        <h2 style='margin:0; color:#4fc3f7;'>{__app_name__} <span style='color:#90caf9; font-size:11pt;'>v{__version__}</span></h2>
        <p style='margin:4px 0 8px 0; color:#aaa;'>Obrir → Reproduir → Dividir → Exportar<br>
        <span style='font-size:9pt; color:#666;'>Stream copy amb FFmpeg — sense pèrdua de qualitat</span></p>
        <hr style='border:none; border-top:1px solid #333; margin:8px 0;'>
        <p style='margin:4px 0;'><b>Autor:</b> Josep Maria Tapia<br>
        <b>Web:</b> <a href='https://www.posicionamientowebysem.com/' style='color:#4fc3f7;'>https://www.posicionamientowebysem.com/</a></p>
        <hr style='border:none; border-top:1px solid #333; margin:8px 0;'>
        <p style='margin:4px 0; font-size:9pt; color:#bbb;'>
        <b>Python</b> {sys.version.split()[0]} &nbsp;|&nbsp;
        <b>PySide6</b> {PySide6.__version__} &nbsp;|&nbsp;
        <b>NumPy</b> {numpy.__version__}<br>
        <b>FFmpeg</b> {ff_ver}<br>
        <b>PyInstaller</b> {pi_ver}
        </p>
        <p style='margin:8px 0 0 0; font-size:8pt; color:#666;'>
        © 2026 Josep Maria Tapia — Llicència MIT<br>
        Icona i FFmpeg Essentials amb llicències pròpies
        </p>
        </div>
        """
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Sobre {__app_name__}")
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet("QDialog { background:#1e1e1e; }")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 12)
        lab = QLabel(html)
        lab.setTextFormat(Qt.TextFormat.RichText)
        lab.setWordWrap(True)
        lab.setOpenExternalLinks(True)
        lab.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        lab.setStyleSheet("color:#ddd;")
        lay.addWidget(lab)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btns.setStyleSheet(
            "QPushButton { background:#2a6cb6; color:white; border:none; border-radius:6px; padding:6px 18px; min-width:80px; }"
            "QPushButton:hover { background:#337ed1; }"
        )
        btns.accepted.connect(dlg.accept)
        lay.addWidget(btns)
        dlg.exec()

    def closeEvent(self, event):
        if self._wave_worker and self._wave_worker.isRunning():
            self._wave_worker.terminate()
            self._wave_worker.wait(800)
        self.player.stop()
        super().closeEvent(event)


# --- Styles ---
def _primary_btn() -> str:
    return """
    QPushButton {
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #2a6cb6, stop:1 #1e4a82);
        color: white; border: none; border-radius: 8px; font-weight: 700; font-size: 13px; padding: 6px 18px;
    }
    QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #337ed1, stop:1 #255a9a); }
    QPushButton:pressed { background: #1a3a62; }
    QPushButton:disabled { background: #2a2a2a; color: #666; }
    """


def _transport_btn() -> str:
    return """
    QPushButton {
        background: #262626; color: #ddd; border: 1px solid #3a3a3a; border-radius: 8px; font-weight: 600; font-size: 12px;
    }
    QPushButton:hover { background: #333; color: white; border-color: #4a4a4a; }
    QPushButton:pressed { background: #1e1e1e; }
    QPushButton:disabled { background: #222; color: #555; border-color: #2a2a2a; }
    """


def _split_btn() -> str:
    return """
    QPushButton {
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f9a825, stop:1 #ef6c00);
        color: #1a1a1a; border: none; border-radius: 8px; font-weight: 800; font-size: 13px; padding: 6px 22px;
    }
    QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffb740, stop:1 #f57c00); }
    QPushButton:pressed { background: #e65100; color: white; }
    QPushButton:disabled { background: #2a2a2a; color: #666; }
    """


def _export_btn() -> str:
    return """
    QPushButton {
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #2e7d32, stop:1 #1b5e20);
        color: white; border: none; border-radius: 10px; font-weight: 800; font-size: 14px; letter-spacing: 0.5px;
    }
    QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #388e3c, stop:1 #2e7d32); }
    QPushButton:pressed { background: #1b4d1e; }
    QPushButton:disabled { background: #2a2a2a; color: #666; }
    """


def _slider_style(small=False) -> str:
    h = "6px" if small else "8px"
    handle = "10px" if small else "14px"
    return f"""
    QSlider::groove:horizontal {{ background: #2a2a2a; height: {h}; border-radius: 4px; }}
    QSlider::sub-page:horizontal {{ background: #4fc3f7; border-radius: 4px; }}
    QSlider::add-page:horizontal {{ background: #333; border-radius: 4px; }}
    QSlider::handle:horizontal {{ background: white; width: {handle}; height: {handle}; margin: -4px 0; border-radius: 7px; }}
    QSlider::handle:horizontal:hover {{ background: #e1f5fe; }}
    """


def _list_style() -> str:
    return """
    QListWidget {
        background: #1a1a1a; border: 1px solid #2e2e2e; border-radius: 8px; padding: 4px;
    }
    QListWidget::item { border-radius: 6px; margin: 2px 0; padding: 0; }
    QListWidget::item:selected { background: #263445; }
    QListWidget::item:hover { background: #232323; }
    """
