from __future__ import annotations

import traceback
from typing import Any, Callable

from PySide6 import QtCore, QtWidgets

_ACTIVE_WORKERS: set["Worker"] = set()


class WorkerSignals(QtCore.QObject):
    success = QtCore.Signal(object)
    error = QtCore.Signal(str)
    done = QtCore.Signal()


class Worker(QtCore.QRunnable):
    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @QtCore.Slot()
    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            self.signals.error.emit(traceback.format_exc())
        else:
            self.signals.success.emit(result)
        finally:
            self.signals.done.emit()


def run_async(
    thread_pool: QtCore.QThreadPool,
    fn: Callable[..., Any],
    on_success: Callable[[Any], None],
    on_error: Callable[[str], None],
    on_done: Callable[[], None] | None = None,
    *args: Any,
    **kwargs: Any,
) -> None:
    worker = Worker(fn, *args, **kwargs)
    _ACTIVE_WORKERS.add(worker)
    worker.signals.success.connect(on_success)
    worker.signals.error.connect(on_error)
    worker.signals.done.connect(lambda: _ACTIVE_WORKERS.discard(worker))
    if on_done:
        worker.signals.done.connect(on_done)
    thread_pool.start(worker)


def v_spacer(height: int = 12) -> QtWidgets.QSpacerItem:
    return QtWidgets.QSpacerItem(0, height, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)


def make_label(text: str, object_name: str = "", word_wrap: bool = True) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    if object_name:
        label.setObjectName(object_name)
    label.setWordWrap(word_wrap)
    return label


def make_button(text: str, object_name: str) -> QtWidgets.QPushButton:
    button = QtWidgets.QPushButton(text)
    button.setObjectName(object_name)
    button.setCursor(QtCore.Qt.PointingHandCursor)
    return button
