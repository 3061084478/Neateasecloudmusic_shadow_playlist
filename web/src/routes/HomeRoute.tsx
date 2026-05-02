import { motion } from "framer-motion";

export function HomeRoute({
  shell,
  currentFriend,
  homeCards
}: {
  shell: any;
  currentFriend: any;
  homeCards: Array<{ title: string; summary: string; detail: string; actions: Array<{ label: string; onClick: () => void }> }>;
}) {
  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.06,
        delayChildren: 0.04
      }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 18, scale: 0.985 },
    show: {
      opacity: 1,
      y: 0,
      scale: 1,
      transition: { duration: 0.26, ease: "easeOut" }
    }
  };

  return (
    <motion.div className="page-stack" variants={containerVariants} initial="hidden" animate="show">
      <motion.section className="home-overview-card" variants={itemVariants}>
        <div className="home-overview-inline">
          <span>当前账号/选中好友：</span>
          <strong>{shell.account?.nickname || "未登录"} / {currentFriend?.nickname || "未选择好友"}</strong>
        </div>
      </motion.section>

      <motion.section className="card-grid compact-grid dense-card-grid" variants={containerVariants}>
        {homeCards.map((card) => (
          <motion.div
            key={card.title}
            className="feature-card"
            variants={itemVariants}
            whileHover={{ y: -3, scale: 1.01 }}
            whileTap={{ scale: 0.992 }}
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
                  whileHover={{ y: -1, scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  {action.label}
                </motion.button>
              ))}
            </div>
          </motion.div>
        ))}
      </motion.section>
    </motion.div>
  );
}
