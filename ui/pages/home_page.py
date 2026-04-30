from __future__ import annotations

from typing import Any, Dict

from PySide6 import QtCore, QtWidgets

from ui.widgets.common import make_label


class SummaryCard(QtWidgets.QFrame):
    def __init__(self, title: str, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("summaryCard")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        layout.addWidget(make_label(title, "sectionTitle", False))
        self.body = QtWidgets.QVBoxLayout()
        self.body.setSpacing(8)
        layout.addLayout(self.body)
        layout.addStretch(1)

    def _clear_layout(self, layout: QtWidgets.QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            child_widget = item.widget()
            child_layout = item.layout()
            if child_layout:
                self._clear_layout(child_layout)
                child_layout.deleteLater()
            if child_widget:
                child_widget.deleteLater()

    def set_rows(self, rows: list[tuple[str, str]]) -> None:
        self._clear_layout(self.body)
        for key, value in rows:
            line = QtWidgets.QHBoxLayout()
            line.setSpacing(8)
            key_label = make_label(key, "mutedText", False)
            key_label.setMinimumWidth(76)
            key_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
            value_label = make_label(value or "-", "", True)
            value_label.setWordWrap(True)
            value_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
            line.addWidget(key_label, 0)
            line.addWidget(value_label, 1)
            self.body.addLayout(line)


class HomePage(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(20)

        header = QtWidgets.QVBoxLayout()
        header.setSpacing(4)
        header.addWidget(make_label("首页", "pageTitle", False))
        layout.addLayout(header)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)
        layout.addLayout(grid)

        self.connection_card = SummaryCard("当前连接状态")
        self.friend_card = SummaryCard("当前好友摘要")
        self.playlist_card = SummaryCard("当前影子歌单摘要")
        self.overview_card = SummaryCard("数据概览")

        grid.addWidget(self.connection_card, 0, 0)
        grid.addWidget(self.friend_card, 0, 1)
        grid.addWidget(self.playlist_card, 1, 0)
        grid.addWidget(self.overview_card, 1, 1)
        layout.addStretch(1)

    def refresh_content(self, snapshot: Dict[str, Any]) -> None:
        connection = snapshot.get("connection", {})
        friend = snapshot.get("friend", {})
        playlist = snapshot.get("shadow_playlist", {})
        overview = snapshot.get("overview", {})

        self.connection_card.set_rows(
            [
                ("当前模式", str(connection.get("mode") or "-")),
                ("API 状态", str(connection.get("api_status") or "-")),
                ("Cookie 状态", str(connection.get("cookie_status") or "-")),
                ("账号状态", str(connection.get("account_status") or "-")),
            ]
        )
        self.friend_card.set_rows(
            [
                ("昵称", str(friend.get("nickname") or "-")),
                ("UID", str(friend.get("uid") or "-")),
                ("头像", "已加载占位" if friend.get("avatar_url") else "暂无"),
                ("最近使用", str(friend.get("last_used_at") or "-")),
            ]
        )
        self.playlist_card.set_rows(
            [
                ("名称", str(playlist.get("name") or "-")),
                ("歌单 ID", str(playlist.get("playlist_id") or "-")),
                ("当前策略", str(playlist.get("strategy") or "-")),
                ("是否私密", "是" if playlist.get("is_private") else "否"),
                ("最近设置", str(playlist.get("last_set_at") or "-")),
            ]
        )
        self.overview_card.set_rows(
            [
                ("聊天记录数量", str(overview.get("chat_count") or 0)),
                ("歌曲分享数量", str(overview.get("song_share_count") or 0)),
                ("候选歌曲数量", str(overview.get("candidate_count") or 0)),
                ("最近一次生成摘要", str(overview.get("last_build_summary") or 0)),
            ]
        )
