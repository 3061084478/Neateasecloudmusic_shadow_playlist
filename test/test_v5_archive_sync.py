import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.app_controller import AppController
from core.models import FriendEntry


class ArchiveSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="v5-archive-sync-"))
        (self.temp_dir / "data" / "cache").mkdir(parents=True, exist_ok=True)
        (self.temp_dir / "data" / "archive").mkdir(parents=True, exist_ok=True)
        (self.temp_dir / "config.json").write_text(
            json.dumps(
                {
                    "api_base": "http://127.0.0.1:3000",
                    "cookie": "cookie=1",
                    "request_timeout": 5,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_archive_all_friends_from_cursors_uses_one_page_probe_by_default(self) -> None:
        controller = AppController(workspace_root=str(self.temp_dir))
        controller.session_state.mode = "real"
        friend = FriendEntry(uid="100", nickname="甲", avatar_url="")
        controller.friend_service.get_all_mutual_friends = lambda force_refresh=True: [friend]  # type: ignore[assignment]
        controller.chat_service.repository.get_latest_message = lambda uid: {"msg_time_ms": 1000}  # type: ignore[assignment]
        controller.chat_service.get_chat_archive_cursor_ms = lambda uid: 1000  # type: ignore[assignment]
        controller.playlist_service.get_song_archive_cursor_ms = lambda uid: 1000  # type: ignore[assignment]

        calls: list[dict] = []

        def fake_sync_recent_history_delta(uid: str, initial_pages: int = 3, limit: int = 50, stop_at_ms: int | None = None):
            calls.append(
                {
                    "uid": uid,
                    "initial_pages": initial_pages,
                    "limit": limit,
                    "stop_at_ms": stop_at_ms,
                }
            )
            return {}

        controller.chat_service.sync_recent_history_delta = fake_sync_recent_history_delta  # type: ignore[assignment]
        controller.chat_service.sync_chat_archive_cursor_to_latest_archived = lambda uid: None  # type: ignore[assignment]
        controller.playlist_service.sync_song_archive_cursor_to_latest_archived = lambda uid: None  # type: ignore[assignment]

        result = controller.archive_all_friends_from_cursors()

        self.assertEqual(result["delta_synced"], 1)
        self.assertFalse(result["failed"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["initial_pages"], 1)


if __name__ == "__main__":
    unittest.main()
