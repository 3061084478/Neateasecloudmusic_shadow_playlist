from __future__ import annotations

from typing import Any, Dict

from PySide6 import QtCore, QtGui, QtWidgets

from core.app_controller import AppController
from ui.widgets.common import make_button, make_label, run_async


class StartupView(QtWidgets.QWidget):
    completed = QtCore.Signal()

    def __init__(self, controller: AppController, thread_pool: QtCore.QThreadPool, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.thread_pool = thread_pool
        self._initialized = False
        self._polling = False
        self.qr_key = ""

        self.poll_timer = QtCore.QTimer(self)
        self.poll_timer.setInterval(2200)
        self.poll_timer.timeout.connect(self.poll_qr_status)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(0)

        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        root.addWidget(self.scroll_area, 1)

        content = QtWidgets.QWidget()
        self.scroll_area.setWidget(content)

        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(24, 16, 24, 24)
        content_layout.setSpacing(20)

        surface = QtWidgets.QFrame()
        surface.setObjectName("startupSurface")
        surface_layout = QtWidgets.QVBoxLayout(surface)
        surface_layout.setContentsMargins(28, 28, 28, 28)
        surface_layout.setSpacing(18)
        content_layout.addWidget(surface, 1)

        headline = QtWidgets.QVBoxLayout()
        headline.setSpacing(4)
        headline.addWidget(make_label("网易云影子歌单 V5", "pageTitle", False))
        headline.addWidget(make_label("启动后先做 API / Cookie / 登录检查，不直接跳主界面。", "mutedText", False))
        surface_layout.addLayout(headline)

        self.status_label = make_label("准备启动检查。", "sectionTitle", False)
        surface_layout.addWidget(self.status_label)

        self.detail_label = make_label("等待执行。", "mutedText", True)
        surface_layout.addWidget(self.detail_label)

        button_row = QtWidgets.QHBoxLayout()
        self.start_api_button = make_button("启动本地 API", "primaryButton")
        self.retry_button = make_button("重试检测", "secondaryButton")
        self.qr_button = make_button("二维码登录", "secondaryButton")
        button_row.addWidget(self.start_api_button)
        button_row.addWidget(self.retry_button)
        button_row.addWidget(self.qr_button)
        button_row.addStretch(1)
        surface_layout.addLayout(button_row)

        qr_card = QtWidgets.QFrame()
        qr_card.setObjectName("card")
        qr_card.setMinimumHeight(430)
        qr_card.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        qr_layout = QtWidgets.QVBoxLayout(qr_card)
        qr_layout.setContentsMargins(18, 18, 18, 18)
        qr_layout.setSpacing(12)
        qr_layout.addWidget(make_label("扫码登录", "sectionTitle", False))

        self.qr_label = QtWidgets.QLabel("二维码区域")
        self.qr_label.setAlignment(QtCore.Qt.AlignCenter)
        self.qr_label.setMinimumSize(320, 320)
        self.qr_label.setMaximumHeight(340)
        self.qr_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.qr_label.setStyleSheet("background:#ffffff; border-radius:20px; padding:12px; color:#111111;")

        self.qr_url_label = make_label("", "mutedText", True)
        self.qr_url_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.qr_url_label.setWordWrap(True)
        qr_layout.addWidget(self.qr_label)
        qr_layout.addWidget(self.qr_url_label)
        surface_layout.addWidget(qr_card)

        log_card = QtWidgets.QFrame()
        log_card.setObjectName("card")
        log_card.setMaximumHeight(260)
        log_layout = QtWidgets.QVBoxLayout(log_card)
        log_layout.setContentsMargins(18, 18, 18, 18)
        log_layout.setSpacing(8)
        log_layout.addWidget(make_label("启动日志", "sectionTitle", False))
        self.log_output = QtWidgets.QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(140)
        self.log_output.setMaximumHeight(180)
        log_layout.addWidget(self.log_output)
        surface_layout.addWidget(log_card)

        self.start_api_button.clicked.connect(self.start_api)
        self.retry_button.clicked.connect(self.start_initial_check)
        self.qr_button.clicked.connect(self.start_qr_login)
        self._set_button_visibility(show_api=False, show_retry=True, show_qr=False)

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # type: ignore[name-defined]
        super().showEvent(event)
        if not self._initialized:
            self._initialized = True
            QtCore.QTimer.singleShot(80, self.start_initial_check)

    def append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)

    def _set_button_visibility(self, show_api: bool, show_retry: bool, show_qr: bool) -> None:
        self.start_api_button.setVisible(show_api)
        self.retry_button.setVisible(show_retry)
        self.qr_button.setVisible(show_qr)

    def start_initial_check(self) -> None:
        self.status_label.setText("正在检测本地 API ...")
        self.detail_label.setText("先快速检测本地 3000 端口，再继续检测 Cookie。")
        self.append_log("开始执行启动检查。")
        self.append_log(f"当前配置文件：{self.controller.bootstrap.get_config_path()}")
        run_async(
            self.thread_pool,
            self.controller.bootstrap.is_api_port_open,
            self._handle_port_check_result,
            self._handle_error,
        )

    def _handle_port_check_result(self, api_ready: Any) -> None:
        if not bool(api_ready):
            self.status_label.setText("未检测到本地 API")
            self.detail_label.setText("端口未开启，请先启动本地 NeteaseCloudMusicApi，或点击重试检测。")
            self._set_button_visibility(show_api=True, show_retry=True, show_qr=False)
            self.append_log("未检测到本地 API。")
            return

        self.append_log("已检测到 API 端口开启。")
        self.status_label.setText("已检测到本地 API，正在检测 Cookie ...")
        self.detail_label.setText("API 已连接，下一步检查本地 Cookie 是否有效。")
        self._set_button_visibility(show_api=False, show_retry=True, show_qr=False)
        self.append_log(
            "已读取到本地 Cookie。"
            if self.controller.bootstrap.has_saved_cookie()
            else "当前配置里没有本地 Cookie。"
        )
        run_async(
            self.thread_pool,
            self.controller.bootstrap.is_cookie_valid,
            self._handle_cookie_check_result,
            self._handle_error,
        )

    def _handle_cookie_check_result(self, cookie_valid: Any) -> None:
        if bool(cookie_valid):
            self.status_label.setText("已检测到有效 Cookie，正在进入主界面。")
            self.detail_label.setText("启动检查完成，应用将切换到已登录主界面。")
            self.append_log("Cookie 有效，启动检查完成。")
            self.controller.apply_startup_authenticated_state()
            self.completed.emit()
            return

        self.status_label.setText("Cookie 无效或不存在")
        self.detail_label.setText("请使用二维码登录，登录成功后会自动进入主界面。")
        self._set_button_visibility(show_api=False, show_retry=True, show_qr=True)
        self.append_log("Cookie 校验未通过，进入二维码登录流程。")
        self.start_qr_login()

    def start_api(self) -> None:
        self.status_label.setText("正在启动本地 API ...")
        self.detail_label.setText("正在拉起本地服务，检测到端口可用后会自动继续。")
        self.append_log("尝试启动本地 API。")
        run_async(
            self.thread_pool,
            self.controller.bootstrap.ensure_api_ready,
            lambda _: self.start_initial_check(),
            self._handle_error,
        )

    def start_qr_login(self) -> None:
        self.status_label.setText("正在生成二维码 ...")
        self.append_log("开始生成二维码。")
        run_async(
            self.thread_pool,
            self.controller.bootstrap.create_qr_session,
            self._handle_qr_ready,
            self._handle_error,
        )

    def _handle_qr_ready(self, payload: Dict[str, Any]) -> None:
        self.qr_key = str(payload.get("key") or "")
        qr_url = str(payload.get("qr_url") or "")
        pixmap = self.controller.bootstrap.build_qr_pixmap(qr_url)
        if pixmap:
            self.qr_label.setPixmap(pixmap)
        else:
            self.qr_label.setText("当前环境未安装 qrcode，已展示登录链接。")
        self.qr_url_label.setText(qr_url)
        self.status_label.setText("请使用网易云音乐 App 扫码登录")
        self.detail_label.setText("扫码后请在手机确认，成功后会自动进入主界面。")
        self.append_log("二维码已生成。")
        self._polling = True
        self.poll_timer.start()

    def poll_qr_status(self) -> None:
        if not self.qr_key or self._polling is False:
            return
        self._polling = False
        run_async(
            self.thread_pool,
            self.controller.bootstrap.check_qr_session,
            self._handle_qr_status,
            self._handle_error,
            self._resume_polling,
            self.qr_key,
        )

    def _resume_polling(self) -> None:
        if self.poll_timer.isActive():
            self._polling = True

    def _handle_qr_status(self, payload: Dict[str, Any]) -> None:
        code = int(payload.get("code") or 0)
        if code == 801:
            self.append_log("等待扫码。")
            return
        if code == 802:
            self.append_log("已扫码，等待手机确认。")
            self.status_label.setText("已扫码，请在手机确认登录")
            return
        if code == 803:
            self.poll_timer.stop()
            self.status_label.setText("登录成功，正在进入主界面。")
            self.detail_label.setText("二维码登录成功，应用将自动切换到主界面。")
            self.append_log("二维码登录成功。")
            self.controller.apply_startup_authenticated_state()
            self.completed.emit()
            return
        if code == 800:
            self.poll_timer.stop()
            self.status_label.setText("二维码已过期")
            self.detail_label.setText("请重新生成二维码。")
            self.append_log("二维码已过期。")

    def _handle_error(self, error_text: str) -> None:
        message = error_text.strip().splitlines()[-1]
        self.status_label.setText("启动流程发生错误")
        self.detail_label.setText(message)
        self.append_log(message)
