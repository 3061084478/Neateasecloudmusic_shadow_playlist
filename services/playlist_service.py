from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from services.config_store import ConfigStore
from services.netease_api import NeteaseApiClient, NeteaseApiError
from services.parser import parse_chat_messages, parse_song_messages
from services.sequence_builder import build_sequence
from services.storage import CacheStore, ChatArchiveRepository

MESSAGE_WINDOW_SIZE = 30
LIVE_HISTORY_REQUEST_LIMIT = 50
SONG_SHARE_FEATURE_SCOPE = "song_share"
PLAYLIST_GENERATION_FEATURE_SCOPE = "playlist_generation"
SONG_ARCHIVE_CURSOR_SCOPE = "song_archive_cursor"
DEFAULT_SHADOW_PLAYLIST_NAME = "网易云影子歌单"


class PlaylistManager:
    def __init__(self, api_client: NeteaseApiClient, config: Dict[str, Any]):
        self.api_client = api_client
        self.playlist_id = str(config.get("shadow_playlist_id") or "")
        self.sleep_seconds = float(config.get("sleep_seconds", 0.5))

    def get_playlist_state(self) -> List[Dict[str, str]]:
        songs = self.api_client.get_playlist_tracks(self.playlist_id)
        return [
            {
                "song_id": str(song.get("id") or ""),
                "song_name": str(song.get("name") or "").strip(),
                "artist_name": "/".join(
                    str(artist.get("name") or "").strip()
                    for artist in (song.get("ar") or song.get("artists") or [])
                    if isinstance(artist, dict) and artist.get("name")
                ),
            }
            for song in songs
            if song.get("id")
        ]

    def rename_playlist(self, name: str) -> None:
        data = self.api_client.update_playlist_name(self.playlist_id, name)
        if self.api_client.extract_status_code(data) != 200:
            raise NeteaseApiError(f"更新歌单名称失败，接口返回: {data}")

    def clear_playlist(self) -> int:
        current_tracks = self.get_playlist_state()
        existing_song_ids = [item["song_id"] for item in current_tracks if item["song_id"]]
        if not existing_song_ids:
            return 0
        data = self.api_client.remove_tracks_from_playlist(self.playlist_id, existing_song_ids)
        if self.api_client.extract_status_code(data) != 200:
            raise NeteaseApiError(f"清空歌单失败，接口返回: {data}")
        time.sleep(self.sleep_seconds)
        return len(existing_song_ids)

    def add_tracks(self, track_ids: List[str]) -> int:
        if not track_ids:
            return 0
        data = self.api_client.add_tracks_to_playlist(self.playlist_id, track_ids)
        if self.api_client.extract_status_code(data) != 200:
            raise NeteaseApiError(f"添加歌曲失败，接口返回: {data}")
        time.sleep(self.sleep_seconds)
        return len(track_ids)

    def rebuild_playlist(self, track_ids: List[str]) -> Dict[str, int]:
        cleared = self.clear_playlist()
        added = self.add_tracks(track_ids)
        return {"cleared_count": cleared, "added_count": added}


class PlaylistService:
    def __init__(self, config_store: ConfigStore):
        self.config_store = config_store
        self.cache_store = CacheStore(config_store.cache_dir)
        self.chat_repository = ChatArchiveRepository(config_store.archive_db_path)
        self._last_song_data_source = "unknown"

    def _load_config(self) -> Dict[str, Any]:
        return self.config_store.load()

    def _save_config(self, payload: Dict[str, Any]) -> None:
        self.config_store.save(payload)

    def _client(self) -> NeteaseApiClient:
        return NeteaseApiClient(self._load_config())

    def _playlist_manager(self) -> PlaylistManager:
        config = self._load_config()
        return PlaylistManager(self._client(), config)

    def _resolve_friend_name(self, uid: str) -> str:
        try:
            profile = self._client().get_user_detail(uid)
            nickname = str(profile.get("nickname") or "").strip()
            if nickname:
                return nickname
        except NeteaseApiError:
            pass
        return f"好友{uid}"

    def list_owned_playlists(self) -> List[Dict[str, Any]]:
        status = self._client().get_login_status()
        user_id = str(status.get("user_id") or "").strip()
        if not user_id:
            raise NeteaseApiError("未获取到当前登录账号 UID，无法读取歌单列表。")

        current_shadow_id = str(self._load_config().get("shadow_playlist_id") or "").strip()
        playlists = self._client().get_user_playlists(user_id)
        owned: List[Dict[str, Any]] = []
        for item in playlists:
            playlist_id = str(item.get("id") or "").strip()
            creator = item.get("creator") or {}
            creator_id = str(creator.get("userId") or "").strip()
            if not playlist_id or creator_id != user_id or playlist_id == current_shadow_id:
                continue
            owned.append(
                {
                    "playlist_id": playlist_id,
                    "name": str(item.get("name") or "").strip() or f"歌单 {playlist_id}",
                    "track_count": int(item.get("trackCount") or 0),
                    "is_private": bool(item.get("privacy") or item.get("ordered") == False),
                }
            )

        owned.sort(key=lambda item: item["name"].lower())
        return owned

    def _ensure_shadow_playlist_exists(self) -> None:
        config = self._load_config()
        playlist_id = str(config.get("shadow_playlist_id") or "").strip()
        if playlist_id:
            try:
                self._client().get_playlist_tracks(playlist_id)
                return
            except NeteaseApiError:
                pass
        created = self._client().create_playlist(DEFAULT_SHADOW_PLAYLIST_NAME, privacy=10)
        config.update(
            {
                "shadow_playlist_id": str(created["playlist_id"]),
                "shadow_playlist_strategy": "auto_create",
                "shadow_playlist_private": True,
                "shadow_playlist_name": DEFAULT_SHADOW_PLAYLIST_NAME,
                "shadow_playlist_last_set_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        self._save_config(config)

    def get_local_shadow_playlist_summary(self) -> Dict[str, Any]:
        config = self._load_config()
        playlist_id = str(config.get("shadow_playlist_id") or "").strip()
        strategy = str(config.get("shadow_playlist_strategy") or "use_existing")
        is_private = bool(config.get("shadow_playlist_private", False))
        last_set_at = str(config.get("shadow_playlist_last_set_at") or "")
        return {
            "playlist_id": playlist_id,
            "strategy": strategy,
            "is_private": is_private,
            "last_set_at": last_set_at,
            "name": str(config.get("shadow_playlist_name") or ""),
            "status_text": "已设置目标歌单" if playlist_id else "尚未设置目标歌单",
        }

    def get_shadow_playlist_summary(
        self,
        validate_remote: bool = True,
        ensure_exists: bool = False,
    ) -> Dict[str, Any]:
        if ensure_exists:
            self._ensure_shadow_playlist_exists()
        summary = self.get_local_shadow_playlist_summary()
        playlist_id = str(summary.get("playlist_id") or "").strip()
        if validate_remote and playlist_id:
            try:
                detail = self._client().get_playlist_detail(playlist_id)
                summary["name"] = detail["name"]
                summary["is_private"] = bool(detail.get("privacy"))
            except NeteaseApiError as exc:
                summary["status_text"] = f"歌单状态校验失败: {exc}"
        return summary

    def save_shadow_playlist_selection(
        self,
        strategy: str,
        manual_playlist_id: str = "",
        selected_playlist_id: str = "",
        new_playlist_name: str = "",
        is_private: bool = False,
    ) -> Dict[str, Any]:
        config = self._load_config()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if strategy == "use_existing":
            playlist_id = str(config.get("shadow_playlist_id") or "").strip()
            if not playlist_id:
                raise ValueError("当前没有已记录的目标歌单。")
            detail = self._client().get_playlist_detail(playlist_id)
            config.update(
                {
                    "shadow_playlist_strategy": strategy,
                    "shadow_playlist_name": detail["name"],
                    "shadow_playlist_private": bool(detail.get("privacy")),
                    "shadow_playlist_last_set_at": now,
                }
            )
        elif strategy == "manual_id":
            playlist_id = str(manual_playlist_id or "").strip()
            if not playlist_id:
                raise ValueError("手动指定歌单 ID 不能为空。")
            detail = self._client().get_playlist_detail(playlist_id)
            config.update(
                {
                    "shadow_playlist_id": detail["playlist_id"],
                    "shadow_playlist_strategy": strategy,
                    "shadow_playlist_name": detail["name"],
                    "shadow_playlist_private": bool(detail.get("privacy")),
                    "shadow_playlist_last_set_at": now,
                }
            )
        elif strategy == "select_owned":
            playlist_id = str(selected_playlist_id or "").strip()
            if not playlist_id:
                raise ValueError("请选择一个已有歌单。")
            detail = self._client().get_playlist_detail(playlist_id)
            config.update(
                {
                    "shadow_playlist_id": detail["playlist_id"],
                    "shadow_playlist_strategy": strategy,
                    "shadow_playlist_name": detail["name"],
                    "shadow_playlist_private": bool(detail.get("privacy")),
                    "shadow_playlist_last_set_at": now,
                }
            )
        elif strategy == "auto_create":
            playlist_name = str(new_playlist_name or DEFAULT_SHADOW_PLAYLIST_NAME).strip() or DEFAULT_SHADOW_PLAYLIST_NAME
            created = self._client().create_playlist(playlist_name, privacy=10 if is_private else 0)
            detail = self._client().get_playlist_detail(created["playlist_id"])
            config.update(
                {
                    "shadow_playlist_id": detail["playlist_id"],
                    "shadow_playlist_strategy": strategy,
                    "shadow_playlist_name": detail["name"],
                    "shadow_playlist_private": is_private,
                    "shadow_playlist_last_set_at": now,
                }
            )
        else:
            raise ValueError("未知的影子歌单策略。")
        self._save_config(config)
        return self.get_shadow_playlist_summary()

    @staticmethod
    def _resolve_window_message_limit(max_pages: int) -> int:
        if max_pages < 1:
            raise ValueError("消息窗口页数必须大于等于 1")
        return max_pages * MESSAGE_WINDOW_SIZE

    def _get_archived_window_messages(self, uid: str, max_pages: int) -> List[Dict[str, Any]]:
        rows = self.chat_repository.query_messages(uid=uid)
        if not rows:
            return []
        return rows[-self._resolve_window_message_limit(max_pages) :]

    def _has_archived_history(self, uid: str) -> bool:
        return bool(self.chat_repository.get_archive_range(uid).get("newest_archived_time"))

    def _has_complete_archived_history(self, uid: str) -> bool:
        return self.chat_repository.get_backfill_status(uid) is not None

    def _sync_recent_archive_delta(self, uid: str, max_pages: int, limit: int) -> Dict[str, Any]:
        archive_range_before = self.chat_repository.get_archive_range(uid)
        previous_newest = archive_range_before.get("newest_archived_time")
        previous_newest_ms = None
        if previous_newest:
            previous_newest_ms = int(datetime.strptime(previous_newest, "%Y-%m-%d %H:%M:%S").timestamp() * 1000)

        request_limit = min(limit, LIVE_HISTORY_REQUEST_LIMIT) if limit > 0 else LIVE_HISTORY_REQUEST_LIMIT
        target_message_count = self._resolve_window_message_limit(max_pages)
        collected_message_count = 0
        fetched_pages = 0
        total_inserted = 0
        total_skipped = 0
        before: Optional[int] = None
        previous_page_signature: Optional[List[str]] = None

        while True:
            raw_messages = self._client().get_private_messages_for_archive(uid=uid, limit=request_limit, before=before)
            if not raw_messages:
                break
            page_signature = [str(item.get("id") or item.get("msgId") or "") for item in raw_messages]
            if previous_page_signature is not None and page_signature == previous_page_signature:
                break
            previous_page_signature = page_signature
            parsed_messages = parse_chat_messages(raw_messages, uid=uid)
            write_result = self.chat_repository.upsert_messages(uid=uid, messages=parsed_messages)
            fetched_pages += 1
            total_inserted += write_result["inserted_count"]
            total_skipped += write_result["skipped_count"]
            collected_message_count += len(raw_messages)
            sorted_messages = sorted(raw_messages, key=lambda item: int(item.get("time", 0)))
            page_earliest_ms = int(sorted_messages[0].get("time", 0))
            if previous_newest_ms is not None and page_earliest_ms <= previous_newest_ms:
                break
            before = max(0, page_earliest_ms - 1)
            if previous_newest_ms is None and collected_message_count >= target_message_count:
                break

        archive_range_after = self.chat_repository.get_archive_range(uid)
        return {
            "previous_newest_archived_time": previous_newest,
            "newest_archived_time": archive_range_after.get("newest_archived_time"),
            "pages_fetched": fetched_pages,
            "inserted_count": total_inserted,
            "skipped_count": total_skipped,
        }

    def _song_messages_from_archive(self, uid: str, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
        rows = (
            self.chat_repository.query_messages(uid=uid, msg_type="song")
            if max_pages is None
            else [item for item in self._get_archived_window_messages(uid, max_pages) if item.get("msg_type") == "song"]
        )
        return [
            {
                "msg_id": item["msg_id"],
                "uid": item["uid"],
                "direction": item["direction"],
                "sender_uid": item["sender_uid"],
                "sender_name": item["sender_name"],
                "song_id": item["song_id"],
                "song_name": item["song_name"],
                "artist_name": item["artist_name"],
                "msg_time_ms": item["msg_time_ms"],
                "msg_time_str": item["msg_time_str"],
            }
            for item in rows
        ]

    def _get_incremental_song_messages_from_archive(self, uid: str, feature_scope: str) -> List[Dict[str, Any]]:
        consumption_state = self.chat_repository.get_consumption_state(uid=uid, feature_scope=feature_scope)
        start_datetime = None
        start_time_ms = 0
        last_consumed_msg_id = ""
        if consumption_state:
            start_datetime = consumption_state.get("last_consumed_msg_time_str") or None
            start_time_ms = int(consumption_state.get("last_consumed_msg_time_ms") or 0)
            last_consumed_msg_id = str(consumption_state.get("last_consumed_msg_id") or "")
        rows = self.chat_repository.query_messages(uid=uid, start_datetime=start_datetime, msg_type="song")
        result = []
        for item in rows:
            item_time_ms = int(item.get("msg_time_ms") or 0)
            item_msg_id = str(item.get("msg_id") or "")
            if item_time_ms < start_time_ms:
                continue
            if item_time_ms == start_time_ms and last_consumed_msg_id and item_msg_id <= last_consumed_msg_id:
                continue
            result.append(
                {
                    "msg_id": item["msg_id"],
                    "uid": item["uid"],
                    "direction": item["direction"],
                    "sender_uid": item["sender_uid"],
                    "sender_name": item["sender_name"],
                    "song_id": item["song_id"],
                    "song_name": item["song_name"],
                    "artist_name": item["artist_name"],
                    "msg_time_ms": item["msg_time_ms"],
                    "msg_time_str": item["msg_time_str"],
                }
            )
        result.sort(key=lambda item: (item["msg_time_ms"], item["msg_id"]))
        return result

    def _collect_live_song_messages(self, uid: str, limit: int, fetch_all: bool, max_pages: int) -> List[Dict[str, Any]]:
        raw_message_limit = None if fetch_all else self._resolve_window_message_limit(max_pages)
        request_limit = min(limit, LIVE_HISTORY_REQUEST_LIMIT) if limit > 0 else LIVE_HISTORY_REQUEST_LIMIT
        collected_raw_count = 0
        all_song_messages: List[Dict[str, Any]] = []
        seen_song_msg_ids: Set[str] = set()
        seen_raw_ids: Set[str] = set()
        before: Optional[int] = None
        previous_page_signature: Optional[List[str]] = None
        previous_earliest_time: Optional[int] = None

        while True:
            raw_messages = self._client().get_private_history(uid=uid, limit=request_limit, before=before)
            if not raw_messages:
                break
            page_signature = [str(item.get("id") or "") for item in raw_messages]
            if previous_page_signature is not None and page_signature == previous_page_signature:
                break
            previous_page_signature = page_signature

            fresh_raw_messages = []
            for item in raw_messages:
                raw_id = str(item.get("id") or item.get("msgId") or "")
                if raw_id and raw_id in seen_raw_ids:
                    continue
                if raw_id:
                    seen_raw_ids.add(raw_id)
                fresh_raw_messages.append(item)

            collected_raw_count += len(fresh_raw_messages)
            song_messages = parse_song_messages(fresh_raw_messages, uid)
            for item in song_messages:
                if item["msg_id"] in seen_song_msg_ids:
                    continue
                seen_song_msg_ids.add(item["msg_id"])
                all_song_messages.append(item)

            earliest_time_ms = min(int(item.get("time", 0)) for item in raw_messages if item.get("time") is not None)
            if previous_earliest_time is not None and earliest_time_ms >= previous_earliest_time:
                break
            previous_earliest_time = earliest_time_ms
            before = max(0, earliest_time_ms - 1)

            if raw_message_limit is not None and collected_raw_count >= raw_message_limit:
                break

        all_song_messages.sort(key=lambda item: item["msg_time_ms"])
        return all_song_messages

    @staticmethod
    def _to_day_start_ms(date_text: str) -> int:
        return int(datetime.strptime(date_text, "%Y-%m-%d").timestamp() * 1000)

    @staticmethod
    def _to_day_end_ms(date_text: str) -> int:
        return int(datetime.strptime(f"{date_text} 23:59:59", "%Y-%m-%d %H:%M:%S").timestamp() * 1000)

    def _filter_song_messages(
        self,
        song_messages: List[Dict[str, Any]],
        sender_scope: str = "all",
        keyword: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        keyword_text = (keyword or "").strip().lower()
        start_ms = self._to_day_start_ms(start_date) if start_date else None
        end_ms = self._to_day_end_ms(end_date) if end_date else None
        filtered = []
        for item in song_messages:
            if sender_scope != "all" and item.get("direction") != sender_scope:
                continue
            msg_time_ms = int(item.get("msg_time_ms") or 0)
            if start_ms is not None and msg_time_ms < start_ms:
                continue
            if end_ms is not None and msg_time_ms > end_ms:
                continue
            if keyword_text:
                haystack = " ".join(
                    [
                        str(item.get("song_name") or ""),
                        str(item.get("artist_name") or ""),
                        str(item.get("sender_name") or ""),
                    ]
                ).lower()
                if keyword_text not in haystack:
                    continue
            filtered.append(item)
        return filtered

    def summarize_song_messages(self, song_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not song_messages:
            return {"count": 0, "oldest_msg_time": None, "latest_msg_time": None}
        sorted_messages = sorted(song_messages, key=lambda item: int(item.get("msg_time_ms") or 0))
        return {
            "count": len(sorted_messages),
            "oldest_msg_time": sorted_messages[0]["msg_time_str"],
            "latest_msg_time": sorted_messages[-1]["msg_time_str"],
        }

    def list_friend_song_messages(
        self,
        uid: str,
        limit: Optional[int] = None,
        max_pages: int = 3,
        fetch_all: bool = False,
        scope: str = "pages",
        sender_scope: str = "all",
        keyword: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        incremental_feature_scope: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if limit is None:
            limit = int(self._load_config().get("default_limit", 200))
        if not fetch_all and max_pages < 1:
            raise ValueError("歌曲分享扫描页数必须大于等于 1")

        self._sync_recent_archive_delta(uid=uid, max_pages=max_pages, limit=limit)

        if scope == "recent":
            archived_song_messages = self._song_messages_from_archive(uid, max_pages=max_pages)
            self._last_song_data_source = "archive"
            filtered = self._filter_song_messages(archived_song_messages, sender_scope, keyword, start_date, end_date)
            self.cache_store.save_song_messages(uid, filtered)
            return filtered

        if scope == "incremental":
            archived_song_messages = self._get_incremental_song_messages_from_archive(
                uid=uid,
                feature_scope=incremental_feature_scope or SONG_SHARE_FEATURE_SCOPE,
            )
            self._last_song_data_source = "archive"
            filtered = self._filter_song_messages(archived_song_messages, sender_scope, keyword, start_date, end_date)
            self.cache_store.save_song_messages(uid, filtered)
            return filtered

        if self._has_archived_history(uid) and (not fetch_all or self._has_complete_archived_history(uid)):
            archived_song_messages = self._song_messages_from_archive(uid, None if fetch_all else max_pages)
            if archived_song_messages:
                self._last_song_data_source = "archive"
                filtered = self._filter_song_messages(archived_song_messages, sender_scope, keyword, start_date, end_date)
                self.cache_store.save_song_messages(uid, filtered)
                return filtered

        all_song_messages = self._collect_live_song_messages(uid=uid, limit=limit, fetch_all=fetch_all, max_pages=max_pages)
        self._last_song_data_source = "live"
        filtered = self._filter_song_messages(all_song_messages, sender_scope, keyword, start_date, end_date)
        self.cache_store.save_song_messages(uid, filtered)
        return filtered

    def get_last_song_data_source(self) -> str:
        return self._last_song_data_source

    def list_song_active_dates(self, uid: str, scope: str = "all", pages: int = 3) -> List[str]:
        if scope == "all":
            return self.chat_repository.list_active_dates(uid=uid, msg_type="song")
        if scope == "incremental":
            rows = self._get_incremental_song_messages_from_archive(uid=uid, feature_scope=PLAYLIST_GENERATION_FEATURE_SCOPE)
            return sorted({str(item.get("msg_time_str") or "")[:10] for item in rows if str(item.get("msg_time_str") or "")[:10]})
        window_limit = self._resolve_window_message_limit(pages)
        return self.chat_repository.list_active_dates_in_window(
            uid=uid,
            limit=window_limit,
            msg_type="song",
        )

    def mark_song_messages_consumed(self, uid: str, feature_scope: str, song_messages: List[Dict[str, Any]]) -> None:
        if not song_messages:
            return
        latest_message = max(song_messages, key=lambda item: (int(item.get("msg_time_ms") or 0), str(item.get("msg_id") or "")))
        self.chat_repository.advance_consumption_state(
            uid=uid,
            feature_scope=feature_scope,
            last_consumed_msg_id=str(latest_message.get("msg_id") or ""),
            last_consumed_msg_time_ms=int(latest_message.get("msg_time_ms") or 0),
            last_consumed_msg_time_str=str(latest_message.get("msg_time_str") or ""),
        )

    def advance_song_archive_cursor(self, uid: str, song_messages: List[Dict[str, Any]]) -> None:
        if not song_messages:
            return
        latest_message = max(song_messages, key=lambda item: (int(item.get("msg_time_ms") or 0), str(item.get("msg_id") or "")))
        self.chat_repository.advance_consumption_state(
            uid=uid,
            feature_scope=SONG_ARCHIVE_CURSOR_SCOPE,
            last_consumed_msg_id=str(latest_message.get("msg_id") or ""),
            last_consumed_msg_time_ms=int(latest_message.get("msg_time_ms") or 0),
            last_consumed_msg_time_str=str(latest_message.get("msg_time_str") or ""),
        )

    def sync_song_archive_cursor_to_latest_archived(self, uid: str) -> None:
        latest_message = self.chat_repository.get_latest_message(uid=uid, msg_type="song")
        if not latest_message:
            return
        self.chat_repository.advance_consumption_state(
            uid=uid,
            feature_scope=SONG_ARCHIVE_CURSOR_SCOPE,
            last_consumed_msg_id=str(latest_message.get("msg_id") or ""),
            last_consumed_msg_time_ms=int(latest_message.get("msg_time_ms") or 0),
            last_consumed_msg_time_str=str(latest_message.get("msg_time_str") or ""),
        )

    def get_song_archive_cursor_ms(self, uid: str) -> int:
        state = self.chat_repository.get_consumption_state(uid=uid, feature_scope=SONG_ARCHIVE_CURSOR_SCOPE)
        return int((state or {}).get("last_consumed_msg_time_ms") or 0)

    def query_song_shares(
        self,
        uid: str,
        scope: str = "recent",
        pages: int = 3,
        sender_scope: str = "all",
        query_mode: str = "all",
        target_date: str = "",
        start_date: str = "",
        end_date: str = "",
        keyword: str = "",
    ) -> Dict[str, Any]:
        fetch_all = scope == "all"
        normalized_scope = "pages" if scope in {"pages", "all"} else scope
        if query_mode == "date" and target_date:
            start_date = target_date
            end_date = target_date
        if query_mode == "keyword" and not keyword.strip():
            raise ValueError("按关键词查询时，关键词不能为空。")
        items = self.list_friend_song_messages(
            uid=uid,
            max_pages=pages,
            fetch_all=fetch_all,
            scope=normalized_scope,
            sender_scope=sender_scope,
            keyword=keyword if query_mode == "keyword" else keyword,
            start_date=start_date if query_mode in {"date", "range"} else None,
            end_date=end_date if query_mode in {"date", "range"} else None,
            incremental_feature_scope=PLAYLIST_GENERATION_FEATURE_SCOPE,
        )
        self.advance_song_archive_cursor(uid=uid, song_messages=items)
        return {
            "items": items,
            "summary": {
                **self.summarize_song_messages(items),
                "data_source": self.get_last_song_data_source(),
                "scope": scope,
                "pages": pages,
                "query_mode": query_mode,
                "sender_scope": sender_scope,
            },
        }

    def get_playlist_state(self) -> List[Dict[str, Any]]:
        self._ensure_shadow_playlist_exists()
        return self._playlist_manager().get_playlist_state()

    @staticmethod
    def _resolve_generation_sequence(
        song_messages: List[Dict[str, Any]],
        anchor_index: int,
        max_gap_hours: Optional[int],
        max_songs: Optional[int],
        apply_sequence_rules: bool,
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]], int, str]:
        if not song_messages:
            raise ValueError("没有解析到歌曲分享消息")
        if anchor_index < 0 or anchor_index >= len(song_messages):
            raise ValueError("起点编号越界")

        if apply_sequence_rules:
            return build_sequence(
                song_messages=song_messages,
                anchor_index=anchor_index,
                max_gap_hours=max_gap_hours,
                max_songs=max_songs,
            )

        anchor = song_messages[anchor_index]
        sequence = [item for item in song_messages[anchor_index:] if item.get("uid") == anchor.get("uid")]
        return anchor, sequence, 0, ""

    def generate_shadow_playlist(
        self,
        uid: str,
        anchor_index: int,
        max_gap_hours: Optional[int] = None,
        max_songs: Optional[int] = None,
        limit: Optional[int] = None,
        song_scan_pages: int = 3,
        fetch_all_song_history: bool = False,
        song_messages: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        self._ensure_shadow_playlist_exists()
        provided_song_messages = song_messages is not None
        if song_messages is None:
            song_messages = self.list_friend_song_messages(
                uid=uid,
                limit=limit,
                max_pages=song_scan_pages,
                fetch_all=fetch_all_song_history,
                scope="all" if fetch_all_song_history else "pages",
                incremental_feature_scope=PLAYLIST_GENERATION_FEATURE_SCOPE,
            )
        apply_sequence_rules = (not provided_song_messages) or max_gap_hours is not None or max_songs is not None

        friend_name = self._resolve_friend_name(uid)
        playlist_name = f"{friend_name}的私信分享"
        anchor, sequence, skipped_duplicates, stop_reason = self._resolve_generation_sequence(
            song_messages=song_messages,
            anchor_index=anchor_index,
            max_gap_hours=max_gap_hours,
            max_songs=max_songs,
            apply_sequence_rules=apply_sequence_rules,
        )

        playlist_manager = self._playlist_manager()
        rename_error = None
        try:
            playlist_manager.rename_playlist(playlist_name)
        except NeteaseApiError as exc:
            rename_error = str(exc)

        rebuild_result = playlist_manager.rebuild_playlist([item["song_id"] for item in sequence])
        final_payload = {
            "uid": uid,
            "friend_name": friend_name,
            "playlist_name": playlist_name,
            "playlist_rename_error": rename_error,
            "song_scan_pages": song_scan_pages,
            "fetch_all_song_history": fetch_all_song_history,
            "anchor_index": anchor_index,
            "anchor_song_name": anchor["song_name"],
            "anchor_song_id": anchor["song_id"],
            "anchor_msg_id": anchor["msg_id"],
            "anchor_time": anchor["msg_time_str"],
            "max_gap_hours": max_gap_hours,
            "max_songs": max_songs,
            "generated_count": len(sequence),
            "skipped_duplicates": skipped_duplicates,
            "stop_reason": stop_reason,
            "rebuild_result": rebuild_result,
            "songs": [
                {
                    "song_id": item["song_id"],
                    "song_name": item["song_name"],
                    "artist_name": item["artist_name"],
                    "msg_id": item["msg_id"],
                    "msg_time": item["msg_time_str"],
                }
                for item in sequence
            ],
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.cache_store.save_last_build(final_payload)
        self.mark_song_messages_consumed(uid=uid, feature_scope=PLAYLIST_GENERATION_FEATURE_SCOPE, song_messages=sequence)
        self.advance_song_archive_cursor(uid=uid, song_messages=sequence)
        return final_payload

    def get_last_build_record(self) -> Optional[Dict[str, Any]]:
        return self.cache_store.read_last_build()
