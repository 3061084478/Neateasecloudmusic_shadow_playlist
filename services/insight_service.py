from __future__ import annotations

import json
from typing import Any, Dict, List

import requests


class InsightService:
    def __init__(self) -> None:
        pass

    @staticmethod
    def _mode_key(mode: str) -> str:
        normalized = (mode or "").strip().lower()
        if normalized in {"style", "风格", "风格版"}:
            return "style"
        if normalized in {"commentary", "comment", "评论", "评论版"}:
            return "commentary"
        if normalized in {"annual", "year", "年度", "年度报告", "年度报告版"}:
            return "annual"
        return "rational"

    @staticmethod
    def _is_insufficient(payload: Dict[str, Any]) -> bool:
        return int(payload.get("total_songs") or 0) < 10 or int(payload.get("active_span_days") or 0) < 7

    def fallback_template(self, payload: Dict[str, Any], mode: str) -> str:
        mode_key = self._mode_key(mode)
        name = str(payload.get("friend_name") or "这段关系")
        total_songs = int(payload.get("total_songs") or 0)
        total_msgs = int(payload.get("total_msgs") or 0)
        active_days = int(payload.get("active_span_days") or 0)
        top_genres = payload.get("top_genre_3") or []
        top_artists = payload.get("top_artist_3") or []
        top_moods = payload.get("top_mood_3") or []
        night_ratio = float(payload.get("night_ratio") or 0.0)
        genre_text = "、".join(str(item.get("name")) for item in top_genres if item.get("name")) or "风格尚不稳定"
        artist_text = "、".join(str(item.get("name")) for item in top_artists if item.get("name")) or "歌手偏好尚未形成"
        mood_text = "、".join(str(item.get("name")) for item in top_moods if item.get("name")) or "情绪分布尚不明显"
        if self._is_insufficient(payload):
            return (
                f"样本量较少（歌曲 {total_songs} 首、活跃天数 {active_days} 天），当前仅能给出轻量观察："
                f"{name} 的分享集中在 {genre_text}，夜间占比约 {night_ratio * 100:.1f}%。"
                "建议继续累积一段时间后再生成完整画像。"
            )
        if mode_key == "annual":
            annual = payload.get("annual_review") or {}
            year = str(annual.get("year") or "当年")
            annual_songs = int(annual.get("song_count") or total_songs)
            annual_msgs = int(annual.get("message_count") or total_msgs)
            peak_month = str(annual.get("peak_month") or "-")
            top_friend = str(annual.get("top_song_friend_name") or "暂无")
            return (
                f"{year} 年度音乐社交回顾：你共收到 {annual_songs} 首歌曲、产生 {annual_msgs} 条互动消息。"
                f"高峰月份在 {peak_month}，代表关系对象是 {top_friend}。"
                f"全年风格主轴为 {genre_text}，夜间占比约 {night_ratio * 100:.1f}%。"
                "这一年你的音乐世界在稳定偏好之外，也保持了可观的探索弹性。"
            )
        if mode_key == "commentary":
            return (
                f"如果把这段关系写成乐评，它的主线是 {genre_text}，副线是 {mood_text}。"
                f"{name} 在 {active_days} 天里投递了 {total_songs} 首歌，像持续更新的私人栏目；"
                f"而 {artist_text} 则是这个栏目反复出现的关键署名。"
                f"夜间占比 {night_ratio * 100:.1f}% 说明你们常在一天收束时交换情绪与声音。"
            )
        if mode_key == "style":
            return (
                f"{name} 像在用歌单写长信：你们在 {active_days} 天里留下了 {total_msgs} 条消息和 {total_songs} 首歌。"
                f"主色调落在 {genre_text}，常出现的名字是 {artist_text}。"
                f"情绪层面更偏向 {mood_text}，其中夜间时段约占 {night_ratio * 100:.1f}%，"
                "像是把白天说不完的话，交给了深夜的耳机。"
            )
        return (
            f"{name} 在当前周期内产生 {total_msgs} 条消息、{total_songs} 首歌曲分享。"
            f"高频风格为 {genre_text}，高频歌手为 {artist_text}，情绪倾向 {mood_text}。"
            f"夜间分享比例约 {night_ratio * 100:.1f}%。"
            "整体表现为有稳定偏好，同时保留一定探索性。"
        )

    def _build_system_prompt(self, mode: str) -> str:
        mode_key = self._mode_key(mode)
        if mode_key == "annual":
            return (
                "你是年度音乐社交报告编辑。请输出一段年度回顾文案，"
                "语气克制、结论清晰，必须引用至少3个可验证指标，不得编造。"
            )
        if mode_key == "commentary":
            return (
                "你是音乐评论编辑。请输出评论体中文文案，有文风但不浮夸，"
                "每段至少有一个数据锚点，不得脱离输入事实。"
            )
        if mode_key == "style":
            return (
                "你是音乐关系评论编辑。输出一段有叙事感但不过度夸张的中文短文。"
                "只能依据输入结构化特征，不得捏造新事实。"
                "必须点出至少2个可验证指标。"
            )
        return (
            "你是音乐关系分析师。输出简洁、可核验的中文分析。"
            "只能使用输入中的结构化特征，不得编造。"
            "需要明确写出核心指标和结论。"
        )

    def _cloud_generate(self, payload: Dict[str, Any], mode: str, config: Dict[str, Any]) -> str:
        api_key = str(config.get("ai_api_key") or "").strip()
        base_url = str(config.get("ai_base_url") or "").strip().rstrip("/")
        model = str(config.get("ai_model") or "").strip()
        if not api_key or not base_url or not model:
            raise RuntimeError("AI 配置不完整。")
        endpoint = f"{base_url}/chat/completions"
        timeout = int(config.get("ai_timeout") or 20)
        body = {
            "model": model,
            "temperature": 0.55 if self._mode_key(mode) == "style" else 0.3,
            "messages": [
                {"role": "system", "content": self._build_system_prompt(mode)},
                {
                    "role": "user",
                    "content": "请根据以下 JSON 生成分析文段（禁止脱离数据）：\n"
                    + json.dumps(payload, ensure_ascii=False, indent=2),
                },
            ],
        }
        response = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("云端 AI 返回为空。")
        message = choices[0].get("message") or {}
        content = str(message.get("content") or "").strip()
        if not content:
            raise RuntimeError("云端 AI 未返回文段。")
        return content

    def _generate(self, payload: Dict[str, Any], mode: str, config: Dict[str, Any]) -> Dict[str, Any]:
        mode_key = self._mode_key(mode)
        insufficient = self._is_insufficient(payload)
        cloud_enabled = bool(config.get("ai_enabled", False))
        text = ""
        source = "fallback"
        if cloud_enabled and not insufficient:
            try:
                text = self._cloud_generate(payload, mode_key, config)
                source = "cloud"
            except Exception:
                text = self.fallback_template(payload, mode_key)
                source = "fallback"
        else:
            text = self.fallback_template(payload, mode_key)
            source = "fallback"
        return {
            "mode": mode_key,
            "text": text,
            "source": source,
            "insufficient_data": insufficient,
            "version": "v1",
            "evidence_tracks": list(payload.get("evidence_tracks") or [])[:5],
            "trust_basis": "依据来自：趋势、Top歌手、证据歌曲、活跃时段",
        }

    def generate_friend_insight(self, payload: Dict[str, Any], mode: str, config: Dict[str, Any]) -> Dict[str, Any]:
        return self._generate(payload, mode, config)

    def generate_self_insight(self, payload: Dict[str, Any], mode: str, config: Dict[str, Any]) -> Dict[str, Any]:
        return self._generate(payload, mode, config)
