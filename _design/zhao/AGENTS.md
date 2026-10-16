# AGENTS.md · 4 套线上系统前端换皮执行手册

> 读者：AI 编码智能体。人看的详细版是 `交接文档.md`；两者冲突时以本文件为准。
> 本文件**不复述** `designs/design-system.css` 里能查到的任何数值（token、断点、组件类清单）。凡涉及具体值，一律打开该 CSS 现读。这里只缓存环境里查不到的东西：理由、坑、约定。

## 0. 角色与总原则

- 你是谁：AI 编码智能体。任务：把 4 套线上系统的**前端**改成 `designs/` 里设计稿的样子。
- 改动范围 = 前端表现层（组件、样式、页面结构）。**硬护栏：`api/` 目录、后端接口、数据库 schema、Agent 编排逻辑一行不改**（不可越界）。
  - 正向目标：所有交互照旧调用既有接口——列表仍拉原接口、提交仍打原端点、流式仍走原 SSE/WS，你只换界面皮。
- 零外部依赖纪律：不引 CDN、web 字体、图标库、图片资源。
  - 正向目标：需要图标就用 `icons.js` 注入的 sprite（`<use href="#i-…">`），需要图就用内联/占位块。理由：作品集首页要 GitHub Pages 离线秒开；设计稿全部内联，引入外部资源即破坏此前提。
- 完成定义：§5 全部可判定项通过，才允许说"完成"。任一项没过就说"未完成"并列出未过项。

## 1. 文件地图（从哪改到哪）—— 核心资产

每个 `designs/*.html` 对应一个线上路由，改该路由的源码页（仓库 `github.com/haojiezhao343-code/…`）：

| 设计稿 | 线上目标 | 源码文件 |
|---|---|---|
| `kb-chat.html` | 7954 `/chat.html` | `knowledge-base` → `web/page/chat.html` |
| `kb-import.html` | 7954 `/import.html` | `knowledge-base` → `web/page/import.html` |
| `research.html` | 8000 `/` | 联网调研前端（Vue3+Vite 单屏，无 router）——**前端源码不在任何公开仓库**，路径与 WS 事件一律以线上 `:8000` 实测为准，别因 GitHub 搜不到就卡住 |
| `support.html` | 18082 `/` | `dianshang` → `customer-service-frontend/`（Vue3+Vite 单屏，无 router） |
| `workspace.html` | 80 `/` | `ecommerce-operation-assistant` → `web/src/app/page.tsx` |
| `imports.html` | 80 `/imports` | `ecommerce-operation-assistant` → `web/src/app/imports/page.tsx` |
| `model-config.html` | 80 `/settings` | `ecommerce-operation-assistant` → `web/src/app/settings/page.tsx` |
| `login.html` | 80 `/login` | `ecommerce-operation-assistant` → `web/src/app/login/page.tsx` |
| `agent.html` | 80 `/agent` | `ecommerce-operation-assistant` → `web/src/app/agent/page.tsx` |
| `product-detail.html` | 80 `/products/[id]` | `ecommerce-operation-assistant` → `web/src/app/products/[id]/page.tsx` |
| `store-detail.html` | 80 `/stores/[id]` | `ecommerce-operation-assistant` → `web/src/app/stores/[id]/page.tsx` |
| `generation-job.html` | 80 `/products/[id]/generation-jobs/[jobId]` | `ecommerce-operation-assistant` → `web/src/app/products/[id]/generation-jobs/[jobId]/page.tsx` |
| `designs/index.html` | — | 设计稿总览目录页，不落地 |

- 每页设计稿顶部注释里已写明它对应的源码路径（例：`generation-job.html` 第 14 行），**以注释为准**；落地前用 `ls` 复核目标目录存在。
- :80 仓库另有 `agent-runs/[runId]`、`agent/tasks/[taskId]`、`agent/approvals/[approvalId]` 等子路由，**设计稿未覆盖，本次不动**。
- 仓库根 `index.html`（作品集首页）是已交付成品，不是本次改动目标。

## 2. 设计系统：指向 + 只缓存理由与坑

**消费规则（唯一真相源 `designs/design-system.css`）**：颜色 / 圆角 / 阴影 / 字体 / 间距 / 字阶 / 缓动 / 断点**只许 `var(--...)` 取值**，组件规则内不许出现裸色值、裸圆角、裸阴影。token 值、组件类清单、断点值一律现读该 CSS。

只缓存以下查不到的东西：

- **`--accent` 与 `--accent-solid` 为什么拆开**：同一值无法同时满足"实心按钮底要暗、白字才够对比"与"文字/边框要亮、深底才够对比"。曾因直接压暗 `--accent` 砸伤 54 处 accent 文字/边框用法。**改按钮底色时只许动 `--accent-solid`（及 `--accent-hover`），绝不动 `--accent`**。
- **中文排版**：`text-autospace: normal` 必须显式写（三家浏览器默认值都是 `no-autospace`，不写等于没开）；中文标题**不许负 letter-spacing**（汉字墨迹占 em 框 88–94%，负字距撞笔画）——标题字距一律取 0，只有全大写拉丁眉标（`.eyebrow`）才放开；正文行高 1.75–1.85。
- **对比度**：全站底线 ≥4.5，实测最低值写在 CSS 注释里。深色按钮 hover 态（3.81）是**已裁定接受的权衡**（瞬时态，基础态达标），不要"修"它。
- **无限动画预算**：仅限状态指示（状态灯 / 骨架 / 流式光标）；同一视口同时呼吸 ≤8，超出用 `animation-delay` 错峰（model-config 49 个已全部错峰）。
- **`.rail` 的 mask-image 渐隐是功能性豁免**（滚动可用性提示，不是装饰渐变），CSS 内有注释——**不许当违规渐变删掉**。
- **`body{overflow-x:hidden}` 禁用**：它会把真实溢出静默裁掉（历史两个 1px bug 都是被它掩盖的）。
  - 正向目标：溢出要修根因——给栅格列写 `minmax(0, 1fr)`，让内容在列内换行 / 滚动，而不是裁掉；验收时先把 `overflow-x` 临时改成 `visible` 再量（见 §5.3）。
- **`.tab` 上圆下直**（`var(--radius) var(--radius) 0 0`）是功能性形态（页签接直边面板），已裁定豁免。

### 2.1 三栈接入差异（按栈展开，不都用得上）

- **:80（Next.js 16 App Router + Tailwind 4）**：与设计稿同构度最高，从这里起步。把设计系统 CSS 引入 `globals.css`（`@import` 放在 Tailwind 之前，让工具类可覆盖组件类），或把 token 映射进 Tailwind `@theme`。**两套颜色体系不许混用**：要么全走设计 token，要么全走 Tailwind 色阶。`icons.js` 是 IIFE，需在客户端加载（根 layout 的 `<script>` 或 effect 里），并给 `<html>` 加 `class="js"`（`.reveal` 进场依赖它）。
- **7954（FastAPI + 原生 HTML，无框架）**：最简单。静态目录放 `design-system.css` / `icons.js`，页面加 `<link>` / `<script>`，**删掉页面内原有 `:root` 变量块**（旧 `--c-brand` 等会冲突），重写 DOM 套组件类。SSE / 上传逻辑不动。
- **8000 / 18082（Vue3 + Vite，单屏 SPA）**：在 `main.js` 顶部 `import` 设计系统 CSS；`icons.js` 在 `index.html` 或 `main.js` 引入。**不要把它改写成 Vue 组件**——纯 CSS 类直接写在 template 的 `class` 上。**这两个是单屏应用、没有 vue-router**：设计稿里的"左栏会话列表 / 右栏文件面板"是 `v-if` 面板开关，**别照设计稿加路由**。状态管理与 WS / API 调用不动。

## 3. 实施步骤（有序，每步带完成标准）

**Step 0 · 侦察**
读 `design-system.css` + 每页设计稿 + 每页对应源码，产出一份"设计稿用到、源码没有"的字段 / 状态清单。
完成标准：清单与 §4 的补渲染清单逐条一致，无遗漏。

**Step 1 · 共享层落地**
按 §2.1 把 `design-system.css` + `icons.js` 接进各栈并引入。
完成标准：任一页在 DevTools 里 `getComputedStyle(document.body).fontFamily` 与 `--font-body` 解析值一致；任一 `.btn` 的 computed `border-radius` 等于 `--radius` 的 computed 值；§5.1 的 R1–R4 对改动目录 grep 0 命中。

**Step 2 · :80 集群逐页移植**（workspace → imports → settings → login → agent → product-detail → store-detail → generation-job）
从同构度最高的 :80 起步。**每页改完立即跑该页验收**，不攒到最后。
完成标准（每页）：1440 宽浅 / 深 + 375 / 390 无横向溢出（§5.3）；该页 §4 列出的补渲染字段已出现在 TSX（`rg 字段名 web/src/app/...` 有命中）；空态 / 错误态 / 骨架态与设计稿逐一对应。

**Step 3 · Vue 两套**（research → support）
完成标准：未新增 vue-router（`package.json` diff 无 router）；面板切换仍是原有 `v-if`；1440 / 375 无溢出。

**Step 4 · 7954 两页**（kb-chat → kb-import）
完成标准：页面内旧 `:root` 变量块已删（grep 0 命中）；`git diff` 只含 DOM / 样式改动，SSE 与上传函数体 0 行改动。

## 4. 逐页实现要点（照抄设计稿之外必须知道的）

- **后端有字段、原前端从没渲染——应当补上（这是相对原版的核心增量）**：
  1. `AgentTask` 耗时 `finished_at − created_at`；
  2. `AgentApproval.note` 决策理由（reject 表单原来没接）；
  3. `AgentApproval.expires_at`；
  4. `catalog.coordinator`；
  5. `workflow.agents`（专家链）；
  6. `required_context_any`；
  7. `?section=` 锚点参数（声明未用）；
  8. `Store.platform_accounts` + 账号 3 态（active / expired / disabled）；
  9. `InventoryMovement` 五类型（inbound / outbound / adjustment / lock / release）。
  另有：`generation_jobs` 8 种事件、`_jimeng_status` 离散态、`video_generation` 返回的 `provider/model/size/duration`、取消仅限 pending / running。
- **生成任务不许编造进度百分比**：供应商只返回离散态（done / failed），**没有 0–100 字段**。设计稿用 5 阶段轨迹 + 耗时轨道（30 分超时预算是调度器兜底值）+ 历史 P50/P90 参考值替代。**前端照做，不要画假进度条。**
- **每页的空态 / 错误态 / 骨架屏设计稿里都有，逐态照抄**，不许只实现正常态。
- **登录页**：不许出现任何明文凭据（原版曾泄露，设计稿已改中性说明）；测试账号提示改成"向管理员获取"。
- **1 项无法在仓库核实的接口情报**（实现时以线上真实返回为准，设计稿以此为据）：8000 WS 的 `tool_start` / `assistant_call` 事件（前端源码不在任何公开仓库，见 §1 research 行）。其余三项已核实，别再当"待确认"：7954 `/health`（`knowledge-base` `main.py:246` 返回 `{"ok": true}`）、7954 `/status/{task_id}`（`main.py:137` 返回 `{code, task_id, status, done_list, running_list}`）、18082 的 6 流程节点定义在 `customer-service-backend/flow_config/user_flows.yml`（**不是 `refund_flow.yaml`**，流程名见 `交接文档.md` §7.6）。
- 各页"修掉了什么缺陷"的完整清单见 `交接文档.md` §4，逐页对照。

## 5. 验收（总闸）

### 5.1 八条机械规则（对每个改动过的前端源码目录跑）

用 ripgrep，**必须带 `-P`（PCRE2，负向断言要用）**；无 PCRE2 时用等价 `grep -rnP`。`<IMPL>` = 该栈改动目录：

1. 裸色值（意图：可见色一律 `var(--)`，样式里不许写死色值）：`rg -nP '(?:color|background|border|fill|stroke)\s*:[^;]*#[0-9a-fA-F]{3,8}|\brgba?\(|\bhsla?\(' <IMPL>` → **0 命中**。豁免：`design-system.css` 的 `:root` token 定义块；`.rail` mask 的 `#000`（css L531/532，alpha 通道不是颜色）；favicon data URI；注释行。通过标准还要求**锚定颜色属性**：正文 / 表格里的任务号 `#1042` / `#4821`、`RUN #119`、锚点 `#h-…` 都不是颜色，旧的无锚定版本在本包误报 44 处，一律不算命中。
2. 裸圆角（意图：圆角一律 `var(--radius)`，不许胶囊按钮 / 圆形头像）：`rg -nP 'border-radius\s*:\s*(?!var\(--radius\))' <IMPL>`，命中必须逐行落在下列**已知合法清单**内，清单外 → **0 命中**。清单（存量已实测）：`border-radius:0` 直角复位 1 处 = `kb-import.html:96` `.trace-flush`；`border-radius:50%` 功能圆点 5 处 = `design-system.css:269` `.status-led`、`design-system.css:448` `.trace-dot`、`kb-chat.html:69` `.sess-dot`、`research.html:66` `.sess-dot`、`imports.html:96` `.opt-mark`（根 `index.html:225` `.status-led` 同理，属作品集首页存量）。`50%` 只许 3–8px 功能圆点，`9999px` 只许 sr-only；`.tab` 四值 `var(--radius) var(--radius) 0 0`（`workspace.html:151` / `support.html:176` / `store-detail.html:99` / `product-detail.html:93`）被上面负向断言自动豁免，是已裁定功能性形态。
3. 投影（意图：零投影，层级靠边框与底色区分）：`rg -nP 'box-shadow\s*:' <IMPL>` → **0 命中**，无豁免（全包现值就是 0，连 `box-shadow:none` 都不用写）。
4. 渐变 / 毛玻璃 / 模糊（意图：零渐变、零辉光、零玻璃拟态）：`rg -nP 'linear-gradient|radial-gradient|conic-gradient|backdrop-filter|filter\s*:\s*blur' <IMPL>` → 通过标准 = 命中**只允许** `design-system.css` L531/532 的 `.rail` mask 两行（功能性渐隐，css L524–530 有注释，不许当违规渐变删），其余 **0 命中**。豁免：注释行——css L292 注释文本含字面 `backdrop-filter`，那是「已禁用」的说明，不是用法。
5. 负字距（意图：中文标题不许负字距，汉字墨迹占 em 框 88–94%）：`rg -nP 'letter-spacing\s*:\s*-' <IMPL>` → **0 命中**，无豁免。
6. emoji（意图：不许拿 emoji 当图标，图标一律 `icons.js` sprite）：`rg -nP '[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{FE0F}]' <IMPL>` → **0 命中**。豁免：排版符号 `→` `←` `↑` `↓` `·` `—` `≥` `≤` `×` `✓` 不算图标。
7. 外部资源（意图：零外部依赖、离线可开，`<script src>` / `<link href>` / `<img src>` 不许指向远程）：`rg -nP '<(?:script|img)\b[^>]*\ssrc\s*=\s*["'']https?://|<link\b[^>]*\shref\s*=\s*["'']https?://' <IMPL>` → **0 命中**。豁免：`<a href>` 外链跳转不算；展示型 URL（`input` 的 `placeholder` / `value`、正文表格里的商品链接、JSON 示例字段、favicon data URI）不算资源引用。通过标准要求**锚定标签属性**而非任意 http 串——旧规则 scope 写成「任何 URL 字符串」时 25/25 全误报。
8. 字号下限（意图：投影仪可读性，新增样式一律 ≥12px）：`rg -nP 'font-size\s*:\s*\d' <IMPL>`，每条命中必须落在下列**存量例外清单**内，清单外 → **0 命中**。清单（共 5 处，已渲染实测）：`design-system.css:406` `.msg-avatar` 11px；`design-system.css:604` 打印态 `.tbl` 10.5px（A4 横版窄字号换列）；`research.html:189` `.file-kind` 11px；`workspace.html:176` `.tbl-cover` 10px；`store-detail.html:191` `.tbl-cover` 10px。新增页面 / 组件规则出现 <12px 即不通过；确要新增先改本清单并写明理由。

另：全包 grep `overflow-x\s*:\s*hidden` 必须 **0 命中**（本轮已在 `designs/` 的 support / store-detail / model-config / login / product-detail / agent / generation-job 7 页移除；根 `index.html` 是已交付的作品集首页、不属本轮参照页，见 §1）。新代码同样禁止，见 §2 的 `body{overflow-x:hidden}` 条。

### 5.2 `verify.ps1`

在**作品集仓库根**（不在交付包内）跑 `powershell -ExecutionPolicy Bypass -File .\verify.ps1`。
完成标准：末行 `RESULT: 7/7 PASS`。注意它只测根 `index.html`（作品集首页），**设计页 / 落地页不在其覆盖内**，要另跑 §5.3。

### 5.3 渲染验收

- 每页在 **1440 宽浅色 + 1440 宽深色**、**375 与 390 宽**各渲一次。
- 完成标准：四组合下 `documentElement.scrollWidth == clientWidth`（无横向溢出）。
- **坑**：Chrome 无头有约 500px 最小窗口宽，直接开 375 会得到假象。**用 iframe 画框法**——外层固定 iframe 宽 375 / 390，在内层文档里量；并先把内层 `html,body` 的 `overflow-x` 临时改成 `visible`，否则 `overflow-x:hidden` 会把真实溢出藏起来（`verify.ps1` 的探针就是这么做的，可复用其思路）。

### 5.4 对比度抽测

抽 `--faint`、`--muted`、实心按钮（`--accent-solid` 配 `--on-accent`）各浅 / 深两档，实测值与 `design-system.css` 注释里的实测值逐一比对；全站最低值 ≥4.5。disabled 态（如 `opacity:.45` / `pointer-events:none` 的失效按钮）文本不参与 ≥4.5 静态扫描：WCAG 1.4.3 豁免非活动 UI 组件，已裁定；同理深色 hover 态 3.81 为已接受权衡。

### 5.5 完成标准

**§5.1–§5.4 全部可判定项通过，才许说"完成"。** 任一未过 → 报"未完成"并列出未过项。

## 6. 与 `交接文档.md` 的关系

`交接文档.md` 是给人看的详细版（背景、逐页缺陷、实测数字）。本文件是给 AI 的执行版。**两者冲突时以本文件为准**；需要更细的逐页说明时去读它。
