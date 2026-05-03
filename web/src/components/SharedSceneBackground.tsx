import { AnimatePresence, motion } from "framer-motion";
import type { CSSProperties } from "react";
import type { ShellEntryMode } from "../startup";

type BeamStage = "booting" | "beamGrow" | "beamRelax" | "settled";
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

const BEAM_STATE_MAP: Record<BeamStage, { vars: Record<string, number>; transition: { duration: number; ease: [number, number, number, number] } }> = {
  booting: {
    vars: {
      "--beam-progress": 0.02,
      "--beam-energy": 0.04,
      "--beam-focus": 1.24,
      "--beam-spread": 0.08,
      "--beam-length": 0.08
    },
    transition: { duration: 0.1, ease: [0.4, 0, 0.2, 1] }
  },
  beamGrow: {
    vars: {
      "--beam-progress": 0.82,
      "--beam-energy": 1,
      "--beam-focus": 1.16,
      "--beam-spread": 0.28,
      "--beam-length": 0.82
    },
    transition: { duration: 1.26, ease: [0.19, 1, 0.22, 1] }
  },
  beamRelax: {
    vars: {
      "--beam-progress": 1,
      "--beam-energy": 0.54,
      "--beam-focus": 0.58,
      "--beam-spread": 0.86,
      "--beam-length": 1
    },
    transition: { duration: 0.7, ease: [0.22, 1, 0.36, 1] }
  },
  settled: {
    vars: {
      "--beam-progress": 1,
      "--beam-energy": 0.46,
      "--beam-focus": 0.52,
      "--beam-spread": 0.94,
      "--beam-length": 1
    },
    transition: { duration: 0.42, ease: [0.22, 1, 0.36, 1] }
  }
};

export function SharedSceneBackground({
  beamStage,
  showButterflies,
  butterflyEntranceMode
}: {
  beamStage: BeamStage;
  showButterflies: boolean;
  butterflyEntranceMode: ShellEntryMode;
}) {
  const beamState = BEAM_STATE_MAP[beamStage];
  const butterflyTransition =
    butterflyEntranceMode === "shell-enter-home"
      ? { duration: 2.64, delay: 0.22, ease: [0.22, 1, 0.36, 1] as [number, number, number, number] }
      : { duration: 0.42, delay: 0.18, ease: [0.22, 1, 0.36, 1] as [number, number, number, number] };

  return (
    <motion.div
      className="scene-background"
      initial={false}
      animate={beamState.vars as any}
      transition={beamState.transition}
    >
      <div className="scene-background-base" />
      <div className="scene-beam-layer" aria-hidden="true">
        <span className="scene-beam-source" />
        <span className="scene-beam-core" />
        <span className="scene-beam-fog" />
      </div>

      <AnimatePresence>
        {showButterflies ? (
          <motion.div
            className="shell-butterfly-layer"
            aria-hidden="true"
            initial={butterflyEntranceMode === "shell-enter-home" ? { opacity: 0, y: 10, scale: 0.986, filter: "blur(20px)" } : { opacity: 0 }}
            animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
            exit={{ opacity: 0 }}
            transition={butterflyTransition}
          >
            {SHELL_BUTTERFLIES.map((butterfly, index) => (
              <span key={`${butterfly.src}-${index}`} className={`shell-butterfly is-${butterfly.role}`} style={butterfly.style}>
                <img className="shell-butterfly-shadow" src={butterfly.src} alt="" />
                <img className="shell-butterfly-rim" src={butterfly.src} alt="" />
                <img className="shell-butterfly-body" src={butterfly.src} alt="" />
              </span>
            ))}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.div>
  );
}
