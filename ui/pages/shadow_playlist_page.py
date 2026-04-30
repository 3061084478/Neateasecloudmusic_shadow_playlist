from __future__ import annotations

from typing import Any, Dict, List

from PySide6 import QtCore, QtGui, QtWidgets

from core.app_controller import AppController
from ui.theme import PALETTES
from ui.widgets.common import make_button, make_label, run_async
from ui.widgets.date_availability import ActiveDateCalendar, apply_active_dates, attach_active_calendar
from ui.widgets.navigation import AnimatedStackedWidget, SegmentedNavigation


class ShadowPlaylistPage(QtWidgets.QWidget):
    palette_changed = QtCore.Signal(str)

    def __init__(self, controller: AppController, thread_pool: QtCore.QThreadPool, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.thread_pool = thread_pool
        self._active_dates_key: tuple[str, str, int] = ("", "all", 3)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(20)
        layout.addWidget(make_label("影子歌单", "pageTitle", False))

        self.subnav = SegmentedNavigation(
            [("selector", "选择 / 启动设置"), ("generator", "生成影子歌单"), ("status", "查看状态")],
            object_name="shadowSegmentedButton",
        )
        layout.addWidget(self.subnav)

        self.stack = AnimatedStackedWidget()
        layout.addWidget(self.stack, 1)

        self.selector_page = self._build_selector_page()
        self.generator_page = self._build_generator_page()
        self.status_page = self._build_status_page()

        for widget in (self.selector_page, self.generator_page, self.status_page):
            self.stack.addWidget(widget)

        self.subnav.changed.connect(self._switch_subpage)
        self.subnav.set_current("selector")
        self.subnav.set_accent_color(PALETTES["selector"]["accent"])
        self.refresh_date_availability(force=True)
        self.refresh_status()

    def _switch_subpage(self, key: str) -> None:
        page_map = {"selector": 0, "generator": 1, "status": 2}
        self.stack.slide_to_index(page_map[key])
        self.subnav.set_accent_color(PALETTES[key]["accent"])
        self.palette_changed.emit(key)
        if key == "status":
            self.refresh_status()

    def _build_selector_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(18)

        summary_card = QtWidgets.QFrame()
        summary_card.setObjectName("card")
        summary_layout = QtWidgets.QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(18, 18, 18, 18)
        summary_layout.setSpacing(8)
        summary_layout.addWidget(make_label("当前已记录影子歌单", "sectionTitle", False))
        self.selector_summary = make_label("等待读取。", "mutedText", True)
        summary_layout.addWidget(self.selector_summary)
        layout.addWidget(summary_card)

        form_card = QtWidgets.QFrame()
        form_card.setObjectName("filterCard")
        form_layout = QtWidgets.QGridLayout(form_card)
        form_layout.setContentsMargins(18, 18, 18, 18)
        form_layout.setHorizontalSpacing(14)
        form_layout.setVerticalSpacing(14)
        layout.addWidget(form_card)

        self.strategy_combo = QtWidgets.QComboBox()
        self.strategy_combo.addItems(["使用当前已记录歌单", "选择自己已有的其他歌单", "手动输入歌单 ID", "放弃当前记录并自动新建"])
        self.owned_playlist_combo = QtWidgets.QComboBox()
        self.owned_playlist_combo.addItem("请选择已有歌单", "")
        self.manual_playlist_edit = QtWidgets.QLineEdit()
        self.manual_playlist_edit.setPlaceholderText("输入歌单 ID")
        self.new_playlist_name_edit = QtWidgets.QLineEdit()
        self.new_playlist_name_edit.setPlaceholderText("新歌单名称")
        self.private_checkbox = QtWidgets.QCheckBox("设为私密歌单")
        self.strategy_field = self._create_field("当前策略", self.strategy_combo)
        self.owned_playlist_field = self._create_field("已有歌单", self.owned_playlist_combo)
        self.manual_playlist_field = self._create_field("手动歌单 ID", self.manual_playlist_edit)
        self.new_playlist_name_field = self._create_field("新歌单名称", self.new_playlist_name_edit)

        form_layout.addWidget(self.strategy_field, 0, 0, 1, 2)
        form_layout.addWidget(self.owned_playlist_field, 1, 0, 1, 2)
        form_layout.addWidget(self.manual_playlist_field, 2, 0, 1, 2)
        form_layout.addWidget(self.new_playlist_name_field, 3, 0)
        form_layout.addWidget(self.private_checkbox, 3, 1)

        button_row = QtWidgets.QHBoxLayout()
        self.save_selector_button = make_button("保存设置", "primaryButton")
        self.selector_status = make_label("尚未保存。", "mutedText", False)
        button_row.addWidget(self.save_selector_button)
        button_row.addStretch(1)
        button_row.addWidget(self.selector_status)
        form_layout.addLayout(button_row, 4, 0, 1, 2)

        self.strategy_combo.currentTextChanged.connect(self._update_selector_fields)
        self.save_selector_button.clicked.connect(self.save_selector_settings)
        self._update_selector_fields()
        layout.addStretch(1)
        return page

    def _update_selector_fields(self) -> None:
        strategy = self.strategy_combo.currentText()
        show_owned = strategy == "选择自己已有的其他歌单"
        self.owned_playlist_field.setVisible(show_owned)
        self.manual_playlist_field.setVisible(strategy == "手动输入歌单 ID")
        self.new_playlist_name_field.setVisible(strategy == "放弃当前记录并自动新建")
        self.private_checkbox.setVisible(strategy == "放弃当前记录并自动新建")
        if show_owned:
            self._load_owned_playlists()

    def _build_generator_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(18)

        filter_card = QtWidgets.QFrame()
        filter_card.setObjectName("filterCard")
        form = QtWidgets.QVBoxLayout(filter_card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setSpacing(14)
        layout.addWidget(filter_card)

        self.gen_scope_combo = QtWidgets.QComboBox()
        self.gen_scope_combo.addItems(["全部历史", "最近", "特定页数", "本次新增"])
        self.gen_pages_spin = QtWidgets.QSpinBox()
        self.gen_pages_spin.setRange(1, 99)
        self.gen_pages_spin.setValue(3)
        self.gen_sender_combo = QtWidgets.QComboBox()
        self.gen_sender_combo.addItems(["双方", "我方", "好友"])
        self.gen_mode_combo = QtWidgets.QComboBox()
        self.gen_mode_combo.addItems(["全部", "按日期", "按时间段"])
        self.gen_date_edit = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.gen_date_edit.setCalendarPopup(True)
        self.gen_start_edit = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.gen_start_edit.setCalendarPopup(True)
        self.gen_end_edit = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.gen_end_edit.setCalendarPopup(True)
        attach_active_calendar(self.gen_date_edit)
        attach_active_calendar(self.gen_start_edit)
        attach_active_calendar(self.gen_end_edit)
        self.gen_gap_edit = QtWidgets.QLineEdit()
        self.gen_gap_edit.setPlaceholderText("留空表示不限制")
        self.gen_gap_edit.setValidator(QtGui.QIntValidator(1, 999, self))
        self.gen_max_songs_edit = QtWidgets.QLineEdit()
        self.gen_max_songs_edit.setPlaceholderText("留空表示不限制")
        self.gen_max_songs_edit.setValidator(QtGui.QIntValidator(1, 500, self))
        self.gen_keyword_edit = QtWidgets.QLineEdit()
        self.gen_keyword_edit.setPlaceholderText("关键词筛选")

        self.gen_scope_field = self._create_field("范围", self.gen_scope_combo)
        self.gen_pages_field = self._create_field("页数", self.gen_pages_spin)
        self.gen_sender_field = self._create_field("发送方", self.gen_sender_combo)
        self.gen_mode_field = self._create_field("查询方式", self.gen_mode_combo)
        self.gen_date_field = self._create_field("日期", self.gen_date_edit)
        self.gen_start_field = self._create_field("开始时间", self.gen_start_edit)
        self.gen_end_field = self._create_field("结束时间", self.gen_end_edit)
        self.gen_gap_field = self._create_field("最大时间间隔 (小时)", self.gen_gap_edit)
        self.gen_max_songs_field = self._create_field("最大歌曲数量", self.gen_max_songs_edit)
        self.gen_keyword_field = self._create_field("关键词", self.gen_keyword_edit)

        self.generator_top_row = QtWidgets.QHBoxLayout()
        self.generator_top_row.setSpacing(14)
        self.generator_top_row.setAlignment(QtCore.Qt.AlignLeft)
        form.addLayout(self.generator_top_row)
        self.generator_top_row.addWidget(self.gen_scope_field, 1)
        self.generator_top_row.addWidget(self.gen_pages_field, 1)
        self.generator_top_row.addWidget(self.gen_sender_field, 1)
        self.generator_top_row.addWidget(self.gen_mode_field, 1)
        self.generator_top_row.addStretch(1)

        self.generator_middle_row = QtWidgets.QHBoxLayout()
        self.generator_middle_row.setSpacing(14)
        self.generator_middle_row.setAlignment(QtCore.Qt.AlignLeft)
        form.addLayout(self.generator_middle_row)
        self.generator_middle_row.addWidget(self.gen_date_field, 1)
        self.generator_middle_row.addWidget(self.gen_start_field, 1)
        self.generator_middle_row.addWidget(self.gen_end_field, 1)
        self.generator_middle_row.addWidget(self.gen_keyword_field, 1)
        self.generator_middle_row.addStretch(1)

        self.generator_bottom_row = QtWidgets.QHBoxLayout()
        self.generator_bottom_row.setSpacing(14)
        self.generator_bottom_row.setAlignment(QtCore.Qt.AlignLeft)
        form.addLayout(self.generator_bottom_row)
        self.generator_bottom_row.addWidget(self.gen_gap_field, 1)
        self.generator_bottom_row.addWidget(self.gen_max_songs_field, 1)
        self.generator_bottom_row.addStretch(1)

        button_row = QtWidgets.QHBoxLayout()
        self.load_candidates_button = make_button("加载候选歌曲", "primaryButton")
        self.clear_generator_button = make_button("清空条件", "secondaryButton")
        self.generate_button = make_button("生成影子歌单", "secondaryButton")
        self.generator_status = make_label("等待加载候选。", "mutedText", False)
        button_row.addWidget(self.load_candidates_button)
        button_row.addWidget(self.clear_generator_button)
        button_row.addWidget(self.generate_button)
        button_row.addStretch(1)
        button_row.addWidget(self.generator_status)
        form.addLayout(button_row)

        tools_row = QtWidgets.QHBoxLayout()
        self.select_all_button = make_button("全选", "ghostButton")
        self.select_none_button = make_button("全不选", "ghostButton")
        self.invert_button = make_button("反选", "ghostButton")
        self.candidate_badge = make_label("候选 0 / 已选 0", "statusBadge", False)
        tools_row.addWidget(self.select_all_button)
        tools_row.addWidget(self.select_none_button)
        tools_row.addWidget(self.invert_button)
        tools_row.addStretch(1)
        tools_row.addWidget(self.candidate_badge)
        layout.addLayout(tools_row)

        self.candidate_layout = QtWidgets.QVBoxLayout()
        self.candidate_layout.setSpacing(12)
        layout.addLayout(self.candidate_layout)
        layout.addStretch(1)

        self.load_candidates_button.clicked.connect(self.load_candidates)
        self.clear_generator_button.clicked.connect(self.clear_generator_filters)
        self.generate_button.clicked.connect(self.generate_playlist)
        self.select_all_button.clicked.connect(lambda: self._set_candidate_selection(True))
        self.select_none_button.clicked.connect(lambda: self._set_candidate_selection(False))
        self.invert_button.clicked.connect(self._invert_candidate_selection)
        self.gen_scope_combo.currentTextChanged.connect(self._update_generator_fields)
        self.gen_scope_combo.currentTextChanged.connect(lambda _text: self.refresh_date_availability(force=True))
        self.gen_pages_spin.valueChanged.connect(lambda _value: self.refresh_date_availability(force=True))
        self.gen_mode_combo.currentTextChanged.connect(self._update_generator_fields)
        self.gen_start_edit.dateChanged.connect(lambda _date: self._sync_generator_range_boundaries())
        self._update_generator_fields()
        self._sync_generator_range_boundaries()
        self.render_candidates([])
        return page

    def _build_status_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(18)
        self.status_summary = make_label("等待读取状态。", "mutedText", True)
        layout.addWidget(self.status_summary)
        self.playlist_state_layout = QtWidgets.QVBoxLayout()
        self.playlist_state_layout.setSpacing(12)
        layout.addLayout(self.playlist_state_layout)
        layout.addStretch(1)
        return page

    def _create_field(self, label: str, widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(make_label(label, "mutedText", False))
        layout.addWidget(widget)
        return container

    def _load_owned_playlists(self) -> None:
        self.owned_playlist_combo.clear()
        self.owned_playlist_combo.addItem("正在读取已有歌单...", "")
        run_async(
            self.thread_pool,
            self.controller.list_owned_playlists,
            self._on_owned_playlists_loaded,
            self._on_owned_playlists_error,
        )

    def _on_owned_playlists_loaded(self, items: List[Dict[str, Any]]) -> None:
        self.owned_playlist_combo.clear()
        if not items:
            self.owned_playlist_combo.addItem("没有可选的已有歌单", "")
            return
        self.owned_playlist_combo.addItem("请选择已有歌单", "")
        for item in items:
            label = f"{item.get('name') or '-'}  |  ID {item.get('playlist_id') or '-'}  |  {item.get('track_count') or 0} 首"
            self.owned_playlist_combo.addItem(label, item.get("playlist_id") or "")

    def _on_owned_playlists_error(self, error_text: str) -> None:
        self.owned_playlist_combo.clear()
        self.owned_playlist_combo.addItem("读取已有歌单失败", "")
        self.selector_status.setText(error_text.strip().splitlines()[-1])

    def _update_generator_fields(self) -> None:
        scope = self.gen_scope_combo.currentText()
        mode = self.gen_mode_combo.currentText()
        self.gen_pages_field.setVisible(scope == "特定页数")
        self.gen_date_field.setVisible(mode == "按日期")
        show_range = mode == "按时间段"
        self.gen_start_field.setVisible(show_range)
        self.gen_end_field.setVisible(show_range)

    def refresh_date_availability(self, force: bool = False) -> None:
        friend = self.controller.current_friend()
        uid = friend.uid if friend else ""
        scope_map = {"全部历史": "all", "最近": "recent", "特定页数": "pages", "本次新增": "recent"}
        scope = scope_map.get(self.gen_scope_combo.currentText(), "all")
        pages = self.gen_pages_spin.value()
        key = (uid, scope, pages)
        if not force and key == self._active_dates_key:
            return
        self._active_dates_key = key
        active_dates = self.controller.get_song_active_dates(scope=scope, pages=pages) if uid else []
        apply_active_dates([self.gen_date_edit, self.gen_start_edit, self.gen_end_edit], active_dates)
        self._sync_generator_range_boundaries()

    def _sync_generator_range_boundaries(self) -> None:
        start_date = self.gen_start_edit.date()
        end_calendar = self.gen_end_edit.calendarWidget()
        max_date = self.gen_end_edit.maximumDate()
        if start_date > max_date:
            start_date = max_date
        with QtCore.QSignalBlocker(self.gen_end_edit):
            self.gen_end_edit.setMinimumDate(start_date)
            if self.gen_end_edit.date() < start_date:
                self.gen_end_edit.setDate(start_date)
        if isinstance(end_calendar, ActiveDateCalendar):
            with QtCore.QSignalBlocker(end_calendar):
                end_calendar.setMinimumDate(start_date)
            end_calendar.updateCells()

    def save_selector_settings(self) -> None:
        strategy_map = {
            "使用当前已记录歌单": "use_existing",
            "选择自己已有的其他歌单": "select_owned",
            "手动输入歌单 ID": "manual_id",
            "放弃当前记录并自动新建": "auto_create",
        }
        payload = {
            "strategy": strategy_map[self.strategy_combo.currentText()],
            "selected_playlist_id": str(self.owned_playlist_combo.currentData() or ""),
            "manual_playlist_id": self.manual_playlist_edit.text().strip(),
            "new_playlist_name": self.new_playlist_name_edit.text().strip(),
            "is_private": self.private_checkbox.isChecked(),
        }
        self.save_selector_button.setEnabled(False)
        run_async(
            self.thread_pool,
            self.controller.save_shadow_playlist_selection,
            self._on_selector_saved,
            self._on_selector_error,
            lambda: self.save_selector_button.setEnabled(True),
            **payload,
        )

    def _on_selector_saved(self, summary: Dict[str, Any]) -> None:
        self.selector_status.setText("保存成功。")
        self.selector_summary.setText(
            f"名称：{summary.get('name') or '-'}\nID：{summary.get('playlist_id') or '-'}\n策略：{summary.get('strategy') or '-'}\n私密：{'是' if summary.get('is_private') else '否'}"
        )

    def _on_selector_error(self, error_text: str) -> None:
        self.selector_status.setText(error_text.strip().splitlines()[-1])

    def _collect_candidate_filters(self) -> Dict[str, Any]:
        scope_map = {"全部历史": "all", "最近": "recent", "特定页数": "pages", "本次新增": "incremental"}
        sender_map = {"双方": "all", "我方": "self", "好友": "friend"}
        mode_map = {"全部": "all", "按日期": "date", "按时间段": "range"}
        scope = scope_map[self.gen_scope_combo.currentText()]
        query_mode = mode_map[self.gen_mode_combo.currentText()]
        return {
            "max_pages": self.gen_pages_spin.value(),
            "fetch_all": scope == "all",
            "scope": "all" if scope == "all" else scope,
            "sender_scope": sender_map[self.gen_sender_combo.currentText()],
            "keyword": self.gen_keyword_edit.text().strip() or None,
            "start_date": self.gen_date_edit.date().toString("yyyy-MM-dd") if query_mode == "date" else (
                self.gen_start_edit.date().toString("yyyy-MM-dd") if query_mode == "range" else None
            ),
            "end_date": self.gen_date_edit.date().toString("yyyy-MM-dd") if query_mode == "date" else (
                self.gen_end_edit.date().toString("yyyy-MM-dd") if query_mode == "range" else None
            ),
            "incremental_feature_scope": "playlist_generation" if scope == "incremental" else None,
            "max_gap_hours": int(self.gen_gap_edit.text()) if self.gen_gap_edit.text().strip() else None,
            "max_songs": int(self.gen_max_songs_edit.text()) if self.gen_max_songs_edit.text().strip() else None,
        }

    def clear_generator_filters(self) -> None:
        self.gen_scope_combo.setCurrentIndex(1)
        self.gen_pages_spin.setValue(3)
        self.gen_sender_combo.setCurrentIndex(0)
        self.gen_mode_combo.setCurrentIndex(0)
        self.gen_gap_edit.clear()
        self.gen_max_songs_edit.clear()
        self.gen_keyword_edit.clear()
        self._update_generator_fields()
        self.generator_status.setText("已清空条件。")

    def load_candidates(self) -> None:
        self.load_candidates_button.setEnabled(False)
        self.generator_status.setText("候选歌曲加载中...")
        run_async(
            self.thread_pool,
            self.controller.load_shadow_candidates,
            self._on_candidates_loaded,
            self._on_candidates_error,
            lambda: self.load_candidates_button.setEnabled(True),
            **self._collect_candidate_filters(),
        )

    def _on_candidates_loaded(self, payload: Dict[str, Any]) -> None:
        summary = payload.get("summary", {})
        raw_count = int(summary.get("raw_count") or 0)
        current_count = int(summary.get("count") or 0)
        if raw_count and raw_count != current_count:
            self.generator_status.setText(f"候选歌曲已加载，已按当前限制收敛为 {current_count} 首。")
        else:
            self.generator_status.setText("候选歌曲已加载。")
        self.render_candidates(payload.get("items", []))
        self.refresh_date_availability(force=True)

    def _on_candidates_error(self, error_text: str) -> None:
        self.generator_status.setText(error_text.strip().splitlines()[-1])
        self.render_candidates([])

    def _clear_candidate_layout(self) -> None:
        while self.candidate_layout.count():
            item = self.candidate_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def render_candidates(self, items: List[Dict[str, Any]]) -> None:
        self._clear_candidate_layout()
        if not items:
            self.candidate_layout.addWidget(make_label("当前没有候选歌曲。", "mutedText"))
        for item in items:
            card = QtWidgets.QFrame()
            card.setObjectName("resultCard")
            card_layout = QtWidgets.QVBoxLayout(card)
            card_layout.setContentsMargins(16, 16, 16, 16)
            card_layout.setSpacing(6)
            top_row = QtWidgets.QHBoxLayout()
            top_row.setSpacing(10)
            check = QtWidgets.QCheckBox()
            check.setChecked(item.get("msg_id") in self.controller.selected_candidate_ids)
            check.toggled.connect(lambda checked, msg_id=item.get("msg_id"): self.controller.toggle_candidate_selection(str(msg_id), checked))
            top_row.addWidget(check, 0, QtCore.Qt.AlignTop)
            is_self = item.get("direction") != "friend"
            bubble = QtWidgets.QFrame()
            bubble.setObjectName("messageBubbleSelf" if is_self else "messageBubbleFriend")
            bubble.setMaximumWidth(760)
            bubble_layout = QtWidgets.QVBoxLayout(bubble)
            bubble_layout.setContentsMargins(14, 12, 14, 12)
            bubble_layout.setSpacing(6)
            title = make_label(
                f"{item.get('song_name') or '未知歌曲'} · {item.get('artist_name') or '未知歌手'}",
                "messageSelfText" if is_self else "messageFriendText",
                True,
            )
            title.setWordWrap(True)
            bubble_layout.addWidget(title)
            source = make_label(
                f"来源：{'好友' if item.get('direction') == 'friend' else '我方'}",
                "messageSelfMeta" if is_self else "messageFriendMeta",
                True,
            )
            source.setWordWrap(True)
            bubble_layout.addWidget(source)
            time_label = make_label(
                f"时间：{item.get('msg_time_str') or '-'}",
                "messageSelfMeta" if is_self else "messageFriendMeta",
                True,
            )
            time_label.setWordWrap(True)
            bubble_layout.addWidget(time_label)
            if is_self:
                top_row.addStretch(1)
                top_row.addWidget(bubble, 0, QtCore.Qt.AlignRight)
            else:
                top_row.addWidget(bubble, 0, QtCore.Qt.AlignLeft)
                top_row.addStretch(1)
            card_layout.addLayout(top_row)
            self.candidate_layout.addWidget(card)
        self._refresh_candidate_badge()

    def _refresh_candidate_badge(self) -> None:
        self.candidate_badge.setText(f"候选 {len(self.controller.shadow_candidates)} / 已选 {len(self.controller.selected_candidate_ids)}")

    def _set_candidate_selection(self, selected: bool) -> None:
        self.controller.set_all_candidates_selected(selected)
        self.render_candidates(self.controller.shadow_candidates)

    def _invert_candidate_selection(self) -> None:
        self.controller.invert_candidate_selection()
        self.render_candidates(self.controller.shadow_candidates)

    def generate_playlist(self) -> None:
        self.generate_button.setEnabled(False)
        self.generator_status.setText("生成中...")
        run_async(
            self.thread_pool,
            self.controller.generate_shadow_playlist,
            self._on_generate_success,
            self._on_generate_error,
            lambda: self.generate_button.setEnabled(True),
            int(self.gen_gap_edit.text()) if self.gen_gap_edit.text().strip() else None,
            int(self.gen_max_songs_edit.text()) if self.gen_max_songs_edit.text().strip() else None,
        )

    def _on_generate_success(self, payload: Dict[str, Any]) -> None:
        stop_reason = str(payload.get("stop_reason") or "").strip()
        skipped_duplicates = int(payload.get("skipped_duplicates") or 0)
        if stop_reason:
            status_text = (
                f"生成成功，写入 {payload.get('generated_count') or 0} 首歌曲。停止原因：{stop_reason}"
            )
        else:
            status_text = f"生成成功，写入 {payload.get('generated_count') or 0} 首歌曲。"
        if skipped_duplicates > 0:
            status_text += f"（去重跳过 {skipped_duplicates} 首）"
        self.generator_status.setText(status_text)
        self.refresh_status()

    def _on_generate_error(self, error_text: str) -> None:
        self.generator_status.setText(error_text.strip().splitlines()[-1])

    def refresh_status(self) -> None:
        payload = self.controller.get_shadow_status_snapshot()
        playlist = payload.get("playlist", {})
        last_build = payload.get("last_build", {})
        self.selector_summary.setText(
            f"名称：{playlist.get('name') or '-'}\nID：{playlist.get('playlist_id') or '-'}\n策略：{playlist.get('strategy') or '-'}\n私密：{'是' if playlist.get('is_private') else '否'}\n状态：{playlist.get('status_text') or '-'}"
        )
        self.status_summary.setText(
            f"当前目标歌单：{playlist.get('name') or '-'} ({playlist.get('playlist_id') or '-'})\n"
            f"当前策略：{playlist.get('strategy') or '-'}\n"
            f"最近生成时间：{last_build.get('generated_at') or '-'}\n"
            f"最近生成歌曲数：{last_build.get('generated_count') or 0}\n"
            f"当前是否可生成：{'是' if payload.get('can_generate') else '否'}\n"
            f"当前模式：{payload.get('mode') or '-'}"
        )
        while self.playlist_state_layout.count():
            item = self.playlist_state_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        playlist_state = payload.get("playlist_state", [])
        if not playlist_state:
            self.playlist_state_layout.addWidget(make_label("当前写入目标歌单为空。", "mutedText"))
        for item in playlist_state[:12]:
            card = QtWidgets.QFrame()
            card.setObjectName("resultCard")
            card_layout = QtWidgets.QVBoxLayout(card)
            card_layout.setContentsMargins(14, 14, 14, 14)
            card_layout.setSpacing(4)
            card_layout.addWidget(make_label(item.get("song_name") or "未知歌曲", "sectionTitle", False))
            card_layout.addWidget(make_label(item.get("artist_name") or "未知歌手", "mutedText", False))
            self.playlist_state_layout.addWidget(card)
