from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Any, Dict, List, Optional


class CacheStore:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _read_json(self, filename: str) -> Optional[Dict[str, Any]]:
        path = os.path.join(self.base_dir, filename)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    def _write_json(self, filename: str, data: Dict[str, Any]) -> str:
        path = os.path.join(self.base_dir, filename)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        return path

    def save_song_messages(self, uid: str, song_messages: List[Dict[str, Any]]) -> str:
        return self._write_json(
            f"friend_{uid}_song_messages.json",
            {
                "uid": uid,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "count": len(song_messages),
                "song_messages": song_messages,
            },
        )

    def save_last_build(self, build_data: Dict[str, Any]) -> str:
        payload = dict(build_data)
        payload["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return self._write_json("shadow_playlist_last_build.json", payload)

    def read_last_build(self) -> Optional[Dict[str, Any]]:
        return self._read_json("shadow_playlist_last_build.json")

    def read_recent_friends(self) -> List[Dict[str, Any]]:
        payload = self._read_json("recent_friends.json")
        if not payload or not isinstance(payload.get("recent_friends"), list):
            return []
        normalized: List[Dict[str, Any]] = []
        for item in payload["recent_friends"]:
            if not isinstance(item, dict):
                continue
            uid = str(item.get("uid") or "").strip()
            if not uid:
                continue
            normalized.append(
                {
                    "uid": uid,
                    "friend_name": str(item.get("friend_name") or "").strip(),
                    "avatar_url": str(item.get("avatar_url") or "").strip(),
                    "last_used_at": str(item.get("last_used_at") or "").strip(),
                    "is_pinned": bool(item.get("is_pinned", False)),
                }
            )
        return normalized

    def save_recent_friends(self, recent_friends: List[Dict[str, Any]]) -> str:
        return self._write_json(
            "recent_friends.json",
            {
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "recent_friends": recent_friends,
            },
        )

    def touch_recent_friend(self, uid: str, friend_name: str, avatar_url: str = "", max_items: int = 12) -> List[Dict[str, Any]]:
        existing = self.read_recent_friends()
        target = next((item for item in existing if item["uid"] == uid), None)
        preserved = [item for item in existing if item["uid"] != uid]
        touched = {
            "uid": uid,
            "friend_name": friend_name,
            "avatar_url": avatar_url,
            "last_used_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "is_pinned": bool(target.get("is_pinned")) if target else False,
        }
        pinned = [item for item in preserved if item.get("is_pinned")]
        regular = [item for item in preserved if not item.get("is_pinned")]
        recent_friends = [touched] + regular if touched["is_pinned"] else pinned + [touched] + regular
        trimmed = recent_friends[:max_items]
        self.save_recent_friends(trimmed)
        return trimmed

    def delete_recent_friend(self, uid: str) -> List[Dict[str, Any]]:
        filtered = [item for item in self.read_recent_friends() if item.get("uid") != uid]
        self.save_recent_friends(filtered)
        return filtered

    def clear_recent_friends(self) -> List[Dict[str, Any]]:
        self.save_recent_friends([])
        return []

    def pin_recent_friend(self, uid: str) -> List[Dict[str, Any]]:
        recent_friends = self.read_recent_friends()
        target = next((item for item in recent_friends if item.get("uid") == uid), None)
        if not target:
            return recent_friends
        reordered = [{**target, "is_pinned": True}]
        for item in recent_friends:
            if item.get("uid") == uid:
                continue
            reordered.append({**item, "is_pinned": False})
        self.save_recent_friends(reordered)
        return reordered

    def unpin_recent_friend(self, uid: str) -> List[Dict[str, Any]]:
        recent_friends = self.read_recent_friends()
        if not any(item.get("uid") == uid for item in recent_friends):
            return recent_friends
        reordered = [{**item, "is_pinned": False} for item in recent_friends]
        self.save_recent_friends(reordered)
        return reordered


class ChatArchiveRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_parent_dir()
        self._initialize_schema()

    def _ensure_parent_dir(self) -> None:
        parent_dir = os.path.dirname(self.db_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    uid TEXT NOT NULL,
                    msg_id TEXT NOT NULL,
                    msg_time_ms INTEGER NOT NULL,
                    msg_time_str TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    sender_uid TEXT,
                    sender_name TEXT NOT NULL,
                    msg_type TEXT NOT NULL,
                    text_content TEXT NOT NULL DEFAULT '',
                    song_id TEXT NOT NULL DEFAULT '',
                    song_name TEXT NOT NULL DEFAULT '',
                    artist_name TEXT NOT NULL DEFAULT '',
                    raw_msg_json TEXT NOT NULL,
                    archived_at TEXT NOT NULL,
                    PRIMARY KEY (uid, msg_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS backfill_runs (
                    uid TEXT PRIMARY KEY,
                    last_backfill_at TEXT NOT NULL,
                    oldest_archived_time TEXT,
                    newest_archived_time TEXT,
                    pages_fetched INTEGER NOT NULL DEFAULT 0,
                    fetched_count INTEGER NOT NULL DEFAULT 0,
                    inserted_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS consumption_state (
                    uid TEXT NOT NULL,
                    feature_scope TEXT NOT NULL,
                    last_consumed_msg_id TEXT NOT NULL DEFAULT '',
                    last_consumed_msg_time_ms INTEGER NOT NULL DEFAULT 0,
                    last_consumed_msg_time_str TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (uid, feature_scope)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS feature_message_state (
                    uid TEXT NOT NULL,
                    feature_scope TEXT NOT NULL,
                    msg_id TEXT NOT NULL,
                    consumed_at TEXT NOT NULL,
                    PRIMARY KEY (uid, feature_scope, msg_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS song_genre_cache (
                    song_key TEXT PRIMARY KEY,
                    song_id TEXT NOT NULL DEFAULT '',
                    song_name TEXT NOT NULL DEFAULT '',
                    artist_name TEXT NOT NULL DEFAULT '',
                    canonical_genre TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT '',
                    raw_tags_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT '',
                    resolved_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_messages_uid_time ON messages(uid, msg_time_ms)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_messages_uid_type_time ON messages(uid, msg_type, msg_time_ms)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_feature_message_state_uid_scope ON feature_message_state(uid, feature_scope)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_song_genre_cache_song_id ON song_genre_cache(song_id)")
            connection.commit()

    def upsert_messages(self, uid: str, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not messages:
            return {
                "uid": uid,
                "processed_count": 0,
                "inserted_count": 0,
                "skipped_count": 0,
                "earliest_msg_time": None,
                "latest_msg_time": None,
            }
        archived_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        inserted_count = 0
        with closing(self._connect()) as connection:
            for item in messages:
                existing = connection.execute(
                    "SELECT 1 FROM messages WHERE uid = ? AND msg_id = ?",
                    (item["uid"], item["msg_id"]),
                ).fetchone()
                cursor = connection.execute(
                    """
                    INSERT INTO messages (
                        uid, msg_id, msg_time_ms, msg_time_str, direction, sender_uid, sender_name,
                        msg_type, text_content, song_id, song_name, artist_name, raw_msg_json, archived_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(uid, msg_id) DO UPDATE SET
                        msg_time_ms=excluded.msg_time_ms,
                        msg_time_str=excluded.msg_time_str,
                        direction=excluded.direction,
                        sender_uid=excluded.sender_uid,
                        sender_name=excluded.sender_name,
                        msg_type=excluded.msg_type,
                        text_content=excluded.text_content,
                        song_id=excluded.song_id,
                        song_name=excluded.song_name,
                        artist_name=excluded.artist_name,
                        raw_msg_json=excluded.raw_msg_json,
                        archived_at=excluded.archived_at
                    """,
                    (
                        item["uid"],
                        item["msg_id"],
                        item["msg_time_ms"],
                        item["msg_time_str"],
                        item["direction"],
                        item["sender_uid"],
                        item["sender_name"],
                        item["msg_type"],
                        item["text_content"],
                        item["song_id"],
                        item["song_name"],
                        item["artist_name"],
                        item["raw_msg_json"],
                        archived_at,
                    ),
                )
                if not existing and cursor.rowcount > 0:
                    inserted_count += 1
            connection.commit()
        sorted_messages = sorted(messages, key=lambda item: item["msg_time_ms"])
        return {
            "uid": uid,
            "processed_count": len(messages),
            "inserted_count": inserted_count,
            "skipped_count": len(messages) - inserted_count,
            "earliest_msg_time": sorted_messages[0]["msg_time_str"],
            "latest_msg_time": sorted_messages[-1]["msg_time_str"],
        }

    def save_backfill_status(
        self,
        uid: str,
        status: str,
        pages_fetched: int,
        fetched_count: int,
        inserted_count: int,
        oldest_archived_time: Optional[str],
        newest_archived_time: Optional[str],
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO backfill_runs (
                    uid, last_backfill_at, oldest_archived_time, newest_archived_time,
                    pages_fetched, fetched_count, inserted_count, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(uid) DO UPDATE SET
                    last_backfill_at=excluded.last_backfill_at,
                    oldest_archived_time=excluded.oldest_archived_time,
                    newest_archived_time=excluded.newest_archived_time,
                    pages_fetched=excluded.pages_fetched,
                    fetched_count=excluded.fetched_count,
                    inserted_count=excluded.inserted_count,
                    status=excluded.status
                """,
                (
                    uid,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    oldest_archived_time,
                    newest_archived_time,
                    pages_fetched,
                    fetched_count,
                    inserted_count,
                    status,
                ),
            )
            connection.commit()

    def get_backfill_status(self, uid: str) -> Optional[Dict[str, Any]]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT uid, last_backfill_at, oldest_archived_time, newest_archived_time,
                       pages_fetched, fetched_count, inserted_count, status
                FROM backfill_runs
                WHERE uid = ?
                """,
                (uid,),
            ).fetchone()
        return dict(row) if row else None

    def get_consumption_state(self, uid: str, feature_scope: str) -> Optional[Dict[str, Any]]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT uid, feature_scope, last_consumed_msg_id, last_consumed_msg_time_ms,
                       last_consumed_msg_time_str, updated_at
                FROM consumption_state
                WHERE uid = ? AND feature_scope = ?
                """,
                (uid, feature_scope),
            ).fetchone()
        return dict(row) if row else None

    def save_consumption_state(
        self,
        uid: str,
        feature_scope: str,
        last_consumed_msg_id: str,
        last_consumed_msg_time_ms: int,
        last_consumed_msg_time_str: str,
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO consumption_state (
                    uid, feature_scope, last_consumed_msg_id, last_consumed_msg_time_ms,
                    last_consumed_msg_time_str, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(uid, feature_scope) DO UPDATE SET
                    last_consumed_msg_id=excluded.last_consumed_msg_id,
                    last_consumed_msg_time_ms=excluded.last_consumed_msg_time_ms,
                    last_consumed_msg_time_str=excluded.last_consumed_msg_time_str,
                    updated_at=excluded.updated_at
                """,
                (
                    uid,
                    feature_scope,
                    last_consumed_msg_id,
                    last_consumed_msg_time_ms,
                    last_consumed_msg_time_str,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            connection.commit()

    def advance_consumption_state(
        self,
        uid: str,
        feature_scope: str,
        last_consumed_msg_id: str,
        last_consumed_msg_time_ms: int,
        last_consumed_msg_time_str: str,
    ) -> bool:
        current = self.get_consumption_state(uid=uid, feature_scope=feature_scope)
        current_time_ms = int((current or {}).get("last_consumed_msg_time_ms") or 0)
        current_msg_id = str((current or {}).get("last_consumed_msg_id") or "")
        next_time_ms = int(last_consumed_msg_time_ms or 0)
        next_msg_id = str(last_consumed_msg_id or "")
        if current and (next_time_ms, next_msg_id) <= (current_time_ms, current_msg_id):
            return False
        self.save_consumption_state(
            uid=uid,
            feature_scope=feature_scope,
            last_consumed_msg_id=next_msg_id,
            last_consumed_msg_time_ms=next_time_ms,
            last_consumed_msg_time_str=str(last_consumed_msg_time_str or ""),
        )
        return True

    def mark_messages_consumed(self, uid: str, feature_scope: str, msg_ids: List[str]) -> None:
        if not msg_ids:
            return
        consumed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with closing(self._connect()) as connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO feature_message_state (
                    uid, feature_scope, msg_id, consumed_at
                ) VALUES (?, ?, ?, ?)
                """,
                [(uid, feature_scope, msg_id, consumed_at) for msg_id in msg_ids],
            )
            connection.commit()

    def get_archive_range(self, uid: str) -> Dict[str, Optional[str]]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT MIN(msg_time_str) AS oldest_archived_time,
                       MAX(msg_time_str) AS newest_archived_time
                FROM messages
                WHERE uid = ?
                """,
                (uid,),
            ).fetchone()
        return {
            "oldest_archived_time": row["oldest_archived_time"] if row else None,
            "newest_archived_time": row["newest_archived_time"] if row else None,
        }

    def get_latest_message(self, uid: str, msg_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        query = """
            SELECT uid, msg_id, msg_time_ms, msg_time_str, direction, sender_uid, sender_name,
                   msg_type, text_content, song_id, song_name, artist_name, raw_msg_json, archived_at
            FROM messages
            WHERE uid = ?
        """
        params: List[Any] = [uid]
        if msg_type:
            query += " AND msg_type = ?"
            params.append(msg_type)
        query += " ORDER BY msg_time_ms DESC, msg_id DESC LIMIT 1"
        with closing(self._connect()) as connection:
            row = connection.execute(query, params).fetchone()
        return dict(row) if row else None

    def get_latest_sender_name(self, uid: str, direction: str) -> Optional[str]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT sender_name
                FROM messages
                WHERE uid = ? AND direction = ? AND sender_name <> ''
                ORDER BY msg_time_ms DESC, msg_id DESC
                LIMIT 1
                """,
                (uid, direction),
            ).fetchone()
        return row["sender_name"] if row else None

    def list_active_dates(self, uid: str, msg_type: Optional[str] = None) -> List[str]:
        query = """
            SELECT DISTINCT substr(msg_time_str, 1, 10) AS active_date
            FROM messages
            WHERE uid = ?
        """
        params: List[Any] = [uid]
        if msg_type:
            query += " AND msg_type = ?"
            params.append(msg_type)
        query += " ORDER BY active_date ASC"
        with closing(self._connect()) as connection:
            rows = connection.execute(query, params).fetchall()
        return [row["active_date"] for row in rows]

    def list_active_dates_in_window(self, uid: str, limit: int, msg_type: Optional[str] = None) -> List[str]:
        safe_limit = max(1, int(limit))
        query = """
            SELECT DISTINCT substr(msg_time_str, 1, 10) AS active_date
            FROM (
                SELECT msg_time_str, msg_type
                FROM messages
                WHERE uid = ?
                ORDER BY msg_time_ms DESC, msg_id DESC
                LIMIT ?
            ) AS recent_messages
        """
        params: List[Any] = [uid, safe_limit]
        if msg_type:
            query += " WHERE msg_type = ?"
            params.append(msg_type)
        query += " ORDER BY active_date ASC"
        with closing(self._connect()) as connection:
            rows = connection.execute(query, params).fetchall()
        return [row["active_date"] for row in rows]

    def query_messages(
        self,
        uid: str,
        start_datetime: Optional[str] = None,
        end_datetime: Optional[str] = None,
        direction: Optional[str] = None,
        msg_type: Optional[str] = None,
        keyword: Optional[str] = None,
        unread_feature_scope: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT uid, msg_id, msg_time_ms, msg_time_str, direction, sender_uid, sender_name,
                   msg_type, text_content, song_id, song_name, artist_name, raw_msg_json, archived_at
            FROM messages
            WHERE uid = ?
        """
        params: List[Any] = [uid]
        if start_datetime:
            query += " AND msg_time_str >= ?"
            params.append(start_datetime)
        if end_datetime:
            query += " AND msg_time_str <= ?"
            params.append(end_datetime)
        if direction:
            query += " AND direction = ?"
            params.append(direction)
        if msg_type:
            query += " AND msg_type = ?"
            params.append(msg_type)
        if unread_feature_scope:
            query += """
                AND NOT EXISTS (
                    SELECT 1
                    FROM feature_message_state
                    WHERE feature_message_state.uid = messages.uid
                      AND feature_message_state.msg_id = messages.msg_id
                      AND feature_message_state.feature_scope = ?
                )
            """
            params.append(unread_feature_scope)
        if keyword:
            like_value = f"%{keyword}%"
            query += """
                AND (
                    text_content LIKE ?
                    OR song_name LIKE ?
                    OR artist_name LIKE ?
                    OR sender_name LIKE ?
                )
            """
            params.extend([like_value, like_value, like_value, like_value])
        query += " ORDER BY msg_time_ms ASC, msg_id ASC"
        with closing(self._connect()) as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def build_song_cache_key(song_id: str = "", song_name: str = "", artist_name: str = "") -> str:
        normalized_song_id = str(song_id or "").strip()
        if normalized_song_id:
            return f"id::{normalized_song_id}"
        normalized_name = str(song_name or "").strip().lower()
        normalized_artist = str(artist_name or "").strip().lower()
        return f"meta::{normalized_name}::{normalized_artist}"

    def get_song_genre_cache(self, song_id: str = "", song_name: str = "", artist_name: str = "") -> Optional[Dict[str, Any]]:
        song_key = self.build_song_cache_key(song_id=song_id, song_name=song_name, artist_name=artist_name)
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT song_key, song_id, song_name, artist_name, canonical_genre,
                       confidence, source, raw_tags_json, status, resolved_at
                FROM song_genre_cache
                WHERE song_key = ?
                """,
                (song_key,),
            ).fetchone()
        if not row:
            return None
        payload = dict(row)
        try:
            payload["raw_tags"] = json.loads(str(payload.get("raw_tags_json") or "[]"))
        except json.JSONDecodeError:
            payload["raw_tags"] = []
        return payload

    def save_song_genre_cache(
        self,
        *,
        song_id: str,
        song_name: str,
        artist_name: str,
        canonical_genre: str,
        confidence: float,
        source: str,
        raw_tags: List[str],
        status: str,
    ) -> None:
        song_key = self.build_song_cache_key(song_id=song_id, song_name=song_name, artist_name=artist_name)
        resolved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO song_genre_cache (
                    song_key, song_id, song_name, artist_name, canonical_genre,
                    confidence, source, raw_tags_json, status, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(song_key) DO UPDATE SET
                    song_id=excluded.song_id,
                    song_name=excluded.song_name,
                    artist_name=excluded.artist_name,
                    canonical_genre=excluded.canonical_genre,
                    confidence=excluded.confidence,
                    source=excluded.source,
                    raw_tags_json=excluded.raw_tags_json,
                    status=excluded.status,
                    resolved_at=excluded.resolved_at
                """,
                (
                    song_key,
                    str(song_id or "").strip(),
                    str(song_name or "").strip(),
                    str(artist_name or "").strip(),
                    str(canonical_genre or "").strip(),
                    float(confidence or 0.0),
                    str(source or "").strip(),
                    json.dumps(list(raw_tags or []), ensure_ascii=False),
                    str(status or "").strip(),
                    resolved_at,
                ),
            )
            connection.commit()
