from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List

from services.config_store import ConfigStore
from services.storage import ChatArchiveRepository

LANGUAGE_PATTERNS = {
    "中文": re.compile(r"[\u4e00-\u9fff]"),
    "日语": re.compile(r"[\u3040-\u30ff]"),
    "韩语": re.compile(r"[\uac00-\ud7af]"),
    "英语": re.compile(r"[A-Za-z]"),
}

@dataclass(frozen=True)
class WindowRange:
    key: str
    days: int | None


WINDOWS: dict[str, WindowRange] = {
    "all": WindowRange("all", None),
    "30d": WindowRange("30d", 30),
    "7d": WindowRange("7d", 7),
    "year": WindowRange("year", 365),
}


def _safe_parse_time(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


class AnalyticsService:
    def __init__(self, config_store: ConfigStore):
        self.config_store = config_store
        self.repository = ChatArchiveRepository(config_store.archive_db_path)

    @staticmethod
    def _normalize_window(window: str) -> WindowRange:
        return WINDOWS.get(window, WINDOWS["all"])

    def query_friend_messages(self, uid: str, window: str = "all") -> List[Dict[str, Any]]:
        rows = self.repository.query_messages(uid=uid)
        return self._filter_window(rows, window)

    @staticmethod
    def _parse_year_window(window: str) -> int | None:
        text = str(window or "").strip().lower()
        if text.startswith("year:"):
            try:
                return int(text.split(":", 1)[1])
            except ValueError:
                return None
        return None

    @staticmethod
    def _window_identity(window: str) -> str:
        year = AnalyticsService._parse_year_window(window)
        if year is not None:
            return f"year:{year}"
        return AnalyticsService._normalize_window(window).key

    def _filter_window(self, rows: List[Dict[str, Any]], window: str) -> List[Dict[str, Any]]:
        year = self._parse_year_window(window)
        if year is not None:
            filtered_by_year: List[Dict[str, Any]] = []
            for row in rows:
                parsed = _safe_parse_time(row.get("msg_time_str") or "")
                if parsed is not None and parsed.year == year:
                    filtered_by_year.append(row)
            return filtered_by_year
        normalized = self._normalize_window(window)
        if normalized.days is None or not rows:
            return rows
        latest = _safe_parse_time(rows[-1].get("msg_time_str") or "")
        if latest is None:
            latest = datetime.now()
        cutoff = latest - timedelta(days=normalized.days)
        filtered: List[Dict[str, Any]] = []
        for row in rows:
            parsed = _safe_parse_time(row.get("msg_time_str") or "")
            if parsed is None or parsed >= cutoff:
                filtered.append(row)
        return filtered

    def list_available_years(self, uids: List[str]) -> List[int]:
        years: set[int] = set()
        for uid in uids:
            if not str(uid or "").strip():
                continue
            rows = self.repository.query_messages(uid=str(uid))
            for row in rows:
                parsed = _safe_parse_time(str(row.get("msg_time_str") or ""))
                if parsed is not None:
                    years.add(parsed.year)
        return sorted(years)

    @staticmethod
    def _counter_top(counter: Counter[str], limit: int = 5) -> List[Dict[str, Any]]:
        return [{"name": name, "count": int(count)} for name, count in counter.most_common(limit)]

    @staticmethod
    def _is_night_hour(hour: int) -> bool:
        return hour >= 22 or hour < 5

    @staticmethod
    def _infer_language(text: str) -> str:
        for label, pattern in LANGUAGE_PATTERNS.items():
            if pattern.search(text):
                return label
        return "其他"

    @staticmethod
    def _entropy(counter: Counter[str]) -> float:
        total = sum(counter.values())
        if total <= 0:
            return 0.0
        entropy = 0.0
        for value in counter.values():
            p = value / total
            entropy -= p * math.log(p + 1e-12)
        return entropy

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))

    @staticmethod
    def _build_trend_conclusion(trend_series: List[Dict[str, Any]]) -> str:
        if not trend_series:
            return "暂无趋势数据。"
        peak = max(trend_series, key=lambda item: (int(item.get("song_count") or 0), int(item.get("msg_count") or 0)))
        first = trend_series[0]
        last = trend_series[-1]
        song_delta = int(last.get("song_count") or 0) - int(first.get("song_count") or 0)
        if song_delta >= 12:
            phase = "进入升温阶段"
        elif song_delta <= -12:
            phase = "进入降温阶段"
        else:
            phase = "保持稳定节奏"
        return (
            f"互动高峰出现在 {peak.get('month') or '-'}（消息 {int(peak.get('msg_count') or 0)} / 歌曲 {int(peak.get('song_count') or 0)}），"
            f"当前关系 {phase}（较起点 {song_delta:+d} 首歌曲）。"
        )

    @staticmethod
    def _build_activity_conclusion(hour_heatmap: List[Dict[str, Any]]) -> str:
        if not hour_heatmap:
            return "暂无活跃时段数据。"
        values = {int(item.get("hour") or 0): int(item.get("count") or 0) for item in hour_heatmap}
        day_count = sum(values.get(hour, 0) for hour in range(6, 18))
        night_count = sum(values.get(hour, 0) for hour in range(18, 24))
        late_count = sum(values.get(hour, 0) for hour in range(0, 6))
        total = day_count + night_count + late_count
        if total <= 0:
            return "暂无活跃时段数据。"
        buckets = [("白天型", day_count), ("夜间型", night_count), ("深夜型", late_count)]
        peak_label, peak_value = max(buckets, key=lambda item: item[1])
        ratio = peak_value / total
        if ratio < 0.46:
            return "混合型互动明显，三段时段分布较均衡。"
        return f"{peak_label}互动特征明显，核心活跃时段贡献约 {ratio * 100:.1f}%。"

    @staticmethod
    def _build_relation_temperature(snapshot: Dict[str, Any]) -> Dict[str, Any]:
        msg_count = int(snapshot.get("message_count_total") or 0)
        song_count = int(snapshot.get("song_share_count_total") or 0)
        active_days_30d = int(snapshot.get("active_days_30d") or 0)
        msg_component = min(1.0, math.log1p(msg_count) / math.log1p(800))
        song_component = min(1.0, math.log1p(song_count) / math.log1p(220))
        recent_component = min(1.0, active_days_30d / 20)
        score = AnalyticsService._clamp(msg_component * 0.45 + song_component * 0.35 + recent_component * 0.20)
        percent = int(round(score * 100))
        if percent >= 76:
            label = "高温关系"
        elif percent >= 56:
            label = "稳定关系"
        elif percent >= 36:
            label = "持续关系"
        else:
            label = "低频关系"
        return {"score": percent, "label": label}

    @staticmethod
    def _build_relation_cover_line(snapshot: Dict[str, Any]) -> str:
        relation_temp = snapshot.get("relation_temperature") or {}
        label = str(relation_temp.get("label") or "关系未定")
        trend = str(snapshot.get("trend_conclusion") or "互动节奏尚未稳定。")
        return f"{label} · {trend}"

    @staticmethod
    def _build_first_introduced_artist(song_rows: List[Dict[str, Any]]) -> str:
        if not song_rows:
            return "暂无"
        for row in song_rows:
            artists = [part.strip() for part in str(row.get("artist_name") or "").split("/") if part.strip()]
            if artists:
                return artists[0]
        return "暂无"

    @staticmethod
    def _build_silence_and_burst(trend_series: List[Dict[str, Any]]) -> Dict[str, str]:
        if len(trend_series) < 2:
            return {
                "title": "沉默与爆发",
                "detail": "样本不足，暂时无法识别沉默与爆发阶段。",
            }
        max_gap = 0
        burst_point = trend_series[0]
        for idx in range(1, len(trend_series)):
            prev_songs = int(trend_series[idx - 1].get("song_count") or 0)
            curr_songs = int(trend_series[idx].get("song_count") or 0)
            delta = curr_songs - prev_songs
            if delta > max_gap:
                max_gap = delta
                burst_point = trend_series[idx]
        if max_gap <= 0:
            return {
                "title": "沉默与爆发",
                "detail": "最近阶段波动不大，关系节奏更偏持续稳定。",
            }
        return {
            "title": "沉默与爆发",
            "detail": f"{burst_point.get('month') or '-'} 出现明显爆发（环比 +{max_gap} 首歌曲），属于关系升温拐点。",
        }

    @staticmethod
    def _pick_relation_theme_color(snapshot: Dict[str, Any]) -> str:
        return "#7fd3ff"

    @staticmethod
    def _enrich_evidence_tracks(snapshot: Dict[str, Any], evidence_tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not evidence_tracks:
            return evidence_tracks
        peak_month = "-"
        peak_songs = -1
        for point in snapshot.get("trend_series", []):
            songs = int(point.get("song_count") or 0)
            if songs > peak_songs:
                peak_songs = songs
                peak_month = str(point.get("month") or "-")
        top_artist = str((snapshot.get("top_artists") or [{}])[0].get("name") or "")
        enriched: List[Dict[str, Any]] = []
        for item in evidence_tracks:
            support_for: List[str] = ["互动高频"]
            if str(item.get("reason_tag") or "") == "深夜":
                support_for.append("深夜时段")
            song_artist = str(item.get("artist_name") or "")
            if top_artist and top_artist in song_artist:
                support_for.append("Top歌手偏好")
            msg_month = str(item.get("msg_time") or "")[:7]
            if msg_month and msg_month == peak_month:
                support_for.append("高峰月份")
            row = dict(item)
            row["support_for"] = support_for
            enriched.append(row)
        return enriched

    def _build_song_features(self, song_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        artist_counter: Counter[str] = Counter()
        language_counter: Counter[str] = Counter()
        decade_counter: Counter[str] = Counter()
        hour_counter: Counter[int] = Counter()
        month_rows: dict[str, Dict[str, int]] = defaultdict(lambda: {"msg_count": 0, "song_count": 0})
        unique_songs: set[str] = set()

        for row in song_rows:
            msg_time = str(row.get("msg_time_str") or "")
            parsed = _safe_parse_time(msg_time)
            if parsed:
                hour_counter[parsed.hour] += 1
                decade_counter[f"{(parsed.year // 10) * 10}s"] += 1
                month_rows[parsed.strftime("%Y-%m")]["song_count"] += 1
            artists = [part.strip() for part in str(row.get("artist_name") or "").split("/") if part.strip()]
            if not artists:
                artists = ["未知歌手"]
            for artist in artists:
                artist_counter[artist] += 1

            song_id = str(row.get("song_id") or "").strip()
            song_name = str(row.get("song_name") or "").strip()
            song_key = self.repository.build_song_cache_key(song_id=song_id, song_name=song_name, artist_name=str(row.get("artist_name") or ""))
            unique_songs.add(song_key)

            text_content = str(row.get("text_content") or "").strip()
            raw_msg = str(row.get("raw_msg_json") or "")
            raw_hint = raw_msg[:1600] if raw_msg else ""
            text = f"{song_name} {' '.join(artists)} {text_content} {raw_hint}"
            language = self._infer_language(text)
            language_counter[language] += 1

        unique_artist_count = len(artist_counter)
        unique_song_count = len(unique_songs)
        total_songs = len(song_rows)
        niche_artist_count = sum(1 for _, count in artist_counter.items() if count == 1)
        niche_ratio = niche_artist_count / unique_artist_count if unique_artist_count else 0.0
        unique_artist_ratio = unique_artist_count / total_songs if total_songs else 0.0
        unique_song_ratio = unique_song_count / total_songs if total_songs else 0.0
        discovery_index = self._clamp((unique_artist_ratio + unique_song_ratio + niche_ratio) / 3)

        entropy = self._entropy(artist_counter)
        max_entropy = math.log(max(1, len(artist_counter)))
        if max_entropy <= 0:
            stability_score = 0.5 if total_songs else 0.0
        else:
            stability_score = self._clamp(1.0 - entropy / max_entropy)

        night_count = sum(count for hour, count in hour_counter.items() if self._is_night_hour(hour))
        night_ratio = night_count / total_songs if total_songs else 0.0

        hour_heatmap = [{"hour": f"{hour:02d}", "count": int(hour_counter.get(hour, 0))} for hour in range(24)]
        discovery_breakdown = [
            {
                "key": "unique_artist_ratio",
                "label": "歌手多样性",
                "value": round(unique_artist_ratio, 4),
                "weight": 0.34,
                "contribution": round(unique_artist_ratio * 0.34, 4),
                "explain": "不同歌手占比越高，探索维度越广。",
            },
            {
                "key": "unique_song_ratio",
                "label": "曲目新鲜度",
                "value": round(unique_song_ratio, 4),
                "weight": 0.33,
                "contribution": round(unique_song_ratio * 0.33, 4),
                "explain": "重复率越低，说明更偏向发现新歌。",
            },
            {
                "key": "niche_artist_ratio",
                "label": "冷门歌手占比",
                "value": round(niche_ratio, 4),
                "weight": 0.33,
                "contribution": round(niche_ratio * 0.33, 4),
                "explain": "只出现一次的歌手越多，冷门发掘倾向越强。",
            },
        ]
        return {
            "total_songs": total_songs,
            "top_artists": self._counter_top(artist_counter, limit=5),
            "artist_distribution_all": self._counter_top(artist_counter, limit=max(5, len(artist_counter))),
            "unique_artist_count": unique_artist_count,
            "top_genres": [],
            "top_moods": [],
            "top_languages": self._counter_top(language_counter, limit=5),
            "top_decades": self._counter_top(decade_counter, limit=5),
            "hour_heatmap": hour_heatmap,
            "month_rows": month_rows,
            "night_ratio": round(night_ratio, 4),
            "discovery_index": round(discovery_index, 4),
            "stability_score": round(stability_score, 4),
            "discovery_breakdown": discovery_breakdown,
        }

    @staticmethod
    def _build_message_trend(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        month_rows: dict[str, Dict[str, int]] = defaultdict(lambda: {"msg_count": 0, "song_count": 0})
        for row in rows:
            parsed = _safe_parse_time(str(row.get("msg_time_str") or ""))
            if not parsed:
                continue
            month_key = parsed.strftime("%Y-%m")
            month_rows[month_key]["msg_count"] += 1
            if row.get("msg_type") == "song":
                month_rows[month_key]["song_count"] += 1
        return [{"month": month, **counts} for month, counts in sorted(month_rows.items())]

    @staticmethod
    def _build_response_latency_seconds(rows: List[Dict[str, Any]]) -> float:
        if len(rows) < 2:
            return 0.0
        parsed_rows: list[tuple[str, datetime]] = []
        for row in rows:
            parsed = _safe_parse_time(str(row.get("msg_time_str") or ""))
            if parsed is None:
                continue
            parsed_rows.append((str(row.get("direction") or ""), parsed))
        if len(parsed_rows) < 2:
            return 0.0
        latencies: list[float] = []
        for index in range(len(parsed_rows) - 1):
            current_dir, current_time = parsed_rows[index]
            next_dir, next_time = parsed_rows[index + 1]
            if not current_dir or not next_dir or current_dir == next_dir:
                continue
            delta = (next_time - current_time).total_seconds()
            if 0 < delta <= 24 * 3600:
                latencies.append(delta)
        if not latencies:
            return 0.0
        return round(sum(latencies) / len(latencies), 2)

    def _build_personality_cards(self, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        cards: List[Dict[str, Any]] = []
        night_ratio = float(snapshot.get("night_share_ratio") or 0.0)
        discovery_index = float(snapshot.get("discovery_index") or 0.0)
        stability = float(snapshot.get("stability_score") or 0.0)
        top_decades = snapshot.get("top_decades", [])

        if night_ratio >= 0.40:
            cards.append(
                {
                    "tag": "深夜策展人",
                    "score": round(min(1.0, night_ratio * 1.35), 2),
                    "reason": f"夜间分享占比 {night_ratio * 100:.1f}%，明显高于常规日间分布。",
                    "accent": "night",
                }
            )
        if discovery_index >= 0.62:
            cards.append(
                {
                    "tag": "冷门发掘机",
                    "score": round(min(1.0, discovery_index * 1.2), 2),
                    "reason": f"发现力指数 {discovery_index:.2f}，说明存在持续探索新歌与新歌手倾向。",
                    "accent": "discovery",
                }
            )
        if top_decades and str(top_decades[0].get("name") or "").endswith("s"):
            decade_name = str(top_decades[0].get("name") or "")
            if decade_name.startswith("199") or decade_name.startswith("198"):
                cards.append(
                    {
                        "tag": "旧时代考古学家",
                        "score": round(0.70 + min(0.2, stability * 0.2), 2),
                        "reason": f"年代偏好集中在 {decade_name}，呈现明显经典回溯偏好。",
                        "accent": "decade",
                    }
                )
        if not cards:
            cards.append(
                {
                    "tag": "旋律型讲述者",
                    "score": round(0.65 + min(0.2, stability * 0.2), 2),
                    "reason": f"整体稳定度 {stability:.2f}，偏好结构均衡，以旋律表达为主。",
                    "accent": "default",
                }
            )
        return cards[:4]

    def _build_personality_tags(self, snapshot: Dict[str, Any]) -> List[str]:
        return [str(card.get("tag") or "") for card in self._build_personality_cards(snapshot) if card.get("tag")][:3]

    @staticmethod
    def _build_evidence_tracks(song_rows: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
        evidence: list[Dict[str, Any]] = []
        seen: set[str] = set()
        for row in reversed(song_rows):
            song_id = str(row.get("song_id") or row.get("song_name") or row.get("msg_id") or "")
            if not song_id or song_id in seen:
                continue
            seen.add(song_id)
            parsed = _safe_parse_time(str(row.get("msg_time_str") or ""))
            reason = "高频分享样本"
            reason_tag = "高频"
            if parsed and AnalyticsService._is_night_hour(parsed.hour):
                reason = "深夜分享样本"
                reason_tag = "深夜"
            evidence.append(
                {
                    "song_name": str(row.get("song_name") or "未知歌曲"),
                    "artist_name": str(row.get("artist_name") or "未知歌手"),
                    "msg_time": str(row.get("msg_time_str") or "-"),
                    "reason": reason,
                    "reason_tag": reason_tag,
                }
            )
            if len(evidence) >= limit:
                break
        return evidence

    @staticmethod
    def _shared_name_list(items_a: Iterable[Dict[str, Any]], items_b: Iterable[Dict[str, Any]], limit: int = 4) -> List[str]:
        left = {str(item.get("name") or "").strip(): int(item.get("count") or 0) for item in items_a if item.get("name")}
        right = {str(item.get("name") or "").strip(): int(item.get("count") or 0) for item in items_b if item.get("name")}
        shared_names = [name for name in left if name in right]
        shared_names.sort(key=lambda name: left[name] + right[name], reverse=True)
        return shared_names[:limit]

    @staticmethod
    def _shared_artist_rows(items_a: Iterable[Dict[str, Any]], items_b: Iterable[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
        left = {str(item.get("name") or "").strip(): int(item.get("count") or 0) for item in items_a if item.get("name")}
        right = {str(item.get("name") or "").strip(): int(item.get("count") or 0) for item in items_b if item.get("name")}
        shared_rows: List[Dict[str, Any]] = []
        for name, left_count in left.items():
            right_count = right.get(name)
            if not right_count:
                continue
            shared_rows.append(
                {
                    "name": name,
                    "count": left_count + right_count,
                    "my_count": left_count,
                    "friend_count": right_count,
                }
            )
        shared_rows.sort(key=lambda item: (int(item.get("count") or 0), str(item.get("name") or "")), reverse=True)
        return shared_rows[:limit]

    @staticmethod
    def _build_artist_portrait(
        total_artists: List[Dict[str, Any]],
        my_artists: List[Dict[str, Any]],
        friend_artists: List[Dict[str, Any]],
        my_artist_distribution: List[Dict[str, Any]],
        friend_artist_distribution: List[Dict[str, Any]],
        my_song_count: int,
        friend_song_count: int,
        my_artist_count: int,
        friend_artist_count: int,
    ) -> Dict[str, Any]:
        shared = AnalyticsService._shared_artist_rows(my_artist_distribution, friend_artist_distribution, limit=5)
        return {
            "me_top_artists": list(my_artists[:5]),
            "top_artists": list(total_artists[:3]),
            "friend_top_artists": list(friend_artists[:5]),
            "shared_top_artists": shared,
            "shared_artist_names": [str(item.get("name") or "") for item in shared if item.get("name")],
            "has_shared_artists": bool(shared),
            "my_song_count": int(my_song_count),
            "friend_song_count": int(friend_song_count),
            "my_artist_count": int(my_artist_count),
            "friend_artist_count": int(friend_artist_count),
        }

    @staticmethod
    def _phase_label(song_count: int, msg_count: int, delta: int) -> str:
        if song_count <= 0 and msg_count <= 0:
            return "沉默期"
        if delta >= 12:
            return "爆发期"
        if delta >= 3:
            return "回暖期"
        if delta <= -10:
            return "回落期"
        return "稳定期"

    def build_timeline_visual(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        trend = [item for item in snapshot.get("trend_series", []) if str(item.get("month") or "")]
        if not trend:
            return {"phases": [], "events": [], "summary": "样本不足，暂时无法生成关系时间线。", "dominant_phase": "未知"}

        phases: List[Dict[str, Any]] = []
        events: List[Dict[str, Any]] = []
        peak_point = max(trend, key=lambda item: int(item.get("song_count") or 0))
        phase_counter: Counter[str] = Counter()
        prev_song = int(trend[0].get("song_count") or 0)
        for idx, point in enumerate(trend):
            month = str(point.get("month") or "-")
            msg_count = int(point.get("msg_count") or 0)
            song_count = int(point.get("song_count") or 0)
            delta = song_count - prev_song if idx > 0 else 0
            phase = self._phase_label(song_count, msg_count, delta)
            phase_counter[phase] += 1
            phases.append(
                {
                    "month": month,
                    "phase": phase,
                    "msg_count": msg_count,
                    "song_count": song_count,
                    "delta": delta,
                }
            )
            if idx == 0:
                events.append(
                    {
                        "month": month,
                        "phase": phase,
                        "title": "第一次分享",
                        "detail": f"关系起点在 {month}，当月消息 {msg_count} 条，歌曲 {song_count} 首。",
                        "kind": "start",
                    }
                )
            if month == str(peak_point.get("month") or ""):
                events.append(
                    {
                        "month": month,
                        "phase": phase,
                        "title": "高峰阶段",
                        "detail": f"{month} 达到阶段高峰，歌曲 {song_count} 首，消息 {msg_count} 条。",
                        "kind": "peak",
                    }
                )
            if idx > 0 and abs(delta) >= 12:
                direction = "爆发" if delta > 0 else "回落"
                events.append(
                    {
                        "month": month,
                        "phase": phase,
                        "title": f"{direction}转折",
                        "detail": f"{month} 出现显著{direction}（环比 {delta:+d} 首歌曲）。",
                        "kind": "turning",
                    }
                )
            if phase == "沉默期":
                events.append(
                    {
                        "month": month,
                        "phase": phase,
                        "title": "沉默期",
                        "detail": f"{month} 互动显著降温，进入低频阶段。",
                        "kind": "silent",
                    }
                )
            prev_song = song_count

        first_intro_artist = str(snapshot.get("first_introduced_artist") or "").strip()
        if first_intro_artist and first_intro_artist != "暂无":
            events.append(
                {
                    "month": str((snapshot.get("first_share_at") or snapshot.get("first_message_at") or "-"))[:7] or "-",
                    "phase": "记忆点",
                    "title": "第一次被带入歌手",
                    "detail": f"这段关系最早带入的歌手是 {first_intro_artist}。",
                    "kind": "memory",
                }
            )
        top_artist = str((snapshot.get("top_artists") or [{}])[0].get("name") or "").strip()
        if top_artist:
            events.append(
                {
                    "month": str(peak_point.get("month") or "-"),
                    "phase": "记忆点",
                    "title": "关系音乐记忆",
                    "detail": f"峰值阶段常见歌手 {top_artist or '暂无'}。",
                    "kind": "memory",
                }
            )

        dedup: List[Dict[str, Any]] = []
        seen_keys: set[str] = set()
        for event in events:
            key = f"{event.get('month')}::{event.get('title')}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            dedup.append(event)
        dedup.sort(key=lambda item: str(item.get("month") or ""))

        dominant_phase = phase_counter.most_common(1)[0][0] if phase_counter else "稳定期"
        summary = (
            f"主阶段为{dominant_phase}，高峰在 {peak_point.get('month') or '-'}。"
            f"整体覆盖 {len(trend)} 个时间节点。"
        )
        return {
            "phases": phases,
            "events": dedup[:10],
            "dominant_phase": dominant_phase,
            "summary": summary,
        }

    def build_common_world(self, friend_snapshot: Dict[str, Any], global_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        sender_profile = dict(friend_snapshot.get("sender_song_profile") or {})
        me_profile = dict(sender_profile.get("me") or {})
        friend_profile = dict(sender_profile.get("friend") or {})
        if not me_profile:
            me_profile = {
                "genres": [],
                "artists": [],
                "moods": [],
            }
        if not friend_profile:
            friend_profile = {
                "genres": [],
                "artists": [],
                "moods": [],
            }
        shared_artists = [name for name in me_profile.get("artists", []) if name in set(friend_profile.get("artists", []))][:4]
        overlap_score = self._clamp(len(shared_artists) / 4)
        overlap_bars = [
            {"name": "歌手", "value": len(shared_artists)},
        ]
        return {
            "shared_artists": shared_artists,
            "shared_genres": [],
            "shared_moods": [],
            "shared_languages": [],
            "overlap_score": round(overlap_score, 4),
            "overlap_bars": overlap_bars,
            "compare": {
                "me": me_profile,
                "friend": friend_profile,
                "overlap": {
                    "genres": [],
                    "artists": shared_artists,
                    "moods": [],
                },
            },
            "summary": f"共同歌手重合指数约 {overlap_score * 100:.1f}%。",
        }

    @staticmethod
    def build_dual_perspective(friend_snapshot: Dict[str, Any], global_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        top_artist = str((friend_snapshot.get("top_artists") or [{}])[0].get("name") or "歌手偏好未稳定")
        return {
            "friend_style": {
                "summary": f"Ta 的分享里高频出现的歌手是 {top_artist}。",
                "points": [
                    f"高频歌手：{top_artist}，稳定度 {float(friend_snapshot.get('stability_score') or 0.0):.2f}。",
                ],
            },
        }

    def build_friend_snapshot(self, uid: str, friend_name: str, window: str = "all") -> Dict[str, Any]:
        rows = self.query_friend_messages(uid=uid, window=window)
        song_rows = [row for row in rows if row.get("msg_type") == "song"]
        msg_from_friend = sum(1 for row in rows if str(row.get("direction") or "") == "friend")
        msg_from_self = sum(1 for row in rows if str(row.get("direction") or "") == "self")
        friend_song_rows = [row for row in song_rows if str(row.get("direction") or "") == "friend"]
        self_song_rows = [row for row in song_rows if str(row.get("direction") or "") == "self"]
        trend_series = self._build_message_trend(rows)
        song_features = self._build_song_features(song_rows)
        friend_song_features = self._build_song_features(friend_song_rows)
        self_song_features = self._build_song_features(self_song_rows)
        first_time = rows[0].get("msg_time_str") if rows else ""
        last_time = rows[-1].get("msg_time_str") if rows else ""
        active_days = len({str(row.get("msg_time_str") or "")[:10] for row in rows if row.get("msg_time_str")})
        active_days_30d = len(
            {
                str(row.get("msg_time_str") or "")[:10]
                for row in self._filter_window(rows, "30d")
                if row.get("msg_time_str")
            }
        )
        friend_song_count = sum(1 for row in song_rows if row.get("direction") == "friend")
        self_song_count = sum(1 for row in song_rows if row.get("direction") == "self")
        avg_frequency = round(song_features["total_songs"] / max(1, active_days), 2) if active_days else 0.0
        first_share_at = str(song_rows[0].get("msg_time_str") or "") if song_rows else ""
        recent_share_at = str(song_rows[-1].get("msg_time_str") or "") if song_rows else ""
        snapshot = {
            "scope": "friend",
            "window": self._window_identity(window),
            "uid": uid,
            "friend_name": friend_name or f"好友{uid}",
            "message_count_total": len(rows),
            "message_count_from_friend": msg_from_friend,
            "message_count_from_self": msg_from_self,
            "song_share_count_total": song_features["total_songs"],
            "song_share_from_friend": friend_song_count,
            "song_share_from_self": self_song_count,
            "first_message_at": str(first_time or ""),
            "last_message_at": str(last_time or ""),
            "first_share_at": first_share_at,
            "recent_share_at": recent_share_at,
            "active_days_total": active_days,
            "active_days_30d": active_days_30d,
            "avg_share_frequency": avg_frequency,
            "response_latency_avg_sec": self._build_response_latency_seconds(rows),
            "night_share_ratio": song_features["night_ratio"],
            "stability_score": song_features["stability_score"],
            "discovery_index": song_features["discovery_index"],
            "trend_series": trend_series,
            "hour_heatmap": song_features["hour_heatmap"],
            "top_artists": song_features["top_artists"],
            "top_genres": song_features["top_genres"],
            "top_languages": song_features["top_languages"],
            "top_decades": song_features["top_decades"],
            "top_moods": song_features["top_moods"],
            "discovery_breakdown": song_features["discovery_breakdown"],
            "evidence_tracks": self._build_evidence_tracks(song_rows, limit=5),
            "artist_portrait": self._build_artist_portrait(
                total_artists=song_features["top_artists"],
                my_artists=self_song_features["top_artists"],
                friend_artists=friend_song_features["top_artists"],
                my_artist_distribution=self_song_features.get("artist_distribution_all", []),
                friend_artist_distribution=friend_song_features.get("artist_distribution_all", []),
                my_song_count=self_song_count,
                friend_song_count=friend_song_count,
                my_artist_count=int(self_song_features.get("unique_artist_count") or 0),
                friend_artist_count=int(friend_song_features.get("unique_artist_count") or 0),
            ),
            "sender_song_profile": {
                "friend": self._sender_profile_slice(friend_song_features),
                "me": self._sender_profile_slice(self_song_features),
            },
            "sender_artist_distribution": {
                "friend": friend_song_features.get("artist_distribution_all", []),
                "me": self_song_features.get("artist_distribution_all", []),
            },
        }
        snapshot["personality_cards"] = self._build_personality_cards(snapshot)
        snapshot["personality_tags"] = self._build_personality_tags(snapshot)
        snapshot["trend_conclusion"] = self._build_trend_conclusion(trend_series)
        snapshot["activity_conclusion"] = self._build_activity_conclusion(song_features["hour_heatmap"])
        snapshot["relation_temperature"] = self._build_relation_temperature(snapshot)
        snapshot["relation_theme_color"] = self._pick_relation_theme_color(snapshot)
        snapshot["first_introduced_artist"] = self._build_first_introduced_artist(song_rows)
        snapshot["silence_and_burst"] = self._build_silence_and_burst(trend_series)
        snapshot["timeline_visual"] = self.build_timeline_visual(snapshot)
        snapshot["cover_line"] = self._build_relation_cover_line(snapshot)
        snapshot["evidence_tracks"] = self._enrich_evidence_tracks(snapshot, snapshot.get("evidence_tracks", []))
        return snapshot

    @staticmethod
    def _merge_rank_counts(items: Iterable[Dict[str, Any]], key_name: str = "name", count_name: str = "count") -> Counter[str]:
        merged: Counter[str] = Counter()
        for item in items:
            name = str(item.get(key_name) or "").strip()
            count = int(item.get(count_name) or 0)
            if name and count > 0:
                merged[name] += count
        return merged

    @staticmethod
    def _sender_profile_slice(features: Dict[str, Any]) -> Dict[str, List[str]]:
        return {
            "genres": [],
            "artists": [str(item.get("name") or "") for item in (features.get("top_artists") or [])[:4] if item.get("name")],
            "moods": [],
        }

    @staticmethod
    def _build_self_cover_line(snapshot: Dict[str, Any]) -> str:
        tag = str(snapshot.get("social_tag") or "社交均衡型")
        peak = str(snapshot.get("peak_month") or "-")
        active = int(snapshot.get("active_friend_count") or 0)
        song_count = int(snapshot.get("song_count") or 0)
        return f"{tag} · 高峰在 {peak}，当前覆盖 {active} 位活跃好友，累计歌曲 {song_count} 首。"

    @staticmethod
    def _classify_balance(input_value: int, output_value: int) -> Dict[str, Any]:
        total = max(1, input_value + output_value)
        ratio = abs(input_value - output_value) / total
        if ratio <= 0.12:
            label = "平衡型"
        elif input_value > output_value:
            label = "输入型"
        else:
            label = "输出型"
        return {
            "label": label,
            "input": int(input_value),
            "output": int(output_value),
            "ratio": round(ratio, 4),
        }

    @staticmethod
    def _classify_concentration(values: List[int]) -> Dict[str, Any]:
        positive = [int(v) for v in values if int(v) > 0]
        if not positive:
            return {"label": "暂无样本", "score": 0.0}
        total = sum(positive)
        sorted_vals = sorted(positive, reverse=True)
        top_share = (sorted_vals[0] + (sorted_vals[1] if len(sorted_vals) > 1 else 0)) / max(1, total)
        if top_share >= 0.68:
            label = "高集中"
        elif top_share >= 0.46:
            label = "中集中"
        else:
            label = "分散型"
        return {"label": label, "score": round(top_share, 4)}

    @staticmethod
    def _network_top5(friend_snapshots: List[Dict[str, Any]], key: str, unit: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for snap in friend_snapshots:
            value = int(snap.get(key) or 0)
            if value <= 0:
                continue
            rows.append(
                {
                    "uid": str(snap.get("uid") or ""),
                    "name": str(snap.get("friend_name") or "好友"),
                    "avatar_url": str(snap.get("avatar_url") or ""),
                    "value": value,
                    "unit": unit,
                }
            )
        rows.sort(key=lambda item: int(item.get("value") or 0), reverse=True)
        return rows[:5]

    @staticmethod
    def _build_network_summary(title: str, rows: List[Dict[str, Any]], unit: str, direction: str) -> str:
        if not rows:
            return f"{title}暂无有效样本。"
        total = sum(int(item.get("value") or 0) for item in rows)
        lead = rows[0]
        lead_name = str(lead.get("name") or "好友")
        lead_value = int(lead.get("value") or 0)
        lead_ratio = (lead_value / max(1, total)) * 100
        return f"{title}以{direction}为主，核心对象为 {lead_name}（{lead_value}{unit}，占比 {lead_ratio:.1f}%）。"

    @staticmethod
    def _pick_core_friend_name(friend_snapshots: List[Dict[str, Any]]) -> str:
        if not friend_snapshots:
            return ""
        ordered = sorted(
            friend_snapshots,
            key=lambda item: (
                int(item.get("message_count_total") or 0) + int(item.get("song_share_count_total") or 0),
                int(item.get("song_share_from_friend") or 0),
            ),
            reverse=True,
        )
        return str((ordered[0] or {}).get("friend_name") or "")

    @staticmethod
    def _pick_self_first_introduced_artist(friend_snapshots: List[Dict[str, Any]]) -> str:
        first_artist = ""
        first_time: datetime | None = None
        for snapshot in friend_snapshots:
            artist = str(snapshot.get("first_introduced_artist") or "").strip()
            if not artist or artist == "暂无":
                continue
            parsed = _safe_parse_time(str(snapshot.get("first_share_at") or ""))
            if parsed is None:
                continue
            if first_time is None or parsed < first_time:
                first_time = parsed
                first_artist = artist
        return first_artist or "暂无"

    @staticmethod
    def _merge_self_evidence_tracks(friend_snapshots: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        seen: set[str] = set()
        ordered = sorted(friend_snapshots, key=lambda item: int(item.get("song_share_count_total") or 0), reverse=True)
        for snapshot in ordered:
            friend_name = str(snapshot.get("friend_name") or "好友")
            for row in snapshot.get("evidence_tracks", []) or []:
                song_name = str(row.get("song_name") or "").strip()
                artist_name = str(row.get("artist_name") or "").strip()
                dedup_key = f"{song_name}::{artist_name}"
                if not dedup_key or dedup_key in seen:
                    continue
                seen.add(dedup_key)
                merged.append(
                    {
                        "song_name": song_name or "未知歌曲",
                        "artist_name": artist_name or "未知歌手",
                        "msg_time": str(row.get("msg_time") or "-"),
                        "reason": str(row.get("reason") or "样本"),
                        "reason_tag": str(row.get("reason_tag") or "样本"),
                        "support_for": [f"来自 {friend_name}", "社交网络样本"],
                    }
                )
                if len(merged) >= limit:
                    return merged
        return merged

    def _build_self_network_block(self, friend_snapshots: List[Dict[str, Any]]) -> Dict[str, Any]:
        music_in = self._network_top5(friend_snapshots, "song_share_from_friend", "首")
        music_out = self._network_top5(friend_snapshots, "song_share_from_self", "首")
        chat_in = self._network_top5(friend_snapshots, "message_count_from_friend", "条")
        chat_out = self._network_top5(friend_snapshots, "message_count_from_self", "条")

        music_in_total = sum(int(item.get("value") or 0) for item in music_in)
        music_out_total = sum(int(item.get("value") or 0) for item in music_out)
        chat_in_total = sum(int(item.get("value") or 0) for item in chat_in)
        chat_out_total = sum(int(item.get("value") or 0) for item in chat_out)

        music_balance = self._classify_balance(music_in_total, music_out_total)
        chat_balance = self._classify_balance(chat_in_total, chat_out_total)
        music_concentration = self._classify_concentration([int(item.get("value") or 0) for item in music_in])
        chat_concentration = self._classify_concentration([int(item.get("value") or 0) for item in chat_in])
        music_balance["summary"] = (
            f"音乐社交：{music_balance.get('label')}（输入 {music_in_total} 首 / 输出 {music_out_total} 首）。"
        )
        chat_balance["summary"] = (
            f"聊天社交：{chat_balance.get('label')}（输入 {chat_in_total} 条 / 输出 {chat_out_total} 条）。"
        )
        music_concentration["summary"] = (
            f"音乐核心圈层：{music_concentration.get('label')}（Top2 占比 {float(music_concentration.get('score') or 0.0) * 100:.1f}%）。"
        )
        chat_concentration["summary"] = (
            f"聊天核心圈层：{chat_concentration.get('label')}（Top2 占比 {float(chat_concentration.get('score') or 0.0) * 100:.1f}%）。"
        )
        return {
            "music_input": music_in,
            "music_output": music_out,
            "chat_input": chat_in,
            "chat_output": chat_out,
            "music_balance": music_balance,
            "chat_balance": chat_balance,
            "music_concentration": music_concentration,
            "chat_concentration": chat_concentration,
            "music_input_block": {
                "items": music_in,
                "unit": "首",
                "empty_text": "暂无音乐输入数据",
                "summary": self._build_network_summary("音乐输入网络", music_in, "首", "输入"),
            },
            "music_output_block": {
                "items": music_out,
                "unit": "首",
                "empty_text": "暂无音乐输出数据",
                "summary": self._build_network_summary("音乐输出网络", music_out, "首", "输出"),
            },
            "chat_input_block": {
                "items": chat_in,
                "unit": "条",
                "empty_text": "暂无聊天输入数据",
                "summary": self._build_network_summary("聊天输入网络", chat_in, "条", "输入"),
            },
            "chat_output_block": {
                "items": chat_out,
                "unit": "条",
                "empty_text": "暂无聊天输出数据",
                "summary": self._build_network_summary("聊天输出网络", chat_out, "条", "输出"),
            },
        }

    def _build_self_artist_overview(self, friend_snapshots: List[Dict[str, Any]]) -> Dict[str, Any]:
        my_artist_counter: Counter[str] = Counter()
        friend_artist_counter: Counter[str] = Counter()
        for snapshot in friend_snapshots:
            for item in snapshot.get("sender_artist_distribution", {}).get("me", []) or []:
                name = str(item.get("name") or "").strip()
                count = int(item.get("count") or 0)
                if name and count > 0:
                    my_artist_counter[name] += count
            for item in snapshot.get("sender_artist_distribution", {}).get("friend", []) or []:
                name = str(item.get("name") or "").strip()
                count = int(item.get("count") or 0)
                if name and count > 0:
                    friend_artist_counter[name] += count
        shared_top_artists = self._shared_artist_rows(
            [{"name": name, "count": count} for name, count in my_artist_counter.items()],
            [{"name": name, "count": count} for name, count in friend_artist_counter.items()],
            limit=5,
        )
        return {
            "all_friends_top_artists": self._counter_top(friend_artist_counter, 5),
            "my_top_artists": self._counter_top(my_artist_counter, 5),
            "shared_top_artists": shared_top_artists,
        }

    def _build_self_timeline_visual(self, snapshot: Dict[str, Any], window: str) -> Dict[str, Any]:
        trend = [item for item in snapshot.get("trend_series", []) if str(item.get("month") or "")]
        if not trend:
            return {"phases": [], "events": [], "summary": "暂无社交节律样本。", "dominant_phase": "未知"}

        phases: List[Dict[str, Any]] = []
        events: List[Dict[str, Any]] = []
        peak_song_point = max(trend, key=lambda item: int(item.get("song_count") or 0))
        peak_msg_point = max(trend, key=lambda item: int(item.get("msg_count") or 0))
        phase_counter: Counter[str] = Counter()
        prev_song = int(trend[0].get("song_count") or 0)
        for idx, point in enumerate(trend):
            month = str(point.get("month") or "-")
            msg_count = int(point.get("msg_count") or 0)
            song_count = int(point.get("song_count") or 0)
            delta = song_count - prev_song if idx > 0 else 0
            phase = self._phase_label(song_count, msg_count, delta)
            phases.append({"month": month, "phase": phase, "msg_count": msg_count, "song_count": song_count, "delta": delta})
            phase_counter[phase] += 1
            if idx == 0:
                title = "当年第一次分享" if self._parse_year_window(window) is not None else "第一次分享"
                events.append(
                    {
                        "month": month,
                        "phase": phase,
                        "title": title,
                        "detail": f"{month} 开始形成可追踪社交节律（消息 {msg_count} / 歌曲 {song_count}）。",
                        "kind": "start",
                    }
                )
            if month == str(peak_song_point.get("month") or ""):
                title = "当年歌曲高峰月" if self._parse_year_window(window) is not None else "全局歌曲高峰月"
                events.append(
                    {
                        "month": month,
                        "phase": phase,
                        "title": title,
                        "detail": f"{month} 歌曲互动达到峰值（{song_count} 首）。",
                        "kind": "peak",
                    }
                )
            if month == str(peak_msg_point.get("month") or "") and month != str(peak_song_point.get("month") or ""):
                title = "当年聊天高峰月" if self._parse_year_window(window) is not None else "聊天高峰月"
                events.append(
                    {
                        "month": month,
                        "phase": phase,
                        "title": title,
                        "detail": f"{month} 聊天互动最高（{msg_count} 条）。",
                        "kind": "peak",
                    }
                )
            prev_song = song_count

        first_artist = str(snapshot.get("first_introduced_artist") or "").strip()
        if first_artist and first_artist != "暂无":
            title = "当年第一次被带入歌手" if self._parse_year_window(window) is not None else "第一次被带入歌手"
            events.append(
                {
                    "month": str(peak_song_point.get("month") or "-"),
                    "phase": "记忆点",
                    "title": title,
                    "detail": f"该周期内最具代表的带入歌手为 {first_artist}。",
                    "kind": "memory",
                }
            )

        core_friend = str(snapshot.get("core_friend_name") or "").strip()
        if core_friend:
            events.append(
                {
                    "month": str(peak_msg_point.get("month") or "-"),
                    "phase": "记忆点",
                    "title": "升温最明显关系",
                    "detail": f"{core_friend} 在本周期是最主要的升温关系。",
                    "kind": "memory",
                }
            )

        dedup: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for event in events:
            key = f"{event.get('month')}::{event.get('title')}"
            if key in seen:
                continue
            seen.add(key)
            dedup.append(event)
        dedup.sort(key=lambda item: str(item.get("month") or ""))

        dominant = phase_counter.most_common(1)[0][0] if phase_counter else "稳定期"
        summary = f"整体社交主阶段为{dominant}，歌曲高峰在 {peak_song_point.get('month') or '-'}。"
        return {"phases": phases, "events": dedup[:8], "summary": summary, "dominant_phase": dominant}

    def build_global_snapshot(self, friend_snapshots: List[Dict[str, Any]], window: str = "all") -> Dict[str, Any]:
        total_messages = sum(int(item.get("message_count_total") or 0) for item in friend_snapshots)
        total_songs = sum(int(item.get("song_share_count_total") or 0) for item in friend_snapshots)
        active_friend_count = sum(1 for item in friend_snapshots if int(item.get("message_count_total") or 0) > 0)
        chat_rank = sorted(friend_snapshots, key=lambda item: int(item.get("message_count_total") or 0), reverse=True)
        song_rank = sorted(friend_snapshots, key=lambda item: int(item.get("song_share_count_total") or 0), reverse=True)
        top_chat_friends = [
            {
                "uid": item.get("uid"),
                "name": item.get("friend_name"),
                "count": int(item.get("message_count_total") or 0),
            }
            for item in chat_rank[:3]
        ]
        top_song_friends = [
            {
                "uid": item.get("uid"),
                "name": item.get("friend_name"),
                "count": int(item.get("song_share_count_total") or 0),
            }
            for item in song_rank[:3]
        ]

        merged_month: dict[str, Dict[str, int]] = defaultdict(lambda: {"msg_count": 0, "song_count": 0})
        artist_counter: Counter[str] = Counter()
        language_counter: Counter[str] = Counter()
        decade_counter: Counter[str] = Counter()
        weighted_night_sum = 0.0
        weighted_discovery_sum = 0.0
        weighted_stability_sum = 0.0
        weighted_song_base = 0
        for snapshot in friend_snapshots:
            for point in snapshot.get("trend_series", []):
                month = str(point.get("month") or "")
                if not month:
                    continue
                merged_month[month]["msg_count"] += int(point.get("msg_count") or 0)
                merged_month[month]["song_count"] += int(point.get("song_count") or 0)
            artist_counter += self._merge_rank_counts(snapshot.get("top_artists", []))
            language_counter += self._merge_rank_counts(snapshot.get("top_languages", []))
            decade_counter += self._merge_rank_counts(snapshot.get("top_decades", []))
            song_count = int(snapshot.get("song_share_count_total") or 0)
            weighted_song_base += song_count
            weighted_night_sum += song_count * float(snapshot.get("night_share_ratio") or 0.0)
            weighted_discovery_sum += song_count * float(snapshot.get("discovery_index") or 0.0)
            weighted_stability_sum += song_count * float(snapshot.get("stability_score") or 0.0)

        month_trend = [{"month": month, **value} for month, value in sorted(merged_month.items())]
        night_ratio = (weighted_night_sum / weighted_song_base) if weighted_song_base else 0.0
        avg_discovery = (weighted_discovery_sum / weighted_song_base) if weighted_song_base else 0.0
        avg_stability = (weighted_stability_sum / weighted_song_base) if weighted_song_base else 0.0
        return {
            "scope": "global",
            "window": self._window_identity(window),
            "friend_count": len(friend_snapshots),
            "active_friend_count": active_friend_count,
            "message_count": total_messages,
            "song_count": total_songs,
            "top_chat_friends": top_chat_friends,
            "top_song_friends": top_song_friends,
            "top_temperature_friends": sorted(
                [
                    {
                        "uid": item.get("uid"),
                        "name": item.get("friend_name"),
                        "count": int((item.get("relation_temperature") or {}).get("score") or 0),
                    }
                    for item in friend_snapshots
                ],
                key=lambda row: int(row.get("count") or 0),
                reverse=True,
            )[:3],
            "trend_series": month_trend,
            "top_artists": self._counter_top(artist_counter, 5),
            "top_genres": [],
            "top_languages": self._counter_top(language_counter, 5),
            "top_moods": [],
            "top_decades": self._counter_top(decade_counter, 5),
            "night_share_ratio": round(night_ratio, 4),
            "avg_discovery_index": round(avg_discovery, 4),
            "avg_stability_score": round(avg_stability, 4),
            "trend_conclusion": self._build_trend_conclusion(month_trend),
        }

    def build_self_snapshot(
        self,
        friend_snapshots: List[Dict[str, Any]],
        global_snapshot: Dict[str, Any],
        account_name: str,
        window: str = "all",
    ) -> Dict[str, Any]:
        message_total = int(global_snapshot.get("message_count") or 0)
        song_total = int(global_snapshot.get("song_count") or 0)
        night_weight = 0.0
        stability_weight = 0.0
        discovery_weight = 0.0
        weighted_base = 0
        for snapshot in friend_snapshots:
            count = int(snapshot.get("song_share_count_total") or 0)
            weighted_base += count
            night_weight += count * float(snapshot.get("night_share_ratio") or 0.0)
            stability_weight += count * float(snapshot.get("stability_score") or 0.0)
            discovery_weight += count * float(snapshot.get("discovery_index") or 0.0)
        night_ratio = (night_weight / weighted_base) if weighted_base else 0.0
        stability_score = (stability_weight / weighted_base) if weighted_base else 0.0
        discovery_index = (discovery_weight / weighted_base) if weighted_base else 0.0
        network_block = self._build_self_network_block(friend_snapshots)
        peak_month = "-"
        peak_count = 0
        for point in global_snapshot.get("trend_series", []):
            song_count = int(point.get("song_count") or 0)
            if song_count > peak_count:
                peak_count = song_count
                peak_month = str(point.get("month") or "-")
        social_tag = "社交均衡型"
        music_balance_label = str((network_block.get("music_balance") or {}).get("label") or "")
        if music_balance_label == "输入型":
            social_tag = "输入策展型"
        elif music_balance_label == "输出型":
            social_tag = "输出驱动型"
        elif str((network_block.get("music_concentration") or {}).get("label") or "") == "高集中":
            social_tag = "核心圈层型"
        core_friend_name = self._pick_core_friend_name(friend_snapshots)
        first_introduced_artist = self._pick_self_first_introduced_artist(friend_snapshots)
        active_days_total = sum(int(item.get("active_days_total") or 0) for item in friend_snapshots)
        self_snapshot = {
            "scope": "self",
            "window": self._window_identity(window),
            "account_name": account_name or "我",
            "friend_count": global_snapshot.get("friend_count", 0),
            "active_friend_count": global_snapshot.get("active_friend_count", 0),
            "message_count": message_total,
            "song_count": song_total,
            "active_days_total": active_days_total,
            "night_share_ratio": round(night_ratio, 4),
            "stability_score": round(stability_score, 4),
            "discovery_index": round(discovery_index, 4),
            "peak_month": peak_month,
            "social_tag": social_tag,
            "core_friend_name": core_friend_name,
            "first_introduced_artist": first_introduced_artist,
            "top_chat_friends": global_snapshot.get("top_chat_friends", []),
            "top_song_friends": global_snapshot.get("top_song_friends", []),
            "top_temperature_friends": global_snapshot.get("top_temperature_friends", []),
            "top_artists": global_snapshot.get("top_artists", []),
            "top_genres": [],
            "top_languages": global_snapshot.get("top_languages", []),
            "top_decades": global_snapshot.get("top_decades", []),
            "top_moods": [],
            "trend_series": global_snapshot.get("trend_series", []),
            "trend_conclusion": str(global_snapshot.get("trend_conclusion") or "暂无趋势结论。"),
            "network_block": network_block,
            "artist_overview": self._build_self_artist_overview(friend_snapshots),
            "evidence_tracks": self._merge_self_evidence_tracks(friend_snapshots, limit=5),
        }
        self_snapshot["timeline_visual"] = self._build_self_timeline_visual(self_snapshot, window)
        self_snapshot["cover_line"] = self._build_self_cover_line(self_snapshot)
        return self_snapshot

    @staticmethod
    def _month_year(month_value: str) -> int | None:
        text = str(month_value or "").strip()
        if len(text) < 4:
            return None
        try:
            return int(text[:4])
        except ValueError:
            return None

    def build_annual_review(
        self,
        friend_snapshots: List[Dict[str, Any]],
        global_snapshot: Dict[str, Any],
        year: int | None = None,
    ) -> Dict[str, Any]:
        trend = list(global_snapshot.get("trend_series", []) or [])
        if not trend:
            chosen_year = year or datetime.now().year
            return {
                "year": chosen_year,
                "message_count": 0,
                "song_count": 0,
                "peak_month": "-",
                "top_chat_friend_name": "暂无",
                "top_song_friend_name": "暂无",
                "representative_relationship": "暂无",
                "summary": f"{chosen_year} 年暂无可用互动数据。",
            }

        years = [self._month_year(str(item.get("month") or "")) for item in trend]
        valid_years = sorted({item for item in years if item is not None})
        chosen_year = year or (valid_years[-1] if valid_years else datetime.now().year)
        use_all_history = year is None

        year_points = trend if use_all_history else [item for item in trend if self._month_year(str(item.get("month") or "")) == chosen_year]
        if not year_points:
            year_points = trend
            inferred = self._month_year(str(year_points[-1].get("month") or ""))
            if inferred is not None:
                chosen_year = inferred

        message_count = sum(int(item.get("msg_count") or 0) for item in year_points)
        song_count = sum(int(item.get("song_count") or 0) for item in year_points)
        peak_month = "-"
        if year_points:
            peak_month = str(max(year_points, key=lambda item: int(item.get("song_count") or 0)).get("month") or "-")

        friend_year_stats: List[Dict[str, Any]] = []
        for snap in friend_snapshots:
            msg_total = 0
            song_total = 0
            for point in snap.get("trend_series", []) or []:
                if not use_all_history and self._month_year(str(point.get("month") or "")) != chosen_year:
                    continue
                msg_total += int(point.get("msg_count") or 0)
                song_total += int(point.get("song_count") or 0)
            friend_year_stats.append(
                {
                    "uid": str(snap.get("uid") or ""),
                    "friend_name": str(snap.get("friend_name") or "好友"),
                    "msg_count": msg_total,
                    "song_count": song_total,
                    "total_score": msg_total + song_total,
                }
            )

        friend_year_stats.sort(key=lambda item: item["msg_count"], reverse=True)
        top_chat = friend_year_stats[0] if friend_year_stats else {"friend_name": "暂无", "msg_count": 0}
        friend_year_stats.sort(key=lambda item: item["song_count"], reverse=True)
        top_song = friend_year_stats[0] if friend_year_stats else {"friend_name": "暂无", "song_count": 0}
        friend_year_stats.sort(key=lambda item: item["total_score"], reverse=True)
        representative = friend_year_stats[0] if friend_year_stats else {"friend_name": "暂无", "total_score": 0}

        if use_all_history:
            summary = (
                f"全部历史里你累计产生 {message_count} 条消息互动、收到 {song_count} 首歌曲；"
                f"高峰月份在 {peak_month}，代表关系对象是 {representative.get('friend_name') or '暂无'}。"
            )
        else:
            summary = (
                f"{chosen_year} 年你累计产生 {message_count} 条消息互动、收到 {song_count} 首歌曲；"
                f"高峰月份在 {peak_month}，代表关系对象是 {representative.get('friend_name') or '暂无'}。"
            )
        return {
            "year": chosen_year,
            "scope": "all" if use_all_history else "year",
            "message_count": message_count,
            "song_count": song_count,
            "peak_month": peak_month,
            "top_chat_friend_name": str(top_chat.get("friend_name") or "暂无"),
            "top_chat_friend_count": int(top_chat.get("msg_count") or 0),
            "top_song_friend_name": str(top_song.get("friend_name") or "暂无"),
            "top_song_friend_count": int(top_song.get("song_count") or 0),
            "representative_relationship": str(representative.get("friend_name") or "暂无"),
            "representative_score": int(representative.get("total_score") or 0),
            "summary": summary,
        }

    def build_similarity_matrix(self, friend_snapshots: List[Dict[str, Any]], top_n: int = 8) -> List[Dict[str, Any]]:
        valid = [item for item in friend_snapshots if int(item.get("song_share_count_total") or 0) > 0]
        if len(valid) < 2:
            return []
        vectors: dict[str, List[float]] = {}
        for item in valid:
            vectors[str(item.get("uid"))] = [
                float(item.get("night_share_ratio") or 0.0),
                float(item.get("discovery_index") or 0.0),
                float(item.get("stability_score") or 0.0),
            ]

        def _cosine(a: List[float], b: List[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(y * y for y in b))
            if norm_a <= 0 or norm_b <= 0:
                return 0.0
            return max(0.0, min(1.0, dot / (norm_a * norm_b)))

        pairs: list[Dict[str, Any]] = []
        for left_index, left in enumerate(valid):
            left_uid = str(left.get("uid"))
            for right in valid[left_index + 1 :]:
                right_uid = str(right.get("uid"))
                score = _cosine(vectors[left_uid], vectors[right_uid])
                left_artists = {str(item.get("name") or "") for item in left.get("top_artists", []) if item.get("name")}
                right_artists = {str(item.get("name") or "") for item in right.get("top_artists", []) if item.get("name")}
                common_artists = sorted(name for name in (left_artists & right_artists) if name)
                pairs.append(
                    {
                        "uid_a": left_uid,
                        "name_a": left.get("friend_name"),
                        "uid_b": right_uid,
                        "name_b": right.get("friend_name"),
                        "score": round(score, 4),
                        "summary": "、".join(common_artists[:2]) if common_artists else "节奏偏好接近",
                    }
                )
        pairs.sort(key=lambda item: item["score"], reverse=True)
        return pairs[: max(1, top_n)]

    def build_ai_feature_payload(
        self,
        snapshot: Dict[str, Any],
        audience_scope: str,
        period_label: str = "全量历史",
    ) -> Dict[str, Any]:
        return {
            "audience_scope": audience_scope,
            "friend_name": snapshot.get("friend_name") or snapshot.get("account_name") or "关系对象",
            "period_label": period_label,
            "total_songs": int(snapshot.get("song_share_count_total") or snapshot.get("song_count") or 0),
            "total_msgs": int(snapshot.get("message_count_total") or snapshot.get("message_count") or 0),
            "active_span_days": int(snapshot.get("active_days_total") or 0),
            "top_artist_3": snapshot.get("top_artists", [])[:3],
            "decade_distribution": snapshot.get("top_decades", [])[:5],
            "language_distribution": snapshot.get("top_languages", [])[:5],
            "night_ratio": float(snapshot.get("night_share_ratio") or 0.0),
            "stability_score": float(snapshot.get("stability_score") or 0.0),
            "discovery_index": float(snapshot.get("discovery_index") or 0.0),
            "evidence_tracks": snapshot.get("evidence_tracks", [])[:5],
            "common_world": snapshot.get("common_world", {}),
            "discovery_breakdown": snapshot.get("discovery_breakdown", []),
            "personality_cards": snapshot.get("personality_cards", [])[:4],
            "annual_review": snapshot.get("annual_review", {}),
            "relation_temperature": snapshot.get("relation_temperature", {}),
            "timeline_visual": snapshot.get("timeline_visual", {}),
            "trend_conclusion": snapshot.get("trend_conclusion", ""),
            "activity_conclusion": snapshot.get("activity_conclusion", ""),
            "cover_line": snapshot.get("cover_line", ""),
            "first_introduced_artist": snapshot.get("first_introduced_artist", ""),
            "silence_and_burst": snapshot.get("silence_and_burst", {}),
            "relation_theme_color": snapshot.get("relation_theme_color", "#7fd3ff"),
            "social_tag": snapshot.get("social_tag", ""),
            "core_friend_name": snapshot.get("core_friend_name", ""),
            "top_chat_friends": snapshot.get("top_chat_friends", [])[:3],
            "top_song_friends": snapshot.get("top_song_friends", [])[:3],
            "top_temperature_friends": snapshot.get("top_temperature_friends", [])[:3],
            "artist_overview": snapshot.get("artist_overview", {}),
            "network_block": snapshot.get("network_block", {}),
        }
