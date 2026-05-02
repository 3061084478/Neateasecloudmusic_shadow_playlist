import { AnimatePresence, motion } from "framer-motion";
import { AI_MODE_OPTIONS, RelationTab } from "../constants";
import { ActivityHeatmap, AnnualReviewPanel, ArtistPodiumChart, Avatar, CommonWorldPanel, DualRankPanel, EmptyState, FriendRankPanels, GenreDonutChart, MetricCard, MiniList, MoodGrid, NetworkOrbitCard, SelectField, TextField, TimelineVisualChart } from "../components/primitives";

const relationTabStageVariants = {
  initial: (direction: number) => ({
    opacity: 0,
    x: direction >= 0 ? 48 : -48,
    y: 12,
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
      duration: 0.3,
      ease: [0.22, 1, 0.36, 1]
    }
  },
  exit: (direction: number) => ({
    opacity: 0,
    x: direction >= 0 ? -38 : 38,
    y: -10,
    scale: 0.964,
    rotateY: direction >= 0 ? -6 : 6,
    filter: "blur(6px)",
    transition: {
      duration: 0.22,
      ease: [0.4, 0, 1, 1]
    }
  })
};

function buildYearOptions(years: number[]) {
  return (years || []).map((year) => ({ value: String(year), label: `${year} 年` }));
}

function findPeakMonth(trendSeries: any[]) {
  if (!trendSeries?.length) {
    return "-";
  }
  const peak = [...trendSeries].sort((left, right) => {
    const rightValue = Number(right?.song_count || 0) + Number(right?.msg_count || 0);
    const leftValue = Number(left?.song_count || 0) + Number(left?.msg_count || 0);
    return rightValue - leftValue;
  })[0];
  return peak?.month || "-";
}

function buildStructureMetrics(selfData: any) {
  const network = selfData?.network_block || {};
  return [
    { title: "音乐输入/输出", value: network?.music_balance?.label || "-" },
    { title: "聊天输入/输出", value: network?.chat_balance?.label || "-" },
    { title: "音乐圈层浓度", value: network?.music_concentration?.label || "-" },
    { title: "聊天圈层浓度", value: network?.chat_concentration?.label || "-" },
  ];
}

export function RelationRoute({
  relationPayload,
  relationTab,
  setRelationTab,
  relationWindowMode,
  setRelationWindowMode,
  relationYear,
  setRelationYear,
  friendAiMode,
  setFriendAiMode,
  selfAiMode,
  setSelfAiMode,
  friendInsight,
  selfInsight,
  reports,
  reportType,
  setReportType,
  reportKeyword,
  setReportKeyword,
  currentFriend,
  onRefresh,
  onGenerateFriendAi,
  onGenerateSelfAi,
  onExportFriendReport,
  onExportSelfReport,
  onExportAnnualReport,
  onLoadReports,
  onCleanupReports,
  onOpenReport,
  onOpenReportDirectory
}: {
  relationPayload: any;
  relationTab: RelationTab;
  setRelationTab: (tab: RelationTab) => void;
  relationWindowMode: "all" | "year";
  setRelationWindowMode: (mode: "all" | "year") => void;
  relationYear: string;
  setRelationYear: (year: string) => void;
  friendAiMode: string;
  setFriendAiMode: (value: string) => void;
  selfAiMode: string;
  setSelfAiMode: (value: string) => void;
  friendInsight: any;
  selfInsight: any;
  reports: any[];
  reportType: string;
  setReportType: (value: string) => void;
  reportKeyword: string;
  setReportKeyword: (value: string) => void;
  currentFriend: any;
  onRefresh: () => void;
  onGenerateFriendAi: () => void;
  onGenerateSelfAi: () => void;
  onExportFriendReport: () => void;
  onExportSelfReport: () => void;
  onExportAnnualReport: () => void;
  onLoadReports: () => void;
  onCleanupReports: () => void;
  onOpenReport: (path: string) => void;
  onOpenReportDirectory: () => void;
}) {
  const overview = relationPayload?.overview || {};
  const friendData = relationPayload?.friend || {};
  const selfData = relationPayload?.self || {};
  const friendMap = new Map<string, any>((relationPayload?.friends || []).map((item: any) => [String(item?.uid || ""), item]));
  const topSections = [
    { title: "聊天 Top3", unit: "条", items: (selfData?.top_chat_friends || []).map((item: any) => ({ ...item, avatarUrl: friendMap.get(String(item?.uid || ""))?.avatar_url })) },
    { title: "歌曲 Top3", unit: "首", items: (selfData?.top_song_friends || []).map((item: any) => ({ ...item, avatarUrl: friendMap.get(String(item?.uid || ""))?.avatar_url })) },
    { title: "关系温度 Top3", unit: "分", items: (selfData?.top_temperature_friends || []).map((item: any) => ({ ...item, avatarUrl: friendMap.get(String(item?.uid || ""))?.avatar_url })) },
  ];
  const relationYearOptions = buildYearOptions(relationPayload?.available_years || []);
  const structureMetrics = buildStructureMetrics(selfData);
  const relationTabOrder: RelationTab[] = ["overview", "friend", "self", "reports"];
  const relationTabDirection = Math.max(0, relationTabOrder.indexOf(relationTab));
  const sectionVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.055,
        delayChildren: 0.02
      }
    }
  };
  const blockVariants = {
    hidden: { opacity: 0, y: 14 },
    show: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.24, ease: "easeOut" }
    }
  };

  return (
    <div className="page-stack">
      <div className="relation-window-row">
        <button className={`subtab-pill ${relationWindowMode === "all" ? "is-active" : ""}`} onClick={() => setRelationWindowMode("all")}>
          全量历史
        </button>
        <button className={`subtab-pill ${relationWindowMode === "year" ? "is-active" : ""}`} onClick={() => setRelationWindowMode("year")}>
          特定年份
        </button>
        {relationWindowMode === "year" ? (
          <SelectField className="field-inline" label="年份" value={relationYear} onChange={setRelationYear} options={relationYearOptions} />
        ) : null}
      </div>

      <div className="subtab-row section-tabs">
        {[
          ["overview", "总览"],
          ["friend", "单好友画像"],
          ["self", "我的音乐社交"],
          ["reports", "报告中心"]
        ].map(([key, label]) => (
          <button
            key={key}
            className={`subtab-pill ${relationTab === key ? "is-active" : ""}`}
            onClick={() => {
              setRelationTab(key as RelationTab);
              if (key === "reports") {
                onLoadReports();
              }
            }}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="subroute-stage-wrap">
        <AnimatePresence mode="wait" initial={false} custom={relationTabDirection}>
          {relationTab === "overview" ? (
            <motion.div
              key="relation-overview"
              className="page-stack subroute-stage"
              custom={relationTabDirection}
              variants={relationTabStageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
            >
              <section className="analysis-stat-strip three-up">
                <div className="analysis-stat-card">
                  <span>覆盖好友数</span>
                  <strong>{overview.friend_count || 0}</strong>
                </div>
                <div className="analysis-stat-card">
                  <span>信息总数</span>
                  <strong>{overview.message_count || 0}</strong>
                </div>
                <div className="analysis-stat-card">
                  <span>歌曲总数</span>
                  <strong>{overview.song_count || 0}</strong>
                </div>
              </section>

              <section className="panel current-friend-overview">
                <div className="current-friend-overview-head">
                  <Avatar avatarUrl={friendData?.avatar_url} name={friendData?.friend_name} size={56} />
                  <div>
                    <h3>{friendData?.friend_name || currentFriend?.nickname || "未选择好友"}</h3>
                    <div className="current-friend-meta">
                      <span>信息 {friendData?.message_count_total || 0} 条</span>
                      <span>歌曲 {friendData?.song_share_count_total || 0} 首</span>
                      <span>共同 top 风格：{friendData?.top_genres?.[0]?.name || "暂无"}</span>
                      <span>共同 top 歌手：{friendData?.top_artists?.[0]?.name || "暂无"}</span>
                    </div>
                  </div>
                </div>
              </section>
            </motion.div>
          ) : null}

          {relationTab === "friend" ? (
            <motion.div
              key="relation-friend"
              className="page-stack subroute-stage"
              custom={relationTabDirection}
              variants={relationTabStageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
            >
              <motion.div className="page-stack" variants={sectionVariants} initial="hidden" animate="show">
          <motion.section className="hero-panel friend-hero" variants={blockVariants}>
            <Avatar avatarUrl={relationPayload?.friend?.avatar_url} name={relationPayload?.friend?.friend_name} size={72} />
            <div className="hero-copy">
              <h2>{relationPayload?.friend?.friend_name || currentFriend?.nickname || "未选择好友"}</h2>
              <p>{relationPayload?.friend?.cover_line || "当前好友画像待生成。"}</p>
            </div>
            <div className="hero-side-stack">
              <div className="hero-side-chip">
                <span>关系温度</span>
                <strong>{friendData?.relation_temperature?.label || "--"}</strong>
              </div>
              <div className="hero-side-chip">
                <span>分值</span>
                <strong>{friendData?.relation_temperature?.score || 0}</strong>
              </div>
            </div>
          </motion.section>
          <motion.section className="metric-grid" variants={blockVariants}>
            <MetricCard title="消息总数" value={friendData?.message_count_total || 0} />
            <MetricCard title="歌曲总数" value={friendData?.song_share_count_total || 0} />
            <MetricCard title="活跃天数" value={friendData?.active_days_total || 0} />
            <MetricCard title="平均频率" value={friendData?.avg_share_frequency || 0} />
          </motion.section>
          <motion.section className="panel" variants={blockVariants}>
            <div className="panel-head">
              <div>
                <h3>关系节律时间线</h3>
              </div>
            </div>
            <TimelineVisualChart timeline={friendData?.timeline_visual} />
          </motion.section>
          {friendData?.hour_heatmap?.length ? (
            <motion.section className="panel" variants={blockVariants}>
              <div className="panel-head">
                <div>
                  <h3>活跃节律热力图</h3>
                </div>
              </div>
              <ActivityHeatmap items={friendData?.hour_heatmap || []} summary={friendData?.activity_conclusion} />
            </motion.section>
          ) : null}
          <motion.section className="panel" variants={blockVariants}>
            <div className="panel-head">
              <div>
                <h3>音乐画像</h3>
              </div>
            </div>
            <div className="portrait-three-up">
              <div className="relation-chart-card portrait-genres">
                <div className="panel-head compact">
                  <div>
                    <h3>Top 风格</h3>
                  </div>
                </div>
                <GenreDonutChart items={friendData?.top_genres} />
              </div>
              <div className="relation-chart-card portrait-moods">
                <div className="panel-head compact">
                  <div>
                    <h3>Top 情绪</h3>
                  </div>
                </div>
                <MoodGrid items={friendData?.top_moods} />
              </div>
              <div className="relation-chart-card portrait-artists">
                <div className="panel-head compact">
                  <div>
                    <h3>Top 歌手</h3>
                  </div>
                </div>
                <ArtistPodiumChart items={friendData?.top_artists} />
              </div>
            </div>
            <div className="portrait-common-world">
              <CommonWorldPanel data={friendData?.common_world} />
            </div>
          </motion.section>
          <motion.section className="panel" variants={blockVariants}>
              <div className="panel-head">
                <div>
                  <h3>好友 AI 文段</h3>
                </div>
              </div>
              <div className="toolbar">
                <SelectField className="field-inline" label="模式" value={friendAiMode} onChange={setFriendAiMode} options={AI_MODE_OPTIONS} />
                <button className="primary-button" onClick={onGenerateFriendAi}>生成文段</button>
                <button className="secondary-button" onClick={onExportFriendReport}>导出报告</button>
              </div>
              <p className="long-copy">{friendInsight?.text || "当前还没有生成 AI 文段。"}</p>
              {friendInsight?.evidence_tracks?.length ? (
                <>
                  <div className="panel-note">证据歌曲</div>
                  <MiniList items={friendInsight?.evidence_tracks} render={(item: any) => `${item.song_name || "未知歌曲"} · ${item.artist_name || "未知歌手"} · ${item.reason || "样本"}`} />
                </>
              ) : null}
          </motion.section>
              </motion.div>
            </motion.div>
          ) : null}

          {relationTab === "self" ? (
            <motion.div
              key="relation-self"
              className="page-stack subroute-stage"
              custom={relationTabDirection}
              variants={relationTabStageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
            >
              <motion.div className="page-stack" variants={sectionVariants} initial="hidden" animate="show">
          <motion.section className="hero-panel friend-hero self-hero" variants={blockVariants}>
            <Avatar avatarUrl={selfData?.account_avatar_url} name={relationPayload?.self?.account_name} size={72} />
            <div className="hero-copy">
              <h2>{relationPayload?.self?.account_name || "我"}</h2>
              <p>{relationPayload?.self?.cover_line || "当前还没有生成个人音乐社交摘要。"}</p>
            </div>
            <div className="hero-side-stack">
              <div className="hero-side-chip">
                <span>社交标签</span>
                <strong>{selfData?.social_tag || "--"}</strong>
              </div>
              <div className="hero-side-chip">
                <span>核心好友</span>
                <strong>{selfData?.core_friend_name || "--"}</strong>
              </div>
            </div>
          </motion.section>
          <motion.section className="metric-grid" variants={blockVariants}>
            <MetricCard title="活跃好友" value={selfData?.active_friend_count || 0} />
            <MetricCard title="消息总数" value={selfData?.message_count || 0} />
            <MetricCard title="歌曲总数" value={selfData?.song_count || 0} />
            <MetricCard title="活跃峰值" value={findPeakMonth(selfData?.trend_series || [])} />
          </motion.section>
          <motion.section className="panel" variants={blockVariants}>
            <div className="panel-head">
              <div>
                <h3>关系强度 Top3</h3>
              </div>
            </div>
            <FriendRankPanels sections={topSections} />
          </motion.section>
          <motion.div className="metric-grid structure-metric-grid" variants={blockVariants}>
            {structureMetrics.map((item) => (
              <MetricCard key={item.title} title={item.title} value={item.value} />
            ))}
          </motion.div>
          <motion.section className="panel" variants={blockVariants}>
            <div className="panel-head">
              <div>
                <h3>音乐社交结构</h3>
              </div>
            </div>
            <div className="network-grid">
              <NetworkOrbitCard
                title="音乐输入"
                summary={selfData?.network_block?.music_input_block?.summary || "暂无音乐输入数据"}
                items={selfData?.network_block?.music_input_block?.items || []}
                unit={selfData?.network_block?.music_input_block?.unit || "首"}
                centerAvatarUrl={selfData?.account_avatar_url}
                centerName={selfData?.account_name}
              />
              <NetworkOrbitCard
                title="音乐输出"
                summary={selfData?.network_block?.music_output_block?.summary || "暂无音乐输出数据"}
                items={selfData?.network_block?.music_output_block?.items || []}
                unit={selfData?.network_block?.music_output_block?.unit || "首"}
                centerAvatarUrl={selfData?.account_avatar_url}
                centerName={selfData?.account_name}
              />
              <NetworkOrbitCard
                title="聊天输入"
                summary={selfData?.network_block?.chat_input_block?.summary || "暂无聊天输入数据"}
                items={selfData?.network_block?.chat_input_block?.items || []}
                unit={selfData?.network_block?.chat_input_block?.unit || "条"}
                centerAvatarUrl={selfData?.account_avatar_url}
                centerName={selfData?.account_name}
              />
              <NetworkOrbitCard
                title="聊天输出"
                summary={selfData?.network_block?.chat_output_block?.summary || "暂无聊天输出数据"}
                items={selfData?.network_block?.chat_output_block?.items || []}
                unit={selfData?.network_block?.chat_output_block?.unit || "条"}
                centerAvatarUrl={selfData?.account_avatar_url}
                centerName={selfData?.account_name}
              />
            </div>
          </motion.section>
          <motion.section className="panel" variants={blockVariants}>
            <div className="panel-head">
              <div>
                <h3>关系节律时间线</h3>
              </div>
            </div>
            <TimelineVisualChart timeline={selfData?.timeline_visual} />
          </motion.section>
          <motion.section className="panel" variants={blockVariants}>
            <div className="panel-head">
              <div>
                <h3>整体风格与歌手</h3>
              </div>
            </div>
            <DualRankPanel genres={selfData?.top_genres || []} artists={selfData?.top_artists || []} />
          </motion.section>
          <motion.section className="panel" variants={blockVariants}>
            <div className="panel-head">
              <div>
                <h3>我的音乐社交 AI 文段</h3>
              </div>
            </div>
            <div className="toolbar">
              <SelectField className="field-inline" label="模式" value={selfAiMode} onChange={setSelfAiMode} options={AI_MODE_OPTIONS} />
              <button className="primary-button" onClick={onGenerateSelfAi}>生成文段</button>
              <button className="secondary-button" onClick={onExportSelfReport}>导出个人报告</button>
              <button className="ghost-button" onClick={onExportAnnualReport}>导出年度回顾</button>
            </div>
            <p className="long-copy">{selfInsight?.text || "当前还没有生成社交 AI 文段。"}</p>
            {selfInsight?.evidence_tracks?.length ? (
              <>
                <div className="panel-note">证据歌曲</div>
                  <MiniList items={selfInsight?.evidence_tracks} render={(item: any) => `${item.song_name || "未知歌曲"} · ${item.artist_name || "未知歌手"} · ${item.reason || "样本"}`} />
                </>
              ) : null}
          </motion.section>
          {(selfData?.annual_review || relationPayload?.annual_review) ? (
            <motion.section className="panel" variants={blockVariants}>
              <div className="panel-head">
                <div>
                  <h3>年度音乐社交回顾</h3>
                </div>
              </div>
              <AnnualReviewPanel review={selfData?.annual_review || relationPayload?.annual_review} mode={relationWindowMode} />
            </motion.section>
          ) : null}
              </motion.div>
            </motion.div>
          ) : null}

          {relationTab === "reports" ? (
            <motion.div
              key="relation-reports"
              className="page-stack subroute-stage"
              custom={relationTabDirection}
              variants={relationTabStageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
            >
              <section className="command-panel">
                <div className="field-row">
                  <SelectField
                    label="报告类型"
                    value={reportType}
                    onChange={(value) => {
                      setReportType(value);
                      onLoadReports();
                    }}
                    options={[
                      { value: "all", label: "全部报告" },
                      { value: "friend", label: "好友报告" },
                      { value: "self", label: "个人报告" },
                      { value: "annual", label: "年度回顾" }
                    ]}
                  />
                  <TextField
                    label="搜索"
                    value={reportKeyword}
                    onChange={(value) => {
                      setReportKeyword(value);
                      onLoadReports();
                    }}
                    placeholder="标题 / 主角 / 路径"
                  />
                </div>
                <div className="toolbar">
                  <button className="secondary-button" onClick={onOpenReportDirectory}>打开报告目录</button>
                  <button className="ghost-button" onClick={onCleanupReports}>清理失效报告</button>
                </div>
              </section>

              {reports?.length ? (
                <div className="report-grid">
                  {reports.map((item: any, index: number) => (
                    <button key={item.path || index} className="report-card" onClick={() => onOpenReport(item.path || "")}>
                      <div className="stream-head">
                        <span className="status-pill">{item.display_type || "报告"}</span>
                        <span>{item.generated_at || "-"}</span>
                      </div>
                      <h3>{item.title || "未命名报告"}</h3>
                      <p>{item.summary || "暂无摘要"}</p>
                      <small>{item.path || "-"}</small>
                    </button>
                  ))}
                </div>
              ) : (
                <EmptyState title="当前没有导出报告" detail="导出好友画像、个人报告或年度回顾后，这里会作为统一报告库展示。" />
              )}
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>

      {!relationPayload ? <EmptyState title="音乐关系正在准备中" detail="切换好友、切换年份或首次进入时，系统会在这里加载关系分析结果。" /> : null}
    </div>
  );
}
