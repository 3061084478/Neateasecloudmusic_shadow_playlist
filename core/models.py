from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FriendEntry:
    uid: str
    nickname: str
    avatar_url: str = ""
    last_used_at: str = ""
    is_pinned: bool = False


@dataclass
class AccountProfile:
    user_id: str = ""
    nickname: str = ""
    avatar_url: str = ""


@dataclass
class ShadowPlaylistSummary:
    playlist_id: str = ""
    name: str = ""
    strategy: str = "use_existing"
    is_private: bool = False
    last_set_at: str = ""
    status_text: str = "尚未设置目标歌单"


@dataclass
class AppSessionState:
    mode: str = "mock"
    api_status: str = "unknown"
    cookie_status: str = "unknown"
    account_profile: AccountProfile = field(default_factory=AccountProfile)
    current_friend: Optional[FriendEntry] = None
    current_shadow_playlist: ShadowPlaylistSummary = field(default_factory=ShadowPlaylistSummary)


@dataclass
class FriendSidebarState:
    active_list_type: str = "all"
    search_keyword: str = ""
    selected_friend_uid: str = ""
    pinned_friend_uids: List[str] = field(default_factory=list)


@dataclass
class QueryResult:
    items: List[Dict[str, Any]]
    summary: Dict[str, Any]
    state: str = "success"
    message: str = ""
