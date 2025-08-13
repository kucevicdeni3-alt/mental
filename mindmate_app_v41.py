# mindmate_app_v42.py — Hero sa “planet glow” iza VSL-a + KPI + Chart (vraćeno),
# responsive dizajn, bez before/after; Pro Features + Comparison; Sticky CTA;
# Početna / Chat (Ollama ili OpenAI) / Check-in / Analitika (Plotly)

import os, json, requests, math
import streamlit as st
from datetime import datetime, date, timedelta
from streamlit.components.v1 import html as st_html

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

APP_TITLE = "MindMate"
DB_PATH   = os.environ.get("MINDMATE_DB", "mindmate_db.json")

# Chat backend env
CHAT_PROVIDER = os.environ.get("CHAT_PROVIDER", "ollama").lower().strip()
OLLAMA_HOST   = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL  = os.environ.get("OLLAMA_MODEL", "llama3.1")
OPENAI_API_KEY= os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL  = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

def safe_rerun():
    if hasattr(st, "rerun"): st.rerun()
    else: st.experimental_rerun()

st.set_page_config(page_title=APP_TITLE, page_icon="🧠", layout="wide")

# ---------- GLOBAL STYLES (responsive patch) ----------
st.markdown("""
<style>
/* Fluid main container */
.main .block-container{
  padding-top:.6rem!important; padding-left:3rem!important; padding-right:3rem!important;
  max-width:1440px!important; margin-inline:auto!important;
}
@media (max-width:1100px){ .main .block-container{padding-left:2rem!important;padding-right:2rem!important} }
@media (max-width:768px){ .main .block-container{padding-left:1rem!important;padding-right:1rem!important} }
.element-container > div:has(> iframe){display:flex; justify-content:center;}
.stButton>button[kind="primary"]{
  background:linear-gradient(90deg,#7C5CFF,#4EA3FF)!important;color:#0B0D12!important;
  font-weight:800!important;border:none!important
}
</style>
""", unsafe_allow_html=True)

# ---------- JSON “BAZA” ----------
def _init_db():
    if not os.path.exists(DB_PATH):
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump({"checkins": [], "chat_events": []}, f)
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {"checkins": [], "chat_events": []}
        data.setdefault("checkins", [])
        data.setdefault("chat_events", [])
        return data
    except Exception:
        return {"checkins": [], "chat_events": []}

def _save_db(db):
    try:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

if "DB_CACHE" not in st.session_state:
    st.session_state.DB_CACHE = _init_db()

def _get_db(): return st.session_state.DB_CACHE
def _persist_db(): _save_db(st.session_state.DB_CACHE)

def get_or_create_uid():
    if "uid" not in st.session_state:
        st.session_state.uid = f"user_{int(datetime.utcnow().timestamp())}"
    return st.session_state.uid

def save_checkin(uid, phq1, phq2, gad1, gad2, notes=""):
    db = _get_db()
    db["checkins"].append({
        "uid": uid,
        "ts": datetime.utcnow().isoformat(),
        "date": date.today().isoformat(),
        "phq1": int(phq1), "phq2": int(phq2),
        "gad1": int(gad1), "gad2": int(gad2),
        "notes": notes or ""
    })
    _persist_db()

def save_chat_event(uid, role, content):
    db = _get_db()
    db["chat_events"].append({
        "uid": uid,
        "ts": datetime.utcnow().isoformat(),
        "role": role,
        "content": (content or "")[:4000]
    })
    _persist_db()

def compute_metrics():
    db = _get_db()
    uids = set([r.get("uid","") for r in db["checkins"]] + [r.get("uid","") for r in db["chat_events"]])
    uids.discard("")
    users = len(uids) or 1
    sessions = sum(1 for r in db["chat_events"] if r.get("role")=="user")
    cutoff = datetime.utcnow()-timedelta(days=30)
    recent = []
    for r in db["checkins"]:
        try: dt = datetime.fromisoformat(r.get("ts",""))
        except Exception: dt = datetime.utcnow()
        if dt>=cutoff: recent.append(r)
    if recent:
        good=sum(1 for r in recent if (int(r.get("phq1",0))+int(r.get("phq2",0))+int(r.get("gad1",0))+int(r.get("gad2",0)))<=3)
        sat = int(round(100*good/len(recent)))
    else: sat=92
    return users, sessions, sat

def compute_trend_series():
    db = _get_db()
    rows = sorted(db["checkins"], key=lambda r:(r.get("date",""), r.get("ts","")))[-12:]
    labels, prod, mood = [], [], []
    if rows:
        for i,r in enumerate(rows):
            d = r.get("date") or (r.get("ts","")[:10] if r.get("ts") else "")
            labels.append(d or "")
            total = int(r.get("phq1",0))+int(r.get("phq2",0))+int(r.get("gad1",0))+int(r.get("gad2",0))
            mood.append(max(40,95-total*4))
            prod.append(max(35,92-total*3+(2 if (i%3==0) else 0)))
    else:
        base = [(date.today()-timedelta(days=(11-i))).isoformat() for i in range(12)]
        labels = base
        for i in range(12):
            t=i/11
            mood.append(int(70+20*math.sin(t*3.14)+5*t))
            prod.append(int(65+18*math.sin(t*3.14*.9)+7*t))
    return labels, prod, mood

# ---------- CHAT BACKENDS ----------
def chat_ollama(messages):
    try:
        r = requests.post(f"{OLLAMA_HOST}/api/chat",
                          json={"model":OLLAMA_MODEL,"messages":messages,"stream":False}, timeout=120)
        if r.status_code==404:
            prompt=""
            for m in messages:
                role=m.get("role","user")
                tag="SISTEM" if role=="system" else ("KORISNIK" if role=="user" else "ASISTENT")
                prompt+=f"[{tag}]: {m.get('content','')}\n"
            r = requests.post(f"{OLLAMA_HOST}/api/generate",
                              json={"model":OLLAMA_MODEL,"prompt":prompt,"stream":False}, timeout=120)
        r.raise_for_status()
        ct=(r.headers.get("Content-Type") or "").lower()
        if "ndjson" in ct or "\n" in r.text.strip():
            out=""
            for line in r.text.strip().splitlines():
                line=line.strip()
                if not line: continue
                try:
                    data=json.loads(line)
                    out += (data.get("message",{}) or {}).get("content") or data.get("response") or ""
                except Exception:
                    pass
            if out: return out
        data=r.json()
        return (data.get("message",{}) or {}).get("content") or data.get("response") or ""
    except Exception as e:
        return f"[Greška Ollama: {e}]"

def chat_openai(messages):
    if not OPENAI_API_KEY: return "[OPENAI_API_KEY nije postavljen]"
    try:
        r=requests.post("https://api.openai.com/v1/chat/completions",
                        headers={"Authorization":f"Bearer {OPENAI_API_KEY}","Content-Type":"application/json"},
                        json={"model":OPENAI_MODEL,"messages":messages}, timeout=120)
        r.raise_for_status(); j=r.json()
        return j["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[Greška OpenAI: {e}]"

SYSTEM_PROMPT = (
    "Ti si MindMate — AI mentalni wellness asistent na srpskom. "
    "Empatičan, jasan i praktičan (CBT/ACT/mindfulness). "
    "Nema dijagnostike/preskripcije. Rizik → 112 i stručna pomoć. "
    "Daj mikro-korake (5–10min) i traži kratke update-e."
)

# ---------- ROUTER ----------
if "page" not in st.session_state: st.session_state.page="landing"
if "chat_log" not in st.session_state: st.session_state.chat_log=[]
def goto(p): st.session_state.page=p; safe_rerun()

# ---------- NAV ----------
st.markdown("""
<style>
.mm-navwrap{position:sticky;top:0;z-index:9;background:rgba(17,20,28,.55);backdrop-filter:blur(12px);
             border-bottom:1px solid rgba(255,255,255,.06)}
.mm-nav{width:min(1320px,96vw);margin:0 auto;padding:10px 6px;display:flex;align-items:center;justify-content:space-between}
.mm-brand{display:flex;align-items:center;gap:10px;font-weight:900;color:#E8EAEE}
.mm-dot{width:10px;height:10px;border-radius:50%;background:linear-gradient(90deg,#7C5CFF,#4EA3FF);
        box-shadow:0 0 12px rgba(124,92,255,.7)}
.mm-links{display:flex;gap:10px;flex-wrap:wrap}
.mm-links a{text-decoration:none;color:#E8EAEE;font-weight:700;padding:8px 12px;border:1px solid rgba(255,255,255,.08);
            border-radius:12px;background:rgba(255,255,255,.02);transition:transform .18s ease}
.mm-links a:hover{border-color:rgba(255,255,255,.18); transform:translateY(-1px) scale(1.02)}
@media (max-width: 640px){ .mm-links a{padding:6px 10px} }
</style>
<div class="mm-navwrap"><div class="mm-nav">
  <div class="mm-brand"><div class="mm-dot"></div><div>MindMate</div></div>
  <div class="mm-links">
    <a href="?landing">Welcome</a><a href="?home">Početna</a><a href="?chat">Chat</a>
    <a href="?checkin">Check-in</a><a href="?analytics">Analitika</a>
  </div>
</div></div>
""", unsafe_allow_html=True)

qp=st.query_params
if   "landing"  in qp: st.session_state.page="landing"
elif "home"     in qp: st.session_state.page="home"
elif "chat"     in qp: st.session_state.page="chat"
elif "checkin"  in qp: st.session_state.page="checkin"
elif "analytics"in qp: st.session_state.page="analytics"

# ---------- LANDING (planet glow + VSL + KPI + Chart) ----------
LANDING_TEMPLATE = """
<!doctype html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
<style>
:root{ --bg:#0B0D12; --panel:#10131B; --text:#E8EAEE; --mute:#A9B1C1; --ring:rgba(255,255,255,.08);
       --g1:#7C5CFF; --g2:#4EA3FF; }
*{box-sizing:border-box} html,body{margin:0;padding:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;overflow-x:hidden}
.section{width:min(1200px,95vw);margin:0 auto;padding:42px 0}
.badge{display:inline-flex;gap:10px;align-items:center;padding:8px 12px;border-radius:999px;background:rgba(255,255,255,.06);border:1px solid var(--ring);color:#C7CEDA;font-weight:800}
.h1{font-size:clamp(28px,4.2vw,48px);line-height:1.1;margin:8px 0 6px}
.lead{color:var(--mute);font-size:clamp(14px,2vw,18px);margin:0}

/* HERO with planet glow */
.hero{padding-top:10px;text-align:center}
.planet-wrap{position:relative;margin-top:12px}
.glow-orbit{position:absolute;left:50%;top:0;transform:translate(-50%, -38%);width:min(1180px,96vw);height:min(1180px,96vw); pointer-events:none; z-index:0;
  background:
    radial-gradient(60% 40% at 50% 55%, rgba(124,92,255,.50), transparent 60%),
    radial-gradient(56% 38% at 50% 60%, rgba(78,163,255,.40), transparent 65%);
  filter: blur(22px) saturate(1.04); opacity:.85;
}
.planet-card{position:relative;border:1px solid var(--ring); background:linear-gradient(180deg,#0D0F17 0%,#0D0F17 58%,#0B0D12 100%);
  box-shadow:0 30px 80px rgba(0,0,0,.55); border-radius:22px; padding:clamp(12px,2vw,16px); z-index:1; }
.vsl{aspect-ratio:16/9;width:100%;border-radius:14px;overflow:hidden;border:1px solid var(--ring);background:#000}
.vsl iframe{width:100%;height:100%;border:0;display:block}

/* CTA */
.cta{display:flex;gap:12px;flex-wrap:wrap;justify-content:center;margin-top:14px}
.btn{padding:12px 16px;border-radius:14px;border:1px solid var(--ring);text-decoration:none;color:var(--text);font-weight:800;display:inline-flex;gap:10px;align-items:center;transition:transform .18s ease}
.btn:hover{transform:translateY(-1px) scale(1.03)}
.btn-primary{background:linear-gradient(90deg,var(--g1),var(--g2));color:#0B0D12}
.btn-ghost{background:rgba(255,255,255,.06)}
.flower{width:26px;height:26px;border-radius:50%;background:radial-gradient(circle at 30% 30%,var(--g1),var(--g2));box-shadow:0 0 14px rgba(124,92,255,.55)}

/* KPI */
.kpis{display:grid;grid-template-columns:repeat(12,1fr);gap:16px;margin-top:20px}
.kpi{grid-column:span 4;background:rgba(17,20,28,.58);border:1px solid var(--ring);border-radius:16px;padding:22px;text-align:center}
.kpi .num{font-size:clamp(24px,3.2vw,36px);font-weight:900;background:linear-gradient(90deg,var(--g1),var(--g2));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.kpi .label{color:var(--mute);margin-top:6px}

/* Mini Chart (SVG) */
.chart-wrap{background:#0F1219;border:1px solid var(--ring);border-radius:18px;padding:18px;box-shadow:0 14px 36px rgba(0,0,0,.28); margin-top:18px}
.legend{display:flex;gap:14px;align-items:center;color:#C7CEDA;margin-bottom:8px}.dot{width:12px;height:12px;border-radius:50%}
.dot-prod{background:#7C5CFF}.dot-mood{background:#4EA3FF}

/* Features + Comparison */
.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:16px}
.card{grid-column:span 4;background:#10131B;border:1px solid var(--ring);border-radius:16px;padding:18px}
.card h4{margin:.2rem 0}.muted{color:var(--mute)}
.table{border:1px solid var(--ring);border-radius:16px;overflow:hidden}
.table table{width:100%;border-collapse:collapse}
.table th,.table td{padding:12px 14px;border-bottom:1px solid var(--ring)}
.table th{text-align:left;background:rgba(255,255,255,.04)}
.tick{color:#71F0A9;font-weight:900}

/* Sticky CTA */
.sticky{position:fixed;left:0;right:0;bottom:16px;z-index:50;display:flex;justify-content:center;pointer-events:none}
.sticky .inner{pointer-events:auto;width:min(1100px,92vw);background:rgba(20,24,33,.72);backdrop-filter:blur(12px);border:1px solid var(--ring);border-radius:16px;padding:12px 16px;display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center}
@media (max-width:1100px){ .card{grid-column:span 6} }
@media (max-width:768px){
  .sticky .inner{grid-template-columns:1fr}
  .card{grid-column:span 12}
}
</style>
</head>
<body>

<section class="section hero">
  <div class="badge"><span class="flower"></span> Dobrodošao u MindMate</div>
  <h1 class="h1">Diskretna podrška mentalnom zdravlju — odmah, 24/7</h1>
  <p class="lead">VSL preko “planete” sa glow efektom + naš brending (flower strelica).</p>

  <div class="planet-wrap">
    <div class="glow-orbit"></div>
    <div class="planet-card">
      <div class="vsl">
        <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ?rel=0&modestbranding=1"
                title="MindMate VSL" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>
      </div>
      <div class="cta">
        <a class="btn btn-primary" href="?home"><span class="flower"></span> Isprobaj besplatno</a>
        <a class="btn btn-ghost" href="?home">Pogledaj benefite</a>
      </div>
    </div>
  </div>

  <!-- KPI -->
  <div class="kpis" id="kpiBlock">
    <div class="kpi"><div class="num" data-target="__SESS__">0</div><div class="label">Ukupno sesija</div></div>
    <div class="kpi"><div class="num" data-target="__USERS__">0</div><div class="label">Aktivnih korisnika</div></div>
    <div class="kpi"><div class="num" data-target="__SAT__">0</div><div class="label">Zadovoljstvo (%)</div></div>
  </div>
</section>

<!-- CHART -->
<section class="section">
  <div class="chart-wrap">
    <div style="font-weight:900;margin:0 0 10px 0">Produktivnost & Raspoloženje (poslednje sesije)</div>
    <div class="legend"><div class="dot dot-prod"></div><div>Produktivnost</div><div class="dot dot-mood" style="margin-left:12px"></div><div>Raspoloženje</div></div>
    <svg id="mmChart" viewBox="0 0 1100 360" width="100%" height="360" preserveAspectRatio="xMidYMid meet">
      <defs><linearGradient id="gProd" x1="0" x2="1" y1="0" y2="0"><stop offset="0%" stop-color="#7C5CFF"/><stop offset="100%" stop-color="#4EA3FF"/></linearGradient>
      <linearGradient id="gMood" x1="0" x2="1" y1="0" y2="0"><stop offset="0%" stop-color="#4EA3FF"/><stop offset="100%" stop-color="#7C5CFF"/></linearGradient></defs>
      <g id="grid"></g>
      <path id="prodPath" fill="none" stroke="url(#gProd)" stroke-width="3" stroke-linecap="round"/>
      <path id="moodPath" fill="none" stroke="url(#gMood)" stroke-width="3" stroke-linecap="round"/>
      <g id="xlabels"></g>
    </svg>
  </div>
</section>

<!-- FEATURES -->
<section class="section">
  <h2 class="h1" style="font-size:clamp(22px,3.4vw,32px)">MindMate Pro Features</h2>
  <div class="grid">
    <div class="card"><h4>Automated Nudges</h4><div class="muted">Pametni podsetnici da ne gubiš ritam (Check-in/mini-navike).</div></div>
    <div class="card"><h4>Real-time Patterns</h4><div class="muted">Brzo vidi kada opada fokus ili raspoloženje.</div></div>
    <div class="card"><h4>One-click Reflection</h4><div class="muted">Spajaj beleške i dobij predloge mikro-koraka.</div></div>
    <div class="card"><h4>Privacy-first</h4><div class="muted">Sve lokalno u MVP-u (Ollama). Istoriju brišeš jednim klikom.</div></div>
    <div class="card"><h4>CBT/ACT/Mindfulness</h4><div class="muted">Empatičan ton i validirane tehnike bez dijagnostike.</div></div>
    <div class="card"><h4>Trends & Goals</h4><div class="muted">Laki grafovi + ciljevi koji su dostižni.</div></div>
  </div>
</section>

<!-- COMPARISON -->
<section class="section">
  <div class="table">
    <table>
      <thead><tr><th> </th><th>MindMate</th><th>Klasične navike</th></tr></thead>
      <tbody>
        <tr><td>Check-in za 30s</td><td class="tick">✔</td><td>—</td></tr>
        <tr><td>Predlog mikro-koraka</td><td class="tick">✔</td><td>—</td></tr>
        <tr><td>Privatnost (lokalno)</td><td class="tick">✔</td><td>?</td></tr>
        <tr><td>Trendovi & ciljevi</td><td class="tick">✔</td><td>—</td></tr>
      </tbody>
    </table>
  </div>
</section>

<!-- STICKY CTA -->
<div class="sticky">
  <div class="inner">
    <div class="muted">Tvoj bolji dan počinje sada — check-in, mikro-navike, jasni trendovi.</div>
    <div style="display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap">
      <a class="btn btn-primary" href="?home"><span class="flower"></span> Start</a>
      <a class="btn btn-ghost" href="?home">Pogledaj benefite</a>
    </div>
  </div>
</div>

<script>
// KPI count-up
function countUp(el){const t=parseInt(el.getAttribute('data-target'))||0,d=1400,s=performance.now();
  function tick(now){const p=Math.min((now-s)/d,1);el.textContent=Math.floor(t*(.1+.9*p)).toLocaleString(); if(p<1) requestAnimationFrame(tick)}
  requestAnimationFrame(tick)}
const kio=new IntersectionObserver(e=>{e.forEach(x=>{if(x.isIntersecting){x.target.querySelectorAll('.num').forEach(countUp);kio.unobserve(x.target)}})},{threshold:.35});
document.querySelectorAll('#kpiBlock').forEach(el=>kio.observe(el));

// Mini chart
const labels=__X_LABELS__, prod=__P_SERIES__, mood=__M_SERIES__; const W=1100,H=360,P=48,ymin=0,ymax=100;
const grid=document.getElementById('grid'), xg=document.getElementById('xlabels'), svg=document.getElementById('mmChart');
for(let i=0;i<=5;i++){const y=P+(H-2*P)*(i/5), l=document.createElementNS("http://www.w3.org/2000/svg","line");
  l.setAttribute("x1",P);l.setAttribute("x2",W-P);l.setAttribute("y1",y);l.setAttribute("y2",y);l.setAttribute("stroke","rgba(255,255,255,.08)");grid.appendChild(l)}
labels.forEach((lab,i)=>{const x=P+(W-2*P)*(i/(labels.length-1||1)), t=document.createElementNS("http://www.w3.org/2000/svg","text");
  t.setAttribute("x",x);t.setAttribute("y",H-12);t.setAttribute("fill","#9AA3B2");t.setAttribute("font-size","12");t.setAttribute("text-anchor","middle");
  t.textContent=lab.slice(5).replace("-","/");xg.appendChild(t)});
function path(vals){const pts=vals.map((v,i)=>[P+(W-2*P)*(i/(vals.length-1||1)), P+(H-2*P)*(1-(v-ymin)/(ymax-ymin))]);
  if(!pts.length)return ""; let d=`M ${pts[0][0]} ${pts[0][1]}`; for(let i=1;i<pts.length;i++){d+=` L ${pts[i][0]} ${pts[i][1]}`} return d}
const prodPath=document.getElementById('prodPath'), moodPath=document.getElementById('moodPath');
prodPath.setAttribute("d",path(prod)); moodPath.setAttribute("d",path(mood));
function strokeAnim(p,d=1600){const L=p.getTotalLength();p.style.strokeDasharray=L;p.style.strokeDashoffset=L;p.getBoundingClientRect();p.style.transition=`stroke-dashoffset ${d}ms ease`;p.style.strokeDashoffset="0"}
const cio=new IntersectionObserver(e=>{e.forEach(x=>{if(x.isIntersecting){strokeAnim(prodPath,1400);setTimeout(()=>strokeAnim(moodPath,1600),200);cio.unobserve(svg)}})},{threshold:.3});
cio.observe(svg);
</script>

</body></html>
"""

def render_landing():
    users, sessions, sat = compute_metrics()
    labels, prod, mood = compute_trend_series()
    html = (LANDING_TEMPLATE
            .replace("__SESS__", str(max(sessions,0)))
            .replace("__USERS__", str(users or 1))
            .replace("__SAT__", str(max(min(sat,100),0)))
            .replace("__X_LABELS__", json.dumps(labels))
            .replace("__P_SERIES__", json.dumps(prod))
            .replace("__M_SERIES__", json.dumps(mood))
           )
    st_html(html, height=3000, width=1280, scrolling=True)

# ---------- HOME / CHAT / CHECKIN / ANALYTICS ----------
def render_home():
    st.markdown("### Tvoja kontrolna tabla")
    c1,c2,c3=st.columns(3)
    with c1:
        st.write("**Chat** — AI na srpskom, praktičan i podržavajući.")
        if st.button("Otvori chat →", use_container_width=True): goto("chat")
    with c2:
        st.write("**Check-in** — 2 pitanja + mikro-ciljevi i streak.")
        if st.button("Idi na check-in →", use_container_width=True): goto("checkin")
    with c3:
        st.write("**Analitika** — trendovi i talasne linije napretka.")
        if st.button("Vidi trendove →", use_container_width=True): goto("analytics")

def chat_reply(sys, log):
    msgs=[{"role":"system","content":sys}] + [{"role":r,"content":m} for r,m in log]
    return chat_openai(msgs) if CHAT_PROVIDER=="openai" else chat_ollama(msgs)

def render_chat():
    st.subheader("💬 Chat")
    st.caption(f"Backend: {CHAT_PROVIDER.upper()} | Model: {OLLAMA_MODEL if CHAT_PROVIDER=='ollama' else OPENAI_MODEL}")
    uid=get_or_create_uid()
    for role,msg in st.session_state.chat_log:
        with st.chat_message(role): st.markdown(msg)
    user=st.chat_input("Upiši poruku…")
    if user:
        st.session_state.chat_log.append(("user",user)); save_chat_event(uid,"user",user)
        with st.chat_message("assistant"):
            reply=chat_reply(SYSTEM_PROMPT, st.session_state.chat_log)
            st.markdown(reply); st.session_state.chat_log.append(("assistant",reply)); save_chat_event(uid,"assistant",reply)

def render_checkin():
    st.subheader("🗓️ Daily Check-in"); st.caption("PHQ-2/GAD-2 inspirisano, nije dijagnoza.")
    c1,c2=st.columns(2)
    with c1:
        phq1=st.slider("Gubitak interesovanja / zadovoljstva",0,3,0)
        phq2=st.slider("Potištenost / tuga / beznađe",0,3,0)
    with c2:
        gad1=st.slider("Nervoza / anksioznost / napetost",0,3,0)
        gad2=st.slider("Teško prestajem da brinem",0,3,0)
    notes=st.text_area("Napomene (opciono)")
    if st.button("Sačuvaj današnji check-in", use_container_width=True):
        save_checkin(get_or_create_uid(), phq1,phq2,gad1,gad2, notes); st.success("✅ Zabeleženo!")

def render_analytics():
    st.subheader("📈 Analitika")
    rows=sorted(_get_db()["checkins"], key=lambda r:r.get("date",""))
    if not rows:
        st.info("Još nema podataka. Uradi prvi check-in.")
        return

    df = pd.DataFrame(rows)
    df["total"] = df[["phq1","phq2","gad1","gad2"]].sum(axis=1)
    df["date"]  = pd.to_datetime(df["date"], errors="coerce")
    df.sort_values("date", inplace=True)

    fig1 = px.line(df, x="date", y="total", markers=True, title="Ukupan skor (PHQ2+GAD2) kroz vreme")
    fig1.update_layout(paper_bgcolor="#0B0D12", plot_bgcolor="#11141C", font_color="#E8EAEE",
                       xaxis_title="Datum", yaxis_title="Skor (0–12)",
                       margin=dict(l=10,r=10,t=50,b=10))
    st.plotly_chart(fig1, use_container_width=True)

    mood = (95 - df["total"]*4).clip(40, 100)
    prod = (92 - df["total"]*3 + (df.index%3==0)*2).clip(35, 100)
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=df["date"], y=prod, mode="lines+markers", name="Produktivnost"))
    fig2.add_trace(go.Scatter(x=df["date"], y=mood, mode="lines+markers", name="Raspoloženje"))
    fig2.update_layout(title="Raspoloženje & Produktivnost",
                       paper_bgcolor="#0B0D12", plot_bgcolor="#11141C", font_color="#E8EAEE",
                       xaxis_title="Datum", yaxis_title="Skor (0–100)",
                       margin=dict(l=10,r=10,t=50,b=10))
    st.plotly_chart(fig2, use_container_width=True)

    try:
        hh = pd.to_datetime(df["ts"], errors="coerce").dt.hour.dropna()
        if not hh.empty:
            fig3 = px.histogram(hh, nbins=24, title="Vreme dana kada radiš check-in")
            fig3.update_layout(paper_bgcolor="#0B0D12", plot_bgcolor="#11141C", font_color="#E8EAEE",
                               xaxis_title="Sat u danu", yaxis_title="Broj check-in-a",
                               margin=dict(l=10,r=10,t=50,b=10))
            st.plotly_chart(fig3, use_container_width=True)
    except Exception:
        pass

# ---------- ROUTE ----------
page=st.session_state.page
if page=="landing": render_landing()
elif page=="home": render_home()
elif page=="chat": render_chat()
elif page=="checkin": render_checkin()
elif page=="analytics": render_analytics()

st.markdown("<div style='text-align:center;color:#9AA3B2;margin-top:18px'>© 2025 MindMate. Nije medicinski alat. Za hitne slučajeve — 112.</div>", unsafe_allow_html=True)
