from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from core.app_controller import AppController
from ui.web_bridge import WebBridge


class WebShellPage(QtWidgets.QWidget):
    def __init__(self, controller: AppController, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self._loaded = False
        self._dist_index_path = Path(__file__).resolve().parents[2] / "web" / "dist" / "index.html"
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor("#07080a"))
        self.setPalette(palette)
        self.setStyleSheet("background:#07080a;")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.web_view = QWebEngineView()
        self.web_view.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        self.web_view.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, True)
        self.web_view.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.web_view.setAutoFillBackground(True)
        self.web_view.setStyleSheet("background:#07080a;")
        self.web_view.page().setBackgroundColor(QtGui.QColor("#07080a"))
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, False)
        settings.setAttribute(QWebEngineSettings.ErrorPageEnabled, True)

        self.bridge = WebBridge(controller, self)
        self.channel = QWebChannel(self.web_view.page())
        self.channel.registerObject("pybridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        self.stack.addWidget(self.web_view)

        self.fallback = self._build_fallback()
        self.stack.addWidget(self.fallback)
        self.stack.setCurrentWidget(self.fallback)

        self.web_view.loadFinished.connect(self._on_load_finished)

    def _build_fallback(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        shell = QtWidgets.QFrame()
        shell.setObjectName("startupSurface")
        shell_layout = QtWidgets.QVBoxLayout(shell)
        shell_layout.setContentsMargins(28, 28, 28, 28)
        shell_layout.setSpacing(14)

        title = QtWidgets.QLabel("Web Shell 尚未构建")
        title.setObjectName("pageTitle")
        shell_layout.addWidget(title)

        desc = QtWidgets.QLabel(
            "登录后的主界面已经切换到 React / WebView 壳。当前没有找到 web 构建产物，请先在 V5/web 下安装依赖并执行构建。"
        )
        desc.setObjectName("mutedText")
        desc.setWordWrap(True)
        shell_layout.addWidget(desc)

        command_box = QtWidgets.QPlainTextEdit()
        command_box.setReadOnly(True)
        command_box.setPlainText("cd V5\\web\nnpm install\nnpm run build")
        command_box.setMinimumHeight(110)
        shell_layout.addWidget(command_box)

        button_row = QtWidgets.QHBoxLayout()
        reload_button = QtWidgets.QPushButton("重新检测构建产物")
        reload_button.setObjectName("secondaryButton")
        reload_button.clicked.connect(self.ensure_loaded)
        button_row.addWidget(reload_button)
        button_row.addStretch(1)
        shell_layout.addLayout(button_row)

        layout.addWidget(shell, 0)
        layout.addStretch(1)
        return page

    def ensure_loaded(self) -> None:
        if not self._dist_index_path.exists():
            self.stack.setCurrentWidget(self.fallback)
            return
        if self._loaded:
            self.stack.setCurrentWidget(self.web_view)
            self.web_view.reload()
            return
        self._loaded = True
        self.stack.setCurrentWidget(self.web_view)
        self.web_view.load(QtCore.QUrl.fromLocalFile(str(self._dist_index_path)))

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            self.stack.setCurrentWidget(self.fallback)
