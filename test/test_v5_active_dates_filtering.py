import os
import shutil
import tempfile
import unittest
from datetime import datetime

from services.storage import ChatArchiveRepository


class ActiveDatesFilteringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="v5-active-dates-")
        self.db_path = os.path.join(self.temp_dir, "archive.db")
        self.repository = ChatArchiveRepository(self.db_path)
        self.uid = "10001"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @staticmethod
    def _to_ms(text: str) -> int:
        return int(datetime.strptime(text, "%Y-%m-%d %H:%M:%S").timestamp() * 1000)

    def _message(self, msg_id: str, msg_type: str, msg_time: str) -> dict:
        return {
            "uid": self.uid,
            "msg_id": msg_id,
            "msg_time_ms": self._to_ms(msg_time),
            "msg_time_str": msg_time,
            "direction": "friend",
            "sender_uid": self.uid,
            "sender_name": "好友",
            "msg_type": msg_type,
            "text_content": "",
            "song_id": "1" if msg_type == "song" else "",
            "song_name": "测试歌曲" if msg_type == "song" else "",
            "artist_name": "测试歌手" if msg_type == "song" else "",
            "raw_msg_json": "{}",
        }

    def test_list_active_dates_can_filter_by_msg_type(self) -> None:
        self.repository.upsert_messages(
            uid=self.uid,
            messages=[
                self._message("m1", "song", "2026-04-10 10:00:00"),
                self._message("m2", "text", "2026-04-11 12:00:00"),
                self._message("m3", "song", "2026-04-11 21:00:00"),
                self._message("m4", "text", "2026-04-12 09:00:00"),
            ],
        )

        self.assertEqual(
            self.repository.list_active_dates(self.uid),
            ["2026-04-10", "2026-04-11", "2026-04-12"],
        )
        self.assertEqual(
            self.repository.list_active_dates(self.uid, msg_type="song"),
            ["2026-04-10", "2026-04-11"],
        )
        self.assertEqual(
            self.repository.list_active_dates(self.uid, msg_type="text"),
            ["2026-04-11", "2026-04-12"],
        )

    def test_list_active_dates_in_window_respects_recent_limit(self) -> None:
        self.repository.upsert_messages(
            uid=self.uid,
            messages=[
                self._message("m1", "song", "2026-04-01 09:00:00"),
                self._message("m2", "text", "2026-04-02 10:00:00"),
                self._message("m3", "song", "2026-04-03 11:00:00"),
                self._message("m4", "text", "2026-04-04 12:00:00"),
                self._message("m5", "song", "2026-04-05 13:00:00"),
            ],
        )
        self.assertEqual(
            self.repository.list_active_dates_in_window(self.uid, limit=2),
            ["2026-04-04", "2026-04-05"],
        )
        self.assertEqual(
            self.repository.list_active_dates_in_window(self.uid, limit=3, msg_type="song"),
            ["2026-04-03", "2026-04-05"],
        )


if __name__ == "__main__":
    unittest.main()
