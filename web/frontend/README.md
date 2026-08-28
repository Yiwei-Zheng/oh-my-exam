# Oh My Exam Web

React/Vite 官网与本地搜题页面。首页使用项目 `assets/` 中的视频；搜题页只在用户选科后加载对应 SQLite 数据库，在浏览器中完成 OCR 和索引化题干匹配，再通过本站代理取得原卷并按坐标裁切题目与答案。

## 同步题库

双击项目根目录下的 `tools/sync_web_databases.cmd`，或运行：

```powershell
npm run sync:databases
```

脚本会校验并把 `data/databases/**/*.sqlite` 同步到网页静态运行时，生成科目清单，并删除网页端已经过期的数据库副本。`npm run dev`、`npm run dev:lan` 和 `npm run build` 也会在启动前自动同步。

## 运行

```powershell
npm install
npm run dev
```

不要用 VS Code **Go Live** 运行完整搜题功能；静态服务器没有原卷代理 `/api/papers`。应使用上述 Vite 命令。

`npm run dev` 默认监听 `0.0.0.0`，同一局域网设备可通过开发机 IP 和 Vite 显示的端口访问。固定使用 4173 端口时运行：

```powershell
npm run dev:lan
```

手机端点击搜题页的图片上传区后，会先显示图片来源弹窗；选择“从本地相册选择”会打开系统图片选择器，选择“现场拍照”会请求浏览器打开后置相机。桌面端保持直接打开文件选择器，并支持在上传区粘贴图片。

生产构建与本地预览：

```powershell
npm run build
npm run preview
```

`dev` 与 `preview` 会提供 PDF 本地代理，代理按数据库记录的完整 URL 下载，并把原卷缓存在 `tmp/web-paper-cache/`。代理依次读取 `OH_MY_EXAM_PROXY`、常见的 `HTTPS_PROXY` / `HTTP_PROXY` 环境变量；Windows 下没有这些变量时，会自动使用当前用户启用的系统代理。浏览器把本次使用的 PDF 保存在页面会话内，“打开原卷”与“打开答案”进入本站源 PDF 路由，不会跳转到第三方页面；返回搜题会恢复原有题目、答案、候选结果与滚动位置。正式部署必须保留等价的 `/api/papers?url=...` 代理。

## 主要文件

- `src/App.jsx`：官网与搜题交互。
- `src/content.js`：中英文文案。
- `src/services/ocr.js`：本地 OCR 与图像预处理。
- `src/services/matcher.js`：倒排索引与题干相似度匹配。
- `src/services/paperSession.js`：当前页面会话的原卷下载与 Blob URL。
- `src/workers/database.worker.js`：WASM SQLite 加载与后台检索。
- `src/services/pdfCrop.js`：原卷下载与坐标裁切。
- `vite.config.js`：视频、科目数据库、OCR 模型和 PDF 代理。
