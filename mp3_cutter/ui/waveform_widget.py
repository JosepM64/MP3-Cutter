from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget


class WaveformWidget(QWidget):
    clickedAt = Signal(float)  # seconds
    splitRequested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._peaks: np.ndarray | None = None
        self._duration: float = 0.0
        self._cursor: float = 0.0
        self._splits: list[float] = []
        self._hover_pos: float | None = None

        # colors - dark modern
        self._bg = QColor("#1e1e1e")
        self._wave_top = QColor("#4fc3f7")
        self._wave_bot = QColor("#0288d1")
        self._wave_played_top = QColor("#81d4fa")
        self._grid = QColor(255, 255, 255, 30)
        self._cursor_col = QColor("#ff3d00")
        self._split_col = QColor("#ffea00")
        self._split_bg = QColor(255, 234, 0, 40)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # --- API ---
    def set_waveform(self, peaks: np.ndarray | None, duration: float):
        self._peaks = peaks
        self._duration = max(0.0, duration)
        self.update()

    def set_cursor(self, sec: float):
        # clamp
        if self._duration > 0:
            sec = max(0.0, min(sec, self._duration))
        else:
            sec = max(0.0, sec)
        self._cursor = sec
        self.update()

    def set_splits(self, splits: list[float]):
        self._splits = sorted(max(0.0, s) for s in splits)
        self.update()

    def duration(self) -> float:
        return self._duration

    # --- helpers ---
    def _x_to_sec(self, x: float) -> float:
        w = self.width()
        if w <= 1 or self._duration <= 0:
            return 0.0
        # 8px padding left/right
        pad = 6
        usable = w - 2 * pad
        if usable <= 0:
            return 0.0
        frac = (x - pad) / usable
        frac = max(0.0, min(1.0, frac))
        return frac * self._duration

    def _sec_to_x(self, sec: float) -> float:
        w = self.width()
        pad = 6
        usable = w - 2 * pad
        if self._duration <= 0 or usable <= 0:
            return pad
        frac = sec / self._duration
        frac = max(0.0, min(1.0, frac))
        return pad + frac * usable

    # --- paint ---
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = self.width()
        h = self.height()

        # bg
        p.fillRect(self.rect(), self._bg)

        # no data -> placeholder
        if self._peaks is None or self._duration <= 0:
            p.setPen(QColor("#888"))
            f = QFont()
            f.setPointSize(11)
            p.setFont(f)
            p.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Arrossega un MP3 aquí  o  prem «Obrir MP3»",
            )
            # subtle border
            p.setPen(QPen(QColor(255, 255, 255, 20), 1, Qt.PenStyle.DashLine))
            p.drawRoundedRect(4, 4, w - 8, h - 8, 8, 8)
            return

        pad = 6
        usable_w = w - 2 * pad
        # waveform area
        wave_top = 10
        wave_h = h - 32  # reserve 22 for time ruler
        mid_y = wave_top + wave_h / 2.0

        # draw background track line
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        p.drawLine(int(pad), int(mid_y), int(pad + usable_w), int(mid_y))

        # grid ticks (time)
        self._draw_time_ruler(p, pad, usable_w, h)

        # splits background zones? draw thin verticals first behind wave
        for s in self._splits:
            x = self._sec_to_x(s)
            p.setPen(QPen(self._split_col, 1, Qt.PenStyle.DashLine))
            p.drawLine(int(x), wave_top, int(x), int(wave_top + wave_h))
            # small triangle top
            p.setBrush(QBrush(self._split_col))
            p.setPen(Qt.PenStyle.NoPen)
            tri = [  # top marker
                (x, wave_top),
                (x - 5, wave_top - 2),
                (x + 5, wave_top - 2),
            ]
            from PySide6.QtCore import QPointF
            from PySide6.QtGui import QPolygonF

            poly = QPolygonF([QPointF(*pt) for pt in tri])
            # only if within
            if wave_top >= 6:
                p.drawPolygon(poly)

        # waveform bars
        peaks = self._peaks
        n = len(peaks)
        if n == 0:
            return

        # map peaks to pixels: each peak -> one x column, but if usable_w != n, we interpolate
        # Use rect per column
        cursor_x = self._sec_to_x(self._cursor)

        # Prepare gradient for waveform
        # We will draw two passes: played vs unplayed color difference subtle
        # Instead draw per-column with color based on x < cursor_x
        bar_w = usable_w / n
        # at least 1px
        # If very many peaks vs pixels, bar_w <1 -> we still draw 1px line
        # Optimize: batch draw via QPainter rect

        # Clip to wave area
        p.setClipRect(pad, int(wave_top), int(usable_w), int(wave_h))

        # For performance, draw as vertical lines centered
        # Use pen width 1 or 2 depending on density
        if n > usable_w * 1.2:
            # dense -> draw 1px lines
            pen_played = QPen(self._wave_played_top, 1)
            pen_unplayed = QPen(self._wave_top, 1)
            pen_played.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen_unplayed.setCapStyle(Qt.PenCapStyle.RoundCap)
            for i, v in enumerate(peaks):
                x = pad + (i + 0.5) * bar_w
                amp = float(v)  # 0..1
                # slight log boost for visibility of quiet parts
                # amp = math.pow(amp, 0.85)
                amp_h = max(1.0, amp * (wave_h * 0.88))
                y1 = mid_y - amp_h / 2.0
                y2 = mid_y + amp_h / 2.0
                if x < cursor_x:
                    p.setPen(pen_played)
                else:
                    p.setPen(pen_unplayed)
                p.drawLine(int(x), int(y1), int(x), int(y2))
        else:
            # sparse -> rounded rect bars
            for i, v in enumerate(peaks):
                x = pad + i * bar_w
                amp = float(v)
                amp_h = max(2.0, amp * (wave_h * 0.88))
                y1 = mid_y - amp_h / 2.0
                rect = QRectF(x + 0.5, y1, max(1.0, bar_w - 0.8), amp_h)
                # rounded
                is_played = (x + bar_w / 2) < cursor_x
                col = self._wave_played_top if is_played else self._wave_top
                # vertical gradient darker at bottom
                grad = QLinearGradient(
                    rect.left(), rect.top(), rect.left(), rect.bottom()
                )
                grad.setColorAt(0, col.lighter(125))
                grad.setColorAt(1, col.darker(125))
                p.setBrush(QBrush(grad))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(rect, 1.5, 1.5)

        p.setClipping(False)

        # cursor
        cx = int(self._sec_to_x(self._cursor))
        p.setPen(QPen(self._cursor_col, 2))
        p.drawLine(cx, int(wave_top - 4), cx, int(wave_top + wave_h + 2))
        # cursor circle
        p.setBrush(QBrush(self._cursor_col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(cx - 5), int(wave_top + wave_h + 2 - 5), 10, 10)
        # inner white dot
        p.setBrush(QBrush(QColor("white")))
        p.drawEllipse(int(cx - 2), int(wave_top + wave_h + 2 - 2), 4, 4)

        # hover indicator (subtle)
        if self._hover_pos is not None:
            hx = int(self._sec_to_x(self._hover_pos))
            p.setPen(QPen(QColor(255, 255, 255, 60), 1, Qt.PenStyle.DotLine))
            p.drawLine(hx, int(wave_top), hx, int(wave_top + wave_h))

        # border
        p.setPen(QPen(QColor(255, 255, 255, 14), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(1, 1, w - 2, h - 2, 8, 8)

    def _draw_time_ruler(self, p: QPainter, pad: int, usable_w: float, h: int):
        if self._duration <= 0:
            return
        # choose 4-6 ticks
        dur = self._duration
        # target ~5 ticks
        ideal_step = dur / 5.0
        # snap to nice numbers: 1,2,5,10,15,30,60,120...
        nice = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900]
        step = nice[-1]
        for n in nice:
            if n >= ideal_step:
                step = n
                break
        if dur > 3600:
            step = max(step, 300)

        p.setPen(QColor("#aaa"))
        f = QFont()
        f.setPointSize(8)
        p.setFont(f)

        y = h - 6
        t = 0.0
        while t <= dur + 0.001:
            x = self._sec_to_x(t)
            # tick
            p.setPen(QPen(self._grid, 1))
            p.drawLine(int(x), h - 22, int(x), h - 18)
            # label
            p.setPen(QColor("#bbb"))
            label = self._fmt_tick(t)
            # avoid overflow at right edge
            tw = p.fontMetrics().horizontalAdvance(label)
            lx = int(x - tw / 2)
            lx = max(pad, min(lx, int(pad + usable_w - tw)))
            p.drawText(lx, y, label)
            t += step
            if t > dur and abs(t - step - dur) > 0.5:
                # ensure last tick at dur
                if dur - (t - step) > step * 0.4:
                    x2 = self._sec_to_x(dur)
                    p.setPen(QPen(self._grid, 1))
                    p.drawLine(int(x2), h - 22, int(x2), h - 18)
                    p.setPen(QColor("#bbb"))
                    label2 = self._fmt_tick(dur)
                    tw2 = p.fontMetrics().horizontalAdvance(label2)
                    lx2 = int(x2 - tw2 / 2)
                    lx2 = max(pad, min(lx2, int(pad + usable_w - tw2)))
                    p.drawText(lx2, y, label2)
                break

    def _fmt_tick(self, sec: float) -> str:
        m = int(sec) // 60
        s = int(sec) % 60
        if self._duration >= 3600:
            h = int(sec) // 3600
            m = (int(sec) % 3600) // 60
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    # --- events ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            sec = self._x_to_sec(event.position().x())
            self.clickedAt.emit(sec)
            self.set_cursor(sec)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._duration > 0:
            sec = self._x_to_sec(event.position().x())
            self._hover_pos = sec
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_pos = None
        self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        # Space = play/pause handled by parent, but we emit split on S?
        if event.key() == Qt.Key.Key_S or event.key() == Qt.Key.Key_Space:
            # let main handle
            event.ignore()
        super().keyPressEvent(event)

    def sizeHint(self):
        return QSize(800, 160)
