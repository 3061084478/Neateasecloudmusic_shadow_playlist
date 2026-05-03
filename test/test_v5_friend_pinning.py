import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.app_controller import AppController
from core.models import FriendEntry


class FriendPinningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="v5-friend-pin-"))
        (self.temp_dir / "data" / "cache").mkdir(parents=True, exist_ok=True)
        (self.temp_dir / "data" / "archive").mkdir(parents=True, exist_ok=True)
        (self.temp_dir / "config.json").write_text(
            json.dumps(
                {
                    "api_base": "http://127.0.0.1:3000",
                    "cookie": "",
                    "request_timeout": 5,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_pin_from_all_friend_list_promotes_and_marks_friend(self) -> None:
        controller = AppController(workspace_root=str(self.temp_dir))
        target = FriendEntry(uid="100", nickname="甲", avatar_url="http://example.com/a.jpg")
        other = FriendEntry(uid="200", nickname="乙", avatar_url="http://example.com/b.jpg")
        controller.all_friends = [other, target]
        controller.session_state.current_friend = target
        controller.friend_sidebar_state.selected_friend_uid = target.uid
        controller.friend_sidebar_state.active_list_type = "all"

        controller.pin_friend(target.uid)

        self.assertTrue(controller.recent_friends)
        self.assertEqual(controller.recent_friends[0].uid, target.uid)
        self.assertTrue(controller.recent_friends[0].is_pinned)
        visible = controller.get_visible_friends()
        self.assertEqual(visible[0].uid, target.uid)
        self.assertTrue(visible[0].is_pinned)

    def test_unpin_clears_global_pinned_state(self) -> None:
        controller = AppController(workspace_root=str(self.temp_dir))
        target = FriendEntry(uid="100", nickname="甲", avatar_url="http://example.com/a.jpg")
        controller.all_friends = [target]
        controller.pin_friend("100")
        self.assertTrue(any(item.is_pinned for item in controller.recent_friends))
        controller.unpin_friend("100")
        self.assertFalse(any(item.is_pinned for item in controller.recent_friends))

    def test_current_friend_pinned_state_tracks_pin_toggle(self) -> None:
        controller = AppController(workspace_root=str(self.temp_dir))
        target = FriendEntry(uid="100", nickname="甲", avatar_url="http://example.com/a.jpg")
        controller.all_friends = [target]
        controller.session_state.current_friend = FriendEntry(
            uid=target.uid,
            nickname=target.nickname,
            avatar_url=target.avatar_url,
        )
        controller.friend_sidebar_state.selected_friend_uid = target.uid
        controller.friend_sidebar_state.active_list_type = "all"

        controller.pin_friend(target.uid)
        self.assertTrue(controller.current_friend())
        self.assertTrue(controller.current_friend().is_pinned)

        controller.unpin_friend(target.uid)
        self.assertFalse(controller.current_friend().is_pinned)


if __name__ == "__main__":
    unittest.main()
