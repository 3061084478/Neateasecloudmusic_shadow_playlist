import { CHAT_TYPES, SENDER_OPTIONS, SONG_QUERY_MODES, SONG_SCOPE_OPTIONS } from "../constants";
import { DateMatrixField, NumberField, ResultStream, SelectField, TextField, ToolRoute } from "../components/primitives";

export function ChatRoute({
  chatFilters,
  setChatFilters,
  chatResult,
  chatActiveDates,
  hasQueried,
  onQuery,
  onReset
}: {
  chatFilters: any;
  setChatFilters: (updater: (prev: any) => any) => void;
  chatResult: any;
  chatActiveDates: string[];
  hasQueried: boolean;
  onQuery: () => void;
  onReset: () => void;
}) {
  return (
    <ToolRoute title="聊天记录">
      <div className="command-panel">
        <div className="field-row">
          <SelectField className="field-compact" label="范围" value={chatFilters.scope} onChange={(value) => setChatFilters((prev: any) => ({ ...prev, scope: value }))} options={SONG_SCOPE_OPTIONS} />
          {chatFilters.scope === "pages" ? (
            <NumberField className="field-compact field-micro" label="页数" value={chatFilters.pages} min={1} max={99} onChange={(value) => setChatFilters((prev: any) => ({ ...prev, pages: value }))} />
          ) : null}
          <SelectField className="field-compact" label="发送方" value={chatFilters.sender_scope} onChange={(value) => setChatFilters((prev: any) => ({ ...prev, sender_scope: value }))} options={SENDER_OPTIONS} />
          <SelectField className="field-compact" label="消息类型" value={chatFilters.message_type} onChange={(value) => setChatFilters((prev: any) => ({ ...prev, message_type: value }))} options={CHAT_TYPES} />
          <SelectField className="field-compact" label="查询方式" value={chatFilters.query_mode} onChange={(value) => setChatFilters((prev: any) => ({ ...prev, query_mode: value }))} options={SONG_QUERY_MODES} />
          <TextField className="field-grow" label="关键词" value={chatFilters.keyword} onChange={(value) => setChatFilters((prev: any) => ({ ...prev, keyword: value }))} placeholder="消息文本 / 歌曲名 / 歌手" />
        </div>
        {chatFilters.query_mode !== "all" ? (
          <div className="field-row date-row">
            {chatFilters.query_mode === "date" ? (
              <DateMatrixField className="field-date" label="日期" value={chatFilters.target_date} activeDates={chatActiveDates} onChange={(value) => setChatFilters((prev: any) => ({ ...prev, target_date: value }))} />
            ) : null}
            {chatFilters.query_mode === "range" ? (
              <>
                <DateMatrixField className="field-date" label="开始时间" value={String(chatFilters.start_datetime || "").slice(0, 10)} activeDates={chatActiveDates} onChange={(value) => setChatFilters((prev: any) => ({ ...prev, start_datetime: value, end_datetime: prev.end_datetime && String(prev.end_datetime).slice(0, 10) < value ? "" : prev.end_datetime }))} />
                <DateMatrixField className="field-date" label="结束时间" value={String(chatFilters.end_datetime || "").slice(0, 10)} activeDates={chatActiveDates} minDate={String(chatFilters.start_datetime || "").slice(0, 10) || undefined} onChange={(value) => setChatFilters((prev: any) => ({ ...prev, end_datetime: value }))} />
              </>
            ) : null}
          </div>
        ) : null}
        <div className="toolbar">
          <button className="primary-button" onClick={onQuery}>查询聊天内容</button>
          <button className="secondary-button" onClick={onReset}>清空条件</button>
          <span className={`toolbar-meta ${chatResult?.summary?.count ? "is-active" : "is-idle"}`}>{chatResult?.summary?.count ? `${chatResult.summary.count} 条结果` : "等待查询"}</span>
        </div>
      </div>

      {hasQueried ? (
        <ResultStream items={chatResult?.items} emptyTitle="当前没有命中聊天结果">
          {(item: any) => (
            <div className={`stream-card ${item.direction === "friend" ? "" : "is-self"}`}>
              <div className="stream-head">
                <span className="status-pill">{(item.direction === "friend" ? "好友" : "我方") + " · " + (item.msg_type || "unknown")}</span>
                <span>{item.msg_time_str || "-"}</span>
              </div>
              <h3>{item.text_content || item.song_name || "[暂无内容]"}</h3>
              {item.song_name ? <p>{item.song_name} · {item.artist_name || "未知歌手"}</p> : null}
              {item.msg_type === "image" && item.image_url ? <img className="chat-inline-image" src={item.image_url} alt="聊天图片" /> : null}
            </div>
          )}
        </ResultStream>
      ) : null}
    </ToolRoute>
  );
}
