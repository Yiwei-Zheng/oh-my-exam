# Oh My Exam Frontend

Vue 3 + TypeScript 浏览器客户端，包含双语登录页和管理员后台。后台提供用户统计、活跃度、树状题库浏览及题库更新任务入口，暂不开放注册。

## 环境

- Node.js 20.17.0, 版本记录在 `.node-version`
- npm
- Element Plus 和 ECharts
- 后端默认运行于 `http://127.0.0.1:8000`

所有前端依赖安装在项目内的 `node_modules/`, npm 缓存写入项目内的
`.npm-cache/`. 不需要也不允许全局安装前端包.

## 命令

```powershell
npm install
npm run dev
npm run dev:lan
npm run lint
npm run typecheck
npm test
npm run build
```

开发服务器把 `/api` 转发到后端. 如需修改目标地址, 设置 `VITE_API_PROXY_TARGET`.

## 约定

- `src/router/`: URL 与页面路由边界.
- `src/stores/`: Pinia 客户端状态.
- `src/i18n/`: 中英文翻译资源.
- 后续业务模块按 feature 建目录, 不在 `App.vue` 中堆积业务逻辑.
- 前端只通过版本化 HTTP API 使用后端能力.
