import { KeyValueRow, NumberField, TextField } from "../components/primitives";

export function SettingsRoute({
  settingsPayload,
  settingsForm,
  setSettingsForm,
  onAction,
  onSave,
  onRefresh,
  onOpenReportDirectory
}: {
  settingsPayload: any;
  settingsForm: any;
  setSettingsForm: (updater: (prev: any) => any) => void;
  onAction: (method: string, successText: string) => void;
  onSave: () => void;
  onRefresh: () => void;
  onOpenReportDirectory: () => void;
}) {
  return (
    <div className="page-stack">
      <section className="two-column">
        <div className="panel">
          <div className="panel-head">
            <div>
              <div className="eyebrow">CONNECTION</div>
              <h3>当前连接状态</h3>
            </div>
          </div>
          <div className="key-value-list">
            <KeyValueRow label="模式" value={settingsPayload?.connection?.mode || "-"} />
            <KeyValueRow label="API" value={settingsPayload?.connection?.apiStatus || "-"} />
            <KeyValueRow label="Cookie" value={settingsPayload?.connection?.cookieStatus || "-"} />
            <KeyValueRow label="账号" value={settingsPayload?.connection?.accountNickname || "未登录"} />
            <KeyValueRow label="影子歌单" value={settingsPayload?.connection?.shadowPlaylistName || "未设置目标歌单"} />
          </div>
          <div className="toolbar wrap">
            <button className="secondary-button" onClick={() => onAction("detectApi", "已检测 API 状态")}>检测 API</button>
            <button className="secondary-button" onClick={() => onAction("startApi", "已尝试启动本地 API")}>启动本地 API</button>
            <button className="secondary-button" onClick={() => onAction("detectCookie", "已检测 Cookie 状态")}>检测 Cookie</button>
            <button className="ghost-button" onClick={() => onAction("clearCookie", "本地 Cookie 已清空")}>清空 Cookie</button>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <div>
              <div className="eyebrow">QR LOGIN</div>
              <h3>二维码登录</h3>
            </div>
            <button className="primary-button" onClick={() => onAction("startQrLogin", "二维码已生成")}>生成二维码</button>
          </div>
          {settingsPayload?.qr?.imageDataUrl ? (
            <img className="qr-image" src={settingsPayload.qr.imageDataUrl} alt="二维码登录" />
          ) : (
            <div className="empty-state">
              <div className="empty-icon">·</div>
              <h3>当前还没有二维码</h3>
              <p>点击右上按钮生成新的登录二维码。</p>
            </div>
          )}
          <p className="panel-note">{settingsPayload?.qr?.url || "二维码链接会显示在这里。"}</p>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <div className="eyebrow">AI SETTINGS</div>
            <h3>AI 文段配置</h3>
          </div>
        </div>
        <div className="field-grid">
          <label className="checkbox-row">
            <input type="checkbox" checked={settingsForm.ai_enabled} onChange={(event) => setSettingsForm((prev: any) => ({ ...prev, ai_enabled: event.target.checked }))} />
            <span>启用云端 AI</span>
          </label>
          <TextField label="Base URL" value={settingsForm.ai_base_url} onChange={(value) => setSettingsForm((prev: any) => ({ ...prev, ai_base_url: value }))} placeholder="https://api.openai.com/v1" />
          <TextField label="Model" value={settingsForm.ai_model} onChange={(value) => setSettingsForm((prev: any) => ({ ...prev, ai_model: value }))} placeholder="gpt-4o-mini" />
          <TextField label="API Key" type="password" value={settingsForm.ai_api_key} onChange={(value) => setSettingsForm((prev: any) => ({ ...prev, ai_api_key: value }))} placeholder="未填写时回退模板" />
          <NumberField label="超时（秒）" value={settingsForm.ai_timeout} min={5} max={120} onChange={(value) => setSettingsForm((prev: any) => ({ ...prev, ai_timeout: value }))} />
        </div>
        <div className="toolbar">
          <button className="primary-button" onClick={onSave}>保存 AI 配置</button>
        </div>
      </section>

      <section className="two-column">
        <div className="panel">
          <div className="panel-head">
            <div>
              <div className="eyebrow">DIAGNOSTICS</div>
              <h3>运行日志</h3>
            </div>
            <button className="ghost-button small" onClick={onRefresh}>刷新设置</button>
          </div>
          <div className="log-block">
            {(settingsPayload?.diagnostics?.logs || []).length ? (
              (settingsPayload?.diagnostics?.logs || []).map((line: string, index: number) => <div key={`${line}-${index}`}>{line}</div>)
            ) : (
              <div>当前没有诊断日志。</div>
            )}
          </div>
        </div>
        <div className="panel">
          <div className="panel-head">
            <div>
              <div className="eyebrow">ARCHIVE</div>
              <h3>数据管理</h3>
            </div>
          </div>
          <p className="panel-note">报告目录：{settingsPayload?.diagnostics?.reportDirectory || "-"}</p>
          <p className="panel-note">最近错误：{settingsPayload?.diagnostics?.lastError || "暂无错误"}</p>
          <div className="toolbar">
            <button className="secondary-button" onClick={() => onAction("requestFullArchiveRebuild", "已发起全量归档重建")}>全量重建归档</button>
            <button className="ghost-button" onClick={onOpenReportDirectory}>打开报告目录</button>
          </div>
        </div>
      </section>
    </div>
  );
}
