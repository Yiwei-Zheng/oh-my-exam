# Oh My Exam Frontend

Vue 3 + TypeScript 前端空工程. 当前仅完成开发环境和模块边界配置, 尚未实现产品页面或业务流程.

## 环境

- Node.js 20.17.0, 版本记录在 `.node-version`
- npm
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
