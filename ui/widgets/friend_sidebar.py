from __future__ import annotations

from typing import List

from PySide6 import QtCore, QtGui, QtNetwork, QtWidgets

from core.models import FriendEntry
from ui.widgets.common import make_label
from ui.widgets.navigation import SegmentedNavigation


class AvatarLoader:
    _manager: QtNetwork.QNetworkAccessManager | None = None
    _cache: dict[str, QtGui.QPixmap] = {}

    @classmethod
    def _network_manager(cls) -> QtNetwork.QNetworkAccessManager:
        if cls._manager is None:
            cls._manager = QtNetwork.QNetworkAccessManager()
        return cls._manager

    @classmethod
    def _fallback_pixmap(cls, text: str, size: int) -> QtGui.QPixmap:
        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setBrush(QtGui.QColor(52, 52, 52))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)
        painter.setPen(QtGui.QColor("#f3f7fb"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(max(10, size // 3))
        painter.setFont(font)
        painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, (text or "友")[:1].upper())
        painter.end()
        return pixmap

    @classmethod
    def _circular_pixmap(cls, pixmap: QtGui.QPixmap, size: int) -> QtGui.QPixmap:
        if pixmap.isNull():
            return cls._fallback_pixmap("", size)
        scaled = pixmap.scaled(
            size,
            size,
            QtCore.Qt.KeepAspectRatioByExpanding,
            QtCore.Qt.SmoothTransformation,
        )
        source = QtCore.QRect(
            max(0, (scaled.width() - size) // 2),
            max(0, (scaled.height() - size) // 2),
            size,
            size,
        )
        circular = QtGui.QPixmap(size, size)
        circular.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(circular)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        path = QtGui.QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        painter.drawPixmap(QtCore.QRect(0, 0, size, size), scaled, source)
        painter.end()
        return circular

    @classmethod
    def set_avatar(cls, label: QtWidgets.QLabel, avatar_url: str, fallback_text: str) -> None:
        size = max(36, min(label.width() or 36, label.height() or 36))
        if not avatar_url:
            label.setPixmap(cls._fallback_pixmap(fallback_text, size))
            return
        if avatar_url in cls._cache:
            label.setPixmap(cls._circular_pixmap(cls._cache[avatar_url], size))
            return

        label.setPixmap(cls._fallback_pixmap(fallback_text, size))
        request = QtNetwork.QNetworkRequest(QtCore.QUrl(avatar_url))
        reply = cls._network_manager().get(request)
        label.destroyed.connect(reply.abort)

        def _finish() -> None:
            try:
                if reply.error() == QtNetwork.QNetworkReply.NoError:
                    pixmap = QtGui.QPixmap()
                    pixmap.loadFromData(reply.readAll())
                    if not pixmap.isNull():
                        cls._cache[avatar_url] = pixmap
                        try:
                            label.setPixmap(cls._circular_pixmap(pixmap, size))
                        except RuntimeError:
                            pass
            finally:
                reply.deleteLater()

        reply.finished.connect(_finish)


class ClickableFrame(QtWidgets.QFrame):
    clicked = QtCore.Signal()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class FriendSidebar(QtWidgets.QWidget):
    friend_selected = QtCore.Signal(object)
    list_type_changed = QtCore.Signal(str)
    keyword_changed = QtCore.Signal(str)
    pin_requested = QtCore.Signal(str)
    unpin_requested = QtCore.Signal(str)
    delete_requested = QtCore.Signal(str)
    clear_recent_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("friendSidebarShell")
        self._current_uid = ""
        self._current_is_pinned = False
        self._list_type = "all"
        self._visible_friends: List[FriendEntry] = []

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        self.info_bar = QtWidgets.QFrame()
        self.info_bar.setObjectName("friendInfoBar")
        info_layout = QtWidgets.QHBoxLayout(self.info_bar)
        info_layout.setContentsMargins(12, 12, 12, 12)
        info_layout.setSpacing(12)
        self.info_avatar = QtWidgets.QLabel()
        self.info_avatar.setMinimumSize(44, 44)
        self.info_avatar.setMaximumSize(44, 44)
        self.info_avatar.setObjectName("friendInfoAvatar")
        info_layout.addWidget(self.info_avatar, 0, QtCore.Qt.AlignVCenter)
        info_text_col = QtWidgets.QVBoxLayout()
        info_text_col.setSpacing(4)
        self.info_name = make_label("当前好友", "sectionTitle", False)
        self.info_uid = make_label("UID -", "mutedText", False)
        info_text_col.addWidget(self.info_name)
        info_text_col.addWidget(self.info_uid)
        info_layout.addLayout(info_text_col, 1)
        outer.addWidget(self.info_bar)

        self.type_nav = SegmentedNavigation([("all", "全部好友"), ("recent", "最近好友")], fill_width=True)
        self.type_nav.changed.connect(self._on_list_type_changed)
        outer.addWidget(self.type_nav)

        search_row = QtWidgets.QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(10)
        self.tool_button = QtWidgets.QToolButton()
        self.tool_button.setObjectName("friendToolButton")
        self.tool_button.setText("⚙")
        self.tool_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.tool_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.tool_button.setFixedSize(56, 42)
        self.tool_menu = QtWidgets.QMenu(self.tool_button)
        self.tool_button.setMenu(self.tool_menu)
        search_row.addWidget(self.tool_button, 0, QtCore.Qt.AlignVCenter)

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("搜索昵称或 UID")
        self.search_edit.setMinimumHeight(42)
        self.search_edit.textChanged.connect(self.keyword_changed.emit)
        search_row.addWidget(self.search_edit, 1)
        outer.addLayout(search_row)

        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setObjectName("friendListScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll_area.viewport().setObjectName("friendListViewport")
        self.scroll_area.viewport().setAttribute(QtCore.Qt.WA_Hover, True)

        self.list_container = QtWidgets.QWidget()
        self.list_container.setObjectName("friendListShell")
        self.list_container.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.list_layout = QtWidgets.QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(10, 10, 8, 10)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch(1)
        self.scroll_area.setWidget(self.list_container)
        outer.addWidget(self.scroll_area, 1)
        self.type_nav.set_current("all")
        self._rebuild_tool_menu()

    def _on_list_type_changed(self, list_type: str) -> None:
        self._list_type = list_type
        self.list_type_changed.emit(list_type)
        self._rebuild_tool_menu()
        self.render_friends(self._visible_friends)

    def _rebuild_tool_menu(self) -> None:
        self.tool_menu.clear()
        uid = self._current_uid
        pin_action = self.tool_menu.addAction("置顶")
        pin_action.triggered.connect(lambda checked=False, friend_uid=uid: self.pin_requested.emit(friend_uid))
        unpin_action = self.tool_menu.addAction("取消置顶")
        unpin_action.triggered.connect(lambda checked=False, friend_uid=uid: self.unpin_requested.emit(friend_uid))

        has_uid = bool(uid)
        pin_action.setEnabled(has_uid and not self._current_is_pinned)
        unpin_action.setEnabled(has_uid and self._current_is_pinned)

        if self._list_type == "recent":
            delete_action = self.tool_menu.addAction("删除")
            delete_action.triggered.connect(lambda checked=False, friend_uid=uid: self.delete_requested.emit(friend_uid))
            delete_action.setEnabled(has_uid)
            clear_action = self.tool_menu.addAction("删除列表")
            clear_action.triggered.connect(self.clear_recent_requested.emit)

    def set_current_friend(self, friend: FriendEntry | None) -> None:
        self._current_uid = friend.uid if friend else ""
        visible_pinned = next((item.is_pinned for item in self._visible_friends if item.uid == self._current_uid), None)
        self._current_is_pinned = visible_pinned if visible_pinned is not None else (bool(friend.is_pinned) if friend else False)
        self.info_name.setText(friend.nickname if friend else "当前好友")
        self.info_uid.setText(f"UID {friend.uid}" if friend else "UID -")
        AvatarLoader.set_avatar(self.info_avatar, friend.avatar_url if friend else "", friend.nickname if friend else "友")
        self._rebuild_tool_menu()
        self.render_friends(self._visible_friends)

    def set_list_type(self, list_type: str) -> None:
        self._list_type = list_type
        self.type_nav.set_current(list_type)
        self._rebuild_tool_menu()
        self.render_friends(self._visible_friends)

    def set_search_keyword(self, keyword: str) -> None:
        self.search_edit.blockSignals(True)
        self.search_edit.setText(keyword)
        self.search_edit.blockSignals(False)

    def render_friends(self, friends: List[FriendEntry]) -> None:
        self._visible_friends = friends
        if self._current_uid:
            self._current_is_pinned = any(item.uid == self._current_uid and item.is_pinned for item in friends)
        self._rebuild_tool_menu()
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not friends:
            empty = make_label("当前没有好友数据。", "mutedText", False)
            empty.setAlignment(QtCore.Qt.AlignCenter)
            self.list_layout.insertWidget(0, empty)
            return

        for friend in friends:
            card = ClickableFrame()
            card.setObjectName("friendItem")
            card.setProperty("selected", friend.uid == self._current_uid)
            card.setCursor(QtCore.Qt.PointingHandCursor)
            card.setMinimumHeight(100)
            card.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            card.clicked.connect(lambda payload=friend: self.friend_selected.emit(payload))

            row = QtWidgets.QHBoxLayout(card)
            row.setContentsMargins(14, 12, 14, 12)
            row.setSpacing(12)

            avatar = QtWidgets.QLabel()
            avatar.setAlignment(QtCore.Qt.AlignCenter)
            avatar.setObjectName("friendAvatar")
            avatar.setMinimumSize(36, 36)
            avatar.setMaximumSize(36, 36)
            AvatarLoader.set_avatar(avatar, friend.avatar_url, friend.nickname)
            row.addWidget(avatar, 0, QtCore.Qt.AlignVCenter)

            text_col = QtWidgets.QVBoxLayout()
            text_col.setContentsMargins(0, 2, 0, 2)
            text_col.setSpacing(6)
            name_label = make_label(friend.nickname or "未命名好友", "sectionTitle", False)
            name_label.setStyleSheet("font-size: 15px;")
            name_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
            name_row = QtWidgets.QHBoxLayout()
            name_row.setContentsMargins(0, 0, 0, 0)
            name_row.setSpacing(8)
            name_row.addWidget(name_label, 1)
            if friend.is_pinned:
                pinned_state = make_label("置顶", "friendPinnedState", False)
                pinned_state.setWordWrap(False)
                pinned_state.setAlignment(QtCore.Qt.AlignCenter)
                pinned_state.setMinimumSize(58, 34)
                pinned_state.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
                name_row.addWidget(pinned_state, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
            text_col.addLayout(name_row)
            if self._list_type == "recent":
                last_used = friend.last_used_at or "-"
                second_line = make_label(f"最近使用 {last_used}", "mutedText", False)
            else:
                second_line = make_label(f"UID {friend.uid}", "mutedText", False)
            second_line.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
            text_col.addWidget(second_line)
            row.addLayout(text_col, 1)

            self.list_layout.insertWidget(self.list_layout.count() - 1, card)
            card.style().unpolish(card)
            card.style().polish(card)
