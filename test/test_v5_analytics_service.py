import shutil
import tempfile
import unittest
from pathlib import Path

from services.analytics_service import AnalyticsService
from services.config_store import ConfigStore


class AnalyticsServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="v5-analytics-"))
        self.config_store = ConfigStore(workspace_root=str(self.temp_dir))
        self.service = AnalyticsService(self.config_store)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @staticmethod
    def _message(uid: str, msg_id: str, dt: str, msg_type: str, direction: str, song_name: str = "", artist: str = "") -> dict:
        return {
            "uid": uid,
            "msg_id": msg_id,
            "msg_time_ms": 0,
            "msg_time_str": dt,
            "direction": direction,
            "sender_uid": uid if direction == "friend" else "self",
            "sender_name": "好友A" if direction == "friend" else "我",
            "msg_type": msg_type,
            "text_content": "" if msg_type == "song" else "hello",
            "song_id": f"id_{msg_id}" if msg_type == "song" else "",
            "song_name": song_name,
            "artist_name": artist,
            "raw_msg_json": "{}",
        }

    def test_build_friend_snapshot_basic_metrics(self) -> None:
        uid = "1001"
        rows = [
            self._message(uid, "m1", "2026-04-01 22:10:00", "song", "friend", "Night Drive", "Artist A"),
            self._message(uid, "m2", "2026-04-02 09:20:00", "text", "self"),
            self._message(uid, "m3", "2026-04-10 10:30:00", "song", "friend", "City Light", "Artist B"),
        ]
        self.service.repository.upsert_messages(uid, rows)

        snapshot = self.service.build_friend_snapshot(uid=uid, friend_name="好友A", window="all")
        self.assertEqual(snapshot["message_count_total"], 3)
        self.assertEqual(snapshot["song_share_count_total"], 2)
        self.assertGreaterEqual(len(snapshot["top_artists"]), 1)
        self.assertGreaterEqual(len(snapshot["trend_series"]), 1)
        self.assertIn("personality_tags", snapshot)
        self.assertIn("trend_conclusion", snapshot)
        self.assertIn("activity_conclusion", snapshot)
        self.assertIn("relation_temperature", snapshot)
        self.assertIn("cover_line", snapshot)
        self.assertIn("relation_theme_color", snapshot)
        self.assertIn("style_radar", snapshot)
        self.assertIn("first_introduced_artist", snapshot)
        self.assertIn("silence_and_burst", snapshot)
        self.assertIn("timeline_visual", snapshot)
        self.assertTrue(snapshot["timeline_visual"].get("phases"))
        self.assertTrue(snapshot["timeline_visual"].get("events"))
        self.assertIn("genre_confidence", snapshot["top_genres"][0])
        self.assertTrue(snapshot["evidence_tracks"])
        self.assertIn("reason_tag", snapshot["evidence_tracks"][0])
        self.assertIn("support_for", snapshot["evidence_tracks"][0])

    def test_similarity_matrix_returns_pairs(self) -> None:
        uid_a = "2001"
        uid_b = "2002"
        rows_a = [
            self._message(uid_a, "a1", "2026-04-01 21:00:00", "song", "friend", "Rap Night", "MC One"),
            self._message(uid_a, "a2", "2026-04-05 22:00:00", "song", "friend", "Street Rap", "MC Two"),
        ]
        rows_b = [
            self._message(uid_b, "b1", "2026-04-02 20:00:00", "song", "friend", "Rap City", "MC One"),
            self._message(uid_b, "b2", "2026-04-06 23:30:00", "song", "friend", "Urban Rap", "MC Three"),
        ]
        self.service.repository.upsert_messages(uid_a, rows_a)
        self.service.repository.upsert_messages(uid_b, rows_b)

        snapshots = [
            self.service.build_friend_snapshot(uid_a, "好友A", "all"),
            self.service.build_friend_snapshot(uid_b, "好友B", "all"),
        ]
        pairs = self.service.build_similarity_matrix(snapshots, top_n=3)
        self.assertTrue(pairs)
        self.assertGreaterEqual(pairs[0]["score"], 0.0)

    def test_second_phase_modules_payloads_exist(self) -> None:
        uid_a = "3001"
        uid_b = "3002"
        rows_a = [
            self._message(uid_a, "a1", "2026-01-01 23:00:00", "song", "friend", "Night Rap", "MC One"),
            self._message(uid_a, "a2", "2026-02-02 21:00:00", "song", "friend", "City Jazz", "Band A"),
            self._message(uid_a, "a3", "2026-03-05 10:00:00", "text", "self"),
            self._message(uid_a, "a4", "2026-04-10 22:30:00", "song", "friend", "Late Pop", "Singer A"),
        ]
        rows_b = [
            self._message(uid_b, "b1", "2026-01-03 19:00:00", "song", "friend", "Night Rap", "MC One"),
            self._message(uid_b, "b2", "2026-02-06 08:30:00", "song", "friend", "Morning Pop", "Singer B"),
        ]
        self.service.repository.upsert_messages(uid_a, rows_a)
        self.service.repository.upsert_messages(uid_b, rows_b)

        snap_a = self.service.build_friend_snapshot(uid_a, "好友A", "all")
        snap_b = self.service.build_friend_snapshot(uid_b, "好友B", "all")
        global_snapshot = self.service.build_global_snapshot([snap_a, snap_b], "all")
        common_world = self.service.build_common_world(snap_a, global_snapshot)
        dual = self.service.build_dual_perspective(snap_a, global_snapshot)
        self_snapshot = self.service.build_self_snapshot([snap_a, snap_b], global_snapshot, "我", "all")

        self.assertTrue(snap_a.get("discovery_breakdown"))
        self.assertTrue(snap_a.get("timeline_visual"))
        self.assertIn("shared_genres", common_world)
        self.assertTrue(common_world.get("compare"))
        self.assertTrue(common_world.get("overlap_bars"))
        self.assertIn("friend_style", dual)
        self.assertTrue(snap_a.get("personality_cards"))
        self.assertEqual(len(global_snapshot.get("top_temperature_friends", [])), 2)
        annual = self.service.build_annual_review([snap_a, snap_b], global_snapshot, year=2026)
        self.assertEqual(int(annual.get("year") or 0), 2026)
        self.assertIn("summary", annual)
        self.assertIn("trend_conclusion", global_snapshot)
        self.assertIn("network_block", self_snapshot)
        self.assertIn("timeline_visual", self_snapshot)
        self.assertIn("cover_line", self_snapshot)
        self.assertIn("social_tag", self_snapshot)

    def test_year_window_filter_and_year_list(self) -> None:
        uid = "4001"
        rows = [
            self._message(uid, "x1", "2025-12-29 21:00:00", "song", "friend", "Late 2025", "A"),
            self._message(uid, "x2", "2026-01-02 21:00:00", "song", "friend", "Start 2026", "B"),
            self._message(uid, "x3", "2026-02-02 10:00:00", "text", "self"),
        ]
        self.service.repository.upsert_messages(uid, rows)
        filtered_2026 = self.service.query_friend_messages(uid, window="year:2026")
        filtered_2025 = self.service.query_friend_messages(uid, window="year:2025")
        self.assertEqual(len(filtered_2026), 2)
        self.assertEqual(len(filtered_2025), 1)
        years = self.service.list_available_years([uid])
        self.assertEqual(years, [2025, 2026])


if __name__ == "__main__":
    unittest.main()
