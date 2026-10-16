/* kb 换皮自检脚本：§5.1 八条机械规则 + 函数体逐字包含验证 */
const fs = require('fs');
const path = require('path');

const PAGE = 'C:/Users/gbb/Desktop/stady_all/xm/b_w/knowledge_base/web/page';
const BACKUP = 'C:/Users/gbb/Desktop/项目/_backup/20261015_kb_1';

const files = {
  chat: fs.readFileSync(path.join(PAGE, 'chat.html'), 'utf8'),
  imp: fs.readFileSync(path.join(PAGE, 'import.html'), 'utf8'),
  dsc: fs.readFileSync(path.join(PAGE, 'design-system.css'), 'utf8'),
};
const bak = {
  chat: fs.readFileSync(path.join(BACKUP, 'chat.html'), 'utf8'),
  imp: fs.readFileSync(path.join(BACKUP, 'import.html'), 'utf8'),
};

const results = [];
function check(name, ok, detail) {
  results.push({ name, ok, detail });
}

/* ---------- 规则1：锚定颜色属性的裸色值 ---------- */
const re1 = /(?:color|background|border|fill|stroke)\s*:[^;]*#[0-9a-fA-F]{3,8}|\brgba?\(|\bhsla?\(/;
for (const [k, src] of Object.entries(files)) {
  const lines = src.split('\n');
  const hits = [];
  lines.forEach((l, i) => {
    if (l.trim().startsWith('/*') || l.trim().startsWith('*')) return; // 注释行豁免
    if (re1.test(l)) {
      // design-system.css 的 :root / [data-theme] / 打印 token 定义块豁免
      if (k === 'dsc') {
        let depth = 0, inRoot = false;
        // 简化：token 定义行形如 `--xxx: value;` 直接豁免
        if (/^\s*--[a-z-]+\s*:/i.test(l)) return;
        // .rail mask 的 linear-gradient(#000…) 豁免
        if (/mask-image/.test(l)) return;
      }
      hits.push(`L${i + 1}: ${l.trim().slice(0, 120)}`);
    }
  });
  check(`R1 裸色值 ${k}`, hits.length === 0, hits.join(' | ') || '0 命中');
}

/* ---------- 规则2：裸圆角 ---------- */
const re2 = /border-radius\s*:\s*(?!\s*var\(--radius\))/;
for (const [k, src] of Object.entries(files)) {
  const hits = [];
  src.split('\n').forEach((l, i) => {
    if (re2.test(l)) {
      // design-system.css 已知合法：50% 功能圆点 / 0 直角复位（存量清单）
      if (k === 'dsc' && /border-radius\s*:\s*(50%|0)\s*[;}/]/.test(l)) return;
      hits.push(`L${i + 1}: ${l.trim().slice(0, 120)}`);
    }
  });
  check(`R2 裸圆角 ${k}`, hits.length === 0, hits.join(' | ') || '0 命中');
}

/* ---------- 规则3：投影（只允许 var(--shadow-card)） ---------- */
const re3 = /box-shadow\s*:\s*(?!\s*var\(--shadow-card\))/;
for (const [k, src] of Object.entries(files)) {
  const hits = [];
  src.split('\n').forEach((l, i) => { if (re3.test(l)) hits.push(`L${i + 1}: ${l.trim()}`); });
  check(`R3 投影 ${k}`, hits.length === 0, hits.join(' | ') || '0 命中');
}

/* ---------- 规则4：渐变/毛玻璃（.rail mask 豁免） ---------- */
const re4 = /linear-gradient|radial-gradient|conic-gradient|backdrop-filter|filter\s*:\s*blur/;
for (const [k, src] of Object.entries(files)) {
  const hits = [];
  src.split('\n').forEach((l, i) => {
    if (re4.test(l)) {
      if (k === 'dsc' && /mask-image/.test(l)) return; // 功能性豁免
      if (l.trim().startsWith('*') || l.trim().startsWith('/*')) return; // 注释
      hits.push(`L${i + 1}: ${l.trim().slice(0, 120)}`);
    }
  });
  check(`R4 渐变/毛玻璃 ${k}`, hits.length === 0, hits.join(' | ') || '0 命中（dsc mask 豁免 2 行另计）');
}

/* ---------- 规则5：负字距 ---------- */
const re5 = /letter-spacing\s*:\s*-/;
for (const [k, src] of Object.entries(files)) {
  const hits = src.split('\n').filter(l => re5.test(l));
  check(`R5 负字距 ${k}`, hits.length === 0, `${hits.length} 命中`);
}

/* ---------- 规则6：emoji ---------- */
const re6 = /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}]/u;
const exempt = new Set(['\u2192', '\u2190', '\u2191', '\u2193', '\u00B7', '\u2014', '\u2265', '\u2264', '\u00D7', '\u2713']);
for (const [k, src] of Object.entries(files)) {
  const hits = [];
  src.split('\n').forEach((l, i) => {
    for (const ch of l) {
      if (re6.test(ch) && !exempt.has(ch)) { hits.push(`L${i + 1}: U+${ch.codePointAt(0).toString(16)} ${l.trim().slice(0, 80)}`); break; }
    }
  });
  check(`R6 emoji ${k}`, hits.length === 0, hits.join(' | ') || '0 命中（✓ U+2713 属排版符号豁免）');
}

/* ---------- 规则7：外链资源引用（锚定标签属性） ---------- */
const re7 = /<(?:script|img)\b[^>]*\ssrc\s*=\s*["']https?:\/\/|<link\b[^>]*\shref\s*=\s*["']https?:\/\//;
for (const [k, src] of Object.entries(files)) {
  check(`R7 外链资源 ${k}`, !re7.test(src), re7.test(src) ? '有命中' : '0 命中');
}

/* ---------- 规则8：新增 <12px 字号 ---------- */
const re8 = /font-size\s*:\s*(\d+(?:\.\d+)?)(px|rem|em)/;
for (const [k, src] of Object.entries(files)) {
  const hits = [];
  src.split('\n').forEach((l, i) => {
    const m = l.match(re8);
    if (m) {
      const px = m[2] === 'px' ? parseFloat(m[1]) : parseFloat(m[1]) * 16;
      if (px < 12) {
        // design-system.css 存量豁免清单（AGENTS.md §5.1 规则8）：.msg-avatar 11px / 打印态 .tbl 10.5px
        if (k === 'dsc' && (px === 11 || px === 10.5)) return;
        hits.push(`L${i + 1}: ${l.trim().slice(0, 100)}`);
      }
    }
  });
  check(`R8 字号下限 ${k}`, hits.length === 0, hits.join(' | ') || '0 命中');
}

/* ---------- 附加：overflow-x:hidden ---------- */
for (const [k, src] of Object.entries(files)) {
  check(`R9 overflow-x:hidden ${k}`, !/overflow-x\s*:\s*hidden/.test(src), /overflow-x\s*:\s*hidden/.test(src) ? '有命中' : '0 命中');
}

/* ---------- 函数体逐字包含验证 ---------- */
function norm(s) { return s.split('\n').map(l => l.replace(/\s+$/, '')).join('\n'); }

// chat.html：备份脚本整段（唯一差异 = renderProgress 的 ✅→✓、⏳→…）
const bakChatScript = bak.chat.slice(bak.chat.indexOf('    // 默认同源'), bak.chat.indexOf('</script>', bak.chat.indexOf('setTimeout(() => inputEl.focus(), 200);')));
const chatExpected = norm(bakChatScript
  .replace('`✅ ${x}`', '`✓ ${x}`')
  .replace('`⏳ ${x}`', '`… ${x}`'));
check('CHAT SSE/逻辑函数体逐字一致', norm(files.chat).includes(chatExpected),
  norm(files.chat).includes(chatExpected) ? '备份脚本段（应用唯一声明的两处 emoji→排版符号替换后）逐字节包含于新文件' : '存在差异');

// 关键锚点单独再验
for (const anchor of [
  "const API_BASE = `${location.protocol}//${location.host}`.includes('http')",
  "const es = new EventSource(`${API_BASE}/stream/${session_id}`);",
  "es.addEventListener('delta', (e) => {",
  "es.addEventListener('final', (e) => {",
  "es.addEventListener('final_answer', (e) => {",
  "es.addEventListener('error', (e) => {",
  "await fetch(`${API_BASE}/query`, {",
  "await fetch(`${API_BASE}/status/${taskId}`);",
  "await fetch(`${API_BASE}/history/${sessionId}`);",
]) {
  check(`CHAT 锚点: ${anchor.slice(0, 44)}…`, norm(files.chat).includes(anchor), '包含');
}

// import.html：备份脚本整段（零改动）
const bakImpScript = bak.imp.slice(bak.imp.indexOf('    const dropZone'), bak.imp.indexOf('</script>', bak.imp.indexOf("}, 2000); // 每2秒轮询一次")));
check('IMPORT 上传/轮询函数体逐字一致', norm(files.imp).includes(norm(bakImpScript)),
  norm(files.imp).includes(norm(bakImpScript)) ? '备份脚本段逐字节包含于新文件（零改动）' : '存在差异');

for (const anchor of [
  "const API_BASE = 'http://127.0.0.1:8000';",
  "await fetch(`${API_BASE}/upload`, {",
  "formData.append('files', file);",
  "const res = await fetch(`${API_BASE}/status/${taskId}`);",
  "onclick=\"document.getElementById('fileInput').click()\"",
]) {
  check(`IMPORT 锚点: ${anchor.slice(0, 44)}…`, files.imp.includes(anchor), '包含');
}

/* ---------- 相对路径存在性 ---------- */
for (const f of ['design-system.css', 'icons.js']) {
  const ok = fs.existsSync(path.join(PAGE, f)) && files.chat.includes(`href="${f}"`) === false;
  const ref = files.chat.includes(f) && files.imp.includes(f);
  check(`相对路径 ${f} 存在于 web/page/`, fs.existsSync(path.join(PAGE, f)) && ref, fs.existsSync(path.join(PAGE, f)) ? '存在且两页均引用' : '缺失');
}

/* ---------- 汇总 ---------- */
let pass = 0, fail = 0;
for (const r of results) {
  console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.name}  ${r.detail ? '— ' + r.detail : ''}`);
  r.ok ? pass++ : fail++;
}
console.log(`\nRESULT: ${pass}/${results.length} PASS, ${fail} FAIL`);
