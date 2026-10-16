// kb 活体 -> 项目展示副本 同步脚本（指挥官执行）
// 同步前先备份项目副本，同步后打印字节数自证
const fs = require('fs');
const path = require('path');

const LIVING = 'C:/Users/gbb/Desktop/stady_all/xm/b_w/knowledge_base/web/page';
const PROJ = 'C:/Users/gbb/Desktop/项目/b_w/knowledge_base/web/page';
const BK = 'C:/Users/gbb/Desktop/项目/_backup/20261015_kb_sync';

// 1. 备份项目副本将被覆盖的两个文件
fs.mkdirSync(BK, { recursive: true });
for (const f of ['chat.html', 'import.html']) {
  fs.copyFileSync(path.join(PROJ, f), path.join(BK, f));
  console.log('backup', f, fs.statSync(path.join(BK, f)).size, 'bytes');
}

// 2. 活体 -> 项目副本（4 个文件：2 页 + 2 个新资源）
const files = ['chat.html', 'import.html', 'design-system.css', 'icons.js'];
let allOk = true;
for (const f of files) {
  const src = path.join(LIVING, f);
  const dst = path.join(PROJ, f);
  fs.copyFileSync(src, dst);
  const a = fs.statSync(src).size;
  const b = fs.statSync(dst).size;
  const ok = a === b;
  if (!ok) allOk = false;
  console.log('sync', f, a, '->', b, ok ? 'OK' : 'MISMATCH');
}
console.log(allOk ? 'ALL OK' : 'HAS MISMATCH');
