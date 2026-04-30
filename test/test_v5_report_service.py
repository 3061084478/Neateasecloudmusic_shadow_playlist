import shutil
import tempfile
import unittest
from pathlib import Path

from services.config_store import ConfigStore
from services.report_service import ReportService


class ReportServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="v5-report-")
        self.config_store = ConfigStore(self.temp_dir)
        self.service = ReportService(self.config_store)
        self.existing_file = Path(self.service.report_dir) / "friend_demo.png"
        self.existing_file.write_bytes(b"png")
        missing_file = Path(self.service.report_dir) / "missing_demo.png"
        self.service._save_history(
            [
                {
                    "type": "friend",
                    "uid": "100",
                    "title": "好友A 音乐关系报告",
                    "summary": "高峰出现在 4 月",
                    "lead": "好友A",
                    "path": str(self.existing_file),
                    "generated_at": "2026-04-24 10:00:00",
                },
                {
                    "type": "annual",
                    "uid": "",
                    "title": "2026 年度回顾",
                    "path": str(missing_file),
                    "generated_at": "2026-04-24 11:00:00",
                },
            ]
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_list_reports_support_type_and_keyword_filter(self) -> None:
        rows = self.service.list_recent_reports(report_type="friend", keyword="好友A")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["type"], "friend")
        self.assertEqual(rows[0]["display_type"], "好友报告")
        self.assertEqual(rows[0]["lead"], "好友A")

    def test_list_reports_can_search_summary(self) -> None:
        rows = self.service.list_recent_reports(report_type="all", keyword="高峰出现在")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["type"], "friend")

    def test_prune_missing_reports_removes_broken_entries(self) -> None:
        result = self.service.prune_missing_reports()
        self.assertEqual(result["removed"], 1)
        self.assertEqual(result["kept"], 1)
        rows = self.service.list_recent_reports(report_type="all")
        self.assertEqual(len(rows), 1)
        self.assertTrue(Path(rows[0]["path"]).exists())


if __name__ == "__main__":
    unittest.main()
