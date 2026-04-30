import { Fragment, useEffect, useMemo, useRef, useState } from "react";

export function ToolRoute({
  title,
  children
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="page-stack">
      {children}
    </div>
  );
}

function useOutsideDismiss<T extends HTMLElement>(open: boolean, onClose: () => void) {
  const ref = useRef<T | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handlePointerDown = (event: MouseEvent) => {
      if (ref.current && event.target instanceof Node && !ref.current.contains(event.target)) {
        onClose();
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleEscape);
    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [open, onClose]);

  return ref;
}

function formatCalendarMonth(value: string) {
  const [year, month] = value.split("-");
  return `${year} 年 ${Number(month)} 月`;
}

function buildMonthMap(activeDates: string[], minDate?: string) {
  const enabled = new Set(
    (activeDates || []).filter((item) => {
      if (!item) {
        return false;
      }
      if (minDate && item < minDate) {
        return false;
      }
      return true;
    })
  );
  const sortedDates = Array.from(enabled).sort();
  const firstDate = sortedDates[0];
  const lastDate = sortedDates[sortedDates.length - 1];
  if (!firstDate || !lastDate) {
    return { months: [] as string[], enabled };
  }
  const [startYear, startMonth] = firstDate.split("-").map((item) => Number(item));
  const [endYear, endMonth] = lastDate.split("-").map((item) => Number(item));
  const months: string[] = [];
  let year = startYear;
  let month = startMonth;
  while (year < endYear || (year === endYear && month <= endMonth)) {
    months.push(`${year}-${String(month).padStart(2, "0")}`);
    month += 1;
    if (month > 12) {
      month = 1;
      year += 1;
    }
  }
  return { months, enabled };
}

function CalendarPanel({
  value,
  activeDates,
  minDate,
  onPick
}: {
  value: string;
  activeDates: string[];
  minDate?: string;
  onPick: (value: string) => void;
}) {
  const { months, enabled } = useMemo(() => buildMonthMap(activeDates, minDate), [activeDates, minDate]);
  const [monthIndex, setMonthIndex] = useState(() => {
    if (!months.length) {
      return 0;
    }
    const targetMonth = (value || minDate || months[months.length - 1]).slice(0, 7);
    const matched = months.indexOf(targetMonth);
    return matched >= 0 ? matched : months.length - 1;
  });

  useEffect(() => {
    if (!months.length) {
      setMonthIndex(0);
      return;
    }
    const targetMonth = (value || minDate || months[months.length - 1]).slice(0, 7);
    const matched = months.indexOf(targetMonth);
    setMonthIndex(matched >= 0 ? matched : months.length - 1);
  }, [months, value, minDate]);

  const currentMonth = months[monthIndex];
  const days = useMemo(() => {
    if (!currentMonth) {
      return [];
    }
    const [year, month] = currentMonth.split("-").map((item) => Number(item));
    const firstWeekday = new Date(year, month - 1, 1).getDay();
    const dayCount = new Date(year, month, 0).getDate();
    const cells: Array<{ key: string; label: string; date?: string; enabled: boolean; selected: boolean }> = [];
    const normalizedOffset = firstWeekday === 0 ? 6 : firstWeekday - 1;
    for (let index = 0; index < normalizedOffset; index += 1) {
      cells.push({ key: `blank-${index}`, label: "", enabled: false, selected: false });
    }
    for (let day = 1; day <= dayCount; day += 1) {
      const date = `${currentMonth}-${String(day).padStart(2, "0")}`;
      const isEnabled = enabled.has(date);
      cells.push({
        key: date,
        label: String(day),
        date,
        enabled: isEnabled,
        selected: value === date,
      });
    }
    return cells;
  }, [currentMonth, enabled, value]);

  return (
    <div className="calendar-shell">
      <div className="calendar-head">
        <button type="button" className="calendar-nav" disabled={monthIndex <= 0} onClick={() => setMonthIndex((prev) => Math.max(0, prev - 1))}>
          ←
        </button>
        <strong>{currentMonth ? formatCalendarMonth(currentMonth) : "暂无日期"}</strong>
        <button
          type="button"
          className="calendar-nav"
          disabled={monthIndex >= months.length - 1}
          onClick={() => setMonthIndex((prev) => Math.min(months.length - 1, prev + 1))}
        >
          →
        </button>
      </div>
      <div className="calendar-weekdays">
        {["一", "二", "三", "四", "五", "六", "日"].map((item) => (
          <span key={item}>{item}</span>
        ))}
      </div>
      <div className="calendar-grid">
        {days.length ? (
          days.map((cell) => (
            <button
              key={cell.key}
              type="button"
              className={`calendar-cell ${cell.enabled ? "is-enabled" : ""} ${cell.selected ? "is-selected" : ""}`}
              disabled={!cell.enabled}
              onClick={() => cell.date && onPick(cell.date)}
            >
              {cell.label}
            </button>
          ))
        ) : (
          <div className="calendar-empty">当前范围没有可用日期</div>
        )}
      </div>
    </div>
  );
}

export function DateMatrixField({
  label,
  value,
  onChange,
  activeDates,
  minDate,
  className = "",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  activeDates: string[];
  minDate?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useOutsideDismiss<HTMLDivElement>(open, () => setOpen(false));

  return (
    <div className={`field calendar-field ${className}`.trim()} ref={wrapperRef}>
      <span>{label}</span>
      <div className={`picker-input ${open ? "is-open" : ""}`}>
        <input value={value} readOnly placeholder="选择日期" onClick={() => setOpen((prev) => !prev)} />
        <button type="button" className="picker-trigger" onClick={() => setOpen((prev) => !prev)}>
          ▦
        </button>
      </div>
      {open ? (
        <div className="floating-panel calendar-panel">
          <CalendarPanel
            value={value}
            activeDates={activeDates}
            minDate={minDate}
            onPick={(nextValue) => {
              onChange(nextValue);
              setOpen(false);
            }}
          />
        </div>
      ) : null}
    </div>
  );
}

export function SelectField({
  label,
  value,
  onChange,
  options,
  className = ""
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useOutsideDismiss<HTMLDivElement>(open, () => setOpen(false));
  const activeOption = options.find((item) => item.value === value) || options[0];

  return (
    <div className={`field select-field ${className}`.trim()} ref={wrapperRef}>
      <span>{label}</span>
      <button type="button" className={`picker-input select-trigger ${open ? "is-open" : ""}`} onClick={() => setOpen((prev) => !prev)}>
        <strong>{activeOption?.label || "-"}</strong>
        <span className="select-chevron">▾</span>
      </button>
      {open ? (
        <div className="floating-panel select-panel">
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`select-option ${option.value === value ? "is-active" : ""}`}
              onClick={() => {
                onChange(option.value);
                setOpen(false);
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function TextField({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  className = ""
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
  className?: string;
}) {
  return (
    <label className={`field ${className}`.trim()}>
      <span>{label}</span>
      <input type={type} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
    </label>
  );
}

export function NumberField({
  label,
  value,
  min,
  max,
  onChange,
  allowEmpty = false,
  className = ""
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
  allowEmpty?: boolean;
  className?: string;
}) {
  return (
    <label className={`field ${className}`.trim()}>
      <span>{label}</span>
      <input
        type="number"
        value={allowEmpty && value === 0 ? "" : value}
        min={min}
        max={max}
        onChange={(event) => {
          const raw = event.target.value;
          if (allowEmpty && !raw) {
            onChange(0);
            return;
          }
          onChange(Number(raw || min));
        }}
      />
    </label>
  );
}

export function MetricCard({ title, value }: { title: string; value: string | number }) {
  return (
    <div className="metric-card">
      <span>{title}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function KeyValueRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="key-value-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function ResultStream({
  items,
  emptyTitle,
  children
}: {
  items: any[];
  emptyTitle: string;
  children: (item: any) => React.ReactNode;
}) {
  if (!items?.length) {
    return <EmptyState title={emptyTitle} detail="当前没有可展示内容。" />;
  }
  return (
    <div className="result-stream">
      {items.map((item, index) => (
        <Fragment key={item?.msg_id || item?.path || item?.uid || `${index}`}>
          {children(item)}
        </Fragment>
      ))}
    </div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">·</div>
      <h3>{title}</h3>
      <p>{detail}</p>
    </div>
  );
}

function InlineEmpty({ text }: { text: string }) {
  return <div className="inline-empty">{text}</div>;
}

function hashString(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) | 0;
  }
  return Math.abs(hash);
}

function createSeededRandom(seed: number) {
  let state = seed >>> 0;
  return () => {
    state += 0x6D2B79F5;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffledAngles(source: number[], seedText: string) {
  const list = [...source];
  const random = createSeededRandom(hashString(seedText) || 1);
  for (let index = list.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(random() * (index + 1));
    [list[index], list[swapIndex]] = [list[swapIndex], list[index]];
  }
  return list;
}

export function MiniList({
  items,
  render
}: {
  items: any[];
  render: (item: any) => string;
}) {
  if (!items?.length) {
    return null;
  }
  return (
    <div className="mini-list">
      {items.slice(0, 6).map((item, index) => (
        <div key={index} className="mini-list-row">
          {render(item)}
        </div>
      ))}
    </div>
  );
}

export function TagCloud({ items }: { items: any[] }) {
  if (!items?.length) {
    return <InlineEmpty text="当前没有标签数据" />;
  }
  return (
    <div className="chip-row">
      {items.slice(0, 12).map((item, index) => (
        <span key={`${item.name || index}-${index}`} className="tag-pill">
          {item.name || "未知"} · {item.count || 0}
        </span>
      ))}
    </div>
  );
}

export function SparkBars({ items }: { items: any[] }) {
  if (!items?.length) {
    return <InlineEmpty text="当前没有趋势数据" />;
  }
  const maxValue = Math.max(
    ...items.map((item) => Math.max(Number(item.msg_count || 0), Number(item.song_count || 0))),
    1
  );
  return (
    <div className="spark-bars">
      {items.slice(-12).map((item, index) => (
        <div key={`${item.month || index}-${index}`} className="spark-bar-group">
          <div className="spark-bar-stack">
            <div className="spark-bar song" style={{ height: `${(Number(item.song_count || 0) / maxValue) * 100}%` }} />
            <div className="spark-bar msg" style={{ height: `${(Number(item.msg_count || 0) / maxValue) * 100}%` }} />
          </div>
          <small>{String(item.month || "").slice(5) || "-"}</small>
        </div>
      ))}
    </div>
  );
}

function timelinePhaseTone(phase: string) {
  if (phase === "爆发期") {
    return "is-burst";
  }
  if (phase === "回暖期") {
    return "is-rise";
  }
  if (phase === "回落期") {
    return "is-fall";
  }
  if (phase === "沉默期") {
    return "is-muted";
  }
  return "is-steady";
}

export function TimelineVisualChart({
  timeline
}: {
  timeline: { phases?: any[]; events?: any[]; summary?: string } | null | undefined;
}) {
  const phases = (timeline?.phases || []).slice(-12);
  if (!phases.length) {
    return null;
  }
  const maxMessage = Math.max(...phases.map((item) => Number(item?.msg_count || 0)), 1);
  const maxSong = Math.max(...phases.map((item) => Number(item?.song_count || 0)), 1);
  const events = (timeline?.events || []).slice(0, 8);

  return (
    <div className="timeline-visual">
      <div className="timeline-topbar">
        <div className="timeline-legend">
          <span><i className="legend-dot msg" />消息</span>
          <span><i className="legend-dot song" />歌曲</span>
        </div>
        <div className="timeline-count-head">
          <span className="timeline-count-chip msg">消息量</span>
          <span className="timeline-count-chip song">歌曲量</span>
        </div>
      </div>
      {phases.map((item, index) => {
        const phase = String(item?.phase || "稳定期");
        return (
          <div key={`${item?.month || index}-${index}`} className={`timeline-row ${index % 2 === 0 ? "is-even" : "is-odd"}`}>
            <div className="timeline-month">{item?.month || "-"}</div>
            <span className={`timeline-phase ${timelinePhaseTone(phase)}`}>{phase}</span>
            <div className="timeline-bars">
              <div className="timeline-bar-track">
                <div className="timeline-bar-fill song" style={{ width: `${(Number(item?.song_count || 0) / maxSong) * 100}%` }} />
              </div>
              <div className="timeline-bar-track">
                <div className="timeline-bar-fill msg" style={{ width: `${(Number(item?.msg_count || 0) / maxMessage) * 100}%` }} />
              </div>
            </div>
            <div className="timeline-counts">
              <strong className="msg">{item?.msg_count || 0}</strong>
              <strong className="song">{item?.song_count || 0}</strong>
            </div>
          </div>
        );
      })}
      {events.length ? (
        <div className="timeline-events">
          {events.map((event, index) => (
            <div key={`${event?.month || index}-${event?.title || index}`} className="timeline-event-card">
              <div className="timeline-event-head">
                <strong>{event?.month || "-"}</strong>
                <span>{event?.title || "关键时间点"}</span>
              </div>
              <p>{event?.detail || "-"}</p>
            </div>
          ))}
        </div>
      ) : null}
      {timeline?.summary ? <div className="timeline-summary">{timeline.summary}</div> : null}
    </div>
  );
}

export function ActivityHeatmap({
  items,
  summary
}: {
  items: any[];
  summary?: string;
}) {
  if (!items?.length) {
    return null;
  }
  const total = items.reduce((sum, item) => sum + Number(item?.count || 0), 0) || 1;
  const day = items.filter((item) => {
    const hour = Number(item?.hour || 0);
    return hour >= 6 && hour < 18;
  }).reduce((sum, item) => sum + Number(item?.count || 0), 0);
  const night = items.filter((item) => {
    const hour = Number(item?.hour || 0);
    return hour >= 18 && hour < 24;
  }).reduce((sum, item) => sum + Number(item?.count || 0), 0);
  const late = items.filter((item) => Number(item?.hour || 0) < 6).reduce((sum, item) => sum + Number(item?.count || 0), 0);
  const maxCount = Math.max(...items.map((item) => Number(item?.count || 0)), 1);

  function hourTone(hour: number) {
    if (hour < 6) return "late";
    if (hour < 18) return "day";
    return "night";
  }

  return (
    <div className="activity-heatmap">
      <div className="heatmap-legend">
        <span><i className="legend-dot msg" />白天时段</span>
        <span><i className="legend-dot song" />夜间时段</span>
        <span><i className="legend-dot late" />深夜时段</span>
      </div>
      <div className="heatmap-ratios">
        <span className="heatmap-pill day">白天 {((day / total) * 100).toFixed(1)}%</span>
        <span className="heatmap-pill night">夜间 {((night / total) * 100).toFixed(1)}%</span>
        <span className="heatmap-pill late">深夜 {((late / total) * 100).toFixed(1)}%</span>
      </div>
      <div className="heatmap-grid">
        {items.map((item, index) => {
          const hour = Number(item?.hour || 0);
          const tone = hourTone(hour);
          const opacity = 0.22 + (Number(item?.count || 0) / maxCount) * 0.78;
          return (
            <div key={`${item?.hour || index}-${index}`} className={`heatmap-cell ${tone}`} style={{ opacity }}>
              <strong>{String(item?.hour || "0").padStart(2, "0")}</strong>
              <span>{item?.count || 0}</span>
            </div>
          );
        })}
      </div>
      {summary ? <div className="timeline-summary">{summary}</div> : null}
    </div>
  );
}

export function MoodGrid({ items }: { items: any[] }) {
  const topItems = (items || []).slice(0, 4);
  if (!topItems.length) {
    return <InlineEmpty text="当前没有情绪数据" />;
  }
  const total = topItems.reduce((sum, item) => sum + Number(item?.count || 0), 0) || 1;
  const tones = ["mood-a", "mood-b", "mood-c", "mood-d"];
  return (
    <div className="mood-grid">
      {topItems.map((item, index) => (
        <div key={`${item?.name || index}-${index}`} className={`mood-card ${tones[index % tones.length]}`}>
          <strong>{item?.name || "未知"}</strong>
          <span>{item?.count || 0} 次 · {((Number(item?.count || 0) / total) * 100).toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
}

export function CommonWorldPanel({ data }: { data: any }) {
  const compare = data?.compare || {};
  const me = compare?.me || {};
  const friend = compare?.friend || {};
  const overlap = compare?.overlap || {};
  const summary = (() => {
    const genres = (overlap?.genres || []).slice(0, 2).join("、");
    const moods = (overlap?.moods || []).slice(0, 2).join("、");
    const score = ((Number(data?.overlap_score || 0)) * 100).toFixed(1);
    if (genres && moods) {
      return `重合度 ${score}%，共同风格集中在 ${genres}，共同情绪更偏 ${moods}。`;
    }
    if (genres) {
      return `重合度 ${score}%，共同风格集中在 ${genres}。`;
    }
    return `重合度 ${score}%，当前共同世界还在形成中。`;
  })();
  return (
    <div className="common-world-panel">
      <div className="common-world-column me">
        <h4>我的世界</h4>
        <div className="common-world-lines">
          <div><span>风格</span><strong>{(me?.genres || []).slice(0, 4).join("、") || "暂无"}</strong></div>
          <div><span>歌手</span><strong>{(me?.artists || []).slice(0, 4).join("、") || "暂无"}</strong></div>
          <div><span>情绪</span><strong>{(me?.moods || []).slice(0, 4).join("、") || "暂无"}</strong></div>
        </div>
      </div>
      <div className="common-world-column overlap">
        <h4>共同世界</h4>
        <div className="common-overlap-score">{((Number(data?.overlap_score || 0)) * 100).toFixed(1)}%</div>
        <div className="common-world-lines">
          <div><span>共同风格</span><strong>{(overlap?.genres || []).slice(0, 4).join("、") || "暂无"}</strong></div>
          <div><span>共同歌手</span><strong>{(overlap?.artists || []).slice(0, 4).join("、") || "暂无"}</strong></div>
          <div><span>共同情绪</span><strong>{(overlap?.moods || []).slice(0, 4).join("、") || "暂无"}</strong></div>
        </div>
      </div>
      <div className="common-world-column friend">
        <h4>好友的世界</h4>
        <div className="common-world-lines">
          <div><span>风格</span><strong>{(friend?.genres || []).slice(0, 4).join("、") || "暂无"}</strong></div>
          <div><span>歌手</span><strong>{(friend?.artists || []).slice(0, 4).join("、") || "暂无"}</strong></div>
          <div><span>情绪</span><strong>{(friend?.moods || []).slice(0, 4).join("、") || "暂无"}</strong></div>
        </div>
      </div>
      <div className="timeline-summary common-world-summary">{summary}</div>
    </div>
  );
}

export function GenreDonutChart({ items }: { items: any[] }) {
  const chartItems = (items || []).slice(0, 4);
  if (!chartItems.length) {
    return <InlineEmpty text="当前没有风格数据" />;
  }
  const total = chartItems.reduce((sum, item) => sum + Number(item.count || 0), 0) || 1;
  const radius = 62;
  const circumference = 2 * Math.PI * radius;
  const colors = ["#7dd3fc", "#86efac", "#fda4af", "#fcd34d"];
  let progress = 0;

  return (
    <div className="donut-chart">
      <svg viewBox="0 0 180 180" className="donut-svg">
        <circle cx="90" cy="90" r={radius} className="donut-track" />
        {chartItems.map((item, index) => {
          const value = Number(item.count || 0);
          const ratio = value / total;
          const dash = ratio * circumference;
          const gap = circumference - dash;
          const strokeDasharray = `${dash} ${gap}`;
          const strokeDashoffset = -progress * circumference;
          progress += ratio;
          return (
            <circle
              key={`${item.name || index}-${index}`}
              cx="90"
              cy="90"
              r={radius}
              className="donut-segment"
              style={{ stroke: colors[index % colors.length], strokeDasharray, strokeDashoffset }}
            />
          );
        })}
        <text x="90" y="84" textAnchor="middle" className="donut-center-label">
          TOP1
        </text>
        <text x="90" y="106" textAnchor="middle" className="donut-center-value">
          {chartItems[0]?.name || "暂无"}
        </text>
      </svg>
      <div className="chart-legend">
        {chartItems.map((item, index) => (
          <div key={`${item.name || index}-${index}`} className="chart-legend-row">
            <span className="legend-dot" style={{ background: colors[index % colors.length] }} />
            <span>{item.name || "未知"}</span>
            <strong>{item.count || 0}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ArtistPodiumChart({ items }: { items: any[] }) {
  const chartItems = (items || []).slice(0, 3);
  if (!chartItems.length) {
    return <InlineEmpty text="当前没有歌手数据" />;
  }
  const ordered = [chartItems[1], chartItems[0], chartItems[2]].filter(Boolean);
  const maxValue = Math.max(...ordered.map((item) => Number(item?.count || 0)), 1);
  return (
    <div className="podium-chart">
      <div className="podium-bars">
        {ordered.map((item, index) => {
          const height = 78 + (Number(item?.count || 0) / maxValue) * 84;
          return (
            <div key={`${item?.name || index}-${index}`} className={`podium-slot rank-${index + 1}`}>
              <div className="podium-name">{item?.name || "暂无"}</div>
              <div className="podium-bar" style={{ height }}>
                <span>{item?.count || 0}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function NetworkOrbitCard({
  title,
  summary,
  items,
  unit,
  centerAvatarUrl,
  centerName
}: {
  title: string;
  summary: string;
  items: any[];
  unit: string;
  centerAvatarUrl?: string;
  centerName?: string;
}) {
  const nodes = (items || []).slice(0, 5);
  if (!nodes.length) {
    return (
      <div className="network-orbit-card">
        <div className="network-orbit-head">
          <h4>{title}</h4>
        </div>
        <InlineEmpty text="好友间没有信息" />
      </div>
    );
  }
  const maxValue = Math.max(...nodes.map((item) => Number(item?.value || 0)), 1);
  const slotCenters = [-148, -88, -8, 82, 152];
  const layoutSeed = `${title}-${nodes.map((item) => `${item?.uid || item?.name || "x"}:${item?.value || 0}`).join("|")}`;
  const layoutRandom = createSeededRandom(hashString(layoutSeed) || 1);
  const globalRotation = (layoutRandom() - 0.5) * 26;
  const angleSlots = shuffledAngles(
    slotCenters,
    layoutSeed
  );
  return (
    <div className="network-orbit-card">
      <div className="network-orbit-head">
        <h4>{title}</h4>
      </div>
      <div className="network-orbit-scene">
        <svg viewBox="0 0 320 240" className="network-orbit-svg">
          {nodes.map((item, index) => {
            const seed = hashString(`${title}-${item?.uid || item?.name || index}`);
            const valueRatio = Number(item?.value || 0) / maxValue;
            const emphasis = Math.sqrt(Math.max(0, valueRatio));
            const angleDrift = ((((seed % 17) - 8) * 1.15) * Math.PI) / 180;
            const angle = ((angleSlots[index % angleSlots.length] + globalRotation) * Math.PI) / 180 + angleDrift;
            const radiusDrift = (((Math.floor(seed / 13)) % 11) - 5) * 2.2;
            const radius = 148 - emphasis * 38 + radiusDrift;
            const driftX = ((seed % 7) - 3) * 1.4;
            const driftY = (((Math.floor(seed / 11)) % 7) - 3) * 1.2;
            const rawX = 160 + Math.cos(angle) * radius + driftX;
            const rawY = 120 + Math.sin(angle) * radius + driftY;
            const avatarSize = 28 + emphasis * 18;
            const x = Math.min(320 - avatarSize / 2 - 18, Math.max(avatarSize / 2 + 18, rawX));
            const y = Math.min(240 - avatarSize / 2 - 18, Math.max(avatarSize / 2 + 18, rawY));
            const badgeValue = `${item?.value || 0}${unit}`;
            const badgeWidth = Math.max(48, Math.min(82, 24 + badgeValue.length * 8));
            const badgeHeight = 28;
            const labelCenterX = (160 + x) / 2;
            const labelCenterY = (120 + y) / 2;
            const labelX = labelCenterX - badgeWidth / 2;
            const labelY = labelCenterY - badgeHeight / 2;
            return (
              <g key={`${item?.uid || item?.name || index}-${index}`}>
                <line x1="160" y1="120" x2={x} y2={y} className="network-link" />
                <foreignObject x={x - avatarSize / 2} y={y - avatarSize / 2} width={avatarSize} height={avatarSize}>
                  <div className="network-node-wrap">
                    <Avatar avatarUrl={item?.avatar_url} name={item?.name} size={avatarSize} />
                  </div>
                </foreignObject>
                <foreignObject x={labelX} y={labelY} width={badgeWidth} height={badgeHeight}>
                  <div className="network-link-badge">{badgeValue}</div>
                </foreignObject>
              </g>
            );
          })}
          <foreignObject x="141" y="101" width="38" height="38">
            <div className="network-core-wrap">
              <Avatar avatarUrl={centerAvatarUrl} name={centerName || "我"} size={38} />
            </div>
          </foreignObject>
        </svg>
      </div>
      <p className="panel-note">{summary}</p>
    </div>
  );
}

export function FriendRankPanels({
  sections
}: {
  sections: Array<{ title: string; unit: string; items: any[] }>;
}) {
  return (
    <div className="friend-rank-grid">
      {sections.map((section) => (
        <div key={section.title} className="friend-rank-panel">
          <div className="panel-head compact">
            <div>
              <h3>{section.title}</h3>
            </div>
          </div>
          <div className="friend-rank-list">
            {(section.items || []).slice(0, 3).map((item, index) => (
              <div key={`${section.title}-${item?.uid || item?.name || index}`} className="friend-rank-row">
                <div className="friend-rank-leading">
                  <span className="friend-rank-badge">TOP {index + 1}</span>
                  <Avatar avatarUrl={item?.avatarUrl || item?.avatar_url} name={item?.name} size={40} />
                  <div className="friend-rank-copy">
                    <strong>{item?.name || "未命名好友"}</strong>
                    <small>{item?.count || 0}{section.unit}</small>
                  </div>
                </div>
              </div>
            ))}
            {!section.items?.length ? <InlineEmpty text={`当前没有${section.title}`} /> : null}
          </div>
        </div>
      ))}
    </div>
  );
}

export function AnnualReviewPanel({
  review,
  mode
}: {
  review: any;
  mode: "all" | "year";
}) {
  if (!review || (!review.message_count && !review.song_count && !review.summary)) {
    return null;
  }
  const title = mode === "year" ? `${review?.year || "-"} 音乐社交回顾` : "全部历史音乐社交回顾";
  const eyebrow = mode === "year" ? `${review?.year || "-"} YEAR` : "ALL HISTORY";
  return (
    <div className="annual-review-panel">
      <div className="annual-review-hero">
        <div>
          <h4>{title}</h4>
          <p>{review?.summary || "暂无年度回顾。"}</p>
        </div>
        <span>{eyebrow}</span>
      </div>
      <div className="annual-review-grid">
        <div className="annual-review-stat"><span>消息总量</span><strong>{review?.message_count || 0} 条</strong></div>
        <div className="annual-review-stat"><span>歌曲总量</span><strong>{review?.song_count || 0} 首</strong></div>
        <div className="annual-review-stat"><span>活跃峰值</span><strong>{review?.peak_month || "-"}</strong></div>
        <div className="annual-review-stat"><span>关系主角</span><strong>{review?.representative_relationship || "暂无"}</strong></div>
      </div>
      <div className="annual-review-grid secondary">
        <div className="annual-review-stat"><span>聊天最多</span><strong>{review?.top_chat_friend_name || "暂无"}</strong></div>
        <div className="annual-review-stat"><span>发歌最多</span><strong>{review?.top_song_friend_name || "暂无"}</strong></div>
      </div>
    </div>
  );
}

export function DualRankPanel({
  genres,
  artists
}: {
  genres: any[];
  artists: any[];
}) {
  const left = (genres || []).slice(0, 4);
  const right = (artists || []).slice(0, 4);
  const maxValue = Math.max(
    ...left.map((item) => Number(item.count || 0)),
    ...right.map((item) => Number(item.count || 0)),
    1
  );

  return (
    <div className="dual-rank-panel">
      <div className="rank-column">
        <h4>风格</h4>
        {left.map((item, index) => (
          <div key={`${item.name || index}-${index}`} className="rank-row">
            <span>{item.name || "未知"}</span>
            <div className="rank-track">
              <div className="rank-fill genre" style={{ width: `${(Number(item.count || 0) / maxValue) * 100}%` }} />
            </div>
            <strong>{item.count || 0}</strong>
          </div>
        ))}
      </div>
      <div className="rank-column">
        <h4>歌手</h4>
        {right.map((item, index) => (
          <div key={`${item.name || index}-${index}`} className="rank-row">
            <span>{item.name || "未知"}</span>
            <div className="rank-track">
              <div className="rank-fill artist" style={{ width: `${(Number(item.count || 0) / maxValue) * 100}%` }} />
            </div>
            <strong>{item.count || 0}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Avatar({ avatarUrl, name, size }: { avatarUrl?: string; name?: string; size?: number }) {
  const label = String(name || "S").slice(0, 1).toUpperCase();
  const style = {
    width: size || 44,
    height: size || 44
  };
  return avatarUrl ? (
    <img className="avatar" src={avatarUrl} alt={name || "avatar"} style={style} />
  ) : (
    <div className="avatar avatar-fallback" style={style}>
      {label}
    </div>
  );
}
