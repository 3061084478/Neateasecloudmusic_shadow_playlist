from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from PySide6 import QtCore

from core.models import AccountProfile, AppSessionState, FriendEntry, FriendSidebarState, ShadowPlaylistSummary
from services.analytics_service import AnalyticsService
from core.startup_bootstrap import StartupBootstrap
from services.chat_service import ChatService
from services.config_store import ConfigStore
from services.friend_service import FriendService
from services.insight_service import InsightService
from services.netease_api import NeteaseApiError
from services.playlist_service import PlaylistService
from services.report_service import ReportService
from services.sequence_builder import build_sequence


class AppController(QtCore.QObject):
    state_changed = QtCore.Signal()
    friend_lists_changed = QtCore.Signal()

    def __init__(self, workspace_root: str, config_path: str | None = None, bundle_root: str | None = None):
        super().__init__()
        self.config_store = ConfigStore(workspace_root=workspace_root, config_path=config_path, bundle_root=bundle_root)
        self.bootstrap = StartupBootstrap(self.config_store)
        self.friend_service = FriendService(self.config_store)
        self.chat_service = ChatService(self.config_store)
        self.playlist_service = PlaylistService(self.config_store)
        self.analytics_service = AnalyticsService(self.config_store)
        self.insight_service = InsightService()
        self.report_service = ReportService(self.config_store)

        self.session_state = AppSessionState()
        self.friend_sidebar_state = FriendSidebarState()
        self.all_friends: List[FriendEntry] = []
        self.recent_friends: List[FriendEntry] = []
        self.shadow_candidates: List[Dict[str, Any]] = []
        self.selected_candidate_ids: List[str] = []
        self._relation_cache: Dict[str, Any] = {}
        self._relation_cache_ts = 0.0
        self._relation_cache_window = "all"
        self._relation_cache_uid = ""
        self.apply_initial_local_state()
        self.refresh_friend_lists()

    def _invalidate_relation_cache(self) -> None:
        self._relation_cache = {}
        self._relation_cache_ts = 0.0
        self._relation_cache_window = "all"
        self._relation_cache_uid = ""

    @staticmethod
    def _shadow_summary_from_payload(payload: Dict[str, Any]) -> ShadowPlaylistSummary:
        return ShadowPlaylistSummary(
            playlist_id=str(payload.get("playlist_id") or ""),
            name=str(payload.get("name") or ""),
            strategy=str(payload.get("strategy") or "use_existing"),
            is_private=bool(payload.get("is_private", False)),
            last_set_at=str(payload.get("last_set_at") or ""),
            status_text=str(payload.get("status_text") or "尚未设置目标歌单"),
        )

    def apply_initial_local_state(self) -> AppSessionState:
        self.session_state = AppSessionState(
            mode="mock",
            api_status="unknown",
            cookie_status="unknown",
            account_profile=self.session_state.account_profile,
            current_friend=self.session_state.current_friend,
            current_shadow_playlist=self._shadow_summary_from_payload(
                self.playlist_service.get_local_shadow_playlist_summary()
            ),
        )
        self._invalidate_relation_cache()
        self.state_changed.emit()
        return self.session_state

    def apply_startup_authenticated_state(self) -> AppSessionState:
        self.session_state = AppSessionState(
            mode="real",
            api_status="online",
            cookie_status="valid",
            account_profile=self.session_state.account_profile,
            current_friend=self.session_state.current_friend,
            current_shadow_playlist=self._shadow_summary_from_payload(
                self.playlist_service.get_local_shadow_playlist_summary()
            ),
        )
        self._invalidate_relation_cache()
        self.state_changed.emit()
        return self.session_state

    def build_session_state(self, fetch_account_profile: bool = True, fetch_shadow_playlist: bool = True) -> AppSessionState:
        api_ready = self.bootstrap.is_api_ready()
        cookie_valid = self.bootstrap.is_cookie_valid() if api_ready else False
        mode = "real" if api_ready and cookie_valid else "mock"
        profile = self.session_state.account_profile if cookie_valid else AccountProfile()
        if cookie_valid:
            if fetch_account_profile:
                try:
                    account = self.bootstrap.get_account_profile()
                    profile = AccountProfile(
                        user_id=str(account.get("user_id") or ""),
                        nickname=str(account.get("nickname") or ""),
                        avatar_url=str(account.get("avatar_url") or ""),
                    )
                except NeteaseApiError:
                    profile = self.session_state.account_profile

        shadow = self.playlist_service.get_local_shadow_playlist_summary()
        if api_ready and cookie_valid and fetch_shadow_playlist:
            shadow = self.playlist_service.get_shadow_playlist_summary(validate_remote=True, ensure_exists=False)

        return AppSessionState(
            mode=mode,
            api_status="online" if api_ready else "offline",
            cookie_status="valid" if cookie_valid else "invalid",
            account_profile=profile,
            current_friend=self.session_state.current_friend,
            current_shadow_playlist=self._shadow_summary_from_payload(shadow),
        )

    def apply_session_state(self, state: AppSessionState) -> AppSessionState:
        self.session_state = state
        self._invalidate_relation_cache()
        self.state_changed.emit()
        return self.session_state

    def refresh_session_state(self, fetch_account_profile: bool = True, fetch_shadow_playlist: bool = True) -> AppSessionState:
        return self.apply_session_state(
            self.build_session_state(
                fetch_account_profile=fetch_account_profile,
                fetch_shadow_playlist=fetch_shadow_playlist,
            )
        )

    def refresh_friend_lists(self, force_all_refresh: bool = False) -> None:
        try:
            self.recent_friends = self.friend_service.get_recent_friends()
            if force_all_refresh and self.session_state.mode == "real":
                self.all_friends = self.friend_service.get_all_mutual_friends(force_refresh=True)
        except NeteaseApiError:
            self.recent_friends = self.friend_service.get_recent_friends()
            self.all_friends = []
        self.friend_sidebar_state.pinned_friend_uids = [item.uid for item in self.recent_friends if item.is_pinned]
        if not self.session_state.current_friend:
            default_friend = self.recent_friends[0] if self.recent_friends else (self.all_friends[0] if self.all_friends else None)
            if default_friend:
                self.session_state.current_friend = default_friend
                self.friend_sidebar_state.selected_friend_uid = default_friend.uid
        self.friend_lists_changed.emit()
        self._invalidate_relation_cache()
        self.state_changed.emit()

    def load_all_friends(self, force_refresh: bool = False) -> List[FriendEntry]:
        if self.session_state.mode != "real":
            return []
        return self.friend_service.get_all_mutual_friends(force_refresh=force_refresh)

    def apply_all_friends(self, friends: List[FriendEntry]) -> None:
        self.all_friends = friends
        if not self.session_state.current_friend and friends:
            self.session_state.current_friend = friends[0]
            self.friend_sidebar_state.selected_friend_uid = friends[0].uid
        self.friend_lists_changed.emit()
        self._invalidate_relation_cache()
        self.state_changed.emit()

    def get_visible_friends(self) -> List[FriendEntry]:
        source = (
            self._decorate_all_friends(self.all_friends)
            if self.friend_sidebar_state.active_list_type == "all"
            else self.recent_friends
        )
        return self.friend_service.search_friends(source, self.friend_sidebar_state.search_keyword)

    def _decorate_all_friends(self, friends: List[FriendEntry]) -> List[FriendEntry]:
        pinned_set = {item.uid for item in self.recent_friends if item.is_pinned}
        decorated = [
            FriendEntry(
                uid=item.uid,
                nickname=item.nickname,
                avatar_url=item.avatar_url,
                last_used_at=item.last_used_at,
                is_pinned=item.uid in pinned_set,
            )
            for item in friends
        ]
        decorated.sort(key=lambda item: (0 if item.is_pinned else 1, item.nickname.lower(), item.uid))
        return decorated

    def set_friend_list_type(self, list_type: str) -> None:
        self.friend_sidebar_state.active_list_type = list_type
        self.friend_lists_changed.emit()

    def set_friend_search_keyword(self, keyword: str) -> None:
        self.friend_sidebar_state.search_keyword = keyword
        self.friend_lists_changed.emit()

    def select_friend(self, friend: FriendEntry) -> FriendEntry:
        self.session_state.current_friend = friend
        self.friend_sidebar_state.selected_friend_uid = friend.uid
        self.recent_friends = self.friend_service.remember_friend(friend.uid, friend.nickname, friend.avatar_url)
        self.friend_sidebar_state.pinned_friend_uids = [item.uid for item in self.recent_friends if item.is_pinned]
        self.friend_lists_changed.emit()
        self._invalidate_relation_cache()
        self.state_changed.emit()
        return friend

    def pin_friend(self, uid: str) -> None:
        if not uid:
            return
        if not any(item.uid == uid for item in self.recent_friends):
            profile = next((item for item in self.all_friends if item.uid == uid), None)
            if not profile and self.session_state.current_friend and self.session_state.current_friend.uid == uid:
                profile = self.session_state.current_friend
            if profile:
                self.recent_friends = self.friend_service.remember_friend(profile.uid, profile.nickname, profile.avatar_url)
        self.recent_friends = self.friend_service.pin_recent_friend(uid)
        self.friend_sidebar_state.pinned_friend_uids = [item.uid for item in self.recent_friends if item.is_pinned]
        self.friend_lists_changed.emit()
        self._invalidate_relation_cache()
        self.state_changed.emit()

    def pin_current_friend(self) -> None:
        uid = self.friend_sidebar_state.selected_friend_uid or (self.session_state.current_friend.uid if self.session_state.current_friend else "")
        self.pin_friend(uid)

    def unpin_friend(self, uid: str) -> None:
        if not uid:
            return
        self.recent_friends = self.friend_service.unpin_recent_friend(uid)
        self.friend_sidebar_state.pinned_friend_uids = [item.uid for item in self.recent_friends if item.is_pinned]
        self.friend_lists_changed.emit()
        self._invalidate_relation_cache()
        self.state_changed.emit()

    def delete_recent_friend(self, uid: str) -> None:
        if not uid:
            return
        self.recent_friends = self.friend_service.delete_recent_friend(uid)
        if self.session_state.current_friend and self.session_state.current_friend.uid == uid:
            self.session_state.current_friend = self.recent_friends[0] if self.recent_friends else None
        self.friend_lists_changed.emit()
        self._invalidate_relation_cache()
        self.state_changed.emit()

    def delete_current_recent_friend(self) -> None:
        uid = self.friend_sidebar_state.selected_friend_uid
        self.delete_recent_friend(uid)

    def clear_recent_friends(self) -> None:
        self.recent_friends = self.friend_service.clear_recent_friends()
        self.friend_lists_changed.emit()
        self._invalidate_relation_cache()
        self.state_changed.emit()

    def current_friend(self) -> Optional[FriendEntry]:
        return self.session_state.current_friend

    def get_home_snapshot(self) -> Dict[str, Any]:
        friend = self.current_friend()
        friend_uid = friend.uid if friend else ""
        all_messages = self.chat_service.repository.query_messages(friend_uid) if friend_uid else []
        total_chat_count = len(all_messages)
        total_song_share_count = sum(1 for item in all_messages if item.get("msg_type") == "song")
        last_build = self.playlist_service.get_last_build_record() or {}
        playlist_track_count = 0
        if self.session_state.mode == "real" and self.session_state.current_shadow_playlist.playlist_id:
            try:
                playlist_track_count = len(self.playlist_service.get_playlist_state())
            except Exception:
                playlist_track_count = 0
        relation_summary = {
            "friend_top_artist": "暂无",
            "shared_artists": "无",
            "self_social_tag": "暂无",
        }
        if friend_uid:
            try:
                relation_payload = self.get_relation_dashboard_payload(window="all", force=False)
                friend_snapshot = relation_payload.get("friend") or {}
                self_snapshot = relation_payload.get("self") or {}
                shared_rows = (friend_snapshot.get("artist_portrait") or {}).get("shared_top_artists") or []
                relation_summary = {
                    "friend_top_artist": str((((friend_snapshot.get("artist_portrait") or {}).get("friend_top_artists") or [{}])[0].get("name")) or "暂无"),
                    "shared_artists": "、".join(str(item.get("name") or "") for item in shared_rows[:2] if item.get("name")) or "无",
                    "self_social_tag": str(self_snapshot.get("social_tag") or "暂无"),
                }
            except Exception:
                relation_summary = relation_summary
        return {
            "connection": {
                "mode": self.session_state.mode,
                "api_status": self.session_state.api_status,
                "cookie_status": self.session_state.cookie_status,
                "account_status": self.session_state.account_profile.nickname or "未登录",
            },
            "friend": {
                "nickname": friend.nickname if friend else "未选择",
                "uid": friend.uid if friend else "-",
                "avatar_url": friend.avatar_url if friend else "",
                "last_used_at": friend.last_used_at if friend else "",
            },
            "shadow_playlist": {
                "name": self.session_state.current_shadow_playlist.name or "未设置",
                "playlist_id": self.session_state.current_shadow_playlist.playlist_id or "-",
                "strategy": self.session_state.current_shadow_playlist.strategy,
                "is_private": self.session_state.current_shadow_playlist.is_private,
                "last_set_at": self.session_state.current_shadow_playlist.last_set_at or "",
            },
            "overview": {
                "chat_count": total_chat_count,
                "song_share_count": total_song_share_count,
                "candidate_count": len(self.shadow_candidates),
                "last_build_summary": last_build.get("generated_count") or 0,
                "playlist_track_count": playlist_track_count,
            },
            "relation_summary": relation_summary,
        }

    def query_song_shares(self, **filters: Any) -> Dict[str, Any]:
        friend = self.current_friend()
        if not friend:
            raise ValueError("请先选择好友。")
        return self.playlist_service.query_song_shares(uid=friend.uid, **filters)

    def get_song_active_dates(self, scope: str = "all", pages: int = 3) -> List[str]:
        friend = self.current_friend()
        if not friend:
            return []
        return self.playlist_service.list_song_active_dates(friend.uid, scope=scope, pages=pages)

    def query_chat_history(self, **filters: Any) -> Dict[str, Any]:
        friend = self.current_friend()
        if not friend:
            raise ValueError("请先选择好友。")
        return self.chat_service.query_chat_history(uid=friend.uid, **filters)

    def get_chat_active_dates(self, scope: str = "all", pages: int = 3) -> List[str]:
        friend = self.current_friend()
        if not friend:
            return []
        return self.chat_service.list_active_dates(friend.uid, scope=scope, pages=pages)

    def load_shadow_candidates(self, **filters: Any) -> Dict[str, Any]:
        friend = self.current_friend()
        if not friend:
            raise ValueError("请先选择好友。")
        max_gap_hours = filters.pop("max_gap_hours", None)
        max_songs = filters.pop("max_songs", None)
        items = self.playlist_service.list_friend_song_messages(uid=friend.uid, **filters)
        preview_items = items
        if items and (max_gap_hours is not None or max_songs is not None):
            _, preview_items, _, _ = build_sequence(
                song_messages=items,
                anchor_index=0,
                max_gap_hours=max_gap_hours,
                max_songs=max_songs,
            )
        self.shadow_candidates = preview_items
        self.selected_candidate_ids = [item["msg_id"] for item in preview_items]
        self.playlist_service.advance_song_archive_cursor(uid=friend.uid, song_messages=preview_items)
        return {
            "items": preview_items,
            "summary": {
                **self.playlist_service.summarize_song_messages(preview_items),
                "selected_count": len(self.selected_candidate_ids),
                "data_source": self.playlist_service.get_last_song_data_source(),
                "raw_count": len(items),
            },
        }

    def list_owned_playlists(self) -> List[Dict[str, Any]]:
        return self.playlist_service.list_owned_playlists()

    def should_auto_archive_all_friends(self) -> bool:
        payload = self.config_store.load()
        return bool(payload.get("auto_archive_all_friends", True))

    def ensure_global_archive_ready(self, force_full: bool = False) -> Dict[str, Any]:
        if self.session_state.mode != "real":
            return {
                "friends": [],
                "total_friends": 0,
                "full_synced": 0,
                "delta_synced": 0,
                "failed": [],
                "skipped": True,
            }
        friends = self.friend_service.get_all_mutual_friends(force_refresh=True)
        full_synced = 0
        delta_synced = 0
        failed: List[Dict[str, str]] = []
        for friend in friends:
            uid = str(friend.uid or "").strip()
            if not uid:
                continue
            try:
                status = self.chat_service.repository.get_backfill_status(uid)
                if force_full or status is None:
                    self.chat_service.sync_full_history_backfill(uid=uid, limit=50)
                    full_synced += 1
                else:
                    self.chat_service.sync_recent_history_delta(uid=uid, initial_pages=6, limit=50)
                    delta_synced += 1
            except Exception as exc:
                failed.append({"uid": uid, "name": friend.nickname, "error": str(exc)})
        self.config_store.update(
            auto_archive_initialized=True,
            auto_archive_last_run=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
        return {
            "friends": friends,
            "total_friends": len(friends),
            "full_synced": full_synced,
            "delta_synced": delta_synced,
            "failed": failed,
            "skipped": False,
        }

    def archive_all_friends_from_cursors(self, initial_pages: int = 1, limit: int = 50) -> Dict[str, Any]:
        if self.session_state.mode != "real":
            return {
                "friends": [],
                "total_friends": 0,
                "full_synced": 0,
                "delta_synced": 0,
                "failed": [],
                "skipped": True,
            }
        friends = self.friend_service.get_all_mutual_friends(force_refresh=True)
        full_synced = 0
        delta_synced = 0
        failed: List[Dict[str, str]] = []
        for friend in friends:
            uid = str(friend.uid or "").strip()
            if not uid:
                continue
            try:
                latest_archived = self.chat_service.repository.get_latest_message(uid=uid)
                archive_newest_ms = int((latest_archived or {}).get("msg_time_ms") or 0)
                stop_at_ms = max(
                    archive_newest_ms,
                    self.chat_service.get_chat_archive_cursor_ms(uid),
                    self.playlist_service.get_song_archive_cursor_ms(uid),
                )
                if stop_at_ms <= 0:
                    self.chat_service.sync_full_history_backfill(uid=uid, limit=limit)
                    full_synced += 1
                else:
                    self.chat_service.sync_recent_history_delta(
                        uid=uid,
                        initial_pages=initial_pages,
                        limit=limit,
                        stop_at_ms=stop_at_ms,
                    )
                    delta_synced += 1
                self.chat_service.sync_chat_archive_cursor_to_latest_archived(uid)
                self.playlist_service.sync_song_archive_cursor_to_latest_archived(uid)
            except Exception as exc:
                failed.append({"uid": uid, "name": friend.nickname, "error": str(exc)})
        self.config_store.update(
            auto_archive_initialized=True,
            auto_archive_last_run=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
        self._invalidate_relation_cache()
        self.state_changed.emit()
        return {
            "friends": friends,
            "total_friends": len(friends),
            "full_synced": full_synced,
            "delta_synced": delta_synced,
            "failed": failed,
            "skipped": False,
        }

    def _relation_friend_pool(self) -> List[FriendEntry]:
        pool: List[FriendEntry] = []
        seen: set[str] = set()
        for source in (self.recent_friends, self.all_friends):
            for friend in source:
                if friend.uid and friend.uid not in seen:
                    seen.add(friend.uid)
                    pool.append(friend)
        current = self.current_friend()
        if current and current.uid and current.uid not in seen:
            pool.insert(0, current)
        return pool

    def _ensure_relation_seed_data(self, uid: str) -> None:
        if not uid:
            return
        rows = self.analytics_service.query_friend_messages(uid, window="all")
        if rows or self.session_state.mode != "real":
            return
        try:
            self.chat_service.sync_friend_history_pages(uid=uid, pages=6)
        except Exception:
            return

    def get_relation_dashboard_payload(self, window: str = "all", force: bool = False) -> Dict[str, Any]:
        current_uid = self.current_friend().uid if self.current_friend() else ""
        now = time.time()
        if (
            not force
            and self._relation_cache
            and self._relation_cache_window == window
            and self._relation_cache_uid == current_uid
            and now - self._relation_cache_ts < 15
        ):
            return self._relation_cache

        friend_pool = self._relation_friend_pool()
        available_years = self.analytics_service.list_available_years([friend.uid for friend in friend_pool if friend.uid])
        snapshots: List[Dict[str, Any]] = []
        for friend in friend_pool:
            if friend.uid == current_uid:
                self._ensure_relation_seed_data(friend.uid)
            snapshot = self.analytics_service.build_friend_snapshot(
                uid=friend.uid,
                friend_name=friend.nickname,
                window=window,
            )
            snapshot["avatar_url"] = friend.avatar_url
            snapshots.append(snapshot)

        global_snapshot = self.analytics_service.build_global_snapshot(snapshots, window=window)
        self_snapshot = self.analytics_service.build_self_snapshot(
            snapshots,
            global_snapshot,
            account_name=self.session_state.account_profile.nickname or "我",
            window=window,
        )
        year = self.analytics_service._parse_year_window(window)
        annual_review = self.analytics_service.build_annual_review(snapshots, global_snapshot, year=year)
        self_snapshot["account_avatar_url"] = self.session_state.account_profile.avatar_url or ""
        self_snapshot["annual_review"] = annual_review

        snapshot_map = {str(item.get("uid") or ""): item for item in snapshots}
        friend_snapshot = snapshot_map.get(current_uid) if current_uid else None
        if not friend_snapshot:
            friend_snapshot = snapshots[0] if snapshots else self.analytics_service.build_friend_snapshot("", "未选择好友", window=window)
        dual_perspective = self.analytics_service.build_dual_perspective(friend_snapshot, global_snapshot)
        friend_snapshot["dual_perspective"] = dual_perspective
        friend_snapshot["common_world"] = self.analytics_service.build_common_world(friend_snapshot, global_snapshot)

        payload = {
            "overview": global_snapshot,
            "friend": friend_snapshot,
            "self": self_snapshot,
            "similarity": self.analytics_service.build_similarity_matrix(snapshots, top_n=8),
            "friends": snapshots,
            "annual_review": annual_review,
            "available_years": available_years,
        }
        self._relation_cache = payload
        self._relation_cache_ts = now
        self._relation_cache_window = window
        self._relation_cache_uid = current_uid
        return payload

    @staticmethod
    def _normalize_insight_mode(mode: str) -> str:
        normalized = (mode or "").strip().lower()
        if normalized in {"style", "summary", "风格", "风格版", "总结", "总结版"}:
            return "style"
        if normalized in {"commentary", "comment", "评论", "评论版"}:
            return "commentary"
        if normalized in {"annual", "year", "年度", "年度报告", "年度报告版"}:
            return "annual"
        return "rational"

    def generate_friend_insight(self, mode: str = "rational", window: str = "all") -> Dict[str, Any]:
        dashboard = self.get_relation_dashboard_payload(window=window, force=False)
        friend_snapshot = dashboard.get("friend", {})
        ai_payload = self.analytics_service.build_ai_feature_payload(
            friend_snapshot,
            audience_scope="friend",
            period_label=window,
        )
        return self.insight_service.generate_friend_insight(
            ai_payload,
            self._normalize_insight_mode(mode),
            self.config_store.load(),
        )

    def generate_self_insight(self, mode: str = "rational", window: str = "all") -> Dict[str, Any]:
        dashboard = self.get_relation_dashboard_payload(window=window, force=False)
        self_snapshot = dashboard.get("self", {})
        ai_payload = self.analytics_service.build_ai_feature_payload(
            self_snapshot,
            audience_scope="self",
            period_label=window,
        )
        return self.insight_service.generate_self_insight(
            ai_payload,
            self._normalize_insight_mode(mode),
            self.config_store.load(),
        )

    def export_friend_report(self, mode: str = "rational", window: str = "all") -> Dict[str, Any]:
        dashboard = self.get_relation_dashboard_payload(window=window, force=False)
        insight = self.generate_friend_insight(mode=mode, window=window)
        return self.report_service.render_friend_report_png(dashboard.get("friend", {}), insight)

    def export_self_report(self, mode: str = "rational", window: str = "all") -> Dict[str, Any]:
        dashboard = self.get_relation_dashboard_payload(window=window, force=False)
        insight = self.generate_self_insight(mode=mode, window=window)
        return self.report_service.render_self_report_png(dashboard.get("self", {}), insight)

    def export_annual_report(self, mode: str = "annual", window: str = "year") -> Dict[str, Any]:
        dashboard = self.get_relation_dashboard_payload(window=window, force=False)
        annual_snapshot = dict(dashboard.get("annual_review") or {})
        self_snapshot = dict(dashboard.get("self") or {})
        annual_snapshot.setdefault("account_name", self_snapshot.get("account_name") or self.session_state.account_profile.nickname or "我")
        annual_payload = dict(self_snapshot)
        annual_payload["annual_review"] = annual_snapshot
        ai_payload = self.analytics_service.build_ai_feature_payload(
            annual_payload,
            audience_scope="annual",
            period_label=window,
        )
        insight = self.insight_service.generate_self_insight(
            ai_payload,
            self._normalize_insight_mode(mode),
            self.config_store.load(),
        )
        return self.report_service.render_annual_report_png(annual_snapshot, insight)

    def list_relation_reports(self, limit: int = 30, report_type: str = "all", keyword: str = "") -> List[Dict[str, Any]]:
        return self.report_service.list_recent_reports(limit=limit, report_type=report_type, keyword=keyword)

    def cleanup_relation_reports(self) -> Dict[str, int]:
        return self.report_service.prune_missing_reports()

    def report_directory(self) -> str:
        return str(self.report_service.report_dir)

    def get_ai_settings(self) -> Dict[str, Any]:
        payload = self.config_store.load()
        return {
            "ai_enabled": bool(payload.get("ai_enabled", False)),
            "ai_base_url": str(payload.get("ai_base_url") or ""),
            "ai_model": str(payload.get("ai_model") or ""),
            "ai_api_key": str(payload.get("ai_api_key") or ""),
            "ai_timeout": int(payload.get("ai_timeout") or 20),
        }

    def save_ai_settings(
        self,
        ai_enabled: bool,
        ai_base_url: str,
        ai_model: str,
        ai_api_key: str,
        ai_timeout: int,
    ) -> Dict[str, Any]:
        updated = self.config_store.update(
            ai_enabled=bool(ai_enabled),
            ai_base_url=str(ai_base_url or "").strip(),
            ai_model=str(ai_model or "").strip(),
            ai_api_key=str(ai_api_key or "").strip(),
            ai_timeout=max(5, int(ai_timeout)),
        )
        return {
            "ai_enabled": bool(updated.get("ai_enabled", False)),
            "ai_base_url": str(updated.get("ai_base_url") or ""),
            "ai_model": str(updated.get("ai_model") or ""),
            "ai_api_key": str(updated.get("ai_api_key") or ""),
            "ai_timeout": int(updated.get("ai_timeout") or 20),
        }

    def toggle_candidate_selection(self, msg_id: str, checked: bool) -> None:
        if checked and msg_id not in self.selected_candidate_ids:
            self.selected_candidate_ids.append(msg_id)
        if not checked and msg_id in self.selected_candidate_ids:
            self.selected_candidate_ids.remove(msg_id)
        self.state_changed.emit()

    def set_all_candidates_selected(self, selected: bool) -> None:
        self.selected_candidate_ids = [item["msg_id"] for item in self.shadow_candidates] if selected else []
        self.state_changed.emit()

    def invert_candidate_selection(self) -> None:
        current = set(self.selected_candidate_ids)
        self.selected_candidate_ids = [item["msg_id"] for item in self.shadow_candidates if item["msg_id"] not in current]
        self.state_changed.emit()

    def generate_shadow_playlist(self, max_gap_hours: Optional[int], max_songs: Optional[int]) -> Dict[str, Any]:
        friend = self.current_friend()
        if not friend:
            raise ValueError("请先选择好友。")
        if not self.session_state.current_shadow_playlist.playlist_id:
            raise ValueError("当前尚未设置目标歌单，请先在影子歌单设置中指定覆盖目标。")
        selected_items = [item for item in self.shadow_candidates if item["msg_id"] in self.selected_candidate_ids]
        if not selected_items:
            raise ValueError("请至少选择一首候选歌曲。")
        return self.playlist_service.generate_shadow_playlist(
            uid=friend.uid,
            anchor_index=0,
            max_gap_hours=max_gap_hours,
            max_songs=max_songs,
            song_messages=selected_items,
        )

    def get_shadow_status_snapshot(self) -> Dict[str, Any]:
        playlist_summary = {
            "playlist_id": self.session_state.current_shadow_playlist.playlist_id,
            "name": self.session_state.current_shadow_playlist.name,
            "strategy": self.session_state.current_shadow_playlist.strategy,
            "is_private": self.session_state.current_shadow_playlist.is_private,
            "last_set_at": self.session_state.current_shadow_playlist.last_set_at,
            "status_text": self.session_state.current_shadow_playlist.status_text,
        }
        playlist_state = []
        if self.session_state.mode == "real" and self.session_state.current_shadow_playlist.playlist_id:
            try:
                playlist_summary = self.playlist_service.get_shadow_playlist_summary()
                playlist_state = self.playlist_service.get_playlist_state()
            except Exception:
                playlist_state = []
        return {
            "playlist": playlist_summary,
            "last_build": self.playlist_service.get_last_build_record() or {},
            "playlist_state": playlist_state,
            "can_generate": bool(self.session_state.current_shadow_playlist.playlist_id and self.current_friend()),
            "mode": self.session_state.mode,
        }

    def save_shadow_playlist_selection(self, **payload: Any) -> Dict[str, Any]:
        summary = self.playlist_service.save_shadow_playlist_selection(**payload)
        self.session_state.current_shadow_playlist = ShadowPlaylistSummary(
            playlist_id=str(summary.get("playlist_id") or ""),
            name=str(summary.get("name") or ""),
            strategy=str(summary.get("strategy") or "use_existing"),
            is_private=bool(summary.get("is_private", False)),
            last_set_at=str(summary.get("last_set_at") or ""),
            status_text=str(summary.get("status_text") or ""),
        )
        self.state_changed.emit()
        return summary
