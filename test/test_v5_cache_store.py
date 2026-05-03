import shutil
import tempfile
import unittest

from services.storage import CacheStore


class CacheStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="v5-cache-")
        self.cache = CacheStore(self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_touch_recent_friend_keeps_pinned_friend_first(self) -> None:
        self.cache.touch_recent_friend("100", "甲")
        self.cache.pin_recent_friend("100")
        recent = self.cache.touch_recent_friend("200", "乙")
        self.assertEqual(recent[0]["uid"], "100")
        self.assertTrue(recent[0]["is_pinned"])
        self.assertEqual(recent[1]["uid"], "200")

    def test_delete_and_clear_recent_friends(self) -> None:
        self.cache.touch_recent_friend("100", "甲")
        self.cache.touch_recent_friend("200", "乙")
        recent = self.cache.delete_recent_friend("100")
        self.assertEqual([item["uid"] for item in recent], ["200"])
        cleared = self.cache.clear_recent_friends()
        self.assertEqual(cleared, [])

    def test_unpin_recent_friend_clears_pinned_status(self) -> None:
        self.cache.touch_recent_friend("100", "甲")
        self.cache.pin_recent_friend("100")
        recent = self.cache.unpin_recent_friend("100")
        self.assertEqual(recent[0]["uid"], "100")
        self.assertFalse(recent[0]["is_pinned"])


if __name__ == "__main__":
    unittest.main()
