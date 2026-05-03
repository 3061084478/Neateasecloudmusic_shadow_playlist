import unittest

from services.sequence_builder import build_sequence


class SequenceBuilderTests(unittest.TestCase):
    def test_build_sequence_skips_duplicates(self) -> None:
        anchor, songs, skipped, reason = build_sequence(
            [
                {"uid": "1", "song_id": "a", "song_name": "A", "msg_time_ms": 1000},
                {"uid": "1", "song_id": "a", "song_name": "A", "msg_time_ms": 2000},
                {"uid": "1", "song_id": "b", "song_name": "B", "msg_time_ms": 3000},
            ],
            anchor_index=0,
        )
        self.assertEqual(anchor["song_id"], "a")
        self.assertEqual([item["song_id"] for item in songs], ["a", "b"])
        self.assertEqual(skipped, 1)
        self.assertEqual(reason, "到达消息末尾")

    def test_build_sequence_respects_gap_limit(self) -> None:
        _, songs, skipped, reason = build_sequence(
            [
                {"uid": "1", "song_id": "a", "song_name": "A", "msg_time_ms": 0},
                {"uid": "1", "song_id": "b", "song_name": "B", "msg_time_ms": 1 * 3600 * 1000},
                {"uid": "1", "song_id": "c", "song_name": "C", "msg_time_ms": 5 * 3600 * 1000},
            ],
            anchor_index=0,
            max_gap_hours=2,
        )
        self.assertEqual([item["song_id"] for item in songs], ["a", "b"])
        self.assertEqual(skipped, 0)
        self.assertIn("超过 2 小时", reason)


if __name__ == "__main__":
    unittest.main()
