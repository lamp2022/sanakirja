#!/usr/bin/env python3
"""
Browse-only UI for the cleaned dictionary.
Shows FI→EN (data.json) and EN→FI (en_fi_data.json) — Finnish-English only.

Usage:
    python3 15_browse_server.py
    Open http://localhost:8001
"""
import http.server, json, socketserver, webbrowser

PORT = 8001
HTML = """<!doctype html>
<html><head>
<meta charset="utf-8">
<title>Sanakirja — Finnish-English Dictionary</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font: 15px/1.5 -apple-system, sans-serif; background: #fafafa; color: #222; }
.wrap { max-width: 900px; margin: 0 auto; padding: 24px; }
h1 { font-size: 22px; margin-bottom: 4px; }
.sub { color: #666; margin-bottom: 16px; font-size: 13px; }
.tabs { display: flex; gap: 4px; margin-bottom: 12px; }
.tab { padding: 8px 16px; background: #eee; border-radius: 6px 6px 0 0; cursor: pointer; user-select: none; }
.tab.active { background: #fff; font-weight: 600; }
.search { width: 100%; padding: 10px 14px; font-size: 16px; border: 1px solid #ccc; border-radius: 6px; margin-bottom: 12px; }
.stats { color: #888; font-size: 13px; margin-bottom: 8px; }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 8px 12px; border-bottom: 1px solid #eee; background: #fff; }
.row:hover { background: #f5f5f5; }
.fi { font-weight: 600; }
.en { color: #333; }
.alt { color: #888; font-size: 13px; }
.list { background: #fff; border: 1px solid #e5e5e5; border-radius: 6px; }
.empty { padding: 40px; text-align: center; color: #888; }
</style>
</head><body>
<div class="wrap">
  <h1>Sanakirja</h1>
  <div class="sub">Finnish ↔ English dictionary</div>
  <div class="tabs">
    <div class="tab active" data-tab="fi-en">Finnish → English</div>
    <div class="tab" data-tab="en-fi">English → Finnish</div>
  </div>
  <input class="search" placeholder="Search…" id="q">
  <div class="stats" id="stats"></div>
  <div class="list" id="list"></div>
</div>
<script>
let fiEn = [], enFi = [], current = 'fi-en';

async function load() {
  fiEn = await fetch('/data.json').then(r => r.json());
  enFi = await fetch('/en_fi_data.json').then(r => r.json());
  render();
}

function render() {
  const q = document.getElementById('q').value.toLowerCase().trim();
  const data = current === 'fi-en' ? fiEn : enFi;
  const filtered = q
    ? data.filter(d => {
        const fi = (Array.isArray(d.fi) ? d.fi.join(' ') : d.fi || '').toLowerCase();
        const en = (Array.isArray(d.en) ? d.en.join(' ') : d.en || '').toLowerCase();
        return fi.includes(q) || en.includes(q);
      })
    : data;

  document.getElementById('stats').textContent =
    `${filtered.length.toLocaleString()} entries${q ? ` (filtered from ${data.length.toLocaleString()})` : ''}`;

  const list = document.getElementById('list');
  if (!filtered.length) {
    list.innerHTML = '<div class="empty">No results</div>';
    return;
  }
  // Cap to 500 displayed for perf
  const slice = filtered.slice(0, 500);
  list.innerHTML = slice.map(d => {
    const fi = Array.isArray(d.fi) ? d.fi : [d.fi];
    const en = Array.isArray(d.en) ? d.en : [d.en];
    if (current === 'fi-en') {
      return `<div class="row"><div class="fi">${fi[0] || ''}</div>
        <div class="en">${en[0] || ''}${en.length > 1 ? ` <span class="alt">· ${en.slice(1).join(', ')}</span>` : ''}</div></div>`;
    } else {
      return `<div class="row"><div class="en">${en[0] || ''}</div>
        <div class="fi">${fi[0] || ''}${fi.length > 1 ? ` <span class="alt">· ${fi.slice(1).join(', ')}</span>` : ''}</div></div>`;
    }
  }).join('');
  if (filtered.length > 500) {
    list.innerHTML += `<div class="empty">…and ${filtered.length - 500} more — refine search</div>`;
  }
}

document.querySelectorAll('.tab').forEach(t => {
  t.onclick = () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    current = t.dataset.tab;
    render();
  };
});
document.getElementById('q').oninput = render;
load();
</script>
</body></html>"""


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML.encode('utf-8'))
            return
        return super().do_GET()


with socketserver.TCPServer(("", PORT), Handler) as httpd:
    url = f"http://localhost:{PORT}"
    print(f"Browsing dictionary at {url}")
    webbrowser.open(url)
    httpd.serve_forever()
