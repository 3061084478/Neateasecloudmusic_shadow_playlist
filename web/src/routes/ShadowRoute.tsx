import { AnimatePresence, motion } from "framer-motion";
import { SENDER_OPTIONS, SHADOW_SCOPE_OPTIONS } from "../constants";
import { DateMatrixField, KeyValueRow, NumberField, ResultStream, SelectField, TextField } from "../components/primitives";

const shadowTabStageVariants = {
  initial: (direction: number) => ({
    opacity: 0,
    x: direction >= 0 ? 44 : -44,
    y: 10,
    scale: 0.975,
    rotateY: direction >= 0 ? 8 : -8,
    filter: "blur(8px)"
  }),
  animate: {
    opacity: 1,
    x: 0,
    y: 0,
    scale: 1,
    rotateY: 0,
    filter: "blur(0px)",
    transition: {
      duration: 0.28,
      ease: [0.22, 1, 0.36, 1]
    }
  },
  exit: (direction: number) => ({
    opacity: 0,
    x: direction >= 0 ? -34 : 34,
    y: -8,
    scale: 0.964,
    rotateY: direction >= 0 ? -6 : 6,
    filter: "blur(6px)",
    transition: {
      duration: 0.2,
      ease: [0.4, 0, 1, 1]
    }
  })
};

export function ShadowRoute({
  shell,
  shadowPayload,
  shadowOwnedPlaylists,
  songActiveDates,
  shadowTab,
  setShadowTab,
  shadowSelectorForm,
  setShadowSelectorForm,
  shadowGenerateFilters,
  setShadowGenerateFilters,
  selectedCandidateIds,
  onLoadOwnedPlaylists,
  onSaveTarget,
  onLoadCandidates,
  onToggleCandidate,
  onBulkCandidate,
  onGenerate,
  onRefreshStatus
}: {
  shell: any;
  shadowPayload: any;
  shadowOwnedPlaylists: any[];
  songActiveDates: string[];
  shadowTab: "selector" | "generator" | "status";
  setShadowTab: (tab: "selector" | "generator" | "status") => void;
  shadowSelectorForm: any;
  setShadowSelectorForm: (updater: (prev: any) => any) => void;
  shadowGenerateFilters: any;
  setShadowGenerateFilters: (updater: (prev: any) => any) => void;
  selectedCandidateIds: Set<string>;
  onLoadOwnedPlaylists: () => void;
  onSaveTarget: () => void;
  onLoadCandidates: () => void;
  onToggleCandidate: (msgId: string, checked: boolean) => void;
  onBulkCandidate: (mode: "all" | "none" | "invert") => void;
  onGenerate: () => void;
  onRefreshStatus: () => void;
}) {
  const shadowCandidates = shadowPayload?.candidates || [];
  const shadowStatus = shadowPayload?.status || {};
  const lastBuild = shadowStatus?.last_build || {};
  const shadowTabOrder = ["selector", "generator", "status"] as const;
  const shadowTabDirection = Math.max(0, shadowTabOrder.indexOf(shadowTab as typeof shadowTabOrder[number]));

  return (
    <div className="page-stack">
      <section className="hero-panel compact">
        <div className="hero-copy">
          <h2>影子歌单工作流</h2>
        </div>
        <div className="hero-pills workflow-tabs">
          <button className={`subtab-pill ${shadowTab === "selector" ? "is-active" : ""}`} onClick={() => { setShadowTab("selector"); }}>目标歌单</button>
          <button className={`subtab-pill ${shadowTab === "generator" ? "is-active" : ""}`} onClick={() => { setShadowTab("generator"); }}>候选歌曲</button>
          <button className={`subtab-pill ${shadowTab === "status" ? "is-active" : ""}`} onClick={() => { setShadowTab("status"); }}>生成状态</button>
        </div>
      </section>

      <div className="subroute-stage-wrap">
        <AnimatePresence mode="wait" initial={false} custom={shadowTabDirection}>
          {shadowTab === "selector" ? (
            <motion.section
              key="shadow-selector"
              className="two-column subroute-stage"
              custom={shadowTabDirection}
              variants={shadowTabStageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
            >
              <div className="panel">
                <div className="panel-head">
                  <div>
                    <h3>当前目标歌单</h3>
                  </div>
                </div>
                <div className="key-value-list">
                  <KeyValueRow label="名称" value={shell.shadowPlaylist?.name || "未设置"} />
                  <KeyValueRow label="最近生成时间" value={lastBuild?.generated_at || "-"} />
                </div>
              </div>

              <div className="panel">
                <div className="panel-head">
                  <div>
                    <h3>目标歌单设置</h3>
                  </div>
                  <button className="ghost-button small" onClick={onLoadOwnedPlaylists}>读取已有歌单</button>
                </div>
                <div className="field-grid">
                  <SelectField
                    label="策略"
                    value={shadowSelectorForm.strategy}
                    onChange={(value) => setShadowSelectorForm((prev: any) => ({ ...prev, strategy: value }))}
                    options={[
                      { value: "use_existing", label: "使用当前已记录歌单" },
                      { value: "select_owned", label: "选择已有歌单" },
                      { value: "manual_id", label: "手动输入歌单 ID" },
                      { value: "auto_create", label: "自动新建歌单" }
                    ]}
                  />
                  {shadowSelectorForm.strategy === "select_owned" ? (
                    <SelectField
                      label="已有歌单"
                      value={shadowSelectorForm.selected_playlist_id}
                      onChange={(value) => setShadowSelectorForm((prev: any) => ({ ...prev, selected_playlist_id: value }))}
                      options={[
                        { value: "", label: "请选择已有歌单" },
                        ...shadowOwnedPlaylists.map((item: any) => ({
                          value: String(item.playlist_id || ""),
                          label: `${item.name || "-"} · ${item.track_count || 0} 首`
                        }))
                      ]}
                    />
                  ) : null}
                  {shadowSelectorForm.strategy === "manual_id" ? (
                    <TextField
                      label="歌单 ID"
                      value={shadowSelectorForm.manual_playlist_id}
                      onChange={(value) => setShadowSelectorForm((prev: any) => ({ ...prev, manual_playlist_id: value }))}
                      placeholder="输入歌单 ID"
                    />
                  ) : null}
                  {shadowSelectorForm.strategy === "auto_create" ? (
                    <>
                      <TextField
                        label="新歌单名称"
                        value={shadowSelectorForm.new_playlist_name}
                        onChange={(value) => setShadowSelectorForm((prev: any) => ({ ...prev, new_playlist_name: value }))}
                        placeholder="例如：某某的私信分享"
                      />
                      <label className="checkbox-row">
                        <input
                          type="checkbox"
                          checked={shadowSelectorForm.is_private}
                          onChange={(event) => setShadowSelectorForm((prev: any) => ({ ...prev, is_private: event.target.checked }))}
                        />
                        <span>设为私密歌单</span>
                      </label>
                    </>
                  ) : null}
                </div>
                <div className="toolbar">
                  <button className="primary-button" onClick={onSaveTarget}>保存设置</button>
                </div>
              </div>
            </motion.section>
          ) : null}

          {shadowTab === "generator" ? (
            <motion.section
              key="shadow-generator"
              className="page-stack subroute-stage"
              custom={shadowTabDirection}
              variants={shadowTabStageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
            >
              <div className="command-panel">
                <div className="field-row">
                  <SelectField className="field-compact" label="范围" value={shadowGenerateFilters.scope} onChange={(value) => setShadowGenerateFilters((prev: any) => ({ ...prev, scope: value }))} options={SHADOW_SCOPE_OPTIONS} />
                  {shadowGenerateFilters.scope === "pages" ? (
                    <NumberField className="field-compact field-micro" label="页数" value={shadowGenerateFilters.max_pages} min={1} max={99} onChange={(value) => setShadowGenerateFilters((prev: any) => ({ ...prev, max_pages: value }))} />
                  ) : null}
                  <SelectField className="field-compact" label="发送方" value={shadowGenerateFilters.sender_scope} onChange={(value) => setShadowGenerateFilters((prev: any) => ({ ...prev, sender_scope: value }))} options={SENDER_OPTIONS} />
                  <SelectField
                    className="field-compact"
                    label="查询方式"
                    value={shadowGenerateFilters.query_mode}
                    onChange={(value) => setShadowGenerateFilters((prev: any) => ({ ...prev, query_mode: value }))}
                    options={[
                      { value: "all", label: "全部" },
                      { value: "date", label: "按日期" },
                      { value: "range", label: "按时间段" }
                    ]}
                  />
                  <TextField className="field-grow" label="关键词" value={shadowGenerateFilters.keyword} onChange={(value) => setShadowGenerateFilters((prev: any) => ({ ...prev, keyword: value }))} placeholder="歌曲名 / 歌手" />
                  <NumberField
                    className="field-compact"
                    label="最多歌曲"
                    value={Number(shadowGenerateFilters.max_songs || 0)}
                    min={0}
                    max={500}
                    allowEmpty
                    onChange={(value) => setShadowGenerateFilters((prev: any) => ({ ...prev, max_songs: value ? String(value) : "" }))}
                  />
                </div>
                {shadowGenerateFilters.query_mode !== "all" ? (
                  <div className="field-row date-row">
                    {shadowGenerateFilters.query_mode === "date" ? (
                      <DateMatrixField
                        className="field-date"
                        label="日期"
                        value={shadowGenerateFilters.start_date}
                        activeDates={songActiveDates}
                        onChange={(value) => setShadowGenerateFilters((prev: any) => ({ ...prev, start_date: value, end_date: value }))}
                      />
                    ) : null}
                    {shadowGenerateFilters.query_mode === "range" ? (
                      <>
                        <DateMatrixField className="field-date" label="开始时间" value={shadowGenerateFilters.start_date} activeDates={songActiveDates} onChange={(value) => setShadowGenerateFilters((prev: any) => ({ ...prev, start_date: value, end_date: prev.end_date && prev.end_date < value ? "" : prev.end_date }))} />
                        <DateMatrixField className="field-date" label="结束时间" value={shadowGenerateFilters.end_date} activeDates={songActiveDates} minDate={shadowGenerateFilters.start_date || undefined} onChange={(value) => setShadowGenerateFilters((prev: any) => ({ ...prev, end_date: value }))} />
                      </>
                    ) : null}
                  </div>
                ) : null}
                <div className="toolbar">
                  <button className="primary-button" onClick={onLoadCandidates}>加载候选歌曲</button>
                  <button className="secondary-button" onClick={onGenerate}>生成影子歌单</button>
                  <button className="ghost-button" onClick={() => onBulkCandidate("all")}>全选</button>
                  <button className="ghost-button" onClick={() => onBulkCandidate("none")}>全不选</button>
                  <button className="ghost-button" onClick={() => onBulkCandidate("invert")}>反选</button>
                  <span className="toolbar-meta is-active">候选 {shadowCandidates.length} / 已选 {selectedCandidateIds.size}</span>
                </div>
              </div>

              {Array.isArray(shadowPayload?.candidates) && shadowCandidates.length > 0 ? (
                <div className="panel">
                  <div className="panel-head">
                    <div>
                      <h3>候选歌曲队列</h3>
                    </div>
                  </div>
                  <ResultStream items={shadowCandidates} emptyTitle="当前没有可用候选歌曲">
                    {(item: any) => (
                      <label className="workflow-card">
                        <div className="checkbox-row">
                          <input type="checkbox" checked={selectedCandidateIds.has(String(item.msg_id))} onChange={(event) => onToggleCandidate(String(item.msg_id), event.target.checked)} />
                          <span>{item.direction === "friend" ? "好友分享" : "我方分享"}</span>
                        </div>
                        <div className="workflow-main">
                          <h3>{item.song_name || "未知歌曲"}</h3>
                          <p>{item.artist_name || "未知歌手"}</p>
                          <small>{item.msg_time_str || "-"}</small>
                        </div>
                      </label>
                    )}
                  </ResultStream>
                </div>
              ) : null}
            </motion.section>
          ) : null}

          {shadowTab === "status" ? (
            <motion.section
              key="shadow-status"
              className="page-stack subroute-stage"
              custom={shadowTabDirection}
              variants={shadowTabStageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
            >
              <div className="toolbar">
                <span className="toolbar-meta is-idle">最近生成时间 {lastBuild?.generated_at || "-"}</span>
                <span className="toolbar-meta is-active">最近生成数量 {lastBuild?.generated_count || 0} 首</span>
                <button className="ghost-button small" onClick={onRefreshStatus}>刷新状态</button>
              </div>
              {Array.isArray(shadowStatus?.playlist_state) && shadowStatus.playlist_state.length > 0 ? (
                <div className="panel">
                  <div className="panel-head">
                    <div>
                      <h3>当前歌单内容</h3>
                    </div>
                  </div>
                  <ResultStream items={shadowStatus?.playlist_state} emptyTitle="当前目标歌单为空">
                    {(item: any) => (
                      <div className="stream-card">
                        <h3>{item.song_name || "未知歌曲"}</h3>
                        <p>{item.artist_name || "未知歌手"}</p>
                      </div>
                    )}
                  </ResultStream>
                </div>
              ) : null}
            </motion.section>
          ) : null}
        </AnimatePresence>
      </div>
    </div>
  );
}
