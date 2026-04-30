import { SENDER_OPTIONS, SONG_QUERY_MODES, SONG_SCOPE_OPTIONS } from "../constants";
import { DateMatrixField, NumberField, ResultStream, SelectField, TextField, ToolRoute } from "../components/primitives";

export function SongRoute({
  songFilters,
  setSongFilters,
  songResult,
  songActiveDates,
  hasQueried,
  onQuery,
  onReset
}: {
  songFilters: any;
  setSongFilters: (updater: (prev: any) => any) => void;
  songResult: any;
  songActiveDates: string[];
  hasQueried: boolean;
  onQuery: () => void;
  onReset: () => void;
}) {
  return (
    <ToolRoute title="歌曲分享">
      <div className="command-panel">
        <div className="field-row">
          <SelectField className="field-compact" label="范围" value={songFilters.scope} onChange={(value) => setSongFilters((prev: any) => ({ ...prev, scope: value }))} options={SONG_SCOPE_OPTIONS} />
          {songFilters.scope === "pages" ? (
            <NumberField className="field-compact field-micro" label="页数" value={songFilters.pages} min={1} max={99} onChange={(value) => setSongFilters((prev: any) => ({ ...prev, pages: value }))} />
          ) : null}
          <SelectField className="field-compact" label="发送方" value={songFilters.sender_scope} onChange={(value) => setSongFilters((prev: any) => ({ ...prev, sender_scope: value }))} options={SENDER_OPTIONS} />
          <SelectField className="field-compact" label="查询方式" value={songFilters.query_mode} onChange={(value) => setSongFilters((prev: any) => ({ ...prev, query_mode: value }))} options={SONG_QUERY_MODES} />
          <TextField className="field-grow" label="关键词" value={songFilters.keyword} onChange={(value) => setSongFilters((prev: any) => ({ ...prev, keyword: value }))} placeholder="歌曲名 / 歌手" />
        </div>
        {songFilters.query_mode !== "all" ? (
          <div className="field-row date-row">
            {songFilters.query_mode === "date" ? (
              <DateMatrixField className="field-date" label="日期" value={songFilters.target_date} activeDates={songActiveDates} onChange={(value) => setSongFilters((prev: any) => ({ ...prev, target_date: value }))} />
            ) : null}
            {songFilters.query_mode === "range" ? (
              <>
                <DateMatrixField className="field-date" label="开始时间" value={songFilters.start_date} activeDates={songActiveDates} onChange={(value) => setSongFilters((prev: any) => ({ ...prev, start_date: value, end_date: prev.end_date && prev.end_date < value ? "" : prev.end_date }))} />
                <DateMatrixField className="field-date" label="结束时间" value={songFilters.end_date} activeDates={songActiveDates} minDate={songFilters.start_date || undefined} onChange={(value) => setSongFilters((prev: any) => ({ ...prev, end_date: value }))} />
              </>
            ) : null}
          </div>
        ) : null}
        <div className="toolbar">
          <button className="primary-button" onClick={onQuery}>查询歌曲分享</button>
          <button className="secondary-button" onClick={onReset}>清空条件</button>
          <span className="toolbar-meta">{songResult?.summary?.count ? `${songResult.summary.count} 条结果` : "等待查询"}</span>
        </div>
      </div>

      {hasQueried ? (
        <ResultStream items={songResult?.items} emptyTitle="当前没有命中歌曲分享结果">
          {(item: any) => (
            <div className={`stream-card ${item.direction === "friend" ? "" : "is-self"}`}>
              <div className="stream-head">
                <span className="status-pill">{item.direction === "friend" ? "好友" : "我方"}</span>
                <span>{item.msg_time_str || "-"}</span>
              </div>
              <h3>{item.song_name || "未知歌曲"}</h3>
              <p>{item.artist_name || "未知歌手"}</p>
              <small>msg_id: {item.msg_id || "-"}</small>
            </div>
          )}
        </ResultStream>
      ) : null}
    </ToolRoute>
  );
}
