from __future__ import annotations

from typing import Any, Dict, List

from PySide6 import QtCore, QtGui, QtNetwork, QtWidgets

from core.app_controller import AppController
from services.parser import extract_image_preview_url
from ui.widgets.common import make_button, make_label, run_async
from ui.widgets.date_availability import ActiveDateCalendar, apply_active_dates, attach_active_calendar


class ChatImagePreview(QtWidgets.QLabel):
    _manager: QtNetwork.QNetworkAccessManager | None = None
    _cache: dict[str, QtGui.QPixmap] = {}

    def __init__(self, image_url: str, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._image_url = image_url
        self._full_pixmap: QtGui.QPixmap | None = None
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setWordWrap(True)
        self.setMinimumSize(180, 120)
        self.setMaximumSize(320, 220)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setStyleSheet(
            "background: rgba(255, 255, 255, 0.04);"
            "border: 1px solid rgba(255, 255, 255, 0.08);"
            "border-radius: 16px;"
            "padding: 8px;"
        )
        if not image_url:
            self.setText("图片消息")
            return
        if image_url in self._cache:
            self._apply_pixmap(self._cache[image_url])
            return
        self.setText("图片加载中...")
        self._load()

    @classmethod
    def _network_manager(cls) -> QtNetwork.QNetworkAccessManager:
        if cls._manager is None:
            cls._manager = QtNetwork.QNetworkAccessManager()
        return cls._manager

    def _scaled_pixmap(self, pixmap: QtGui.QPixmap) -> QtGui.QPixmap:
        return pixmap.scaled(
            304,
            204,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation,
        )

    def _apply_pixmap(self, pixmap: QtGui.QPixmap) -> None:
        self._full_pixmap = pixmap
        scaled = self._scaled_pixmap(pixmap)
        self.setText("")
        self.setPixmap(scaled)
        self.setFixedSize(max(180, scaled.width() + 16), max(120, scaled.height() + 16))

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() != QtCore.Qt.LeftButton:
            super().mouseDoubleClickEvent(event)
            return
        if not self._full_pixmap or self._full_pixmap.isNull():
            return
        dialog = QtWidgets.QDialog(self.window())
        dialog.setWindowTitle("图片预览")
        dialog.resize(960, 720)
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        image_label = QtWidgets.QLabel()
        image_label.setAlignment(QtCore.Qt.AlignCenter)
        image_label.setPixmap(self._full_pixmap)
        scroll.setWidget(image_label)
        layout.addWidget(scroll)
        dialog.exec()

    def _load(self) -> None:
        reply = self._network_manager().get(QtNetwork.QNetworkRequest(QtCore.QUrl(self._image_url)))
        self.destroyed.connect(reply.abort)

        def _finish() -> None:
            try:
                if reply.error() == QtNetwork.QNetworkReply.NoError:
                    pixmap = QtGui.QPixmap()
                    pixmap.loadFromData(reply.readAll())
                    if not pixmap.isNull():
                        self._cache[self._image_url] = pixmap
                        try:
                            self._apply_pixmap(pixmap)
                            return
                        except RuntimeError:
                            return
                try:
                    self.setText("图片加载失败")
                except RuntimeError:
                    return
            finally:
                reply.deleteLater()

        reply.finished.connect(_finish)


class ChatPage(QtWidgets.QWidget):
    def __init__(self, controller: AppController, thread_pool: QtCore.QThreadPool, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.thread_pool = thread_pool
        self._active_dates_key: tuple[str, str, int] = ("", "all", 3)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(20)

        layout.addWidget(make_label("聊天记录", "pageTitle", False))

        self.filter_card = QtWidgets.QFrame()
        self.filter_card.setObjectName("filterCard")
        filter_layout = QtWidgets.QVBoxLayout(self.filter_card)
        filter_layout.setContentsMargins(18, 18, 18, 18)
        filter_layout.setSpacing(14)
        layout.addWidget(self.filter_card)

        self.scope_combo = QtWidgets.QComboBox()
        self.scope_combo.addItems(["全部历史", "最近", "特定页数"])
        self.pages_spin = QtWidgets.QSpinBox()
        self.pages_spin.setRange(1, 99)
        self.pages_spin.setValue(3)
        self.sender_combo = QtWidgets.QComboBox()
        self.sender_combo.addItems(["双方", "我方", "好友"])
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(["全部", "文本", "歌曲", "图片", "视频", "未知"])
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["全部", "按日期", "按时间段", "按关键词"])
        self.date_edit = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.start_edit = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.start_edit.setCalendarPopup(True)
        self.end_edit = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.end_edit.setCalendarPopup(True)
        attach_active_calendar(self.date_edit)
        attach_active_calendar(self.start_edit)
        attach_active_calendar(self.end_edit)
        self.keyword_edit = QtWidgets.QLineEdit()
        self.keyword_edit.setPlaceholderText("输入关键词")

        self.scope_field = self._create_field("范围", self.scope_combo)
        self.pages_field = self._create_field("页数", self.pages_spin)
        self.sender_field = self._create_field("发送方", self.sender_combo)
        self.type_field = self._create_field("消息类型", self.type_combo)
        self.mode_field = self._create_field("查询方式", self.mode_combo)
        self.date_field = self._create_field("日期", self.date_edit)
        self.start_field = self._create_field("开始时间", self.start_edit)
        self.end_field = self._create_field("结束时间", self.end_edit)
        self.keyword_field = self._create_field("关键词", self.keyword_edit)
        self.filter_top_row = QtWidgets.QHBoxLayout()
        self.filter_top_row.setSpacing(14)
        self.filter_top_row.setAlignment(QtCore.Qt.AlignLeft)
        filter_layout.addLayout(self.filter_top_row)
        self.filter_top_row.addWidget(self.scope_field, 1)
        self.filter_top_row.addWidget(self.pages_field, 1)
        self.filter_top_row.addWidget(self.sender_field, 1)
        self.filter_top_row.addWidget(self.type_field, 1)
        self.filter_top_row.addWidget(self.mode_field, 1)
        self.filter_top_row.addStretch(1)

        self.filter_bottom_row = QtWidgets.QHBoxLayout()
        self.filter_bottom_row.setSpacing(14)
        self.filter_bottom_row.setAlignment(QtCore.Qt.AlignLeft)
        filter_layout.addLayout(self.filter_bottom_row)
        self.filter_bottom_row.addWidget(self.date_field, 1)
        self.filter_bottom_row.addWidget(self.start_field, 1)
        self.filter_bottom_row.addWidget(self.end_field, 1)
        self.filter_bottom_row.addWidget(self.keyword_field, 1)
        self.filter_bottom_row.addStretch(1)

        button_row = QtWidgets.QHBoxLayout()
        self.query_button = make_button("查询聊天记录", "primaryButton")
        self.clear_button = make_button("清空条件", "secondaryButton")
        self.status_label = make_label("等待查询。", "mutedText", False)
        button_row.addWidget(self.query_button)
        button_row.addWidget(self.clear_button)
        button_row.addStretch(1)
        button_row.addWidget(self.status_label)
        filter_layout.addLayout(button_row)

        header = QtWidgets.QHBoxLayout()
        header.addWidget(make_label("消息结果", "sectionTitle", False))
        self.summary_badge = make_label("0 条结果", "statusBadge", False)
        header.addStretch(1)
        header.addWidget(self.summary_badge)
        layout.addLayout(header)

        self.result_layout = QtWidgets.QVBoxLayout()
        self.result_layout.setSpacing(12)
        layout.addLayout(self.result_layout)
        layout.addStretch(1)

        self.query_button.clicked.connect(self.run_query)
        self.clear_button.clicked.connect(self.reset_filters)
        self.scope_combo.currentTextChanged.connect(self._update_filter_visibility)
        self.scope_combo.currentTextChanged.connect(lambda _text: self.refresh_date_availability(force=True))
        self.pages_spin.valueChanged.connect(lambda _value: self.refresh_date_availability(force=True))
        self.mode_combo.currentTextChanged.connect(self._update_filter_visibility)
        self.start_edit.dateChanged.connect(lambda _date: self._sync_range_boundaries())
        self._update_filter_visibility()
        self.refresh_date_availability(force=True)
        self._sync_range_boundaries()
        self.render_results([], {"count": 0})

    def refresh_date_availability(self, force: bool = False) -> None:
        friend = self.controller.current_friend()
        uid = friend.uid if friend else ""
        scope_map = {"全部历史": "all", "最近": "recent", "特定页数": "pages"}
        scope = scope_map.get(self.scope_combo.currentText(), "all")
        pages = self.pages_spin.value()
        key = (uid, scope, pages)
        if not force and key == self._active_dates_key:
            return
        self._active_dates_key = key
        active_dates = self.controller.get_chat_active_dates(scope=scope, pages=pages) if uid else []
        apply_active_dates([self.date_edit, self.start_edit, self.end_edit], active_dates)
        self._sync_range_boundaries()

    def _sync_range_boundaries(self) -> None:
        start_date = self.start_edit.date()
        end_calendar = self.end_edit.calendarWidget()
        max_date = self.end_edit.maximumDate()
        if start_date > max_date:
            start_date = max_date
        with QtCore.QSignalBlocker(self.end_edit):
            self.end_edit.setMinimumDate(start_date)
            if self.end_edit.date() < start_date:
                self.end_edit.setDate(start_date)
        if isinstance(end_calendar, ActiveDateCalendar):
            with QtCore.QSignalBlocker(end_calendar):
                end_calendar.setMinimumDate(start_date)
            end_calendar.updateCells()

    def _create_field(self, label: str, widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(make_label(label, "mutedText", False))
        layout.addWidget(widget)
        return container

    def _update_filter_visibility(self) -> None:
        scope = self.scope_combo.currentText()
        mode = self.mode_combo.currentText()
        self.pages_field.setVisible(scope == "特定页数")
        self.date_field.setVisible(mode == "按日期")
        show_range = mode == "按时间段"
        self.start_field.setVisible(show_range)
        self.end_field.setVisible(show_range)
        self.keyword_field.setVisible(mode == "按关键词")

    def _collect_filters(self) -> Dict[str, Any]:
        scope_map = {"全部历史": "all", "最近": "recent", "特定页数": "pages"}
        sender_map = {"双方": "all", "我方": "self", "好友": "friend"}
        type_map = {"全部": "all", "文本": "text", "歌曲": "song", "图片": "image", "视频": "video", "未知": "unknown"}
        mode_map = {"全部": "all", "按日期": "date", "按时间段": "range", "按关键词": "keyword"}
        query_mode = mode_map[self.mode_combo.currentText()]
        return {
            "scope": scope_map[self.scope_combo.currentText()],
            "pages": self.pages_spin.value(),
            "sender_scope": sender_map[self.sender_combo.currentText()],
            "message_type": type_map[self.type_combo.currentText()],
            "query_mode": query_mode,
            "target_date": self.date_edit.date().toString("yyyy-MM-dd") if query_mode == "date" else None,
            "start_datetime": self.start_edit.date().toString("yyyy-MM-dd") if query_mode == "range" else None,
            "end_datetime": self.end_edit.date().toString("yyyy-MM-dd") if query_mode == "range" else None,
            "keyword": self.keyword_edit.text().strip() if query_mode == "keyword" else None,
        }

    def reset_filters(self) -> None:
        self.scope_combo.setCurrentIndex(1)
        self.pages_spin.setValue(3)
        self.sender_combo.setCurrentIndex(0)
        self.type_combo.setCurrentIndex(0)
        self.mode_combo.setCurrentIndex(0)
        self.keyword_edit.clear()
        self._update_filter_visibility()
        self.status_label.setText("已清空条件。")

    def run_query(self) -> None:
        self.query_button.setEnabled(False)
        self.status_label.setText("查询中...")
        run_async(
            self.thread_pool,
            self.controller.query_chat_history,
            self._on_query_success,
            self._on_query_error,
            lambda: self.query_button.setEnabled(True),
            **self._collect_filters(),
        )

    def _on_query_success(self, payload: Dict[str, Any]) -> None:
        self.status_label.setText("查询完成。")
        self.render_results(payload.get("items", []), payload.get("summary", {}))
        self.refresh_date_availability(force=True)

    def _on_query_error(self, error_text: str) -> None:
        self.status_label.setText("查询失败。")
        self.render_error(error_text.strip().splitlines()[-1])

    def _clear_results(self) -> None:
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def render_results(self, items: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
        self._clear_results()
        self.summary_badge.setText(f"{summary.get('count', 0)} 条结果")
        if not items:
            self.result_layout.addWidget(make_label("当前没有命中聊天记录结果。", "mutedText"))
            return
        for item in items:
            sender = "好友" if item.get("direction") == "friend" else "我方"
            is_self = item.get("direction") != "friend"
            row = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)
            bubble = QtWidgets.QFrame()
            bubble.setObjectName("messageBubbleSelf" if is_self else "messageBubbleFriend")
            bubble.setMaximumWidth(760)
            bubble_layout = QtWidgets.QVBoxLayout(bubble)
            bubble_layout.setContentsMargins(14, 12, 14, 12)
            bubble_layout.setSpacing(8)
            head_label = make_label(f"{sender} · {item.get('msg_type') or 'unknown'}", "messageSelfText" if is_self else "messageFriendText", True)
            head_label.setWordWrap(True)
            bubble_layout.addWidget(head_label)
            time_label = make_label(item.get("msg_time_str") or "-", "messageSelfMeta" if is_self else "messageFriendMeta", False)
            bubble_layout.addWidget(time_label)
            content = item.get("text_content") or item.get("song_name") or "[暂无内容]"
            if item.get("msg_type") == "image":
                image_url = extract_image_preview_url(item.get("raw_msg_json"))
                bubble_layout.addWidget(ChatImagePreview(image_url))
                content = f"图片消息 · {item.get('text_content')}" if item.get("text_content") else "图片消息"
            elif item.get("msg_type") == "video":
                content = item.get("text_content") or "[视频消息占位]"
            content_label = make_label(content, "messageSelfText" if is_self else "messageFriendText", True)
            content_label.setWordWrap(True)
            bubble_layout.addWidget(content_label)
            if item.get("song_name"):
                song_label = make_label(
                    f"歌曲：{item.get('song_name')} · {item.get('artist_name') or '未知歌手'}",
                    "messageSelfMeta" if is_self else "messageFriendMeta",
                    True,
                )
                song_label.setWordWrap(True)
                bubble_layout.addWidget(song_label)
            if is_self:
                row_layout.addStretch(1)
                row_layout.addWidget(bubble, 0, QtCore.Qt.AlignRight)
            else:
                row_layout.addWidget(bubble, 0, QtCore.Qt.AlignLeft)
                row_layout.addStretch(1)
            self.result_layout.addWidget(row)

    def render_error(self, message: str) -> None:
        self._clear_results()
        self.summary_badge.setText("错误状态")
        self.result_layout.addWidget(make_label(message or "查询失败。", "mutedText"))
