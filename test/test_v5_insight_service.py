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
            "relation_temperature": {"label": "稳定关系", "score": 64},
            "trend_conclusion": "互动高峰出现在 2026-04（消息 52 / 歌曲 12），当前关系保持稳定节奏（较起点 +8 首歌曲）。",
            "activity_conclusion": "夜间型互动特征明显，核心活跃时段贡献约 48.0%。",
            "cover_line": "稳定关系 · 互动高峰出现在 2026-04",
            "common_world": {"shared_artists": ["Artist A", "Artist B"]},
            "first_introduced_artist": "Artist A",
            "silence_and_burst": {"detail": "2026-04 出现明显爆发（环比 +8 首歌曲），属于关系升温拐点。"},
            "evidence_tracks": [
                {
                    "song_name": "Song 1",
                    "artist_name": "Artist A",
                    "msg_time": "2026-04-01 21:00:00",
                    "reason": "样本",
                    "support_for": ["互动高频", "高峰月份"],
                }
            ],
        }
        self.self_payload = {
            "audience_scope": "self",
            "friend_name": "我的音乐社交",
            "period_label": "all",
            "total_songs": 88,
            "total_msgs": 420,
            "active_span_days": 96,
            "top_artist_3": [{"name": "JID", "count": 18}, {"name": "SZA", "count": 14}, {"name": "Common A", "count": 11}],
            "decade_distribution": [{"name": "2020s", "count": 52}],
            "language_distribution": [{"name": "英语", "count": 47}, {"name": "华语", "count": 26}],
            "night_ratio": 0.41,
            "stability_score": 0.57,
            "discovery_index": 0.63,
            "trend_conclusion": "互动高峰出现在 2026-04（消息 138 / 歌曲 28），当前整体保持稳定推进。",
            "cover_line": "输入策展型 · 高峰在 2026-04，当前覆盖 8 位活跃好友，累计歌曲 88 首。",
            "social_tag": "输入策展型",
            "core_friend_name": "好友A",
            "top_chat_friends": [{"name": "好友A", "count": 132}],
            "top_song_friends": [{"name": "好友B", "count": 25}],
            "top_temperature_friends": [{"name": "好友A", "count": 84}],
            "artist_overview": {
                "all_friends_top_artists": [{"name": "SZA", "count": 14}],
                "my_top_artists": [{"name": "JID", "count": 16}],
                "shared_top_artists": [{"name": "Common A", "count": 8}],
            },
            "network_block": {
                "music_balance": {"label": "输入型"},
                "music_concentration": {"label": "高集中"},
            },
            "first_introduced_artist": "SZA",
            "personality_cards": [{"tag": "深夜策展人", "reason": "夜间分享占比 41.0%，明显高于常规日间分布。"}],
            "evidence_tracks": [
                {
                    "song_name": "Song 2",
                    "artist_name": "JID",
                    "msg_time": "2026-04-03 22:00:00",
                    "reason": "样本",
                    "support_for": ["来自 好友A", "社交网络样本"],
                }
            ],
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
        self.assertIn("当成一段关系看", result["text"])
        self.assertIn("稳定关系", result["text"])
        self.assertIn("最常回到的歌手先落在 Artist A", result["text"])
        self.assertIn("共同歌手已经形成清晰交集", result["text"])
        self.assertIn("像 《Song 1》 / Artist A 这样的歌", result["text"])
        self.assertIn("相处节奏", result["text"])
        self.assertFalse(result["insufficient_data"])
        self.assertIn("trust_basis", result)
        self.assertEqual(result["version"], "v4")
        self.assertIn("\n\n", result["text"])

    def test_style_mode_generates_more_polished_summary(self) -> None:
        config = {"ai_enabled": False, "ai_base_url": "", "ai_model": "", "ai_api_key": "", "ai_timeout": 20}
        result = self.service.generate_friend_insight(self.base_payload, "总结版", config)
        self.assertEqual(result["mode"], "style")
        self.assertIn("私人音乐线", result["text"])
        self.assertIn("Artist A", result["text"])
        self.assertIn("像 《Song 1》 / Artist A 这样的歌", result["text"])
        self.assertNotIn("总结下来", result["text"])
        self.assertNotIn("综合收束", result["text"])
        self.assertNotIn("最打动人的地方", result["text"])

    def test_self_modes_use_different_template_family(self) -> None:
        config = {"ai_enabled": False, "ai_base_url": "", "ai_model": "", "ai_api_key": "", "ai_timeout": 20}
        rational = self.service.generate_self_insight(self.self_payload, "理性分析版", config)
        style = self.service.generate_self_insight(self.self_payload, "总结版", config)
        self.assertEqual(rational["mode"], "rational")
        self.assertIn("当成你这一阶段的侧写看", rational["text"])
        self.assertIn("社交气质更接近“输入策展型”", rational["text"])
        self.assertIn("好友A 会是最先被提到的名字", rational["text"])
        self.assertIn("你的听歌习惯", rational["text"])
        self.assertIn("输入策展型", style["text"])
        self.assertIn("慢慢显出性格的一面", style["text"])
        self.assertIn("好友A 留下的那部分影响", style["text"])
        self.assertIn("《Song 2》 / JID", style["text"])
        self.assertIn("深夜策展人", style["text"])
        self.assertIn("社交标签、核心好友、关系网络结构", rational["trust_basis"])
        self.assertNotIn("总结下来", style["text"])
        self.assertNotIn("综合收束", style["text"])
        self.assertNotIn("社交存在感", style["text"])
        self.assertNotIn("进入你的社交样本，对应", style["text"])
        self.assertNotIn("当成一段关系去看", style["text"])

    def test_friend_and_self_voice_are_clearly_different(self) -> None:
        config = {"ai_enabled": False, "ai_base_url": "", "ai_model": "", "ai_api_key": "", "ai_timeout": 20}
        friend_text = self.service.generate_friend_insight(self.base_payload, "总结版", config)["text"]
        self_text = self.service.generate_self_insight(self.self_payload, "总结版", config)["text"]
        self.assertIn("关系去看", friend_text)
        self.assertIn("性格的一面", self_text)
        self.assertNotIn("性格的一面", friend_text)

    def test_insufficient_data_switches_to_lightweight(self) -> None:
        config = {"ai_enabled": True, "ai_base_url": "", "ai_model": "", "ai_api_key": "", "ai_timeout": 20}
        low_payload = dict(self.base_payload)
        low_payload["total_songs"] = 6
        low_payload["active_span_days"] = 3
        result = self.service.generate_friend_insight(low_payload, "rational", config)
        self.assertTrue(result["insufficient_data"])
        self.assertIn("样本还比较轻", result["text"])
        self.assertIn("等样本再厚一点", result["text"])

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
        self.assertIn("持续更新的个人栏目", commentary["text"])
        self.assertEqual(annual["mode"], "annual")
        self.assertIn("年度音乐社交回顾", annual["text"])
        self.assertIn("最高峰出现在 2026-04", annual["text"])

    def test_relation_temperature_changes_style_tone(self) -> None:
        config = {"ai_enabled": False, "ai_base_url": "", "ai_model": "", "ai_api_key": "", "ai_timeout": 20}
        hot_payload = dict(self.base_payload)
        hot_payload["relation_temperature"] = {"label": "高温关系", "score": 81}
        cold_payload = dict(self.base_payload)
        cold_payload["relation_temperature"] = {"label": "低频关系", "score": 24}
        hot_text = self.service.generate_friend_insight(hot_payload, "总结版", config)["text"]
        cold_text = self.service.generate_friend_insight(cold_payload, "总结版", config)["text"]
        self.assertIn("明显余温", hot_text)
        self.assertIn("偏克制", cold_text)


if __name__ == "__main__":
    unittest.main()
