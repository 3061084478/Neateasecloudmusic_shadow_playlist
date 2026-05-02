import { AnimatePresence, motion } from "framer-motion";
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
      <motion.div
        className="shell-slice shell-brand-slice"
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.24, ease: "easeOut" }}
      >
        <div className="brand-block">
          <div className="brand-logo" aria-label="Shadow">
            <img src={BRAND_LOGO_SRC} alt="Shadow" className="brand-logo-image" />
          </div>
        </div>
      </motion.div>

      <motion.div
        className="shell-slice shell-nav-slice"
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.24, delay: 0.04, ease: "easeOut" }}
      >
        <nav className="topnav">
          {ROUTES.map((item) => (
            <motion.button
              key={item.key}
              className={`nav-pill ${route === item.key ? "is-active" : ""}`}
              onClick={() => onNavigate(item.key)}
              whileHover={{ y: -2, scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              transition={{ duration: 0.16, ease: "easeOut" }}
            >
              {route === item.key ? (
                <motion.span
                  layoutId="topnav-active-surface"
                  className="nav-pill-active-surface"
                  transition={{ type: "spring", stiffness: 420, damping: 34 }}
                />
              ) : null}
              <span>{item.label}</span>
            </motion.button>
          ))}
        </nav>
      </motion.div>

      <motion.div
        className="shell-slice shell-actions-slice"
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.24, delay: 0.08, ease: "easeOut" }}
      >
        <div className="topbar-actions">
          <motion.button className="ghost-button" onClick={onToggleRail} whileHover={{ y: -1, scale: 1.02 }} whileTap={{ scale: 0.98 }}>
            {railCollapsed ? "展开好友栏" : "收起好友栏"}
          </motion.button>
          <motion.button className="primary-button" onClick={onRefresh} whileHover={{ y: -1, scale: 1.02 }} whileTap={{ scale: 0.98 }}>
            刷新当前页
          </motion.button>
        </div>
      </motion.div>
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
  onToggleRail,
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
  onToggleRail: () => void;
  onClearRecent: () => void;
  onSelectFriend: (uid: string) => void;
  onPinFriend: (uid: string) => void;
  onUnpinFriend: (uid: string) => void;
  onDeleteFriend: (uid: string) => void;
}) {
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
    <motion.aside
      className={`friend-rail ${railCollapsed ? "is-collapsed" : ""}`}
      layout
      initial={{ opacity: 0, x: -18 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
    >
      {railCollapsed ? (
        <motion.div
          className="rail-collapsed-stack"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
        >
          <motion.button className="rail-collapsed-avatar" onClick={onToggleRail} whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
            <Avatar avatarUrl={currentFriend?.avatarUrl || currentFriend?.avatar_url} name={currentFriend?.nickname} size={44} />
          </motion.button>
          <motion.button className="rail-collapsed-toggle" onClick={onToggleRail} whileHover={{ y: -1 }} whileTap={{ scale: 0.98 }}>
            展开
          </motion.button>
          <div className="rail-collapsed-line" />
        </motion.div>
      ) : (
        <>
          <motion.div className="rail-profile-card" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22, ease: "easeOut" }}>
            <Avatar avatarUrl={currentFriend?.avatarUrl || currentFriend?.avatar_url} name={currentFriend?.nickname} size={56} />
            <div className="rail-profile-copy">
              <strong>{currentFriend?.nickname || "未选择好友"}</strong>
              <span>UID {currentFriend?.uid || "-"}</span>
            </div>
          </motion.div>

          <motion.div className="rail-toolbar" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22, delay: 0.04, ease: "easeOut" }}>
            <div className="segmented">
              <button className={friendListType === "all" ? "is-active" : ""} onClick={() => onToggleListType("all")}>
                全部好友
              </button>
              <button className={friendListType === "recent" ? "is-active" : ""} onClick={() => onToggleListType("recent")}>
                最近好友
              </button>
            </div>
          </motion.div>

          <motion.div className="rail-search-row" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22, delay: 0.08, ease: "easeOut" }}>
            <input className="rail-search-input" value={friendKeyword} onChange={(event) => onKeywordChange(event.target.value)} placeholder="搜索昵称或 UID" />
            <div className="rail-menu-wrap" ref={menuRef}>
              <button type="button" className="rail-menu-trigger" onClick={() => setMenuOpen((value) => !value)} disabled={!menuItems.length}>
                <span>⚙</span>
              </button>
              <AnimatePresence>
                {menuOpen && menuItems.length ? (
                  <motion.div
                    className="rail-menu"
                    initial={{ opacity: 0, y: 8, scale: 0.96 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 6, scale: 0.98 }}
                    transition={{ duration: 0.16, ease: "easeOut" }}
                  >
                    {menuItems.map((item) => (
                      <motion.button key={item.key} type="button" className="rail-menu-item" onClick={item.action} whileHover={{ x: 2 }} whileTap={{ scale: 0.99 }}>
                        {item.label}
                      </motion.button>
                    ))}
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </div>
          </motion.div>

          <motion.div
            className="friend-list"
            initial="hidden"
            animate="show"
            variants={{
              hidden: {},
              show: {
                transition: {
                  staggerChildren: 0.035,
                  delayChildren: 0.1
                }
              }
            }}
          >
            {(friendRail?.items || []).length ? (
              friendRail.items.map((friend: any) => (
                <motion.button
                  key={friend.uid}
                  className={`friend-item ${friend.uid === currentFriend?.uid ? "is-selected" : ""}`}
                  onClick={() => onSelectFriend(friend.uid)}
                  variants={{
                    hidden: { opacity: 0, x: -12 },
                    show: { opacity: 1, x: 0, transition: { duration: 0.2, ease: "easeOut" } }
                  }}
                  whileHover={{ x: 2, y: -1 }}
                  whileTap={{ scale: 0.992 }}
                  layout
                >
                  <Avatar avatarUrl={friend.avatarUrl} name={friend.nickname} size={38} />
                  <div className="friend-copy">
                    <strong>{friend.nickname}</strong>
                    <small>{friend.lastUsedAt || friend.uid}</small>
                  </div>
                  {friend.isPinned ? <span className="friend-pin-badge">已置顶</span> : <span className="friend-tail-spacer" />}
                </motion.button>
              ))
            ) : (
              <EmptyState title="当前没有可展示的好友" detail="切换全部 / 最近，或检查是否已经完成启动与好友同步。" />
            )}
          </motion.div>
        </>
      )}
    </motion.aside>
  );
}
