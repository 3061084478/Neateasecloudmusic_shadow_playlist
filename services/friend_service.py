from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from core.models import FriendEntry
from services.config_store import ConfigStore
from services.netease_api import NeteaseApiClient, NeteaseApiError
from services.storage import CacheStore


class FriendService:
    def __init__(self, config_store: ConfigStore):
        self.config_store = config_store
        self.cache_store = CacheStore(config_store.cache_dir)
        self._all_friends_cache: List[Dict[str, Any]] = []

    def _client(self) -> NeteaseApiClient:
        return NeteaseApiClient(self.config_store.load())

    @staticmethod
    def _extract_user_uid(user: Dict[str, Any]) -> str:
        return str(user.get("userId") or user.get("id") or "").strip()

    @staticmethod
    def _extract_user_name(user: Dict[str, Any], fallback_uid: str) -> str:
        nickname = str(user.get("nickname") or user.get("name") or "").strip()
        return nickname or f"好友{fallback_uid}"

    @staticmethod
    def _extract_avatar_url(user: Dict[str, Any]) -> str:
        return str(user.get("avatarUrl") or user.get("avatar") or "").strip()

    def _fetch_all_follow_users(self, uid: str, page_size: int = 100) -> List[Dict[str, Any]]:
        client = self._client()
        users: List[Dict[str, Any]] = []
        offset = 0
        seen_uids: Set[str] = set()
        while True:
            page = client.get_user_follows_page(uid=uid, limit=page_size, offset=offset)
            page_users = page.get("users") or []
            if not page_users:
                break
            for item in page_users:
                item_uid = self._extract_user_uid(item)
                if item_uid and item_uid not in seen_uids:
                    seen_uids.add(item_uid)
                    users.append(item)
            if not page.get("more") or len(page_users) < page_size:
                break
            offset += page_size
        return users

    def _fetch_all_followed_users(self, uid: str, page_size: int = 100) -> List[Dict[str, Any]]:
        client = self._client()
        users: List[Dict[str, Any]] = []
        offset = 0
        seen_uids: Set[str] = set()
        while True:
            page = client.get_user_followeds_page(uid=uid, limit=page_size, offset=offset)
            page_users = page.get("users") or []
            if not page_users:
                break
            for item in page_users:
                item_uid = self._extract_user_uid(item)
                if item_uid and item_uid not in seen_uids:
                    seen_uids.add(item_uid)
                    users.append(item)
            if not page.get("more") or len(page_users) < page_size:
                break
            offset += page_size
        return users

    def get_all_mutual_friends(self, force_refresh: bool = False) -> List[FriendEntry]:
        if self._all_friends_cache and not force_refresh:
            return [self._to_friend_entry(item) for item in self._all_friends_cache]

        login_status = self._client().get_login_status()
        self_uid = str(login_status.get("user_id") or "").strip()
        if not self_uid:
            raise NeteaseApiError("未获取到当前登录账号 UID，无法读取好友列表。")

        follows = self._fetch_all_follow_users(self_uid)
        followeds = self._fetch_all_followed_users(self_uid)
        followed_uid_set = {self._extract_user_uid(item) for item in followeds if self._extract_user_uid(item)}
        mutual_friends: List[Dict[str, Any]] = []
        for item in follows:
            friend_uid = self._extract_user_uid(item)
            if not friend_uid or friend_uid not in followed_uid_set:
                continue
            mutual_friends.append(
                {
                    "uid": friend_uid,
                    "friend_name": self._extract_user_name(item, friend_uid),
                    "avatar_url": self._extract_avatar_url(item),
                }
            )

        mutual_friends.sort(key=lambda item: (item["friend_name"].lower(), item["uid"]))
        self._all_friends_cache = mutual_friends
        return [self._to_friend_entry(item) for item in mutual_friends]

    def get_recent_friends(self) -> List[FriendEntry]:
        return [self._to_friend_entry(item) for item in self.cache_store.read_recent_friends()]

    def remember_friend(self, uid: str, nickname: str, avatar_url: str = "") -> List[FriendEntry]:
        recent = self.cache_store.touch_recent_friend(uid=uid, friend_name=nickname, avatar_url=avatar_url)
        return [self._to_friend_entry(item) for item in recent]

    def pin_recent_friend(self, uid: str) -> List[FriendEntry]:
        return [self._to_friend_entry(item) for item in self.cache_store.pin_recent_friend(uid)]

    def unpin_recent_friend(self, uid: str) -> List[FriendEntry]:
        return [self._to_friend_entry(item) for item in self.cache_store.unpin_recent_friend(uid)]

    def delete_recent_friend(self, uid: str) -> List[FriendEntry]:
        return [self._to_friend_entry(item) for item in self.cache_store.delete_recent_friend(uid)]

    def clear_recent_friends(self) -> List[FriendEntry]:
        return [self._to_friend_entry(item) for item in self.cache_store.clear_recent_friends()]

    def search_friends(self, friends: List[FriendEntry], keyword: str) -> List[FriendEntry]:
        text = (keyword or "").strip().lower()
        if not text:
            return friends
        return [
            item
            for item in friends
            if text in item.nickname.lower() or text in item.uid.lower()
        ]

    def resolve_friend_profile(self, uid: str) -> FriendEntry:
        cached = next((item for item in self.get_recent_friends() if item.uid == uid), None)
        if cached:
            return cached
        for item in self.get_all_mutual_friends():
            if item.uid == uid:
                return item
        profile = self._client().get_user_detail(uid)
        return FriendEntry(
            uid=uid,
            nickname=str(profile.get("nickname") or f"好友{uid}"),
            avatar_url=str(profile.get("avatarUrl") or ""),
        )

    @staticmethod
    def _to_friend_entry(payload: Dict[str, Any]) -> FriendEntry:
        return FriendEntry(
            uid=str(payload.get("uid") or ""),
            nickname=str(payload.get("friend_name") or payload.get("nickname") or ""),
            avatar_url=str(payload.get("avatar_url") or ""),
            last_used_at=str(payload.get("last_used_at") or ""),
            is_pinned=bool(payload.get("is_pinned", False)),
        )
