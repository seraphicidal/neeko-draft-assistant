"""The painted parts of the interface.

Qt's stock controls are styled in `theme.py`; everything with real shape --
switches, the slider, the status pill, the champion showcase, Neeko's avatar --
is drawn here so the app does not look like a form.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QMovie,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui import theme


def colour(value: str, alpha: float = 1.0) -> QColor:
    result = QColor(value)
    if alpha < 1.0:
        result.setAlphaF(alpha)
    return result


def blend(start: QColor, end: QColor, amount: float) -> QColor:
    amount = max(0.0, min(1.0, amount))
    return QColor(
        int(start.red() + (end.red() - start.red()) * amount),
        int(start.green() + (end.green() - start.green()) * amount),
        int(start.blue() + (end.blue() - start.blue()) * amount),
    )


def label(text: str = "", kind: str = "body", parent: QWidget | None = None) -> QLabel:
    widget = QLabel(text, parent)
    widget.setObjectName(kind)
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    return widget


def caption(text: str) -> QLabel:
    return label(text.upper(), "caption")


class Hairline(QWidget):
    """A one pixel separator -- grouping without another box."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0.0, colour(theme.LINE, 0.0))
        gradient.setColorAt(0.15, colour(theme.LINE, 1.0))
        gradient.setColorAt(0.85, colour(theme.LINE, 1.0))
        gradient.setColorAt(1.0, colour(theme.LINE, 0.0))
        painter.fillRect(self.rect(), gradient)


class Switch(QAbstractButton):
    """Compact toggle. Orange when on, quiet navy when off."""

    def __init__(self, parent: QWidget | None = None, width: int = 42) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._height = 22
        self.setFixedSize(width, self._height)
        self._offset = 0.0
        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._slide)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _slide(self, checked: bool) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._offset)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def setChecked(self, checked: bool) -> None:  # noqa: N802 - Qt naming
        super().setChecked(checked)
        self._offset = 1.0 if checked else 0.0
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt naming
        return self.size()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        track = blend(colour(theme.NAVY_700), colour(theme.ORANGE), self._offset)
        painter.setBrush(track)
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self._height), 11, 11)

        if self._offset < 0.5:
            painter.setPen(QPen(colour(theme.LINE), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                QRectF(0.5, 0.5, self.width() - 1, self._height - 1), 11, 11
            )
            painter.setPen(Qt.PenStyle.NoPen)

        travel = self.width() - self._height
        knob = QRectF(3 + travel * self._offset, 3, self._height - 6, self._height - 6)
        painter.setBrush(colour(theme.CREAM if self._offset > 0.5 else theme.MUTED))
        painter.drawEllipse(knob)


class SwitchRow(QWidget):
    """A labelled switch with its state spelled out -- no card around it."""

    toggled = Signal(bool)

    def __init__(
        self,
        text: str,
        checked: bool = False,
        note: str = "",
        compact: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        self.title = label(text, "caption" if compact else "body")
        titles.addWidget(self.title)
        self.note = None
        if note:
            self.note = label(note, "small")
            self.note.setWordWrap(True)
            titles.addWidget(self.note)
        layout.addLayout(titles, 1)

        self.state = label("OFF", "small")
        self.state.setMinimumWidth(26)
        self.state.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.state)

        self.switch = Switch(width=38 if compact else 42)
        self.switch.setChecked(checked)
        self.switch.toggled.connect(self._on_toggled)
        layout.addWidget(self.switch)

        self._render(checked)

    def _on_toggled(self, value: bool) -> None:
        self._render(value)
        self.toggled.emit(value)

    def _render(self, value: bool) -> None:
        self.state.setText("ON" if value else "OFF")
        self.state.setStyleSheet(
            f"color: {theme.ORANGE if value else theme.DIM}; font-size: 11px; font-weight: 700;"
        )

    def setChecked(self, value: bool) -> None:  # noqa: N802 - Qt naming
        self.switch.blockSignals(True)
        self.switch.setChecked(value)
        self.switch.blockSignals(False)
        self._render(value)

    def isChecked(self) -> bool:  # noqa: N802 - Qt naming
        return self.switch.isChecked()

    def setEnabled(self, value: bool) -> None:  # noqa: N802 - Qt naming
        super().setEnabled(value)
        self.switch.setEnabled(value)


class Slider(QWidget):
    """A flat slider: orange fill, cream knob, snapping to fixed steps."""

    valueChanged = Signal(float)

    HEIGHT = 26
    KNOB = 8
    PAD = 9

    def __init__(
        self,
        value: float = 0.0,
        maximum: float = 10.0,
        step: float = 0.5,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._value = value
        self._maximum = maximum
        self._step = step
        self._hover = False
        self.setMouseTracking(True)

    def value(self) -> float:
        return self._value

    def setValue(self, value: float) -> None:  # noqa: N802 - Qt naming
        value = max(0.0, min(self._maximum, value))
        if value != self._value:
            self._value = value
            self.update()

    def enterEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        self._hover = True
        self.update()

    def leaveEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        self._hover = False
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self._seek(event.position().x())

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._seek(event.position().x())

    def _seek(self, x: float) -> None:
        span = max(1, self.width() - 2 * self.PAD)
        ratio = min(1.0, max(0.0, (x - self.PAD) / span))
        value = round(ratio * self._maximum / self._step) * self._step
        if value != self._value:
            self._value = value
            self.update()
            self.valueChanged.emit(value)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        middle = self.HEIGHT / 2
        left, right = self.PAD, max(self.PAD + 1, self.width() - self.PAD)

        painter.setBrush(colour(theme.NAVY_700))
        painter.drawRoundedRect(QRectF(left, middle - 2.5, right - left, 5), 3, 3)

        position = left + (right - left) * (self._value / self._maximum)
        if position > left:
            gradient = QLinearGradient(left, 0, position, 0)
            gradient.setColorAt(0.0, colour(theme.ORANGE_DEEP))
            gradient.setColorAt(1.0, colour(theme.ORANGE))
            painter.setBrush(gradient)
            painter.drawRoundedRect(QRectF(left, middle - 2.5, position - left, 5), 3, 3)

        if self._hover:
            painter.setBrush(colour(theme.ORANGE, 0.22))
            painter.drawEllipse(QRectF(position - 13, middle - 13, 26, 26))

        painter.setBrush(colour(theme.CREAM))
        painter.drawEllipse(
            QRectF(position - self.KNOB, middle - self.KNOB, self.KNOB * 2, self.KNOB * 2)
        )
        painter.setPen(QPen(colour(theme.ORANGE), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(
            QRectF(position - self.KNOB, middle - self.KNOB, self.KNOB * 2, self.KNOB * 2)
        )


class StatePill(QWidget):
    """The live state, as a tinted chip with a breathing dot."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(28)
        self._text = "Waiting for League"
        self._colour = colour(theme.DIM)
        self._pulse = 0.0
        self._animation = QPropertyAnimation(self, b"pulse", self)
        self._animation.setDuration(1800)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._animation.setLoopCount(-1)
        self._animation.start()

    def _get_pulse(self) -> float:
        return self._pulse

    def _set_pulse(self, value: float) -> None:
        self._pulse = value
        self.update()

    pulse = Property(float, _get_pulse, _set_pulse)

    def set_state(self, text: str, tint: str) -> None:
        self._text = text
        self._colour = colour(tint)
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt naming
        metrics = self.fontMetrics()
        return QSize(metrics.horizontalAdvance(self._text) + 46, 28)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(QColor(self._colour.red(), self._colour.green(), self._colour.blue(), 34))
        painter.drawRoundedRect(QRectF(self.rect()), 14, 14)

        swell = 1.0 - abs(self._pulse * 2 - 1)
        halo = QColor(self._colour)
        halo.setAlphaF(0.20 + 0.30 * swell)
        painter.setBrush(halo)
        painter.drawEllipse(QRectF(11, self.height() / 2 - 6, 12, 12))
        painter.setBrush(self._colour)
        painter.drawEllipse(QRectF(14, self.height() / 2 - 3, 6, 6))

        painter.setPen(colour(theme.TEXT))
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            QRect(28, 0, self.width() - 38, self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._text,
        )


class TimerBar(QWidget):
    """The draft countdown."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(5)
        self._fraction = 0.0

    def set_fraction(self, value: float) -> None:
        value = max(0.0, min(1.0, value))
        if abs(value - self._fraction) > 0.004:
            self._fraction = value
            self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour(theme.NAVY_700))
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 2.5, 2.5)

        if self._fraction <= 0:
            return
        end = colour(theme.SKY_BRIGHT if self._fraction > 0.35 else theme.ORANGE)
        gradient = QLinearGradient(0, 0, self.width() * self._fraction, 0)
        gradient.setColorAt(0.0, colour(theme.CYAN if self._fraction > 0.35 else theme.ORANGE_DEEP))
        gradient.setColorAt(1.0, end)
        painter.setBrush(gradient)
        painter.drawRoundedRect(
            QRectF(0, 0, self.width() * self._fraction, self.height()), 2.5, 2.5
        )


class Avatar(QWidget):
    """Neeko herself: a round portrait whose ring answers to her mood."""

    clicked = Signal()

    def __init__(self, path: Path | None, size: int = 64, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size + 10, size + 10)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._size = size
        self._movie: QMovie | None = None
        self._pixmap: QPixmap | None = None
        self._ring = colour(theme.SKY)
        self._energy = 0.0
        self._pulse = 0.0

        if path and path.exists():
            if path.suffix.lower() == ".gif":
                self._movie = QMovie(str(path))
                self._movie.frameChanged.connect(self.update)
                self._movie.start()
            else:
                self._pixmap = QPixmap(str(path))

        self._animation = QPropertyAnimation(self, b"pulse", self)
        self._animation.setDuration(2200)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._animation.setLoopCount(-1)
        self._animation.start()

    def _get_pulse(self) -> float:
        return self._pulse

    def _set_pulse(self, value: float) -> None:
        self._pulse = value
        self.update()

    pulse = Property(float, _get_pulse, _set_pulse)

    def set_mood(self, ring: str, energy: float) -> None:
        self._ring = colour(ring)
        self._energy = max(0.0, min(1.0, energy))
        self.update()

    def set_animated(self, playing: bool) -> None:
        """Pausing the GIF while hidden keeps the app cheap in the tray."""
        if self._movie is None:
            return
        self._movie.setPaused(not playing)

    def mousePressEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        self.clicked.emit()

    def _frame(self) -> QPixmap | None:
        if self._movie is not None:
            frame = self._movie.currentPixmap()
            return frame if not frame.isNull() else None
        return self._pixmap

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        centre = QRectF(5, 5, self._size, self._size)
        swell = 1.0 - abs(self._pulse * 2 - 1)

        if self._energy > 0.05:
            glow = QColor(self._ring)
            glow.setAlphaF(0.10 + 0.28 * self._energy * swell)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            spread = 2 + 4 * self._energy * swell
            painter.drawEllipse(centre.adjusted(-spread, -spread, spread, spread))

        clip = QPainterPath()
        clip.addEllipse(centre)
        painter.save()
        painter.setClipPath(clip)
        painter.fillRect(self.rect(), colour(theme.NAVY_700))
        frame = self._frame()
        if frame is not None:
            scaled = frame.scaled(
                centre.size().toSize(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(
                int(centre.x() - (scaled.width() - centre.width()) / 2),
                int(centre.y() - (scaled.height() - centre.height()) / 2),
                scaled,
            )
        painter.restore()

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(self._ring, 2.4))
        painter.drawEllipse(centre)


class SpeechLine(QWidget):
    """What Neeko is saying, cross-faded when it changes."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.text = label("", "sky")
        self.text.setWordWrap(True)
        layout.addWidget(self.text)

        self._effect = QGraphicsOpacityEffect(self.text)
        self._effect.setOpacity(1.0)
        self.text.setGraphicsEffect(self._effect)
        self._fade = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade.setDuration(220)
        self._current = ""

    def say(self, line: str, tint: str, animate: bool = True) -> None:
        if line == self._current:
            return
        self._current = line
        self.text.setText(line)
        self.text.setStyleSheet(f"color: {tint}; font-size: 12px; font-weight: 600;")
        if not animate:
            return
        self._fade.stop()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()


def magnifier_icon(tint: str = theme.MUTED, size: int = 16) -> QIcon:
    """A small search glyph, drawn rather than shipped as a file."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(colour(tint), 1.7))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QRectF(2.5, 2.5, 8.5, 8.5))
    painter.drawLine(QPoint(11, 11), QPoint(14, 14))
    painter.end()
    return QIcon(pixmap)


class WindowButton(QAbstractButton):
    """Minimise and close, drawn rather than typed as glyphs."""

    MINIMISE = "minimise"
    CLOSE = "close"

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(30, 26)
        self._hover = False

    def enterEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        self._hover = True
        self.update()

    def leaveEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        self._hover = False
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._hover:
            painter.setPen(Qt.PenStyle.NoPen)
            tint = theme.DANGER if self.kind == self.CLOSE else theme.SKY
            painter.setBrush(colour(tint, 0.22))
            painter.drawRoundedRect(QRectF(self.rect()), 7, 7)

        stroke = colour(theme.CREAM if self._hover else theme.MUTED)
        painter.setPen(QPen(stroke, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        middle_x, middle_y = self.width() / 2, self.height() / 2
        if self.kind == self.MINIMISE:
            painter.drawLine(QPoint(int(middle_x - 5), int(middle_y)),
                             QPoint(int(middle_x + 5), int(middle_y)))
        else:
            painter.drawLine(QPoint(int(middle_x - 5), int(middle_y - 5)),
                             QPoint(int(middle_x + 5), int(middle_y + 5)))
            painter.drawLine(QPoint(int(middle_x + 5), int(middle_y - 5)),
                             QPoint(int(middle_x - 5), int(middle_y + 5)))


class ChampionShowcase(QWidget):
    """The centrepiece: splash art, the champion, and the two draft switches."""

    declare_toggled = Signal(bool)
    lock_toggled = Signal(bool)

    HEIGHT = 178

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT)
        self._splash: QPixmap | None = None
        self._icon: QPixmap | None = None
        self._has_champion = False
        self._highlight = False
        self._flower = self._load(theme_flower())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(0)

        layout.addWidget(caption("Your champion"))
        layout.addSpacing(8)

        identity = QHBoxLayout()
        identity.setSpacing(12)
        self.icon_slot = QWidget()
        self.icon_slot.setFixedSize(54, 54)
        identity.addWidget(self.icon_slot)

        names = QVBoxLayout()
        names.setSpacing(0)
        names.addStretch(1)
        self.name = label("Nobody yet", "display")
        self.title = label("pick someone below", "muted")
        names.addWidget(self.name)
        names.addWidget(self.title)
        names.addStretch(1)
        identity.addLayout(names, 1)
        layout.addLayout(identity)

        layout.addStretch(1)

        switches = QHBoxLayout()
        switches.setSpacing(18)
        self.declare_row = SwitchRow("Auto declare", True, compact=True)
        self.declare_row.toggled.connect(self.declare_toggled.emit)
        self.lock_row = SwitchRow("Auto lock in", False, compact=True)
        self.lock_row.toggled.connect(self.lock_toggled.emit)
        switches.addWidget(self.declare_row, 1)
        switches.addWidget(self.lock_row, 1)
        layout.addLayout(switches)

    @staticmethod
    def _load(path: Path | None) -> QPixmap | None:
        if path is None or not Path(path).exists():
            return None
        pixmap = QPixmap(str(path))
        return None if pixmap.isNull() else pixmap

    # -- content ----------------------------------------------------------

    def set_champion(self, name: str, title: str) -> None:
        self._has_champion = bool(name)
        self.name.setText(name or "Nobody yet")
        self.name.setStyleSheet(
            f"color: {theme.CREAM if name else theme.MUTED}; font-size: 19px; font-weight: 700;"
        )
        self.title.setText(title or ("pick someone below" if not name else ""))
        if not name:
            self._splash = None
            self._icon = None
        self.update()

    def set_icon(self, pixmap: QPixmap | None) -> None:
        self._icon = pixmap
        self.update()

    def set_splash(self, pixmap: QPixmap | None) -> None:
        self._splash = pixmap
        self.update()

    def set_highlight(self, on: bool) -> None:
        if on != self._highlight:
            self._highlight = on
            self.update()

    def set_states(self, declare: bool, lock: bool) -> None:
        self.declare_row.setChecked(declare)
        self.lock_row.setChecked(lock)

    # -- painting ---------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        body = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        clip = QPainterPath()
        clip.addRoundedRect(body, theme.PANEL_RADIUS, theme.PANEL_RADIUS)

        painter.save()
        painter.setClipPath(clip)
        painter.fillRect(self.rect(), colour(theme.NAVY_800))

        if self._splash is not None:
            scaled = self._splash.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            # Splash art is centred on the face; bias upward so it is in frame.
            painter.drawPixmap(
                int((self.width() - scaled.width()) / 2),
                int((self.height() - scaled.height()) * 0.32),
                scaled,
            )
            wash = QLinearGradient(0, 0, self.width(), 0)
            wash.setColorAt(0.0, colour(theme.NAVY_800, 0.97))
            wash.setColorAt(0.55, colour(theme.NAVY_800, 0.72))
            wash.setColorAt(1.0, colour(theme.NAVY_800, 0.30))
            painter.fillRect(self.rect(), wash)

            base = QLinearGradient(0, self.height() * 0.45, 0, self.height())
            base.setColorAt(0.0, colour(theme.NAVY_800, 0.0))
            base.setColorAt(1.0, colour(theme.NAVY_800, 0.94))
            painter.fillRect(self.rect(), base)
        elif self._flower is not None:
            painter.setOpacity(0.07)
            side = int(self.height() * 1.15)
            painter.drawPixmap(
                self.width() - side + 30,
                -20,
                self._flower.scaled(
                    side, side,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ),
            )
            painter.setOpacity(1.0)
        painter.restore()

        # The icon sits in the slot the layout reserved for it.
        slot = self.icon_slot.geometry()
        target = QRectF(slot)
        icon_clip = QPainterPath()
        icon_clip.addRoundedRect(target, 14, 14)
        painter.save()
        painter.setClipPath(icon_clip)
        painter.fillRect(target, colour(theme.NAVY_700))
        if self._icon is not None:
            scaled = self._icon.scaled(
                target.size().toSize(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(int(target.x()), int(target.y()), scaled)
        elif self._flower is not None:
            painter.setOpacity(0.5)
            side = int(target.width() * 0.6)
            painter.drawPixmap(
                int(target.x() + (target.width() - side) / 2),
                int(target.y() + (target.height() - side) / 2),
                self._flower.scaled(
                    side, side,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ),
            )
            painter.setOpacity(1.0)
        painter.restore()

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(colour(theme.ORANGE, 0.85 if self._has_champion else 0.35), 1.6))
        painter.drawRoundedRect(target, 14, 14)

        if self._highlight:
            edge = colour(theme.ORANGE)
            width = 1.8
        elif self._has_champion:
            edge = colour(theme.ORANGE, 0.40)
            width = 1.2
        else:
            edge = colour(theme.LINE)
            width = 1.0
        painter.setPen(QPen(edge, width))
        painter.drawRoundedRect(body, theme.PANEL_RADIUS, theme.PANEL_RADIUS)


class MiniChampion(QWidget):
    """A small champion chip, used for the backup pick."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(30, 30)
        self._icon: QPixmap | None = None
        self._letter = ""
        self._tint = theme.SKY

    def set_champion(self, name: str, tint: str = theme.SKY) -> None:
        self._letter = (name or "")[:1].upper()
        self._tint = tint
        if not name:
            self._icon = None
        self.update()

    def set_icon(self, pixmap: QPixmap | None) -> None:
        self._icon = pixmap
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        body = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        clip = QPainterPath()
        clip.addRoundedRect(body, 9, 9)
        painter.setClipPath(clip)
        painter.fillRect(self.rect(), colour(theme.NAVY_700))

        if self._icon is not None:
            scaled = self._icon.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(0, 0, scaled)
        elif self._letter:
            painter.setPen(colour(self._tint))
            font = QFont(theme.FONT, 11)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._letter)

        painter.setClipping(False)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(colour(self._tint, 0.7), 1.2))
        painter.drawRoundedRect(body, 9, 9)


class ChampionSearch(QWidget):
    """Search field plus a compact result list that only shows while typing."""

    chosen = Signal(int, str)

    def __init__(self, catalog, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.catalog = catalog

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.field = QLineEdit()
        self.field.setPlaceholderText(placeholder)
        self.field.addAction(magnifier_icon(), QLineEdit.ActionPosition.LeadingPosition)
        self.field.setClearButtonEnabled(True)
        self.field.textChanged.connect(self._on_typed)
        self.field.returnPressed.connect(self._on_return)
        layout.addWidget(self.field)

        self.results = QListWidget()
        self.results.setMaximumHeight(168)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results.hide()
        self.results.itemClicked.connect(self._on_activated)
        self.results.itemActivated.connect(self._on_activated)
        layout.addWidget(self.results)

    def _on_typed(self, text: str) -> None:
        matches = self.catalog.search(text)
        self.results.clear()
        if not matches:
            self.results.hide()
            return
        for champion in matches:
            item = QListWidgetItem(f"{champion.name}   ·   {champion.title}".rstrip(" ·"))
            item.setData(Qt.ItemDataRole.UserRole, champion.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, champion.name)
            self.results.addItem(item)
        self.results.setCurrentRow(0)
        self.results.show()

    def _on_return(self) -> None:
        if self.results.isVisible() and self.results.currentItem():
            self._on_activated(self.results.currentItem())

    def _on_activated(self, item: QListWidgetItem) -> None:
        champion_id = int(item.data(Qt.ItemDataRole.UserRole))
        name = str(item.data(Qt.ItemDataRole.UserRole + 1))
        self.field.clear()
        self.results.hide()
        self.chosen.emit(champion_id, name)

    def clear(self) -> None:
        self.field.clear()
        self.results.hide()


def theme_flower() -> Path | None:
    from ui import assets

    return assets.FLOWER if assets.FLOWER.exists() else None


def row(*widgets, spacing: int = 10, stretch_at: int | None = None) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for index, widget in enumerate(widgets):
        layout.addWidget(widget, 1 if index == stretch_at else 0)
    return layout
