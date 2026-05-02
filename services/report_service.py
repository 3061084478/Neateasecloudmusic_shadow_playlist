from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from PySide6 import QtCore, QtGui

from services.config_store import ConfigStore


class ReportService:
    def __init__(self, config_store: ConfigStore):
        self.config_store = config_store
        self.report_dir = Path(self.config_store.workspace_root) / "data" / "reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = Path(self.config_store.cache_dir) / "music_report_history.json"

    def _load_history(self) -> List[Dict[str, Any]]:
        if not self.index_path.exists():
            return []
        try:
            with self.index_path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
            records = payload.get("records") or []
            if isinstance(records, list):
                return [item for item in records if isinstance(item, dict)]
        except Exception:
            return []
        return []

    def _save_history(self, records: List[Dict[str, Any]]) -> None:
        payload = {"updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "records": records[:100]}
        with self.index_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)

    def _record(self, item: Dict[str, Any]) -> Dict[str, Any]:
        records = self._load_history()
        records.insert(0, item)
        self._save_history(records)
        return item

    @staticmethod
    def _normalized_report_type(report_type: str) -> str:
        normalized = str(report_type or "").strip().lower()
        if normalized in {"friend", "self", "annual"}:
            return normalized
        return "all"

    @staticmethod
    def _type_label(report_type: str) -> str:
        mapping = {
            "friend": "好友报告",
            "self": "个人报告",
            "annual": "年度回顾",
        }
        return mapping.get(report_type, "报告")

    @staticmethod
    def _draw_text_block(
        painter: QtGui.QPainter,
        rect: QtCore.QRect,
        text: str,
        color: QtGui.QColor,
        point_size: int,
        bold: bool = False,
    ) -> None:
        font = QtGui.QFont("Microsoft YaHei UI", point_size)
        font.setBold(bold)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(rect, int(QtCore.Qt.TextWordWrap | QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop), text)

    def _render_image(
        self,
        title: str,
        subtitle: str,
        metrics: List[str],
        insight_text: str,
        evidence_tracks: List[Dict[str, Any]],
        memory_points: List[Dict[str, Any]] | None = None,
        accent_color: str | None = None,
    ) -> QtGui.QImage:
        points = list(memory_points or [])
        accent = QtGui.QColor(accent_color or "#7fd3ff")
        if not accent.isValid():
            accent = QtGui.QColor("#7fd3ff")
        accent_border = QtGui.QColor(accent)
        accent_border.setAlpha(120)
        accent_fill = QtGui.QColor(accent)
        accent_fill.setAlpha(36)
        image = QtGui.QImage(1200, 1680, QtGui.QImage.Format_ARGB32)
        image.fill(QtGui.QColor("#0f1722"))
        painter = QtGui.QPainter(image)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        painter.fillRect(QtCore.QRect(44, 44, 1112, 1592), QtGui.QColor("#141f2f"))
        painter.setPen(QtGui.QPen(accent_border, 1))
        painter.drawRoundedRect(QtCore.QRect(44, 44, 1112, 1592), 24, 24)
        painter.fillRect(QtCore.QRect(84, 82, 1020, 6), accent_fill)

        self._draw_text_block(painter, QtCore.QRect(84, 84, 1020, 78), title, QtGui.QColor("#f4f7fb"), 26, True)
        self._draw_text_block(painter, QtCore.QRect(84, 154, 1020, 44), subtitle, QtGui.QColor("#b4c0cf"), 14, False)

        top = 226
        for metric in metrics:
            painter.fillRect(QtCore.QRect(84, top, 1020, 48), QtGui.QColor(255, 255, 255, 16))
            self._draw_text_block(painter, QtCore.QRect(104, top + 10, 980, 30), metric, QtGui.QColor("#ebf1f9"), 13, False)
            top += 58

        top += 10
        if points:
            visible_points = points[:4]
            block_h = 50 + len(visible_points) * 46
            painter.fillRect(QtCore.QRect(84, top, 1020, block_h), QtGui.QColor(255, 255, 255, 12))
            self._draw_text_block(painter, QtCore.QRect(104, top + 14, 980, 30), "关系时间线节点", QtGui.QColor("#f4f7fb"), 17, True)
            row_top = top + 48
            for item in visible_points:
                tag = str(item.get("tag") or "记忆")
                title_text = str(item.get("title") or "关系记忆")
                detail = str(item.get("detail") or "")
                line = f"[{tag}] {title_text}：{detail}"
                self._draw_text_block(painter, QtCore.QRect(104, row_top, 980, 40), line, QtGui.QColor("#dce7f3"), 12, False)
                row_top += 44
            top += block_h + 14

        ai_height = 320
        painter.fillRect(QtCore.QRect(84, top, 1020, ai_height), QtGui.QColor(255, 255, 255, 12))
        self._draw_text_block(painter, QtCore.QRect(104, top + 16, 980, 32), "AI 分析", QtGui.QColor("#f4f7fb"), 18, True)
        self._draw_text_block(
            painter,
            QtCore.QRect(104, top + 58, 980, ai_height - 76),
            insight_text or "暂无分析文段。",
            QtGui.QColor("#e7edf6"),
            13,
            False,
        )
        top += ai_height + 14

        evidence_height = max(220, 1592 - (top - 44) - 20)
        painter.fillRect(QtCore.QRect(84, top, 1020, evidence_height), QtGui.QColor(255, 255, 255, 10))
        self._draw_text_block(painter, QtCore.QRect(104, top + 16, 980, 34), "证据歌曲", QtGui.QColor("#f4f7fb"), 18, True)
        row_top = top + 64
        if not evidence_tracks:
            self._draw_text_block(painter, QtCore.QRect(104, row_top, 980, 40), "暂无证据歌曲。", QtGui.QColor("#b9c7d9"), 12, False)
        else:
            for index, track in enumerate(evidence_tracks[:5], start=1):
                line = (
                    f"{index}. {track.get('song_name') or '未知歌曲'} - {track.get('artist_name') or '未知歌手'} | "
                    f"{track.get('msg_time') or '-'} | {track.get('reason') or '样本依据'}"
                )
                self._draw_text_block(painter, QtCore.QRect(104, row_top, 980, 80), line, QtGui.QColor("#dce7f3"), 12, False)
                row_top += 94

        painter.end()
        return image

    def render_friend_report_png(
        self,
        snapshot: Dict[str, Any],
        insight: Dict[str, Any],
    ) -> Dict[str, Any]:
        uid = str(snapshot.get("uid") or "unknown")
        friend_name = str(snapshot.get("friend_name") or f"好友{uid}")
        generated_at = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"friend_{uid}_{generated_at}.png"
        output_path = self.report_dir / filename
        metrics = [
            f"消息总数：{snapshot.get('message_count_total', 0)}",
            f"歌曲分享总数：{snapshot.get('song_share_count_total', 0)}",
            f"活跃天数：{snapshot.get('active_days_total', 0)}",
            f"深夜分享比例：{float(snapshot.get('night_share_ratio', 0.0)) * 100:.1f}%",
            f"发现力指数：{float(snapshot.get('discovery_index', 0.0)):.2f}",
            f"稳定度：{float(snapshot.get('stability_score', 0.0)):.2f}",
        ]
        timeline_events = list((snapshot.get("timeline_visual") or {}).get("events") or [])[:4]
        memory_points = [
            {
                "tag": str(event.get("phase") or "阶段"),
                "title": str(event.get("title") or "关系节点"),
                "detail": str(event.get("detail") or ""),
            }
            for event in timeline_events
        ]
        image = self._render_image(
            title=f"{friend_name} 音乐关系报告",
            subtitle=f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            metrics=metrics,
            insight_text=str(insight.get("text") or ""),
            evidence_tracks=list(insight.get("evidence_tracks") or snapshot.get("evidence_tracks") or []),
            memory_points=memory_points,
            accent_color="#7fd3ff",
        )
        image.save(str(output_path), "PNG")
        record = {
            "type": "friend",
            "uid": uid,
            "title": f"{friend_name} 音乐关系报告",
            "summary": str(snapshot.get("cover_line") or snapshot.get("trend_conclusion") or ""),
            "lead": friend_name,
            "path": str(output_path),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return self._record(record)

    def render_self_report_png(
        self,
        snapshot: Dict[str, Any],
        insight: Dict[str, Any],
    ) -> Dict[str, Any]:
        account_name = str(snapshot.get("account_name") or "我")
        generated_at = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"self_{generated_at}.png"
        output_path = self.report_dir / filename
        metrics = [
            f"覆盖好友数：{snapshot.get('friend_count', 0)}",
            f"活跃好友数：{snapshot.get('active_friend_count', 0)}",
            f"消息总数：{snapshot.get('message_count', 0)}",
            f"歌曲总数：{snapshot.get('song_count', 0)}",
            f"深夜分享比例：{float(snapshot.get('night_share_ratio', 0.0)) * 100:.1f}%",
            f"活跃高峰月份：{snapshot.get('peak_month') or '-'}",
        ]
        image = self._render_image(
            title=f"{account_name} 音乐社交画像",
            subtitle=f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            metrics=metrics,
            insight_text=str(insight.get("text") or ""),
            evidence_tracks=list(insight.get("evidence_tracks") or []),
            memory_points=[],
            accent_color="#7fd3ff",
        )
        image.save(str(output_path), "PNG")
        record = {
            "type": "self",
            "uid": "",
            "title": f"{account_name} 音乐社交画像",
            "summary": str(snapshot.get("trend_conclusion") or ""),
            "lead": str((snapshot.get("top_song_friends") or [{}])[0].get("name") or ""),
            "path": str(output_path),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return self._record(record)

    def render_annual_report_png(
        self,
        annual_snapshot: Dict[str, Any],
        insight: Dict[str, Any],
    ) -> Dict[str, Any]:
        account_name = str(annual_snapshot.get("account_name") or "我")
        year = str(annual_snapshot.get("year") or datetime.now().year)
        generated_at = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"annual_{year}_{generated_at}.png"
        output_path = self.report_dir / filename
        metrics = [
            f"年度消息总数：{int(annual_snapshot.get('message_count') or 0)}",
            f"年度歌曲总数：{int(annual_snapshot.get('song_count') or 0)}",
            f"年度高峰月份：{annual_snapshot.get('peak_month') or '-'}",
            f"聊天最多好友：{annual_snapshot.get('top_chat_friend_name') or '暂无'}（{int(annual_snapshot.get('top_chat_friend_count') or 0)} 条）",
            f"发歌最多好友：{annual_snapshot.get('top_song_friend_name') or '暂无'}（{int(annual_snapshot.get('top_song_friend_count') or 0)} 首）",
            f"代表关系对象：{annual_snapshot.get('representative_relationship') or '暂无'}",
        ]
        annual_points = [
            {"tag": "峰值", "title": "年度高峰", "detail": f"{annual_snapshot.get('peak_month') or '-'} 是这一年的互动峰值月份。"},
            {
                "tag": "主角",
                "title": "关系主角",
                "detail": f"{annual_snapshot.get('representative_relationship') or '暂无'} 是你本年度最具代表性的音乐关系对象。",
            },
            {
                "tag": "记录",
                "title": "年度记录",
                "detail": f"全年累计消息 {int(annual_snapshot.get('message_count') or 0)} 条，歌曲 {int(annual_snapshot.get('song_count') or 0)} 首。",
            },
        ]
        image = self._render_image(
            title=f"{account_name} {year} 年度音乐社交回顾",
            subtitle=f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            metrics=metrics,
            insight_text=str(insight.get("text") or annual_snapshot.get("summary") or ""),
            evidence_tracks=list(insight.get("evidence_tracks") or []),
            memory_points=annual_points,
            accent_color="#7fd3ff",
        )
        image.save(str(output_path), "PNG")
        record = {
            "type": "annual",
            "uid": "",
            "title": f"{account_name} {year} 年度音乐社交回顾",
            "summary": str(annual_snapshot.get("summary") or ""),
            "lead": str(annual_snapshot.get("representative_relationship") or ""),
            "path": str(output_path),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return self._record(record)

    def list_recent_reports(self, limit: int = 20, report_type: str = "all", keyword: str = "") -> List[Dict[str, Any]]:
        records = self._load_history()
        selected_type = self._normalized_report_type(report_type)
        keyword_normalized = str(keyword or "").strip().lower()
        valid_records: List[Dict[str, Any]] = []
        for item in records:
            if not Path(str(item.get("path") or "")).exists():
                continue
            current_type = str(item.get("type") or "").strip().lower()
            if selected_type != "all" and current_type != selected_type:
                continue
            haystack = " ".join(
                [
                    str(item.get("generated_at") or ""),
                    str(item.get("title") or ""),
                    str(item.get("summary") or ""),
                    str(item.get("lead") or ""),
                    str(item.get("uid") or ""),
                    str(item.get("path") or ""),
                ]
            ).lower()
            if keyword_normalized and keyword_normalized not in haystack:
                continue
            row = dict(item)
            row["display_type"] = self._type_label(current_type)
            valid_records.append(row)
        return valid_records[: max(1, int(limit or 1))]

    def prune_missing_reports(self) -> Dict[str, int]:
        records = self._load_history()
        kept_records: List[Dict[str, Any]] = []
        removed_count = 0
        for item in records:
            if Path(str(item.get("path") or "")).exists():
                kept_records.append(item)
            else:
                removed_count += 1
        if removed_count:
            self._save_history(kept_records)
        return {"removed": removed_count, "kept": len(kept_records)}
