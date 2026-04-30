export function HomeRoute({
  shell,
  currentFriend,
  homeCards
}: {
  shell: any;
  currentFriend: any;
  homeCards: Array<{ title: string; summary: string; detail: string; actions: Array<{ label: string; onClick: () => void }> }>;
}) {
  return (
    <div className="page-stack">
      <section className="home-overview-card">
        <div className="home-overview-inline">
          <span>当前账号/选中好友：</span>
          <strong>{shell.account?.nickname || "未登录"} / {currentFriend?.nickname || "未选择好友"}</strong>
        </div>
      </section>

      <section className="card-grid compact-grid dense-card-grid">
        {homeCards.map((card) => (
          <div key={card.title} className="feature-card">
            <div className="feature-card-head">
              <h3>{card.title}</h3>
            </div>
            <div className="feature-card-copy">
              <p>{card.summary}</p>
              <small>{card.detail}</small>
            </div>
            <div className="feature-card-actions">
              {card.actions.map((action) => (
                <button key={action.label} className="secondary-button compact-action" onClick={action.onClick}>
                  {action.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
