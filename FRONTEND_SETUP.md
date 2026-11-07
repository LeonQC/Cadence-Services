# TodoApp 前后端分离结构

项目现在包含两个可独立运行的应用：

- `main.py`：FastAPI 后端，负责数据库、鉴权和业务 API。
- `frontend/`：React + Vite 前端，页面和样式全部由前端项目管理。

## 启动后端

在项目根目录执行：

```powershell
uvicorn main:app --reload --port 8000
```

## 启动前端

打开第二个终端：

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

浏览器访问 `http://localhost:5173`。前端默认请求 `http://localhost:8000`，也可以通过环境变量覆盖：

```powershell
$env:VITE_API_URL="http://localhost:8000"
npm.cmd run dev
```

开发环境的 Vite 会把 `/api`、`/auth`、`/invite` 和 `/settings` 代理到 `http://localhost:8000`。生产部署时建议让反向代理把这些路径转发到 FastAPI，并设置 `TODOAPP_CORS_ORIGINS` 为实际前端域名。

## 当前 API

- `GET /api/me`：当前用户、工作区和团队信息
- `GET /api/teams/{team_key}/issues`：团队 Issue 列表
- `POST /api/teams/{team_key}/issues`：创建 Issue
- `PATCH /api/issues/{identifier}`：修改标题、描述、优先级或状态
- `DELETE /api/issues/{identifier}`：删除 Issue

登录仍使用后端的 HttpOnly Cookie，因此 React 不需要保存 JWT。FastAPI 不再挂载旧的 `/static` 目录，也不再注册旧的 Jinja HTML 页面路由；前端 UI 位于 `frontend/` 内。
