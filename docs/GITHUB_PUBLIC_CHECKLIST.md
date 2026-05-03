# GitHub 公开前检查清单

这份清单用于把 `V5` 作为公开源码仓库上传到 GitHub，同时尽量避免带出个人隐私、运行痕迹和本机环境信息。

## 1. 这类内容不要上传

- `config.json`
- `data/`
- `build/`
- `dist/`
- `release/`
- `runtime/`
- `web/node_modules/`
- 任何 Cookie、AI Key、聊天数据库、缓存、报告、日志、二维码图片
- 任何带本机绝对路径、内部交接内容或私人测试流程的脚本/文档

## 2. 当前仓库里建议排除的已跟踪文件

这些文件即使写进 `.gitignore`，如果已经被 Git 跟踪，仍需要手动从索引移除：

- `docs/shadow_v5_topic_handoff_2026-05-03.md`
- `tools/render_brand_draft.py`
- `tools/vacuum_qr_manual_test.ps1`
- `tools/vacuum_smoke_test.ps1`

执行下面的命令只会停止跟踪，不会删除你本地文件：

```powershell
git rm --cached docs/shadow_v5_topic_handoff_2026-05-03.md
git rm --cached tools/render_brand_draft.py
git rm --cached tools/vacuum_qr_manual_test.ps1
git rm --cached tools/vacuum_smoke_test.ps1
```

## 3. 首次公开前建议检查

### 查看当前变更

```powershell
git status --short
```

### 确认关键目录已被忽略

```powershell
git check-ignore -v config.json data release runtime web/node_modules
```

### 检查暂存区里到底要上传什么

```powershell
git diff --cached --stat
git diff --cached
```

### 搜索仓库里可能残留的本机路径或敏感字段

```powershell
rg -n "C:\\Users\\|cookie|ai_api_key|token|secret" .
```

如果 `cookie`、`ai_api_key` 只是出现在模板字段名、测试样例或业务代码逻辑里，这是正常的；重点是不要出现真实值。

## 4. 推荐的首次上传流程

以下命令默认你已经在 `V5` 目录内：

```powershell
git init
git branch -M main
git add .
git status
git commit -m "Initial public source release"
git remote add origin https://github.com/<your-name>/<your-repo>.git
git push -u origin main
```

如果你之前已经初始化过仓库，只需要从 `git add .` 开始执行即可。

## 5. 如果仓库已经有提交历史

如果这些隐私文件曾经被提交过，但还没推到 GitHub，建议先完成以下动作再首次公开：

```powershell
git rm --cached docs/shadow_v5_topic_handoff_2026-05-03.md
git rm --cached tools/render_brand_draft.py
git rm --cached tools/vacuum_qr_manual_test.ps1
git rm --cached tools/vacuum_smoke_test.ps1
git add .gitignore
git commit -m "Remove private files from public repo scope"
```

如果这些内容已经推到公开仓库，光删当前文件还不够，还需要额外清理 Git 历史。

## 6. 推荐仓库结构

公开时建议直接以 `V5` 作为 GitHub 仓库根目录，而不是上传更外层的个人工作目录。

## 7. 上传后建议再检查一次

- GitHub 网页仓库里是否出现了 `config.json`
- 是否出现了 `data/`、`release/`、`dist/`
- 是否还能搜到你的本机路径
- 是否出现了私人交接文档或内部测试脚本
- README 是否足够让别人理解项目用途和运行方式
