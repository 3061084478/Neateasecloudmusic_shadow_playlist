import shutil
import tempfile
import unittest
from pathlib import Path

from services.chat_service import CHAT_ARCHIVE_CURSOR_SCOPE, ChatService
from services.config_store import ConfigStore
from services.playlist_service import SONG_ARCHIVE_CURSOR_SCOPE, PlaylistService
from services.storage import ChatArchiveRepository


class ArchiveCursorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="v5-archive-cursor-"))
        self.config_store = ConfigStore(workspace_root=str(self.temp_dir))
        self.repository = ChatArchiveRepository(self.config_store.archive_db_path)
        self.chat_service = ChatService(self.config_store)
        self.playlist_service = PlaylistService(self.config_store)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @staticmethod
    def _message(uid: str, msg_id: str, msg_time_ms: int, msg_time_str: str, msg_type: str) -> dict:
        return {
            "uid": uid,
            "msg_id": msg_id,
            "msg_time_ms": msg_time_ms,
            "msg_time_str": msg_time_str,
            "direction": "friend",
            "sender_uid": uid,
            "sender_name": "好友A",
            "msg_type": msg_type,
            "text_content": "" if msg_type == "song" else "hello",
            "song_id": f"song_{msg_id}" if msg_type == "song" else "",
            "song_name": f"歌曲{msg_id}" if msg_type == "song" else "",
            "artist_name": f"歌手{msg_id}" if msg_type == "song" else "",
            "raw_msg_json": "{}",
        }

    def test_consumption_state_only_advances(self) -> None:
        advanced = self.repository.advance_consumption_state(
            uid="1001",
            feature_scope=SONG_ARCHIVE_CURSOR_SCOPE,
            last_consumed_msg_id="m2",
            last_consumed_msg_time_ms=200,
            last_consumed_msg_time_str="2026-05-01 10:10:00",
        )
        self.assertTrue(advanced)

        advanced = self.repository.advance_consumption_state(
            uid="1001",
            feature_scope=SONG_ARCHIVE_CURSOR_SCOPE,
            last_consumed_msg_id="m1",
            last_consumed_msg_time_ms=100,
            last_consumed_msg_time_str="2026-05-01 10:00:00",
        )
        self.assertFalse(advanced)

        state = self.repository.get_consumption_state(uid="1001", feature_scope=SONG_ARCHIVE_CURSOR_SCOPE)
        self.assertEqual(state["last_consumed_msg_id"], "m2")
        self.assertEqual(int(state["last_consumed_msg_time_ms"]), 200)

    def test_archive_cursor_syncs_to_latest_archived_rows(self) -> None:
        uid = "2001"
        rows = [
            self._message(uid, "m1", 100, "2026-05-01 09:00:00", "song"),
            self._message(uid, "m2", 200, "2026-05-01 10:00:00", "text"),
            self._message(uid, "m3", 300, "2026-05-01 11:00:00", "song"),
        ]
        self.repository.upsert_messages(uid, rows)

        self.chat_service.sync_chat_archive_cursor_to_latest_archived(uid)
        self.playlist_service.sync_song_archive_cursor_to_latest_archived(uid)

        chat_state = self.repository.get_consumption_state(uid=uid, feature_scope=CHAT_ARCHIVE_CURSOR_SCOPE)
        song_state = self.repository.get_consumption_state(uid=uid, feature_scope=SONG_ARCHIVE_CURSOR_SCOPE)

        self.assertEqual(chat_state["last_consumed_msg_id"], "m3")
        self.assertEqual(song_state["last_consumed_msg_id"], "m3")

    def test_song_archive_cursor_does_not_retreat_on_older_results(self) -> None:
        uid = "3001"
        newer = [
            {
                "msg_id": "m3",
                "msg_time_ms": 300,
                "msg_time_str": "2026-05-01 11:00:00",
            }
        ]
        older = [
            {
                "msg_id": "m1",
                "msg_time_ms": 100,
                "msg_time_str": "2026-05-01 09:00:00",
            }
        ]

        self.playlist_service.advance_song_archive_cursor(uid, newer)
        self.playlist_service.advance_song_archive_cursor(uid, older)

        state = self.repository.get_consumption_state(uid=uid, feature_scope=SONG_ARCHIVE_CURSOR_SCOPE)
        self.assertEqual(state["last_consumed_msg_id"], "m3")
        self.assertEqual(int(state["last_consumed_msg_time_ms"]), 300)


if __name__ == "__main__":
    unittest.main()
