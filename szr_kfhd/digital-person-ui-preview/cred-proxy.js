// 本地凭证代理：/api/* -> 127.0.0.1:18082，带开放 CORS（允许沙箱 iframe 的 null Origin）
// 仅为预览页演示用，不改项目任何代码；会话结束即停。
const http = require('http');
const TARGET_HOST = '127.0.0.1';
const TARGET_PORT = 18082;
const PORT = 18777;

http.createServer((req, res) => {
  const cors = {
    'Access-Control-Allow-Origin': req.headers.origin || '*',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': '*',
  };
  if (req.method === 'OPTIONS') {
    res.writeHead(204, cors);
    return res.end();
  }
  const upstream = http.request(
    {
      host: TARGET_HOST,
      port: TARGET_PORT,
      path: req.url,
      method: req.method,
      headers: { ...req.headers, host: TARGET_HOST + ':' + TARGET_PORT },
    },
    (pr) => {
      res.writeHead(pr.statusCode || 502, { ...pr.headers, ...cors });
      pr.pipe(res);
    }
  );
  upstream.on('error', (e) => {
    res.writeHead(502, cors);
    res.end(JSON.stringify({ error: 'proxy error: ' + e.message }));
  });
  req.pipe(upstream);
}).listen(PORT, '127.0.0.1', () => {
  console.log('cred proxy listening on http://127.0.0.1:' + PORT);
});
