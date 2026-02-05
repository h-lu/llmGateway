# TeachProxy Admin Frontend

基于 React 18 + TypeScript + Vite 构建的现代化管理面板，用于管理 TeachProxy AI 教学网关。

## 功能特性

- 📊 **Dashboard** - 系统概览、统计数据、活动趋势
- 👥 **学生管理** - 创建/编辑/删除学生、配额管理、API Key 重置
- 💬 **对话查看** - 按学生/操作筛选、内容搜索、JSON 导出
- 🛡️ **规则引擎** - 创建/编辑拦截规则、启用/禁用规则
- 📅 **周系统提示** - 管理每周的系统提示词设置

## 技术栈

- **React 18** - UI 框架
- **TypeScript** - 类型安全
- **Vite** - 构建工具
- **shadcn/ui** - UI 组件库
- **Tailwind CSS** - 样式
- **TanStack Query** - 服务端状态管理
- **React Router** - 路由
- **Recharts** - 图表

## 快速开始

### 安装依赖

```bash
cd web
npm install
```

### 开发模式

```bash
npm run dev
```

服务将运行在 http://localhost:5173

### 生产构建

```bash
npm run build
```

构建产物位于 `dist/` 目录。

### 环境变量

创建 `.env` 文件：

```bash
VITE_API_URL=http://localhost:8000
```

## 项目结构

```
web/
├── src/
│   ├── components/      # UI 组件
│   │   ├── layout.tsx   # 布局组件
│   │   ├── sidebar.tsx  # 侧边栏导航
│   │   └── ui/          # shadcn/ui 组件
│   ├── hooks/           # 自定义 hooks
│   ├── lib/             # 工具函数、API 客户端
│   ├── pages/           # 页面组件
│   ├── providers/       # React Context Providers
│   └── types/           # TypeScript 类型定义
├── public/              # 静态资源
└── index.html           # 入口 HTML
```

## 开发指南

### 添加新页面

1. 在 `src/pages/` 创建组件
2. 在 `src/App.tsx` 添加路由
3. 在 `src/components/sidebar.tsx` 添加导航项

### API 调用

使用 `src/lib/api.ts` 中定义的 API 客户端：

```typescript
import { studentsApi } from '@/lib/api';

// 在组件中使用
const { data } = useQuery({
  queryKey: ['students'],
  queryFn: () => studentsApi.list(),
});
```

### 组件规范

- 使用 shadcn/ui 组件作为基础
- 自定义样式使用 Tailwind CSS
- 复杂逻辑封装到自定义 hooks

## 测试

```bash
# 单元测试
npm run test

# E2E 测试
npm run test:e2e
```

## 与后端集成

确保后端服务已启动：

```bash
cd ..
uvicorn gateway.app.main:app --reload --port 8000
```

管理面板需要配置 Admin Token 进行认证。
