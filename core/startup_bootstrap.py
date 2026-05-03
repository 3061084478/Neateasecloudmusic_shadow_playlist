from __future__ import annotations

import os
import socket
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

try:
    import qrcode
except ImportError:  # pragma: no cover
    qrcode = None

import requests
from PySide6 import QtCore, QtGui

from services.config_store import ConfigStore
from services.netease_api import NeteaseApiClient, NeteaseApiError


class StartupBootstrapError(Exception):
    pass


DEFAULT_API_START_COMMAND = ["cmd", "/c", "npx", "NeteaseCloudMusicApi"]
DEFAULT_NO_PROXY = "localhost,127.0.0.1,::1"
NCM_API_PACKAGE = "NeteaseCloudMusicApi"
API_READY_TIMEOUT_SECONDS = 30
API_READY_POLL_INTERVAL_SECONDS = 0.5
QUICK_LOCAL_REQUEST_TIMEOUT = (0.25, 1.0)
RUNTIME_TEMP_DIRNAME = "tmp"
ANONYMOUS_TOKEN_FILENAME = "anonymous_token"


class StartupBootstrap:
    def __init__(self, config_store: ConfigStore):
        self.config_store = config_store
        self.config = self.config_store.load()
        self.api_client = NeteaseApiClient(self.config)
        self.api_process: Optional[subprocess.Popen] = None

    def reload(self) -> Dict[str, Any]:
        self.config = self.config_store.load()
        self.api_client = NeteaseApiClient(self.config)
        return self.config

    def get_config_path(self) -> str:
        return str(self.config_store.config_path)

    def has_saved_cookie(self) -> bool:
        self.reload()
        return bool(str(self.config.get("cookie") or "").strip())

    def _build_api_start_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "http_proxy",
            "https_proxy",
            "ALL_PROXY",
            "all_proxy",
            "npm_config_proxy",
            "npm_config_https_proxy",
        ):
            env.pop(key, None)
        npm_cache_dir = self.config_store.workspace_root / "data" / "npm_cache"
        runtime_tmp_dir = self.config_store.workspace_root / "data" / RUNTIME_TEMP_DIRNAME
        npm_cache_dir.mkdir(parents=True, exist_ok=True)
        runtime_tmp_dir.mkdir(parents=True, exist_ok=True)
        anonymous_token_path = runtime_tmp_dir / ANONYMOUS_TOKEN_FILENAME
        if not anonymous_token_path.exists():
            anonymous_token_path.write_text("anonymous", encoding="utf-8")
        env["npm_config_offline"] = "false"
        env["npm_config_cache"] = str(npm_cache_dir)
        env["TEMP"] = str(runtime_tmp_dir)
        env["TMP"] = str(runtime_tmp_dir)
        env["TMPDIR"] = str(runtime_tmp_dir)
        env["NO_PROXY"] = DEFAULT_NO_PROXY
        env["no_proxy"] = DEFAULT_NO_PROXY
        return env

    def _resolve_api_start_command(self) -> list[str] | str:
        configured = self.config.get("api_start_command")
        if isinstance(configured, list) and configured:
            return [str(item) for item in configured]
        if isinstance(configured, str) and configured.strip():
            return configured
        bundled = self._resolve_bundled_api_start_command()
        if bundled:
            return bundled
        return DEFAULT_API_START_COMMAND

    def _resolve_api_host_port(self) -> tuple[str, int]:
        host = "127.0.0.1"
        port = 3000
        api_base = str(self.api_client.api_base or "")
        if "://" in api_base:
            parsed = urlparse(api_base)
            if parsed.hostname:
                host = parsed.hostname
            if parsed.port:
                port = parsed.port
        return host, port

    @staticmethod
    def _build_node_eval(server_path: str, port: int) -> str:
        return f"require({server_path!r}).serveNcmApi({{checkVersion:false, port:{int(port)}}})"

    def _resolve_bundled_api_start_command(self) -> Optional[list[str]]:
        _host, target_port = self._resolve_api_host_port()
        runtime_dirs = [
            self.config_store.bundle_root / "runtime" / NCM_API_PACKAGE,
            self.config_store.workspace_root / "runtime" / NCM_API_PACKAGE,
        ]
        for runtime_dir in runtime_dirs:
            if not runtime_dir.exists():
                continue
            server_path = runtime_dir / "server.js"
            node_bin = runtime_dir / "node.exe"
            if server_path.exists() and node_bin.exists():
                return [
                    str(node_bin),
                    "-e",
                    self._build_node_eval(str(server_path), target_port),
                ]
            bat_path = runtime_dir / "start_api.bat"
            if bat_path.exists():
                return ["cmd", "/c", str(bat_path)]
            cmd_path = runtime_dir / "start_api.cmd"
            if cmd_path.exists():
                return ["cmd", "/c", str(cmd_path)]
            ps1_path = runtime_dir / "start_api.ps1"
            if ps1_path.exists():
                return [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ps1_path),
                ]
        return None

    def _ensure_default_api_package_cached(self, env: Dict[str, str]) -> None:
        result = subprocess.run(
            ["cmd", "/c", "npx", "--yes", "--package", NCM_API_PACKAGE, "node", "-p", "2+2"],
            cwd=str(self.config_store.workspace_root),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode == 0:
            return
        detail = (result.stderr or "").strip() or "未知错误"
        raise StartupBootstrapError(f"自动准备本地 API 运行包失败：{detail}")

    def _resolve_cached_server_path(self) -> str:
        npm_cache = self.config_store.workspace_root / "data" / "npm_cache" / "_npx"
        matches = list(npm_cache.glob(f"*/node_modules/{NCM_API_PACKAGE}/server.js"))
        if not matches:
            raise StartupBootstrapError("未找到本地缓存的 NeteaseCloudMusicApi server.js")
        return str(max(matches, key=lambda item: item.stat().st_mtime))

    def is_api_ready(self) -> bool:
        return self.is_api_http_responding()

    def is_api_port_open(self) -> bool:
        host, port = self._resolve_api_host_port()
        try:
            with socket.create_connection((host, port), timeout=0.35):
                return True
        except OSError:
            return False

    def is_api_http_responding(self) -> bool:
        try:
            session = requests.Session()
            session.trust_env = False
            response = session.get(
                f"{self.api_client.api_base}/login/status",
                params={"timestamp": time.time()},
                timeout=QUICK_LOCAL_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            return False
        return self.api_client.extract_status_code(data) == 200

    def start_api_service(self) -> None:
        command = self._resolve_api_start_command()
        env = self._build_api_start_env()
        creationflags = subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, "CREATE_NEW_CONSOLE") else 0

        if command == DEFAULT_API_START_COMMAND:
            if getattr(sys, "frozen", False):
                raise StartupBootstrapError(
                    "当前便携版缺少内置 API 运行时。请重新生成包含 runtime\\NeteaseCloudMusicApi 的发布包。"
                )
            if shutil.which("node") is None:
                raise StartupBootstrapError("未检测到 node，请先安装 Node.js 后再启动。")
            self._ensure_default_api_package_cached(env)
            server_path = self._resolve_cached_server_path()
            _host, target_port = self._resolve_api_host_port()
            command = ["node", "-e", self._build_node_eval(server_path, target_port)]

        self.api_process = subprocess.Popen(
            command,
            cwd=str(self.config_store.workspace_root),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            shell=isinstance(command, str),
        )

    def ensure_api_ready(self) -> None:
        if self.is_api_http_responding():
            return
        if self.is_api_port_open():
            raise StartupBootstrapError(
                "检测到 API 端口已被占用，但当前服务不是兼容的 NeteaseCloudMusicApi。请关闭占用 3000 端口的程序后重试。"
            )
        self.start_api_service()
        deadline = time.time() + API_READY_TIMEOUT_SECONDS
        while time.time() < deadline:
            if self.is_api_http_responding():
                return
            time.sleep(API_READY_POLL_INTERVAL_SECONDS)
        if self.is_api_port_open():
            raise StartupBootstrapError("本地 API 端口已打开，但接口未就绪。请检查端口冲突或 API 版本兼容性。")
        raise StartupBootstrapError("本地 API 服务启动超时，请检查 NeteaseCloudMusicApi 是否已正确安装。")

    def is_cookie_valid(self) -> bool:
        self.reload()
        cookie = str(self.config.get("cookie") or "").strip()
        if not cookie:
            return False
        try:
            session = requests.Session()
            session.trust_env = False
            response = session.get(
                f"{self.api_client.api_base}/login/status",
                params={
                    "cookie": cookie,
                    "timestamp": time.time(),
                },
                timeout=QUICK_LOCAL_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            return False
        if self.api_client.extract_status_code(data) != 200:
            return False
        account = data.get("data", {}).get("account") or {}
        profile = data.get("data", {}).get("profile") or {}
        if not profile:
            return False
        if account.get("anonimousUser"):
            return False
        return bool(account.get("id") or profile.get("userId"))

    def get_account_profile(self) -> Dict[str, str]:
        self.reload()
        return self.api_client.get_login_status()

    def create_qr_session(self) -> Dict[str, str]:
        self.reload()
        key = self.api_client.get_qr_key()
        qr_url = self.api_client.create_qr(key)
        return {"key": key, "qr_url": qr_url}

    def check_qr_session(self, key: str) -> Dict[str, Any]:
        status = self.api_client.check_qr_status(key)
        if status["code"] == 803 and status["cookie"]:
            self.config_store.update(cookie=status["cookie"])
            self.reload()
        return status

    def clear_saved_cookie(self) -> None:
        payload = self.config_store.load()
        payload["cookie"] = ""
        self.config_store.save(payload)
        self.reload()

    def build_qr_pixmap(self, qr_url: str, size: int = 320) -> Optional[QtGui.QPixmap]:
        if qrcode is None:
            return None
        qr = qrcode.QRCode(border=2, box_size=8)
        qr.add_data(qr_url)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white")
        buffer = image.convert("RGBA").tobytes("raw", "RGBA")
        qimage = QtGui.QImage(buffer, image.size[0], image.size[1], QtGui.QImage.Format_RGBA8888)
        pixmap = QtGui.QPixmap.fromImage(qimage.copy())
        return pixmap.scaled(size, size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
