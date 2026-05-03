# Shadow V5 打包发布（Windows x64 便携版）

## 发布目标
- 最终产物为 `release\Shadow-V5-Portable.zip`
- 用户解压后，压缩包顶层直接看到 `Shadow.exe`
- 首次运行后产生的 `config.json`、缓存、归档、报告、临时文件都只写入解压目录内部
- 删除整个解压目录即可彻底清理

## 1. 构建桌面程序
在 `V5` 目录运行：

```powershell
pwsh -ExecutionPolicy Bypass -File .\tools\build_windows_release.ps1 -Clean
```

该脚本会：
- 构建前端 `web/dist`
- 打包桌面程序
- 注入 `config.template.json`
- 注入受控的 `runtime\NeteaseCloudMusicApi`

构建完成后主程序位于：

`dist\Shadow\Shadow.exe`

## 2. 生成纯净便携压缩包

```powershell
pwsh -ExecutionPolicy Bypass -File .\tools\package_portable.ps1
```

输出：

- `release\Shadow-V5-Portable`
- `release\Shadow-V5-Portable.zip`

该脚本会自动：
- 将 `Shadow.exe` 放到压缩包顶层
- 只复制运行所需的打包产物
- 删除发布副本中的 `config.json`、`data`、`logs`、`tmp`、`tmp_frames`
- 校验 `_internal\web\dist\index.html` 是否存在
- 校验 `_internal\runtime\NeteaseCloudMusicApi\server.js` 与 `node.exe` 是否存在
- 清理内置 API runtime 中不应随包发布的 `data`、`logs`、`tmp`、`tmp_frames`

## 3. 兼容旧命令

```powershell
pwsh -ExecutionPolicy Bypass -File .\tools\create_share_bundle.ps1
```

该脚本现在等价于调用：

```powershell
pwsh -ExecutionPolicy Bypass -File .\tools\package_portable.ps1
```

## 4. 运行与清理说明
- 用户直接双击 `Shadow.exe` 即可启动
- 程序首次运行后会在解压目录生成 `config.json`
- 报告、数据库、缓存、临时文件都在解压目录下的 `data\` 中
- 删除整个解压目录即可彻底清理

## 5. 发布前检查
- 不要把你本机根目录下的 `config.json`、`data\`、`tmp\`、`tmp_frames\` 当作发布内容
- 最终以 `release\Shadow-V5-Portable.zip` 为准，不直接拿源码目录发用户
