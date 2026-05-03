import unittest

from services.sequence_builder import build_sequence


class ShadowCandidateLimitTests(unittest.TestCase):
    def test_build_sequence_respects_max_songs_for_candidate_preview(self) -> None:
        _, songs, _, reason = build_sequence(
            [
                {"uid": "1", "song_id": "a", "song_name": "A", "msg_time_ms": 0},
                {"uid": "1", "song_id": "b", "song_name": "B", "msg_time_ms": 1000},
                {"uid": "1", "song_id": "c", "song_name": "C", "msg_time_ms": 2000},
            ],
            anchor_index=0,
            max_songs=1,
        )
        self.assertEqual([item["song_id"] for item in songs], ["a"])
        self.assertIn("最大歌曲数量限制 1", reason)


if __name__ == "__main__":
    unittest.main()
