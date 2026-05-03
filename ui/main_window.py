from __future__ import annotations

from PySide6 import QtWidgets

from core.app_controller import AppController
from ui.pages.web_shell_page import WebShellPage


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, controller: AppController, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("网易云影子歌单 V5")
        self.resize(1460, 980)
        self.setMinimumSize(1280, 820)

        root = QtWidgets.QWidget()
        root.setObjectName("windowRoot")
        self.setCentralWidget(root)

        root_layout = QtWidgets.QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.web_shell_page = WebShellPage(controller)
        root_layout.addWidget(self.web_shell_page, 1)
        self.web_shell_page.ensure_loaded()
