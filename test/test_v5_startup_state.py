import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from core.app_controller import AppController
from core.startup_bootstrap import StartupBootstrap
from services.config_store import ConfigStore
from services.playlist_service import PlaylistService
from ui.web_bridge import WebBridge


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


class StartupBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="v5-startup-bridge-"))
        (self.temp_dir / "data" / "cache").mkdir(parents=True, exist_ok=True)
        (self.temp_dir / "data" / "archive").mkdir(parents=True, exist_ok=True)
        (self.temp_dir / "config.json").write_text(
            json.dumps(
                {
                    "api_base": "http://127.0.0.1:3000",
                    "cookie": "cookie=1",
                    "shadow_playlist_id": "123456",
                    "shadow_playlist_name": "测试歌单",
                    "request_timeout": 5,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.controller = AppController(workspace_root=str(self.temp_dir))
        self.controller.load_all_friends = Mock(return_value=[])
        self.bridge = WebBridge(self.controller)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @staticmethod
    def _unwrap(raw: str) -> dict:
        payload = json.loads(raw)
        assert payload["ok"] is True
        return payload["data"]

    def test_get_startup_payload_marks_offline_state(self) -> None:
        self.controller.bootstrap.is_api_ready = Mock(return_value=False)
        self.controller.bootstrap.is_cookie_valid = Mock(return_value=False)

        payload = self._unwrap(self.bridge.getStartupPayload())

        self.assertEqual(payload["connection"]["apiStatus"], "offline")
        self.assertEqual(payload["connection"]["cookieStatus"], "invalid")
        self.assertFalse(payload["startup"]["canAutoEnter"])
        self.assertFalse(payload["startup"]["hasQr"])

    def test_probe_startup_status_reveals_qr_when_cookie_missing(self) -> None:
        self.controller.bootstrap.is_api_ready = Mock(return_value=True)
        self.controller.bootstrap.is_cookie_valid = Mock(return_value=False)
        self.controller.bootstrap.create_qr_session = Mock(return_value={"key": "qr-key", "qr_url": "https://example.com/qr"})
        self.controller.bootstrap.build_qr_pixmap = Mock(return_value=None)

        payload = self._unwrap(self.bridge.probeStartupStatus(True))

        self.assertEqual(payload["connection"]["apiStatus"], "online")
        self.assertEqual(payload["connection"]["cookieStatus"], "invalid")
        self.assertEqual(payload["qr"]["status"], "ready")
        self.assertTrue(payload["startup"]["hasQr"])

    def test_run_startup_primary_action_enters_authenticated_state(self) -> None:
        self.controller.bootstrap.ensure_api_ready = Mock()
        self.controller.bootstrap.is_api_ready = Mock(return_value=True)
        self.controller.bootstrap.is_cookie_valid = Mock(return_value=True)
        self.controller.bootstrap.get_account_profile = Mock(
            return_value={
                "user_id": "42",
                "nickname": "Shadow Tester",
                "avatar_url": "https://example.com/avatar.png",
            }
        )

        payload = self._unwrap(self.bridge.runStartupPrimaryAction())

        self.assertTrue(payload["startup"]["canAutoEnter"])
        self.assertEqual(payload["connection"]["apiStatus"], "online")
        self.assertEqual(payload["connection"]["cookieStatus"], "valid")
        self.assertEqual(payload["connection"]["accountNickname"], "Shadow Tester")


if __name__ == "__main__":
    unittest.main()
