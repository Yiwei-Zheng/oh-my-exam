# Oh My Exam Frontend

Next.js + TypeScript + shadcn 浏览器客户端. 设计系统固定使用 preset
`b27I38wi` (Rhea, neutral, blue, Figtree, Hugeicons). 管理后台包含题目搜索、
AI Token 账单、题目资产盘点和账号管理.

## 环境

- Node.js 20.19 或更高版本
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
npm run build
```

开发服务器把 `/api` 转发到后端. 如需修改目标地址, 设置 `OME_API_PROXY_TARGET`.

## 约定

- `app/`: App Router 页面边界.
- `components/ui/`: shadcn 组件源码.
- `components/admin/`: 管理端模块.
- `components/locale-provider.tsx`: 中英文文案与语言状态.
- 前端只通过版本化 HTTP API 使用后端能力.
