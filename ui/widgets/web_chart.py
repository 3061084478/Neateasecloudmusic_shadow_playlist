from __future__ import annotations

import hashlib
import math
from html import escape
from typing import Iterable, List

from PySide6 import QtCore, QtWidgets

try:
    from PySide6 import QtWebEngineWidgets
except Exception:  # pragma: no cover - optional runtime
    QtWebEngineWidgets = None


class WebChartWidget(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._preferred_height = 240
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self._is_webengine = QtWebEngineWidgets is not None
        if self._is_webengine:
            self._view = QtWebEngineWidgets.QWebEngineView()
            self._view.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
            self._view.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
            layout.addWidget(self._view)
        else:
            browser = QtWidgets.QTextBrowser()
            browser.setOpenExternalLinks(False)
            browser.setReadOnly(True)
            browser.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
            browser.setFrameShape(QtWidgets.QFrame.NoFrame)
            browser.setStyleSheet(
                "QTextBrowser {background: rgba(17, 27, 40, 0.96); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px;}"
            )
            self._view = browser
            layout.addWidget(browser)
        self._set_preferred_height(self._preferred_height)

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(640, self._preferred_height)

    def minimumSizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(320, self._preferred_height)

    def _set_preferred_height(self, height: int) -> None:
        bounded = max(140, min(620, int(height)))
        self._preferred_height = bounded
        self._view.setFixedHeight(bounded)
        self.setFixedHeight(bounded)

    def _set_html(self, html: str) -> None:
        if self._is_webengine:
            self._view.setHtml(html)  # type: ignore[attr-defined]
        else:
            self._view.setHtml(html)

    @staticmethod
    def _shell_html(title: str, content: str) -> str:
        title_html = f"<div class='title'>{escape(title)}</div>" if str(title or "").strip() else ""
        return f"""
        <html>
          <head>
            <meta charset="utf-8" />
            <style>
              body {{
                margin: 0;
                padding: 12px 14px;
                background: #121b29;
                color: #eef4fb;
                font-family: 'Microsoft YaHei UI', sans-serif;
                font-size: 12px;
              }}
              .title {{
                font-size: 13px;
                font-weight: 700;
                margin-bottom: 10px;
                color: #f4f8ff;
              }}
              .muted {{
                color: rgba(238, 244, 251, 0.66);
              }}
              .legend {{
                display: flex;
                align-items: center;
                gap: 14px;
                margin-bottom: 8px;
              }}
              .legend-item {{
                display: inline-flex;
                align-items: center;
                gap: 6px;
                color: rgba(238, 244, 251, 0.82);
                font-size: 12px;
              }}
              .dot {{
                width: 10px;
                height: 10px;
                border-radius: 50%;
                display: inline-block;
              }}
              .dot-primary {{
                background: #6fb7ff;
              }}
              .dot-secondary {{
                background: #ff6f7d;
              }}
              .grid {{
                display: grid;
                grid-template-columns: 120px 1fr 56px;
                gap: 6px 10px;
                align-items: center;
              }}
              .rows-scroll {{
                max-height: 370px;
                overflow-y: auto;
                padding-right: 6px;
              }}
              .rows-scroll::-webkit-scrollbar {{
                width: 8px;
              }}
              .rows-scroll::-webkit-scrollbar-thumb {{
                background: rgba(255, 255, 255, 0.18);
                border-radius: 6px;
              }}
              .bar-wrap {{
                height: 12px;
                border-radius: 8px;
                background: rgba(255,255,255,0.08);
                overflow: hidden;
              }}
              .bar {{
                height: 12px;
                border-radius: 8px;
                background: linear-gradient(90deg, #6fb7ff 0%, #4d9fff 100%);
              }}
              .bar2 {{
                height: 12px;
                border-radius: 8px;
                background: linear-gradient(90deg, #ff8a94 0%, #ff616f 100%);
                margin-top: 4px;
              }}
              .peak-tag {{
                display: inline-block;
                margin-left: 8px;
                padding: 1px 6px;
                border-radius: 9px;
                background: rgba(255, 196, 74, 0.2);
                border: 1px solid rgba(255, 196, 74, 0.55);
                color: #ffd478;
                font-size: 10px;
                font-weight: 700;
              }}
              .note {{
                margin-top: 8px;
                padding: 7px 10px;
                border-radius: 10px;
                background: linear-gradient(180deg, rgba(22, 35, 53, 0.78), rgba(13, 23, 37, 0.82));
                border: 1px solid rgba(125, 181, 224, 0.16);
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.035);
                color: rgba(238, 244, 251, 0.86);
                font-size: 12px;
              }}
              .chip {{
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 2px 8px;
                margin-right: 5px;
                background: rgba(127, 211, 255, 0.16);
                border: 1px solid rgba(127, 211, 255, 0.35);
                color: #cdefff;
                font-size: 11px;
              }}
              .chip-day {{
                background: rgba(105, 183, 255, 0.18);
                border-color: rgba(105, 183, 255, 0.42);
                color: #d8eeff;
              }}
              .chip-night {{
                background: rgba(255, 138, 148, 0.18);
                border-color: rgba(255, 138, 148, 0.42);
                color: #ffe1e4;
              }}
              .chip-late {{
                background: rgba(172, 126, 255, 0.18);
                border-color: rgba(172, 126, 255, 0.42);
                color: #eadbff;
              }}
              .heat {{
                display: grid;
                grid-template-columns: repeat(12, minmax(0, 1fr));
                gap: 5px;
              }}
              .cell {{
                border-radius: 8px;
                height: 26px;
                border: 1px solid rgba(255,255,255,0.08);
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                font-size: 11px;
              }}
              .timeline-rows {{
                display: grid;
                grid-template-columns: 92px 1fr 72px;
                gap: 6px 10px;
                align-items: center;
              }}
              .rhythm-rows {{
                display: grid;
                grid-template-columns: 82px 1fr 34px 34px;
                gap: 7px 10px;
                align-items: center;
              }}
              .rhythm-top {{
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 8px;
                margin-bottom: 5px;
              }}
              .rhythm-legend {{
                margin-bottom: 0;
              }}
              .rhythm-heads {{
                display: grid;
                grid-template-columns: 46px 46px;
                gap: 4px;
                flex-shrink: 0;
              }}
              .rhythm-head {{
                text-align: center;
                font-size: 11px;
                font-weight: 700;
                line-height: 14px;
                border-radius: 7px;
                padding: 3px 0;
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.12);
              }}
              .rhythm-head.msg {{
                color: #79beff;
                border-color: rgba(111, 183, 255, 0.38);
                background: rgba(111, 183, 255, 0.10);
              }}
              .rhythm-head.song {{
                color: #ff99a4;
                border-color: rgba(255, 138, 148, 0.38);
                background: rgba(255, 138, 148, 0.10);
              }}
              .rhythm-value {{
                text-align: center;
                font-size: 11px;
                font-weight: 700;
              }}
              .rhythm-value.msg {{
                color: #89c8ff;
              }}
              .rhythm-value.song {{
                color: #ffacb5;
              }}
              .rhythm-table {{
                width: 100%;
                table-layout: fixed;
                border-collapse: collapse;
                border-spacing: 0;
                overflow: hidden;
                border-radius: 8px;
              }}
              .rhythm-col-month {{
                width: 78px;
              }}
              .rhythm-col-msg {{
                width: 46px;
              }}
              .rhythm-col-song {{
                width: 46px;
              }}
              .rhythm-table td {{
                padding: 5px 7px;
                vertical-align: middle;
              }}
              .rhythm-table tr.odd td {{
                background: rgba(255, 255, 255, 0.035);
              }}
              .rhythm-table tr.even td {{
                background: rgba(255, 255, 255, 0.07);
              }}
              .rhythm-month {{
                white-space: nowrap;
                color: rgba(238, 244, 251, 0.8);
                font-size: 11px;
              }}
              .phase-track {{
                border-radius: 8px;
                height: 12px;
                background: rgba(255,255,255,0.08);
                overflow: hidden;
              }}
              .phase-fill {{
                height: 12px;
                border-radius: 8px;
              }}
              .event-list {{
                margin-top: 10px;
                display: flex;
                flex-direction: column;
                gap: 7px;
              }}
              .event-item {{
                display: grid;
                grid-template-columns: 16px 1fr;
                gap: 8px;
                align-items: stretch;
                padding: 8px 10px;
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.10);
                background: linear-gradient(135deg, rgba(255,255,255,0.065), rgba(255,255,255,0.028));
              }}
              .event-rail {{
                position: relative;
                display: flex;
                justify-content: center;
              }}
              .event-dot {{
                width: 8px;
                height: 8px;
                border-radius: 50%;
                margin-top: 4px;
                background: #7fb8ff;
                box-shadow: 0 0 0 2px rgba(127,184,255,0.16);
              }}
              .event-line {{
                position: absolute;
                top: 14px;
                bottom: -8px;
                width: 1px;
                background: rgba(127,184,255,0.28);
              }}
              .event-title {{
                display: flex;
                align-items: center;
                gap: 8px;
                color: #f1f7ff;
                font-size: 12px;
                font-weight: 700;
                line-height: 16px;
              }}
              .event-time {{
                color: #8ac2ff;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.2px;
                flex-shrink: 0;
              }}
              .event-detail {{
                margin-top: 3px;
                color: rgba(238, 244, 251, 0.82);
                font-size: 11px;
                line-height: 16px;
              }}
              .portrait-layout {{
                display: grid;
                grid-template-columns: 1fr 1fr 1fr;
                gap: 9px;
              }}
              .portrait-panel {{
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 7px;
                background: rgba(255,255,255,0.03);
              }}
              .panel-title {{
                color: rgba(238, 244, 251, 0.86);
                font-size: 12px;
                font-weight: 700;
                margin-bottom: 7px;
              }}
              .donut {{
                width: 106px;
                height: 106px;
                border-radius: 50%;
                margin: 0 auto 7px auto;
                position: relative;
              }}
              .donut::after {{
                content: '';
                position: absolute;
                inset: 22px;
                border-radius: 50%;
                background: #121b29;
                border: 1px solid rgba(255,255,255,0.08);
              }}
              .tiny-list {{
                display: flex;
                flex-direction: column;
                gap: 5px;
              }}
              .tiny-item {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 8px;
                font-size: 11px;
                color: rgba(238, 244, 251, 0.84);
              }}
              .legend-swatch {{
                width: 10px;
                height: 10px;
                border-radius: 50%;
                display: inline-block;
                margin-right: 6px;
              }}
              .mood-grid {{
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 7px;
              }}
              .mood-card {{
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 10px;
                background: linear-gradient(135deg, rgba(111,183,255,0.18), rgba(78,227,193,0.14));
                padding: 7px;
                min-height: 46px;
              }}
              .mood-name {{
                font-size: 12px;
                color: #f2f7ff;
                font-weight: 700;
              }}
              .mood-meta {{
                margin-top: 4px;
                font-size: 11px;
                color: rgba(238, 244, 251, 0.8);
              }}
              .podium {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 6px;
                align-items: end;
                min-height: 108px;
              }}
              .podium-step {{
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px 8px 0 0;
                background: rgba(255,255,255,0.06);
                padding: 6px 4px;
                text-align: center;
                font-size: 11px;
                color: #eef4fb;
              }}
              .podium-step.gold {{
                background: linear-gradient(180deg, rgba(255,203,92,0.32), rgba(255,184,56,0.18));
                border-color: rgba(255, 210, 115, 0.62);
              }}
              .podium-step.silver {{
                background: linear-gradient(180deg, rgba(165,205,239,0.28), rgba(129,173,211,0.16));
                border-color: rgba(183, 216, 245, 0.56);
              }}
              .podium-step.bronze {{
                background: linear-gradient(180deg, rgba(240,160,118,0.28), rgba(194,119,84,0.16));
                border-color: rgba(236, 167, 132, 0.54);
              }}
              .podium-rank {{
                font-size: 10px;
                opacity: 0.86;
                margin-bottom: 3px;
              }}
              .compare-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
              }}
              .compare-col {{
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                background: rgba(255,255,255,0.03);
                padding: 8px;
              }}
              .compare-col.me {{
                border-color: rgba(118, 186, 255, 0.42);
                background: linear-gradient(145deg, rgba(95, 159, 234, 0.18), rgba(67, 112, 178, 0.08));
              }}
              .compare-col.friend {{
                border-color: rgba(163, 138, 236, 0.44);
                background: linear-gradient(145deg, rgba(142, 112, 216, 0.18), rgba(87, 96, 174, 0.08));
              }}
              .overlap-box {{
                margin-top: 10px;
                border: 1px solid rgba(126, 245, 139, 0.38);
                border-radius: 10px;
                background: rgba(126, 245, 139, 0.08);
                padding: 8px;
              }}
              .network-wrap {{
                border: 1px solid rgba(119, 179, 224, 0.18);
                border-radius: 12px;
                background: linear-gradient(180deg, rgba(21, 32, 49, 0.88), rgba(12, 22, 36, 0.94));
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.04), 0 12px 30px rgba(2, 8, 18, 0.14);
                padding: 8px;
              }}
              .network-canvas {{
                position: relative;
                height: 264px;
                overflow: hidden;
                border-radius: 10px;
                border: 1px solid rgba(121, 171, 214, 0.10);
                background:
                  radial-gradient(circle at 50% 48%, rgba(96, 167, 218, 0.12), transparent 42%),
                  radial-gradient(circle at 72% 26%, rgba(137, 126, 214, 0.08), transparent 34%),
                  radial-gradient(circle at 24% 76%, rgba(83, 196, 196, 0.06), transparent 30%),
                  linear-gradient(145deg, rgba(18, 29, 45, 0.98), rgba(9, 17, 30, 0.98));
              }}
              .network-lines {{
                position: absolute;
                inset: 0;
                width: 100%;
                height: 100%;
                z-index: 1;
                pointer-events: none;
              }}
              .network-lines line {{
                stroke: rgba(121, 173, 219, 0.58);
                stroke-width: 2.2;
                stroke-linecap: round;
                filter: drop-shadow(0 0 3px rgba(89, 164, 215, 0.16));
              }}
              .network-edge {{
                position: absolute;
                left: 50%;
                top: 50%;
                transform-origin: 0 0;
                height: 2px;
                background: linear-gradient(90deg, rgba(111,183,255,0.42), rgba(255,138,148,0.42));
                border-radius: 999px;
                opacity: 0.9;
                z-index: 1;
              }}
              .network-edge-value {{
                position: absolute;
                transform: translate(-50%, -50%);
                padding: 2px 7px;
                border-radius: 999px;
                border: 1px solid rgba(139, 193, 230, 0.28);
                background: linear-gradient(180deg, rgba(15, 27, 43, 0.96), rgba(7, 15, 27, 0.94));
                color: #f0f7ff;
                font-size: 10px;
                font-weight: 700;
                line-height: 1;
                white-space: nowrap;
                z-index: 2;
                box-shadow: 0 4px 12px rgba(2, 8, 18, 0.28), 0 0 0 1px rgba(77, 161, 213, 0.06);
              }}
              .network-node {{
                position: absolute;
                transform: translate(-50%, -50%);
                border-radius: 50%;
                border: 1px solid rgba(157, 197, 230, 0.24);
                box-shadow: 0 8px 22px rgba(0,0,0,0.30), 0 0 0 1px rgba(142,190,229,0.08);
                overflow: hidden;
                display: flex;
                align-items: center;
                justify-content: center;
                text-align: center;
                font-size: 11px;
                font-weight: 700;
                color: #f2f7ff;
                background: rgba(95, 153, 204, 0.18);
                z-index: 3;
              }}
              .network-node.center {{
                width: 52px;
                height: 52px;
                border-color: rgba(126, 214, 218, 0.58);
                background: linear-gradient(135deg, rgba(86, 166, 219, 0.38), rgba(89, 113, 190, 0.24));
                box-shadow: 0 10px 28px rgba(2,8,18,0.34), 0 0 24px rgba(87, 196, 205, 0.18), inset 0 1px 0 rgba(255,255,255,0.14);
              }}
              .network-node.friend {{
                border-color: rgba(168, 197, 226, 0.30);
                background: linear-gradient(135deg, rgba(94, 151, 203, 0.18), rgba(132, 122, 202, 0.14));
                box-shadow: 0 8px 20px rgba(0,0,0,0.30), 0 0 12px rgba(99, 177, 217, 0.10);
              }}
              .network-avatar {{
                display: block;
                width: 100%;
                height: 100%;
                object-fit: cover;
              }}
              .empty-block {{
                min-height: 244px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 10px;
                border: 1px dashed rgba(255,255,255,0.2);
                color: rgba(238,244,251,0.68);
                font-size: 12px;
                background: rgba(255,255,255,0.02);
              }}
            </style>
          </head>
          <body>
            {title_html}
            {content}
          </body>
        </html>
        """

    def set_placeholder(self, title: str, message: str) -> None:
        self._set_preferred_height(160)
        html = self._shell_html(title, f"<div class='muted'>{escape(message)}</div>")
        self._set_html(html)

    def set_single_series(self, title: str, labels: Iterable[str], values: Iterable[int]) -> None:
        pairs = [(str(label), int(value)) for label, value in zip(labels, values)]
        if not pairs:
            self.set_placeholder(title, "暂无数据")
            return
        visible_rows = min(len(pairs), 8)
        self._set_preferred_height(78 + visible_rows * 38)
        max_value = max(value for _, value in pairs) or 1
        rows: List[str] = []
        for label, value in pairs:
            width = int(value / max_value * 100)
            rows.append(
                f"<div class='muted'>{escape(label)}</div>"
                f"<div class='bar-wrap'><div class='bar' style='width:{width}%;'></div></div>"
                f"<div class='muted'>{value}</div>"
            )
        html = self._shell_html(title, f"<div class='grid'>{''.join(rows)}</div>")
        self._set_html(html)

    def set_dual_series(
        self,
        title: str,
        labels: Iterable[str],
        primary: Iterable[int],
        secondary: Iterable[int],
        primary_name: str = "消息",
        secondary_name: str = "歌曲",
        max_visible_rows: int | None = None,
        conclusion: str | None = None,
    ) -> None:
        rows_data = [(str(label), int(v1), int(v2)) for label, v1, v2 in zip(labels, primary, secondary)]
        if not rows_data:
            self.set_placeholder(title, "暂无数据")
            return
        max_value = max(max(v1, v2) for _, v1, v2 in rows_data) or 1
        peak_month = ""
        peak_v1 = 0
        peak_v2 = 0
        for month, v1, v2 in rows_data:
            if (v1 + v2) > (peak_v1 + peak_v2):
                peak_month = month
                peak_v1 = v1
                peak_v2 = v2
        legend_html = (
            "<div class='legend'>"
            f"<span class='legend-item'><span class='dot dot-primary'></span>{escape(primary_name)}</span>"
            f"<span class='legend-item'><span class='dot dot-secondary'></span>{escape(secondary_name)}</span>"
            "</div>"
        )
        rows: List[str] = []
        for label, v1, v2 in rows_data:
            width1 = int(v1 / max_value * 100)
            width2 = int(v2 / max_value * 100)
            peak_tag = "<span class='peak-tag'>峰值</span>" if label == peak_month else ""
            rows.append(
                f"<div class='muted'>{escape(label)}</div>"
                f"<div>"
                f"<div class='bar-wrap'><div class='bar' style='width:{width1}%;'></div></div>"
                f"<div class='bar-wrap' style='margin-top:4px;'><div class='bar2' style='width:{width2}%;'></div></div>"
                f"</div>"
                f"<div class='muted'>{v1}/{v2}{peak_tag}</div>"
            )
        scroll_style = ""
        visible_rows = len(rows_data)
        if isinstance(max_visible_rows, int) and max_visible_rows > 0:
            row_height_px = 46
            max_height = max(150, max_visible_rows * row_height_px)
            scroll_style = f" style='max-height:{max_height}px;'"
            visible_rows = min(len(rows_data), max_visible_rows)
        extra_note_h = 48 if conclusion else 0
        self._set_preferred_height(92 + max(1, visible_rows) * 46 + extra_note_h)
        note_html = f"<div class='note'>{escape(conclusion or '')}</div>" if conclusion else ""
        html = self._shell_html(
            title,
            f"{legend_html}<div class='rows-scroll'{scroll_style}><div class='grid'>{''.join(rows)}</div></div>{note_html}",
        )
        self._set_html(html)

    def set_heatmap(self, title: str, hour_counts: Iterable[dict]) -> None:
        values = [{"hour": str(item.get("hour") or "00"), "count": int(item.get("count") or 0)} for item in hour_counts]
        if not values:
            self.set_placeholder(title, "暂无数据")
            return
        rows = max(1, math.ceil(len(values) / 12))
        self._set_preferred_height(96 + rows * 30)
        max_count = max(item["count"] for item in values) or 1
        day_count = sum(item["count"] for item in values if 6 <= int(item["hour"]) < 18)
        night_count = sum(item["count"] for item in values if 18 <= int(item["hour"]) <= 23)
        late_count = sum(item["count"] for item in values if 0 <= int(item["hour"]) < 6)
        total = max(1, day_count + night_count + late_count)
        phase_pairs = [("白天型", day_count), ("夜间型", night_count), ("深夜型", late_count)]
        lead_name, lead_value = max(phase_pairs, key=lambda item: item[1])
        lead_phase = "混合型" if (lead_value / total) < 0.45 else lead_name
        chips_html = (
            "<div style='margin-bottom:6px;'>"
            f"<span class='chip chip-day'>白天 {day_count / total * 100:.1f}%</span>"
            f"<span class='chip chip-night'>夜间 {night_count / total * 100:.1f}%</span>"
            f"<span class='chip chip-late'>深夜 {late_count / total * 100:.1f}%</span>"
            "</div>"
        )
        legend_html = (
            "<div class='legend'>"
            "<span class='legend-item'><span class='dot' style='background:#69b7ff;'></span>白天时段</span>"
            "<span class='legend-item'><span class='dot' style='background:#ff8a94;'></span>夜间时段</span>"
            "<span class='legend-item'><span class='dot' style='background:#ac7eff;'></span>深夜时段</span>"
            "</div>"
        )
        cells: List[str] = []
        for item in values:
            hour_int = int(item["hour"])
            if 6 <= hour_int < 18:
                rgb = (105, 183, 255)
            elif 18 <= hour_int <= 23:
                rgb = (255, 138, 148)
            elif 0 <= hour_int < 6:
                rgb = (172, 126, 255)
            else:
                rgb = (105, 183, 255)
            ratio = item["count"] / max_count if max_count else 0.0
            opacity = 0.15 + ratio * 0.75
            cells.append(
                f"<div class='cell' style='background: rgba({rgb[0]},{rgb[1]},{rgb[2]},{opacity:.3f});'>"
                f"<div>{escape(item['hour'])}</div><div>{item['count']}</div></div>"
            )
        lead_html = f"<div class='note' style='margin-top:5px;'>类型判定：{escape(lead_phase)}（按三段总热度判定）</div>"
        html = self._shell_html(title, f"{legend_html}{chips_html}<div class='heat'>{''.join(cells)}</div>{lead_html}")
        self._set_html(html)

    def set_relationship_rhythm_timeline(self, title: str, trend_rows: Iterable[dict], timeline: dict, note: str = "") -> None:
        rows = [item for item in trend_rows if item]
        if not rows:
            self.set_placeholder(title, "暂无节律数据")
            return
        latest_rows = rows[-10:]
        max_msg = max([int(item.get("msg_count") or 0) for item in latest_rows] or [1])
        max_song = max([int(item.get("song_count") or 0) for item in latest_rows] or [1])
        legend_inner = (
            "<div class='legend rhythm-legend'>"
            "<span class='legend-item'><span class='dot dot-primary'></span>消息</span>"
            "<span class='legend-item'><span class='dot dot-secondary'></span>歌曲</span>"
            "</div>"
        )
        top_html = (
            "<div class='rhythm-top'>"
            f"{legend_inner}"
            "<div class='rhythm-heads'>"
            "<div class='rhythm-head msg'>消息量</div>"
            "<div class='rhythm-head song'>歌曲量</div>"
            "</div>"
            "</div>"
        )
        phase_map = {str(item.get("month") or ""): str(item.get("phase") or "稳定期") for item in (timeline.get("phases") or [])}
        row_html: List[str] = []
        for idx, item in enumerate(latest_rows):
            month = str(item.get("month") or "-")
            msg_count = int(item.get("msg_count") or 0)
            song_count = int(item.get("song_count") or 0)
            phase = phase_map.get(month, "稳定期")
            if phase == "爆发期":
                phase_color = "#ffc44a"
            elif phase == "沉默期":
                phase_color = "#6a7a92"
            elif phase == "回暖期":
                phase_color = "#4ee3c1"
            elif phase == "回落期":
                phase_color = "#ff8a94"
            else:
                phase_color = "#69b7ff"
            msg_width = int(max(4, min(100, (msg_count / max_msg) * 100)))
            song_width = int(max(4, min(100, (song_count / max_song) * 100)))
            row_class = "odd" if (idx % 2 == 0) else "even"
            row_html.append(
                f"<tr class='{row_class}'>"
                f"<td class='rhythm-month'>{escape(month)}</td>"
                "<td>"
                f"<div class='bar-wrap'><div class='bar' style='width:{msg_width}%;'></div></div>"
                f"<div class='bar-wrap' style='margin-top:4px;'><div class='bar2' style='width:{song_width}%;'></div></div>"
                f"<div class='muted' style='margin-top:3px;'><span class='chip' style='background:{phase_color}22;border-color:{phase_color};color:#eef4fb;'>{escape(phase)}</span></div>"
                "</td>"
                f"<td class='rhythm-value msg'>{msg_count}</td>"
                f"<td class='rhythm-value song'>{song_count}</td>"
                "</tr>"
            )
        events_html: List[str] = []
        events = list(timeline.get("events") or [])[:6]
        for idx, event in enumerate(events):
            month_text = str(event.get("month") or "-")
            title_text = str(event.get("title") or "关键节点")
            line_html = "<span class='event-line'></span>" if idx < len(events) - 1 else ""
            events_html.append(
                "<div class='event-item'>"
                "<div class='event-rail'>"
                "<span class='event-dot'></span>"
                f"{line_html}"
                "</div>"
                "<div>"
                f"<div class='event-title'><span class='event-time'>{escape(month_text)}</span>{escape(title_text)}</div>"
                f"<div class='event-detail'>{escape(str(event.get('detail') or ''))}</div>"
                "</div>"
                "</div>"
            )
        note_text = note or str(timeline.get("summary") or "")
        note_html = f"<div class='note'>{escape(note_text)}</div>" if note_text else ""
        self._set_preferred_height(170 + len(latest_rows) * 42 + min(len(events_html), 5) * 46 + (44 if note_html else 0))
        self._set_html(
            self._shell_html(
                title,
                f"{top_html}"
                "<table class='rhythm-table'>"
                "<colgroup>"
                "<col class='rhythm-col-month'/>"
                "<col class='rhythm-col-main'/>"
                "<col class='rhythm-col-msg'/>"
                "<col class='rhythm-col-song'/>"
                "</colgroup>"
                f"<tbody>{''.join(row_html)}</tbody>"
                "</table>"
                f"<div class='event-list'>{''.join(events_html)}</div>{note_html}",
            )
        )

    def set_music_portrait(self, title: str, genres: Iterable[dict], moods: Iterable[dict], artists: Iterable[dict], note: str = "") -> None:
        genre_rows = [dict(item) for item in genres if item]
        mood_rows = [dict(item) for item in moods if item]
        artist_rows = [dict(item) for item in artists if item]
        if not genre_rows and not mood_rows and not artist_rows:
            self.set_placeholder(title, "暂无音乐画像数据")
            return

        total_genre = max(1e-6, sum(float(item.get("weighted_score") or item.get("count") or 0.0) for item in genre_rows))
        sorted_genres = sorted(genre_rows, key=lambda item: int(item.get("count") or 0), reverse=True)
        visible = sorted_genres[:]
        if len(visible) > 4:
            visible = visible[:3]
            other_count = sum(int(item.get("count") or 0) for item in sorted_genres[3:])
            other_weight = sum(float(item.get("weighted_score") or item.get("count") or 0.0) for item in sorted_genres[3:])
            if other_count > 0:
                visible.append({"name": "其他", "count": other_count, "weighted_score": other_weight, "genre_confidence": 0.35})
        # 风格环图使用更柔和的雾面色系，避免高饱和刺眼感
        genre_palette = {
            "流行": "#7EAED6",
            "Hip-Hop/Rap": "#D88CA2",
            "R&B/Soul": "#72C7B7",
            "其他": "#9A8FC8",
            "其他/待确认": "#9A8FC8",
        }
        fallback_palette = ["#7EAED6", "#D88CA2", "#72C7B7", "#9A8FC8", "#8FA6C0"]
        parts: List[str] = []
        start = 0.0
        legend_items: List[str] = []
        for idx, item in enumerate(visible):
            weighted = float(item.get("weighted_score") or item.get("count") or 0.0)
            pct = (weighted / total_genre) * 100
            end = start + pct
            genre_name = str(item.get("name") or "").strip()
            color = genre_palette.get(genre_name, fallback_palette[idx % len(fallback_palette)])
            parts.append(f"{color} {start:.2f}% {end:.2f}%")
            conf = float(item.get("genre_confidence") or 0.0)
            conf_mark = "（低置信）" if conf and conf < 0.45 else ""
            legend_items.append(
                "<div class='tiny-item'>"
                f"<span style='color:{color};font-weight:600;'>"
                f"<span class='legend-swatch' style='background:{color};'></span>{escape(str(item.get('name') or '-'))}{conf_mark}"
                "</span>"
                f"<span>{pct:.1f}%</span>"
                "</div>"
            )
            start = end
        donut_style = ", ".join(parts) if parts else "#7EAED6 0% 100%"

        total_mood = max(1, sum(int(item.get("count") or 0) for item in mood_rows))
        def _mood_colors(mood_name: str) -> tuple[str, str]:
            key = mood_name.strip()
            mapping = {
                "沉思": ("rgba(82, 140, 187, 0.26)", "rgba(111, 184, 240, 0.44)"),
                "浪漫": ("rgba(158, 96, 171, 0.26)", "rgba(214, 142, 193, 0.46)"),
                "压抑": ("rgba(88, 93, 124, 0.26)", "rgba(124, 132, 173, 0.44)"),
                "治愈": ("rgba(80, 154, 133, 0.26)", "rgba(114, 204, 175, 0.46)"),
                "热烈": ("rgba(171, 114, 87, 0.26)", "rgba(230, 154, 116, 0.46)"),
                "孤独": ("rgba(91, 110, 136, 0.26)", "rgba(132, 157, 194, 0.44)"),
                "平静": ("rgba(75, 130, 162, 0.26)", "rgba(109, 170, 209, 0.44)"),
                "忧郁": ("rgba(95, 95, 156, 0.26)", "rgba(149, 146, 214, 0.46)"),
            }
            return mapping.get(key, ("rgba(102, 124, 160, 0.24)", "rgba(141, 165, 204, 0.42)"))

        mood_cards = sorted(mood_rows, key=lambda item: int(item.get("count") or 0), reverse=True)[:4]
        if mood_cards:
            mood_parts: List[str] = []
            for item in mood_cards:
                mood_name = str(item.get("name") or "-")
                mood_bg, mood_border = _mood_colors(mood_name)
                mood_parts.append(
                    "<div class='mood-card' style='"
                    f"background: linear-gradient(135deg, {mood_bg}, rgba(14,22,34,0.62));"
                    f"border-color: {mood_border};"
                    "'>"
                    f"<div class='mood-name'>{escape(mood_name)}</div>"
                    f"<div class='mood-meta'>{int(item.get('count') or 0)} 次 · {int(item.get('count') or 0) / total_mood * 100:.1f}%</div>"
                    "</div>"
                )
            mood_html = "<div class='mood-grid'>" + "".join(mood_parts) + "</div>"
        else:
            mood_html = "<div class='muted'>暂无情绪数据</div>"

        podium = sorted(artist_rows, key=lambda item: int(item.get("count") or 0), reverse=True)[:3]
        first = podium[0] if len(podium) > 0 else {"name": "-", "count": 0}
        second = podium[1] if len(podium) > 1 else {"name": "-", "count": 0}
        third = podium[2] if len(podium) > 2 else {"name": "-", "count": 0}
        podium_html_parts = [
            (
                "<div class='podium-step silver' style='height:86px;'>"
                "<div class='podium-rank'>TOP2</div>"
                f"<div>{escape(str(second.get('name') or '-'))}</div>"
                f"<div class='muted' style='margin-top:4px;'>{int(second.get('count') or 0)}</div>"
                "</div>"
            ),
            (
                "<div class='podium-step gold' style='height:112px;'>"
                "<div class='podium-rank'>TOP1</div>"
                f"<div>{escape(str(first.get('name') or '-'))}</div>"
                f"<div class='muted' style='margin-top:4px;'>{int(first.get('count') or 0)}</div>"
                "</div>"
            ),
            (
                "<div class='podium-step bronze' style='height:66px;'>"
                "<div class='podium-rank'>TOP3</div>"
                f"<div>{escape(str(third.get('name') or '-'))}</div>"
                f"<div class='muted' style='margin-top:4px;'>{int(third.get('count') or 0)}</div>"
                "</div>"
            ),
        ]
        portrait_html = (
            "<div class='portrait-layout'>"
            "<div class='portrait-panel'>"
            "<div class='panel-title'>风格分布</div>"
            f"<div class='donut' style='background: conic-gradient({donut_style});'></div>"
            f"<div class='tiny-list'>{''.join(legend_items) if legend_items else '<div class=muted>暂无风格数据</div>'}</div>"
            "</div>"
            "<div class='portrait-panel'>"
            "<div class='panel-title'>Top 情绪</div>"
            f"<div class='tiny-list'>{mood_html}</div>"
            "</div>"
            "<div class='portrait-panel'>"
            "<div class='panel-title'>Top3 歌手</div>"
            f"<div class='podium'>{''.join(podium_html_parts)}</div>"
            "</div>"
            "</div>"
        )
        note_html = f"<div class='note'>{escape(note)}</div>" if note else ""
        self._set_preferred_height(244 + (42 if note else 0))
        self._set_html(self._shell_html(title, portrait_html + note_html))

    def set_common_world_compare(self, title: str, payload: dict, note: str = "") -> None:
        compare = dict(payload.get("compare") or {})
        me = dict(compare.get("me") or {})
        friend = dict(compare.get("friend") or {})
        overlap = dict(compare.get("overlap") or {})
        if not me and not friend and not overlap:
            self.set_placeholder(title, "暂无共同世界数据")
            return

        def _render_col(label: str, block: dict) -> str:
            genres = "、".join(str(item) for item in list(block.get("genres") or [])[:4]) or "-"
            artists = "、".join(str(item) for item in list(block.get("artists") or [])[:4]) or "-"
            moods = "、".join(str(item) for item in list(block.get("moods") or [])[:4]) or "-"
            role_class = "me" if label == "我" else "friend"
            return (
                f"<div class='compare-col {role_class}'>"
                f"<div class='panel-title'>{escape(label)}</div>"
                f"<div class='tiny-item'><span>风格</span><span>{escape(genres)}</span></div>"
                f"<div class='tiny-item'><span>歌手</span><span>{escape(artists)}</span></div>"
                f"<div class='tiny-item'><span>情绪</span><span>{escape(moods)}</span></div>"
                "</div>"
            )

        overlap_genres = "、".join(str(item) for item in list(overlap.get("genres") or [])[:4]) or "-"
        overlap_artists = "、".join(str(item) for item in list(overlap.get("artists") or [])[:4]) or "-"
        overlap_moods = "、".join(str(item) for item in list(overlap.get("moods") or [])[:4]) or "-"
        overlap_html = (
            "<div class='overlap-box'>"
            "<div class='panel-title'>交集高亮</div>"
            f"<div class='tiny-item'><span>共同风格</span><span>{escape(overlap_genres)}</span></div>"
            f"<div class='tiny-item'><span>共同歌手</span><span>{escape(overlap_artists)}</span></div>"
            f"<div class='tiny-item'><span>共同情绪</span><span>{escape(overlap_moods)}</span></div>"
            "</div>"
        )
        note_html = f"<div class='note'>{escape(note)}</div>" if note else ""
        self._set_preferred_height(196 + (42 if note else 0))
        self._set_html(
            self._shell_html(
                title,
                f"<div class='compare-grid'>{_render_col('我', me)}{_render_col('好友', friend)}</div>{overlap_html}{note_html}",
            )
        )

    def set_social_network_graph(
        self,
        title: str,
        center_name: str,
        nodes: Iterable[dict],
        unit: str = "首",
        empty_text: str = "暂无数据",
        note: str = "",
        center_avatar_url: str = "",
        layout_key: str = "",
    ) -> None:
        node_rows = [dict(item) for item in nodes if int(item.get("value") or 0) > 0]
        node_rows.sort(key=lambda item: int(item.get("value") or 0), reverse=True)
        node_rows = node_rows[:5]
        if not node_rows:
            note_html = f"<div class='note'>{escape(note)}</div>" if note else ""
            self._set_preferred_height(258 + (42 if note else 0))
            self._set_html(
                self._shell_html(
                    title,
                    f"<div class='network-wrap'><div class='empty-block'>◌ {escape(empty_text)}</div></div>{note_html}",
                )
            )
            return

        canvas_w = 560.0
        canvas_h = 264.0
        center_x = canvas_w * 0.50
        center_y = canvas_h * 0.50
        center_radius = 26.0
        orbit_rx = canvas_w * 0.36
        orbit_ry = canvas_h * 0.36
        max_vertical_jitter = canvas_h * 0.38
        min_gap = 15.0
        min_node_size = 34.0
        max_node_size = 48.0
        values = [max(1, int(item.get("value") or 0)) for item in node_rows]
        max_value = max(values) if values else 1
        min_value = min(values) if values else 1

        def _clamp(value: float, low: float, high: float) -> float:
            return max(low, min(high, value))

        def _to_pct_x(value: float) -> float:
            return value / canvas_w * 100.0

        def _to_pct_y(value: float) -> float:
            return value / canvas_h * 100.0

        def _bbox_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float], pad: float = 0.0) -> bool:
            ax1, ay1, ax2, ay2 = a
            bx1, by1, bx2, by2 = b
            return not (ax2 + pad < bx1 or bx2 + pad < ax1 or ay2 + pad < by1 or by2 + pad < ay1)

        def _rect_intersects_circle(rect: tuple[float, float, float, float], cx: float, cy: float, cr: float, pad: float = 0.0) -> bool:
            x1, y1, x2, y2 = rect
            nx = _clamp(cx, x1, x2)
            ny = _clamp(cy, y1, y2)
            dx = cx - nx
            dy = cy - ny
            return dx * dx + dy * dy <= (cr + pad) * (cr + pad)

        def _node_size(value: int) -> float:
            if max_value <= min_value:
                ratio = 0.5
            else:
                ratio = (math.sqrt(value) - math.sqrt(min_value)) / max(1e-6, math.sqrt(max_value) - math.sqrt(min_value))
            ratio = _clamp(ratio, 0.0, 1.0)
            return min_node_size + (max_node_size - min_node_size) * ratio

        def _seed_pair(text: str) -> tuple[float, float]:
            token = hashlib.md5(text.encode("utf-8")).hexdigest()
            a = (int(token[:8], 16) % 10000) / 10000.0
            b = (int(token[8:16], 16) % 10000) / 10000.0
            return a, b

        placed_nodes: List[dict] = []

        def _has_overlap(x: float, y: float, radius: float, ignore_idx: int = -1) -> bool:
            if (x - center_x) ** 2 + (y - center_y) ** 2 < (radius + center_radius + min_gap) ** 2:
                return True
            for idx, node in enumerate(placed_nodes):
                if idx == ignore_idx:
                    continue
                nx = float(node["x"])
                ny = float(node["y"])
                nr = float(node["radius"])
                if (x - nx) ** 2 + (y - ny) ** 2 < (radius + nr + min_gap) ** 2:
                    return True
            return False

        layout_signature = "|".join(
            f"{str(row.get('uid') or row.get('name') or '')}:{int(row.get('value') or 0)}" for row in node_rows
        )
        layout_a, layout_b = _seed_pair(f"{layout_key or 'default'}|{layout_signature}")
        natural_templates: List[List[float]] = [
            [-92.0, -18.0, 42.0, 150.0, -152.0],
            [-76.0, 22.0, -34.0, 176.0, 126.0],
            [-112.0, -8.0, 58.0, -166.0, 142.0],
            [-64.0, 164.0, 8.0, -134.0, 84.0],
        ]
        template = natural_templates[int(layout_a * len(natural_templates)) % len(natural_templates)]
        global_rotate = (layout_b - 0.5) * 18.0
        angle_offsets = [0.0, 7.0, -7.0, 12.0, -12.0, 18.0, -18.0]
        radius_offsets = [0.0, 8.0, -8.0, 14.0, -14.0, 20.0, -20.0]
        y_offsets = [0.0, 7.0, -7.0, 12.0, -12.0]

        for idx, row in enumerate(node_rows):
            name = str(row.get("name") or "好友")
            uid = str(row.get("uid") or name)
            value = max(1, int(row.get("value") or 0))
            avatar_url = str(row.get("avatar_url") or "").strip()
            size = _node_size(value)
            radius = size / 2.0
            seed_a, seed_b = _seed_pair(f"{layout_key or 'default'}|{uid}")
            core_angle = template[idx % len(template)] + global_rotate + (seed_a - 0.5) * 18.0
            radial_jitter = (seed_b - 0.5) * 24.0
            y_jitter = ((seed_a * 1.9) % 1.0 - 0.5) * 18.0

            picked_x = None
            picked_y = None
            for a_off in angle_offsets:
                for r_off in radius_offsets:
                    for y_off in y_offsets:
                        angle = math.radians(core_angle + a_off)
                        xr = orbit_rx + radial_jitter + r_off
                        yr = orbit_ry * (0.92 + (seed_a - 0.5) * 0.18)
                        x = center_x + xr * math.cos(angle)
                        y = center_y + yr * math.sin(angle) + y_jitter + y_off
                        y = _clamp(y, center_y - max_vertical_jitter, center_y + max_vertical_jitter)
                        if x - radius < 8 or x + radius > canvas_w - 8:
                            continue
                        if y - radius < 8 or y + radius > canvas_h - 8:
                            continue
                        if _has_overlap(x, y, radius):
                            continue
                        picked_x = x
                        picked_y = y
                        break
                    if picked_x is not None:
                        break
                if picked_x is not None:
                    break

            if picked_x is None:
                angle = math.radians(core_angle)
                picked_x = _clamp(center_x + (orbit_rx + radial_jitter) * math.cos(angle), 8 + radius, canvas_w - 8 - radius)
                picked_y = _clamp(center_y + orbit_ry * math.sin(angle) + y_jitter, 8 + radius, canvas_h - 8 - radius)

            placed_nodes.append(
                {
                    "x": picked_x,
                    "y": picked_y,
                    "radius": radius,
                    "size": size,
                    "name": name,
                    "value": value,
                    "avatar_url": avatar_url,
                    "seed": seed_a,
                }
            )

        # 最后兜底一次：如果仍有碰撞，轻微推开
        for i in range(len(placed_nodes)):
            for j in range(i + 1, len(placed_nodes)):
                ni = placed_nodes[i]
                nj = placed_nodes[j]
                dx = float(nj["x"]) - float(ni["x"])
                dy = float(nj["y"]) - float(ni["y"])
                dist = max(1e-6, math.sqrt(dx * dx + dy * dy))
                min_dist = float(ni["radius"]) + float(nj["radius"]) + min_gap
                if dist >= min_dist:
                    continue
                ux = dx / dist
                uy = dy / dist
                push = (min_dist - dist) / 2.0 + 0.8
                ni["x"] = _clamp(float(ni["x"]) - ux * push, 8 + float(ni["radius"]), canvas_w - 8 - float(ni["radius"]))
                ni["y"] = _clamp(float(ni["y"]) - uy * push, 8 + float(ni["radius"]), canvas_h - 8 - float(ni["radius"]))
                nj["x"] = _clamp(float(nj["x"]) + ux * push, 8 + float(nj["radius"]), canvas_w - 8 - float(nj["radius"]))
                nj["y"] = _clamp(float(nj["y"]) + uy * push, 8 + float(nj["radius"]), canvas_h - 8 - float(nj["radius"]))

        line_svg: List[str] = []
        label_html: List[str] = []
        label_rects: List[tuple[float, float, float, float]] = []
        for node in placed_nodes:
            x = float(node["x"])
            y = float(node["y"])
            # 连线按头像边缘到边缘，确保视觉上真正连接头像
            dx = x - center_x
            dy = y - center_y
            dist = max(1e-6, math.sqrt(dx * dx + dy * dy))
            ux = dx / dist
            uy = dy / dist
            sx = center_x + ux * center_radius
            sy = center_y + uy * center_radius
            ex = x - ux * float(node["radius"])
            ey = y - uy * float(node["radius"])
            line_svg.append(
                f"<line x1='{sx:.2f}' y1='{sy:.2f}' x2='{ex:.2f}' y2='{ey:.2f}' />"
            )
            # 数字标签独立于头像，仅锚定在线段中后段
            value_text = f"{int(node['value'])}{escape(unit)}"
            label_w = max(34.0, len(value_text) * 7.0 + 12.0)
            label_h = 18.0
            nx = -uy
            ny = ux
            sign = 1.0 if float(node.get("seed") or 0.5) >= 0.5 else -1.0
            t_candidates = [0.63, 0.67, 0.59, 0.70, 0.56]
            n_offsets = [0.0, 1.6 * sign, -1.6 * sign, 3.0 * sign, -3.0 * sign]
            solved = None
            for t in t_candidates:
                bx = sx + (ex - sx) * t
                by = sy + (ey - sy) * t
                for n_off in n_offsets:
                    tx = bx + nx * n_off
                    ty = by + ny * n_off
                    rect = (tx - label_w / 2, ty - label_h / 2, tx + label_w / 2, ty + label_h / 2)
                    if rect[0] < 4 or rect[2] > canvas_w - 4 or rect[1] < 4 or rect[3] > canvas_h - 4:
                        continue
                    if any(_bbox_overlap(rect, old, pad=2.0) for old in label_rects):
                        continue
                    if _rect_intersects_circle(rect, center_x, center_y, center_radius, pad=1.5):
                        continue
                    blocked = False
                    for other in placed_nodes:
                        if _rect_intersects_circle(rect, float(other["x"]), float(other["y"]), float(other["radius"]), pad=1.5):
                            blocked = True
                            break
                    if blocked:
                        continue
                    solved = (tx, ty, rect)
                    break
                if solved is not None:
                    break
            if solved is None:
                # 兜底仍放在线上
                tx = center_x + dx * 0.62
                ty = center_y + dy * 0.62
                solved = (tx, ty, (tx - label_w / 2, ty - label_h / 2, tx + label_w / 2, ty + label_h / 2))
            label_rects.append(tuple(solved[2]))
            label_html.append(
                f"<div class='network-edge-value' style='left:{_to_pct_x(float(solved[0])):.2f}%;top:{_to_pct_y(float(solved[1])):.2f}%;'>{value_text}</div>"
            )

        center_avatar = str(center_avatar_url or "").strip()
        center_fallback = escape((center_name or "我")[:1] or "我")
        center_content = f"<img class='network-avatar' src='{escape(center_avatar)}' />" if center_avatar else center_fallback
        nodes_html: List[str] = [
            f"<div class='network-node center' style='left:{_to_pct_x(center_x):.2f}%;top:{_to_pct_y(center_y):.2f}%;'>{center_content}</div>"
        ]
        for node in placed_nodes:
            x = float(node["x"])
            y = float(node["y"])
            size = float(node["size"])
            avatar_url = str(node.get("avatar_url") or "")
            fallback_name = str(node.get("name") or "好友")
            content = f"<img class='network-avatar' src='{escape(avatar_url)}' />" if avatar_url else escape(fallback_name[:1])
            nodes_html.append(
                f"<div class='network-node friend' style='left:{_to_pct_x(x):.2f}%;top:{_to_pct_y(y):.2f}%;width:{size:.1f}px;height:{size:.1f}px;'>{content}</div>"
            )

        note_html = f"<div class='note'>{escape(note)}</div>" if note else ""
        self._set_preferred_height(306 + (42 if note else 0))
        self._set_html(
            self._shell_html(
                title,
                (
                    "<div class='network-wrap'>"
                    "<div class='network-canvas'>"
                    f"<svg class='network-lines' viewBox='0 0 {int(canvas_w)} {int(canvas_h)}' preserveAspectRatio='none'>{''.join(line_svg)}</svg>"
                    f"{''.join(label_html)}"
                    f"{''.join(nodes_html)}"
                    "</div>"
                    "</div>"
                    f"{note_html}"
                ),
            )
        )

    def set_timeline(self, title: str, timeline: dict, note: str = "") -> None:
        self.set_relationship_rhythm_timeline(title, timeline.get("phases") or [], timeline, note)

    def set_radar_bars(self, title: str, items: Iterable[dict], note: str = "") -> None:
        rows = [{"name": str(item.get("name") or "-"), "value": int(item.get("value") or 0)} for item in items]
        rows = [item for item in rows if item["name"]]
        if not rows:
            self.set_placeholder(title, "暂无风格画像数据")
            return
        max_value = max(item["value"] for item in rows) or 1
        html_rows: List[str] = []
        for row in rows:
            width = int(row["value"] / max_value * 100)
            html_rows.append(
                f"<div class='muted'>{escape(row['name'])}</div>"
                f"<div class='bar-wrap'><div class='bar' style='width:{width}%;'></div></div>"
                f"<div class='muted'>{row['value']}%</div>"
            )
        note_html = f"<div class='note'>{escape(note)}</div>" if note else ""
        self._set_preferred_height(84 + len(rows) * 36 + (44 if note else 0))
        self._set_html(self._shell_html(title, f"<div class='grid'>{''.join(html_rows)}</div>{note_html}"))

    def set_influence_bars(self, title: str, items: Iterable[dict], note: str = "") -> None:
        self.set_radar_bars(title, items, note)

    def set_overlap_bars(self, title: str, items: Iterable[dict], note: str = "") -> None:
        self.set_radar_bars(title, items, note)

    def set_similarity_map(self, title: str, pairs: Iterable[dict], focus_name: str = "") -> None:
        rows = list(pairs)
        if not rows:
            self.set_placeholder(title, "暂无相似度数据")
            return
        display = rows[:8]
        html_rows: List[str] = []
        for row in display:
            left = str(row.get("name_a") or "-")
            right = str(row.get("name_b") or "-")
            score = float(row.get("score") or 0.0)
            width = int(max(0.0, min(1.0, score)) * 100)
            summary = str(row.get("summary") or "风格接近")
            html_rows.append(
                "<div class='muted'>"
                f"{escape(left)} ↔ {escape(right)}"
                "</div>"
                f"<div class='bar-wrap'><div class='bar' style='width:{width}%;'></div></div>"
                f"<div class='muted'>{score * 100:.1f}%</div>"
                "<div></div>"
                f"<div class='muted'>{escape(summary)}</div>"
                "<div></div>"
            )
        focus_text = f"焦点好友：{focus_name}" if focus_name else "相似关系网络（MVP）"
        self._set_preferred_height(130 + len(display) * 52)
        self._set_html(
            self._shell_html(
                title,
                f"<div class='note'>{escape(focus_text)}</div><div class='grid' style='grid-template-columns: 200px 1fr 68px;'>{''.join(html_rows)}</div>",
            )
        )
