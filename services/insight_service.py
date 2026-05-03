from __future__ import annotations

import json
from typing import Any, Dict, List

import requests


class InsightService:
    _FORBIDDEN_PHRASES = (
        "总结下来",
        "综合收束",
        "最后看下来",
        "最打动人的地方",
        "它的核心特征是",
    )

    def __init__(self) -> None:
        pass

    @staticmethod
    def _mode_key(mode: str) -> str:
        normalized = (mode or "").strip().lower()
        if normalized in {"style", "summary", "风格", "风格版", "总结", "总结版"}:
            return "style"
        if normalized in {"commentary", "comment", "评论", "评论版"}:
            return "commentary"
        if normalized in {"annual", "year", "年度", "年度报告", "年度报告版"}:
            return "annual"
        return "rational"

    @staticmethod
    def _is_insufficient(payload: Dict[str, Any]) -> bool:
        return int(payload.get("total_songs") or 0) < 10 or int(payload.get("active_span_days") or 0) < 7

    @staticmethod
    def _top_names(items: List[Dict[str, Any]], limit: int = 3) -> str:
        names = [str(item.get("name") or "").strip() for item in items[:limit] if str(item.get("name") or "").strip()]
        return "、".join(names)

    @staticmethod
    def _percent_text(value: float) -> str:
        return f"{max(0.0, value) * 100:.1f}%"

    @staticmethod
    def _period_label_text(period_label: str) -> str:
        mapping = {
            "all": "全部历史",
            "year": "年度范围",
            "30d": "最近 30 天",
            "90d": "最近 90 天",
        }
        return mapping.get(str(period_label or "").strip().lower(), str(period_label or "当前周期"))

    @staticmethod
    def _pick_subject(payload: Dict[str, Any]) -> str:
        audience_scope = str(payload.get("audience_scope") or "").strip().lower()
        if audience_scope == "self":
            return str(payload.get("friend_name") or "你的音乐社交")
        if audience_scope == "annual":
            return "这一年你的音乐社交"
        return str(payload.get("friend_name") or "这段关系")

    @staticmethod
    def _stability_phrase(score: float) -> str:
        if score >= 0.72:
            return "偏好非常稳定，核心歌手反复出现"
        if score >= 0.52:
            return "偏好较稳定，同时保留少量变化"
        if score >= 0.32:
            return "偏好有重心，但切换频率也比较明显"
        return "偏好分散，更像持续试探不同方向"

    @staticmethod
    def _discovery_phrase(score: float) -> str:
        if score >= 0.72:
            return "探索倾向很强，新歌手和新曲目进入频率高"
        if score >= 0.52:
            return "既有稳定回访，也保持明显探索"
        if score >= 0.32:
            return "探索性适中，更多是在熟悉范围内微调"
        return "探索倾向偏弱，主要围绕熟悉内容循环"

    @staticmethod
    def _sentence_key(text: str) -> str:
        cleaned = str(text or "").strip().lower()
        for char in " \t\r\n，。！？；：、“”‘’\"'`()[]{}<>-_/\\|":
            cleaned = cleaned.replace(char, "")
        return cleaned

    @classmethod
    def _normalize_sentence(cls, text: str) -> str:
        sentence = " ".join(str(text or "").replace("\r", "\n").split()).strip()
        if not sentence:
            return ""
        for phrase in cls._FORBIDDEN_PHRASES:
            sentence = sentence.replace(f"{phrase}，", "")
            sentence = sentence.replace(f"{phrase}：", "")
            sentence = sentence.replace(phrase, "")
        sentence = sentence.strip(" ，；：")
        if not sentence:
            return ""
        if sentence[-1] not in "。！？!?":
            sentence += "。"
        return sentence

    @classmethod
    def _paragraph(cls, *sentences: str) -> str:
        parts: List[str] = []
        seen: set[str] = set()
        for sentence in sentences:
            normalized = cls._normalize_sentence(sentence)
            if not normalized:
                continue
            key = cls._sentence_key(normalized)
            if key and key in seen:
                continue
            seen.add(key)
            parts.append(normalized)
        return "".join(parts)

    @classmethod
    def _compose_text(cls, *paragraphs: str) -> str:
        blocks: List[str] = []
        seen: set[str] = set()
        for paragraph in paragraphs:
            block = str(paragraph or "").strip()
            if not block:
                continue
            key = cls._sentence_key(block)
            if key and key in seen:
                continue
            seen.add(key)
            blocks.append(block)
        return "\n\n".join(blocks)

    @classmethod
    def _clean_text(cls, text: str) -> str:
        cleaned = str(text or "").replace("\r\n", "\n").strip()
        for phrase in cls._FORBIDDEN_PHRASES:
            cleaned = cleaned.replace(f"{phrase}，", "")
            cleaned = cleaned.replace(f"{phrase}：", "")
            cleaned = cleaned.replace(phrase, "")
        paragraphs = [part.strip() for part in cleaned.split("\n\n") if part.strip()]
        unique: List[str] = []
        seen: set[str] = set()
        for paragraph in paragraphs:
            key = cls._sentence_key(paragraph)
            if key and key in seen:
                continue
            seen.add(key)
            unique.append(paragraph)
        return "\n\n".join(unique).strip()

    @staticmethod
    def _strip_lead_phrase(text: str, prefixes: tuple[str, ...]) -> str:
        cleaned = str(text or "").strip()
        for prefix in prefixes:
            if cleaned.startswith(prefix):
                return cleaned[len(prefix):].strip()
        return cleaned

    @staticmethod
    def _relation_wrap_up(label: str) -> str:
        mapping = {
            "高温关系": "一种持续升温、默契也越来越密的靠近方式",
            "稳定关系": "一种稳稳往前走、默契很清楚的相处节奏",
            "持续关系": "一种还在慢慢加深的来往状态",
            "低频关系": "一种还需要继续观察的轻联系",
        }
        return mapping.get(label, "一种还在慢慢加深的来往状态")

    @staticmethod
    def _self_wrap_up(tag: str) -> str:
        mapping = {
            "输入策展型": "一种会被关系网络不断带入、最后沉到你自己口味里的听歌气质",
            "输出驱动型": "一种明显带着你个人判断和主动表达的听歌气质",
            "核心圈层型": "一种重心很稳、会被少数重要关系慢慢塑出来的听歌气质",
            "社交均衡型": "一种输入输出都比较均衡、流动感很自然的社交气质",
        }
        return mapping.get(tag, "一种被关系网络慢慢带出来的听歌气质")

    @staticmethod
    def _relation_tone_pack(label: str) -> Dict[str, str]:
        mapping = {
            "高温关系": {
                "opening": "这段关系已经不是轻描淡写的交换，而是会留下明显余温的靠近。",
                "memory": "很多记忆点都不是偶发经过，而是会留下后续回响。",
                "closing": "很多回应都已经带着持续升温后的默契。",
            },
            "稳定关系": {
                "opening": "这段关系不是靠单次爆发撑起来的，而是一直在稳定推进。",
                "memory": "它的记忆点不会一下子冲出来，但回头看会很清楚。",
                "closing": "它不是忽冷忽热的来往，更像稳稳累起来的默契。",
            },
            "持续关系": {
                "opening": "这段关系还在缓慢推进，热度不算最高，但主线已经能看见。",
                "memory": "它的记忆点是一段一段累出来的，不算轰烈，但始终没断。",
                "closing": "它还没到最浓的时候，但来往已经慢慢有了分量。",
            },
            "低频关系": {
                "opening": "这段关系目前还偏克制，更多像偶尔被点亮的联系。",
                "memory": "它留下的记忆点还比较轻，暂时更适合观察而不是下重判断。",
                "closing": "眼下还是轻联系，判断宜轻一些。",
            },
        }
        return mapping.get(label, mapping["持续关系"])

    @staticmethod
    def _social_tone_pack(tag: str) -> Dict[str, str]:
        mapping = {
            "输入策展型": {
                "opening": "你的音乐社交更像一张不断被递进来的策展清单。",
                "portrait": "你擅长接住别人带来的声音，再把它们整理成自己的听觉主线。",
                "closing": "你更容易先被别人带进一段声音，再慢慢把它留成自己的口味。",
            },
            "输出驱动型": {
                "opening": "你的音乐社交带着很明显的主动发起感。",
                "portrait": "你不是在等别人先开口，而是更常自己先把歌和判断送出去。",
                "closing": "你的喜好不只是表达出来，也会反过来带动周围的人。",
            },
            "核心圈层型": {
                "opening": "你的音乐社交不是铺得很散，而是围着少数核心关系慢慢加深。",
                "portrait": "你会把分享密度和注意力压在更重要的人身上，所以纵深比铺开更明显。",
                "closing": "真正能改写你听歌感觉的，往往就是那几个重要的人。",
            },
            "社交均衡型": {
                "opening": "你的音乐社交整体节奏比较匀称，没有明显偏向单侧。",
                "portrait": "你既会接住别人递来的歌，也会把自己的判断自然送出去。",
                "closing": "你的社交并不偏向某一侧，更像自然来回的交换。",
            },
        }
        return mapping.get(tag, mapping["社交均衡型"])

    @staticmethod
    def _friend_rank_line(items: List[Dict[str, Any]], label: str) -> str:
        if not items:
            return ""
        top = items[0]
        name = str(top.get("name") or "暂无").strip()
        count = int(top.get("count") or 0)
        return f"{label}目前最突出的是 {name}（{count}）。"

    @staticmethod
    def _artist_overview_line(overview: Dict[str, Any]) -> str:
        shared = overview.get("shared_top_artists") or []
        mine = overview.get("my_top_artists") or []
        friends = overview.get("all_friends_top_artists") or []
        shared_text = "、".join(str(item.get("name") or "").strip() for item in shared[:2] if str(item.get("name") or "").strip())
        mine_text = "、".join(str(item.get("name") or "").strip() for item in mine[:2] if str(item.get("name") or "").strip())
        friend_text = "、".join(str(item.get("name") or "").strip() for item in friends[:2] if str(item.get("name") or "").strip())
        parts: List[str] = []
        if mine_text:
            parts.append(f"你主动分享时最常回到 {mine_text}")
        if friend_text:
            parts.append(f"好友们递给你的高频歌手则集中在 {friend_text}")
        if shared_text:
            parts.append(f"双方真正重叠下来的共同歌手是 {shared_text}")
        return "；".join(parts) if parts else ""

    @staticmethod
    def _network_balance_line(network_block: Dict[str, Any]) -> str:
        music_balance = network_block.get("music_balance") or {}
        music_concentration = network_block.get("music_concentration") or {}
        balance_label = str(music_balance.get("label") or "").strip()
        concentration_label = str(music_concentration.get("label") or "").strip()
        fragments: List[str] = []
        if balance_label:
            fragments.append(f"音乐交换结构更偏{balance_label}")
        if concentration_label:
            fragments.append(f"关系浓度呈现{concentration_label}")
        return "，".join(fragments)

    @staticmethod
    def _track_label(item: Dict[str, Any]) -> str:
        song_name = str(item.get("song_name") or "").strip()
        artist_name = str(item.get("artist_name") or "").strip()
        if song_name and artist_name:
            return f"《{song_name}》 / {artist_name}"
        if song_name:
            return f"《{song_name}》"
        if artist_name:
            return artist_name
        return ""

    def _common_world_line(self, payload: Dict[str, Any]) -> str:
        common_world = payload.get("common_world") or {}
        shared_artists = common_world.get("shared_artists") or common_world.get("shared_artist_names") or []
        shared_text = "、".join(str(name).strip() for name in shared_artists[:3] if str(name).strip())
        if shared_text:
            return f"共同歌手已经形成清晰交集，最明显的是 {shared_text}"
        return ""

    def _first_artist_line(self, payload: Dict[str, Any]) -> str:
        first_artist = str(payload.get("first_introduced_artist") or "").strip()
        if not first_artist or first_artist == "暂无":
            return ""
        scope = str(payload.get("audience_scope") or "").strip().lower()
        if scope == "self":
            return f"更早把你带进这张网络的名字里，{first_artist} 会很靠前"
        return f"这段关系更早留下来的带入歌手里，{first_artist} 很难绕开"

    def _burst_line(self, payload: Dict[str, Any]) -> str:
        detail = str((payload.get("silence_and_burst") or {}).get("detail") or "").strip()
        if not detail or "样本不足" in detail or "波动不大" in detail:
            return ""
        return detail

    def _personality_line(self, payload: Dict[str, Any]) -> str:
        cards = list(payload.get("personality_cards") or [])
        if not cards:
            return ""
        top = cards[0]
        tag = str(top.get("tag") or "").strip()
        reason = str(top.get("reason") or "").strip()
        if tag and reason:
            return f"整体气质上，你更像“{tag}”：{reason}"
        if tag:
            return f"整体气质上，你更像“{tag}”"
        return ""

    def _evidence_line(self, payload: Dict[str, Any]) -> str:
        evidence_tracks = list(payload.get("evidence_tracks") or [])
        if not evidence_tracks:
            return ""
        scope = str(payload.get("audience_scope") or "").strip().lower()
        labels: List[str] = []
        sources: List[str] = []
        for item in evidence_tracks[:2]:
            label = self._track_label(item)
            if not label:
                continue
            labels.append(label)
            for support in item.get("support_for") or []:
                support_text = str(support).strip()
                if support_text.startswith("来自 "):
                    source_name = support_text[3:].strip()
                    if source_name:
                        sources.append(source_name)
        if not labels:
            return ""
        label_text = "、".join(labels)
        primary_source = sources[0] if sources and len(set(sources)) == 1 else ""
        if scope == "self":
            if primary_source:
                return f"像 {label_text} 这样的歌，大概就能看出 {primary_source} 留下的那部分影响"
            return f"像 {label_text} 这样的歌，最能代表这张网络反复回来的口味"
        return f"像 {label_text} 这样的歌，就是这段关系里反复冒出来的那类声音"

    def _build_insufficient_fallback(self, payload: Dict[str, Any]) -> str:
        subject = self._pick_subject(payload)
        total_songs = int(payload.get("total_songs") or 0)
        total_msgs = int(payload.get("total_msgs") or 0)
        active_days = int(payload.get("active_span_days") or 0)
        artist_text = self._top_names(list(payload.get("top_artist_3") or []), limit=3) or "歌手偏好还没真正成形"
        evidence_line = self._evidence_line(payload)
        paragraph = self._paragraph(
            f"{subject} 当前样本还比较轻，只覆盖 {active_days} 个活跃日、{total_songs} 首歌曲和 {total_msgs} 条消息",
            f"先能看出来的，是高频歌手集中在 {artist_text}",
            evidence_line,
            "等样本再厚一点，再看趋势和关系判断会更稳",
        )
        return self._compose_text(paragraph)

    def _build_friend_rational_fallback(self, payload: Dict[str, Any]) -> str:
        subject = self._pick_subject(payload)
        period_text = self._period_label_text(str(payload.get("period_label") or ""))
        total_songs = int(payload.get("total_songs") or 0)
        total_msgs = int(payload.get("total_msgs") or 0)
        active_days = int(payload.get("active_span_days") or 0)
        artist_text = self._top_names(list(payload.get("top_artist_3") or []), limit=3) or "歌手偏好尚未形成"
        language_text = self._top_names(list(payload.get("language_distribution") or []), limit=2) or "语言偏好暂未显著"
        decade_text = self._top_names(list(payload.get("decade_distribution") or []), limit=2) or "年代偏好暂未显著"
        stability = float(payload.get("stability_score") or 0.0)
        discovery = float(payload.get("discovery_index") or 0.0)
        relation_temperature = payload.get("relation_temperature") or {}
        relation_label = str(relation_temperature.get("label") or "关系未定").strip()
        relation_score = int(relation_temperature.get("score") or 0)

        paragraph_a = self._paragraph(
            f"把 {subject} 当成一段关系看，它目前更接近“{relation_label}”（约 {relation_score} 分）",
            f"在{period_text}里，你们之间累计形成 {total_songs} 首歌曲分享、{total_msgs} 条消息互动，覆盖 {active_days} 个活跃日",
            f"这段关系最常回到的歌手先落在 {artist_text}",
            f"语言更偏 {language_text}，年代更靠近 {decade_text}",
            f"稳定度约 {self._percent_text(stability)}，说明它{self._stability_phrase(stability)}",
            f"探索度约 {self._percent_text(discovery)}，说明它{self._discovery_phrase(discovery)}",
        )
        paragraph_b = self._paragraph(
            str(payload.get("trend_conclusion") or ""),
            str(payload.get("activity_conclusion") or ""),
            self._burst_line(payload),
            self._common_world_line(payload),
            self._first_artist_line(payload),
            self._evidence_line(payload),
            f"顺着这些痕迹看下去，这段关系更像 {self._relation_wrap_up(relation_label)}",
        )
        return self._compose_text(paragraph_a, paragraph_b)

    def _build_self_rational_fallback(self, payload: Dict[str, Any]) -> str:
        subject = self._pick_subject(payload)
        period_text = self._period_label_text(str(payload.get("period_label") or ""))
        total_songs = int(payload.get("total_songs") or 0)
        total_msgs = int(payload.get("total_msgs") or 0)
        active_days = int(payload.get("active_span_days") or 0)
        artist_text = self._top_names(list(payload.get("top_artist_3") or []), limit=3) or "歌手偏好还没真正收拢"
        language_text = self._top_names(list(payload.get("language_distribution") or []), limit=2) or "语言分布暂未显著"
        decade_text = self._top_names(list(payload.get("decade_distribution") or []), limit=2) or "年代分布暂未显著"
        stability = float(payload.get("stability_score") or 0.0)
        discovery = float(payload.get("discovery_index") or 0.0)
        social_tag = str(payload.get("social_tag") or "社交均衡型").strip()
        core_friend = str(payload.get("core_friend_name") or "").strip()
        top_chat_line = self._friend_rank_line(list(payload.get("top_chat_friends") or []), "聊天互动")
        top_song_line = self._friend_rank_line(list(payload.get("top_song_friends") or []), "歌曲交换")
        top_temp_line = self._friend_rank_line(list(payload.get("top_temperature_friends") or []), "关系温度")
        artist_overview_line = self._artist_overview_line(dict(payload.get("artist_overview") or {}))
        network_line = self._network_balance_line(dict(payload.get("network_block") or {}))

        paragraph_a = self._paragraph(
            f"把 {subject} 当成你这一阶段的侧写看，在{period_text}里它累计覆盖 {total_songs} 首歌曲、{total_msgs} 条消息和 {active_days} 个活跃日",
            f"这一面的社交气质更接近“{social_tag}”",
            f"真正把你的听歌习惯慢慢拉出来的歌手主要是 {artist_text}",
            f"语言更偏 {language_text}，年代更靠近 {decade_text}",
            f"稳定度约 {self._percent_text(stability)}，说明你{self._stability_phrase(stability)}",
            f"探索度约 {self._percent_text(discovery)}，说明你{self._discovery_phrase(discovery)}",
        )
        paragraph_b = self._paragraph(
            f"如果只挑一个当前阶段最能代表你这面侧写的人，{core_friend} 会是最先被提到的名字" if core_friend else "",
            network_line,
            top_chat_line,
            top_song_line,
            top_temp_line,
            artist_overview_line,
            str(payload.get("trend_conclusion") or ""),
            self._first_artist_line(payload),
            self._evidence_line(payload),
            f"合起来看，你这一面的样子最后会变成 {self._self_wrap_up(social_tag)}",
        )
        return self._compose_text(paragraph_a, paragraph_b)

    def _build_rational_fallback(self, payload: Dict[str, Any]) -> str:
        scope = str(payload.get("audience_scope") or "").strip().lower()
        if scope == "self":
            return self._build_self_rational_fallback(payload)
        return self._build_friend_rational_fallback(payload)

    def _build_commentary_fallback(self, payload: Dict[str, Any]) -> str:
        subject = self._pick_subject(payload)
        total_songs = int(payload.get("total_songs") or 0)
        active_days = int(payload.get("active_span_days") or 0)
        artist_text = self._top_names(list(payload.get("top_artist_3") or []), limit=3) or "尚未固定的歌手方向"
        paragraph_a = self._paragraph(
            f"如果把 {subject} 写成一段乐评，它的主线会落在 {artist_text} 这些反复出现的名字上",
            f"{active_days} 个活跃日里一共投递了 {total_songs} 首歌",
            "这不是偶发分享，而是持续更新的个人栏目",
        )
        paragraph_b = self._paragraph(
            str(payload.get("trend_conclusion") or "节奏尚未完全定型"),
            str(payload.get("activity_conclusion") or ""),
            self._evidence_line(payload),
            "整体听感不是喧闹密集型关系，而是带着稳定母题、又偶尔拐向新方向的缓慢推进",
        )
        return self._compose_text(paragraph_a, paragraph_b)

    def _build_friend_style_fallback(self, payload: Dict[str, Any]) -> str:
        subject = self._pick_subject(payload)
        total_songs = int(payload.get("total_songs") or 0)
        active_days = int(payload.get("active_span_days") or 0)
        artist_text = self._top_names(list(payload.get("top_artist_3") or []), limit=3) or "尚未稳定的歌手偏好"
        relation_temperature = payload.get("relation_temperature") or {}
        relation_label = str(relation_temperature.get("label") or "关系未定").strip()
        tone = self._relation_tone_pack(relation_label)
        stability = float(payload.get("stability_score") or 0.0)
        discovery = float(payload.get("discovery_index") or 0.0)

        paragraph_a = self._paragraph(
            tone["opening"],
            f"如果把 {subject} 当成一段关系去看，它更像一条慢慢成形的私人音乐线",
            f"{active_days} 个活跃日里累积出的 {total_songs} 首歌，已经把样子慢慢带出来了",
            f"这里最稳定落下来的歌手是 {artist_text}",
            f"稳定度约 {self._percent_text(stability)}，说明它有明确母题",
            f"探索度约 {self._percent_text(discovery)}，也说明它不会只在一个方向里原地打转",
        )
        paragraph_b = self._paragraph(
            tone["memory"],
            self._burst_line(payload),
            str(payload.get("activity_conclusion") or ""),
            self._common_world_line(payload),
            self._first_artist_line(payload),
            self._evidence_line(payload),
            f"放回关系观察里看，它最后会落成 {self._relation_wrap_up(relation_label)}",
        )
        return self._compose_text(paragraph_a, paragraph_b)

    def _build_self_style_fallback(self, payload: Dict[str, Any]) -> str:
        subject = self._pick_subject(payload)
        social_tag = str(payload.get("social_tag") or "社交均衡型").strip()
        tone = self._social_tone_pack(social_tag)
        total_songs = int(payload.get("total_songs") or 0)
        total_msgs = int(payload.get("total_msgs") or 0)
        artist_text = self._top_names(list(payload.get("top_artist_3") or []), limit=3) or "还没完全定型的歌手偏好"
        core_friend = str(payload.get("core_friend_name") or "").strip()
        artist_overview_line = self._artist_overview_line(dict(payload.get("artist_overview") or {}))
        network_line = self._network_balance_line(dict(payload.get("network_block") or {}))

        paragraph_a = self._paragraph(
            tone["opening"],
            f"{subject} 不是一堆好友数据的机械相加，而是在 {total_songs} 首歌曲、{total_msgs} 条消息里慢慢显出性格的一面",
            f"真要给这一面下一个判断，它更接近“{social_tag}”",
            tone["portrait"],
            f"反复把这一面带出来的歌手主要是 {artist_text}",
        )
        paragraph_b = self._paragraph(
            f"{core_friend} 会是这一阶段最像主角的关系对象" if core_friend else "",
            f"{core_friend} 也是最容易改写你听歌重心的人" if core_friend else "",
            network_line,
            artist_overview_line,
            self._personality_line(payload),
            self._first_artist_line(payload),
            self._evidence_line(payload),
            f"落到你这个人身上看，它最后会变成 {self._self_wrap_up(social_tag)}",
        )
        return self._compose_text(paragraph_a, paragraph_b)

    def _build_style_fallback(self, payload: Dict[str, Any]) -> str:
        scope = str(payload.get("audience_scope") or "").strip().lower()
        if scope == "self":
            return self._build_self_style_fallback(payload)
        return self._build_friend_style_fallback(payload)

    def _build_annual_fallback(self, payload: Dict[str, Any]) -> str:
        annual = payload.get("annual_review") or {}
        year = str(annual.get("year") or "当年")
        song_count = int(annual.get("song_count") or payload.get("total_songs") or 0)
        message_count = int(annual.get("message_count") or payload.get("total_msgs") or 0)
        peak_month = str(annual.get("peak_month") or "-")
        top_song_friend = str(annual.get("top_song_friend_name") or "暂无")
        representative = str(annual.get("representative_relationship") or top_song_friend or "暂无")
        artist_text = self._top_names(list(payload.get("top_artist_3") or []), limit=3) or "歌手偏好尚未形成"
        night_ratio = float(payload.get("night_ratio") or 0.0)
        discovery = float(payload.get("discovery_index") or 0.0)
        paragraph_a = self._paragraph(
            f"{year} 年度音乐社交回顾：这一年你累计收到 {song_count} 首歌曲、产生 {message_count} 条互动消息，最高峰出现在 {peak_month}",
            f"如果只看年度代表关系，最醒目的对象是 {representative}",
            f"若只看分享密度，最突出的也是 {top_song_friend}",
        )
        paragraph_b = self._paragraph(
            f"全年高频歌手主要集中在 {artist_text}，夜间分享占比约 {self._percent_text(night_ratio)}",
            str(payload.get("trend_conclusion") or "整体节奏以稳定推进为主"),
            f"这一年既保留了熟悉偏好的回访，也留下了约 {self._percent_text(discovery)} 的探索空间",
        )
        return self._compose_text(paragraph_a, paragraph_b)

    def fallback_template(self, payload: Dict[str, Any], mode: str) -> str:
        mode_key = self._mode_key(mode)
        if self._is_insufficient(payload):
            return self._build_insufficient_fallback(payload)
        if mode_key == "annual":
            return self._build_annual_fallback(payload)
        if mode_key == "style":
            return self._build_style_fallback(payload)
        if mode_key == "commentary":
            return self._build_commentary_fallback(payload)
        return self._build_rational_fallback(payload)

    def _build_system_prompt(self, mode: str) -> str:
        mode_key = self._mode_key(mode)
        if mode_key == "annual":
            return (
                "你是年度音乐社交报告编辑。请输出一段年度回顾文案，"
                "语气克制、结论清晰，必须引用至少3个可验证指标，不得编造。"
            )
        if mode_key == "style":
            return (
                "你是音乐关系总结文案编辑。请把结构化数据整理成一段更像成品文案的中文总结，"
                "要求清楚、好懂、带一点延展感，但不能脱离输入事实，也不能空泛抒情。"
            )
        if mode_key == "commentary":
            return (
                "你是音乐评论编辑。请输出评论体中文文案，有文风但不浮夸，"
                "每段至少有一个数据锚点，不得脱离输入事实。"
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
            "temperature": 0.3,
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
        text = self._clean_text(text)
        return {
            "mode": mode_key,
            "text": text,
            "source": source,
            "insufficient_data": insufficient,
            "version": "v4",
            "evidence_tracks": list(payload.get("evidence_tracks") or [])[:5],
            "trust_basis": (
                "依据来自：总量指标、趋势结论、Top歌手、语言/年代分布、活跃时段与证据歌曲"
                if str(payload.get("audience_scope") or "").strip().lower() != "self"
                else "依据来自：总量指标、趋势结论、Top歌手、社交标签、核心好友、关系网络结构与证据歌曲"
            ),
        }

    def generate_friend_insight(self, payload: Dict[str, Any], mode: str, config: Dict[str, Any]) -> Dict[str, Any]:
        return self._generate(payload, mode, config)

    def generate_self_insight(self, payload: Dict[str, Any], mode: str, config: Dict[str, Any]) -> Dict[str, Any]:
        return self._generate(payload, mode, config)
