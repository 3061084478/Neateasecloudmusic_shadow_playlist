from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict


class ConfigStore:
    def __init__(self, workspace_root: str, config_path: str | None = None, bundle_root: str | None = None):
        self.workspace_root = Path(workspace_root).resolve()
        self.bundle_root = Path(bundle_root).resolve() if bundle_root else self.workspace_root
        if config_path:
            self.config_path = Path(config_path).resolve()
        else:
            self.config_path = self.workspace_root / "config.json"
        self._initialize_config_if_missing()

    @staticmethod
    def _default_payload() -> Dict[str, Any]:
        return {
            "api_base": "http://127.0.0.1:3000",
            "cookie": "",
            "request_timeout": 8,
            "default_limit": 50,
            "sleep_seconds": 0.25,
            "shadow_playlist_id": "",
            "shadow_playlist_name": "",
            "shadow_playlist_strategy": "use_existing",
            "shadow_playlist_private": False,
            "shadow_playlist_last_set_at": "",
            "auto_archive_all_friends": True,
            "auto_archive_initialized": False,
            "auto_archive_last_run": "",
            "ai_enabled": False,
            "ai_base_url": "https://api.openai.com/v1",
            "ai_model": "gpt-4o-mini",
            "ai_api_key": "",
            "ai_timeout": 20,
        }

    def _initialize_config_if_missing(self) -> None:
        if self.config_path.exists():
            return
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        template_path = self.bundle_root / "config.template.json"
        if template_path.exists():
            shutil.copyfile(template_path, self.config_path)
            return
        with self.config_path.open("w", encoding="utf-8") as file:
            json.dump(self._default_payload(), file, ensure_ascii=False, indent=2)

    def load(self) -> Dict[str, Any]:
        with self.config_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def save(self, payload: Dict[str, Any]) -> None:
        with self.config_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)

    def update(self, **fields: Any) -> Dict[str, Any]:
        payload = self.load()
        payload.update(fields)
        self.save(payload)
        return payload

    @property
    def cache_dir(self) -> str:
        path = self.workspace_root / "data" / "cache"
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @property
    def archive_db_path(self) -> str:
        path = self.workspace_root / "data" / "archive" / "chat_history.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    @property
    def font_assets_dir(self) -> str:
        relatives = (Path("assets/fonts"),)
        search_roots = (
            self.bundle_root,
            self.workspace_root,
        )
        for base in search_roots:
            for relative in relatives:
                candidate = (base / relative).resolve()
                if candidate.exists():
                    return str(candidate)
        return str((self.bundle_root / relatives[0]).resolve())
