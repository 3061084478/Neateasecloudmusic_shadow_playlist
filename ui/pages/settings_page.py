from __future__ import annotations

from typing import Any, Dict

from PySide6 import QtCore, QtGui, QtWidgets

from core.app_controller import AppController
from ui.widgets.common import make_button, make_label, run_async


class SettingsPage(QtWidgets.QWidget):
    relogin_requested = QtCore.Signal()
    full_archive_requested = QtCore.Signal()

    def __init__(self, controller: AppController, thread_pool: QtCore.QThreadPool, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.thread_pool = thread_pool
        self.qr_key = ""
        self._polling = False

        self.poll_timer = QtCore.QTimer(self)
        self.poll_timer.setInterval(2200)
        self.poll_timer.timeout.connect(self.poll_qr_status)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(20)

        layout.addWidget(make_label("设置 / 账号", "pageTitle", False))

        self.status_card = QtWidgets.QFrame()
        self.status_card.setObjectName("summaryCard")
        status_layout = QtWidgets.QVBoxLayout(self.status_card)
        status_layout.setContentsMargins(18, 18, 18, 18)
        status_layout.setSpacing(8)
        status_layout.addWidget(make_label("当前连接状态", "sectionTitle", False))
        self.status_rows = QtWidgets.QVBoxLayout()
        self.status_rows.setSpacing(8)
        status_layout.addLayout(self.status_rows)
        layout.addWidget(self.status_card)

        self.action_panel = QtWidgets.QWidget()
        self.action_panel.setObjectName("settingsActionPanel")
        button_row = QtWidgets.QGridLayout(self.action_panel)
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setHorizontalSpacing(12)
        button_row.setVerticalSpacing(12)
        layout.addWidget(self.action_panel)

        self.detect_api_button = make_button("检测 API", "secondaryButton")
        self.start_api_button = make_button("启动本地 API", "secondaryButton")
        self.detect_cookie_button = make_button("检测 Cookie", "secondaryButton")
        self.qr_login_button = make_button("二维码登录", "secondaryButton")
        self.clear_cookie_button = make_button("清空本地 Cookie", "secondaryButton")
        self.relogin_button = make_button("重新登录", "secondaryButton")
        self.rebuild_archive_button = make_button("全量重建归档", "secondaryButton")
        self.refresh_button = make_button("刷新状态", "ghostButton")
        buttons = [
            self.detect_api_button,
            self.start_api_button,
            self.detect_cookie_button,
            self.qr_login_button,
            self.clear_cookie_button,
            self.relogin_button,
            self.rebuild_archive_button,
            self.refresh_button,
        ]
        for index, button in enumerate(buttons):
            button_row.addWidget(button, index // 3, index % 3)

        self.ai_card = QtWidgets.QFrame()
        self.ai_card.setObjectName("card")
        ai_layout = QtWidgets.QVBoxLayout(self.ai_card)
        ai_layout.setContentsMargins(18, 18, 18, 18)
        ai_layout.setSpacing(10)
        ai_layout.addWidget(make_label("AI 文段配置（可选）", "sectionTitle", False))
        self.ai_enabled_check = QtWidgets.QCheckBox("启用云端 AI（未启用时自动使用本地模板）")
        ai_layout.addWidget(self.ai_enabled_check)
        ai_form = QtWidgets.QGridLayout()
        ai_form.setHorizontalSpacing(10)
        ai_form.setVerticalSpacing(8)
        self.ai_base_url_edit = QtWidgets.QLineEdit()
        self.ai_base_url_edit.setPlaceholderText("例如：https://api.openai.com/v1")
        self.ai_model_edit = QtWidgets.QLineEdit()
        self.ai_model_edit.setPlaceholderText("例如：gpt-4o-mini")
        self.ai_key_edit = QtWidgets.QLineEdit()
        self.ai_key_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.ai_key_edit.setPlaceholderText("可留空，留空时自动回退模板")
        self.ai_timeout_spin = QtWidgets.QSpinBox()
        self.ai_timeout_spin.setRange(5, 120)
        self.ai_timeout_spin.setValue(20)
        ai_form.addWidget(make_label("Base URL", "mutedText", False), 0, 0)
        ai_form.addWidget(self.ai_base_url_edit, 0, 1)
        ai_form.addWidget(make_label("Model", "mutedText", False), 1, 0)
        ai_form.addWidget(self.ai_model_edit, 1, 1)
        ai_form.addWidget(make_label("API Key", "mutedText", False), 2, 0)
        ai_form.addWidget(self.ai_key_edit, 2, 1)
        ai_form.addWidget(make_label("超时（秒）", "mutedText", False), 3, 0)
        ai_form.addWidget(self.ai_timeout_spin, 3, 1)
        ai_layout.addLayout(ai_form)
        ai_button_row = QtWidgets.QHBoxLayout()
        self.ai_save_button = make_button("保存 AI 配置", "secondaryButton")
        ai_button_row.addWidget(self.ai_save_button)
        ai_button_row.addStretch(1)
        ai_layout.addLayout(ai_button_row)
        layout.addWidget(self.ai_card)

        self.qr_card = QtWidgets.QFrame()
        self.qr_card.setObjectName("card")
        qr_layout = QtWidgets.QVBoxLayout(self.qr_card)
        qr_layout.setContentsMargins(18, 18, 18, 18)
        qr_layout.setSpacing(10)
        qr_layout.addWidget(make_label("二维码登录", "sectionTitle", False))
        self.qr_label = QtWidgets.QLabel("等待生成二维码")
        self.qr_label.setAlignment(QtCore.Qt.AlignCenter)
        self.qr_label.setMinimumHeight(260)
        self.qr_url_label = make_label("", "mutedText", True)
        qr_layout.addWidget(self.qr_label)
        qr_layout.addWidget(self.qr_url_label)
        layout.addWidget(self.qr_card)

        self.diagnostic_card = QtWidgets.QFrame()
        self.diagnostic_card.setObjectName("card")
        diagnostic_layout = QtWidgets.QVBoxLayout(self.diagnostic_card)
        diagnostic_layout.setContentsMargins(18, 18, 18, 18)
        diagnostic_layout.setSpacing(10)
        diagnostic_layout.addWidget(make_label("运行结果 / 诊断输出", "sectionTitle", False))
        self.diagnostic_output = QtWidgets.QPlainTextEdit()
        self.diagnostic_output.setReadOnly(True)
        self.diagnostic_output.setMinimumHeight(180)
        diagnostic_layout.addWidget(self.diagnostic_output)
        layout.addWidget(self.diagnostic_card)

        self.error_card = QtWidgets.QFrame()
        self.error_card.setObjectName("card")
        error_layout = QtWidgets.QVBoxLayout(self.error_card)
        error_layout.setContentsMargins(18, 18, 18, 18)
        error_layout.setSpacing(8)
        error_layout.addWidget(make_label("最近错误信息", "sectionTitle", False))
        self.error_label = make_label("暂无错误。", "mutedText", True)
        error_layout.addWidget(self.error_label)
        layout.addWidget(self.error_card)
        layout.addStretch(1)

        self.detect_api_button.clicked.connect(self.detect_api)
        self.start_api_button.clicked.connect(self.start_api)
        self.detect_cookie_button.clicked.connect(self.detect_cookie)
        self.qr_login_button.clicked.connect(self.start_qr_login)
        self.clear_cookie_button.clicked.connect(self.clear_cookie)
        self.relogin_button.clicked.connect(self.relogin_requested.emit)
        self.rebuild_archive_button.clicked.connect(self._request_full_archive_rebuild)
        self.refresh_button.clicked.connect(self.refresh_state_async)
        self.ai_save_button.clicked.connect(self.save_ai_settings)
        self.refresh_state()
        self.refresh_ai_settings()

    def append_log(self, message: str) -> None:
        self.diagnostic_output.appendPlainText(message)

    def set_error(self, message: str) -> None:
        self.error_label.setText(message or "暂无错误。")

    def refresh_state(self) -> None:
        state = self.controller.session_state
        while self.status_rows.count():
            item = self.status_rows.takeAt(0)
            if item.layout():
                while item.layout().count():
                    inner = item.layout().takeAt(0)
                    if inner.widget():
                        inner.widget().deleteLater()
        for label, value in (
            ("当前模式", state.mode),
            ("API 状态", state.api_status),
            ("Cookie 状态", state.cookie_status),
            ("当前账号", state.account_profile.nickname or "未登录"),
        ):
            row = QtWidgets.QHBoxLayout()
            row.addWidget(make_label(label, "mutedText", False))
            row.addWidget(make_label(value, "", False), 1)
            self.status_rows.addLayout(row)
        self.refresh_ai_settings()

    def refresh_ai_settings(self) -> None:
        settings = self.controller.get_ai_settings()
        self.ai_enabled_check.setChecked(bool(settings.get("ai_enabled", False)))
        self.ai_base_url_edit.setText(str(settings.get("ai_base_url") or ""))
        self.ai_model_edit.setText(str(settings.get("ai_model") or ""))
        self.ai_key_edit.setText(str(settings.get("ai_api_key") or ""))
        self.ai_timeout_spin.setValue(int(settings.get("ai_timeout") or 20))

    def save_ai_settings(self) -> None:
        saved = self.controller.save_ai_settings(
            ai_enabled=self.ai_enabled_check.isChecked(),
            ai_base_url=self.ai_base_url_edit.text().strip(),
            ai_model=self.ai_model_edit.text().strip(),
            ai_api_key=self.ai_key_edit.text().strip(),
            ai_timeout=self.ai_timeout_spin.value(),
        )
        self.append_log(
            "AI 配置已保存："
            f"enabled={saved.get('ai_enabled')}, model={saved.get('ai_model') or '-'}, timeout={saved.get('ai_timeout')}"
        )

    def _request_full_archive_rebuild(self) -> None:
        self.append_log("已请求全量重建归档任务。")
        self.full_archive_requested.emit()

    def refresh_state_async(self) -> None:
        self.append_log("正在刷新连接状态 ...")
        run_async(
            self.thread_pool,
            self.controller.build_session_state,
            self._handle_state_refreshed,
            self._handle_error,
            None,
            True,
            True,
        )

    def _handle_state_refreshed(self, state: Any) -> None:
        self.controller.apply_session_state(state)
        self.refresh_state()

    def detect_api(self) -> None:
        self.append_log("开始检测 API ...")
        run_async(
            self.thread_pool,
            self.controller.bootstrap.is_api_ready,
            lambda result: self._handle_api_detected(bool(result)),
            self._handle_error,
        )

    def _handle_api_detected(self, ready: bool) -> None:
        self.append_log("API 状态：在线" if ready else "API 状态：离线")
        self.refresh_state_async()

    def start_api(self) -> None:
        self.append_log("尝试启动本地 API ...")
        run_async(
            self.thread_pool,
            self.controller.bootstrap.ensure_api_ready,
            lambda _: self._handle_api_started(),
            self._handle_error,
        )

    def _handle_api_started(self) -> None:
        self.append_log("本地 API 已启动。")
        self.refresh_state_async()

    def detect_cookie(self) -> None:
        self.append_log("开始检测 Cookie ...")
        run_async(
            self.thread_pool,
            self.controller.bootstrap.is_cookie_valid,
            lambda valid: self._handle_cookie_detected(bool(valid)),
            self._handle_error,
        )

    def _handle_cookie_detected(self, valid: bool) -> None:
        self.append_log("Cookie 状态：有效" if valid else "Cookie 状态：无效")
        self.refresh_state_async()

    def clear_cookie(self) -> None:
        self.controller.bootstrap.clear_saved_cookie()
        self.controller.apply_initial_local_state()
        self.append_log("本地 Cookie 已清空。")
        self.refresh_state()

    def start_qr_login(self) -> None:
        self.append_log("开始生成二维码 ...")
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
            self.qr_label.setText("当前环境未安装 qrcode，已显示登录链接。")
        self.qr_url_label.setText(qr_url)
        self.append_log("二维码已生成，请使用网易云音乐 App 扫码。")
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
            self.append_log("等待扫码 ...")
            return
        if code == 802:
            self.append_log("已扫码，请在手机上确认登录。")
            return
        if code == 803:
            self.append_log("登录成功，状态已刷新。")
            self.poll_timer.stop()
            self.controller.apply_startup_authenticated_state()
            self.refresh_state_async()
            return
        if code == 800:
            self.poll_timer.stop()
            self.append_log("二维码已过期，请重新生成。")
            return
        self.append_log(f"二维码状态返回: {code}")

    def _handle_error(self, error_text: str) -> None:
        message = error_text.strip().splitlines()[-1]
        self.set_error(message)
        self.append_log(message)
