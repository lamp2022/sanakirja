#!/usr/bin/env python3
"""
Step 10: Local QC server for FI<->EN batch review.

Usage:
    python3 10_qc_server.py [batch_number]   # default batch 1

Navigate between batches with the Prev/Next buttons in the browser.
Keyboard: Tab/Enter = approve, type to correct, '-' + Enter = reject.
Mouse:    [✓] = approve, [✗] = reject.
Saves to: fi_en_batch_NN_decisions.json
"""
import http.server, json, os, socketserver, sys, urllib.parse, webbrowser

PORT = 8000


def find_batches():
    return sorted(
        int(f[len("fi_en_batch_"):-len(".json")])
        for f in os.listdir(".")
        if f.startswith("fi_en_batch_") and f.endswith(".json") and "_decisions" not in f
        and f != "fi_en_batch_review.json"
    )


def load_batch(num):
    path = f"fi_en_batch_{num:02d}.json" if isinstance(num, int) else f"fi_en_batch_{num}.json"
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_saved_decisions(batch_num):
    path = f"fi_en_batch_{batch_num:02d}_decisions.json" if isinstance(batch_num, int) else f"fi_en_batch_{batch_num}_decisions.json"
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {str(d["id"]): d for d in data.get("decisions", [])}


def make_html(batch_num, batch_data, batches):
    batch_json = json.dumps(batch_data, ensure_ascii=False)
    saved_json = json.dumps(load_saved_decisions(batch_num), ensure_ascii=False)
    total = len(batches)
    pos = batches.index(batch_num) + 1 if batch_num in batches else 0
    prev_num = batches[batches.index(batch_num) - 1] if batch_num in batches and batches.index(batch_num) > 0 else None
    next_num = batches[batches.index(batch_num) + 1] if batch_num in batches and batches.index(batch_num) < len(batches) - 1 else None
    prev_btn = f'<a class="nav-btn" href="#" onclick="saveAndGo(\'/?batch={prev_num}\')">← Prev</a>' if prev_num else '<span class="nav-btn disabled">← Prev</span>'
    next_btn = f'<a class="nav-btn" href="#" onclick="saveAndGo(\'/?batch={next_num}\')">Next →</a>' if next_num else '<span class="nav-btn disabled">Next →</span>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FI↔EN QC — Batch {batch_num}/{total}</title>
<style>
*{{box-sizing:border-box;font-family:system-ui,sans-serif;margin:0;padding:0}}
body{{padding:1rem;background:#f5f5f5}}
header{{display:flex;align-items:center;gap:.6rem;margin-bottom:1rem;flex-wrap:wrap}}
h1{{font-size:1.1rem}}
#progress{{font-size:.85rem;color:#666;margin-right:.4rem}}
.nav-btn{{padding:.3rem .75rem;background:#e5e7eb;color:#111;border:none;border-radius:4px;cursor:pointer;font-size:.85rem;text-decoration:none;display:inline-block}}
.nav-btn:hover{{background:#d1d5db}}
.nav-btn.disabled{{color:#aaa;pointer-events:none}}
#save-btn{{padding:.35rem .9rem;background:#0070f3;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:.85rem}}
#save-btn:hover{{background:#0060df}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
th{{background:#333;color:#fff;padding:.45rem .7rem;text-align:left;font-size:.8rem}}
td{{padding:.35rem .7rem;border-bottom:1px solid #eee;font-size:.85rem;vertical-align:middle}}
tr.auto td:first-child{{border-left:3px solid #22c55e}}
tr.review td:first-child{{border-left:3px solid #f59e0b}}
tr.borderline{{background:#fff8f8}}
tr.borderline td:first-child{{border-left:3px solid #ef4444}}
tr.done-approve{{background:#f0fdf4}}
tr.done-reject{{background:#fff0f0}}
tr.done-edit{{background:#eff6ff}}
tr:focus-within:not(.done-reject){{background:#fefce8 !important;outline:2px solid #eab308;outline-offset:-2px}}
input.en-input{{border:1px solid #ccc;border-radius:4px;padding:.2rem .45rem;width:155px;font-size:.85rem}}
input.en-input:focus{{outline:none;border-color:#0070f3;box-shadow:0 0 0 2px rgba(0,112,243,.2)}}
.action-btns{{display:flex;gap:.2rem}}
.btn-ok,.btn-no{{border:none;border-radius:4px;cursor:pointer;padding:.15rem .45rem;font-size:.8rem}}
.btn-ok{{background:#dcfce7;color:#15803d}}.btn-ok:hover{{background:#bbf7d0}}
.btn-no{{background:#fee2e2;color:#b91c1c}}.btn-no:hover{{background:#fecaca}}
.badge{{font-size:.72rem;padding:.1rem .35rem;border-radius:3px;white-space:nowrap}}
.badge-ok{{background:#dcfce7;color:#15803d}}
.badge-no{{background:#fee2e2;color:#b91c1c}}
.badge-edit{{background:#dbeafe;color:#1d4ed8}}
.pos{{font-size:.72rem;background:#e5e7eb;padding:.1rem .3rem;border-radius:3px;color:#555}}
.conf{{font-size:.7rem;padding:.1rem .3rem;border-radius:3px}}
.conf-auto{{background:#dcfce7;color:#15803d}}
.conf-review{{background:#fef3c7;color:#92400e}}
.conf-borderline{{background:#fee2e2;color:#b91c1c}}
</style>
</head>
<body>
<header>
  <h1>Batch {batch_num} / {total}</h1>
  <span id="progress">0 / {len(batch_data)} reviewed</span>
  {prev_btn}
  {next_btn}
  <button id="save-btn" onclick="saveBatch()">Save</button>
</header>
<table>
<thead><tr>
  <th>#</th><th>FI</th><th>EN (edit to correct)</th><th>POS</th>
  <th>Source</th><th>Conf</th><th>Action</th><th>Status</th>
</tr></thead>
<tbody id="rows"></tbody>
</table>
<script>
const BATCH={batch_json};
const BATCH_NUM={json.dumps(batch_num)};
const SAVED={saved_json};
const FINGERPRINT=BATCH.map(r=>r.id+r.fi).join(',');
const STORAGE_KEY='sanakirja_batch_{batch_num}_'+btoa(FINGERPRINT).slice(0,12);
let state=Object.assign({{}},SAVED);
try{{const s=localStorage.getItem(STORAGE_KEY);if(s)Object.assign(state,JSON.parse(s));}}catch(e){{}}

function esc(s){{return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}}

function save(){{localStorage.setItem(STORAGE_KEY,JSON.stringify(state));updateProgress();}}

function updateProgress(){{
  document.getElementById('progress').textContent=Object.keys(state).length+' / '+BATCH.length+' reviewed';
}}

function decide(id,action,enFinal){{
  const row=BATCH.find(r=>r.id===id);
  state[id]={{id,fi:row.fi,fi_pos:row.fi_pos,en_final:enFinal,action,en_original:row.en}};
  save();renderRow(id);
}}

function approve(id){{
  const row=BATCH.find(r=>r.id===id);
  const inp=document.getElementById('inp-'+id);
  const val=inp?inp.value.trim():'';
  const final=val===''?row.en:val;
  decide(id,val!==''&&val!==row.en?'edit':'approve',final);
}}

function reject(id){{decide(id,'reject',null);}}

function renderRow(id){{
  const row=BATCH.find(r=>r.id===id);
  const tr=document.getElementById('tr-'+id);
  if(!tr)return;
  const d=state[id];
  tr.className=row.confidence+(d?' done-'+(d.action==='edit'?'edit':d.action==='reject'?'reject':'approve'):'');
  const badge=tr.querySelector('.badge');
  if(badge){{
    if(!d){{badge.textContent='';badge.className='badge';}}
    else if(d.action==='approve'){{badge.textContent='✓';badge.className='badge badge-ok';}}
    else if(d.action==='reject'){{badge.textContent='✗';badge.className='badge badge-no';}}
    else{{badge.textContent='✎ '+esc(d.en_final);badge.className='badge badge-edit';}}
  }}
}}

function buildTable(){{
  const order={{borderline:0,review:1,auto:2}};
  const sorted=[...BATCH].sort((a,b)=>order[a.confidence]-order[b.confidence]);
  const tbody=document.getElementById('rows');
  tbody.innerHTML=sorted.map((row,i)=>{{
    const d=state[row.id];
    const src=row.source_lang+(row.source_lemma&&row.source_lemma!==row.fi?'→'+esc(row.source_lemma):'');
    const cls=row.confidence+(d?' done-'+(d.action==='edit'?'edit':d.action==='reject'?'reject':'approve'):'');
    const bdg=d?(d.action==='approve'?`<span class="badge badge-ok">✓</span>`:d.action==='reject'?`<span class="badge badge-no">✗</span>`:`<span class="badge badge-edit">✎ ${{esc(d.en_final)}}</span>`):`<span class="badge"></span>`;
    return `<tr id="tr-${{row.id}}" class="${{cls}}" onclick="document.getElementById('inp-${{row.id}}').focus()">
      <td>${{i+1}}</td>
      <td><strong>${{esc(row.fi)}}</strong></td>
      <td><input class="en-input" id="inp-${{row.id}}" value="${{esc(d&&d.action==='edit'?d.en_final:row.en)}}" data-id="${{row.id}}" data-orig="${{esc(row.en)}}"
           onkeydown="handleKey(event,${{row.id}})" onblur="if(!state[${{row.id}}])approve(${{row.id}})"></td>
      <td><span class="pos">${{esc(row.fi_pos)}}</span></td>
      <td>${{esc(src)}}</td>
      <td><span class="conf conf-${{row.confidence}}">${{row.confidence}}</span></td>
      <td class="action-btns">
        <button class="btn-ok" onclick="event.stopPropagation();approve(${{row.id}})">✓</button>
        <button class="btn-no" onclick="event.stopPropagation();reject(${{row.id}})">✗</button>
      </td>
      <td>${{bdg}}</td>
    </tr>`;
  }}).join('');
  const first=tbody.querySelector('input');
  if(first)first.focus();
  updateProgress();
}}

function handleKey(e,id){{
  if(e.key==='Enter'||(e.key==='Tab'&&!e.shiftKey)){{
    e.preventDefault();
    const inp=document.getElementById('inp-'+id);
    const v=inp?inp.value.trim():'';
    if(v==='-'||v==='0'){{reject(id);inp.value='';}}
    else{{approve(id);}}
    focusNext(id,1);
  }}else if(e.key==='Tab'&&e.shiftKey){{
    e.preventDefault();focusNext(id,-1);
  }}
}}

function focusNext(currentId,dir){{
  const inputs=Array.from(document.querySelectorAll('input.en-input'));
  const idx=inputs.findIndex(i=>parseInt(i.dataset.id)===currentId);
  const next=inputs[idx+dir];
  if(next)next.focus();
}}

async function saveAndGo(url){{
  await saveBatch();
  window.location.href=url;
}}

async function saveBatch(){{
  const btn=document.getElementById('save-btn');
  btn.textContent='Saving...';btn.disabled=true;
  try{{
    const resp=await fetch('/save',{{method:'POST',headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{batch:BATCH_NUM,decisions:Object.values(state)}})}});
    btn.textContent=resp.ok?'Saved ✓':'Error — retry';
    setTimeout(()=>{{btn.textContent='Save batch';btn.disabled=false;}},2000);
  }}catch(err){{btn.textContent='Error — retry';btn.disabled=false;}}
}}

buildTable();
</script>
</body>
</html>"""


class QCHandler(http.server.BaseHTTPRequestHandler):
    default_batch = 1

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            params = urllib.parse.parse_qs(parsed.query)
            raw = params.get("batch", [str(self.default_batch)])[0]
            batch_num = "review" if raw == "review" else int(raw) if raw.isdigit() else self.default_batch

            batches = find_batches()
            batch_data = load_batch(batch_num)
            if batch_data is None:
                self.send_response(404); self.end_headers()
                return

            body = make_html(batch_num, batch_data, batches).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

    def _origin_ok(self):
        # Reject cross-origin POSTs: only accept requests whose Origin (or
        # Host fallback) targets our own localhost:PORT. Prevents CSRF / DNS
        # rebinding from any other tab clobbering decisions files.
        allowed = {f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}"}
        origin = self.headers.get("Origin")
        if origin is not None:
            return origin in allowed
        host = self.headers.get("Host", "")
        return host in {f"localhost:{PORT}", f"127.0.0.1:{PORT}"}

    def do_POST(self):
        if self.path == "/save":
            if not self._origin_ok():
                self.send_response(403); self.end_headers(); return
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self.send_response(400); self.end_headers(); return

            batch_num = data.get("batch", self.default_batch)
            valid_batches = set(find_batches())
            if isinstance(batch_num, int):
                if batch_num not in valid_batches:
                    self.send_response(400); self.end_headers(); return
                out = f"fi_en_batch_{batch_num:02d}_decisions.json"
            elif batch_num == "review":
                out = "fi_en_batch_review_decisions.json"
            else:
                self.send_response(400); self.end_headers(); return
            with open(out, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            decisions = data.get("decisions", [])
            approved = sum(1 for d in decisions if d.get("action") == "approve")
            edited   = sum(1 for d in decisions if d.get("action") == "edit")
            rejected = sum(1 for d in decisions if d.get("action") == "reject")
            print(f"\nBatch {batch_num} → {out}")
            print(f"  Approved {approved}  Edited {edited}  Rejected {rejected}")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        else:
            self.send_response(404); self.end_headers()

    def log_message(self, fmt, *args):
        pass


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "1"
    batch_num = "review" if arg == "review" else int(arg)

    batches = find_batches()
    if not batches and batch_num != "review":
        print("No fi_en_batch_NN.json files found. Run 09_build_fi_en_pairs.py first.")
        sys.exit(1)
    if isinstance(batch_num, int) and batch_num not in batches:
        print(f"Batch {batch_num} not found. Available: {batches}")
        sys.exit(1)
    if batch_num == "review" and not os.path.exists("fi_en_batch_review.json"):
        print("fi_en_batch_review.json not found.")
        sys.exit(1)

    QCHandler.default_batch = batch_num

    if batch_num == "review":
        print(f"QC server: review batch at http://localhost:{PORT}")
    else:
        print(f"QC server: {len(batches)} batches at http://localhost:{PORT}")
        print(f"  Starting at batch {batch_num}. Use Prev/Next buttons to navigate.")
    print("  Tab/Enter = approve  |  edit + Enter = correct  |  '-' + Enter = reject")
    print("  Ctrl+C to stop")

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), QCHandler) as httpd:
        webbrowser.open(f"http://localhost:{PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
