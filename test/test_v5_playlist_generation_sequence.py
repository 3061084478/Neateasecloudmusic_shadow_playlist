import unittest

from services.playlist_service import PlaylistService


class PlaylistGenerationSequenceTests(unittest.TestCase):
    @staticmethod
    def _sample_messages() -> list[dict]:
        return [
            {"uid": "u1", "song_id": "a", "song_name": "A", "msg_id": "1", "msg_time_ms": 1000, "msg_time_str": "t1"},
            {"uid": "u1", "song_id": "a", "song_name": "A", "msg_id": "2", "msg_time_ms": 2000, "msg_time_str": "t2"},
            {"uid": "u1", "song_id": "b", "song_name": "B", "msg_id": "3", "msg_time_ms": 3000, "msg_time_str": "t3"},
        ]

    def test_selected_messages_without_limits_keep_duplicates(self) -> None:
        anchor, sequence, skipped, reason = PlaylistService._resolve_generation_sequence(
            song_messages=self._sample_messages(),
            anchor_index=0,
            max_gap_hours=None,
            max_songs=None,
            apply_sequence_rules=False,
        )
        self.assertEqual(anchor["song_id"], "a")
        self.assertEqual([item["msg_id"] for item in sequence], ["1", "2", "3"])
        self.assertEqual(skipped, 0)
        self.assertEqual(reason, "")

    def test_with_sequence_rules_still_deduplicates(self) -> None:
        _, sequence, skipped, reason = PlaylistService._resolve_generation_sequence(
            song_messages=self._sample_messages(),
            anchor_index=0,
            max_gap_hours=None,
            max_songs=None,
            apply_sequence_rules=True,
        )
        self.assertEqual([item["song_id"] for item in sequence], ["a", "b"])
        self.assertEqual(skipped, 1)
        self.assertEqual(reason, "到达消息末尾")


if __name__ == "__main__":
    unittest.main()

