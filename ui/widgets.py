"""The component library.

Stock Qt controls are styled in `theme.py`. Everything with real shape is drawn
here, from tokens rather than hand-picked numbers, so the interface stays
consistent and a change to the design system lands everywhere at once.
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
    QFrame,
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

# --------------------------------------------------------------- helpers ---


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


def text(content: str = "", role: str = "body", parent: QWidget | None = None) -> QLabel:
    """A label that takes its size, weight and colour from the type scale."""
    widget = QLabel(content, parent)
    widget.setObjectName(role)
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    return widget


def caption(content: str) -> QLabel:
    return text(content.upper(), "caption")


def load_pixmap(path: Path | None) -> QPixmap | None:
    if path is None or not Path(path).exists():
        return None
    pixmap = QPixmap(str(path))
    return None if pixmap.isNull() else pixmap


def paint_shadow(painter: QPainter, rect: QRectF, radius: int, spread: int = 14) -> None:
    """A soft shadow drawn by hand.

    QGraphicsDropShadowEffect caches the widget it decorates, and that cache
    goes stale whenever children appear, move or resize -- which showed up as
    duplicated, offset content. Painting the shadow costs a few rounded rects
    and has no such problem.
    """
    painter.setPen(Qt.PenStyle.NoPen)
    for step in range(spread, 0, -1):
        alpha = 0.030 * (1.0 - step / (spread + 1))
        painter.setBrush(colour("#000000", alpha))
        painter.drawRoundedRect(
            rect.adjusted(-step, -step + 2, step, step + 3), radius + step, radius + step
        )


# ------------------------------------------------------------ primitives ---


class Divider(QWidget):
    """A hairline. Grouping without drawing another box."""

    def __init__(self, inset: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(1)
        self._inset = inset
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.fillRect(
            QRect(self._inset, 0, max(0, self.width() - 2 * self._inset), 1),
            colour(theme.BORDER),
        )


class WindowButton(QAbstractButton):
    """Minimise and close, drawn rather than typed as glyphs."""

    MINIMISE = "minimise"
    CLOSE = "close"

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(30, 26)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAccessibleName("Minimise" if kind == self.MINIMISE else "Close")
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

        active = self._hover or self.hasFocus()
        if active:
            painter.setPen(Qt.PenStyle.NoPen)
            tint = theme.ERROR if self.kind == self.CLOSE else theme.BLUE
            painter.setBrush(colour(tint, 0.20))
            painter.drawRoundedRect(QRectF(self.rect()), theme.RADIUS_SM, theme.RADIUS_SM)

        stroke = colour(theme.TEXT_PRIMARY if active else theme.TEXT_SECONDARY)
        painter.setPen(QPen(stroke, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        middle_x, middle_y = self.width() / 2, self.height() / 2
        if self.kind == self.MINIMISE:
            painter.drawLine(
                QPoint(int(middle_x - 5), int(middle_y)), QPoint(int(middle_x + 5), int(middle_y))
            )
        else:
            painter.drawLine(
                QPoint(int(middle_x - 5), int(middle_y - 5)),
                QPoint(int(middle_x + 5), int(middle_y + 5)),
            )
            painter.drawLine(
                QPoint(int(middle_x + 5), int(middle_y - 5)),
                QPoint(int(middle_x - 5), int(middle_y + 5)),
            )


class Toggle(QAbstractButton):
    """The one switch used everywhere. Orange on, quiet navy off."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(theme.TOGGLE_WIDTH, theme.TOGGLE_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._offset = 0.0
        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setDuration(theme.DURATION_NORMAL)
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
        return QSize(theme.TOGGLE_WIDTH, theme.TOGGLE_HEIGHT)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        height = self.height()
        track = blend(colour(theme.SURFACE_ACTIVE), colour(theme.ACCENT), self._offset)
        painter.setBrush(track)
        painter.drawRoundedRect(QRectF(0, 0, self.width(), height), height / 2, height / 2)

        if self.hasFocus():
            painter.setPen(QPen(colour(theme.BLUE), 1.4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                QRectF(0.7, 0.7, self.width() - 1.4, height - 1.4), height / 2, height / 2
            )
            painter.setPen(Qt.PenStyle.NoPen)

        travel = self.width() - height
        inset = 3
        knob = QRectF(
            inset + travel * self._offset, inset, height - 2 * inset, height - 2 * inset
        )
        painter.setBrush(
            colour(theme.TEXT_PRIMARY if self._offset > 0.5 else theme.TEXT_SECONDARY)
        )
        painter.drawEllipse(knob)


class SettingRow(QWidget):
    """Title, one line of explanation, and a control on the right.

    The same row is used on the dashboard and in settings, which is what keeps
    the two feeling like one application.
    """

    toggled = Signal(bool)

    def __init__(
        self,
        title: str,
        description: str = "",
        checked: bool = False,
        control: QWidget | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(theme.SPACE_4)

        column = QVBoxLayout()
        column.setSpacing(1)
        self.title = text(title, "body-strong")
        column.addWidget(self.title)
        self.description = None
        if description:
            self.description = text(description, "small")
            self.description.setWordWrap(True)
            column.addWidget(self.description)
        layout.addLayout(column, 1)

        self.state = text("", "small")
        self.state.setMinimumWidth(24)
        self.state.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self.state)

        if control is None:
            self.toggle: Toggle | None = Toggle()
            self.toggle.setAccessibleName(title)
            self.toggle.setChecked(checked)
            self.toggle.toggled.connect(self._on_toggled)
            layout.addWidget(self.toggle)
            self._render(checked)
        else:
            self.toggle = None
            self.state.hide()
            layout.addWidget(control)

    def _on_toggled(self, value: bool) -> None:
        self._render(value)
        self.toggled.emit(value)

    def _render(self, value: bool) -> None:
        # State is spelled out as well as coloured, so it never depends on hue.
        self.state.setText("ON" if value else "OFF")
        self.state.setStyleSheet(
            theme.font_css("caption", theme.ACCENT if value else theme.TEXT_MUTED)
        )

    def setChecked(self, value: bool) -> None:  # noqa: N802 - Qt naming
        if self.toggle is None:
            return
        self.toggle.blockSignals(True)
        self.toggle.setChecked(value)
        self.toggle.blockSignals(False)
        self._render(value)

    def isChecked(self) -> bool:  # noqa: N802 - Qt naming
        return bool(self.toggle and self.toggle.isChecked())


class Slider(QWidget):
    """A stepped slider drawn to match the rest of the app."""

    valueChanged = Signal(float)

    HEIGHT = 22
    KNOB = 7
    PAD = 8

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
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
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
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self._seek(event.position().x())

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._seek(event.position().x())

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Down):
            self._commit(self._value - self._step)
        elif event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Up):
            self._commit(self._value + self._step)
        else:
            super().keyPressEvent(event)

    def _seek(self, x: float) -> None:
        span = max(1, self.width() - 2 * self.PAD)
        ratio = min(1.0, max(0.0, (x - self.PAD) / span))
        self._commit(round(ratio * self._maximum / self._step) * self._step)

    def _commit(self, value: float) -> None:
        value = max(0.0, min(self._maximum, round(value / self._step) * self._step))
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

        painter.setBrush(colour(theme.SURFACE_ACTIVE))
        painter.drawRoundedRect(QRectF(left, middle - 2, right - left, 4), 2, 2)

        position = left + (right - left) * (self._value / self._maximum)
        if position > left:
            painter.setBrush(colour(theme.ACCENT))
            painter.drawRoundedRect(QRectF(left, middle - 2, position - left, 4), 2, 2)

        if self._hover or self.hasFocus():
            painter.setBrush(colour(theme.ACCENT, 0.20))
            painter.drawEllipse(QRectF(position - 12, middle - 12, 24, 24))

        painter.setBrush(colour(theme.TEXT_PRIMARY))
        painter.drawEllipse(
            QRectF(position - self.KNOB, middle - self.KNOB, self.KNOB * 2, self.KNOB * 2)
        )


class StatusPill(QWidget):
    """The live state: a dot that breathes, and words that say the same thing."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(26)
        self._text = "Waiting"
        self._colour = colour(theme.TEXT_MUTED)
        self._live = False
        self._pulse = 0.0
        self._animation = QPropertyAnimation(self, b"pulse", self)
        self._animation.setDuration(1900)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._animation.setLoopCount(-1)

    def _get_pulse(self) -> float:
        return self._pulse

    def _set_pulse(self, value: float) -> None:
        self._pulse = value
        self.update()

    pulse = Property(float, _get_pulse, _set_pulse)

    def set_status(self, label: str, tone: str, live: bool = True) -> None:
        self._text = label
        self._colour = colour(tone)
        self._live = live
        running = self._animation.state() == QPropertyAnimation.State.Running
        if live and not running:
            self._animation.start()
        elif not live and running:
            self._animation.stop()
            self._pulse = 0.0
        self.updateGeometry()
        self.update()

    def set_animated(self, playing: bool) -> None:
        if playing and self._live:
            self._animation.start()
        else:
            self._animation.stop()

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt naming
        return QSize(self.fontMetrics().horizontalAdvance(self._text) + 40, 26)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(colour(self._colour.name(), 0.13))
        painter.drawRoundedRect(QRectF(self.rect()), 13, 13)

        swell = 1.0 - abs(self._pulse * 2 - 1)
        if self._live:
            halo = QColor(self._colour)
            halo.setAlphaF(0.18 + 0.28 * swell)
            painter.setBrush(halo)
            painter.drawEllipse(QRectF(9, self.height() / 2 - 5.5, 11, 11))
        painter.setBrush(self._colour)
        painter.drawEllipse(QRectF(11.5, self.height() / 2 - 3, 6, 6))

        painter.setPen(colour(theme.TEXT_PRIMARY))
        font = QFont(theme.FONT, 9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            QRect(26, 0, self.width() - 34, self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._text,
        )


class ProgressBar(QWidget):
    """A thin determinate bar, used for the draft timer and the accept delay."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(4)
        self._fraction = 0.0
        self._tone = theme.BLUE

    def set_progress(self, fraction: float, tone: str | None = None) -> None:
        fraction = max(0.0, min(1.0, fraction))
        changed = abs(fraction - self._fraction) > 0.004 or (tone and tone != self._tone)
        self._fraction = fraction
        if tone:
            self._tone = tone
        if changed:
            self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour(theme.SURFACE_ACTIVE))
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 2, 2)
        if self._fraction > 0:
            painter.setBrush(colour(self._tone))
            painter.drawRoundedRect(
                QRectF(0, 0, self.width() * self._fraction, self.height()), 2, 2
            )


class Avatar(QWidget):
    """The header portrait. Animates when handed a GIF."""

    clicked = Signal()

    def __init__(self, path: Path | None, size: int = 44, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size + 6, size + 6)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._size = size
        self._movie: QMovie | None = None
        self._pixmap: QPixmap | None = None
        self._ring = colour(theme.BLUE)

        if path and Path(path).exists():
            if Path(path).suffix.lower() == ".gif":
                self._movie = QMovie(str(path))
                self._movie.frameChanged.connect(self.update)
                self._movie.start()
            else:
                self._pixmap = QPixmap(str(path))

    def set_tone(self, tone: str) -> None:
        self._ring = colour(tone)
        self.update()

    def set_animated(self, playing: bool) -> None:
        """Paused while hidden, so the tray costs nothing to leave running."""
        if self._movie is not None:
            self._movie.setPaused(not playing)

    def mousePressEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        self.clicked.emit()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        body = QRectF(3, 3, self._size, self._size)
        clip = QPainterPath()
        clip.addEllipse(body)
        painter.save()
        painter.setClipPath(clip)
        painter.fillRect(self.rect(), colour(theme.SURFACE_ACTIVE))

        frame = self._movie.currentPixmap() if self._movie is not None else self._pixmap
        if frame is not None and not frame.isNull():
            scaled = frame.scaled(
                body.size().toSize(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(
                int(body.x() - (scaled.width() - body.width()) / 2),
                int(body.y() - (scaled.height() - body.height()) / 2),
                scaled,
            )
        painter.restore()

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(self._ring, 2.0))
        painter.drawEllipse(body)


class NeekoArt(QWidget):
    """The state illustration, cross-faded when the situation changes."""

    def __init__(self, height: int = 150, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._pixmap: QPixmap | None = None
        self._role = ""
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)
        self._fade = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade.setDuration(theme.DURATION_SLOW)

    def set_art(self, role: str, pixmap: QPixmap | None, animate: bool = True) -> None:
        if role == self._role:
            return
        self._role = role
        self._pixmap = pixmap
        self.update()
        if animate:
            self._fade.stop()
            self._fade.setStartValue(0.0)
            self._fade.setEndValue(1.0)
            self._fade.start()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        if self._pixmap is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        scaled = self._pixmap.scaledToHeight(
            self.height(), Qt.TransformationMode.SmoothTransformation
        )
        painter.drawPixmap(int((self.width() - scaled.width()) / 2), 0, scaled)


# ---------------------------------------------------------- champion bits ---


class ChampionIcon(QWidget):
    """A rounded champion portrait, or a placeholder initial."""

    def __init__(self, size: int = theme.ICON_MD, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._pixmap: QPixmap | None = None
        self._letter = ""
        self._tone = theme.BORDER_STRONG

    def set_champion(self, name: str, tone: str = theme.BORDER_STRONG) -> None:
        self._letter = (name or "")[:1].upper()
        self._tone = tone
        if not name:
            self._pixmap = None
        self.update()

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        body = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        radius = self.width() * 0.28
        clip = QPainterPath()
        clip.addRoundedRect(body, radius, radius)
        painter.setClipPath(clip)
        painter.fillRect(self.rect(), colour(theme.SURFACE_ACTIVE))

        if self._pixmap is not None and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(0, 0, scaled)
        elif self._letter:
            painter.setPen(colour(theme.TEXT_MUTED))
            font = QFont(theme.FONT, max(9, int(self.height() * 0.34)))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._letter)

        painter.setClipping(False)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(colour(self._tone, 0.8), 1.2))
        painter.drawRoundedRect(body, radius, radius)


class ChampionTile(QAbstractButton):
    """One champion, as a row you can click to change it."""

    def __init__(
        self, role_label: str, primary: bool = True, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(54)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._primary = primary
        self._hover = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_3, theme.SPACE_2, theme.SPACE_3, theme.SPACE_2)
        layout.setSpacing(theme.SPACE_3)

        self.icon = ChampionIcon(theme.ICON_MD if primary else theme.ICON_SM)
        layout.addWidget(self.icon)

        names = QVBoxLayout()
        names.setSpacing(0)
        self.name = text("Choose a champion", "body-strong" if primary else "body")
        # Only shown while the slot is empty; a chosen champion needs no caption.
        self.hint = text(
            "your first pick" if primary else "if the first one is gone", "small"
        )
        names.addWidget(self.name)
        names.addWidget(self.hint)
        layout.addLayout(names, 1)

        self.badge = text(role_label.upper(), "caption")
        layout.addWidget(self.badge)

        self.set_champion(0, "")

    def enterEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        self._hover = True
        self.update()

    def leaveEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        self._hover = False
        self.update()

    def set_champion(self, champion_id: int, name: str) -> None:
        tone = theme.ACCENT if self._primary else theme.BLUE
        chosen = bool(champion_id)
        self.icon.set_champion(name, tone if chosen else theme.BORDER_STRONG)
        self.name.setText(name or "Choose a champion")
        self.name.setStyleSheet(
            theme.font_css(
                "body-strong" if self._primary else "body",
                theme.TEXT_PRIMARY if chosen else theme.TEXT_MUTED,
            )
        )
        self.hint.setVisible(not chosen)
        self.badge.setStyleSheet(
            theme.font_css("caption", tone if chosen else theme.TEXT_MUTED)
        )
        self.setAccessibleName(f"{self.badge.text()}: {name or 'not chosen'}")

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        self.icon.set_pixmap(pixmap)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        body = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        if self._hover or self.hasFocus():
            painter.setBrush(colour(theme.SURFACE_HOVER))
            painter.drawRoundedRect(body, theme.RADIUS_MD, theme.RADIUS_MD)
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(colour(theme.BLUE), 1.2))
            painter.drawRoundedRect(body, theme.RADIUS_MD, theme.RADIUS_MD)


class ChampionHero(QWidget):
    """The draft centrepiece: splash art, masked, with the champion on top."""

    def __init__(self, height: int = 152, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(height)
        self._splash: QPixmap | None = None
        self._icon: QPixmap | None = None
        self._name = ""
        self._tone = theme.ACCENT

        layout = QHBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_4, theme.SPACE_4, theme.SPACE_4, theme.SPACE_4)
        layout.setSpacing(theme.SPACE_3)

        self.icon = ChampionIcon(theme.ICON_LG)
        layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignVCenter)

        column = QVBoxLayout()
        column.setSpacing(2)
        column.addStretch(1)
        self.badge = text("YOUR CHAMPION", "caption")
        self.name_label = text("", "display")
        column.addWidget(self.badge)
        column.addWidget(self.name_label)
        column.addStretch(1)
        layout.addLayout(column, 1)

    def set_champion(self, name: str, tone: str = theme.ACCENT) -> None:
        self._name, self._tone = name, tone
        self.name_label.setText(name or "No champion chosen")
        self.name_label.setStyleSheet(
            theme.font_css("display", theme.TEXT_PRIMARY if name else theme.TEXT_MUTED)
        )
        self.badge.setStyleSheet(theme.font_css("caption", tone))
        self.icon.set_champion(name, tone)
        if not name:
            self._splash = None
        self.update()

    def set_icon(self, pixmap: QPixmap | None) -> None:
        self._icon = pixmap
        self.icon.set_pixmap(pixmap)

    def set_splash(self, pixmap: QPixmap | None) -> None:
        self._splash = pixmap
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        body = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        clip = QPainterPath()
        clip.addRoundedRect(body, theme.RADIUS_LG, theme.RADIUS_LG)
        painter.save()
        painter.setClipPath(clip)
        painter.fillRect(self.rect(), colour(theme.SURFACE))

        if self._splash is not None:
            scaled = self._splash.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            # Splashes are composed around the face; bias upward to keep it in frame.
            painter.drawPixmap(
                int((self.width() - scaled.width()) * 0.5),
                int((self.height() - scaled.height()) * 0.3),
                scaled,
            )
            # One horizontal mask keeps the text side readable without a slab.
            wash = QLinearGradient(0, 0, self.width(), 0)
            wash.setColorAt(0.0, colour(theme.SURFACE, 0.98))
            wash.setColorAt(0.52, colour(theme.SURFACE, 0.80))
            wash.setColorAt(1.0, colour(theme.SURFACE, 0.22))
            painter.fillRect(self.rect(), wash)
        painter.restore()

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(colour(self._tone if self._name else theme.BORDER, 0.55), 1.2))
        painter.drawRoundedRect(body, theme.RADIUS_LG, theme.RADIUS_LG)


class ChampionResult(QWidget):
    """One row inside the search overlay."""

    HEIGHT = 36

    def __init__(self, champion, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.champion = champion
        layout = QHBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_2, theme.SPACE_1, theme.SPACE_2, theme.SPACE_1)
        layout.setSpacing(theme.SPACE_3)

        self.icon = ChampionIcon(theme.ICON_SM)
        self.icon.set_champion(champion.name)
        layout.addWidget(self.icon)

        layout.addWidget(text(champion.name, "body-strong"), 1)

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        self.icon.set_pixmap(pixmap)


class SearchOverlay(QFrame):
    """Champion search, floated over the dashboard.

    It is a child of the window rather than a layout item, so opening it never
    reflows anything underneath -- which is both calmer to look at and free of
    the repaint problems a changing layout brings.
    """

    chosen = Signal(int, str)
    dismissed = Signal()
    art_wanted = Signal(str, int)

    MAX_RESULTS = 6

    def __init__(self, catalog, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self._rows: dict[int, ChampionResult] = {}
        # Answers "do we already have this icon?". Rows are rebuilt on every
        # keystroke, and the loader only ever fetches a champion once, so a row
        # created for a second search would otherwise never be filled in.
        self.pixmap_for = lambda champion_id: None
        self.setObjectName("overlay")
        self.setStyleSheet(
            f"""
            QFrame#overlay {{
                background: {theme.SURFACE};
                border: 1px solid {theme.BORDER_STRONG};
                border-radius: {theme.RADIUS_LG}px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_3, theme.SPACE_3, theme.SPACE_3, theme.SPACE_3)
        layout.setSpacing(theme.SPACE_2)

        header = QHBoxLayout()
        self.heading = text("Choose your champion", "title")
        header.addWidget(self.heading, 1)
        close = WindowButton(WindowButton.CLOSE)
        close.clicked.connect(self.dismissed.emit)
        header.addWidget(close)
        layout.addLayout(header)

        self.field = QLineEdit()
        self.field.setPlaceholderText("Search champions")
        self.field.addAction(_magnifier(), QLineEdit.ActionPosition.LeadingPosition)
        self.field.textChanged.connect(self._on_typed)
        self.field.returnPressed.connect(self._on_return)
        layout.addWidget(self.field)

        self.results = QListWidget()
        self.results.setFixedHeight(6 + self.MAX_RESULTS * ChampionResult.HEIGHT)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results.itemClicked.connect(self._on_activated)
        self.results.itemActivated.connect(self._on_activated)
        layout.addWidget(self.results)

        self.hint = text("Type a name, then press Enter.", "small")
        layout.addWidget(self.hint)
        self.hide()

    # -- opening and closing ---------------------------------------------

    def open_for(self, heading: str) -> None:
        self.heading.setText(heading)
        self.field.clear()
        self._populate(self.catalog.all[: self.MAX_RESULTS])
        self.show()
        self.raise_()
        self.field.setFocus(Qt.FocusReason.OtherFocusReason)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.key() == Qt.Key.Key_Escape:
            self.dismissed.emit()
            return
        if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up) and self.results.count():
            self.results.setFocus(Qt.FocusReason.TabFocusReason)
            return
        super().keyPressEvent(event)

    # -- searching --------------------------------------------------------

    def _on_typed(self, query: str) -> None:
        matches = (
            self.catalog.search(query, limit=self.MAX_RESULTS)
            if query.strip()
            else self.catalog.all[: self.MAX_RESULTS]
        )
        self._populate(matches)

    def _populate(self, champions) -> None:
        self.results.clear()
        self._rows.clear()
        for champion in champions:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, ChampionResult.HEIGHT))
            item.setData(Qt.ItemDataRole.UserRole, champion.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, champion.name)
            row = ChampionResult(champion)
            self.results.addItem(item)
            self.results.setItemWidget(item, row)
            self._rows[champion.id] = row

            cached = self.pixmap_for(champion.id)
            if cached is not None:
                row.set_pixmap(cached)
            else:
                self.art_wanted.emit("icon", champion.id)
        if champions:
            self.results.setCurrentRow(0)
        self.hint.setText(
            "Type a name, then press Enter." if champions else "No champion by that name."
        )

    def set_pixmap(self, champion_id: int, pixmap: QPixmap) -> None:
        row = self._rows.get(champion_id)
        if row is not None:
            row.set_pixmap(pixmap)

    def _on_return(self) -> None:
        if self.results.currentItem():
            self._on_activated(self.results.currentItem())

    def _on_activated(self, item: QListWidgetItem) -> None:
        self.chosen.emit(
            int(item.data(Qt.ItemDataRole.UserRole)),
            str(item.data(Qt.ItemDataRole.UserRole + 1)),
        )


def _magnifier(tint: str = theme.TEXT_MUTED, size: int = 16) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(colour(tint), 1.6))
    painter.drawEllipse(QRectF(2.5, 2.5, 8.5, 8.5))
    painter.drawLine(QPoint(11, 11), QPoint(14, 14))
    painter.end()
    return QIcon(pixmap)


class Chip(QWidget):
    """A compact badge saying whether one automation is armed, done or off."""

    OFF = "off"
    ARMED = "armed"
    FAILED = "failed"

    _MARKS = {OFF: "–", ARMED: "•", FAILED: "!"}

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(24)
        self._label = label
        self._state = self.OFF
        self._done = False

    def set_state(self, state: str, done: bool = False) -> None:
        if state == self._state and done == self._done:
            return
        self._state, self._done = state, done
        self.updateGeometry()
        self.update()

    def _tone(self) -> str:
        if self._state == self.FAILED:
            return theme.ERROR
        if self._state == self.OFF:
            return theme.TEXT_MUTED
        return theme.SUCCESS if self._done else theme.BLUE

    def _mark(self) -> str:
        if self._state == self.ARMED and self._done:
            return "✓"
        return self._MARKS[self._state]

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt naming
        return QSize(self.fontMetrics().horizontalAdvance(self._label) + 40, 24)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        tone = self._tone()
        painter.setBrush(colour(tone, 0.13))
        painter.drawRoundedRect(QRectF(self.rect()), 12, 12)

        painter.setPen(colour(tone))
        font = QFont(theme.FONT, 9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            self.rect().adjusted(10, 0, -10, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            f"{self._mark()}  {self._label}",
        )


class Toast(QWidget):
    """A quiet line that reports the last thing the app did."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(20)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = text("", "small")
        layout.addWidget(self.label)

        self._effect = QGraphicsOpacityEffect(self.label)
        self.label.setGraphicsEffect(self._effect)
        self._fade = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade.setDuration(theme.DURATION_SLOW)

    def show_message(self, message: str, tone: str) -> None:
        self.label.setText(message)
        self.label.setStyleSheet(theme.font_css("small", tone))
        self._fade.stop()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()


def row(*widgets, spacing: int = theme.SPACE_3, stretch_at: int | None = None) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for index, widget in enumerate(widgets):
        layout.addWidget(widget, 1 if index == stretch_at else 0)
    return layout
