from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from services.config_store import ConfigStore
from services.netease_api import NeteaseApiClient, NeteaseApiError
from services.parser import extract_image_preview_url, parse_chat_messages
from services.storage import ChatArchiveRepository

MESSAGE_WINDOW_SIZE = 30
LIVE_HISTORY_REQUEST_LIMIT = 50
CHAT_QUERY_FEATURE_SCOPE = "chat_query"
CHAT_ARCHIVE_CURSOR_SCOPE = "chat_archive_cursor"


class ChatService:
    def __init__(self, config_store: ConfigStore):
        self.config_store = config_store
        self.repository = ChatArchiveRepository(config_store.archive_db_path)

    def _client(self) -> NeteaseApiClient:
        return NeteaseApiClient(self.config_store.load())

    def _get_friend_name(self, uid: str) -> str:
        try:
            profile = self._client().get_user_detail(uid)
            nickname = str(profile.get("nickname") or "").strip()
            if nickname:
                return nickname
        except NeteaseApiError:
            pass
        cached_name = self.repository.get_latest_sender_name(uid=uid, direction="friend")
        return cached_name or f"好友{uid}"

    def _get_self_name(self) -> str:
        try:
            status = self._client().get_login_status()
            nickname = str(status.get("nickname") or "").strip()
            if nickname:
                return nickname
        except NeteaseApiError:
            pass
        return "我"

    def get_display_context(self, uid: str) -> Dict[str, str]:
        return {"friend_name": self._get_friend_name(uid), "self_name": self._get_self_name()}

    def get_archive_summary(self, uid: str) -> Dict[str, Any]:
        summary = self.repository.get_archive_range(uid)
        summary["active_dates"] = self.repository.list_active_dates(uid)
        summary["backfill_status"] = self.repository.get_backfill_status(uid)
        summary.update(self.get_display_context(uid))
        return summary

    def list_active_dates(
        self,
        uid: str,
        message_type: Optional[str] = None,
        scope: str = "all",
        pages: int = 3,
    ) -> List[str]:
        normalized_type = None if message_type in (None, "", "all") else message_type
        if scope == "all":
            return self.repository.list_active_dates(uid=uid, msg_type=normalized_type)
        if scope == "incremental":
            rows = self._get_incremental_messages_from_archive(uid=uid, message_type=normalized_type)
            return sorted({str(item.get("msg_time_str") or "")[:10] for item in rows if str(item.get("msg_time_str") or "")[:10]})
        window_limit = self._resolve_window_message_limit(pages)
        return self.repository.list_active_dates_in_window(
            uid=uid,
            limit=window_limit,
            msg_type=normalized_type,
        )

    @staticmethod
    def _resolve_window_message_limit(pages: int) -> int:
        if pages < 1:
            raise ValueError("消息窗口页数必须大于等于 1。")
        return pages * MESSAGE_WINDOW_SIZE

    def _get_archived_window_messages(self, uid: str, pages: int) -> List[Dict[str, Any]]:
        all_messages = self.repository.query_messages(uid=uid)
        if not all_messages:
            return []
        message_limit = self._resolve_window_message_limit(pages)
        return all_messages[-message_limit:]

    def _get_incremental_messages_from_archive(
        self,
        uid: str,
        message_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        consumption_state = self.repository.get_consumption_state(uid=uid, feature_scope=CHAT_QUERY_FEATURE_SCOPE)
        start_datetime = None
        start_time_ms = 0
        last_consumed_msg_id = ""
        if consumption_state:
            start_datetime = consumption_state.get("last_consumed_msg_time_str") or None
            start_time_ms = int(consumption_state.get("last_consumed_msg_time_ms") or 0)
            last_consumed_msg_id = str(consumption_state.get("last_consumed_msg_id") or "")
        rows = self.repository.query_messages(uid=uid, start_datetime=start_datetime, msg_type=message_type)
        result = []
        for item in rows:
            item_time_ms = int(item.get("msg_time_ms") or 0)
            item_msg_id = str(item.get("msg_id") or "")
            if item_time_ms < start_time_ms:
                continue
            if item_time_ms == start_time_ms and last_consumed_msg_id and item_msg_id <= last_consumed_msg_id:
                continue
            result.append(item)
        return result

    def _mark_messages_consumed(self, uid: str, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        latest_message = max(rows, key=lambda item: (int(item.get("msg_time_ms") or 0), str(item.get("msg_id") or "")))
        self.repository.advance_consumption_state(
            uid=uid,
            feature_scope=CHAT_QUERY_FEATURE_SCOPE,
            last_consumed_msg_id=str(latest_message.get("msg_id") or ""),
            last_consumed_msg_time_ms=int(latest_message.get("msg_time_ms") or 0),
            last_consumed_msg_time_str=str(latest_message.get("msg_time_str") or ""),
        )

    def advance_chat_archive_cursor(self, uid: str, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        latest_message = max(rows, key=lambda item: (int(item.get("msg_time_ms") or 0), str(item.get("msg_id") or "")))
        self.repository.advance_consumption_state(
            uid=uid,
            feature_scope=CHAT_ARCHIVE_CURSOR_SCOPE,
            last_consumed_msg_id=str(latest_message.get("msg_id") or ""),
            last_consumed_msg_time_ms=int(latest_message.get("msg_time_ms") or 0),
            last_consumed_msg_time_str=str(latest_message.get("msg_time_str") or ""),
        )

    def sync_chat_archive_cursor_to_latest_archived(self, uid: str) -> None:
        latest_message = self.repository.get_latest_message(uid=uid)
        if not latest_message:
            return
        self.repository.advance_consumption_state(
            uid=uid,
            feature_scope=CHAT_ARCHIVE_CURSOR_SCOPE,
            last_consumed_msg_id=str(latest_message.get("msg_id") or ""),
            last_consumed_msg_time_ms=int(latest_message.get("msg_time_ms") or 0),
            last_consumed_msg_time_str=str(latest_message.get("msg_time_str") or ""),
        )

    def get_chat_archive_cursor_ms(self, uid: str) -> int:
        state = self.repository.get_consumption_state(uid=uid, feature_scope=CHAT_ARCHIVE_CURSOR_SCOPE)
        return int((state or {}).get("last_consumed_msg_time_ms") or 0)

    def sync_friend_history_pages(self, uid: str, pages: int = 3, limit: int = 50) -> Dict[str, Any]:
        if pages < 1:
            raise ValueError("recent pages 必须大于等于 1。")

        request_limit = min(limit, LIVE_HISTORY_REQUEST_LIMIT) if limit > 0 else LIVE_HISTORY_REQUEST_LIMIT
        target_message_count = pages * MESSAGE_WINDOW_SIZE
        collected_message_count = 0
        fetched_pages = 0
        total_processed = 0
        total_inserted = 0
        total_skipped = 0
        before: Optional[int] = None
        previous_page_signature: Optional[Tuple[str, ...]] = None

        while collected_message_count < target_message_count:
            raw_messages = self._client().get_private_messages_for_archive(uid=uid, limit=request_limit, before=before)
            if not raw_messages:
                break

            page_signature = tuple(str(item.get("id") or item.get("msgId") or "") for item in raw_messages)
            if previous_page_signature is not None and page_signature == previous_page_signature:
                break
            previous_page_signature = page_signature

            parsed_messages = parse_chat_messages(raw_messages, uid=uid)
            write_result = self.repository.upsert_messages(uid=uid, messages=parsed_messages)

            fetched_pages += 1
            collected_message_count += len(raw_messages)
            total_processed += write_result["processed_count"]
            total_inserted += write_result["inserted_count"]
            total_skipped += write_result["skipped_count"]

            sorted_messages = sorted(raw_messages, key=lambda item: int(item.get("time", 0)))
            earliest_time_ms = int(sorted_messages[0].get("time", 0))
            next_before = max(0, earliest_time_ms - 1)
            if before is not None and next_before >= before:
                break
            before = next_before

        summary = self.get_archive_summary(uid)
        summary.update(
            {
                "processed_count": total_processed,
                "inserted_count": total_inserted,
                "skipped_count": total_skipped,
                "pages_fetched": fetched_pages,
                "available_range_notice": "当前页默认读取已同步到本地库的聊天记录。",
            }
        )
        return summary

    def sync_recent_history_delta(self, uid: str, initial_pages: int = 3, limit: int = 50, stop_at_ms: Optional[int] = None) -> Dict[str, Any]:
        archive_range_before = self.repository.get_archive_range(uid)
        previous_newest = archive_range_before.get("newest_archived_time")
        previous_newest_ms = None
        if previous_newest:
            previous_newest_ms = int(datetime.strptime(previous_newest, "%Y-%m-%d %H:%M:%S").timestamp() * 1000)
        if stop_at_ms is not None:
            previous_newest_ms = max(previous_newest_ms or 0, int(stop_at_ms or 0))

        request_limit = min(limit, LIVE_HISTORY_REQUEST_LIMIT) if limit > 0 else LIVE_HISTORY_REQUEST_LIMIT
        target_message_count = self._resolve_window_message_limit(initial_pages)
        collected_message_count = 0
        total_processed = 0
        total_inserted = 0
        total_skipped = 0
        fetched_pages = 0
        before: Optional[int] = None
        previous_page_signature: Optional[Tuple[str, ...]] = None

        while True:
            raw_messages = self._client().get_private_messages_for_archive(uid=uid, limit=request_limit, before=before)
            if not raw_messages:
                break
            page_signature = tuple(str(item.get("id") or item.get("msgId") or "") for item in raw_messages)
            if previous_page_signature is not None and page_signature == previous_page_signature:
                break
            previous_page_signature = page_signature
            parsed_messages = parse_chat_messages(raw_messages, uid=uid)
            write_result = self.repository.upsert_messages(uid=uid, messages=parsed_messages)
            fetched_pages += 1
            total_processed += write_result["processed_count"]
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

        summary = self.get_archive_summary(uid)
        summary.update(
            {
                "processed_count": total_processed,
                "inserted_count": total_inserted,
                "skipped_count": total_skipped,
                "pages_fetched": fetched_pages,
                "available_range_notice": "当前结果来自本地归档，可继续刷新获取最新增量。",
            }
        )
        return summary

    def sync_full_history_backfill(self, uid: str, limit: int = 50) -> Dict[str, Any]:
        request_limit = min(limit, LIVE_HISTORY_REQUEST_LIMIT) if limit > 0 else LIVE_HISTORY_REQUEST_LIMIT
        fetched_pages = 0
        total_processed = 0
        total_inserted = 0
        total_skipped = 0
        before: Optional[int] = None
        previous_page_signature: Optional[Tuple[str, ...]] = None

        while True:
            raw_messages = self._client().get_private_messages_for_archive(uid=uid, limit=request_limit, before=before)
            if not raw_messages:
                break

            page_signature = tuple(str(item.get("id") or item.get("msgId") or "") for item in raw_messages)
            if previous_page_signature is not None and page_signature == previous_page_signature:
                break
            previous_page_signature = page_signature

            parsed_messages = parse_chat_messages(raw_messages, uid=uid)
            write_result = self.repository.upsert_messages(uid=uid, messages=parsed_messages)
            fetched_pages += 1
            total_processed += write_result["processed_count"]
            total_inserted += write_result["inserted_count"]
            total_skipped += write_result["skipped_count"]

            sorted_messages = sorted(raw_messages, key=lambda item: int(item.get("time", 0)))
            earliest_time_ms = int(sorted_messages[0].get("time", 0))
            next_before = max(0, earliest_time_ms - 1)
            if before is not None and next_before >= before:
                break
            before = next_before

        archive_range = self.repository.get_archive_range(uid)
        self.repository.save_backfill_status(
            uid=uid,
            status="completed",
            pages_fetched=fetched_pages,
            fetched_count=total_processed,
            inserted_count=total_inserted,
            oldest_archived_time=archive_range.get("oldest_archived_time"),
            newest_archived_time=archive_range.get("newest_archived_time"),
        )
        summary = self.get_archive_summary(uid)
        summary.update(
            {
                "processed_count": total_processed,
                "inserted_count": total_inserted,
                "skipped_count": total_skipped,
                "pages_fetched": fetched_pages,
                "available_range_notice": "当前结果来自完整本地归档，后续会自动追加最新增量。",
            }
        )
        return summary

    @staticmethod
    def _normalize_direction(direction: Optional[str]) -> Optional[str]:
        if direction in (None, "", "all"):
            return None
        return direction

    def query_chat_history(
        self,
        uid: str,
        scope: str = "recent",
        pages: int = 3,
        sender_scope: str = "all",
        message_type: str = "all",
        query_mode: str = "all",
        target_date: Optional[str] = None,
        start_datetime: Optional[str] = None,
        end_datetime: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> Dict[str, Any]:
        if scope in {"recent", "pages"}:
            self.sync_friend_history_pages(uid=uid, pages=pages)
            base_rows = self._get_archived_window_messages(uid=uid, pages=pages)
        elif scope == "incremental":
            self.sync_recent_history_delta(uid=uid, initial_pages=max(3, pages))
            base_rows = self._get_incremental_messages_from_archive(uid=uid)
        elif scope == "all":
            if self.repository.get_backfill_status(uid) is None:
                self.sync_full_history_backfill(uid=uid, limit=LIVE_HISTORY_REQUEST_LIMIT)
            else:
                self.sync_recent_history_delta(uid=uid, initial_pages=max(3, pages))
            base_rows = self.repository.query_messages(uid=uid)
        else:
            raise ValueError("聊天记录范围只能是 all、recent 或 pages。")

        if query_mode == "date" and target_date:
            start_datetime = f"{target_date} 00:00:00"
            end_datetime = f"{target_date} 23:59:59"
        if query_mode == "range" and start_datetime and len(start_datetime) == 10:
            start_datetime = f"{start_datetime} 00:00:00"
        if query_mode == "range" and end_datetime and len(end_datetime) == 10:
            end_datetime = f"{end_datetime} 23:59:59"
        if query_mode == "keyword" and not keyword:
            raise ValueError("按关键词查询时，关键词不能为空。")

        direction = self._normalize_direction(sender_scope)
        rows = []
        for item in base_rows:
            if direction and item.get("direction") != direction:
                continue
            if message_type not in {"all", "", None} and item.get("msg_type") != message_type:
                continue
            msg_time = str(item.get("msg_time_str") or "")
            if start_datetime and msg_time < start_datetime:
                continue
            if end_datetime and msg_time > end_datetime:
                continue
            if keyword:
                haystack = " ".join(
                    [
                        str(item.get("text_content") or ""),
                        str(item.get("song_name") or ""),
                        str(item.get("artist_name") or ""),
                        str(item.get("sender_name") or ""),
                    ]
                ).lower()
                if keyword.strip().lower() not in haystack:
                    continue
            row = dict(item)
            if row.get("msg_type") == "image":
                row["image_url"] = extract_image_preview_url(row.get("raw_msg_json"))
            rows.append(row)

        self._mark_messages_consumed(uid, rows)
        self.advance_chat_archive_cursor(uid, rows)

        context = self.get_display_context(uid)
        return {
            "items": rows,
            "summary": {
                "count": len(rows),
                "friend_name": context["friend_name"],
                "self_name": context["self_name"],
                "scope": scope,
                "pages": pages,
                "query_mode": query_mode,
                "message_type": message_type,
                "sender_scope": sender_scope,
                "oldest_msg_time": rows[0]["msg_time_str"] if rows else None,
                "latest_msg_time": rows[-1]["msg_time_str"] if rows else None,
            },
        }
