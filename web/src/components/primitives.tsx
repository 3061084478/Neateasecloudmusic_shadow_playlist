import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

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
  const triggerRef = useRef<HTMLDivElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [panelRect, setPanelRect] = useState<{ top: number; left: number; width: number } | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    const updatePanelRect = () => {
      const trigger = triggerRef.current;
      if (!trigger) {
        return;
      }
      const rect = trigger.getBoundingClientRect();
      const width = 320;
      const maxLeft = Math.max(12, window.innerWidth - width - 12);
      setPanelRect({
        top: rect.bottom + 8,
        left: Math.min(Math.max(12, rect.left), maxLeft),
        width,
      });
    };

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) {
        return;
      }
      if (triggerRef.current?.contains(target) || panelRef.current?.contains(target)) {
        return;
      }
      setOpen(false);
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    updatePanelRect();
    window.addEventListener("resize", updatePanelRect);
    window.addEventListener("scroll", updatePanelRect, true);
    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleEscape);
    return () => {
      window.removeEventListener("resize", updatePanelRect);
      window.removeEventListener("scroll", updatePanelRect, true);
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  return (
    <div className={`field calendar-field ${className}`.trim()}>
      <span>{label}</span>
      <div ref={triggerRef} className={`picker-input ${open ? "is-open" : ""}`}>
        <input value={value} readOnly placeholder="选择日期" onClick={() => setOpen((prev) => !prev)} />
        <button type="button" className="picker-trigger" onClick={() => setOpen((prev) => !prev)}>
          ▦
        </button>
      </div>
      {typeof document !== "undefined" && panelRect
        ? createPortal(
            <AnimatePresence>
              {open ? (
                <motion.div
                  ref={panelRef}
                  className="floating-panel calendar-panel calendar-panel-portal"
                  style={{
                    position: "fixed",
                    top: panelRect.top,
                    left: panelRect.left,
                    width: panelRect.width,
                  }}
                  initial={{ opacity: 0, y: 10, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 8, scale: 0.985 }}
                  transition={{ duration: 0.16, ease: "easeOut" }}
                >
                  <CalendarPanel
                    value={value}
                    activeDates={activeDates}
                    minDate={minDate}
                    onPick={(nextValue) => {
                      onChange(nextValue);
                      setOpen(false);
                    }}
                  />
                </motion.div>
              ) : null}
            </AnimatePresence>,
            document.body
          )
        : null}
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
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [panelRect, setPanelRect] = useState<{ top: number; left: number; width: number } | null>(null);
  const activeOption = options.find((item) => item.value === value) || options[0];

  useEffect(() => {
    if (!open) {
      return;
    }

    const updatePanelRect = () => {
      const trigger = triggerRef.current;
      if (!trigger) {
        return;
      }
      const rect = trigger.getBoundingClientRect();
      const width = Math.max(rect.width, 168);
      const maxLeft = Math.max(12, window.innerWidth - width - 12);
      setPanelRect({
        top: rect.bottom + 8,
        left: Math.min(Math.max(12, rect.left), maxLeft),
        width,
      });
    };

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) {
        return;
      }
      if (triggerRef.current?.contains(target) || panelRef.current?.contains(target)) {
        return;
      }
      setOpen(false);
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    updatePanelRect();
    window.addEventListener("resize", updatePanelRect);
    window.addEventListener("scroll", updatePanelRect, true);
    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleEscape);
    return () => {
      window.removeEventListener("resize", updatePanelRect);
      window.removeEventListener("scroll", updatePanelRect, true);
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  return (
    <div className={`field select-field ${className}`.trim()}>
      <span>{label}</span>
      <button
        ref={triggerRef}
        type="button"
        className={`picker-input select-trigger ${open ? "is-open" : ""}`}
        onClick={() => setOpen((prev) => !prev)}
      >
        <strong>{activeOption?.label || "-"}</strong>
        <span className="select-chevron">▾</span>
      </button>
      {typeof document !== "undefined" && panelRect
        ? createPortal(
            <AnimatePresence>
              {open ? (
                <motion.div
                  ref={panelRef}
                  className="floating-panel select-panel select-panel-portal"
                  style={{
                    position: "fixed",
                    top: panelRect.top,
                    left: panelRect.left,
                    width: panelRect.width,
                  }}
                  initial={{ opacity: 0, y: 8, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 6, scale: 0.985 }}
                  transition={{ duration: 0.15, ease: "easeOut" }}
                >
                  {options.map((option, index) => (
                    <motion.button
                      key={option.value}
                      type="button"
                      className={`select-option ${option.value === value ? "is-active" : ""}`}
                      onClick={() => {
                        onChange(option.value);
                        setOpen(false);
                      }}
                      initial={{ opacity: 0, x: -6 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.14, delay: index * 0.015, ease: "easeOut" }}
                      whileHover={{ x: 2 }}
                      whileTap={{ scale: 0.99 }}
                    >
                      {option.label}
                    </motion.button>
                  ))}
                </motion.div>
              ) : null}
            </AnimatePresence>,
            document.body
          )
        : null}
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
    <motion.div
      className="metric-card"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
      whileHover={{ y: -3, scale: 1.01 }}
    >
      <span>{title}</span>
      <strong>{value}</strong>
    </motion.div>
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
    <motion.div
      className="result-stream"
      initial="hidden"
      animate="show"
      variants={{
        hidden: {},
        show: {
          transition: {
            staggerChildren: 0.04
          }
        }
      }}
    >
      {items.map((item, index) => (
        <motion.div
          key={item?.msg_id || item?.path || item?.uid || `${index}`}
          variants={{
            hidden: { opacity: 0, y: 12 },
            show: { opacity: 1, y: 0, transition: { duration: 0.22, ease: "easeOut" } }
          }}
          layout
        >
          {children(item)}
        </motion.div>
      ))}
    </motion.div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <motion.div
      className="empty-state"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
    >
      <h3>{title}</h3>
      <p>{detail}</p>
    </motion.div>
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


export function ArtistPodiumChart({ items }: { items: any[] }) {
  const chartItems = (items || []).slice(0, 3);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
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
            <div
              key={`${item?.name || index}-${index}`}
              className={`podium-slot rank-${index + 1} ${hoveredIndex === index ? "is-hovered" : ""}`}
              onMouseEnter={() => setHoveredIndex(index)}
              onMouseLeave={() => setHoveredIndex(null)}
            >
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

export function ArtistTopListCard({
  title,
  items,
  emptyText = "暂无歌手数据",
  accent = "artist"
}: {
  title: string;
  items: any[];
  emptyText?: string;
  accent?: "artist" | "friend" | "shared";
}) {
  const rows = (items || []).slice(0, 5);
  if (!rows.length) {
    return (
      <div className={`artist-top-card artist-top-card-${accent}`}>
        <div className="panel-head compact">
          <div>
            <h3>{title}</h3>
          </div>
        </div>
        <InlineEmpty text={emptyText} />
      </div>
    );
  }
  const maxValue = Math.max(...rows.map((item) => Number(item?.count || 0)), 1);
  return (
    <div className={`artist-top-card artist-top-card-${accent}`}>
      <div className="panel-head compact">
        <div>
          <h3>{title}</h3>
        </div>
      </div>
      <div className="artist-top-list">
        {rows.map((item, index) => (
          <div key={`${title}-${item?.name || index}`} className="artist-top-row">
            <div className="artist-top-rank">#{index + 1}</div>
            <div className="artist-top-main">
              <strong>{item?.name || "未知歌手"}</strong>
              <div className="artist-top-track">
                <div className={`artist-top-fill artist-top-fill-${accent}`} style={{ width: `${(Number(item?.count || 0) / maxValue) * 100}%` }} />
              </div>
            </div>
            <span className="artist-top-count">{item?.count || 0}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ArtistSummaryCard({
  title,
  items
}: {
  title: string;
  items: Array<{ label: string; value: string | number }>;
}) {
  return (
    <div className="artist-summary-card">
      <div className="panel-head compact">
        <div>
          <h3>{title}</h3>
        </div>
      </div>
      <div className="artist-summary-grid">
        {items.map((item) => (
          <div key={item.label} className="artist-summary-item">
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ArtistOverlapInsight({
  title,
  sharedArtists,
  mySongCount,
  friendSongCount,
  myArtistCount,
  friendArtistCount
}: {
  title: string;
  sharedArtists: any[];
  mySongCount: number;
  friendSongCount: number;
  myArtistCount: number;
  friendArtistCount: number;
}) {
  const [activeZone, setActiveZone] = useState<"me" | "friend" | "left" | "right" | "center" | "meter" | "tags" | null>(null);
  const sharedCount = (sharedArtists || []).length;
  const sharedNames = (sharedArtists || []).slice(0, 5).map((item) => String(item?.name || "")).filter(Boolean);
  const overlapRatio = Math.min(1, sharedCount / Math.max(1, Math.min(myArtistCount || 0, friendArtistCount || 0, 5)));
  const meLinked = activeZone === "me" || activeZone === "left";
  const friendLinked = activeZone === "friend" || activeZone === "right";
  const centerLinked = activeZone === "center" || activeZone === "meter" || activeZone === "tags";

  return (
    <div className="artist-summary-card artist-overlap-card">
      <div className="panel-head compact">
        <div>
          <h3>{title}</h3>
        </div>
      </div>
      <div className="artist-overlap-visual">
        <div
          className={`artist-overlap-side is-me ${meLinked ? "is-linked" : ""}`}
          onMouseEnter={() => setActiveZone("me")}
          onMouseLeave={() => setActiveZone(null)}
        >
          <span>我的分享</span>
          <strong>{mySongCount} 首</strong>
          <small>{myArtistCount} 位歌手</small>
        </div>
        <div className={`artist-overlap-center ${centerLinked ? "is-linked" : ""}`}>
          <div className="artist-overlap-rings">
            <div
              className={`artist-overlap-ring is-left ${meLinked ? "is-linked" : ""}`}
              onMouseEnter={() => setActiveZone("left")}
              onMouseLeave={() => setActiveZone(null)}
            />
            <div
              className={`artist-overlap-ring is-right ${friendLinked ? "is-linked" : ""}`}
              onMouseEnter={() => setActiveZone("right")}
              onMouseLeave={() => setActiveZone(null)}
            />
            <div
              className={`artist-overlap-core ${centerLinked ? "is-linked" : ""}`}
              onMouseEnter={() => setActiveZone("center")}
              onMouseLeave={() => setActiveZone(null)}
            >
              <span>共同歌手</span>
              <strong>{sharedCount || 0}</strong>
            </div>
          </div>
          <div
            className={`artist-overlap-meter ${centerLinked ? "is-linked" : ""}`}
            onMouseEnter={() => setActiveZone("meter")}
            onMouseLeave={() => setActiveZone(null)}
          >
            <div className="artist-overlap-meter-fill" style={{ width: `${overlapRatio * 100}%` }} />
          </div>
          <div
            className={`artist-overlap-names ${centerLinked ? "is-linked" : ""}`}
            onMouseEnter={() => setActiveZone("tags")}
            onMouseLeave={() => setActiveZone(null)}
          >
            {sharedNames.length ? sharedNames.map((name) => (
              <span key={name} className="tag-pill">{name}</span>
            )) : <span className="artist-overlap-empty">暂无共同歌手</span>}
          </div>
        </div>
        <div
          className={`artist-overlap-side is-friend ${friendLinked ? "is-linked" : ""}`}
          onMouseEnter={() => setActiveZone("friend")}
          onMouseLeave={() => setActiveZone(null)}
        >
          <span>好友分享</span>
          <strong>{friendSongCount} 首</strong>
          <small>{friendArtistCount} 位歌手</small>
        </div>
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
  const [centerHovered, setCenterHovered] = useState(false);
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
    <div className={`network-orbit-card ${centerHovered ? "is-center-active" : ""}`}>
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
              <g key={`${item?.uid || item?.name || index}-${index}`} className="network-node-group">
                <line x1="160" y1="120" x2={x} y2={y} className="network-link" />
                <foreignObject
                  x={x - avatarSize / 2 - 16}
                  y={y - avatarSize / 2 - 16}
                  width={avatarSize + 32}
                  height={avatarSize + 32}
                >
                  <div className="network-node-wrap network-node-shell">
                    <Avatar avatarUrl={item?.avatar_url} name={item?.name} size={avatarSize} />
                  </div>
                </foreignObject>
                <foreignObject
                  x={labelX - 10}
                  y={labelY - 10}
                  width={badgeWidth + 20}
                  height={badgeHeight + 20}
                >
                  <div className="network-link-badge-shell">
                    <div className="network-link-badge">{badgeValue}</div>
                  </div>
                </foreignObject>
              </g>
            );
          })}
          <foreignObject x="125" y="85" width="70" height="70">
            <div
              className="network-core-wrap network-core-shell"
              onMouseEnter={() => setCenterHovered(true)}
              onMouseLeave={() => setCenterHovered(false)}
            >
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
