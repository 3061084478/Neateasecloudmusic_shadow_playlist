import { useEffect, useMemo, useRef, useState } from "react";
import { FriendListType, ROUTES, RouteKey } from "../constants";
import { Avatar, EmptyState } from "./primitives";

const BRAND_LOGO_SRC = "brand/shadow_brand_mark_trimmed.png";

export function TopBar({
  route,
  railCollapsed,
  onNavigate,
  onToggleRail,
  onRefresh
}: {
  route: RouteKey;
  railCollapsed: boolean;
  onNavigate: (route: RouteKey) => void;
  onToggleRail: () => void;
  onRefresh: () => void;
}) {
  return (
    <header className="topbar">
      <div className="brand-block">
        <div className="brand-logo" aria-label="Shadow">
          <img src={BRAND_LOGO_SRC} alt="Shadow" className="brand-logo-image" />
        </div>
      </div>
      <nav className="topnav">
        {ROUTES.map((item) => (
          <button
            key={item.key}
            className={`nav-pill ${route === item.key ? "is-active" : ""}`}
            onClick={() => onNavigate(item.key)}
          >
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
      <div className="topbar-actions">
        <button className="ghost-button" onClick={onToggleRail}>
          {railCollapsed ? "展开好友栏" : "收起好友栏"}
        </button>
        <button className="primary-button" onClick={onRefresh}>
          刷新当前页
        </button>
      </div>
    </header>
  );
}

export function FriendRail({
  railCollapsed,
  currentFriend,
  friendListType,
  friendKeyword,
  friendRail,
  onToggleListType,
  onKeywordChange,
  onClearRecent,
  onSelectFriend,
  onPinFriend,
  onUnpinFriend,
  onDeleteFriend
}: {
  railCollapsed: boolean;
  currentFriend: any;
  friendListType: FriendListType;
  friendKeyword: string;
  friendRail: any;
  onToggleListType: (listType: FriendListType) => void;
  onKeywordChange: (keyword: string) => void;
  onClearRecent: () => void;
  onSelectFriend: (uid: string) => void;
  onPinFriend: (uid: string) => void;
  onUnpinFriend: (uid: string) => void;
  onDeleteFriend: (uid: string) => void;
}) {
  if (railCollapsed) {
    return null;
  }

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const selectedUid = currentFriend?.uid || "";
  const canPin = Boolean(selectedUid);
  const selectedIsPinned = Boolean(currentFriend?.isPinned);
  const menuItems = useMemo(() => {
    const items: Array<{ key: string; label: string; action: () => void }> = [];
    if (canPin) {
      items.push({
        key: selectedIsPinned ? "unpin" : "pin",
        label: selectedIsPinned ? "取消置顶" : "置顶",
        action: () => {
          if (selectedIsPinned) {
            onUnpinFriend(selectedUid);
          } else {
            onPinFriend(selectedUid);
          }
          setMenuOpen(false);
        }
      });
    }
    if (friendListType === "recent" && selectedUid) {
      items.push({
        key: "delete",
        label: "删除",
        action: () => {
          onDeleteFriend(selectedUid);
          setMenuOpen(false);
        }
      });
    }
    if (friendListType === "recent") {
      items.push({
        key: "clear",
        label: "删除列表",
        action: () => {
          onClearRecent();
          setMenuOpen(false);
        }
      });
    }
    return items;
  }, [canPin, friendListType, onClearRecent, onDeleteFriend, onPinFriend, onUnpinFriend, selectedIsPinned, selectedUid]);

  useEffect(() => {
    if (!menuOpen) {
      return;
    }
    const handlePointerDown = (event: MouseEvent) => {
      if (menuRef.current && event.target instanceof Node && !menuRef.current.contains(event.target)) {
        setMenuOpen(false);
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    };
    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleEscape);
    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [menuOpen]);

  return (
    <aside className={`friend-rail ${railCollapsed ? "is-collapsed" : ""}`}>
      {!railCollapsed ? (
        <>
          <div className="rail-profile-card">
            <Avatar avatarUrl={currentFriend?.avatarUrl || currentFriend?.avatar_url} name={currentFriend?.nickname} size={56} />
            <div className="rail-profile-copy">
              <strong>{currentFriend?.nickname || "未选择好友"}</strong>
              <span>UID {currentFriend?.uid || "-"}</span>
            </div>
          </div>

          <div className="rail-toolbar">
            <div className="segmented">
              <button className={friendListType === "all" ? "is-active" : ""} onClick={() => onToggleListType("all")}>
                全部好友
              </button>
              <button className={friendListType === "recent" ? "is-active" : ""} onClick={() => onToggleListType("recent")}>
                最近好友
              </button>
            </div>
          </div>

          <div className="rail-search-row">
            <input className="rail-search-input" value={friendKeyword} onChange={(event) => onKeywordChange(event.target.value)} placeholder="搜索昵称或 UID" />
            <div className="rail-menu-wrap" ref={menuRef}>
              <button type="button" className="rail-menu-trigger" onClick={() => setMenuOpen((value) => !value)} disabled={!menuItems.length}>
                <span>⚙</span>
              </button>
              {menuOpen && menuItems.length ? (
                <div className="rail-menu">
                  {menuItems.map((item) => (
                    <button key={item.key} type="button" className="rail-menu-item" onClick={item.action}>
                      {item.label}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          </div>

          <div className="friend-list">
            {(friendRail?.items || []).length ? (
              friendRail.items.map((friend: any) => (
                <button
                  key={friend.uid}
                  className={`friend-item ${friend.uid === currentFriend?.uid ? "is-selected" : ""}`}
                  onClick={() => onSelectFriend(friend.uid)}
                >
                  <Avatar avatarUrl={friend.avatarUrl} name={friend.nickname} size={38} />
                  <div className="friend-copy">
                    <strong>{friend.nickname}</strong>
                    <small>{friend.lastUsedAt || friend.uid}</small>
                  </div>
                  {friend.isPinned ? <span className="friend-pin-badge">已置顶</span> : <span className="friend-tail-spacer" />}
                </button>
              ))
            ) : (
              <EmptyState title="当前没有可展示的好友" detail="切换全部 / 最近，或检查是否已经完成启动与好友同步。" />
            )}
          </div>
        </>
      ) : null}
    </aside>
  );
}
