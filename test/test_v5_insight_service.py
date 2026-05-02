import unittest

from services.insight_service import InsightService


class InsightServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = InsightService()
        self.base_payload = {
            "audience_scope": "friend",
            "friend_name": "好友A",
            "period_label": "all",
            "total_songs": 20,
            "total_msgs": 120,
            "active_span_days": 45,
            "top_artist_3": [{"name": "Artist A", "count": 6}],
            "decade_distribution": [{"name": "2020s", "count": 10}],
            "language_distribution": [{"name": "英语", "count": 12}],
            "night_ratio": 0.35,
            "stability_score": 0.62,
            "discovery_index": 0.58,
            "evidence_tracks": [{"song_name": "Song 1", "artist_name": "Artist A", "msg_time": "2026-04-01 21:00:00", "reason": "样本"}],
        }

    def test_fallback_when_cloud_disabled(self) -> None:
        config = {
            "ai_enabled": False,
            "ai_base_url": "",
            "ai_model": "",
            "ai_api_key": "",
            "ai_timeout": 20,
        }
        result = self.service.generate_friend_insight(self.base_payload, "rational", config)
        self.assertEqual(result["source"], "fallback")
        self.assertIn("好友A", result["text"])
        self.assertFalse(result["insufficient_data"])
        self.assertIn("trust_basis", result)

    def test_insufficient_data_switches_to_lightweight(self) -> None:
        config = {"ai_enabled": True, "ai_base_url": "", "ai_model": "", "ai_api_key": "", "ai_timeout": 20}
        low_payload = dict(self.base_payload)
        low_payload["total_songs"] = 6
        low_payload["active_span_days"] = 3
        result = self.service.generate_friend_insight(low_payload, "rational", config)
        self.assertTrue(result["insufficient_data"])
        self.assertIn("样本量较少", result["text"])

    def test_commentary_and_annual_modes_fallback(self) -> None:
        config = {"ai_enabled": False, "ai_base_url": "", "ai_model": "", "ai_api_key": "", "ai_timeout": 20}
        annual_payload = dict(self.base_payload)
        annual_payload["annual_review"] = {
            "year": 2026,
            "message_count": 1234,
            "song_count": 321,
            "peak_month": "2026-04",
            "top_song_friend_name": "好友A",
        }
        commentary = self.service.generate_friend_insight(annual_payload, "评论版", config)
        annual = self.service.generate_self_insight(annual_payload, "年度报告版", config)
        self.assertEqual(commentary["mode"], "commentary")
        self.assertIn("乐评", commentary["text"])
        self.assertEqual(annual["mode"], "annual")
        self.assertIn("年度音乐社交回顾", annual["text"])


if __name__ == "__main__":
    unittest.main()
