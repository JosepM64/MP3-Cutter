from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget


class WaveformWidget(QWidget):
    clickedAt = Signal(float)  # seconds
    splitRequested = Signal(float)
    splitsChanged = Signal(list)  # list[float] when marker dragged
    zoomChanged = Signal(float)

    ZOOM_LEVELS = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0]

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

        # zoom
        self._zoom: float = 1.0
        self._base_width: int = 900  # width at 1x
        self._dragging_idx: int | None = None
        self._drag_threshold_px = 7

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

    def zoom(self) -> float:
        return self._zoom

    def set_zoom(self, factor: float):
        # clamp to levels
        factor = max(0.5, min(8.0, factor))
        # snap to nearest level
        # find closest
        closest = min(self.ZOOM_LEVELS, key=lambda v: abs(v - factor))
        if closest == self._zoom:
            return
        self._zoom = closest
        # update geometry for scroll area
        self._update_geometry()
        self.zoomChanged.emit(self._zoom)
        self.update()

    def zoom_in(self):
        idx = (
            self.ZOOM_LEVELS.index(self._zoom) if self._zoom in self.ZOOM_LEVELS else 1
        )
        if idx + 1 < len(self.ZOOM_LEVELS):
            self.set_zoom(self.ZOOM_LEVELS[idx + 1])

    def zoom_out(self):
        idx = (
            self.ZOOM_LEVELS.index(self._zoom) if self._zoom in self.ZOOM_LEVELS else 1
        )
        if idx - 1 >= 0:
            self.set_zoom(self.ZOOM_LEVELS[idx - 1])

    def reset_zoom(self):
        self.set_zoom(1.0)

    def _update_geometry(self):
        w = int(self._base_width * self._zoom)
        # keep height, only width scales for horizontal zoom
        self.setMinimumWidth(w)
        self.resize(w, self.height())
        self.updateGeometry()

    # --- helpers ---
    def _x_to_sec(self, x: float) -> float:
        w = self.width()
        if w <= 1 or self._duration <= 0:
            return 0.0
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

    def _find_split_at_x(self, x: float) -> int | None:
        for i, s in enumerate(self._splits):
            sx = self._sec_to_x(s)
            if abs(sx - x) <= self._drag_threshold_px:
                return i
        return None

    # --- paint ---
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = self.width()
        h = self.height()

        p.fillRect(self.rect(), self._bg)

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
            p.setPen(QPen(QColor(255, 255, 255, 20), 1, Qt.PenStyle.DashLine))
            p.drawRoundedRect(4, 4, w - 8, h - 8, 8, 8)
            return

        pad = 6
        usable_w = w - 2 * pad
        wave_top = 10
        wave_h = h - 32
        mid_y = wave_top + wave_h / 2.0

        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        p.drawLine(int(pad), int(mid_y), int(pad + usable_w), int(mid_y))

        self._draw_time_ruler(p, pad, usable_w, h)

        # draw segment zones with subtle alternating bg
        pts = [0.0] + self._splits + [self._duration]
        pts = sorted(pts)
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            x1 = self._sec_to_x(a)
            x2 = self._sec_to_x(b)
            # alternate faint tint for readability when zoomed
            if i % 2 == 1:
                p.fillRect(
                    int(x1),
                    int(wave_top),
                    int(x2 - x1),
                    int(wave_h),
                    QColor(255, 255, 255, 8),
                )
            # segment number centered
            if (x2 - x1) > 40:
                cx_seg = (x1 + x2) / 2
                p.setPen(QColor(255, 255, 255, 55))
                f = QFont()
                f.setPointSize(8)
                f.setBold(True)
                p.setFont(f)
                label = f"{i + 1}"
                tw = p.fontMetrics().horizontalAdvance(label)
                p.drawText(int(cx_seg - tw / 2), int(mid_y - 2), label)

        # splits
        for idx, s in enumerate(self._splits):
            x = self._sec_to_x(s)
            is_dragging = self._dragging_idx == idx
            col = QColor("#ffab00") if is_dragging else self._split_col
            # vertical line
            pen_style = Qt.PenStyle.SolidLine if is_dragging else Qt.PenStyle.DashLine
            p.setPen(QPen(col, 2 if is_dragging else 1, pen_style))
            p.drawLine(int(x), wave_top, int(x), int(wave_top + wave_h))

            # marker head (top)
            p.setBrush(QBrush(col))
            p.setPen(Qt.PenStyle.NoPen)
            from PySide6.QtCore import QPointF
            from PySide6.QtGui import QPolygonF

            tri = [(x, wave_top), (x - 7, wave_top - 9), (x + 7, wave_top - 9)]
            poly = QPolygonF([QPointF(*pt) for pt in tri])
            if wave_top >= 9:
                p.drawPolygon(poly)

            # time label for split
            fmt = self._fmt_time_label(s)
            f2 = QFont("Consolas", 7)
            f2.setBold(True)
            p.setFont(f2)
            fm = p.fontMetrics()
            tw = fm.horizontalAdvance(fmt)
            th = fm.height()
            bx = int(x - tw / 2 - 4)
            by = int(wave_top - 11 - th)
            # keep inside widget
            bx = max(2, min(bx, w - tw - 8))
            # bg pill
            p.setBrush(QBrush(QColor(30, 30, 30, 220)))
            p.setPen(QPen(col, 1))
            p.drawRoundedRect(bx, by, tw + 8, th + 2, 4, 4)
            p.setPen(QColor("#ffe082") if is_dragging else QColor("#fff59d"))
            p.drawText(bx + 4, by + th - 1, fmt)

        # waveform bars
        peaks = self._peaks
        n = len(peaks)
        if n == 0:
            return

        cursor_x = self._sec_to_x(self._cursor)
        bar_w = usable_w / n

        p.setClipRect(pad, int(wave_top), int(usable_w), int(wave_h))

        if n > usable_w * 1.2:
            pen_played = QPen(self._wave_played_top, 1)
            pen_unplayed = QPen(self._wave_top, 1)
            pen_played.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen_unplayed.setCapStyle(Qt.PenCapStyle.RoundCap)
            for i, v in enumerate(peaks):
                x = pad + (i + 0.5) * bar_w
                amp = float(v)
                amp_h = max(1.0, amp * (wave_h * 0.88))
                y1 = mid_y - amp_h / 2.0
                y2 = mid_y + amp_h / 2.0
                if x < cursor_x:
                    p.setPen(pen_played)
                else:
                    p.setPen(pen_unplayed)
                p.drawLine(int(x), int(y1), int(x), int(y2))
        else:
            for i, v in enumerate(peaks):
                x = pad + i * bar_w
                amp = float(v)
                amp_h = max(2.0, amp * (wave_h * 0.88))
                y1 = mid_y - amp_h / 2.0
                rect = QRectF(x + 0.5, y1, max(1.0, bar_w - 0.8), amp_h)
                is_played = (x + bar_w / 2) < cursor_x
                col = self._wave_played_top if is_played else self._wave_top
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
        p.setBrush(QBrush(self._cursor_col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(cx - 5), int(wave_top + wave_h + 2 - 5), 10, 10)
        p.setBrush(QBrush(QColor("white")))
        p.drawEllipse(int(cx - 2), int(wave_top + wave_h + 2 - 2), 4, 4)

        # hover
        if self._hover_pos is not None and self._dragging_idx is None:
            hx = int(self._sec_to_x(self._hover_pos))
            p.setPen(QPen(QColor(255, 255, 255, 60), 1, Qt.PenStyle.DotLine))
            p.drawLine(hx, int(wave_top), hx, int(wave_top + wave_h))

        # border
        p.setPen(QPen(QColor(255, 255, 255, 14), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(1, 1, w - 2, h - 2, 8, 8)

        # zoom badge bottom-right
        if self._zoom != 1.0:
            p.setPen(QColor("#90caf9"))
            f = QFont()
            f.setPointSize(7)
            f.setBold(True)
            p.setFont(f)
            txt = f"ZOOM {self._zoom:.1f}x"
            tw = p.fontMetrics().horizontalAdvance(txt) + 10
            p.setBrush(QBrush(QColor(20, 30, 50, 180)))
            p.setPen(QPen(QColor("#90caf9"), 1))
            p.drawRoundedRect(w - tw - 8, h - 18, tw, 12, 6, 6)
            p.setPen(QColor("#e1f5fe"))
            p.drawText(int(w - tw - 3), int(h - 9), txt)

    def _draw_time_ruler(self, p: QPainter, pad: int, usable_w: float, h: int):
        if self._duration <= 0:
            return
        dur = self._duration
        # adapt step to zoom: when zoomed, show denser ticks
        visible_dur = dur / self._zoom if self._zoom > 0 else dur
        ideal_step = visible_dur / 6.0
        nice = [0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900]
        step = nice[-1]
        for n in nice:
            if n >= ideal_step:
                step = n
                break
        if dur > 3600:
            step = max(step, 300)
        # when very zoomed (6x-8x) allow 0.5s steps
        if self._zoom >= 6:
            step = min(step, 1.0)

        p.setPen(QColor("#aaa"))
        f = QFont()
        f.setPointSize(8)
        p.setFont(f)

        y = h - 6
        t = 0.0
        # avoid drawing too many ticks when zoomed out + long file
        max_ticks = 30
        count = 0
        while t <= dur + 0.001 and count < max_ticks:
            x = self._sec_to_x(t)
            # only draw if visible in viewport (widget coords, but scroll may hide)
            # draw anyway - clipping will handle
            p.setPen(QPen(self._grid, 1))
            p.drawLine(int(x), h - 22, int(x), h - 18)
            p.setPen(QColor("#bbb"))
            label = self._fmt_tick(t)
            tw = p.fontMetrics().horizontalAdvance(label)
            lx = int(x - tw / 2)
            lx = max(pad, min(lx, int(pad + usable_w - tw)))
            # avoid overlapping labels when dense: skip if too close to previous?
            p.drawText(lx, y, label)
            t += step
            count += 1
            if t > dur and abs(t - step - dur) > 0.5:
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

    def _fmt_time_label(self, sec: float) -> str:
        m = int(sec) // 60
        s = int(sec) % 60
        ms = int(round((sec - int(sec)) * 1000))
        if ms == 1000:
            ms = 0
            s += 1
            if s == 60:
                s = 0
                m += 1
        if self._duration >= 3600:
            h = m // 60
            m = m % 60
            return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
        return f"{m:02d}:{s:02d}.{ms:03d}"

    # --- events ---
    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            x = event.position().x()
            # check if click near split marker -> start drag
            idx = self._find_split_at_x(x)
            if idx is not None:
                self._dragging_idx = idx
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                self.update()
                event.accept()
                return
            # double click -> add split
            sec = self._x_to_sec(x)
            self.clickedAt.emit(sec)
            self.set_cursor(sec)
        elif event.button() == Qt.MouseButton.RightButton:
            # right click near marker -> request delete? emit for context menu?
            x = event.position().x()
            idx = self._find_split_at_x(x)
            if idx is not None:
                # emit that marker clicked
                self._dragging_idx = None
                # parent will handle via custom context?
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        x = event.position().x()
        if self._dragging_idx is not None:
            sec = self._x_to_sec(x)
            # clamp and avoid extremes
            if self._duration > 0:
                sec = max(0.15, min(sec, self._duration - 0.15))
                # avoid overlap with other splits (min 0.12s)
                for i, s in enumerate(self._splits):
                    if i == self._dragging_idx:
                        continue
                    if abs(s - sec) < 0.12:
                        # snap away? just don't update
                        return
                self._splits[self._dragging_idx] = round(sec, 3)
                self._splits.sort()
                # update dragging idx after sort (find new position of dragged value)
                # keep dragged marker highlighted
                self._dragging_idx = self._splits.index(round(sec, 3))
                self.splitsChanged.emit(self._splits.copy())
                self.update()
            event.accept()
            return

        # hover handling + cursor change near marker
        if self._duration > 0:
            idx = self._find_split_at_x(x)
            if idx is not None:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                self.setToolTip(
                    f"Arrossega per moure el tall {self._fmt_time_label(self._splits[idx])} (clic dret per esborrar)"
                )
            else:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                sec = self._x_to_sec(x)
                self.setToolTip(f"{self._fmt_time_label(sec)} — Ctrl+Roda per zoom")
            sec = self._x_to_sec(x)
            self._hover_pos = sec
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if (
            self._dragging_idx is not None
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._dragging_idx = None
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            sec = self._x_to_sec(event.position().x())
            if 0.2 < sec < self._duration - 0.2:
                self.splitRequested.emit(round(sec, 3))
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def leaveEvent(self, event):
        self._hover_pos = None
        self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_S, Qt.Key.Key_Space):
            event.ignore()
        super().keyPressEvent(event)

    def sizeHint(self):
        return QSize(int(self._base_width * self._zoom), 160)

    def minimumSizeHint(self):
        return QSize(int(300 * self._zoom), 140)
