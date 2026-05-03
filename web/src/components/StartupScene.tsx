import { AnimatePresence, motion } from "framer-motion";
import type { CSSProperties } from "react";
import type { StartupPayload, StartupPhase } from "../startup";

const BRAND_LETTERS = Array.from("Shadow");

function hasReached(current: StartupPhase, target: StartupPhase) {
  const order: StartupPhase[] = [
    "booting",
    "beamGrow",
    "beamRelax",
    "brandReveal",
    "brandHold",
    "brandLift",
    "ctaReveal",
    "idle",
    "qrVisible",
    "enterShell"
  ];
  return order.indexOf(current) >= order.indexOf(target);
}

export function StartupScene({
  phase,
  payload,
  busyLabel,
  onPrimaryAction,
  onRetry
}: {
  phase: StartupPhase;
  payload: StartupPayload | null;
  busyLabel: string;
  onPrimaryAction: () => void;
  onRetry: () => void;
}) {
  const brandVisible = hasReached(phase, "brandReveal");
  const brandHolding = hasReached(phase, "brandHold");
  const brandLifted = hasReached(phase, "brandLift");
  const ctasVisible = hasReached(phase, "ctaReveal");
  const qrVisible =
    hasReached(phase, "qrVisible") &&
    Boolean(payload?.qr?.imageDataUrl) &&
    !["success", "idle"].includes(payload?.qr?.status || "");
  const enteringShell = phase === "enterShell";
  const primaryBusy = Boolean(busyLabel) && !busyLabel.includes("重新检测");
  const retryBusy = busyLabel.includes("重新检测");
  const qrCopy =
    payload?.qr?.status === "waiting-confirm"
      ? "已扫码，请在手机上确认登录。"
      : "";

  return (
    <motion.section
      className="startup-scene"
      initial={false}
      animate={{
        opacity: enteringShell ? 0 : 1,
        scale: enteringShell ? 0.986 : 1,
        filter: enteringShell ? "blur(8px)" : "blur(0px)"
      }}
      transition={{ duration: 0.72, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="startup-stage">
        <div className="startup-stage-center">
          <div className="startup-brand-zone">
            <motion.div
              className="startup-brand-beam-slice"
              aria-hidden="true"
              initial={false}
              animate={{
                opacity: brandVisible ? (brandLifted ? 0.12 : brandHolding ? 0.24 : 0.18) : 0
              }}
              transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
            />

            <motion.div
              className="startup-brand-stack"
              initial={false}
              animate={{
                y: brandLifted ? -84 : 0,
                opacity: brandVisible ? 1 : 0
              }}
              transition={{
                y: { duration: 0.42, ease: [0.16, 1, 0.3, 1] },
                opacity: { duration: 0.28, ease: [0.22, 1, 0.36, 1] }
              }}
            >
              <div className="startup-brand-window">
                <motion.h1
                  className="startup-brand"
                  aria-label="Shadow"
                  initial={false}
                  animate={{
                    opacity: brandVisible ? 0.95 : 0.08,
                    y: brandVisible ? 0 : 72,
                    filter: brandVisible ? "blur(0px)" : "blur(10px)",
                    letterSpacing: brandVisible ? "-0.045em" : "-0.01em"
                  }}
                  transition={{
                    duration: 1.34,
                    ease: "linear"
                  }}
                >
                  {BRAND_LETTERS.map((letter, index) => (
                    <motion.span
                      key={`${letter}-${index}`}
                      className="startup-brand-letter"
                      aria-hidden="true"
                      initial={false}
                      animate={
                        brandVisible
                          ? {
                              opacity: 1,
                              x: 0,
                              y: 0,
                              filter: "blur(0px)",
                              rotateX: 0
                            }
                          : {
                              opacity: 0.16,
                              x: (index - 3) * 3,
                              y: 24,
                              filter: "blur(14px)",
                              rotateX: 20
                            }
                      }
                      transition={{
                        duration: 1.02,
                        delay: brandVisible ? 0.08 + index * 0.055 : 0,
                        ease: [0.19, 1, 0.22, 1]
                      }}
                      style={
                        {
                          transformPerspective: 860,
                          transformOrigin: "50% 78%",
                          "--hover-tilt": index % 2 === 0 ? "-2.4deg" : "2.4deg"
                        } as CSSProperties
                      }
                    >
                      <span className="startup-brand-letter-inner">
                        {letter}
                      </span>
                    </motion.span>
                  ))}
                </motion.h1>
              </div>
            </motion.div>
          </div>

          <motion.div
            className="startup-cta-stack"
            initial={false}
            animate={{
              opacity: ctasVisible ? 1 : 0
            }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="startup-cta-row">
              <motion.div
                className="startup-cta-stage"
                initial={false}
                animate={{
                  opacity: ctasVisible ? 1 : 0.04,
                  scale: ctasVisible ? 1 : 0.78,
                  rotateX: ctasVisible ? 0 : 76,
                  y: ctasVisible ? 0 : 24,
                  z: ctasVisible ? 0 : -140,
                  filter: ctasVisible ? "blur(0px)" : "blur(8px)"
                }}
                transition={{ duration: 0.78, ease: [0.16, 1, 0.3, 1] }}
                style={{ transformPerspective: 1600, transformOrigin: "50% 100%" }}
              >
                <motion.button
                  type="button"
                  className="startup-cta is-primary"
                  disabled={Boolean(busyLabel) || enteringShell}
                  onClick={onPrimaryAction}
                  initial={false}
                  animate={
                    ctasVisible && !enteringShell
                      ? {
                          y: [0, -1.4, 0],
                          scale: [1, 1.012, 1]
                        }
                      : { y: 0, scale: 1 }
                  }
                  transition={
                    ctasVisible && !enteringShell
                      ? {
                          duration: 4.5,
                          delay: 0.72,
                          repeat: Infinity,
                          ease: "easeInOut"
                        }
                      : { duration: 0 }
                  }
                  whileHover={
                    Boolean(busyLabel) || enteringShell
                      ? undefined
                      : {
                          y: -5,
                          scale: 1.026,
                          rotateX: -10,
                          rotateY: -4,
                          filter: "brightness(1.04)"
                        }
                  }
                  whileTap={Boolean(busyLabel) || enteringShell ? undefined : { y: -1, scale: 0.992 }}
                  style={{ transformPerspective: 1200, transformOrigin: "50% 50%" }}
                >
                  <span className="startup-cta-label">{primaryBusy ? "检测中..." : "启动 API"}</span>
                </motion.button>
              </motion.div>

              <motion.div
                className="startup-cta-stage"
                initial={false}
                animate={{
                  opacity: ctasVisible ? 1 : 0.04,
                  scale: ctasVisible ? 1 : 0.78,
                  rotateX: ctasVisible ? 0 : 76,
                  y: ctasVisible ? 0 : 24,
                  z: ctasVisible ? 0 : -140,
                  filter: ctasVisible ? "blur(0px)" : "blur(8px)"
                }}
                transition={{ duration: 0.78, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
                style={{ transformPerspective: 1600, transformOrigin: "50% 100%" }}
              >
                <motion.button
                  type="button"
                  className="startup-cta is-secondary"
                  disabled={Boolean(busyLabel) || enteringShell}
                  onClick={onRetry}
                  initial={false}
                  animate={
                    ctasVisible && !enteringShell
                      ? {
                          y: [0, -1.2, 0],
                          scale: [1, 1.01, 1]
                        }
                      : { y: 0, scale: 1 }
                  }
                  transition={
                    ctasVisible && !enteringShell
                      ? {
                          duration: 4.9,
                          delay: 0.94,
                          repeat: Infinity,
                          ease: "easeInOut"
                        }
                      : { duration: 0 }
                  }
                  whileHover={
                    Boolean(busyLabel) || enteringShell
                      ? undefined
                      : {
                          y: -5,
                          scale: 1.024,
                          rotateX: -10,
                          rotateY: 4,
                          filter: "brightness(1.05)"
                        }
                  }
                  whileTap={Boolean(busyLabel) || enteringShell ? undefined : { y: -1, scale: 0.992 }}
                  style={{ transformPerspective: 1200, transformOrigin: "50% 50%" }}
                >
                  <span className="startup-cta-label">{retryBusy ? "检测中..." : "重新检测"}</span>
                </motion.button>
              </motion.div>
            </div>

            <AnimatePresence>
              {qrVisible ? (
                <motion.div
                  className="startup-qr-card"
                  initial={{
                    opacity: 0,
                    scale: 0.88,
                    rotateX: 68,
                    y: 16,
                    filter: "blur(6px)"
                  }}
                  animate={{
                    opacity: 1,
                    scale: 1,
                    rotateX: 0,
                    y: 0,
                    filter: "blur(0px)"
                  }}
                  exit={{
                    opacity: 0,
                    scale: 0.94,
                    rotateX: 22,
                    y: 8,
                    filter: "blur(4px)"
                  }}
                  transition={{ duration: 0.56, ease: [0.16, 1, 0.3, 1] }}
                >
                  <motion.div
                    className="startup-qr-frame"
                    initial={false}
                    animate={
                      qrVisible
                        ? {
                            y: [0, -2.4, 0],
                            scale: [1, 1.014, 1],
                            rotateZ: [0, 0.35, 0]
                          }
                        : { y: 0, scale: 1, rotateZ: 0 }
                    }
                    transition={
                      qrVisible
                        ? {
                            duration: 5.8,
                            delay: 0.42,
                            repeat: Infinity,
                            ease: "easeInOut"
                          }
                        : { duration: 0 }
                    }
                    whileHover={
                      qrVisible
                        ? {
                            y: -5,
                            scale: 1.028,
                            rotateX: 8,
                            rotateY: -5,
                            rotateZ: -0.9,
                            filter: "brightness(1.025)"
                          }
                        : undefined
                    }
                    style={{ transformPerspective: 1400, transformOrigin: "50% 50%" }}
                  >
                    <img src={payload?.qr?.imageDataUrl || ""} alt="登录二维码" className="startup-qr-image" />
                  </motion.div>
                  <div className="startup-qr-copy">
                    <strong>请使用网易云音乐 App 扫码</strong>
                    {qrCopy ? <span>{qrCopy}</span> : null}
                  </div>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </motion.div>
        </div>
      </div>
    </motion.section>
  );
}
