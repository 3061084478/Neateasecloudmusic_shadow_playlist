import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.chat_service import ChatService
from services.config_store import ConfigStore


class ChatHistoryAllScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="v5-chat-all-"))
        (self.temp_dir / "data" / "cache").mkdir(parents=True, exist_ok=True)
        (self.temp_dir / "data" / "archive").mkdir(parents=True, exist_ok=True)
        (self.temp_dir / "config.json").write_text(
            '{"api_base":"http://127.0.0.1:3000","cookie":"cookie=1","request_timeout":5}',
            encoding="utf-8",
        )
        self.service = ChatService(ConfigStore(workspace_root=str(self.temp_dir)))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_all_scope_prefers_full_backfill_when_not_completed(self) -> None:
        with patch.object(self.service, "sync_full_history_backfill") as full_mock, patch.object(
            self.service, "sync_recent_history_delta"
        ) as recent_mock, patch.object(self.service.repository, "query_messages", return_value=[]):
            self.service.query_chat_history(uid="314548560", scope="all")
        full_mock.assert_called_once()
        recent_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
