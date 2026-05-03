import { motion } from "framer-motion";
import type { ShellEntryMode } from "../startup";

const HOME_CARD_ENTRY_DELAY = 2.28;
const HOME_CARD_ENTRY_STAGGER = 0.22;
const HOME_CARD_ENTRY_DURATION = 1.24;
const HOME_CARD_TRAJECTORIES = [
  { y: -8, rotate: 4.4 },
  { y: 10, rotate: 3.4 },
  { y: -6, rotate: 4.8 },
  { y: 12, rotate: 3.8 },
  { y: 2, rotate: 2.9 }
];

export function HomeRoute({
  shell,
  currentFriend,
  homeCards,
  shellEntryMode,
  shellEntryStarted
}: {
  shell: any;
  currentFriend: any;
  homeCards: Array<{ title: string; summary: string; detail: string; actions: Array<{ label: string; onClick: () => void }> }>;
  shellEntryMode: ShellEntryMode;
  shellEntryStarted: boolean;
}) {
  const shellEntryHome = shellEntryMode === "shell-enter-home";
  const shellEntryArmed = shellEntryHome && !shellEntryStarted;
  const overviewTrajectory = HOME_CARD_TRAJECTORIES[0];

  return (
    <div className="page-stack" style={shellEntryHome ? { pointerEvents: "none" } : undefined}>
      <motion.section
        className="home-overview-card"
        initial={false}
        animate={
          shellEntryArmed
            ? {
                opacity: 0,
                x: 214,
                y: overviewTrajectory.y + 10,
                rotateZ: overviewTrajectory.rotate + 1.2,
                scale: 0.928,
                filter: "blur(14px)"
              }
            : { opacity: 1, x: 0, y: 0, rotateZ: 0, scale: 1, filter: "blur(0px)" }
        }
        transition={
          shellEntryHome
            ? shellEntryStarted
              ? { duration: HOME_CARD_ENTRY_DURATION, delay: HOME_CARD_ENTRY_DELAY, ease: [0.16, 1, 0.3, 1] }
              : { duration: 0 }
            : { duration: 0 }
        }
      >
        <div className="home-overview-inline">
          <span>当前账号/选中好友：</span>
          <strong>{shell.account?.nickname || "未登录"} / {currentFriend?.nickname || "未选择好友"}</strong>
        </div>
      </motion.section>

      <section className="card-grid compact-grid dense-card-grid">
        {homeCards.map((card, index) => {
          const trajectory = HOME_CARD_TRAJECTORIES[index + 1];
          return (
          <motion.div
            key={card.title}
            className="feature-card"
            initial={false}
            animate={
              shellEntryArmed
                ? {
                    opacity: 0,
                    x: 196,
                    y: trajectory.y + 12,
                    rotateZ: trajectory.rotate + 1,
                    scale: 0.94,
                    filter: "blur(12px)"
                  }
                : { opacity: 1, x: 0, y: 0, rotateZ: 0, scale: 1, filter: "blur(0px)" }
            }
            transition={
              shellEntryHome
                ? shellEntryStarted
                  ? {
                      duration: HOME_CARD_ENTRY_DURATION,
                      delay: HOME_CARD_ENTRY_DELAY + (index + 1) * HOME_CARD_ENTRY_STAGGER,
                      ease: [0.16, 1, 0.3, 1]
                    }
                  : { duration: 0 }
                : { duration: 0 }
            }
            whileHover={shellEntryHome ? undefined : { y: -3, scale: 1.01 }}
            whileTap={shellEntryHome ? undefined : { scale: 0.992 }}
          >
            <div className="feature-card-head">
              <h3>{card.title}</h3>
            </div>
            <div className="feature-card-copy">
              <p>{card.summary}</p>
              <small>{card.detail}</small>
            </div>
            <div className="feature-card-actions">
              {card.actions.map((action) => (
                <motion.button
                  key={action.label}
                  className="secondary-button compact-action"
                  onClick={action.onClick}
                  whileHover={shellEntryHome ? undefined : { y: -1, scale: 1.02 }}
                  whileTap={shellEntryHome ? undefined : { scale: 0.98 }}
                >
                  {action.label}
                </motion.button>
              ))}
            </div>
          </motion.div>
          );
        })}
      </section>
    </div>
  );
}
