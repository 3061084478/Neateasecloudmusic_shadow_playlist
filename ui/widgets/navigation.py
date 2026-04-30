from __future__ import annotations

from typing import Dict, List

from PySide6 import QtCore, QtWidgets


class SegmentedNavigation(QtWidgets.QWidget):
    changed = QtCore.Signal(str)

    def __init__(
        self,
        items: List[tuple[str, str]],
        object_name: str = "segmentedButton",
        parent: QtWidgets.QWidget | None = None,
        fill_width: bool = False,
    ):
        super().__init__(parent)
        self.button_object_name = object_name
        self.buttons: Dict[str, QtWidgets.QPushButton] = {}
        self.current_key = ""
        self.accent_color = ""
        self.fill_width = fill_width

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint if fill_width else QtWidgets.QLayout.SetFixedSize)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding if fill_width else QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)

        for key, label in items:
            button = QtWidgets.QPushButton(label)
            button.setObjectName(self.button_object_name)
            button.setCursor(QtCore.Qt.PointingHandCursor)
            button.setCheckable(True)
            button.setSizePolicy(QtWidgets.QSizePolicy.Expanding if fill_width else QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
            button.clicked.connect(lambda checked=False, route_key=key: self.set_current(route_key, emit_signal=True))
            layout.addWidget(button, 1 if fill_width else 0)
            self.buttons[key] = button
        if not self.fill_width:
            self.adjustSize()

    def set_current(self, key: str, emit_signal: bool = False) -> None:
        if key not in self.buttons:
            return
        self.current_key = key
        for route_key, button in self.buttons.items():
            active = route_key == key
            button.setProperty("active", active)
            button.setChecked(active)
            button.style().unpolish(button)
            button.style().polish(button)
            self._apply_button_style(button, active)
        if not self.fill_width:
            self.adjustSize()
        if emit_signal:
            self.changed.emit(key)

    def set_accent_color(self, color: str) -> None:
        self.accent_color = color
        for route_key, button in self.buttons.items():
            self._apply_button_style(button, route_key == self.current_key)

    def _apply_button_style(self, button: QtWidgets.QPushButton, active: bool) -> None:
        if active and self.accent_color:
            button.setStyleSheet(
                f"background:{self.accent_color}; color:#061116; border:0; border-radius:18px; padding:14px 26px; font-weight:700;"
            )
        else:
            button.setStyleSheet("")


class AnimatedStackedWidget(QtWidgets.QStackedWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._animation_group: QtCore.QParallelAnimationGroup | None = None

    def slide_to_index(self, index: int) -> None:
        if index == self.currentIndex() or index < 0 or index >= self.count():
            return

        current_widget = self.currentWidget()
        next_widget = self.widget(index)
        if current_widget is None or next_widget is None:
            self.setCurrentIndex(index)
            return

        width = self.frameRect().width()
        direction = 1 if index > self.currentIndex() else -1
        offset = width * direction * 0.16

        next_widget.setGeometry(self.rect())
        next_widget.move(int(offset), 0)
        next_widget.show()
        next_widget.raise_()

        current_effect = QtWidgets.QGraphicsOpacityEffect(current_widget)
        next_effect = QtWidgets.QGraphicsOpacityEffect(next_widget)
        current_widget.setGraphicsEffect(current_effect)
        next_widget.setGraphicsEffect(next_effect)
        current_effect.setOpacity(1.0)
        next_effect.setOpacity(0.0)

        self._animation_group = QtCore.QParallelAnimationGroup(self)

        current_move = QtCore.QPropertyAnimation(current_widget, b"pos")
        current_move.setDuration(220)
        current_move.setStartValue(current_widget.pos())
        current_move.setEndValue(QtCore.QPoint(int(-offset * 0.32), 0))
        current_move.setEasingCurve(QtCore.QEasingCurve.OutCubic)

        next_move = QtCore.QPropertyAnimation(next_widget, b"pos")
        next_move.setDuration(240)
        next_move.setStartValue(QtCore.QPoint(int(offset), 0))
        next_move.setEndValue(QtCore.QPoint(0, 0))
        next_move.setEasingCurve(QtCore.QEasingCurve.OutCubic)

        current_fade = QtCore.QPropertyAnimation(current_effect, b"opacity")
        current_fade.setDuration(170)
        current_fade.setStartValue(1.0)
        current_fade.setEndValue(0.0)

        next_fade = QtCore.QPropertyAnimation(next_effect, b"opacity")
        next_fade.setDuration(220)
        next_fade.setStartValue(0.0)
        next_fade.setEndValue(1.0)

        for animation in (current_move, next_move, current_fade, next_fade):
            self._animation_group.addAnimation(animation)

        def finish() -> None:
            self.setCurrentIndex(index)
            current_widget.setGraphicsEffect(None)
            next_widget.setGraphicsEffect(None)
            current_widget.move(0, 0)
            next_widget.move(0, 0)

        self._animation_group.finished.connect(finish)
        self._animation_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
