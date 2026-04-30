# Shadow V5 打包发布（Windows）

## 目标
让最终用户无需安装 Python 依赖，双击即可启动 `Shadow`。

## 1. 构建可执行程序
在 `V5` 目录运行：

```powershell
pwsh -ExecutionPolicy Bypass -File .\tools\build_windows_release.ps1 -Clean
```

构建完成后主程序在：

`dist\Shadow\Shadow.exe`

## 2. 生成便携分发包

```powershell
pwsh -ExecutionPolicy Bypass -File .\tools\package_portable.ps1
```

输出目录：

`release\Shadow-V5-Portable`

把这个目录打包发给客户即可。

## 3. 一键生成“可直接分享 ZIP（含内置 API 与 node）”

```powershell
pwsh -ExecutionPolicy Bypass -File .\tools\create_share_bundle.ps1
```

输出：

- `release\Shadow-V5-Share`（解压后目录）
- `release\Shadow-V5-Share.zip`（可直接发用户）

该脚本会自动：

- 将 `Shadow.exe` 放在解压首页（显眼位置）
- 生成 `00_双击启动_Shadow.bat`
- 移除本地 `config.json`、日志和私有数据目录
- 注入 `_internal\runtime\NeteaseCloudMusicApi`（含 `node.exe` 与 API 依赖）

## 4. 内置 API（可选）
如果你希望客户机器不安装 Node.js，也能自动启动 API，请在项目根目录放入：

`runtime\NeteaseCloudMusicApi\`

支持以下任一入口：

- `start_api.bat`
- `start_api.cmd`
- `start_api.ps1`
- `node.exe + server.js`

程序启动 API 时会优先检测内置运行包，其次才回退到 `npx NeteaseCloudMusicApi`。
