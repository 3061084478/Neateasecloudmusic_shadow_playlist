# Shadow V5

Shadow V5 是一个基于 `PySide6 + QWebEngineView + Web UI` 的网易云音乐桌面工具，围绕聊天记录、歌曲分享、影子歌单和音乐关系分析进行整理与展示。

## 功能概览

- `歌曲分享`：在指定范围内提取与当前好友私信中的歌曲记录。
- `影子歌单`：基于候选歌曲生成或覆盖目标歌单。
- `聊天记录`：按范围查询并整理聊天内容。
- `音乐关系`：生成单好友画像、我的音乐社交分析和报告内容。
- `设置`：查看 API、Cookie、目标歌单与 AI 文段配置状态。

## 技术结构

- 桌面端：`PySide6`
- Web 容器：`QWebEngineView`
- 前端：`web/`
- 业务逻辑：`core/`、`services/`
- 桥接层：`ui/web_bridge.py`
- 启动入口：`main.py`

## 本地开发

### 1. 安装 Python 依赖

```powershell
pip install -r requirements.txt
```

### 2. 前端依赖与构建

```powershell
cd web
npm install
npm run build
cd ..
```

### 3. 启动桌面程序

```powershell
python .\main.py
```

## 便携版说明

- 冻结/打包后，程序会以 `Shadow.exe` 所在目录作为运行根目录。
- `config.json`、缓存、归档、报告、临时文件都会写在当前解压目录内部。
- 删除整个解压目录即可清理程序运行产生的全部内容。

## 隐私与公开仓库注意事项

- 不要提交 `config.json`、`data/`、`build/`、`dist/`、`release/`、`runtime/`、`web/node_modules/`。
- 不要提交任何 Cookie、AI Key、聊天数据库、缓存、报告和二维码登录数据。
- 公开仓库前，请先阅读 [docs/GITHUB_PUBLIC_CHECKLIST.md](docs/GITHUB_PUBLIC_CHECKLIST.md)。

## 发布

- 便携版构建与打包流程见 [RELEASE_GUIDE.md](RELEASE_GUIDE.md)。
