import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import { initBridge, invokeBridge } from "./bridge";
import {
  FriendListType,
  RelationTab,
  RouteKey,
  ROUTES,
  ShadowTab
} from "./constants";
import { FriendRail, TopBar } from "./components/shell";
import { EmptyState } from "./components/primitives";
import { HomeRoute } from "./routes/HomeRoute";
import { SongRoute } from "./routes/SongRoute";
import { ChatRoute } from "./routes/ChatRoute";
import { ShadowRoute } from "./routes/ShadowRoute";
import { RelationRoute } from "./routes/RelationRoute";
import { SettingsRoute } from "./routes/SettingsRoute";

const ROUTE_ORDER: RouteKey[] = ["home", "song", "shadow", "chat", "relation", "settings"];

type ShellButterflyRole = "hero" | "support";

const SHELL_BUTTERFLIES: Array<{ role: ShellButterflyRole; src: string; style: CSSProperties }> = [
  {
    role: "hero",
    src: "brand/scene_butterfly_1.png",
    style: {
      "--x": "75.2%",
      "--y": "19.9%",
      "--size": "144px",
      "--rotation": "-13deg",
      "--blur": "0.8px",
      "--opacity": "0.48",
      "--brightness": "0.76",
      "--contrast": "1.05",
      "--rim-light": "0.28",
      "--silhouette-strength": "0.26",
      "--halo-opacity": "0.16",
      "--lift": "-1px"
    } as CSSProperties
  },
  {
    role: "support",
    src: "brand/scene_butterfly_2.png",
    style: {
      "--x": "58.8%",
      "--y": "41.6%",
      "--size": "130px",
      "--rotation": "9deg",
      "--blur": "1.2px",
      "--opacity": "0.56",
      "--brightness": "0.79",
      "--contrast": "1.04",
      "--rim-light": "0.3",
      "--silhouette-strength": "0.36",
      "--halo-opacity": "0.18",
      "--lift": "1px"
    } as CSSProperties
  },
  {
    role: "support",
    src: "brand/scene_butterfly_3.png",
    style: {
      "--x": "35.8%",
      "--y": "69.2%",
      "--size": "116px",
      "--rotation": "14deg",
      "--blur": "1.9px",
      "--opacity": "0.5",
      "--brightness": "0.77",
      "--contrast": "1.03",
      "--rim-light": "0.24",
      "--silhouette-strength": "0.42",
      "--halo-opacity": "0.16",
      "--lift": "4px"
    } as CSSProperties
  }
];

const routeStageVariants = {
  initial: (direction: number) => ({
    opacity: 0,
    x: direction >= 0 ? 52 : -52,
    y: 10,
    scale: 0.986
  }),
  animate: {
    opacity: 1,
    x: 0,
    y: 0,
    scale: 1,
    transition: {
      duration: 0.28,
      ease: [0.22, 1, 0.36, 1]
    }
  },
  exit: (direction: number) => ({
    opacity: 0,
    x: direction >= 0 ? -40 : 40,
    y: -8,
    scale: 0.982,
    transition: {
      duration: 0.2,
      ease: [0.4, 0, 1, 1]
    }
  })
};

function App() {
  const [bridgeReady, setBridgeReady] = useState(false);
  const [bootError, setBootError] = useState("");
  const [shell, setShell] = useState<any>(null);
  const [route, setRoute] = useState<RouteKey>("home");
  const [routeDirection, setRouteDirection] = useState(1);
  const [railCollapsed, setRailCollapsed] = useState(false);
  const [friendListType, setFriendListType] = useState<FriendListType>("recent");
  const [friendKeyword, setFriendKeyword] = useState("");
  const [, setBusyLabel] = useState("");
  const [toast, setToast] = useState("");

  const [homePayload, setHomePayload] = useState<any>(null);
  const [songResult, setSongResult] = useState<any>(null);
  const [songActiveDates, setSongActiveDates] = useState<string[]>([]);
  const [chatResult, setChatResult] = useState<any>(null);
  const [chatActiveDates, setChatActiveDates] = useState<string[]>([]);
  const [shadowPayload, setShadowPayload] = useState<any>(null);
  const [shadowOwnedPlaylists, setShadowOwnedPlaylists] = useState<any[]>([]);
  const [shadowTab, setShadowTab] = useState<ShadowTab>("selector");
  const [relationPayload, setRelationPayload] = useState<any>(null);
  const [relationTab, setRelationTab] = useState<RelationTab>("overview");
  const [relationWindowMode, setRelationWindowMode] = useState<"all" | "year">("all");
  const [relationYear, setRelationYear] = useState("");
  const [friendInsight, setFriendInsight] = useState<any>(null);
  const [selfInsight, setSelfInsight] = useState<any>(null);
  const [reports, setReports] = useState<any[]>([]);
  const [reportType, setReportType] = useState("all");
  const [reportKeyword, setReportKeyword] = useState("");
  const [settingsPayload, setSettingsPayload] = useState<any>(null);
  const [qrPolling, setQrPolling] = useState(false);

  const [songFilters, setSongFilters] = useState({
    scope: "recent",
    pages: 3,
    sender_scope: "all",
    query_mode: "all",
    target_date: "",
    start_date: "",
    end_date: "",
    keyword: ""
  });

  const [chatFilters, setChatFilters] = useState({
    scope: "recent",
    pages: 3,
    sender_scope: "all",
    message_type: "all",
    query_mode: "all",
    target_date: "",
    start_datetime: "",
    end_datetime: "",
    keyword: ""
  });

  const [shadowSelectorForm, setShadowSelectorForm] = useState({
    strategy: "use_existing",
    selected_playlist_id: "",
    manual_playlist_id: "",
    new_playlist_name: "",
    is_private: false
  });

  const [shadowGenerateFilters, setShadowGenerateFilters] = useState({
    scope: "recent",
    max_pages: 3,
    sender_scope: "all",
    query_mode: "all",
    start_date: "",
    end_date: "",
    keyword: "",
    max_songs: ""
  });

  const [friendAiMode, setFriendAiMode] = useState("rational");
  const [selfAiMode, setSelfAiMode] = useState("rational");
  const [settingsForm, setSettingsForm] = useState({
    ai_enabled: false,
    ai_base_url: "",
    ai_model: "",
    ai_api_key: "",
    ai_timeout: 20
  });

  const currentFriend = shell?.currentFriend;
  const friendRail = shell?.friendRail;
  const routeMeta = ROUTES.find((item) => item.key === route) || ROUTES[0];
  const relationWindow = relationWindowMode === "year" && relationYear ? `year:${relationYear}` : "all";
  const selectedCandidateIds = new Set<string>(shadowPayload?.selectedCandidateIds || []);
  const routeRef = useRef<RouteKey>("home");
  const portalTarget = typeof document !== "undefined" ? document.body : null;

  useEffect(() => {
    routeRef.current = route;
  }, [route]);

  useEffect(() => {
    let active = true;
    const boot = async () => {
      try {
        await initBridge();
        if (!active) {
          return;
        }
        setBridgeReady(true);
        const shellPayload = await invokeBridge<any>("getShellPayload");
        if (!active) {
          return;
        }
        applyShellPayload(shellPayload);
        await loadHomePayload();
      } catch (error) {
        if (!active) {
          return;
        }
        setBootError(error instanceof Error ? error.message : "Web Shell 启动失败。");
      }
    };
    window.__shadowReload = boot;
    void boot();
    return () => {
      active = false;
      delete window.__shadowReload;
    };
  }, []);

  useEffect(() => {
    if (!bridgeReady || route !== "song") {
      return;
    }
    void loadSongActiveDateList(songFilters.scope, songFilters.pages);
  }, [bridgeReady, route, songFilters.scope, songFilters.pages]);

  useEffect(() => {
    if (!bridgeReady || route !== "chat") {
      return;
    }
    void loadChatActiveDateList(chatFilters.scope, chatFilters.pages);
  }, [bridgeReady, route, chatFilters.scope, chatFilters.pages]);

  useEffect(() => {
    if (!bridgeReady || route !== "shadow" || shadowTab !== "generator") {
      return;
    }
    void loadSongActiveDateList(shadowGenerateFilters.scope, shadowGenerateFilters.max_pages);
  }, [bridgeReady, route, shadowTab, shadowGenerateFilters.scope, shadowGenerateFilters.max_pages]);

  useEffect(() => {
    if (!bridgeReady || route !== "shadow" || shadowTab !== "status") {
      return;
    }
    if (shadowPayload?.status) {
      return;
    }
    void handleRefreshShadowStatus();
  }, [bridgeReady, route, shadowTab, shadowPayload?.status]);

  useEffect(() => {
    if (!bridgeReady || route === "relation") {
      return;
    }
    void ensureRouteData(route, false);
  }, [bridgeReady, route]);

  useEffect(() => {
    if (!bridgeReady || route !== "relation") {
      return;
    }
    if (relationWindowMode === "year" && !relationYear) {
      return;
    }
    void loadRelationPayload(true);
    void loadReports();
  }, [bridgeReady, route, relationWindowMode, relationYear]);

  useEffect(() => {
    if (!qrPolling || route !== "settings") {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const result = await invokeBridge<any>("pollQrStatus");
        if (result?.settings) {
          applySettingsPayload(result.settings);
        }
        if (result?.shell) {
          applyShellPayload(result.shell);
        }
        const status = result?.settings?.qr?.status;
        if (status === "success" || status === "expired" || status === "idle") {
          setQrPolling(false);
          void loadHomePayload();
        }
      } catch (error) {
        setToast(error instanceof Error ? error.message : "二维码轮询失败。");
        setQrPolling(false);
      }
    }, 2400);
    return () => window.clearInterval(timer);
  }, [qrPolling, route]);

  useEffect(() => {
    if (!toast) {
      return;
    }
    const timer = window.setTimeout(() => {
      setToast("");
    }, 5000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  async function runBusy<T>(label: string, task: () => Promise<T>): Promise<T | undefined> {
    setBusyLabel(label);
    try {
      return await task();
    } catch (error) {
      setToast(error instanceof Error ? error.message : "操作失败。");
      return undefined;
    } finally {
      setBusyLabel("");
    }
  }

  function invalidateData() {
    setHomePayload(null);
    setSongResult(null);
    setChatResult(null);
    setShadowPayload(null);
    setRelationPayload(null);
    setFriendInsight(null);
    setSelfInsight(null);
  }

  function applyShellPayload(payload: any) {
    setShell(payload);
    updateRoute((payload?.activeRoute as RouteKey) || "home");
    setFriendListType((payload?.friendRail?.activeListType as FriendListType) || "recent");
    setFriendKeyword(String(payload?.friendRail?.searchKeyword || ""));
  }

  function updateRoute(nextRoute: RouteKey) {
    const currentRoute = routeRef.current;
    if (currentRoute !== nextRoute) {
      const currentIndex = ROUTE_ORDER.indexOf(currentRoute);
      const nextIndex = ROUTE_ORDER.indexOf(nextRoute);
      setRouteDirection(nextIndex >= currentIndex ? 1 : -1);
      routeRef.current = nextRoute;
    }
    setRoute(nextRoute);
  }

  function applySettingsPayload(payload: any) {
    setSettingsPayload(payload);
    const ai = payload?.aiSettings || {};
    setSettingsForm({
      ai_enabled: Boolean(ai.ai_enabled),
      ai_base_url: String(ai.ai_base_url || ""),
      ai_model: String(ai.ai_model || ""),
      ai_api_key: String(ai.ai_api_key || ""),
      ai_timeout: Number(ai.ai_timeout || 20)
    });
  }

  async function loadHomePayload(force = false) {
    if (homePayload && !force) {
      return;
    }
    setHomePayload(await invokeBridge<any>("getHomePayload"));
  }

  async function loadSongActiveDateList(scope: string, pages: number) {
    const normalizedScope = scope === "all" ? "all" : scope === "pages" ? "pages" : scope === "incremental" ? "incremental" : "recent";
    setSongActiveDates((await invokeBridge<string[]>("getSongActiveDates", normalizedScope, pages)) || []);
  }

  async function loadChatActiveDateList(scope: string, pages: number) {
    const normalizedScope = scope === "all" ? "all" : scope === "pages" ? "pages" : scope === "incremental" ? "incremental" : "recent";
    setChatActiveDates((await invokeBridge<string[]>("getChatActiveDates", normalizedScope, pages)) || []);
  }

  async function loadShadowPayload(force = false) {
    if (shadowPayload && !force) {
      return;
    }
    setShadowPayload(await invokeBridge<any>("getShadowPayload"));
  }

  async function loadRelationPayload(force = false) {
    if (relationPayload && !force) {
      return;
    }
    const payload = await invokeBridge<any>("getRelationPayload", relationWindow, force);
    setRelationPayload(payload);
    const years = payload?.available_years || [];
    if (!relationYear && years.length) {
      setRelationYear(String(years[years.length - 1]));
    }
  }

  async function loadSettings(force = false) {
    if (settingsPayload && !force) {
      return;
    }
    applySettingsPayload(await invokeBridge<any>("getSettingsPayload"));
  }

  async function loadReports() {
    const typeMap: Record<string, string> = {
      all: "全部报告",
      friend: "好友报告",
      self: "个人报告",
      annual: "年度回顾"
    };
    setReports((await invokeBridge<any[]>("listRelationReports", typeMap[reportType] || "全部报告", reportKeyword)) || []);
  }

  async function ensureRouteData(nextRoute: RouteKey, force = false) {
    if (nextRoute === "home") {
      await loadHomePayload(force);
    } else if (nextRoute === "shadow") {
      await loadShadowPayload(force);
    } else if (nextRoute === "relation") {
      await loadRelationPayload(force);
      await loadReports();
    } else if (nextRoute === "settings") {
      await loadSettings(force);
    }
  }

  async function handleNavigate(nextRoute: RouteKey) {
    if (nextRoute === route) {
      return;
    }
    await runBusy(`切换到${ROUTES.find((item) => item.key === nextRoute)?.label || nextRoute}`, async () => {
      await invokeBridge("navigate", nextRoute);
      updateRoute(nextRoute);
      await ensureRouteData(nextRoute, false);
    });
  }

  async function handleRefreshShell() {
    await runBusy("刷新当前状态", async () => {
      const payload = await invokeBridge<any>("refreshShellState");
      applyShellPayload(payload);
      invalidateData();
      await Promise.all([loadHomePayload(true), ensureRouteData(route, true)]);
      setToast("当前状态已刷新。");
    });
  }

  async function handleFriendRailUpdate(nextListType: FriendListType, nextKeyword: string) {
    const payload = await invokeBridge<any>("listFriends", nextListType, nextKeyword);
    setShell((prev: any) => (prev ? { ...prev, friendRail: payload } : prev));
    setFriendListType(nextListType);
    setFriendKeyword(nextKeyword);
  }

  async function handleSelectFriend(uid: string) {
    await runBusy("切换好友", async () => {
      const payload = await invokeBridge<any>("selectFriend", uid);
      applyShellPayload(payload);
      invalidateData();
      setSongResult(null);
      setChatResult(null);
      await Promise.all([loadHomePayload(true), ensureRouteData(route, true)]);
      setToast("当前好友已切换。");
    });
  }

  async function mutateFriend(method: "pinFriend" | "unpinFriend" | "deleteRecentFriend", uid: string) {
    applyShellPayload(await invokeBridge<any>(method, uid));
  }

  async function handleSongQuery() {
    await runBusy("查询歌曲分享", async () => {
      const payload = await invokeBridge<any>("querySongShares", JSON.stringify(songFilters));
      setSongResult(payload);
      setToast(`歌曲分享已返回 ${payload?.summary?.count || 0} 条结果。`);
    });
  }

  async function handleChatQuery() {
    await runBusy("查询聊天记录", async () => {
      const payload = await invokeBridge<any>("queryChatHistory", JSON.stringify(chatFilters));
      setChatResult(payload);
      setToast(`聊天记录已返回 ${payload?.summary?.count || 0} 条结果。`);
    });
  }

  async function handleLoadOwnedPlaylists() {
    setShadowOwnedPlaylists((await invokeBridge<any[]>("listOwnedPlaylists")) || []);
  }

  async function handleSaveShadowTarget() {
    await runBusy("保存影子歌单目标", async () => {
      await invokeBridge<any>("saveShadowTarget", JSON.stringify(shadowSelectorForm));
      const [shellPayload, shadowData] = await Promise.all([invokeBridge<any>("getShellPayload"), invokeBridge<any>("getShadowStatus")]);
      applyShellPayload(shellPayload);
      setShadowPayload((prev: any) => (prev ? { ...prev, status: shadowData } : prev));
      setToast("目标歌单设置已保存。");
    });
  }

  async function handleLoadShadowCandidates() {
    const payload = {
      max_pages: shadowGenerateFilters.max_pages,
      fetch_all: shadowGenerateFilters.scope === "all",
      scope: shadowGenerateFilters.scope === "all" ? "all" : shadowGenerateFilters.scope,
      sender_scope: shadowGenerateFilters.sender_scope,
      keyword: shadowGenerateFilters.keyword || null,
      start_date:
        shadowGenerateFilters.query_mode === "date" || shadowGenerateFilters.query_mode === "range"
          ? shadowGenerateFilters.start_date || null
          : null,
      end_date:
        shadowGenerateFilters.query_mode === "date" || shadowGenerateFilters.query_mode === "range"
          ? shadowGenerateFilters.end_date || null
          : null,
      incremental_feature_scope: shadowGenerateFilters.scope === "incremental" ? "playlist_generation" : null,
      max_gap_hours: null,
      max_songs: shadowGenerateFilters.max_songs ? Number(shadowGenerateFilters.max_songs) : null
    };
    await runBusy("加载候选歌曲", async () => {
      const result = await invokeBridge<any>("loadShadowCandidates", JSON.stringify(payload));
      setShadowPayload((prev: any) => ({
        ...(prev || {}),
        candidates: result?.items || [],
        selectedCandidateIds: (result?.items || []).map((item: any) => String(item.msg_id)),
        lastCandidateSummary: result?.summary || {},
        currentFriend: shell?.currentFriend
      }));
      setToast(`候选歌曲已刷新，当前 ${result?.summary?.count || 0} 首。`);
    });
  }

  async function handleToggleCandidate(msgId: string, checked: boolean) {
    const result = await invokeBridge<any>("toggleCandidateSelection", msgId, checked);
    setShadowPayload((prev: any) => (prev ? { ...prev, selectedCandidateIds: result?.selectedCandidateIds || [] } : prev));
  }

  async function handleBulkCandidate(mode: "all" | "none" | "invert") {
    const result = await invokeBridge<any>("bulkSelectShadowCandidates", mode);
    setShadowPayload((prev: any) => (prev ? { ...prev, selectedCandidateIds: result?.selectedCandidateIds || [] } : prev));
  }

  async function handleGenerateShadowPlaylist() {
    await runBusy("生成影子歌单", async () => {
      const payload = await invokeBridge<any>("generateShadowPlaylist", JSON.stringify({
        max_gap_hours: null,
        max_songs: shadowGenerateFilters.max_songs ? Number(shadowGenerateFilters.max_songs) : null
      }));
      const status = payload?.status || (await invokeBridge<any>("getShadowStatus"));
      setShadowPayload((prev: any) => (prev ? { ...prev, status } : { status }));
      setShadowTab("status");
      setToast(`影子歌单已生成 ${payload?.result?.generated_count || 0} 首歌曲。`);
    });
  }

  async function handleRefreshShadowStatus() {
    const status = await invokeBridge<any>("getShadowStatus");
    setShadowPayload((prev: any) => (prev ? { ...prev, status } : { status }));
  }

  async function handleRelationRefresh(force = true) {
    await runBusy("刷新音乐关系", async () => {
      const payload = await invokeBridge<any>("getRelationPayload", relationWindow, force);
      setRelationPayload(payload);
      await loadReports();
      setToast("音乐关系已刷新。");
    });
  }

  async function handleGlobalArchiveSync() {
    await runBusy("全好友归档", async () => {
      const payload = await invokeBridge<any>("requestGlobalArchiveSync");
      invalidateData();
      await Promise.all([loadHomePayload(true), loadRelationPayload(true)]);
      const failedCount = Array.isArray(payload?.failed) ? payload.failed.length : 0;
      if (failedCount > 0) {
        setToast(`全好友归档完成，失败 ${failedCount} 位。`);
        return;
      }
      setToast(`全好友归档完成，补齐 ${payload?.delta_synced || 0} 位，首次归档 ${payload?.full_synced || 0} 位。`);
    });
  }

  async function handleGenerateFriendAi() {
    if (!currentFriend?.uid) {
      setToast("请先选择好友。");
      return;
    }
    await runBusy("生成好友 AI 文段", async () => {
      const payload = await invokeBridge<any>("generateFriendAi", currentFriend.uid, friendAiMode, relationWindow);
      setFriendInsight(payload);
      setToast("好友 AI 文段已生成。");
    });
  }

  async function handleGenerateSelfAi() {
    await runBusy("生成社交 AI 文段", async () => {
      const payload = await invokeBridge<any>("generateSelfAi", selfAiMode, relationWindow);
      setSelfInsight(payload);
      setToast("音乐社交 AI 文段已生成。");
    });
  }

  async function handleExportFriendReport() {
    if (!currentFriend?.uid) {
      setToast("请先选择好友。");
      return;
    }
    await runBusy("导出好友报告", async () => {
      const payload = await invokeBridge<any>("exportFriendReport", currentFriend.uid, friendAiMode, relationWindow);
      setToast(`好友报告已导出：${payload?.path || ""}`);
      await loadReports();
      setRelationTab("reports");
    });
  }

  async function handleExportSelfReport() {
    await runBusy("导出个人报告", async () => {
      const payload = await invokeBridge<any>("exportSelfReport", selfAiMode, relationWindow);
      setToast(`个人报告已导出：${payload?.path || ""}`);
      await loadReports();
      setRelationTab("reports");
    });
  }

  async function handleExportAnnualReport() {
    await runBusy("导出年度报告", async () => {
      const payload = await invokeBridge<any>("exportAnnualReport", "annual", relationWindow);
      setToast(`年度回顾已导出：${payload?.path || ""}`);
      await loadReports();
      setRelationTab("reports");
    });
  }

  async function handleSaveSettings() {
    await runBusy("保存 AI 配置", async () => {
      const payload = await invokeBridge<any>("saveAiSettings", JSON.stringify(settingsForm));
      setSettingsForm({
        ai_enabled: Boolean(payload.ai_enabled),
        ai_base_url: String(payload.ai_base_url || ""),
        ai_model: String(payload.ai_model || ""),
        ai_api_key: String(payload.ai_api_key || ""),
        ai_timeout: Number(payload.ai_timeout || 20)
      });
      applySettingsPayload(await invokeBridge<any>("getSettingsPayload"));
      setToast("AI 配置已保存。");
    });
  }

  async function handleSettingsAction(method: string, successText: string) {
    await runBusy(successText, async () => {
      const payload = await invokeBridge<any>(method);
      if (payload?.settings) {
        applySettingsPayload(payload.settings);
      } else if (payload?.connection || payload?.diagnostics) {
        applySettingsPayload(payload);
      }
      if (payload?.shell) {
        applyShellPayload(payload.shell);
      }
      if (method === "startQrLogin") {
        setQrPolling(true);
      }
      invalidateData();
      setToast(successText);
    });
  }

  const homeCards = useMemo(() => {
    const friendSummary = homePayload?.friend || {};
    const playlistSummary = homePayload?.shadow_playlist || {};
    const overview = homePayload?.overview || {};
    const relationSummary = homePayload?.relation_summary || {};
    return [
      {
        title: "歌曲分享",
        summary: "查询分享歌曲",
        detail: `${overview.song_share_count || 0} 首`,
        actions: [{ label: "进入", onClick: () => void handleNavigate("song") }],
      },
      {
        title: "影子歌单",
        summary: playlistSummary.name || "未设置歌单",
        detail: `${overview.playlist_track_count || 0} 首`,
        actions: [{ label: "进入", onClick: () => void handleNavigate("shadow") }],
      },
      {
        title: "聊天记录",
        summary: "查询特定筛选条件下的聊天内容",
        detail: `${overview.chat_count || 0} 条`,
        actions: [{ label: "进入", onClick: () => void handleNavigate("chat") }],
      },
      {
        title: "音乐关系",
        summary: `共同歌手：${relationSummary.shared_artists || "无"}`,
        detail: `我的社交标签：${relationSummary.self_social_tag || "暂无"}`,
        actions: [
          { label: "单好友画像", onClick: () => { setRelationTab("friend"); void handleNavigate("relation"); } },
          { label: "我的音乐社交", onClick: () => { setRelationTab("self"); void handleNavigate("relation"); } },
        ],
      }
    ];
  }, [homePayload]);

  if (bootError) {
    return <div className="boot-state">{bootError}</div>;
  }

  if (!bridgeReady || !shell) {
    return <div className="boot-state">Shadow Web Shell 正在连接桌面壳…</div>;
  }

  return (
    <div className="app-shell">
      <div className="shell-butterfly-layer" aria-hidden="true">
        {SHELL_BUTTERFLIES.map((butterfly, index) => (
          <span key={`${butterfly.src}-${index}`} className={`shell-butterfly is-${butterfly.role}`} style={butterfly.style}>
            <img className="shell-butterfly-shadow" src={butterfly.src} alt="" />
            <img className="shell-butterfly-rim" src={butterfly.src} alt="" />
            <img className="shell-butterfly-body" src={butterfly.src} alt="" />
          </span>
        ))}
      </div>

      <TopBar route={route} railCollapsed={railCollapsed} onNavigate={(next) => void handleNavigate(next)} onToggleRail={() => setRailCollapsed((value) => !value)} onRefresh={() => void handleRefreshShell()} />

      <div className={`shell-body ${railCollapsed ? "is-rail-collapsed" : ""}`}>
        <FriendRail
          railCollapsed={railCollapsed}
          currentFriend={currentFriend}
          friendListType={friendListType}
          friendKeyword={friendKeyword}
          friendRail={friendRail}
          onToggleListType={(listType) => void handleFriendRailUpdate(listType, friendKeyword)}
          onKeywordChange={(keyword) => void handleFriendRailUpdate(friendListType, keyword)}
          onToggleRail={() => setRailCollapsed(false)}
          onClearRecent={() => void invokeBridge("clearRecentFriends").then(applyShellPayload)}
          onSelectFriend={(uid) => void handleSelectFriend(uid)}
          onPinFriend={(uid) => void mutateFriend("pinFriend", uid)}
          onUnpinFriend={(uid) => void mutateFriend("unpinFriend", uid)}
          onDeleteFriend={(uid) => void mutateFriend("deleteRecentFriend", uid)}
        />

        <motion.main className="main-stage" layout transition={{ duration: 0.28, ease: "easeOut" }}>
          <div className="main-stage-slice">
            <div className="stage-header">
              <div className="stage-header-copy">
                <div className="stage-title-row">
                  <h1>{routeMeta.label}</h1>
                </div>
              </div>
              {route === "relation" ? (
                <div className="stage-header-actions">
                  <button className="secondary-button" onClick={() => void handleGlobalArchiveSync()}>
                    全好友归档
                  </button>
                  <button className="secondary-button" onClick={() => void handleRelationRefresh(true)}>
                    刷新分析
                  </button>
                </div>
              ) : null}
            </div>

            <div className="route-viewport">
              <AnimatePresence mode="wait" initial={false} custom={routeDirection}>
                <motion.section
                  key={route}
                  className="page-section route-stage"
                  custom={routeDirection}
                  variants={routeStageVariants}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                >
                  {route === "home" ? <HomeRoute shell={shell} currentFriend={currentFriend} homeCards={homeCards} /> : null}
                  {route === "song" ? (
                    <SongRoute
                      songFilters={songFilters}
                      setSongFilters={setSongFilters}
                      songResult={songResult}
                      songActiveDates={songActiveDates}
                      hasQueried={songResult !== null}
                      onQuery={() => void handleSongQuery()}
                      onReset={() => {
                        setSongFilters({ scope: "recent", pages: 3, sender_scope: "all", query_mode: "all", target_date: "", start_date: "", end_date: "", keyword: "" });
                        setSongResult(null);
                      }}
                    />
                  ) : null}
                  {route === "chat" ? (
                    <ChatRoute
                      chatFilters={chatFilters}
                      setChatFilters={setChatFilters}
                      chatResult={chatResult}
                      chatActiveDates={chatActiveDates}
                      hasQueried={chatResult !== null}
                      onQuery={() => void handleChatQuery()}
                      onReset={() => {
                        setChatFilters({ scope: "recent", pages: 3, sender_scope: "all", message_type: "all", query_mode: "all", target_date: "", start_datetime: "", end_datetime: "", keyword: "" });
                        setChatResult(null);
                      }}
                    />
                  ) : null}
                  {route === "shadow" ? (
                    <ShadowRoute
                      shell={shell}
                      shadowPayload={shadowPayload}
                      shadowOwnedPlaylists={shadowOwnedPlaylists}
                      songActiveDates={songActiveDates}
                      shadowTab={shadowTab}
                      setShadowTab={setShadowTab}
                    shadowSelectorForm={shadowSelectorForm}
                    setShadowSelectorForm={setShadowSelectorForm}
                    shadowGenerateFilters={shadowGenerateFilters}
                    setShadowGenerateFilters={setShadowGenerateFilters}
                    selectedCandidateIds={selectedCandidateIds}
                    onLoadOwnedPlaylists={() => void handleLoadOwnedPlaylists()}
                    onSaveTarget={() => void handleSaveShadowTarget()}
                    onLoadCandidates={() => void handleLoadShadowCandidates()}
                    onToggleCandidate={(msgId, checked) => void handleToggleCandidate(msgId, checked)}
                      onBulkCandidate={(mode) => void handleBulkCandidate(mode)}
                      onGenerate={() => void handleGenerateShadowPlaylist()}
                      onRefreshStatus={() => void handleRefreshShadowStatus()}
                    />
                  ) : null}
                  {route === "relation" ? (
                    <RelationRoute
                      relationPayload={relationPayload}
                      relationTab={relationTab}
                      setRelationTab={setRelationTab}
                      relationWindowMode={relationWindowMode}
                      setRelationWindowMode={setRelationWindowMode}
                      relationYear={relationYear}
                      setRelationYear={setRelationYear}
                      friendAiMode={friendAiMode}
                      setFriendAiMode={setFriendAiMode}
                      selfAiMode={selfAiMode}
                      setSelfAiMode={setSelfAiMode}
                      friendInsight={friendInsight}
                      selfInsight={selfInsight}
                      reports={reports}
                      reportType={reportType}
                      setReportType={setReportType}
                      reportKeyword={reportKeyword}
                      setReportKeyword={setReportKeyword}
                      currentFriend={currentFriend}
                      onRefresh={() => void handleRelationRefresh(true)}
                      onGenerateFriendAi={() => void handleGenerateFriendAi()}
                      onGenerateSelfAi={() => void handleGenerateSelfAi()}
                      onExportFriendReport={() => void handleExportFriendReport()}
                      onExportSelfReport={() => void handleExportSelfReport()}
                      onExportAnnualReport={() => void handleExportAnnualReport()}
                      onLoadReports={() => void loadReports()}
                      onCleanupReports={() => void invokeBridge<any>("cleanupRelationReports").then(() => { setToast("已清理失效报告。"); void loadReports(); })}
                      onOpenReport={(path) => void invokeBridge("openReport", path)}
                      onOpenReportDirectory={() => void invokeBridge("openReportDirectory")}
                    />
                  ) : null}
                  {route === "settings" ? (
                    <SettingsRoute
                      settingsPayload={settingsPayload}
                      settingsForm={settingsForm}
                      setSettingsForm={setSettingsForm}
                      onAction={(method, successText) => void handleSettingsAction(method, successText)}
                      onSave={() => void handleSaveSettings()}
                      onRefresh={() => void loadSettings(true)}
                      onOpenReportDirectory={() => void invokeBridge("openReportDirectory")}
                    />
                  ) : null}
                  {!["home", "song", "chat", "shadow", "relation", "settings"].includes(route) ? (
                    <EmptyState title="当前路由未就绪" detail="这个页面还没有被绑定到 Web Shell。继续推进时我会把它接进统一壳层。" />
                  ) : null}
                </motion.section>
              </AnimatePresence>
            </div>
          </div>
        </motion.main>
      </div>

      {portalTarget
        ? createPortal(
            <>
              <AnimatePresence>
                {toast ? (
                  <motion.button
                    className="toast"
                    onClick={() => setToast("")}
                    initial={{ opacity: 0, y: 12, scale: 0.96 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 10, scale: 0.98 }}
                    transition={{ duration: 0.28, ease: "easeOut" }}
                  >
                    {toast}
                  </motion.button>
                ) : null}
              </AnimatePresence>
            </>,
            portalTarget
          )
        : null}
    </div>
  );
}

export default App;
