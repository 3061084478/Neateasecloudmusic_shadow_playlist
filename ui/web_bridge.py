from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from PySide6 import QtCore, QtGui

from core.app_controller import AppController
from core.models import FriendEntry


def _json_ok(data: Any) -> str:
    return json.dumps({"ok": True, "data": data}, ensure_ascii=False)


def _json_error(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, ensure_ascii=False)


class WebBridge(QtCore.QObject):
    def __init__(self, controller: AppController, parent: QtCore.QObject | None = None):
        super().__init__(parent)
        self.controller = controller
        self.active_route = "home"
        self.logs: List[str] = []
        self.last_error = ""
        self.qr_key = ""
        self.qr_url = ""
        self.qr_status = "idle"
        self.qr_image_data_url = ""

    def _append_log(self, message: str) -> None:
        text = str(message or "").strip()
        if not text:
            return
        stamped = f"[{time.strftime('%H:%M:%S')}] {text}"
        self.logs.insert(0, stamped)
        self.logs = self.logs[:80]

    def _set_error(self, message: str) -> None:
        self.last_error = str(message or "").strip()
        if self.last_error:
            self._append_log(self.last_error)

    @staticmethod
    def _friend_to_dict(friend: FriendEntry | None) -> Dict[str, Any] | None:
        if friend is None:
            return None
        return {
            "uid": friend.uid,
            "nickname": friend.nickname,
            "avatarUrl": friend.avatar_url,
            "lastUsedAt": friend.last_used_at,
            "isPinned": friend.is_pinned,
        }

    def _visible_friends_payload(self) -> Dict[str, Any]:
        return {
            "activeListType": self.controller.friend_sidebar_state.active_list_type,
            "searchKeyword": self.controller.friend_sidebar_state.search_keyword,
            "selectedFriendUid": self.controller.friend_sidebar_state.selected_friend_uid,
            "pinnedFriendUids": list(self.controller.friend_sidebar_state.pinned_friend_uids),
            "items": [self._friend_to_dict(item) for item in self.controller.get_visible_friends()],
            "recentCount": len(self.controller.recent_friends),
            "allCount": len(self.controller.all_friends),
        }

    def _shell_payload(self) -> Dict[str, Any]:
        state = self.controller.session_state
        return {
            "activeRoute": self.active_route,
            "connection": {
                "mode": state.mode,
                "apiStatus": state.api_status,
                "cookieStatus": state.cookie_status,
            },
            "account": {
                "userId": state.account_profile.user_id,
                "nickname": state.account_profile.nickname,
                "avatarUrl": state.account_profile.avatar_url,
            },
            "currentFriend": self._friend_to_dict(self.controller.current_friend()),
            "shadowPlaylist": {
                "playlistId": state.current_shadow_playlist.playlist_id,
                "name": state.current_shadow_playlist.name,
                "strategy": state.current_shadow_playlist.strategy,
                "isPrivate": state.current_shadow_playlist.is_private,
                "lastSetAt": state.current_shadow_playlist.last_set_at,
                "statusText": state.current_shadow_playlist.status_text,
            },
            "friendRail": self._visible_friends_payload(),
        }

    def _settings_payload(self) -> Dict[str, Any]:
        state = self.controller.session_state
        return {
            "connection": {
                "mode": state.mode,
                "apiStatus": state.api_status,
                "cookieStatus": state.cookie_status,
                "accountNickname": state.account_profile.nickname or "未登录",
                "shadowPlaylistName": state.current_shadow_playlist.name or "未设置目标歌单",
            },
            "aiSettings": self.controller.get_ai_settings(),
            "qr": {
                "status": self.qr_status,
                "url": self.qr_url,
                "imageDataUrl": self.qr_image_data_url,
            },
            "diagnostics": {
                "logs": list(self.logs),
                "lastError": self.last_error,
                "reportDirectory": self.controller.report_directory(),
            },
        }

    def _clear_qr_session(self, status: str = "idle") -> None:
        self.qr_key = ""
        self.qr_url = ""
        self.qr_status = status
        self.qr_image_data_url = ""

    def _ensure_qr_session(self) -> None:
        if self.qr_key and self.qr_status in {"ready", "waiting-scan", "waiting-confirm"} and self.qr_image_data_url:
            return
        payload = self.controller.bootstrap.create_qr_session()
        self.qr_key = str(payload.get("key") or "")
        self.qr_url = str(payload.get("qr_url") or "")
        self.qr_status = "ready"
        self.qr_image_data_url = self._pixmap_to_data_url(self.controller.bootstrap.build_qr_pixmap(self.qr_url))

    def _refresh_runtime_state(
        self,
        fetch_account_profile: bool = True,
        fetch_shadow_playlist: bool = False,
        load_friends: bool = True,
    ):
        state = self.controller.refresh_session_state(
            fetch_account_profile=fetch_account_profile,
            fetch_shadow_playlist=fetch_shadow_playlist,
        )
        if state.mode == "real" and load_friends:
            try:
                friends = self.controller.load_all_friends(force_refresh=False)
                self.controller.apply_all_friends(friends)
            except Exception as exc:
                self._set_error(str(exc))
        return state

    def _startup_payload(self) -> Dict[str, Any]:
        state = self.controller.session_state
        is_authenticated = state.mode == "real" and state.api_status == "online" and state.cookie_status == "valid"
        has_qr = bool(self.qr_key and self.qr_status in {"ready", "waiting-scan", "waiting-confirm"})
        return {
            "connection": {
                "mode": state.mode,
                "apiStatus": state.api_status,
                "cookieStatus": state.cookie_status,
                "accountNickname": state.account_profile.nickname or "未登录",
            },
            "qr": {
                "status": self.qr_status,
                "url": self.qr_url,
                "imageDataUrl": self.qr_image_data_url,
            },
            "diagnostics": {
                "logs": list(self.logs),
                "lastError": self.last_error,
            },
            "startup": {
                "isAuthenticated": is_authenticated,
                "canAutoEnter": is_authenticated,
                "hasQr": has_qr,
            },
            "shell": self._shell_payload(),
        }

    def _find_friend(self, uid: str) -> FriendEntry | None:
        uid_text = str(uid or "").strip()
        if not uid_text:
            return None
        current = self.controller.current_friend()
        if current and current.uid == uid_text:
            return current
        for source in (self.controller.recent_friends, self.controller.all_friends):
            for friend in source:
                if friend.uid == uid_text:
                    return friend
        if self.controller.session_state.mode == "real" and not self.controller.all_friends:
            try:
                friends = self.controller.load_all_friends(force_refresh=False)
                self.controller.apply_all_friends(friends)
            except Exception:
                return None
            for friend in self.controller.all_friends:
                if friend.uid == uid_text:
                    return friend
        return None

    def _ensure_friend(self, uid: str) -> None:
        if not uid:
            return
        friend = self._find_friend(uid)
        if friend is None:
            raise ValueError("未找到对应好友。")
        self.controller.select_friend(friend)

    @staticmethod
    def _parse_json_arg(raw: str | None) -> Dict[str, Any]:
        if not raw:
            return {}
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _pixmap_to_data_url(pixmap: QtGui.QPixmap | None) -> str:
        if pixmap is None or pixmap.isNull():
            return ""
        buffer = QtCore.QBuffer()
        buffer.open(QtCore.QIODevice.WriteOnly)
        pixmap.save(buffer, "PNG")
        encoded = bytes(buffer.data().toBase64()).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    @QtCore.Slot(result=str)
    def getShellPayload(self) -> str:
        return _json_ok(self._shell_payload())

    @QtCore.Slot(result=str)
    def getStartupPayload(self) -> str:
        try:
            state = self._refresh_runtime_state(fetch_account_profile=True, fetch_shadow_playlist=False, load_friends=True)
            if state.mode == "real":
                self._clear_qr_session("idle")
            elif state.api_status != "online":
                self._clear_qr_session("idle")
            self._append_log("已同步启动状态。")
            return _json_ok(self._startup_payload())
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(bool, result=str)
    def probeStartupStatus(self, reveal_qr_if_missing: bool) -> str:
        try:
            state = self._refresh_runtime_state(fetch_account_profile=True, fetch_shadow_playlist=False, load_friends=True)
            if state.mode == "real":
                self._clear_qr_session("idle")
                self._append_log("检测到有效登录态。")
            elif state.api_status != "online":
                self._clear_qr_session("idle")
                self._append_log("未检测到可用 API。")
            elif reveal_qr_if_missing:
                self._ensure_qr_session()
                self._append_log("未检测到 cookie，已准备二维码。")
            else:
                self._append_log("已重新检测 API / Cookie 状态。")
            return _json_ok(self._startup_payload())
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(result=str)
    def runStartupPrimaryAction(self) -> str:
        try:
            self.controller.bootstrap.ensure_api_ready()
            state = self._refresh_runtime_state(fetch_account_profile=True, fetch_shadow_playlist=False, load_friends=True)
            if state.mode == "real":
                self._clear_qr_session("idle")
                self._append_log("启动流程已确认登录态有效。")
            else:
                self._ensure_qr_session()
                self._append_log("API 已就绪，未检测到 cookie，已生成二维码。")
            return _json_ok(self._startup_payload())
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(result=str)
    def refreshShellState(self) -> str:
        try:
            state = self.controller.build_session_state(True, True)
            self.controller.apply_session_state(state)
            if state.mode == "real":
                try:
                    friends = self.controller.load_all_friends(force_refresh=False)
                    self.controller.apply_all_friends(friends)
                except Exception as exc:
                    self._set_error(str(exc))
            self._append_log("已刷新应用状态。")
            return _json_ok(self._shell_payload())
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, result=str)
    def navigate(self, route: str) -> str:
        self.active_route = str(route or "home").strip() or "home"
        return _json_ok({"route": self.active_route})

    @QtCore.Slot(str, result=str)
    def selectFriend(self, uid: str) -> str:
        try:
            self._ensure_friend(uid)
            self._append_log("已切换当前好友。")
            return _json_ok(self._shell_payload())
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, str, result=str)
    def listFriends(self, list_type: str, keyword: str) -> str:
        try:
            self.controller.set_friend_list_type(str(list_type or "all"))
            self.controller.set_friend_search_keyword(str(keyword or ""))
            if self.controller.friend_sidebar_state.active_list_type == "all" and not self.controller.all_friends and self.controller.session_state.mode == "real":
                friends = self.controller.load_all_friends(force_refresh=False)
                self.controller.apply_all_friends(friends)
            return _json_ok(self._visible_friends_payload())
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, result=str)
    def pinFriend(self, uid: str) -> str:
        try:
            self.controller.pin_friend(uid)
            self._append_log("已置顶好友。")
            return _json_ok(self._shell_payload())
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, result=str)
    def unpinFriend(self, uid: str) -> str:
        try:
            self.controller.unpin_friend(uid)
            self._append_log("已取消置顶好友。")
            return _json_ok(self._shell_payload())
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, result=str)
    def deleteRecentFriend(self, uid: str) -> str:
        try:
            self.controller.delete_recent_friend(uid)
            self._append_log("已删除最近好友记录。")
            return _json_ok(self._shell_payload())
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(result=str)
    def clearRecentFriends(self) -> str:
        try:
            self.controller.clear_recent_friends()
            self._append_log("已清空最近好友列表。")
            return _json_ok(self._shell_payload())
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(result=str)
    def getHomePayload(self) -> str:
        try:
            return _json_ok(self.controller.get_home_snapshot())
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, result=str)
    def querySongShares(self, filters_json: str) -> str:
        try:
            payload = self.controller.query_song_shares(**self._parse_json_arg(filters_json))
            return _json_ok(payload)
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, int, result=str)
    def getSongActiveDates(self, scope: str, pages: int) -> str:
        try:
            return _json_ok(self.controller.get_song_active_dates(scope=scope, pages=pages))
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, result=str)
    def queryChatHistory(self, filters_json: str) -> str:
        try:
            payload = self.controller.query_chat_history(**self._parse_json_arg(filters_json))
            return _json_ok(payload)
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, int, result=str)
    def getChatActiveDates(self, scope: str, pages: int) -> str:
        try:
            return _json_ok(self.controller.get_chat_active_dates(scope=scope, pages=pages))
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(result=str)
    def getShadowPayload(self) -> str:
        try:
            return _json_ok(
                {
                    "status": self.controller.get_shadow_status_snapshot(),
                    "candidates": list(self.controller.shadow_candidates),
                    "selectedCandidateIds": list(self.controller.selected_candidate_ids),
                    "currentFriend": self._friend_to_dict(self.controller.current_friend()),
                }
            )
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(result=str)
    def listOwnedPlaylists(self) -> str:
        try:
            return _json_ok(self.controller.list_owned_playlists())
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, result=str)
    def saveShadowTarget(self, payload_json: str) -> str:
        try:
            result = self.controller.save_shadow_playlist_selection(**self._parse_json_arg(payload_json))
            self._append_log("已保存目标歌单设置。")
            return _json_ok(result)
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, result=str)
    def loadShadowCandidates(self, filters_json: str) -> str:
        try:
            result = self.controller.load_shadow_candidates(**self._parse_json_arg(filters_json))
            self._append_log("已刷新候选歌曲。")
            return _json_ok(result)
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, bool, result=str)
    def toggleCandidateSelection(self, msg_id: str, checked: bool) -> str:
        try:
            self.controller.toggle_candidate_selection(str(msg_id), bool(checked))
            return _json_ok({"selectedCandidateIds": list(self.controller.selected_candidate_ids)})
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, result=str)
    def bulkSelectShadowCandidates(self, mode: str) -> str:
        try:
            normalized = str(mode or "").strip().lower()
            if normalized == "all":
                self.controller.set_all_candidates_selected(True)
            elif normalized == "none":
                self.controller.set_all_candidates_selected(False)
            else:
                self.controller.invert_candidate_selection()
            return _json_ok({"selectedCandidateIds": list(self.controller.selected_candidate_ids)})
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, result=str)
    def generateShadowPlaylist(self, payload_json: str) -> str:
        try:
            payload = self._parse_json_arg(payload_json)
            result = self.controller.generate_shadow_playlist(
                payload.get("max_gap_hours"),
                payload.get("max_songs"),
            )
            self._append_log("已生成影子歌单。")
            return _json_ok(
                {
                    "result": result,
                    "status": self.controller.get_shadow_status_snapshot(),
                }
            )
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(result=str)
    def getShadowStatus(self) -> str:
        try:
            return _json_ok(self.controller.get_shadow_status_snapshot())
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, bool, result=str)
    def getRelationPayload(self, window: str, force: bool) -> str:
        try:
            payload = self.controller.get_relation_dashboard_payload(window=window or "all", force=bool(force))
            return _json_ok(payload)
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, str, str, result=str)
    def generateFriendAi(self, uid: str, mode: str, window: str) -> str:
        try:
            self._ensure_friend(uid)
            return _json_ok(self.controller.generate_friend_insight(mode=mode or "rational", window=window or "all"))
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, str, result=str)
    def generateSelfAi(self, mode: str, window: str) -> str:
        try:
            return _json_ok(self.controller.generate_self_insight(mode=mode or "rational", window=window or "all"))
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, str, str, result=str)
    def exportFriendReport(self, uid: str, mode: str, window: str) -> str:
        try:
            self._ensure_friend(uid)
            result = self.controller.export_friend_report(mode=mode or "rational", window=window or "all")
            self._append_log("已导出好友报告。")
            return _json_ok(result)
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, str, result=str)
    def exportSelfReport(self, mode: str, window: str) -> str:
        try:
            result = self.controller.export_self_report(mode=mode or "rational", window=window or "all")
            self._append_log("已导出个人报告。")
            return _json_ok(result)
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, str, result=str)
    def exportAnnualReport(self, mode: str, window: str) -> str:
        try:
            result = self.controller.export_annual_report(mode=mode or "annual", window=window or "year")
            self._append_log("已导出年度回顾。")
            return _json_ok(result)
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, str, result=str)
    def listRelationReports(self, report_type: str, keyword: str) -> str:
        try:
            mapping = {
                "全部报告": "all",
                "好友报告": "friend",
                "个人报告": "self",
                "年度回顾": "annual",
            }
            normalized = mapping.get(report_type, report_type or "all")
            return _json_ok(self.controller.list_relation_reports(limit=40, report_type=normalized, keyword=keyword or ""))
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(result=str)
    def cleanupRelationReports(self) -> str:
        try:
            result = self.controller.cleanup_relation_reports()
            self._append_log("已清理失效报告记录。")
            return _json_ok(result)
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, result=str)
    def openReport(self, path: str) -> str:
        try:
            target = str(path or "").strip()
            opened = False
            if target:
                url = QtCore.QUrl.fromLocalFile(target) if os.path.exists(target) else QtCore.QUrl(target)
                opened = QtGui.QDesktopServices.openUrl(url)
            return _json_ok({"opened": opened})
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(result=str)
    def openReportDirectory(self) -> str:
        try:
            directory = self.controller.report_directory()
            opened = QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(directory))
            return _json_ok({"opened": opened, "path": directory})
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(result=str)
    def getSettingsPayload(self) -> str:
        try:
            return _json_ok(self._settings_payload())
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(str, result=str)
    def saveAiSettings(self, payload_json: str) -> str:
        try:
            payload = self._parse_json_arg(payload_json)
            saved = self.controller.save_ai_settings(
                ai_enabled=bool(payload.get("ai_enabled", False)),
                ai_base_url=str(payload.get("ai_base_url") or ""),
                ai_model=str(payload.get("ai_model") or ""),
                ai_api_key=str(payload.get("ai_api_key") or ""),
                ai_timeout=int(payload.get("ai_timeout") or 20),
            )
            self._append_log("已保存 AI 配置。")
            return _json_ok(saved)
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(result=str)
    def detectApi(self) -> str:
        try:
            state = self._refresh_runtime_state(fetch_account_profile=False, fetch_shadow_playlist=False, load_friends=False)
            ready = state.api_status == "online"
            self._append_log("API 状态：在线" if ready else "API 状态：离线")
            return _json_ok({"ready": ready, "startup": self._startup_payload(), "settings": self._settings_payload(), "shell": self._shell_payload()})
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(result=str)
    def startApi(self) -> str:
        try:
            self.controller.bootstrap.ensure_api_ready()
            self._refresh_runtime_state(fetch_account_profile=False, fetch_shadow_playlist=False, load_friends=False)
            self._append_log("已尝试启动本地 API。")
            return _json_ok({"startup": self._startup_payload(), "settings": self._settings_payload(), "shell": self._shell_payload()})
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(result=str)
    def detectCookie(self) -> str:
        try:
            state = self._refresh_runtime_state(fetch_account_profile=True, fetch_shadow_playlist=False, load_friends=True)
            valid = state.mode == "real"
            if valid:
                self._clear_qr_session("idle")
            self._append_log("Cookie 状态：有效" if valid else "Cookie 状态：无效")
            return _json_ok({"valid": valid, "startup": self._startup_payload(), "settings": self._settings_payload(), "shell": self._shell_payload()})
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(result=str)
    def startQrLogin(self) -> str:
        try:
            self._ensure_qr_session()
            self._append_log("已生成二维码。")
            return _json_ok({"startup": self._startup_payload(), "settings": self._settings_payload(), "shell": self._shell_payload()})
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(result=str)
    def pollQrStatus(self) -> str:
        try:
            if not self.qr_key:
                raise ValueError("当前没有可轮询的二维码会话。")
            payload = self.controller.bootstrap.check_qr_session(self.qr_key)
            code = int(payload.get("code") or 0)
            if code == 801:
                self.qr_status = "waiting-scan"
            elif code == 802:
                self.qr_status = "waiting-confirm"
            elif code == 803:
                self.qr_status = "success"
                self._refresh_runtime_state(fetch_account_profile=True, fetch_shadow_playlist=False, load_friends=True)
            elif code == 800:
                self.qr_status = "expired"
            self._append_log(f"二维码状态：{code}")
            return _json_ok({"code": code, "startup": self._startup_payload(), "settings": self._settings_payload(), "shell": self._shell_payload()})
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(result=str)
    def clearCookie(self) -> str:
        try:
            self.controller.bootstrap.clear_saved_cookie()
            self.controller.apply_initial_local_state()
            self._clear_qr_session("idle")
            self._append_log("已清空本地 Cookie。")
            return _json_ok({"startup": self._startup_payload(), "settings": self._settings_payload(), "shell": self._shell_payload()})
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(result=str)
    def requestFullArchiveRebuild(self) -> str:
        try:
            result = self.controller.ensure_global_archive_ready(force_full=True)
            friends = result.get("friends")
            if isinstance(friends, list):
                self.controller.apply_all_friends(friends)
            response = dict(result)
            response.pop("friends", None)
            self._append_log("已执行全量归档重建。")
            return _json_ok(response)
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))

    @QtCore.Slot(result=str)
    def requestGlobalArchiveSync(self) -> str:
        try:
            result = self.controller.archive_all_friends_from_cursors()
            friends = result.get("friends")
            if isinstance(friends, list):
                self.controller.apply_all_friends(friends)
            response = dict(result)
            response.pop("friends", None)
            self._append_log("已执行全好友归档。")
            return _json_ok(response)
        except Exception as exc:
            self._set_error(str(exc))
            return _json_error(str(exc))
