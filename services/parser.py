from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional


def _safe_load_content(raw_msg: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_msg, str):
        return None
    try:
        payload = json.loads(raw_msg)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _extract_sender_uid(message: Dict[str, Any]) -> str:
    from_user = message.get("fromUser") or {}
    candidates = [
        from_user.get("userId"),
        from_user.get("uid"),
        message.get("fromUserId"),
        message.get("from"),
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        sender_uid = str(candidate).strip()
        if sender_uid:
            return sender_uid
    return ""


def _extract_sender_name(message: Dict[str, Any]) -> str:
    from_user = message.get("fromUser") or {}
    for candidate in (
        from_user.get("nickname"),
        from_user.get("remarkName"),
        from_user.get("userName"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return "未知发送方"


def _extract_text_content(content: Dict[str, Any]) -> str:
    for key in ("msg", "text", "content"):
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_general_message_text(content: Dict[str, Any]) -> str:
    general_msg = content.get("generalMsg")
    candidates: List[Any] = [content.get("pushMsg"), content.get("msg"), content.get("title")]
    if isinstance(general_msg, dict):
        candidates.extend(
            [
                general_msg.get("inboxBriefContent"),
                general_msg.get("noticeMsg"),
                general_msg.get("title"),
                general_msg.get("subTitle"),
                general_msg.get("resName"),
            ]
        )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _extract_song_payload(content: Dict[str, Any]) -> Dict[str, str]:
    song = content.get("song") or {}
    artists = song.get("artists") or song.get("ar") or []
    artist_names = []
    if isinstance(artists, list):
        for item in artists:
            if isinstance(item, dict) and item.get("name"):
                artist_names.append(str(item["name"]).strip())
    return {
        "song_id": str(song.get("id") or "").strip(),
        "song_name": str(song.get("name") or "").strip(),
        "artist_name": "/".join(artist_names),
    }


def _extract_video_payload(content: Dict[str, Any]) -> Dict[str, str]:
    for container in (
        content.get("video"),
        content.get("videoInfo"),
        content.get("videoinfo"),
        content.get("mv"),
        content.get("mvInfo"),
        content.get("mvinfo"),
    ):
        if not isinstance(container, dict):
            continue
        title = next(
            (
                str(container.get(key)).strip()
                for key in ("title", "name", "desc", "description")
                if isinstance(container.get(key), str) and str(container.get(key)).strip()
            ),
            "",
        )
        url = next(
            (
                str(container.get(key)).strip()
                for key in ("playUrl", "videoUrl", "url", "originUrl", "downloadUrl")
                if isinstance(container.get(key), str) and str(container.get(key)).strip()
            ),
            "",
        )
        duration_ms = next(
            (
                int(container.get(key))
                for key in ("duration", "playTime", "durationMs")
                if isinstance(container.get(key), (int, float))
            ),
            0,
        )
        if title or url or duration_ms:
            parts = []
            if title:
                parts.append(title)
            if duration_ms:
                total_seconds = duration_ms // 1000 if duration_ms > 1000 else duration_ms
                minutes, seconds = divmod(total_seconds, 60)
                parts.append(f"{minutes:02d}:{seconds:02d}")
            if url:
                parts.append(url)
            return {"video_text": " | ".join(parts)}
    direct_url = content.get("playUrl") or content.get("videoUrl")
    if isinstance(direct_url, str) and direct_url.strip():
        return {"video_text": direct_url.strip()}
    return {"video_text": ""}


def _extract_image_payload(content: Dict[str, Any]) -> Dict[str, str]:
    preferred_keys = (
        "picUrl",
        "originUrl",
        "oriUrl",
        "originalUrl",
        "downloadUrl",
        "imageUrl",
        "imgUrl",
        "thumbUrl",
        "thumbnailUrl",
        "url",
    )
    for container in (
        content.get("picInfo"),
        content.get("picinfo"),
        content.get("imageInfo"),
        content.get("imageinfo"),
        content.get("imgInfo"),
        content.get("imginfo"),
        content.get("image"),
        content.get("img"),
        content.get("pic"),
    ):
        if not isinstance(container, dict):
            continue
        image_url = next(
            (
                str(container.get(key)).strip()
                for key in preferred_keys
                if isinstance(container.get(key), str) and str(container.get(key)).strip()
            ),
            "",
        )
        if not image_url:
            continue
        return {
            "image_url": image_url,
            "image_format": str(container.get("format") or "").strip().lower(),
        }
    return {"image_url": "", "image_format": ""}


def extract_image_preview_url(raw_msg: Any) -> str:
    content = _safe_load_content(raw_msg)
    if not content:
        return ""
    return _extract_image_payload(content).get("image_url", "")


def _is_structured_card_message(content: Dict[str, Any]) -> bool:
    return any(
        key in content
        for key in ("generalMsg", "resType", "invokeOperationMap", "bizChannel", "nativeUrl", "webUrl", "resId", "resName")
    )


def _is_image_message(content: Dict[str, Any]) -> bool:
    return not _is_structured_card_message(content) and bool(_extract_image_payload(content)["image_url"])


def _is_video_message(content: Dict[str, Any]) -> bool:
    if _extract_video_payload(content)["video_text"]:
        return True
    content_type = content.get("type")
    return isinstance(content_type, str) and content_type.strip().lower() == "video"


def parse_chat_messages(raw_msgs: List[Dict[str, Any]], uid: str) -> List[Dict[str, Any]]:
    chat_messages: List[Dict[str, Any]] = []
    for message in raw_msgs:
        if "msg" not in message or "time" not in message:
            continue
        msg_time_ms = int(message["time"])
        msg_id = str(message.get("id") or message.get("msgId") or f"{uid}_{msg_time_ms}")
        sender_uid = _extract_sender_uid(message)
        direction = "friend" if sender_uid and sender_uid == str(uid) else "self"
        msg_type = "unknown"
        text_content = ""
        song_id = ""
        song_name = ""
        artist_name = ""
        content = _safe_load_content(message["msg"])
        if content:
            if "song" in content:
                msg_type = "song"
                payload = _extract_song_payload(content)
                song_id = payload["song_id"]
                song_name = payload["song_name"]
                artist_name = payload["artist_name"]
                text_content = _extract_text_content(content)
            elif _is_video_message(content):
                msg_type = "video"
                text_content = _extract_video_payload(content)["video_text"]
            elif _is_image_message(content):
                msg_type = "image"
                text_content = _extract_image_payload(content)["image_format"]
            elif _is_structured_card_message(content):
                extracted_text = _extract_general_message_text(content)
                if extracted_text:
                    msg_type = "text"
                    text_content = extracted_text
            elif any(key in content for key in ("msg", "text", "content")):
                extracted_text = _extract_text_content(content)
                if extracted_text:
                    msg_type = "text"
                    text_content = extracted_text
        chat_messages.append(
            {
                "uid": uid,
                "msg_id": msg_id,
                "msg_time_ms": msg_time_ms,
                "msg_time_str": datetime.fromtimestamp(msg_time_ms / 1000).strftime("%Y-%m-%d %H:%M:%S"),
                "direction": direction,
                "sender_uid": sender_uid,
                "sender_name": _extract_sender_name(message),
                "msg_type": msg_type,
                "text_content": text_content,
                "song_id": song_id,
                "song_name": song_name,
                "artist_name": artist_name,
                "raw_msg_json": message["msg"],
            }
        )
    chat_messages.sort(key=lambda item: (item["msg_time_ms"], item["msg_id"]))
    return chat_messages


def parse_song_messages(raw_msgs: List[Dict[str, Any]], uid: str) -> List[Dict[str, Any]]:
    song_messages: List[Dict[str, Any]] = []
    for message in raw_msgs:
        if "msg" not in message or "time" not in message:
            continue
        content = _safe_load_content(message["msg"])
        if not content or "song" not in content:
            continue
        payload = _extract_song_payload(content)
        if not payload["song_id"] or not payload["song_name"]:
            continue
        msg_time_ms = int(message["time"])
        msg_id = str(message.get("id") or message.get("msgId") or f"{uid}_{msg_time_ms}_{payload['song_id']}")
        sender_uid = _extract_sender_uid(message)
        direction = "friend" if sender_uid and sender_uid == str(uid) else "self"
        song_messages.append(
            {
                "msg_id": msg_id,
                "uid": uid,
                "direction": direction,
                "sender_uid": sender_uid,
                "sender_name": _extract_sender_name(message),
                "song_id": payload["song_id"],
                "song_name": payload["song_name"],
                "artist_name": payload["artist_name"],
                "msg_time_ms": msg_time_ms,
                "msg_time_str": datetime.fromtimestamp(msg_time_ms / 1000).strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    song_messages.sort(key=lambda item: item["msg_time_ms"])
    return song_messages
