from __future__ import annotations

from typing import Any, Dict, List

from PySide6 import QtCore, QtGui, QtWidgets

from core.app_controller import AppController
from core.models import FriendEntry
from ui.widgets.common import make_button, make_label, run_async
from ui.widgets.friend_sidebar import AvatarLoader
from ui.widgets.navigation import SegmentedNavigation
from ui.widgets.web_chart import WebChartWidget


class _MetricCard(QtWidgets.QFrame):
    def __init__(self, title: str, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("summaryCard")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        layout.addWidget(make_label(title, "mutedText", False))
        self.value_label = make_label("-", "sectionTitle", False)
        layout.addWidget(self.value_label)

    def set_value(self, text: str) -> None:
        self.value_label.setText(text)


class _OverviewMetricCard(QtWidgets.QFrame):
    def __init__(self, title: str, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFixedHeight(88)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)
        layout.addWidget(make_label(title, "mutedText", False))
        self.value_label = make_label("-", "sectionTitle", False)
        layout.addWidget(self.value_label)
        layout.addStretch(1)

    def set_value(self, text: str) -> None:
        self.value_label.setText(text)


class MusicRelationPage(QtWidgets.QWidget):
    full_archive_requested = QtCore.Signal()

    def __init__(self, controller: AppController, thread_pool: QtCore.QThreadPool, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.thread_pool = thread_pool
        self._refresh_in_flight = False
        self._latest_payload: Dict[str, Any] = {}
        self._latest_friend_insight: Dict[str, Any] = {}
        self._latest_self_insight: Dict[str, Any] = {}

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(18)

        header_row = QtWidgets.QHBoxLayout()
        header_row.addWidget(make_label("音乐关系", "pageTitle", False))
        header_row.addStretch(1)
        self.scope_combo = QtWidgets.QComboBox()
        self.scope_combo.addItems(["全量历史", "特定年份"])
        self.year_combo = QtWidgets.QComboBox()
        self.year_combo.setEnabled(False)
        self.year_combo.setMinimumWidth(100)
        self.year_combo.addItem("暂无年份")
        self.year_combo.setVisible(False)
        self.refresh_button = make_button("刷新分析", "secondaryButton")
        self.rebuild_archive_button = make_button("全量重建归档", "secondaryButton")
        self.status_label = make_label("等待载入分析数据。", "mutedText", False)
        header_row.addWidget(self.scope_combo)
        header_row.addWidget(self.year_combo)
        header_row.addWidget(self.refresh_button)
        header_row.addWidget(self.rebuild_archive_button)
        header_row.addWidget(self.status_label)
        layout.addLayout(header_row)

        self.sub_nav = SegmentedNavigation(
            [
                ("overview", "总览"),
                ("friend", "单好友画像"),
                ("self", "我的音乐社交"),
                ("report", "报告中心"),
            ],
            object_name="shadowSegmentedButton",
        )
        layout.addWidget(self.sub_nav)

        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.overview_page = self._build_overview_tab()
        self.friend_page = self._build_friend_tab()
        self.self_page = self._build_self_tab()
        self.report_page = self._build_report_tab()
        self.stack.addWidget(self.overview_page)
        self.stack.addWidget(self.friend_page)
        self.stack.addWidget(self.self_page)
        self.stack.addWidget(self.report_page)
        self._page_index = {"overview": 0, "friend": 1, "self": 2, "report": 3}
        self.sub_nav.set_current("overview")

        self.sub_nav.changed.connect(self._switch_tab)
        self.refresh_button.clicked.connect(lambda: self.refresh_content(force=True))
        self.rebuild_archive_button.clicked.connect(self.full_archive_requested.emit)
        self.scope_combo.currentTextChanged.connect(self._on_scope_changed)
        self.year_combo.currentTextChanged.connect(lambda _text: self.refresh_content(force=True))
        self.friend_ai_button.clicked.connect(self._generate_friend_insight)
        self.self_ai_button.clicked.connect(self._generate_self_insight)
        self.friend_export_button.clicked.connect(self._export_friend_report)
        self.self_export_button.clicked.connect(self._export_self_report)
        self.annual_export_button.clicked.connect(self._export_annual_report)
        self.report_refresh_button.clicked.connect(self.refresh_reports)
        self.open_report_dir_button.clicked.connect(self._open_report_dir)
        self.report_cleanup_button.clicked.connect(self._cleanup_reports)
        self.report_type_combo.currentTextChanged.connect(lambda _text: self.refresh_reports())
        self.report_search_edit.textChanged.connect(lambda _text: self.refresh_reports())
        self.report_list.itemDoubleClicked.connect(self._open_report_file)

        self.refresh_content(force=True)
        self.refresh_reports()

    def _build_overview_tab(self) -> QtWidgets.QWidget:
        root = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        hero = QtWidgets.QFrame()
        hero.setObjectName("card")
        hero_layout = QtWidgets.QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 14, 18, 14)
        hero_layout.setSpacing(8)
        self.ov_hero_title = make_label("音乐关系总览", "sectionTitle", False)
        self.ov_hero_summary = make_label("正在汇总当前音乐关系网络。", "mutedText", True)
        self.ov_hero_summary.setObjectName("relationConclusionBar")
        self.ov_hero_summary.setWordWrap(True)
        hero_layout.addWidget(self.ov_hero_title)
        hero_layout.addWidget(self.ov_hero_summary)
        tag_row = QtWidgets.QHBoxLayout()
        tag_row.setSpacing(8)
        self.ov_network_tag = make_label("关系网络：--", "", False)
        self.ov_music_tag = make_label("音乐社交：--", "", False)
        self.ov_core_tag = make_label("核心主角：--", "", False)
        for tag in (self.ov_network_tag, self.ov_music_tag, self.ov_core_tag):
            tag.setObjectName("relationMiniTag")
            tag_row.addWidget(tag, 0)
        tag_row.addStretch(1)
        hero_layout.addLayout(tag_row)
        layout.addWidget(hero)

        metric_grid = QtWidgets.QGridLayout()
        metric_grid.setHorizontalSpacing(10)
        metric_grid.setVerticalSpacing(10)
        self.ov_friend_card = _OverviewMetricCard("覆盖好友数")
        self.ov_message_card = _OverviewMetricCard("信息总数")
        self.ov_song_card = _OverviewMetricCard("歌曲总数")
        self.ov_peak_card = _OverviewMetricCard("当前活跃峰值")
        self.ov_core_card = _OverviewMetricCard("核心圈层浓度")
        self.ov_balance_card = _OverviewMetricCard("输入/输出状态")
        for index, card in enumerate(
            (
                self.ov_friend_card,
                self.ov_message_card,
                self.ov_song_card,
                self.ov_peak_card,
                self.ov_core_card,
                self.ov_balance_card,
            )
        ):
            metric_grid.addWidget(card, index // 3, index % 3)
        layout.addLayout(metric_grid)

        layout.addWidget(make_label("本次看点", "sectionTitle", False))
        spotlight_row = QtWidgets.QHBoxLayout()
        spotlight_row.setSpacing(10)
        self.ov_friend_spot_card, self.ov_friend_spot_title, self.ov_friend_spot_detail, self.ov_friend_spot_button = self._make_overview_action_card(
            "推荐查看好友",
            "等待推荐对象。",
            "查看单好友画像",
        )
        self.ov_status_spot_card, self.ov_status_spot_title, self.ov_status_spot_detail, self.ov_status_spot_button = self._make_overview_action_card(
            "当前社交状态",
            "等待结构判断。",
            "查看我的音乐社交",
        )
        self.ov_report_spot_card, self.ov_report_spot_title, self.ov_report_spot_detail, self.ov_report_spot_button = self._make_overview_action_card(
            "报告中心提醒",
            "报告归档状态待同步。",
            "进入报告中心",
        )
        spotlight_row.addWidget(self.ov_friend_spot_card, 1)
        spotlight_row.addWidget(self.ov_status_spot_card, 1)
        spotlight_row.addWidget(self.ov_report_spot_card, 1)
        layout.addLayout(spotlight_row)

        layout.addWidget(make_label("入口预览", "sectionTitle", False))
        preview_row = QtWidgets.QHBoxLayout()
        preview_row.setSpacing(10)
        self.ov_friend_preview = self._build_overview_friend_preview()
        self.ov_self_preview = self._build_overview_self_preview()
        preview_row.addWidget(self.ov_friend_preview, 1)
        preview_row.addWidget(self.ov_self_preview, 1)
        layout.addLayout(preview_row)

        recent = QtWidgets.QFrame()
        recent.setObjectName("card")
        recent_layout = QtWidgets.QVBoxLayout(recent)
        recent_layout.setContentsMargins(14, 12, 14, 12)
        recent_layout.setSpacing(8)
        recent_layout.addWidget(make_label("最近变化 / 最近记忆点", "sectionTitle", False))
        self.ov_recent_items: List[QtWidgets.QLabel] = []
        for _ in range(4):
            label = make_label("待生成最近变化。", "mutedText", True)
            label.setObjectName("relationConclusionBar")
            label.setWordWrap(True)
            self.ov_recent_items.append(label)
            recent_layout.addWidget(label)
        layout.addWidget(recent)
        layout.addStretch(1)
        self.ov_friend_spot_button.clicked.connect(self._open_overview_friend_preview)
        self.ov_status_spot_button.clicked.connect(lambda: self._go_to_relation_tab("self"))
        self.ov_report_spot_button.clicked.connect(lambda: self._go_to_relation_tab("report"))
        self.ov_friend_preview_button.clicked.connect(self._open_overview_friend_preview)
        self.ov_self_preview_button.clicked.connect(lambda: self._go_to_relation_tab("self"))
        return root

    def _make_overview_action_card(
        self,
        title: str,
        detail: str,
        button_text: str,
    ) -> tuple[QtWidgets.QFrame, QtWidgets.QLabel, QtWidgets.QLabel, QtWidgets.QPushButton]:
        card = QtWidgets.QFrame()
        card.setObjectName("card")
        card.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        card.setFixedHeight(142)
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        title_label = make_label(title, "sectionTitle", False)
        detail_label = make_label(detail, "mutedText", True)
        detail_label.setWordWrap(True)
        detail_label.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        detail_label.setFixedHeight(42)
        detail_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        button = make_button(button_text, "secondaryButton")
        button.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        layout.addWidget(title_label)
        layout.addWidget(detail_label)
        layout.addStretch(1)
        layout.addWidget(button, 0, QtCore.Qt.AlignLeft)
        return card, title_label, detail_label, button

    def _build_overview_friend_preview(self) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setObjectName("card")
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(10)
        self.ov_friend_preview_avatar = QtWidgets.QLabel()
        self.ov_friend_preview_avatar.setObjectName("friendInfoAvatar")
        self.ov_friend_preview_avatar.setMinimumSize(44, 44)
        self.ov_friend_preview_avatar.setMaximumSize(44, 44)
        header.addWidget(self.ov_friend_preview_avatar, 0, QtCore.Qt.AlignTop)
        text_box = QtWidgets.QVBoxLayout()
        text_box.setSpacing(4)
        self.ov_friend_preview_name = make_label("单好友画像预览", "sectionTitle", False)
        self.ov_friend_preview_desc = make_label("选择一个好友查看关系画像。", "mutedText", True)
        self.ov_friend_preview_desc.setWordWrap(True)
        text_box.addWidget(self.ov_friend_preview_name)
        text_box.addWidget(self.ov_friend_preview_desc)
        header.addLayout(text_box, 1)
        self.ov_friend_preview_temp = make_label("关系温度 --", "", False)
        self.ov_friend_preview_temp.setObjectName("relationTempBadge")
        header.addWidget(self.ov_friend_preview_temp, 0, QtCore.Qt.AlignTop)
        layout.addLayout(header)
        self.ov_friend_preview_button = make_button("查看单好友画像", "secondaryButton")
        layout.addWidget(self.ov_friend_preview_button, 0, QtCore.Qt.AlignLeft)
        return card

    def _build_overview_self_preview(self) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setObjectName("card")
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        self.ov_self_preview_title = make_label("我的音乐社交预览", "sectionTitle", False)
        self.ov_self_preview_tag = make_label("社交标签：--", "", False)
        self.ov_self_preview_tag.setObjectName("relationMiniTag")
        self.ov_self_preview_desc = make_label("等待生成我的音乐社交摘要。", "mutedText", True)
        self.ov_self_preview_desc.setWordWrap(True)
        self.ov_self_preview_button = make_button("查看我的音乐社交", "secondaryButton")
        layout.addWidget(self.ov_self_preview_title)
        layout.addWidget(self.ov_self_preview_tag, 0, QtCore.Qt.AlignLeft)
        layout.addWidget(self.ov_self_preview_desc, 1)
        layout.addWidget(self.ov_self_preview_button, 0, QtCore.Qt.AlignLeft)
        return card

    def _build_friend_tab(self) -> QtWidgets.QWidget:
        root = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.friend_hero_card = QtWidgets.QFrame()
        self.friend_hero_card.setObjectName("card")
        self.friend_hero_card.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.friend_hero_card.setFixedHeight(108)
        hero_layout = QtWidgets.QVBoxLayout(self.friend_hero_card)
        hero_layout.setContentsMargins(12, 8, 12, 8)
        hero_layout.setSpacing(6)
        hero_top = QtWidgets.QHBoxLayout()
        hero_top.setContentsMargins(0, 0, 0, 0)
        hero_top.setSpacing(9)
        self.friend_hero_avatar = QtWidgets.QLabel()
        self.friend_hero_avatar.setObjectName("friendInfoAvatar")
        self.friend_hero_avatar.setMinimumSize(42, 42)
        self.friend_hero_avatar.setMaximumSize(42, 42)
        hero_top.addWidget(self.friend_hero_avatar, 0, QtCore.Qt.AlignVCenter)
        self.friend_hero = make_label("未选择好友", "sectionTitle", False)
        self.friend_cover_line = make_label("关系封面语待生成。", "mutedText", True)
        self.friend_cover_line.setObjectName("relationConclusionBar")
        self.friend_cover_line.setWordWrap(False)
        self.friend_cover_line.setFixedHeight(34)
        self.friend_cover_line.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        hero_top.addWidget(self.friend_hero, 1, QtCore.Qt.AlignVCenter)
        self.friend_temp_badge = make_label("关系温度 --", "", False)
        self.friend_temp_badge.setObjectName("relationTempBadge")
        self.friend_temp_badge.setFixedHeight(30)
        self.friend_temp_badge.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        hero_top.addWidget(self.friend_temp_badge, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        hero_layout.addLayout(hero_top)
        hero_layout.addWidget(self.friend_cover_line)
        layout.addWidget(self.friend_hero_card)

        metrics_box = QtWidgets.QWidget()
        metrics_box.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        metrics_box.setFixedHeight(188)
        metrics_box.setStyleSheet(
            """
            QFrame#friendMetricCard {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(110, 183, 237, 0.68);
                border-radius: 20px;
            }
            QFrame#friendMetricCard QLabel#mutedText {
                color: rgba(238,244,251,0.68);
                font-size: 13px;
            }
            QFrame#friendMetricCard QLabel#sectionTitle {
                color: #f4f8ff;
                font-size: 18px;
                font-weight: 800;
            }
            """
        )
        metrics_grid = QtWidgets.QGridLayout(metrics_box)
        metrics_grid.setContentsMargins(0, 0, 0, 0)
        metrics_grid.setHorizontalSpacing(10)
        metrics_grid.setVerticalSpacing(10)
        self.friend_msg_card = _MetricCard("消息总数")
        self.friend_song_card = _MetricCard("发歌总数")
        self.friend_active_card = _MetricCard("活跃天数")
        self.friend_night_card = _MetricCard("深夜占比")
        self.friend_first_share_card = _MetricCard("首次分享")
        self.friend_recent_share_card = _MetricCard("最近分享")
        self.friend_avg_freq_card = _MetricCard("平均频率")
        metric_cards = [
            self.friend_msg_card,
            self.friend_song_card,
            self.friend_active_card,
            self.friend_night_card,
            self.friend_first_share_card,
            self.friend_recent_share_card,
            self.friend_avg_freq_card,
        ]
        for card in metric_cards:
            card.setObjectName("friendMetricCard")
            card.setFixedHeight(88)
            card.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            card_layout = card.layout()
            if card_layout is not None:
                card_layout.setContentsMargins(14, 10, 14, 10)
                card_layout.setSpacing(5)
        for idx, card in enumerate(metric_cards):
            row_index = 0 if idx < 4 else 1
            col_index = idx if idx < 4 else idx - 4
            metrics_grid.addWidget(card, row_index, col_index, 1, 1)
        metrics_grid.setColumnStretch(0, 1)
        metrics_grid.setColumnStretch(1, 1)
        metrics_grid.setColumnStretch(2, 1)
        metrics_grid.setColumnStretch(3, 1)
        layout.addWidget(metrics_box)

        self.friend_rhythm_chart = WebChartWidget()
        layout.addWidget(self._wrap_widget("关系节律时间线", self.friend_rhythm_chart, compact=True))

        self.friend_heat_chart = WebChartWidget()
        layout.addWidget(self._wrap_widget("活跃节律热力图", self.friend_heat_chart, compact=True))

        self.friend_music_portrait_chart = WebChartWidget()
        layout.addWidget(self._wrap_widget("音乐画像", self.friend_music_portrait_chart, compact=True))

        self.friend_common_world_chart = WebChartWidget()
        layout.addWidget(self._wrap_widget("共同世界", self.friend_common_world_chart, compact=True))

        ai_controls_bar = QtWidgets.QFrame()
        ai_controls_bar.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        ai_controls_bar.setFixedHeight(46)
        ai_controls = QtWidgets.QHBoxLayout(ai_controls_bar)
        ai_controls.setContentsMargins(0, 0, 0, 0)
        ai_controls.setSpacing(10)
        ai_controls.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.friend_mode_combo = QtWidgets.QComboBox()
        self.friend_mode_combo.addItems(["理性版", "风格版", "评论版", "年度报告版"])
        self.friend_ai_button = make_button("生成 AI 文段", "primaryButton")
        self.friend_export_button = make_button("导出好友报告 PNG", "secondaryButton")
        self.friend_ai_source = make_label("待生成", "statusBadge", False)
        self.friend_ai_source.setFixedHeight(30)
        self.friend_ai_source.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        ai_controls.addWidget(self.friend_mode_combo)
        ai_controls.addWidget(self.friend_ai_button)
        ai_controls.addWidget(self.friend_export_button)
        ai_controls.addStretch(1)
        ai_controls.addWidget(self.friend_ai_source)
        layout.addWidget(ai_controls_bar)
        self.friend_ai_trust = make_label("依据来自：趋势、Top歌手、证据歌曲、活跃时段", "", True)
        self.friend_ai_trust.setObjectName("relationConclusionBar")
        self.friend_ai_trust.setWordWrap(False)
        self.friend_ai_trust.setFixedHeight(34)
        self.friend_ai_trust.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        layout.addWidget(self.friend_ai_trust)

        ai_row = QtWidgets.QHBoxLayout()
        ai_row.setSpacing(10)
        self.friend_ai_text = QtWidgets.QPlainTextEdit()
        self.friend_ai_text.setObjectName("friendAiText")
        self.friend_ai_text.setReadOnly(True)
        self.friend_ai_text.setMinimumHeight(160)
        self.friend_ai_text.setMaximumHeight(220)
        self.friend_ai_text.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Maximum)
        self.friend_ai_text.setPlaceholderText("点击“生成 AI 文段”后显示分析结果。")
        self.friend_evidence_list = QtWidgets.QListWidget()
        self.friend_evidence_list.setObjectName("friendEvidenceList")
        self.friend_evidence_list.setMinimumHeight(160)
        self.friend_evidence_list.setMaximumHeight(220)
        self.friend_evidence_list.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Maximum)
        ai_row.addWidget(self._wrap_widget("AI 文段", self.friend_ai_text, compact=True), 2)
        ai_row.addWidget(self._wrap_widget("证据歌曲卡片", self.friend_evidence_list, compact=True), 1)
        layout.addLayout(ai_row)
        layout.addStretch(1)
        return root

    def _build_self_tab(self) -> QtWidgets.QWidget:
        root = QtWidgets.QWidget()
        root.setObjectName("musicSelfPage")
        root.setStyleSheet(
            """
            #musicSelfPage #card, #musicSelfPage #summaryCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(25, 39, 58, 0.92),
                    stop:1 rgba(13, 24, 39, 0.96));
                border: 1px solid rgba(112, 174, 222, 0.18);
                border-radius: 22px;
            }
            #musicSelfPage QListWidget#card {
                background: rgba(15, 27, 43, 0.88);
                border: 1px solid rgba(112, 174, 222, 0.16);
            }
            #musicSelfPage QLabel#relationConclusionBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(28, 47, 68, 0.72),
                    stop:1 rgba(19, 31, 50, 0.76));
                border: 1px solid rgba(120, 185, 226, 0.18);
                color: rgba(241, 247, 255, 0.88);
            }
            #musicSelfPage #statusBadge {
                background: rgba(101, 185, 216, 0.13);
                color: #9fd8f2;
            }
            """
        )
        layout = QtWidgets.QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        hero_card = QtWidgets.QFrame()
        hero_card.setObjectName("card")
        hero_layout = QtWidgets.QVBoxLayout(hero_card)
        hero_layout.setContentsMargins(14, 12, 14, 12)
        hero_layout.setSpacing(8)
        self.self_hero = make_label("我的音乐社交封面", "sectionTitle", False)
        hero_layout.addWidget(self.self_hero)
        self.self_story_note = make_label("我的社交画像结论待生成。", "", True)
        self.self_story_note.setObjectName("relationConclusionBar")
        self.self_story_note.setWordWrap(True)
        hero_layout.addWidget(self.self_story_note)
        layout.addWidget(hero_card)

        hero_metrics = QtWidgets.QHBoxLayout()
        hero_metrics.setSpacing(10)
        self.self_friend_card = _MetricCard("覆盖好友数")
        self.self_message_card = _MetricCard("信息总数")
        self.self_song_card = _MetricCard("歌曲总数")
        self.self_peak_card = _MetricCard("活跃峰值")
        for card in (self.self_friend_card, self.self_message_card, self.self_song_card, self.self_peak_card):
            hero_metrics.addWidget(card, 1)
        layout.addLayout(hero_metrics)

        core_row = QtWidgets.QHBoxLayout()
        core_row.setSpacing(10)
        self.self_chat_rank = QtWidgets.QListWidget()
        self.self_song_rank = QtWidgets.QListWidget()
        self.self_temp_rank = QtWidgets.QListWidget()
        for rank_list in (self.self_chat_rank, self.self_song_rank, self.self_temp_rank):
            self._configure_self_top3_list(rank_list)
        core_row.addWidget(self._wrap_widget("聊天 Top3", self.self_chat_rank, compact=True), 1)
        core_row.addWidget(self._wrap_widget("歌曲 Top3", self.self_song_rank, compact=True), 1)
        core_row.addWidget(self._wrap_widget("关系温度 Top3", self.self_temp_rank, compact=True), 1)
        layout.addLayout(core_row)

        struct_row = QtWidgets.QHBoxLayout()
        struct_row.setSpacing(10)
        self.self_music_balance_card = _MetricCard("音乐输入/输出")
        self.self_chat_balance_card = _MetricCard("聊天输入/输出")
        self.self_music_conc_card = _MetricCard("音乐圈层浓度")
        self.self_chat_conc_card = _MetricCard("聊天圈层浓度")
        for card in (
            self.self_music_balance_card,
            self.self_chat_balance_card,
            self.self_music_conc_card,
            self.self_chat_conc_card,
        ):
            struct_row.addWidget(card, 1)
        layout.addLayout(struct_row)
        self.self_struct_note = make_label("社交结构摘要待生成。", "", True)
        self.self_struct_note.setObjectName("relationConclusionBar")
        self.self_struct_note.setWordWrap(True)
        layout.addWidget(self.self_struct_note)

        net_row_top = QtWidgets.QHBoxLayout()
        net_row_top.setSpacing(10)
        self.self_music_in_chart = WebChartWidget()
        self.self_music_out_chart = WebChartWidget()
        net_row_top.addWidget(self._wrap_widget("我的音乐输入网状图", self.self_music_in_chart, compact=True), 1)
        net_row_top.addWidget(self._wrap_widget("我的音乐输出网状图", self.self_music_out_chart, compact=True), 1)
        layout.addLayout(net_row_top)

        net_row_bottom = QtWidgets.QHBoxLayout()
        net_row_bottom.setSpacing(10)
        self.self_chat_in_chart = WebChartWidget()
        self.self_chat_out_chart = WebChartWidget()
        net_row_bottom.addWidget(self._wrap_widget("我的聊天输入网状图", self.self_chat_in_chart, compact=True), 1)
        net_row_bottom.addWidget(self._wrap_widget("我的聊天输出网状图", self.self_chat_out_chart, compact=True), 1)
        layout.addLayout(net_row_bottom)

        self.self_rhythm_chart = WebChartWidget()
        layout.addWidget(self._wrap_widget("我的社交节律时间线", self.self_rhythm_chart, compact=True))

        ai_controls = QtWidgets.QHBoxLayout()
        self.self_mode_combo = QtWidgets.QComboBox()
        self.self_mode_combo.addItems(["理性版", "风格版", "评论版"])
        self.self_ai_button = make_button("生成个人 AI 文段", "primaryButton")
        self.self_export_button = make_button("导出个人报告 PNG", "secondaryButton")
        self.self_ai_source = make_label("待生成", "statusBadge", False)
        ai_controls.addWidget(self.self_mode_combo)
        ai_controls.addWidget(self.self_ai_button)
        ai_controls.addWidget(self.self_export_button)
        ai_controls.addStretch(1)
        ai_controls.addWidget(self.self_ai_source)
        layout.addLayout(ai_controls)

        self.self_ai_trust = make_label("依据来自：趋势、Top歌手、证据歌曲、活跃时段", "", True)
        self.self_ai_trust.setObjectName("relationConclusionBar")
        self.self_ai_trust.setWordWrap(True)
        layout.addWidget(self.self_ai_trust)

        ai_row = QtWidgets.QHBoxLayout()
        ai_row.setSpacing(10)
        self.self_ai_text = QtWidgets.QPlainTextEdit()
        self.self_ai_text.setReadOnly(True)
        self.self_ai_text.setMinimumHeight(180)
        self.self_evidence_list = QtWidgets.QListWidget()
        self.self_evidence_list.setMinimumHeight(180)
        ai_row.addWidget(self._wrap_widget("AI 总结区", self.self_ai_text), 2)
        ai_row.addWidget(self._wrap_widget("证据歌曲卡片", self.self_evidence_list), 1)
        layout.addLayout(ai_row)

        annual_controls = QtWidgets.QHBoxLayout()
        annual_controls.addStretch(1)
        self.annual_export_button = make_button("导出年度回顾 PNG", "secondaryButton")
        annual_controls.addWidget(self.annual_export_button)
        layout.addLayout(annual_controls)

        self.annual_showcase = self._build_annual_showcase()
        layout.addWidget(self._wrap_widget("年度音乐社交回顾", self.annual_showcase))
        layout.addStretch(1)
        return root

    def _build_report_tab(self) -> QtWidgets.QWidget:
        root = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        controls = QtWidgets.QHBoxLayout()
        self.report_type_combo = QtWidgets.QComboBox()
        self.report_type_combo.addItems(["全部报告", "好友报告", "个人报告", "年度回顾"])
        self.report_search_edit = QtWidgets.QLineEdit()
        self.report_search_edit.setPlaceholderText("搜索标题/时间/UID/路径")
        self.report_refresh_button = make_button("刷新记录", "secondaryButton")
        self.report_cleanup_button = make_button("清理失效记录", "secondaryButton")
        self.open_report_dir_button = make_button("打开报告目录", "ghostButton")
        controls.addWidget(self.report_type_combo)
        controls.addWidget(self.report_search_edit, 1)
        controls.addWidget(self.report_refresh_button)
        controls.addWidget(self.report_cleanup_button)
        controls.addWidget(self.open_report_dir_button)
        layout.addLayout(controls)

        self.report_list = QtWidgets.QListWidget()
        self.report_list.setObjectName("card")
        self.report_list.setMinimumHeight(320)
        self.report_list.setSpacing(8)
        self.report_list.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        layout.addWidget(self.report_list, 1)
        return root

    @staticmethod
    def _wrap_widget(title: str, widget: QtWidgets.QWidget, compact: bool = False) -> QtWidgets.QWidget:
        frame = QtWidgets.QFrame()
        frame.setObjectName("card")
        if compact:
            frame.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
        inner = QtWidgets.QVBoxLayout(frame)
        inner.setContentsMargins(14, 12, 14, 12)
        inner.setSpacing(10)
        inner.addWidget(make_label(title, "sectionTitle", False))
        if compact:
            widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        inner.addWidget(widget)
        return frame

    @staticmethod
    def _configure_self_top3_list(widget: QtWidgets.QListWidget) -> None:
        widget.setObjectName("card")
        widget.setSpacing(8)
        widget.setFixedHeight(238)
        widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        widget.setUniformItemSizes(True)
        widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        widget.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)

    def _switch_tab(self, key: str) -> None:
        self.stack.setCurrentIndex(self._page_index.get(key, 0))

    def _build_annual_showcase(self) -> QtWidgets.QWidget:
        root = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        hero_card = QtWidgets.QFrame()
        hero_card.setObjectName("annualHeroCard")
        hero_layout = QtWidgets.QVBoxLayout(hero_card)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        hero_layout.setSpacing(8)
        hero_top = QtWidgets.QHBoxLayout()
        hero_top.setContentsMargins(0, 0, 0, 0)
        hero_top.setSpacing(8)
        self.annual_hero_title = QtWidgets.QLabel("年度音乐社交回顾")
        self.annual_hero_title.setObjectName("annualHeroTitle")
        self.annual_hero_mark = QtWidgets.QLabel("YEAR IN MUSIC")
        self.annual_hero_mark.setObjectName("annualHeroMark")
        hero_top.addWidget(self.annual_hero_title, 1)
        hero_top.addWidget(self.annual_hero_mark, 0, QtCore.Qt.AlignRight)
        hero_layout.addLayout(hero_top)
        self.annual_hero_summary = QtWidgets.QLabel("暂无年度摘要。")
        self.annual_hero_summary.setObjectName("annualHeroSummary")
        self.annual_hero_summary.setWordWrap(True)
        hero_layout.addWidget(self.annual_hero_summary)
        layout.addWidget(hero_card)

        metrics_card = QtWidgets.QFrame()
        metrics_card.setObjectName("annualMetricsCard")
        metrics_layout = QtWidgets.QVBoxLayout(metrics_card)
        metrics_layout.setContentsMargins(14, 12, 14, 12)
        metrics_layout.setSpacing(8)
        self.annual_metric_message = self._add_annual_metric_line(metrics_layout, "消息总量")
        self.annual_metric_song = self._add_annual_metric_line(metrics_layout, "歌曲总量")
        self.annual_metric_peak = self._add_annual_metric_line(metrics_layout, "活跃峰值")
        layout.addWidget(metrics_card)

        lead_card = QtWidgets.QFrame()
        lead_card.setObjectName("annualLeadCard")
        lead_layout = QtWidgets.QVBoxLayout(lead_card)
        lead_layout.setContentsMargins(14, 12, 14, 12)
        lead_layout.setSpacing(8)
        self.annual_lead_title = QtWidgets.QLabel("关系主角")
        self.annual_lead_title.setObjectName("annualLeadTitle")
        self.annual_lead_name = QtWidgets.QLabel("暂无")
        self.annual_lead_name.setObjectName("annualLeadName")
        self.annual_lead_detail = QtWidgets.QLabel("聊天最多：-\n发歌最多：-")
        self.annual_lead_detail.setObjectName("annualLeadDetail")
        self.annual_lead_detail.setWordWrap(True)
        lead_layout.addWidget(self.annual_lead_title)
        lead_layout.addWidget(self.annual_lead_name)
        lead_layout.addWidget(self.annual_lead_detail)
        layout.addWidget(lead_card)
        return root

    @staticmethod
    def _add_annual_metric_line(layout: QtWidgets.QVBoxLayout, label_text: str) -> QtWidgets.QLabel:
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        label = QtWidgets.QLabel(label_text)
        label.setObjectName("annualMetricLabel")
        value = QtWidgets.QLabel("-")
        value.setObjectName("annualMetricValue")
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(value)
        layout.addLayout(row)
        return value

    def _dashboard_window(self) -> str:
        if self.scope_combo.currentText() != "特定年份":
            return "all"
        year_text = str(self.year_combo.currentText() or "").strip()
        if not year_text.isdigit():
            return "all"
        return f"year:{year_text}"

    def _on_scope_changed(self, text: str) -> None:
        is_year_mode = text == "特定年份"
        has_years = self.year_combo.count() > 0 and str(self.year_combo.itemText(0)).isdigit()
        self.year_combo.setVisible(is_year_mode)
        self.year_combo.setEnabled(is_year_mode and has_years)
        self.refresh_content(force=True)

    def _sync_available_years(self, years: List[int]) -> None:
        selected = str(self.year_combo.currentText() or "")
        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        if years:
            for year in sorted({int(item) for item in years}, reverse=True):
                self.year_combo.addItem(str(year))
            if selected.isdigit() and selected in [self.year_combo.itemText(i) for i in range(self.year_combo.count())]:
                self.year_combo.setCurrentText(selected)
        else:
            self.year_combo.addItem("暂无年份")
        self.year_combo.blockSignals(False)
        is_year_mode = self.scope_combo.currentText() == "特定年份"
        self.year_combo.setVisible(is_year_mode)
        self.year_combo.setEnabled(is_year_mode and bool(years))

    def refresh_content(self, force: bool = False) -> None:
        if self._refresh_in_flight:
            return
        self._refresh_in_flight = True
        self.status_label.setText("分析计算中...")
        run_async(
            self.thread_pool,
            self.controller.get_relation_dashboard_payload,
            self._on_dashboard_ready,
            self._on_error,
            self._finish_refresh,
            self._dashboard_window(),
            force,
        )

    def _finish_refresh(self) -> None:
        self._refresh_in_flight = False

    def _on_dashboard_ready(self, payload: Dict[str, Any]) -> None:
        self._latest_payload = payload
        self._sync_available_years([int(item) for item in (payload.get("available_years") or []) if str(item).isdigit()])
        self.status_label.setText("分析已更新。")
        self._render_overview(
            payload.get("overview", {}),
            payload.get("friends", []),
            payload.get("friend", {}),
            payload.get("self", {}),
        )
        self._render_friend(payload.get("friend", {}))
        self._render_self(payload.get("self", {}))
        self.refresh_reports()

    def _render_overview(
        self,
        snapshot: Dict[str, Any],
        friend_rows: List[Dict[str, Any]],
        focus_friend: Dict[str, Any],
        self_snapshot: Dict[str, Any],
    ) -> None:
        friend_index = self._build_snapshot_index(friend_rows)
        network_block = dict(self_snapshot.get("network_block") or {})
        music_balance = dict(network_block.get("music_balance") or {})
        chat_balance = dict(network_block.get("chat_balance") or {})
        music_concentration = dict(network_block.get("music_concentration") or {})
        chat_concentration = dict(network_block.get("chat_concentration") or {})
        music_balance_label = str(music_balance.get("label") or "暂无判断")
        chat_balance_label = str(chat_balance.get("label") or "暂无判断")
        concentration_label = str(music_concentration.get("label") or chat_concentration.get("label") or "暂无判断")
        core_friend = str(self_snapshot.get("core_friend_name") or "")
        if not core_friend:
            top_temp = (snapshot.get("top_temperature_friends") or [{}])[0]
            core_friend = str(top_temp.get("name") or top_temp.get("friend_name") or "暂无")
        peak_month = str(self_snapshot.get("peak_month") or "-")

        self.ov_hero_summary.setText(
            f"当前覆盖 {snapshot.get('friend_count', 0)} 位好友、{snapshot.get('song_count', 0)} 首歌曲分享；"
            f"音乐社交呈现 {music_balance_label}，核心圈层为 {concentration_label}。"
        )
        self.ov_network_tag.setText(f"关系网络：{concentration_label}")
        self.ov_music_tag.setText(f"音乐社交：{music_balance_label}")
        self.ov_core_tag.setText(f"核心主角：{core_friend}")
        self.ov_friend_card.set_value(str(snapshot.get("friend_count", 0)))
        self.ov_message_card.set_value(str(snapshot.get("message_count", 0)))
        self.ov_song_card.set_value(str(snapshot.get("song_count", 0)))
        self.ov_peak_card.set_value(peak_month)
        self.ov_core_card.set_value(concentration_label)
        self.ov_balance_card.set_value(music_balance_label)

        recommended = self._pick_overview_recommended_friend(snapshot, friend_index, focus_friend)
        self._overview_recommended_friend = recommended
        rec_name = str(recommended.get("friend_name") or recommended.get("name") or "暂无好友")
        rec_temp = dict(recommended.get("relation_temperature") or {})
        rec_score = int(rec_temp.get("score") or 0)
        rec_label = str(rec_temp.get("label") or "关系样本")
        rec_summary = str(recommended.get("cover_line") or snapshot.get("trend_conclusion") or "")
        AvatarLoader.set_avatar(self.ov_friend_preview_avatar, str(recommended.get("avatar_url") or ""), rec_name)
        self.ov_friend_preview_name.setText(rec_name)
        self.ov_friend_preview_temp.setText(f"{rec_label} {rec_score}" if rec_score else rec_label)
        self.ov_friend_preview_desc.setText(rec_summary or "当前最值得打开的好友关系画像。")
        self.ov_friend_spot_title.setText("推荐查看好友")
        self.ov_friend_spot_detail.setToolTip(rec_summary or "")
        self.ov_friend_spot_detail.setText(
            f"{rec_name}：{rec_label}，歌曲 {recommended.get('song_share_count_total', 0)} 首 / 消息 {recommended.get('message_count_total', 0)} 条。"
        )

        self.ov_status_spot_title.setText("当前社交状态")
        self.ov_status_spot_detail.setToolTip(
            f"音乐社交：{music_balance_label}；聊天社交：{chat_balance_label}；核心圈层：{concentration_label}。"
        )
        self.ov_status_spot_detail.setText(
            f"音乐 {music_balance_label}，聊天 {chat_balance_label}；圈层 {concentration_label}。"
        )
        self.ov_self_preview_title.setText(f"{self_snapshot.get('account_name') or '我'} 的音乐社交")
        self.ov_self_preview_tag.setText(f"社交标签：{self_snapshot.get('social_tag') or '暂无判断'}")
        cover_line = str(self_snapshot.get("cover_line") or "查看所有好友共同塑造出的音乐社交结构。")
        self.ov_self_preview_desc.setText(
            f"音乐 {music_balance_label}，聊天 {chat_balance_label}，圈层 {concentration_label}。{cover_line}"
        )

        self._update_overview_recent_items(snapshot, self_snapshot, recommended)

    @staticmethod
    def _pick_overview_recommended_friend(
        snapshot: Dict[str, Any],
        friend_index: Dict[str, Dict[str, Any]],
        focus_friend: Dict[str, Any],
    ) -> Dict[str, Any]:
        for row in snapshot.get("top_temperature_friends", []) or []:
            uid = str(row.get("uid") or "")
            if uid and uid in friend_index:
                return friend_index[uid]
        for row in snapshot.get("top_song_friends", []) or []:
            uid = str(row.get("uid") or "")
            if uid and uid in friend_index:
                return friend_index[uid]
        return dict(focus_friend or {})

    def _update_overview_recent_items(
        self,
        snapshot: Dict[str, Any],
        self_snapshot: Dict[str, Any],
        recommended: Dict[str, Any],
    ) -> None:
        trend = list(snapshot.get("trend_series") or [])
        peak = max(trend, key=lambda item: int(item.get("msg_count") or 0) + int(item.get("song_count") or 0)) if trend else {}
        events = [
            f"推荐入口：{recommended.get('friend_name') or '暂无好友'}，当前关系温度 {int((recommended.get('relation_temperature') or {}).get('score') or 0)}。",
            f"当前峰值：{peak.get('month') or self_snapshot.get('peak_month') or '-'}，消息 {int(peak.get('msg_count') or 0)} 条，歌曲 {int(peak.get('song_count') or 0)} 首。",
            f"社交结构：{self_snapshot.get('social_tag') or '暂无判断'}，核心对象 {self_snapshot.get('core_friend_name') or '暂无'}。",
            f"记忆点：第一次被带入歌手 {self_snapshot.get('first_introduced_artist') or '暂无'}。",
        ]
        for label, text in zip(self.ov_recent_items, events):
            label.setText(text)

    def _update_overview_report_hint(self, report_count: int, latest_report: Dict[str, Any] | None = None) -> None:
        if not hasattr(self, "ov_report_spot_detail"):
            return
        if report_count <= 0:
            self.ov_report_spot_detail.setText("暂无已归档报告，可以先从单好友画像或我的音乐社交生成第一份。")
            self.ov_report_spot_detail.setToolTip("")
            return
        latest = dict(latest_report or {})
        latest_title = str(latest.get("title") or latest.get("display_type") or "最近报告")
        latest_short = self._compact_overview_text(latest_title, 18)
        latest_time = str(latest.get("generated_at") or "")
        tooltip = f"已归档 {report_count} 份。最近生成：{latest_title}"
        if latest_time:
            tooltip = f"{tooltip}（{latest_time}）"
        self.ov_report_spot_detail.setToolTip(tooltip)
        self.ov_report_spot_detail.setText(f"已归档 {report_count} 份；最近新增：{latest_short}。")

    @staticmethod
    def _compact_overview_text(text: str, max_chars: int) -> str:
        value = " ".join(str(text or "").split())
        if len(value) <= max_chars:
            return value or "暂无"
        return f"{value[:max_chars - 1]}…"

    def _go_to_relation_tab(self, key: str) -> None:
        self.sub_nav.set_current(key)
        self._switch_tab(key)

    def _open_overview_friend_preview(self) -> None:
        friend = dict(getattr(self, "_overview_recommended_friend", {}) or {})
        uid = str(friend.get("uid") or "")
        if uid:
            self.controller.select_friend(
                FriendEntry(
                    uid=uid,
                    nickname=str(friend.get("friend_name") or friend.get("name") or "好友"),
                    avatar_url=str(friend.get("avatar_url") or ""),
                )
            )
            self.refresh_content(force=True)
        self._go_to_relation_tab("friend")

    def _render_friend(self, snapshot: Dict[str, Any]) -> None:
        name = snapshot.get("friend_name") or "未选择好友"
        tags = " / ".join(snapshot.get("personality_tags", [])) or "暂无标签"
        self.friend_hero.setText(f"{name} · {tags}")
        self.friend_cover_line.setText(str(snapshot.get("cover_line") or "关系封面语待生成。"))
        AvatarLoader.set_avatar(
            self.friend_hero_avatar,
            str(snapshot.get("avatar_url") or ""),
            str(name or "友"),
        )
        relation_temp = snapshot.get("relation_temperature", {})
        self.friend_temp_badge.setText(
            f"{relation_temp.get('label') or '关系温度'} {int(relation_temp.get('score') or 0)}"
        )
        self.friend_msg_card.set_value(str(snapshot.get("message_count_total", 0)))
        self.friend_song_card.set_value(str(snapshot.get("song_share_count_total", 0)))
        self.friend_active_card.set_value(str(snapshot.get("active_days_total", 0)))
        self.friend_night_card.set_value(f"{float(snapshot.get('night_share_ratio', 0.0)) * 100:.1f}%")
        self.friend_first_share_card.set_value(str(snapshot.get("first_share_at") or "-"))
        self.friend_recent_share_card.set_value(str(snapshot.get("recent_share_at") or "-"))
        self.friend_avg_freq_card.set_value(f"{float(snapshot.get('avg_share_frequency') or 0.0):.2f}/天")
        trend = snapshot.get("trend_series", [])
        timeline_visual = snapshot.get("timeline_visual", {})
        self.friend_rhythm_chart.set_relationship_rhythm_timeline(
            "",
            trend,
            timeline_visual,
            note=str(timeline_visual.get("summary") or snapshot.get("trend_conclusion") or ""),
        )
        self.friend_heat_chart.set_heatmap("", snapshot.get("hour_heatmap", []))

        top_artists = "、".join(item.get("name") for item in snapshot.get("top_artists", [])[:3] if item.get("name")) or "暂无"
        top_genres = "、".join(item.get("name") for item in snapshot.get("top_genres", [])[:3] if item.get("name")) or "暂无"
        top_moods = "、".join(item.get("name") for item in snapshot.get("top_moods", [])[:3] if item.get("name")) or "暂无"
        portrait_note = (
            f"画像摘要：Top风格 {top_genres}；Top情绪 {top_moods}；"
            f"Top歌手 {top_artists}；首次被带入歌手 {snapshot.get('first_introduced_artist') or '暂无'}。"
        )
        self.friend_music_portrait_chart.set_music_portrait(
            "",
            snapshot.get("top_genres", []),
            snapshot.get("top_moods", []),
            snapshot.get("top_artists", []),
            note=portrait_note,
        )
        common_world = snapshot.get("common_world", {})
        self.friend_common_world_chart.set_common_world_compare(
            "",
            common_world,
            note=str(common_world.get("summary") or ""),
        )
        self._fill_evidence_list(self.friend_evidence_list, snapshot.get("evidence_tracks", []))
        self.friend_ai_trust.setText("依据来自：趋势、Top歌手、证据歌曲、活跃时段")

    def _render_self(self, snapshot: Dict[str, Any]) -> None:
        account_name = str(snapshot.get("account_name") or "我")
        account_avatar_url = str(snapshot.get("account_avatar_url") or snapshot.get("avatar_url") or "")
        social_tag = str(snapshot.get("social_tag") or "社交均衡型")
        self.self_hero.setText(f"{account_name} 的音乐社交封面 · {social_tag}")
        self.self_story_note.setText(str(snapshot.get("cover_line") or "我的社交画像结论待生成。"))
        self.self_friend_card.set_value(str(snapshot.get("friend_count", 0)))
        self.self_message_card.set_value(str(snapshot.get("message_count", 0)))
        self.self_song_card.set_value(str(snapshot.get("song_count", 0)))
        self.self_peak_card.set_value(str(snapshot.get("peak_month") or "-"))

        friend_index = self._build_snapshot_index(self._latest_payload.get("friends", []))
        self._fill_rank_cards(
            self.self_chat_rank,
            snapshot.get("top_chat_friends", []),
            "count",
            "条消息",
            friend_index,
            uniform=True,
        )
        self._fill_rank_cards(
            self.self_song_rank,
            snapshot.get("top_song_friends", []),
            "count",
            "首歌曲",
            friend_index,
            uniform=True,
        )
        self._fill_rank_cards(
            self.self_temp_rank,
            snapshot.get("top_temperature_friends", []),
            "count",
            "分",
            friend_index,
            uniform=True,
        )

        network_block = dict(snapshot.get("network_block") or {})
        music_balance = dict(network_block.get("music_balance") or {})
        chat_balance = dict(network_block.get("chat_balance") or {})
        music_concentration = dict(network_block.get("music_concentration") or {})
        chat_concentration = dict(network_block.get("chat_concentration") or {})
        self.self_music_balance_card.set_value(str(music_balance.get("label") or "暂无样本"))
        self.self_chat_balance_card.set_value(str(chat_balance.get("label") or "暂无样本"))
        self.self_music_conc_card.set_value(str(music_concentration.get("label") or "暂无样本"))
        self.self_chat_conc_card.set_value(str(chat_concentration.get("label") or "暂无样本"))
        self.self_struct_note.setText(
            "；".join(
                [
                    str(music_balance.get("summary") or "音乐输入输出状态待计算。"),
                    str(chat_balance.get("summary") or "聊天输入输出状态待计算。"),
                    str(music_concentration.get("summary") or "音乐圈层浓度待计算。"),
                    str(chat_concentration.get("summary") or "聊天圈层浓度待计算。"),
                ]
            )
        )

        music_input_block = dict(network_block.get("music_input_block") or {})
        music_output_block = dict(network_block.get("music_output_block") or {})
        chat_input_block = dict(network_block.get("chat_input_block") or {})
        chat_output_block = dict(network_block.get("chat_output_block") or {})
        self.self_music_in_chart.set_social_network_graph(
            "",
            account_name,
            music_input_block.get("items") or [],
            unit=str(music_input_block.get("unit") or "首"),
            empty_text=str(music_input_block.get("empty_text") or "暂无音乐输入数据"),
            note=str(music_input_block.get("summary") or ""),
            center_avatar_url=account_avatar_url,
            layout_key="music_input",
        )
        self.self_music_out_chart.set_social_network_graph(
            "",
            account_name,
            music_output_block.get("items") or [],
            unit=str(music_output_block.get("unit") or "首"),
            empty_text=str(music_output_block.get("empty_text") or "暂无音乐输出数据"),
            note=str(music_output_block.get("summary") or ""),
            center_avatar_url=account_avatar_url,
            layout_key="music_output",
        )
        self.self_chat_in_chart.set_social_network_graph(
            "",
            account_name,
            chat_input_block.get("items") or [],
            unit=str(chat_input_block.get("unit") or "条"),
            empty_text=str(chat_input_block.get("empty_text") or "暂无聊天输入数据"),
            note=str(chat_input_block.get("summary") or ""),
            center_avatar_url=account_avatar_url,
            layout_key="chat_input",
        )
        self.self_chat_out_chart.set_social_network_graph(
            "",
            account_name,
            chat_output_block.get("items") or [],
            unit=str(chat_output_block.get("unit") or "条"),
            empty_text=str(chat_output_block.get("empty_text") or "暂无聊天输出数据"),
            note=str(chat_output_block.get("summary") or ""),
            center_avatar_url=account_avatar_url,
            layout_key="chat_output",
        )

        timeline_visual = dict(snapshot.get("timeline_visual") or {})
        self.self_rhythm_chart.set_relationship_rhythm_timeline(
            "",
            snapshot.get("trend_series") or [],
            timeline_visual,
            note=str(timeline_visual.get("summary") or snapshot.get("trend_conclusion") or ""),
        )

        self._fill_evidence_list(self.self_evidence_list, snapshot.get("evidence_tracks", []))
        self._render_annual_showcase(snapshot.get("annual_review", {}), snapshot)
        self.self_ai_trust.setText("依据来自：趋势、Top歌手、证据歌曲、活跃时段")

    @staticmethod
    def _build_snapshot_index(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        index: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            uid = str(row.get("uid") or "").strip()
            if uid:
                index[uid] = row
        return index

    def _fill_rank_cards(
        self,
        widget: QtWidgets.QListWidget,
        rows: List[Dict[str, Any]],
        count_key: str,
        unit: str,
        snapshot_index: Dict[str, Dict[str, Any]],
        uniform: bool = False,
    ) -> None:
        widget.clear()
        if not rows:
            widget.addItem("暂无数据")
            return
        for index, row in enumerate(rows[:3], start=1):
            uid = str(row.get("uid") or "")
            name = row.get("name") or row.get("friend_name") or uid or "-"
            count = int(row.get(count_key) or 0)
            friend_snapshot = snapshot_index.get(uid, {})
            temp = friend_snapshot.get("relation_temperature", {})
            temp_label = str(temp.get("label") or "关系样本")
            trend = friend_snapshot.get("trend_series") or []
            delta = 0
            if len(trend) >= 2:
                delta = int(trend[-1].get("song_count") or 0) - int(trend[-2].get("song_count") or 0)
            state = "升温" if delta > 0 else ("回暖" if delta == 0 and count > 0 else "回落")
            if delta == 0:
                state = "稳定"
            detail = f"{count}{unit} · {state} · {temp_label}"
            self._add_rank_card_item(
                widget,
                rank=index,
                name=str(name),
                detail=detail,
                avatar_url=str(friend_snapshot.get("avatar_url") or ""),
                uniform=uniform,
            )

    @staticmethod
    def _fill_evidence_list(widget: QtWidgets.QListWidget, rows: List[Dict[str, Any]]) -> None:
        widget.clear()
        if not rows:
            widget.addItem("暂无证据歌曲。")
            return
        for row in rows[:5]:
            support = [str(item) for item in (row.get("support_for") or []) if str(item).strip()]
            support_text = " / ".join(support) if support else "样本支撑"
            MusicRelationPage._add_summary_card_item(
                widget,
                tag=str(row.get("reason_tag") or "样本"),
                title=f"{row.get('song_name') or '未知歌曲'} - {row.get('artist_name') or '未知歌手'}",
                detail=f"{row.get('msg_time') or '-'} · {row.get('reason') or '样本'}\n支撑：{support_text}",
            )

    @staticmethod
    def _add_summary_card_item(widget: QtWidgets.QListWidget, tag: str, title: str, detail: str) -> None:
        item = QtWidgets.QListWidgetItem(widget)
        card = QtWidgets.QFrame()
        card.setObjectName("relationMiniCard")
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(10, 9, 10, 9)
        card_layout.setSpacing(6)

        top_row = QtWidgets.QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        tag_label = QtWidgets.QLabel(tag)
        tag_label.setObjectName("relationMiniTag")
        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("relationMiniTitle")
        title_label.setWordWrap(True)
        top_row.addWidget(tag_label, 0)
        top_row.addWidget(title_label, 1)
        card_layout.addLayout(top_row)

        detail_label = QtWidgets.QLabel(detail)
        detail_label.setObjectName("relationMiniDetail")
        detail_label.setWordWrap(True)
        card_layout.addWidget(detail_label)

        item.setSizeHint(card.sizeHint())
        widget.addItem(item)
        widget.setItemWidget(item, card)

    def _add_rank_card_item(
        self,
        widget: QtWidgets.QListWidget,
        rank: int,
        name: str,
        detail: str,
        avatar_url: str,
        uniform: bool = False,
    ) -> None:
        item = QtWidgets.QListWidgetItem(widget)
        card = QtWidgets.QFrame()
        card.setObjectName("relationMiniCard")
        if uniform:
            card.setFixedHeight(66)
            card.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        card_layout = QtWidgets.QHBoxLayout(card)
        card_layout.setContentsMargins(10, 7 if uniform else 9, 10, 7 if uniform else 9)
        card_layout.setSpacing(9 if uniform else 10)

        avatar = QtWidgets.QLabel()
        avatar.setObjectName("friendAvatar")
        avatar.setMinimumSize(34, 34)
        avatar.setMaximumSize(34, 34)
        AvatarLoader.set_avatar(avatar, avatar_url, name)
        card_layout.addWidget(avatar, 0, QtCore.Qt.AlignTop)

        text_col = QtWidgets.QVBoxLayout()
        text_col.setSpacing(4)
        top_row = QtWidgets.QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        rank_label = QtWidgets.QLabel(f"TOP {rank}")
        rank_label.setObjectName("relationMiniTag")
        name_label = QtWidgets.QLabel(name)
        name_label.setObjectName("relationMiniTitle")
        name_label.setWordWrap(False if uniform else True)
        if uniform:
            name_label.setMaximumHeight(20)
            name_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        top_row.addWidget(rank_label, 0)
        top_row.addWidget(name_label, 1)
        text_col.addLayout(top_row)
        detail_label = QtWidgets.QLabel(detail)
        detail_label.setObjectName("relationMiniDetail")
        detail_label.setWordWrap(False if uniform else True)
        if uniform:
            detail_label.setMaximumHeight(18)
            detail_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        text_col.addWidget(detail_label)
        card_layout.addLayout(text_col, 1)

        item.setSizeHint(QtCore.QSize(0, 72) if uniform else card.sizeHint())
        widget.addItem(item)
        widget.setItemWidget(item, card)

    @staticmethod
    def _mode_key(text: str) -> str:
        if text == "评论版":
            return "commentary"
        if text == "年度报告版":
            return "annual"
        return "style" if text == "风格版" else "rational"

    @staticmethod
    def _report_type_key(text: str) -> str:
        mapping = {
            "全部报告": "all",
            "好友报告": "friend",
            "个人报告": "self",
            "年度回顾": "annual",
        }
        return mapping.get(text, "all")

    def _render_annual_showcase(self, payload: Dict[str, Any], self_snapshot: Dict[str, Any] | None = None) -> None:
        snapshot = dict(self_snapshot or {})
        window_key = self._dashboard_window()
        if window_key.startswith("year:"):
            year_text = window_key.split(":", 1)[1]
            self.annual_hero_title.setText(f"{year_text} 年度音乐社交回顾")
            self.annual_hero_mark.setText(f"{year_text} REVIEW")
            self.annual_hero_summary.setText(str(payload.get("summary") or "暂无年度摘要。"))
            self.annual_metric_message.setText(f"{int(payload.get('message_count') or 0)} 条")
            self.annual_metric_song.setText(f"{int(payload.get('song_count') or 0)} 首")
            self.annual_metric_peak.setText(str(payload.get("peak_month") or "-"))
            lead_name = str(
                payload.get("representative_relationship")
                or payload.get("top_song_friend_name")
                or payload.get("top_chat_friend_name")
                or "暂无"
            )
            self.annual_lead_name.setText(lead_name)
            self.annual_lead_detail.setText(
                f"聊天最多：{payload.get('top_chat_friend_name') or '暂无'}（{int(payload.get('top_chat_friend_count') or 0)} 条）\n"
                f"发歌最多：{payload.get('top_song_friend_name') or '暂无'}（{int(payload.get('top_song_friend_count') or 0)} 首）"
            )
            return

        self.annual_hero_title.setText("全部历史音乐社交回顾")
        self.annual_hero_mark.setText("ALL HISTORY")
        self.annual_hero_summary.setText(
            str(
                snapshot.get("cover_line")
                or payload.get("summary")
                or "暂无全量历史摘要。"
            )
        )
        self.annual_metric_message.setText(f"{int(snapshot.get('message_count') or 0)} 条")
        self.annual_metric_song.setText(f"{int(snapshot.get('song_count') or 0)} 首")
        self.annual_metric_peak.setText(str(snapshot.get("peak_month") or payload.get("peak_month") or "-"))
        lead_name = str(snapshot.get("core_friend_name") or payload.get("representative_relationship") or "暂无")
        self.annual_lead_name.setText(lead_name)
        self.annual_lead_detail.setText(
            f"聊天最多：{snapshot.get('top_chat_friends', [{}])[0].get('name') if snapshot.get('top_chat_friends') else '暂无'}\n"
            f"发歌最多：{snapshot.get('top_song_friends', [{}])[0].get('name') if snapshot.get('top_song_friends') else '暂无'}"
        )

    def _generate_friend_insight(self) -> None:
        self.friend_ai_button.setEnabled(False)
        run_async(
            self.thread_pool,
            self.controller.generate_friend_insight,
            self._on_friend_insight_ready,
            self._on_error,
            lambda: self.friend_ai_button.setEnabled(True),
            self._mode_key(self.friend_mode_combo.currentText()),
            self._dashboard_window(),
        )

    def _generate_self_insight(self) -> None:
        self.self_ai_button.setEnabled(False)
        run_async(
            self.thread_pool,
            self.controller.generate_self_insight,
            self._on_self_insight_ready,
            self._on_error,
            lambda: self.self_ai_button.setEnabled(True),
            self._mode_key(self.self_mode_combo.currentText()),
            self._dashboard_window(),
        )

    def _on_friend_insight_ready(self, payload: Dict[str, Any]) -> None:
        self._latest_friend_insight = payload
        self.friend_ai_source.setText("云端" if payload.get("source") == "cloud" else "本地模板")
        self.friend_ai_text.setPlainText(str(payload.get("text") or ""))
        self.friend_ai_trust.setText(str(payload.get("trust_basis") or "依据来自：趋势、Top歌手、证据歌曲、活跃时段"))
        evidence = payload.get("evidence_tracks") or self._latest_payload.get("friend", {}).get("evidence_tracks", [])
        self._fill_evidence_list(self.friend_evidence_list, evidence)

    def _on_self_insight_ready(self, payload: Dict[str, Any]) -> None:
        self._latest_self_insight = payload
        self.self_ai_source.setText("云端" if payload.get("source") == "cloud" else "本地模板")
        self.self_ai_text.setPlainText(str(payload.get("text") or ""))
        self.self_ai_trust.setText(str(payload.get("trust_basis") or "依据来自：趋势、Top歌手、证据歌曲、活跃时段"))
        evidence = payload.get("evidence_tracks") or self._latest_payload.get("self", {}).get("evidence_tracks", [])
        self._fill_evidence_list(self.self_evidence_list, evidence)

    def _export_friend_report(self) -> None:
        self.friend_export_button.setEnabled(False)
        run_async(
            self.thread_pool,
            self.controller.export_friend_report,
            self._on_report_exported,
            self._on_error,
            lambda: self.friend_export_button.setEnabled(True),
            self._mode_key(self.friend_mode_combo.currentText()),
            self._dashboard_window(),
        )

    def _export_self_report(self) -> None:
        self.self_export_button.setEnabled(False)
        run_async(
            self.thread_pool,
            self.controller.export_self_report,
            self._on_report_exported,
            self._on_error,
            lambda: self.self_export_button.setEnabled(True),
            self._mode_key(self.self_mode_combo.currentText()),
            self._dashboard_window(),
        )

    def _export_annual_report(self) -> None:
        self.annual_export_button.setEnabled(False)
        run_async(
            self.thread_pool,
            self.controller.export_annual_report,
            self._on_report_exported,
            self._on_error,
            lambda: self.annual_export_button.setEnabled(True),
            "annual",
            self._dashboard_window(),
        )

    def _on_report_exported(self, payload: Dict[str, Any]) -> None:
        path = str(payload.get("path") or "")
        self.status_label.setText(f"已导出报告：{path}")
        self.sub_nav.set_current("report")
        self.refresh_reports()

    def refresh_reports(self) -> None:
        reports = self.controller.list_relation_reports(
            report_type=self._report_type_key(self.report_type_combo.currentText()),
            keyword=self.report_search_edit.text(),
        )
        self.report_list.clear()
        if not reports:
            self.report_list.addItem("暂无已导出报告。")
            self.status_label.setText("报告中心：暂无匹配结果。")
            self._update_overview_report_hint(0)
            return
        for item in reports:
            self._add_report_item(item)
        self.status_label.setText(f"报告中心：已加载 {len(reports)} 条。")
        self._update_overview_report_hint(len(reports), reports[0])

    def _add_report_item(self, report: Dict[str, Any]) -> None:
        item = QtWidgets.QListWidgetItem(self.report_list)
        item.setData(QtCore.Qt.UserRole, str(report.get("path") or ""))
        card = QtWidgets.QFrame()
        card.setObjectName("relationMiniCard")
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(10, 9, 10, 9)
        card_layout.setSpacing(6)

        top_row = QtWidgets.QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        tag_label = QtWidgets.QLabel(str(report.get("display_type") or "报告"))
        tag_label.setObjectName("relationMiniTag")
        title_label = QtWidgets.QLabel(str(report.get("title") or "未命名报告"))
        title_label.setObjectName("relationMiniTitle")
        title_label.setWordWrap(True)
        top_row.addWidget(tag_label, 0)
        top_row.addWidget(title_label, 1)
        card_layout.addLayout(top_row)

        generated_at = str(report.get("generated_at") or "-")
        path = str(report.get("path") or "")
        summary = str(report.get("summary") or "")
        lead = str(report.get("lead") or "")
        summary_line = f"{summary}\n" if summary else ""
        lead_line = f"主角：{lead}\n" if lead else ""
        detail_label = QtWidgets.QLabel(f"{summary_line}{lead_line}{generated_at}\n{path}")
        detail_label.setObjectName("relationMiniDetail")
        detail_label.setWordWrap(True)
        detail_label.setToolTip(path)
        card_layout.addWidget(detail_label)

        item.setSizeHint(card.sizeHint())
        self.report_list.addItem(item)
        self.report_list.setItemWidget(item, card)

    def _open_report_dir(self) -> None:
        report_dir = str(self.controller.report_directory())
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(report_dir))

    def _open_report_file(self, item: QtWidgets.QListWidgetItem) -> None:
        path = str(item.data(QtCore.Qt.UserRole) or "")
        if not path:
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))

    def _cleanup_reports(self) -> None:
        result = self.controller.cleanup_relation_reports()
        removed = int(result.get("removed") or 0)
        kept = int(result.get("kept") or 0)
        self.status_label.setText(f"已清理失效记录 {removed} 条，剩余 {kept} 条。")
        self.refresh_reports()

    def _on_error(self, error_text: str) -> None:
        self.status_label.setText("操作失败")
        message = error_text.strip().splitlines()[-1]
        QtWidgets.QMessageBox.warning(self, "音乐关系", message)
