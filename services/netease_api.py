from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests


class NeteaseApiError(Exception):
    pass


class NeteaseApiClient:
    def __init__(self, config: Dict[str, Any]):
        self.api_base = str(config["api_base"]).rstrip("/")
        self.cookie = str(config.get("cookie") or "")
        self.request_timeout = int(config.get("request_timeout", 10))
        self.session = requests.Session()
        self.session.trust_env = False

    def update_cookie(self, cookie: str) -> None:
        self.cookie = str(cookie or "")

    def _get(self, path: str, params: Dict[str, Any], use_cookie: bool = True) -> Dict[str, Any]:
        final_params = dict(params)
        if use_cookie and self.cookie:
            final_params["cookie"] = self.cookie
        final_params["timestamp"] = time.time()
        try:
            response = self.session.get(
                f"{self.api_base}{path}",
                params=final_params,
                timeout=self.request_timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise NeteaseApiError(f"请求失败: {exc}") from exc
        except ValueError as exc:
            raise NeteaseApiError("接口返回不是合法 JSON") from exc

    @staticmethod
    def extract_status_code(data: Dict[str, Any]) -> int:
        return int(
            data.get("code")
            or data.get("body", {}).get("code")
            or data.get("data", {}).get("code")
            or -1
        )

    def get_private_history(self, uid: str, limit: int = 200, before: Optional[int] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"uid": uid, "limit": limit}
        if before is not None:
            params["before"] = before
        data = self._get("/msg/private/history", params)
        return data.get("msgs", [])

    def get_private_messages_for_archive(
        self,
        uid: str,
        limit: int = 200,
        before: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        return self.get_private_history(uid=uid, limit=limit, before=before)

    def get_user_detail(self, uid: str) -> Dict[str, Any]:
        data = self._get("/user/detail", {"uid": uid})
        profile = data.get("profile") or {}
        if not profile:
            raise NeteaseApiError(f"未获取到用户信息: uid={uid}")
        return profile

    def get_login_status(self) -> Dict[str, Any]:
        data = self._get("/login/status", {})
        account = data.get("data", {}).get("account") or {}
        profile = data.get("data", {}).get("profile") or {}
        if not account and not profile:
            raise NeteaseApiError("未获取到当前登录用户信息")
        return {
            "user_id": str(account.get("id") or profile.get("userId") or "").strip(),
            "nickname": str(profile.get("nickname") or "").strip(),
            "avatar_url": str(profile.get("avatarUrl") or "").strip(),
        }

    def get_user_follows_page(self, uid: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        data = self._get("/user/follows", {"uid": uid, "limit": limit, "offset": offset})
        if self.extract_status_code(data) != 200:
            raise NeteaseApiError(f"获取关注列表失败: uid={uid}, response={data}")
        return {"users": data.get("follow") or [], "more": bool(data.get("more"))}

    def get_user_followeds_page(self, uid: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        data = self._get("/user/followeds", {"uid": uid, "limit": limit, "offset": offset})
        if self.extract_status_code(data) != 200:
            raise NeteaseApiError(f"获取粉丝列表失败: uid={uid}, response={data}")
        return {"users": data.get("followeds") or [], "more": bool(data.get("more"))}

    def get_user_playlists(self, uid: str, limit: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        data = self._get("/user/playlist", {"uid": uid, "limit": limit, "offset": offset})
        if self.extract_status_code(data) != 200:
            raise NeteaseApiError(f"获取用户歌单失败: uid={uid}, response={data}")
        return data.get("playlist") or []

    def get_playlist_tracks(self, playlist_id: str) -> List[Dict[str, Any]]:
        data = self._get("/playlist/track/all", {"id": playlist_id})
        if self.extract_status_code(data) != 200:
            raise NeteaseApiError(f"获取歌单内容失败: playlist_id={playlist_id}, response={data}")
        return data.get("songs", [])

    def get_playlist_detail(self, playlist_id: str) -> Dict[str, Any]:
        data = self._get("/playlist/detail", {"id": playlist_id})
        if self.extract_status_code(data) != 200:
            raise NeteaseApiError(f"获取歌单详情失败: playlist_id={playlist_id}, response={data}")
        playlist = data.get("playlist") or {}
        resolved_playlist_id = str(playlist.get("id") or "").strip()
        name = str(playlist.get("name") or "").strip()
        if not resolved_playlist_id or not name:
            raise NeteaseApiError(f"歌单详情缺少关键信息: playlist_id={playlist_id}, response={data}")
        return {
            "playlist_id": resolved_playlist_id,
            "name": name,
            "privacy": int(playlist.get("privacy") or 0),
            "track_count": int(playlist.get("trackCount") or 0),
            "raw": data,
        }

    def create_playlist(self, name: str, privacy: int = 10) -> Dict[str, Any]:
        data = self._get("/playlist/create", {"name": name, "privacy": privacy})
        if self.extract_status_code(data) != 200:
            raise NeteaseApiError(f"创建歌单失败: response={data}")
        playlist = data.get("playlist") or {}
        playlist_id = str(playlist.get("id") or data.get("id") or "").strip()
        if not playlist_id:
            raise NeteaseApiError(f"创建歌单成功但未返回歌单 ID: response={data}")
        return {"playlist_id": playlist_id, "raw": data}

    def update_playlist_name(self, playlist_id: str, name: str) -> Dict[str, Any]:
        return self._get("/playlist/update", {"id": playlist_id, "name": name})

    def remove_tracks_from_playlist(self, playlist_id: str, track_ids: List[str]) -> Dict[str, Any]:
        if not track_ids:
            return {"code": 200}
        return self._get("/playlist/tracks", {"op": "del", "pid": playlist_id, "tracks": ",".join(track_ids)})

    def add_tracks_to_playlist(self, playlist_id: str, track_ids: List[str]) -> Dict[str, Any]:
        if not track_ids:
            return {"code": 200}
        return self._get("/playlist/tracks", {"op": "add", "pid": playlist_id, "tracks": ",".join(track_ids)})

    def get_qr_key(self) -> str:
        data = self._get("/login/qr/key", {}, use_cookie=False)
        qr_key = str(data.get("data", {}).get("unikey") or "").strip()
        if not qr_key:
            raise NeteaseApiError(f"获取二维码 key 失败: {data}")
        return qr_key

    def create_qr(self, key: str) -> str:
        data = self._get("/login/qr/create", {"key": key}, use_cookie=False)
        qr_url = str(data.get("data", {}).get("qrurl") or "").strip()
        if not qr_url:
            raise NeteaseApiError(f"创建二维码失败: {data}")
        return qr_url

    def check_qr_status(self, key: str) -> Dict[str, Any]:
        data = self._get("/login/qr/check", {"key": key}, use_cookie=False)
        return {
            "code": int(data.get("code") or 0),
            "cookie": str(data.get("cookie") or "").strip(),
            "message": str(data.get("message") or data.get("msg") or "").strip(),
            "raw": data,
        }
