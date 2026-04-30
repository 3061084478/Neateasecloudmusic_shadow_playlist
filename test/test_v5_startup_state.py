import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.app_controller import AppController
from core.startup_bootstrap import StartupBootstrap
from services.config_store import ConfigStore
from services.playlist_service import PlaylistService


class StartupStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="v5-startup-"))
        (self.temp_dir / "data" / "cache").mkdir(parents=True, exist_ok=True)
        (self.temp_dir / "data" / "archive").mkdir(parents=True, exist_ok=True)
        (self.temp_dir / "config.json").write_text(
            json.dumps(
                {
                    "api_base": "http://127.0.0.1:3000",
                    "cookie": "cookie=1",
                    "shadow_playlist_id": "123456",
                    "shadow_playlist_strategy": "manual_id",
                    "shadow_playlist_name": "测试歌单",
                    "shadow_playlist_private": True,
                    "shadow_playlist_last_set_at": "2026-04-18 12:00:00",
                    "request_timeout": 5,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_local_shadow_playlist_summary_reads_v5_config(self) -> None:
        service = PlaylistService(ConfigStore(workspace_root=str(self.temp_dir)))
        summary = service.get_local_shadow_playlist_summary()
        self.assertEqual(summary["playlist_id"], "123456")
        self.assertEqual(summary["name"], "测试歌单")
        self.assertEqual(summary["strategy"], "manual_id")
        self.assertTrue(summary["is_private"])

    def test_apply_startup_authenticated_state_uses_local_shadow_summary(self) -> None:
        controller = AppController(workspace_root=str(self.temp_dir))
        state = controller.apply_startup_authenticated_state()
        self.assertEqual(state.mode, "real")
        self.assertEqual(state.api_status, "online")
        self.assertEqual(state.cookie_status, "valid")
        self.assertEqual(state.current_shadow_playlist.playlist_id, "123456")
        self.assertEqual(state.current_shadow_playlist.name, "测试歌单")

    def test_startup_bootstrap_uses_workspace_temp_and_creates_anonymous_token(self) -> None:
        config_store = ConfigStore(workspace_root=str(self.temp_dir))
        bootstrap = StartupBootstrap(config_store)
        env = bootstrap._build_api_start_env()
        expected_tmp = str((self.temp_dir / "data" / "tmp").resolve())
        self.assertEqual(env["TEMP"], expected_tmp)
        self.assertEqual(env["TMP"], expected_tmp)
        self.assertEqual(env["TMPDIR"], expected_tmp)
        token_path = self.temp_dir / "data" / "tmp" / "anonymous_token"
        self.assertTrue(token_path.exists())
        self.assertEqual(token_path.read_text(encoding="utf-8").strip(), "anonymous")


if __name__ == "__main__":
    unittest.main()
