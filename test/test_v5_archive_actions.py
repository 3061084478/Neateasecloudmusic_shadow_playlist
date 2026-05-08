import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from core.app_controller import AppController
from core.models import FriendEntry


class ArchiveActionTests(unittest.TestCase):
    def test_global_archive_backfills_friend_without_backfill_status_even_if_cursors_exist(self) -> None:
        controller = AppController.__new__(AppController)
        controller.session_state = SimpleNamespace(mode="real")
        controller.friend_service = SimpleNamespace(
            get_all_mutual_friends=Mock(return_value=[FriendEntry(uid="1001", nickname="A")])
        )
        controller.chat_service = SimpleNamespace(
            repository=SimpleNamespace(
                get_backfill_status=Mock(return_value=None),
                get_latest_message=Mock(return_value={"msg_time_ms": 1710000000000}),
            ),
            sync_full_history_backfill=Mock(),
            sync_recent_history_delta=Mock(),
            sync_chat_archive_cursor_to_latest_archived=Mock(),
            get_chat_archive_cursor_ms=Mock(return_value=1710000000000),
        )
        controller.playlist_service = SimpleNamespace(
            get_song_archive_cursor_ms=Mock(return_value=1710000000000),
            sync_song_archive_cursor_to_latest_archived=Mock(),
        )
        controller.config_store = SimpleNamespace(update=Mock())
        controller._invalidate_relation_cache = Mock()
        controller.state_changed = SimpleNamespace(emit=Mock())

        result = controller.archive_all_friends_from_cursors()

        self.assertEqual(result["full_synced"], 1)
        self.assertEqual(result["delta_synced"], 0)
        controller.chat_service.sync_full_history_backfill.assert_called_once_with(uid="1001", limit=50)
        controller.chat_service.sync_recent_history_delta.assert_not_called()
        controller.chat_service.sync_chat_archive_cursor_to_latest_archived.assert_called_once_with("1001")
        controller.playlist_service.sync_song_archive_cursor_to_latest_archived.assert_called_once_with("1001")

    def test_global_archive_uses_delta_after_full_backfill_exists(self) -> None:
        controller = AppController.__new__(AppController)
        controller.session_state = SimpleNamespace(mode="real")
        controller.friend_service = SimpleNamespace(
            get_all_mutual_friends=Mock(return_value=[FriendEntry(uid="1002", nickname="B")])
        )
        controller.chat_service = SimpleNamespace(
            repository=SimpleNamespace(
                get_backfill_status=Mock(return_value={"status": "completed"}),
                get_latest_message=Mock(return_value={"msg_time_ms": 1710000000000}),
            ),
            sync_full_history_backfill=Mock(),
            sync_recent_history_delta=Mock(),
            sync_chat_archive_cursor_to_latest_archived=Mock(),
            get_chat_archive_cursor_ms=Mock(return_value=1710000001000),
        )
        controller.playlist_service = SimpleNamespace(
            get_song_archive_cursor_ms=Mock(return_value=1710000002000),
            sync_song_archive_cursor_to_latest_archived=Mock(),
        )
        controller.config_store = SimpleNamespace(update=Mock())
        controller._invalidate_relation_cache = Mock()
        controller.state_changed = SimpleNamespace(emit=Mock())

        result = controller.archive_all_friends_from_cursors(initial_pages=2, limit=40)

        self.assertEqual(result["full_synced"], 0)
        self.assertEqual(result["delta_synced"], 1)
        controller.chat_service.sync_full_history_backfill.assert_not_called()
        controller.chat_service.sync_recent_history_delta.assert_called_once_with(
            uid="1002",
            initial_pages=2,
            limit=40,
            stop_at_ms=1710000000000,
        )

    def test_global_archive_ignores_ahead_cursors_and_stops_at_latest_archived_time(self) -> None:
        controller = AppController.__new__(AppController)
        controller.session_state = SimpleNamespace(mode="real")
        controller.friend_service = SimpleNamespace(
            get_all_mutual_friends=Mock(return_value=[FriendEntry(uid="1003", nickname="C")])
        )
        controller.chat_service = SimpleNamespace(
            repository=SimpleNamespace(
                get_backfill_status=Mock(return_value={"status": "completed"}),
                get_latest_message=Mock(return_value={"msg_time_ms": 1710000000000}),
            ),
            sync_full_history_backfill=Mock(),
            sync_recent_history_delta=Mock(),
            sync_chat_archive_cursor_to_latest_archived=Mock(),
            get_chat_archive_cursor_ms=Mock(return_value=1711000000000),
        )
        controller.playlist_service = SimpleNamespace(
            get_song_archive_cursor_ms=Mock(return_value=1712000000000),
            sync_song_archive_cursor_to_latest_archived=Mock(),
        )
        controller.config_store = SimpleNamespace(update=Mock())
        controller._invalidate_relation_cache = Mock()
        controller.state_changed = SimpleNamespace(emit=Mock())

        controller.archive_all_friends_from_cursors(initial_pages=1, limit=50)

        controller.chat_service.sync_recent_history_delta.assert_called_once_with(
            uid="1003",
            initial_pages=1,
            limit=50,
            stop_at_ms=1710000000000,
        )


if __name__ == "__main__":
    unittest.main()
