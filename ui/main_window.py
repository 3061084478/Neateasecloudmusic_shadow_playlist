from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from core.app_controller import AppController
from ui.pages.web_shell_page import WebShellPage
from ui.startup.startup_view import StartupView


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, controller: AppController, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.thread_pool = QtCore.QThreadPool.globalInstance()
        self.setWindowTitle("网易云影子歌单 V5")
        self.resize(1460, 980)
        self.setMinimumSize(1280, 820)

        root = QtWidgets.QWidget()
        root.setObjectName("windowRoot")
        self.setCentralWidget(root)

        root_layout = QtWidgets.QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.screen_stack = QtWidgets.QStackedWidget()
        root_layout.addWidget(self.screen_stack, 1)

        self.startup_view = StartupView(controller, self.thread_pool)
        self.startup_view.completed.connect(self.show_app_shell)
        self.screen_stack.addWidget(self.startup_view)

        self.app_shell = QtWidgets.QWidget()
        self.app_shell.setObjectName("webShellRoot")
        app_shell_layout = QtWidgets.QVBoxLayout(self.app_shell)
        app_shell_layout.setContentsMargins(0, 0, 0, 0)
        app_shell_layout.setSpacing(0)

        self.web_shell_page = WebShellPage(controller)
        app_shell_layout.addWidget(self.web_shell_page, 1)
        self.screen_stack.addWidget(self.app_shell)

        self.screen_stack.setCurrentWidget(self.startup_view)

    def show_app_shell(self) -> None:
        try:
            state = self.controller.build_session_state(
                fetch_account_profile=True,
                fetch_shadow_playlist=True,
            )
            self.controller.apply_session_state(state)
            if state.mode == "real":
                try:
                    friends = self.controller.load_all_friends(force_refresh=False)
                    self.controller.apply_all_friends(friends)
                except Exception:
                    pass
        except Exception:
            pass

        self.web_shell_page.ensure_loaded()
        self.screen_stack.setCurrentWidget(self.app_shell)

    def show_startup(self) -> None:
        self.screen_stack.setCurrentWidget(self.startup_view)
        self.startup_view.start_initial_check()
