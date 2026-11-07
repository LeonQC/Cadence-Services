# Google 登录接入教程

TodoApp 的 Google 登录已经实现完毕，代码全部就位。**剩下的只有申请 Google 凭据这一步，必须你本人操作**——它绑定你的 Google 账号，我拿不到也不该拿到。

全程大约 10 分钟，不花钱，不需要备案或审核。

---

## 目录

1. [第一步：在 Google Cloud Console 申请凭据](#第一步在-google-cloud-console-申请凭据)（你做）
2. [第二步：把凭据填进 .env](#第二步把凭据填进-env)（你做）
3. [第三步：启动并测试](#第三步启动并测试)（你做，我可以陪你排查）
4. [它是怎么工作的](#它是怎么工作的)
5. [代码改了哪些地方](#代码改了哪些地方)
6. [常见报错对照表](#常见报错对照表)

---

## 第一步：在 Google Cloud Console 申请凭据

### 1.1 创建项目

打开 https://console.cloud.google.com/

顶部有个项目下拉框（可能显示"选择项目"或某个已有项目名）→ 点它 → **新建项目**。

- 项目名称：随便填，比如 `TodoApp`
- 位置：保持"无组织"

点**创建**，等几秒，然后**确保顶部下拉框切换到了这个新项目**（这一步很容易漏，后面配置会配到别的项目上）。

### 1.2 配置 OAuth 同意屏幕

左侧菜单 → **API 和服务** → **OAuth 同意屏幕**

（新版界面可能叫 **Google 身份验证平台** → **概览**，点"开始使用"）

依次填：

| 项目 | 填什么 |
|---|---|
| 应用名称 | `TodoApp`（用户在授权页会看到这个名字） |
| 用户支持电子邮件 | 选你自己的邮箱 |
| 受众群体 / User Type | **外部 (External)** |
| 开发者联系信息 | 你的邮箱 |

保存。

> **关于"外部"和审核**：选"外部"后应用处于**测试 (Testing)** 状态。这个状态下**不需要 Google 审核**，但只有你手动添加的测试用户能登录。个人练习项目就停在这个状态即可，不要点"发布应用"。

### 1.3 添加测试用户 ⚠️ 别漏这步

在 **OAuth 同意屏幕** → **受众群体 / Audience** 页面，找到 **测试用户 (Test users)** → **ADD USERS**

**把你自己的 Gmail 地址加进去。** 不加的话登录时会报 `Error 403: access_denied`。

如果想让别人也能登，把他们的 Gmail 也加进来（上限 100 个）。

### 1.4 创建 OAuth 客户端 ID

左侧 → **API 和服务** → **凭据** → 顶部 **+ 创建凭据** → **OAuth 客户端 ID**

- **应用类型**：选 **Web 应用**（重要，别选"桌面应用"）
- **名称**：`TodoApp Web Client`

往下找到 **已获授权的重定向 URI**，点 **+ 添加 URI**。

**这里是最容易出错的地方。** 建议把下面两个**都**加上：

```
http://localhost:8000/auth/google/callback
http://127.0.0.1:8000/auth/google/callback
```

为什么加两个：`localhost` 和 `127.0.0.1` 在 Google 眼里是**两个完全不同的地址**，虽然它们指向同一台机器。uvicorn 默认监听 `127.0.0.1`，但你在浏览器里习惯敲 `localhost`。两个都登记就不会因为敲错而卡住。

> 注意：Google 只对 `localhost` / `127.0.0.1` 允许 `http://`，其他域名一律强制 `https://`。所以本地开发不需要证书。

点**创建**。弹窗会显示**客户端 ID** 和**客户端密钥**——先别关，下一步要用。（关掉了也没事，凭据页面随时能再看到，密钥可以重新下载。）

---

## 第二步：把凭据填进 .env

在 `TodoApp` 目录下（就是有 `main.py` 的那个目录）执行：

```powershell
copy .env.example .env
```

然后用编辑器打开 `.env`，填入刚才拿到的两个值：

```ini
GOOGLE_CLIENT_ID=1234567890-abcdefg.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxx
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```

三点提醒：

1. **等号两边不要加空格，值不要加引号。**
2. **`GOOGLE_REDIRECT_URI` 必须跟你在 1.4 登记的某一个逐字符相同**，包括 `http`、端口号、结尾没有斜杠。
3. **`.env` 已经被 `.gitignore` 忽略**，不会提交到 git。密钥不会泄露。（`.env.example` 是模板，不含真实值，照常提交。）

---

## 第三步：启动并测试

```powershell
cd "Project 4\Starting Files\Starting Project\TodoApp"
python -m uvicorn main:app --reload
```

> 提示：你的 `py` 启动器在 conda 环境的 cmd 里不在 PATH，用 `python` 即可（`(base)` 环境下等价于 `py -3.12`）。

浏览器打开 **http://localhost:8000/auth**（注意跟 `.env` 里填的保持一致）。

应该看到登录表单下方多了一条分隔线和 **Sign in with Google** 按钮。

点它 → 跳转 Google → 选择账号 → 同意 → 自动跳回 `/todos`，已登录。

### 会看到的额外提示

第一次授权时 Google 可能显示 **"Google 尚未验证此应用"**。这是"测试"状态的正常表现，点**高级** → **转至 TodoApp（不安全）** 继续即可。你自己的应用，安全。

### 验证是否真的关联上了

```powershell
python -c "import sqlite3; con=sqlite3.connect('todos.db'); [print(r) for r in con.execute('select id,username,email,google_sub from users')]"
```

用 Google 登录过的账号，`google_sub` 那一列会是一串数字（Google 给你的唯一 ID）。

---

## 它是怎么工作的

标准 OAuth 2.0 授权码流程：

```
   浏览器                    你的 app                       Google
     │                          │                             │
     │  点 "Sign in with Google"│                             │
     ├─────────────────────────▶│                             │
     │                          │ 生成随机 state              │
     │                          │ state 存进签名 cookie        │
     │  302 跳转（URL 带 state） │                             │
     │◀─────────────────────────┤                             │
     │                                                        │
     │  用户在 Google 页面选账号、同意                          │
     ├───────────────────────────────────────────────────────▶│
     │                                                        │
     │  302 跳回 /auth/google/callback?code=xxx&state=yyy      │
     │◀───────────────────────────────────────────────────────┤
     │                          │                             │
     ├─────────────────────────▶│ ① 对比 URL 里的 state       │
     │                          │    和 cookie 里的 state      │
     │                          │                             │
     │                          │ ② 用 code 换 id_token       │
     │                          ├────────────────────────────▶│
     │                          │◀────────────────────────────┤
     │                          │                             │
     │                          │ ③ 验证 id_token 签名        │
     │                          │ ④ 查/建 users 表记录        │
     │                          │ ⑤ 签发自己的 JWT            │
     │  302 跳 /todos + cookie  │                             │
     │◀─────────────────────────┤                             │
```

**关键点：Google 只负责第 ④ 步之前的"你是谁"。** 从第 ⑤ 步开始，走的还是你原本那套——同一个 `create_access_token()`、同一个 `access_token` cookie、同一套 `get_current_user()` 校验、同一个 Redis 登出黑名单。

所以 Google 登录进来的用户，登出时一样会被写进黑名单，token 一样即时失效。**`todos.py` 一行都没改。**

### 关于 `state`：为什么必须有

`state` 是防**登录 CSRF** 的。没有它，攻击者可以把自己的 `?code=...` 回调链接发给你，你一点就被悄悄登进**攻击者的账号**，之后你记的所有 todo 都存进了他能看到的账号里。

做法是"双提交"：同一个随机值，一份放进跳转 URL 交给 Google，一份用 `SECRET_KEY` 签名后放进 cookie。回调时两边必须对上。攻击者两个都伪造不了。

> 你参考的那篇 Medium 文章**没有实现 state**，直接照抄会带着这个漏洞。（那篇文章还有个更直接的问题：`api/auth/auth.py` 用了 `requests.Request()` 但从未 import `requests`，回调必崩 `NameError`。正确的是 `from google.auth.transport import requests`——注意这个 `requests` 不是 HTTP 库，是 google-auth 自带的传输层，名字撞了很容易搞混。）

### 账号关联规则

| 情况 | 行为 |
|---|---|
| `google_sub` 已存在 | 直接登入该账号 |
| `google_sub` 没有，但邮箱匹配已有账号，且 Google 说邮箱已验证 | **自动关联**，把 `google_sub` 写到该账号上，两种方式今后登同一账号、todo 共享 |
| 邮箱匹配已有账号，但 Google 说邮箱未验证 | **拒绝登录**，提示用密码登录（防账号接管） |
| 全都没匹配上 | 新建账号，用户名取邮箱 `@` 前面部分，重名自动加数字后缀 |

优先用 `google_sub` 而不是邮箱，因为 Google 的 `sub` 永不改变，而邮箱地址是可以改的。

**想改成别的策略**（比如永不自动关联、总是新建独立账号），改 `routers/auth.py` 里的 `find_or_create_google_user()` 即可，逻辑集中在一个函数里。

---

## 代码改了哪些地方

| 文件 | 改动 |
|---|---|
| `routers/auth.py` | 新增 `/auth/google` 和 `/auth/google/callback` 两个路由、`find_or_create_google_user()`、`unique_username()`、state cookie 的签发与校验；顺带修了 `authenticate_user()` 对无密码账号会崩溃的问题 |
| `models.py` | `Users` 增加 `google_sub` 字段（唯一、可空、带索引） |
| `migrate_add_google_sub.py` | **新增**，一次性迁移脚本（已运行） |
| `templates/login.html` | 增加 Google 登录按钮，未配置凭据时自动隐藏 |
| `.env.example` | **新增**，配置模板 |
| `requirements-google.txt` | **新增**，新依赖清单 |
| `.gitignore` | 增加 `.env` 和 `*.db.bak` |
| `routers/todos.py`、`main.py`、`redis_cache.py` | **未改动** |

新增依赖只有 `google-auth`（`httpx`、`python-dotenv` 你环境里本来就有）。

### 两个设计决定

**① state 用签名 cookie，不用 Redis。**

最初我把 state 存在 Redis 里，但那样 Redis 一停 Google 登录就整个不可用——你这台机器 Docker 反复自己停，实测就撞上了。改成签名 cookie 后无需任何外部存储，安全性等价（这也是 Authlib + SessionMiddleware 的底层做法）。**Google 登录不依赖 Redis。**

**② cookie 必须是 `SameSite=Lax`，不能是 `Strict`。**

回调是从 `accounts.google.com` 发起的跨站顶层跳转。`Strict` 会在恰好这个请求上扣住 cookie，导致每次登录都失败。`Lax` 允许顶层导航携带 cookie，同时仍然挡住跨站的表单提交和 iframe 请求。

---

## 常见报错对照表

| 报错 | 原因 | 怎么修 |
|---|---|---|
| `Error 400: redirect_uri_mismatch` | `.env` 里的 URI 跟 Google Console 登记的不一致 | 逐字符对比，注意 `localhost` vs `127.0.0.1`、端口、结尾斜杠。改完 Console 要等几秒生效 |
| `Error 403: access_denied` | 你的 Gmail 不在测试用户名单里 | 回 1.3 添加测试用户 |
| 页面提示 `Google login is not configured` | `.env` 没建、没填、或应用没重启 | 检查 `.env` 存在且两个值都填了；`--reload` 不会重新读 `.env`，**要完全重启进程** |
| 页面提示 `Invalid or expired login attempt` | state cookie 丢了或超过 5 分钟 | 重新点一次登录按钮。如果每次都这样，检查是不是浏览器屏蔽了 cookie |
| 页面提示 `Could not reach Google` | 后端连不上 Google | 检查代理。你有 `HTTP_PROXY=http://127.0.0.1:7897`，httpx 默认会走它——确认代理开着且能通 Google |
| 页面提示 `That email is already registered...` | 该邮箱已有账号且 Google 说邮箱未验证 | 用密码登录，或改 `find_or_create_google_user()` 的策略 |
| `Google 尚未验证此应用` | 应用处于测试状态 | 正常现象，点"高级"→"转至...（不安全）" |

---

## 回退

不想要这个功能了，把 `.env` 删掉或改名即可——按钮自动消失，`/auth/google` 给出提示而非报错，密码登录完全不受影响。数据库里的 `google_sub` 字段留着不碍事。
