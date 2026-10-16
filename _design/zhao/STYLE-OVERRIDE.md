# STYLE-OVERRIDE.md · 风格覆写令（G 定稿，优先级最高）

> 本文件覆盖 AGENTS.md 与设计稿中的视觉 token 值。**结构、组件类、信息架构照设计稿用；颜色/圆角/字体/阴影按本表。** token 名保持 design-system.css 原名，只换值——这样组件类全部继续生效。

## 浅色档（默认）

| Token | 值 | 说明 |
|---|---|---|
| `--bg` | `#ffffff` | 页面底 |
| `--surface` | `#ffffff` | 卡片/面板 |
| `--surface-subtle` | `#f8f9fa` | 表头/hover/次级面 |
| `--surface-sunken` | `#f8f9fa` | 引用来源卡底 |
| `--fg` | `#1a202c` | 正文/标题 |
| `--fg-secondary` | `#4a5568` | 导语 |
| `--muted` | `#718096` | 次要说明 |
| `--faint` | `#a0aec0` | 标签/时间戳 |
| `--border` | `#e2e8f0` | 发丝线 |
| `--border-strong` | `#2d3748` | 强调分隔 |
| `--accent` | `#1F7A50` | 绿色文字/图标/边框（白底 5.3:1） |
| `--accent-solid` | `#267a54` | 实心按钮底（白字 5.3:1） |
| `--accent-hover` | `#1f6a47` | 按钮悬停 |
| `--accent-tint` | `#e7f6ef` | 绿浅底 |
| `--on-accent` | `#ffffff` | 实心绿上的文字 |
| `--success` | `#38a16f`（tint `#e7f6ef`） | 在线/成功 |
| `--warn` | `#d69e2e`（tint `#fdf6e3`） | 进行中 |
| `--info` | `#3182ce`（tint `#e8f1fb`） | 信息 |
| `--border-accent` | `#42b983` | 绿描边（装饰可用，不作文字色） |
| `--radius` | `6px` | 全站唯一圆角（覆写设计稿 2px） |
| `--font-display` | 同 `--font-body` | 无衬线，不用宋体 |
| `--font-body` | `system-ui, -apple-system, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif` | |
| `--font-mono` | `ui-monospace, "SF Mono", Consolas, monospace` | 标签/端口/数字 |
| `--shadow-card` | `0 1px 2px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.06)` | 新增令牌，仅 panel/card 一级可用 |

## 深色档（data-theme="dark"）

| Token | 值 |
|---|---|
| `--bg` | `#2d3748` |
| `--surface` | `#313e51` |
| `--surface-subtle` | `#3a4657` |
| `--surface-sunken` | `#3a4657` |
| `--fg` | `#edf2f7` |
| `--fg-secondary` | `#a0aec0` |
| `--muted` | `#718096` |
| `--faint` | `#64748b` |
| `--border` | `#3d4c63` |
| `--border-strong` | `#a0aec0` |
| `--accent` | `#48bb78`（深底文字/图标） |
| `--accent-solid` | `#2f8f63`（按钮底，白字 4.7:1） |
| `--accent-hover` | `#35a374` |
| `--accent-tint` | `#1d3a2a` |
| `--border-accent` | `#48bb78` |

## 对 AGENTS.md §5.1 机械规则的修订

- 规则 1（裸色值）：照旧 0 命中，全部走 var(--)，唯一来源 = 各项目自己那份 design-system.css 的 :root。
- 规则 3（投影）：改为「只允许 `box-shadow: var(--shadow-card)` 或省略」，其余投影 0 命中。
- 规则 4（渐变）：照旧 0 命中（.rail mask 豁免保留）。
- 规则 2/5/6/7/8：照旧执行。
- 宋体/衬线：设计稿的衬线标题一律不用，标题用 var(--font-display)（无衬线 600）。
