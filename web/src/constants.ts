export type RouteKey = "home" | "song" | "shadow" | "chat" | "relation" | "settings";
export type FriendListType = "all" | "recent";
export type ShadowTab = "selector" | "generator" | "status";
export type RelationTab = "overview" | "friend" | "self" | "reports";

export const ROUTES: Array<{ key: RouteKey; label: string; description: string }> = [
  { key: "home", label: "首页", description: "" },
  { key: "song", label: "歌曲分享", description: "" },
  { key: "shadow", label: "影子歌单", description: "" },
  { key: "chat", label: "聊天记录", description: "" },
  { key: "relation", label: "音乐关系", description: "" },
  { key: "settings", label: "设置", description: "" }
];

export const SONG_SCOPE_OPTIONS = [
  { value: "all", label: "全部历史" },
  { value: "recent", label: "最近" },
  { value: "pages", label: "特定页数" },
  { value: "incremental", label: "新增" }
];

export const SHADOW_SCOPE_OPTIONS = [
  { value: "recent", label: "最近" },
  { value: "all", label: "全部历史" },
  { value: "pages", label: "特定页数" },
  { value: "incremental", label: "本次新增" }
];

export const SENDER_OPTIONS = [
  { value: "all", label: "双方" },
  { value: "self", label: "我方" },
  { value: "friend", label: "好友" }
];

export const SONG_QUERY_MODES = [
  { value: "all", label: "全部" },
  { value: "date", label: "按日期" },
  { value: "range", label: "按时间段" }
];

export const CHAT_TYPES = [
  { value: "all", label: "全部" },
  { value: "text", label: "文本" },
  { value: "song", label: "歌曲" },
  { value: "image", label: "图片" },
  { value: "video", label: "视频" },
  { value: "unknown", label: "未知" }
];

export const AI_MODE_OPTIONS = [
  { value: "rational", label: "理性分析版" },
  { value: "style", label: "总结版" }
];
