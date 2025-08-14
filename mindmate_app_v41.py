# app.py — MindMate landing + BIG FAQ + PRICING (Free/Pro) + Početna/Chat/Check-in/Analitika
import os, json, requests, math
import streamlit as st
from datetime import datetime, date, timedelta
from streamlit.components.v1 import html as st_html
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

APP_TITLE = "MindMate"
DB_PATH   = os.environ.get("MINDMATE_DB", "mindmate_db.json")

CHAT_PROVIDER = os.environ.get("CHAT_PROVIDER", "ollama").lower().strip()
OLLAMA_HOST   = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL  = os.environ.get("OLLAMA_MODEL", "llama3.1")
OPENAI_API_KEY= os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL  = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

def safe_rerun():
    if hasattr(st, "rerun"): st.rerun()
    else: st.experimental_rerun()

st.set_page_config(page_title=APP_TITLE, page_icon="🧠", layout="wide")

# ---------- Global okvir ----------
st.markdown("""
<style>
:root{
  --bg:#0B0D12; --panel:#10141B; --ink:#E8EAEE; --mut:#9AA3B2;
  --g1:#7C5CFF; --g2:#4EA3FF; --ring:rgba(255,255,255,.10);
}
html,body{background:var(--bg); color:var(--ink)}
.main .block-container{
  padding-top:.6rem!important; padding-left:2rem!important; padding-right:2rem!important;
  max-width:1280px!important; margin-inline:auto!important;
}
@media (max-width:900px){
  .main .block-container{padding-left:1.2rem!important; padding-right:1.2rem!important}
}
.element-container > div:has(> iframe){display:flex; justify-content:center;}
.stButton>button[kind="primary"]{
  background:linear-gradient(90deg,var(--g1),var(--g2))!important;color:#0B0D12!important;
  font-weight:800!important;border:none!important
}
</style>
""", unsafe_allow_html=True)

# ---------- “Baza” ----------
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
        try: dt = datetime.fromisoformat(r.get("ts","").split("+")[0])
        except Exception: dt = datetime.utcnow()
        if dt>=cutoff: recent.append(r)
    if recent:
        good=sum(1 for r in recent if (int(r.get("phq1",0))+int(r.get("phq2",0))+int(r.get("gad1",0))+int(r.get("gad2",0)))<=3)
        sat = int(round(100*good/len(recent)))
    else: sat=92
    retention = min(99, 60 + len(recent)//5)
    return users, sessions, sat, retention

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

# ---------- Chat backends ----------
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
        try:
            data=r.json()
            return (data.get("message",{}) or {}).get("content") or data.get("response") or ""
        except Exception:
            return r.text
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

# ---------- Router ----------
if "page" not in st.session_state: st.session_state.page="landing"
if "chat_log" not in st.session_state: st.session_state.chat_log=[]
def goto(p): st.session_state.page=p; safe_rerun()

# ---------- NAV (Apple-style glass, clean) ----------
st.markdown("""
<style>
/* Apple-style MindMate Navbar */
:root{
  --bg:#0B0D12; --panel:rgba(16,20,27,.72); --ink:#E8EAEE; --mut:#A2ACBA; --ring:rgba(255,255,255,.10);
  --g1:#7C5CFF; --g2:#4EA3FF; --max:1180px;
}
.nav-wrap{position:sticky;top:0;z-index:1000;backdrop-filter:saturate(140%) blur(14px);-webkit-backdrop-filter:saturate(140%) blur(14px);}
.nav{max-width:var(--max);margin:0 auto;padding:10px 14px;display:flex;align-items:center;gap:12px;position:relative}
.nav::after{content:"";position:absolute;left:0;right:0;bottom:0;height:1px;background:linear-gradient(90deg,transparent,var(--ring),transparent)}
.bar-bg{position:absolute;inset:0;background:linear-gradient(180deg,color-mix(in oklab,var(--panel)90%,transparent),color-mix(in oklab,#0B0D12 95%,transparent));border-bottom:1px solid var(--ring);transition:box-shadow .24s ease,background .24s ease}
.nav.sticky .bar-bg{box-shadow:0 10px 45px rgba(0,0,0,.35)}
.brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:var(--ink);font-weight:900;letter-spacing:.2px}
.dot{width:10px;height:10px;border-radius:50%;background:linear-gradient(90deg,var(--g1),var(--g2));box-shadow:0 0 18px color-mix(in oklab,var(--g1)60%,transparent)}
.spacer{flex:1}
.links{display:flex;align-items:center;gap:6px;position:relative}
.link{--padx:.9rem;position:relative;display:inline-flex;align-items:center;justify-content:center;height:40px;padding:0 var(--padx);border-radius:12px;text-decoration:none;font-weight:800;color:var(--mut)}
.link:hover{color:var(--ink)}
.link:focus-visible{outline:2px solid color-mix(in oklab, var(--g2) 60%, white); outline-offset:2px; border-radius:14px}
.indicator{position:absolute;bottom:6px;height:2px;border-radius:2px;background:linear-gradient(90deg,var(--g1),var(--g2));width:0;transform:translateX(0);transition:transform .24s cubic-bezier(.2,.8,.2,1),width .24s cubic-bezier(.2,.8,.2,1)}
.cta{display:inline-flex;align-items:center;justify-content:center;height:40px;padding:0 16px;border-radius:999px;font-weight:900;text-decoration:none;color:#0B0D12;background:linear-gradient(90deg,var(--g1),var(--g2));border:1px solid var(--ring);box-shadow:inset 0 1px 0 rgba(255,255,255,.12),0 10px 26px rgba(0,0,0,.35)}
.cta:hover{filter:saturate(1.05)}
/* Mobile */
.burger{display:none;position:relative;width:38px;height:38px;border:0;background:transparent;border-radius:12px}
.burger span{position:absolute;left:10px;right:10px;height:2px;background:var(--ink);border-radius:999px;transition:transform .24s,opacity .24s}
.burger span:nth-child(1){top:11px}.burger span:nth-child(2){top:18px}.burger span:nth-child(3){top:25px}
@media(max-width:920px){.links{display:none}.burger{display:block}}
/* Mobile sheet */
.sheet{position:fixed;inset:60px 10px auto;top:12px;background:rgba(16,20,27,.96);border:1px solid var(--ring);border-radius:16px;padding:10px;display:none;flex-direction:column;gap:6px}
.sheet .link{height:46px;border-radius:10px;color:var(--ink);background:rgba(255,255,255,.04)}
.sheet .cta{height:46px}
</style>
<div class="nav-wrap">
  <div class="nav" id="nav">
    <div class="bar-bg"></div>
    <a class="brand" href="?landing" aria-label="MindMate">
      <span class="dot" aria-hidden="true"></span>
      <span>MindMate</span>
    </a>
    <button class="burger" id="burger" aria-label="Meni" aria-expanded="false" aria-controls="sheet">
      <span></span><span></span><span></span>
    </button>
    <div class="spacer"></div>
    <nav class="links" id="links" aria-label="Glavna navigacija">
      <a class="link" data-page="landing" href="?landing">Welcome</a>
      <a class="link" data-page="home" href="?home">Početna</a>
      <a class="link" data-page="chat" href="?chat">Chat</a>
      <a class="link" data-page="checkin" href="?checkin">Check-in</a>
      <a class="link" data-page="analytics" href="?analytics">Analitika</a>
      <span class="indicator" id="indicator" aria-hidden="true"></span>
    </nav>
    <a class="cta" href="?home">Kreni odmah</a>
  </div>
</div>
<div class="sheet" id="sheet" role="dialog" aria-modal="true" aria-label="Brzi meni">
  <a class="link" href="?landing">Welcome</a>
  <a class="link" href="?home">Početna</a>
  <a class="link" href="?chat">Chat</a>
  <a class="link" href="?checkin">Check-in</a>
  <a class="link" href="?analytics">Analitika</a>
  <a class="cta" href="?home">Kreni odmah</a>
</div>
<script>
// Active underline logic
const links=[...document.querySelectorAll('.links .link')];
const indicator=document.getElementById('indicator');
function setActive(el){
  if(!el) return;
  const r=el.getBoundingClientRect();
  const wrap=el.parentElement.getBoundingClientRect();
  indicator.style.width=r.width+'px';
  indicator.style.transform=`translateX(${r.left-wrap.left}px)`;
}
const qs=new URLSearchParams(location.search);
const key=['landing','home','chat','checkin','analytics'].find(k=>qs.has(k))||'landing';
setActive(links.find(a=>a.dataset.page===key)||links[0]);
links.forEach(a=>a.addEventListener('mouseenter',()=>setActive(a)));
document.querySelector('.links').addEventListener('mouseleave',()=>setActive(links.find(a=>a.dataset.page===key)||links[0]));

// Sticky shadow on scroll
const nav=document.getElementById('nav');
function onScroll(){ nav.classList.toggle('sticky', window.scrollY>6); }
onScroll(); addEventListener('scroll', onScroll, {passive:true});

// Mobile sheet
const burger=document.getElementById('burger');
const sheet=document.getElementById('sheet');
function setSheet(open){
  sheet.style.display=open?'flex':'none';
  burger.setAttribute('aria-expanded', String(open));
  const [a,b,c]=burger.querySelectorAll('span');
  if(open){ a.style.transform='translateY(7px) rotate(45deg)'; b.style.opacity='0'; c.style.transform='translateY(-7px) rotate(-45deg)'; }
  else{ a.style.transform=''; b.style.opacity=''; c.style.transform=''; }
}
burger.addEventListener('click', ()=> setSheet(sheet.style.display!=='flex'));
addEventListener('keydown', e=>{ if(e.key==='Escape') setSheet(false); });
</script>
""", unsafe_allow_html=True)

# query param routing (ostaje isto)
qp=st.query_params
if   "landing"  in qp: st.session_state.page="landing"
elif "home"     in qp: st.session_state.page="home"
elif "chat"     in qp: st.session_state.page="chat"
elif "checkin"  in qp: st.session_state.page="checkin"
elif "analytics"in qp: st.session_state.page="analytics"

# ---------- LANDING (sa PRICING ispod FAQ) ----------
LANDING = """
<!DOCTYPE html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
<style>
:root{
  --bg:#0B0D12; --ink:#E8EAEE; --mut:#9AA3B2; --ring:rgba(255,255,255,.10);
  --g1:#7C5CFF; --g2:#4EA3FF; --MAX:1180px;
  --s-xl:64px; --s-lg:48px; --s-md:32px; --s-sm:20px;
}
*{box-sizing:border-box} html,body{margin:0;padding:0;background:var(--bg);color:var(--ink);font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;overflow-x:hidden}
.container{width:min(var(--MAX),92vw);margin:0 auto}
.section{padding-block:var(--s-lg)} .section.tight{padding-block:var(--s-md)}
.h2{font-size:clamp(22px,2.6vw,30px);margin:0 0 12px 0}
.grid-12{display:grid;grid-template-columns:repeat(12,1fr);gap:18px}
.card{background:#0F1219;border:1px solid var(--ring);border-radius:16px;padding:18px;transition:transform .2s ease, box-shadow .2s ease}
.card:hover{transform:translateY(-2px) scale(1.03); box-shadow:0 14px 48px rgba(0,0,0,.35)}
.btn{display:inline-block;padding:12px 16px;border-radius:12px;font-weight:800;border:1px solid var(--ring);text-decoration:none;transition:transform .2s ease}
.btn:hover{transform:translateY(-1px) scale(1.03)}
.btn-primary{background:linear-gradient(90deg,var(--g1),var(--g2));color:#0B0D12}
.btn-ghost{background:rgba(255,255,255,.06);color:#E8EAEE}

/* Hero */
.hero{padding-top:var(--s-lg);padding-bottom:var(--s-lg)}
.hero-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:28px;align-items:center}
.h-eyebrow{display:inline-block;padding:7px 11px;border-radius:999px;border:1px solid var(--ring);font-size:12px;color:#C7CEDA;background:rgba(255,255,255,.05);margin-bottom:8px}
.h-title{font-size:clamp(28px,4.6vw,56px);line-height:1.06;margin:0 0 8px}
.h-sub{color:var(--mut);margin:0 0 10px}
.cta{display:flex;gap:10px;flex-wrap:wrap}

.mira{display:flex;justify-content:center}
#flower{width:min(380px,68vw);filter:drop-shadow(0 14px 42px rgba(124,92,255,.35))}
#flower .p{transform-origin:50% 50%;animation:sway 6.6s ease-in-out infinite}
#flower .c{animation:pulse 6s ease-in-out infinite}
@keyframes sway{ 0%{transform:rotate(0)} 50%{transform:rotate(2.2deg)} 100%{transform:rotate(0)}}
@keyframes pulse{ 0%,100%{opacity:.85} 50%{opacity:1}}

/* VSL + orb */
.vsl-area{position:relative}
.orb-wrap{position:relative;height:90px}
.orb{
  position:absolute; inset:-180px 0 0 0; margin:auto; z-index:0;
  width:min(980px,90vw); height:min(980px,90vw);
  background:
    radial-gradient(60% 55% at 50% 40%, rgba(124,92,255,.55), transparent 62%),
    radial-gradient(58% 52% at 50% 45%, rgba(78,163,255,.50), transparent 66%),
    radial-gradient(46% 40% at 50% 52%, rgba(154,214,255,.22), transparent 70%);
  filter: blur(28px) saturate(1.05); opacity:.9; animation:orbBreath 12s ease-in-out infinite;
}
@keyframes orbBreath{0%,100%{transform:scale(1)} 50%{transform:scale(1.04)}}
.vsl{position:relative;z-index:1;max-width:980px;margin:0 auto;border-radius:16px;border:1px solid var(--ring);padding:10px;background:rgba(255,255,255,.05);box-shadow:0 28px 90px rgba(0,0,0,.65)}
.vsl iframe{width:100%;aspect-ratio:16/9;height:auto;min-height:240px;border:0;border-radius:10px}

/* Trusted by */
.trusted{display:flex;flex-direction:column;gap:10px;align-items:center;margin-top:14px}
.logos{display:flex;gap:16px;flex-wrap:wrap;justify-content:center}
.logo{width:110px;height:42px;border-radius:12px;border:1px solid var(--ring);background:rgba(255,255,255,.04);display:flex;align-items:center;justify-content:center;color:#C7CEDA;font-weight:800;letter-spacing:.4px;transition:transform .2s}
.logo:hover{transform:translateY(-2px)}

/* 3-up features */
.feat .card{grid-column:span 4}
@media (max-width:900px){ .hero-grid{grid-template-columns:1fr} .feat .card{grid-column:span 12} }

/* Compare */
.compare{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media (max-width:900px){ .compare{grid-template-columns:1fr} }

/* Chart */
.chart-wrap{background:#0F1219;border:1px solid var(--ring);border-radius:16px;padding:18px}
.legend{display:flex;gap:12px;align-items:center;color:#C7CEDA;margin-bottom:6px}.dot{width:12px;height:12px;border-radius:50%}
.dot-prod{background:#7C5CFF}.dot-mood{background:#4EA3FF}

/* KPI */
.kpis .card{grid-column:span 3;text-align:center}
.knum{font-size:clamp(22px,3vw,30px);font-weight:900;background:linear-gradient(90deg,var(--g1),var(--g2));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.kcap{color:var(--mut)}

/* Integrations */
.int .card{grid-column:span 3;text-align:center;color:#C7CEDA}
@media (max-width:900px){ .int .card{grid-column:span 6} }

/* Testimonials */
.twrap{border:1px solid var(--ring);border-radius:16px;padding:16px;background:#0F1219;position:relative;overflow:hidden}
.trail{display:flex;gap:16px;transition:transform .45s ease}
.tcard{min-width:calc(33.33% - 10.6px);background:rgba(255,255,255,.04);border:1px solid var(--ring);border-radius:12px;padding:14px}
.tnav{position:absolute;top:50%;left:8px;right:8px;display:flex;justify-content:space-between;transform:translateY(-50%)}
.tbtn{padding:7px 10px;border-radius:12px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);cursor:pointer;transition:transform .18s}
.tbtn:hover{transform:scale(1.06)}

/* ===== BIG FAQ ===== */
.faq-zone{position:relative;overflow:hidden;border-radius:20px;border:1px solid var(--ring);background:linear-gradient(180deg,#0F1219, #0E131A 55%, #0C1016)}
.faq-clouds:before, .faq-clouds:after{
  content:""; position:absolute; inset:auto -20% -40% -20%; height:240px;
  background:
    radial-gradient(240px 120px at 20% 60%, rgba(255,255,255,.06), transparent 65%),
    radial-gradient(200px 100px at 60% 40%, rgba(255,255,255,.05), transparent 60%),
    radial-gradient(220px 110px at 85% 70%, rgba(255,255,255,.04), transparent 65%);
  filter:blur(12px); opacity:.7; animation:cloudFloat 26s linear infinite;
}
.faq-clouds:after{ inset:auto -25% -45% -25%; animation-duration:32s; opacity:.55 }
@keyframes cloudFloat{0%{transform:translateX(-6%)} 50%{transform:translateX(6%)} 100%{transform:translateX(-6%)}}

.faq-header{text-align:center; padding:28px 16px 10px}
.badge{display:inline-flex;gap:6px;align-items:center;color:#C7CEDA;font-size:13px;padding:7px 12px;border:1px solid var(--ring);border-radius:999px;background:rgba(255,255,255,.05)}
.faq-title{font-size:clamp(26px,4.2vw,44px);margin:8px 0 6px 0}
.faq-sub{color:#A7B0BE;max-width:860px;margin:0 auto 18px}

.faq{max-width:920px;margin:0 auto 26px;background:transparent;border:0}
.faq-item{border:1px solid var(--ring);border-radius:14px;background:#0F1219;margin:12px 0;overflow:hidden;box-shadow:0 10px 26px rgba(0,0,0,.25); transition:transform .18s ease, box-shadow .18s ease}
.faq-item:hover{transform:translateY(-1px); box-shadow:0 14px 36px rgba(0,0,0,.33)}
.faq-q{width:100%;text-align:left;background:none;border:none;color:#E8EAEE;font-weight:800;padding:18px 18px;cursor:pointer; display:flex; align-items:center; justify-content:space-between}
.faq-q .txt{pointer-events:none}
.chev{width:22px;height:22px;border-radius:6px;border:1px solid var(--ring);display:grid;place-items:center;transition:transform .28s cubic-bezier(.2,.8,.2,1)}
.chev svg{width:12px;height:12px}
.faq-a{max-height:0;overflow:hidden;color:#C7CEDA;padding:0 18px;transition:max-height .42s cubic-bezier(.2,.8,.2,1), padding .42s cubic-bezier(.2,.8,.2,1)}
.faq-a.open{padding:12px 18px 18px}
.contact-mini{display:flex;align-items:center;justify-content:center;gap:10px;color:#C7CEDA;padding:8px 0 18px}

/* ===== PRICING ===== */
.pricing .wrap{border:1px solid var(--ring);border-radius:20px;padding:24px;background:#0F1219}
.price-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:stretch}
.price-card{background:rgba(17,20,28,.9);border:1px solid var(--ring);border-radius:18px;padding:22px;box-shadow:0 16px 44px rgba(0,0,0,.35); transition:transform .18s, box-shadow .18s}
.price-card:hover{transform:translateY(-2px) scale(1.02); box-shadow:0 22px 60px rgba(0,0,0,.45)}
.price-title{font-weight:900;margin:0 0 6px 0}
.price-row{display:flex;align-items:baseline;gap:8px}
.price-num{font-size:clamp(28px,4vw,36px);font-weight:900}
.price-unit{color:#9AA3B2;font-weight:700}
.hr{height:1px;background:rgba(255,255,255,.08);margin:12px 0}
.li{display:flex;gap:10px;align-items:flex-start;color:#C7CEDA;margin:8px 0}
.bullet{width:8px;height:8px;border-radius:50%;background:linear-gradient(90deg,var(--g1),var(--g2));margin-top:8px}
.price-btn{margin-top:14px;display:inline-block;padding:12px 16px;border-radius:12px;font-weight:800;text-decoration:none;border:1px solid var(--ring)}
.price-btn.primary{background:linear-gradient(90deg,var(--g1),var(--g2));color:#0B0D12}
.price-btn.ghost{background:rgba(255,255,255,.06);color:#E8EAEE}
@media (max-width:900px){ .price-grid{grid-template-columns:1fr} }

/* Reveal */
.reveal{opacity:0;transform:translateY(20px);transition:opacity 1.2s ease, transform 1.2s ease}
.reveal.v{opacity:1;transform:translateY(0)}

.footer{color:#9AA3B2;text-align:center;padding:16px 0 22px}
@media (max-width:900px){ .hero-grid{grid-template-columns:1fr} }
</style>
</head>
<body>

<!-- HERO -->
<section class="section hero">
  <div class="container hero-grid reveal">
    <div>
      <div class="h-eyebrow">MindMate • Mentalni wellness</div>
      <h1 class="h-title">Preusmeri 80% briga u konkretne korake — za 5 minuta dnevno.</h1>
      <p class="h-sub">Kratki check-in, mikro-navike i empatičan razgovor. Jasni trendovi, tvoj ritam.</p>
      <div class="cta">
        <a class="btn btn-primary" href="?home">Kreni odmah</a>
        <a class="btn btn-ghost" href="?home">Pogledaj kako radi</a>
      </div>
    </div>
    <div class="mira">
      <svg id="flower" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" aria-label="Flower Mira">
        <defs>
          <linearGradient id="pG" x1="0" x2="1" y1="0" y2="1"><stop offset="0%" stop-color="#7C5CFF"/><stop offset="100%" stop-color="#4EA3FF"/></linearGradient>
          <radialGradient id="cG" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#FFF7"/><stop offset="100%" stop-color="#7C5CFF"/></radialGradient>
        </defs>
        <g class="p"><path d="M100,20 C85,45 85,75 100,95 C115,75 115,45 100,20 Z" fill="url(#pG)"/>
           <path d="M55,40 C40,70 52,95 95,105 C78,84 72,60 55,40 Z" fill="url(#pG)" opacity=".75"/>
           <path d="M145,40 C160,70 148,95 105,105 C122,84 128,60 145,40 Z" fill="url(#pG)" opacity=".75"/></g>
        <circle class="c" cx="100" cy="110" r="12" fill="url(#cG)"/>
        <path d="M88 128 Q100 136 112 128" stroke="#E8EAEE" stroke-width="3" fill="none" stroke-linecap="round" opacity=".85"/>
        <circle cx="88" cy="122" r="2.8" fill="#E8EAEE" opacity=".9"/>
        <circle cx="112" cy="122" r="2.8" fill="#E8EAEE" opacity=".9"/>
      </svg>
    </div>
  </div>
</section>

<!-- VSL + planeta + Trusted by -->
<section class="section tight vsl-area">
  <div class="container reveal">
    <div class="orb-wrap"><div class="orb"></div></div>
    <div class="vsl"><iframe src="https://www.youtube.com/embed/1qK0c9J_h10?rel=0&modestbranding=1" title="MindMate VSL" allowfullscreen></iframe></div>
    <div class="trusted">
      <div style="opacity:.9">Trusted by people from:</div>
      <div class="logos">
        <div class="logo">Health+</div><div class="logo">Calmify</div><div class="logo">WellLabs</div>
        <div class="logo">FocusHub</div><div class="logo">MindBank</div>
      </div>
    </div>
  </div>
</section>

<!-- Benefiti -->
<section class="section tight">
  <div class="container">
    <h2 class="h2">Zašto početi danas</h2>
    <div class="grid-12 feat reveal">
      <div class="card" style="grid-column:span 4"><b>2 pitanja dnevno</b><br><span style="color:#9AA3B2">Brz check-in bez frke; gradi ritam.</span></div>
      <div class="card" style="grid-column:span 4"><b>Mikro-navike (5–10 min)</b><br><span style="color:#9AA3B2">Male akcije → vidljiv napredak.</span></div>
      <div class="card" style="grid-column:span 4"><b>Grafovi i obrasci</b><br><span style="color:#9AA3B2">Jasno vidiš raspoloženje i fokus.</span></div>
    </div>
  </div>
</section>

<!-- Poređenje -->
<section class="section tight">
  <div class="container reveal">
    <h2 class="h2">Bez plana vs. sa MindMate</h2>
    <div class="compare">
      <div class="card"><b>Bez plana</b><ul style="color:#9AA3B2;margin:.5rem 0 0 1rem">
        <li>Nasumične navike, bez praćenja</li><li>Preplavljenost</li><li>Nema jasnih trendova</li></ul></div>
      <div class="card"><b>Sa MindMate</b><ul style="color:#9AA3B2;margin:.5rem 0 0 1rem">
        <li>2 pitanja + mikro-koraci</li><li>Empatičan razgovor u tvom tonu</li><li>Grafovi napretka</li></ul></div>
    </div>
  </div>
</section>

<!-- Mini demo graf -->
<section class="section tight">
  <div class="container reveal">
    <div class="chart-wrap">
      <div style="font-weight:900;margin-bottom:6px">Produktivnost & Raspoloženje (poslednje sesije)</div>
      <div class="legend"><div class="dot dot-prod"></div><div>Produktivnost</div><div class="dot dot-mood" style="margin-left:12px"></div><div>Raspoloženje</div></div>
      <svg id="mmChart" viewBox="0 0 1100 320" width="100%" height="320" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="gProd" x1="0" x2="1" y1="0" y2="0"><stop offset="0%" stop-color="#7C5CFF"/><stop offset="100%" stop-color="#4EA3FF"/></linearGradient>
          <linearGradient id="gMood" x1="0" x2="1" y1="0" y2="0"><stop offset="0%" stop-color="#4EA3FF"/><stop offset="100%" stop-color="#7C5CFF"/></linearGradient>
        </defs>
        <g id="grid"></g>
        <path id="prodPath" fill="none" stroke="url(#gProd)" stroke-width="3" stroke-linecap="round"/>
        <path id="moodPath" fill="none" stroke="url(#gMood)" stroke-width="3" stroke-linecap="round"/>
        <g id="xlabels"></g>
      </svg>
    </div>
  </div>
</section>

<!-- KPI -->
<section class="section tight">
  <div class="container">
    <div class="grid-12 kpis reveal">
      <div class="card"><div class="knum" data-k="__USERS__">0</div><div class="kcap">Aktivnih korisnika</div></div>
      <div class="card"><div class="knum" data-k="__SESS__">0</div><div class="kcap">Ukupno sesija</div></div>
      <div class="card"><div class="knum" data-k="__SAT__">0</div><div class="kcap">Zadovoljstvo (%)</div></div>
      <div class="card"><div class="knum" data-k="__RET__">0</div><div class="kcap">Mesečna zadržanost (%)</div></div>
    </div>
  </div>
</section>

<!-- Integracije -->
<section class="section tight">
  <div class="container">
    <h2 class="h2">Privatnost & Integracije</h2>
    <div class="grid-12 int reveal">
      <div class="card">🔒 Lokalno čuvanje (MVP)</div>
      <div class="card">🧠 AI na srpskom</div>
      <div class="card">📊 Analitika napretka</div>
      <div class="card">📱 Telefon & računar</div>
    </div>
  </div>
</section>

<!-- Testimonials -->
<section class="section tight">
  <div class="container reveal">
    <div class="twrap">
      <div class="trail" id="trail">
        <div class="tcard"><b>Mila</b><div style="color:#9AA3B2">28 • Beograd</div><div>“Check-in me drži u ritmu. 5 min i osećam pomak.”</div></div>
        <div class="tcard"><b>Nikola</b><div style="color:#9AA3B2">31 • Novi Sad</div><div>“Sve je na srpskom i u mom fazonu.”</div></div>
        <div class="tcard"><b>Sara</b><div style="color:#9AA3B2">24 • Niš</div><div>“Grafovi jasno pokažu kad padam i zašto.”</div></div>
        <div class="tcard"><b>Vuk</b><div style="color:#9AA3B2">35 • Kragujevac</div><div>“Nije terapija, ali odličan dnevni alat.”</div></div>
      </div>
      <div class="tnav"><div class="tbtn" id="prev">◀</div><div class="tbtn" id="next">▶</div></div>
    </div>
  </div>
</section>

<!-- ===== BIG FAQ ===== -->
<section class="section">
  <div class="container faq-zone faq-clouds reveal">
    <div class="faq-header">
      <div class="badge">❓ Česta pitanja</div>
      <h3 class="faq-title">Pitanja? Odgovori!</h3>
      <div class="faq-sub">Brzi odgovori na najčešća pitanja o MindMate platformi.</div>
    </div>

    <div class="faq" id="faq">
      <div class="faq-item">
        <button class="faq-q" aria-expanded="false">
          <span class="txt">Da li je MindMate zamena za terapiju?</span>
          <span class="chev"><svg viewBox="0 0 20 20"><path d="M6 8l4 4 4-4" fill="none" stroke="#C7CEDA" stroke-width="2" stroke-linecap="round"/></svg></span>
        </button>
        <div class="faq-a">Ne. MindMate nije medicinski alat niti zamena za terapiju. Ako postoji rizik — pozovi 112 i potraži stručnu pomoć.</div>
      </div>

      <div class="faq-item">
        <button class="faq-q" aria-expanded="false">
          <span class="txt">Koliko vremena mi treba dnevno?</span>
          <span class="chev"><svg viewBox="0 0 20 20"><path d="M6 8l4 4 4-4" fill="none" stroke="#C7CEDA" stroke-width="2" stroke-linecap="round"/></svg></span>
        </button>
        <div class="faq-a">Obično 3–5 minuta: 2 pitanja za check-in i jedan mali mikro-korak (5–10 min) kada želiš da dodaš momentum.</div>
      </div>

      <div class="faq-item">
        <button class="faq-q" aria-expanded="false">
          <span class="txt">Kako čuvate privatnost?</span>
          <span class="chev"><svg viewBox="0 0 20 20"><path d="M6 8l4 4 4-4" fill="none" stroke="#C7CEDA" stroke-width="2" stroke-linecap="round"/></svg></span>
        </button>
        <div class="faq-a">Za MVP, podaci ostaju lokalno u okviru aplikacije i mogu se obrisati u bilo kom trenutku. Nema deljenja sa trećim stranama.</div>
      </div>

      <div class="faq-item">
        <button class="faq-q" aria-expanded="false">
          <span class="txt">Da li radi na telefonu i računaru?</span>
          <span class="chev"><svg viewBox="0 0 20 20"><path d="M6 8l4 4 4-4" fill="none" stroke="#C7CEDA" stroke-width="2" stroke-linecap="round"/></svg></span>
        </button>
        <div class="faq-a">Da. Interfejs je responzivan i prilagođava se tvojoj rezoluciji (desktop, tablet, telefon).</div>
      </div>
    </div>

    <div class="contact-mini">📧 Imaš pitanje? Piši: <span style="font-weight:700;margin-left:6px">hello@mindmate.app</span></div>
  </div>
</section>

<!-- ===== PRICING (Free / Pro) ===== -->
<section class="section pricing">
  <div class="container reveal">
    <div class="wrap">
      <h2 class="h2" style="margin-bottom:10px">Odaberi svoj ritam</h2>
      <div class="price-grid">
        <!-- Free -->
        <div class="price-card">
          <div class="price-title">Free Trial</div>
          <div class="price-row"><div class="price-num">0</div><div class="price-unit">RSD / 14 dana</div></div>
          <div class="hr"></div>
          <div class="li"><div class="bullet"></div><div>Kompletne funkcije 14 dana</div></div>
          <div class="li"><div class="bullet"></div><div>Dnevni check-in i analitika</div></div>
          <div class="li"><div class="bullet"></div><div>AI chat (srpski)</div></div>
          <a class="price-btn primary" href="?home">Započni besplatno</a>
        </div>
        <!-- Pro -->
        <div class="price-card">
          <div class="price-title">Pro</div>
          <div class="price-row"><div class="price-num">300</div><div class="price-unit">RSD / mes</div></div>
          <div class="hr"></div>
          <div class="li"><div class="bullet"></div><div>Neograničen chat & check-in</div></div>
          <div class="li"><div class="bullet"></div><div>Napredna analitika & ciljevi</div></div>
          <div class="li"><div class="bullet"></div><div>Prioritetna podrška</div></div>
          <a class="price-btn ghost" href="?home">Kreni sa Pro planom</a>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- CTA -->
<section class="section tight">
  <div class="container reveal" style="text-align:center">
    <a class="btn btn-primary" href="?home">Kreni besplatno</a>
  </div>
</section>

<div class="footer">© 2025 MindMate. Nije medicinski alat. Za hitne slučajeve — 112.</div>

<script>
// Reveal
const ob=new IntersectionObserver(es=>es.forEach(x=>x.isIntersecting&&x.target.classList.add('v')),{threshold:.2});
document.querySelectorAll('.reveal').forEach(el=>ob.observe(el));
// KPI count-up
function cu(el){const t=parseInt(el.getAttribute('data-k'))||0,d=1200,s=performance.now();
function tick(n){const p=Math.min((n-s)/d,1);el.textContent=Math.floor(t*(.15+.85*p)).toLocaleString(); if(p<1) requestAnimationFrame(tick)} requestAnimationFrame(tick)}
const ko=new IntersectionObserver(es=>es.forEach(x=>{if(x.isIntersecting){x.target.querySelectorAll('.knum').forEach(cu);ko.unobserve(x.target)}}),{threshold:.3});
document.querySelectorAll('.kpis').forEach(el=>ko.observe(el));
// Chart
const labels=__X_LABELS__, prod=__P_SERIES__, mood=__M_SERIES__; const W=1100,H=320,P=44,ymin=0,ymax=100;
const grid=document.getElementById('grid'), xg=document.getElementById('xlabels'), svg=document.getElementById('mmChart');
for(let i=0;i<=4;i++){const y=P+(H-2*P)*(i/4), l=document.createElementNS("http://www.w3.org/2000/svg","line");
  l.setAttribute("x1",P);l.setAttribute("x2",W-P);l.setAttribute("y1",y);l.setAttribute("y2",y);l.setAttribute("stroke","rgba(255,255,255,.08)");grid.appendChild(l)}
labels.forEach((lab,i)=>{const x=P+(W-2*P)*(i/(labels.length-1||1)), t=document.createElementNS("http://www.w3.org/2000/svg","text");
  t.setAttribute("x",x);t.setAttribute("y",H-10);t.setAttribute("fill","#9AA3B2");t.setAttribute("font-size","12");t.setAttribute("text-anchor","middle");
  t.textContent=lab.slice(5).replace("-","/");xg.appendChild(t)});
function path(vals){const pts=vals.map((v,i)=>[P+(W-2*P)*(i/(vals.length-1||1)), P+(H-2*P)*(1-(v-ymin)/(ymax-ymin))]); if(!pts.length)return ""; let d=`M ${pts[0][0]} ${pts[0][1]}`; for(let i=1;i<pts.length;i++){d+=` L ${pts[i][0]} ${pts[i][1]}`} return d}
const prodPath=document.getElementById('prodPath'), moodPath=document.getElementById('moodPath'); prodPath.setAttribute("d",path(prod)); moodPath.setAttribute("d",path(mood));
function sAnim(p,d=1300){const L=p.getTotalLength();p.style.strokeDasharray=L;p.style.strokeDashoffset=L;p.getBoundingClientRect();p.style.transition=`stroke-dashoffset ${d}ms ease`;p.style.strokeDashoffset="0"}
const cio=new IntersectionObserver(e=>{e.forEach(x=>{if(x.isIntersecting){sAnim(prodPath,1200);setTimeout(()=>sAnim(moodPath,1500),150);cio.unobserve(svg)}})},{threshold:.35});
cio.observe(svg);
// Testimonials slider
(function(){const rail=document.getElementById('trail'); if(!rail) return; let i=0; const cards=rail.children.length;
function go(d){i=(i+d+cards)%cards; rail.style.transform=`translateX(${-i*(rail.children[0].offsetWidth+16)}px)`;}
document.getElementById('prev').onclick=()=>go(-1);document.getElementById('next').onclick=()=>go(1);})();
// FAQ logic
document.querySelectorAll('.faq-item').forEach(item=>{
  const btn=item.querySelector('.faq-q');
  const chev=item.querySelector('.chev');
  const panel=item.querySelector('.faq-a');
  btn.addEventListener('click',()=>{
    const open = btn.getAttribute('aria-expanded')==='true';
    btn.setAttribute('aria-expanded', String(!open));
    chev.style.transform = open ? 'rotate(0deg)' : 'rotate(180deg)';
    if(open){
      panel.style.maxHeight = panel.scrollHeight + 'px';
      requestAnimationFrame(()=>{ panel.style.maxHeight = '0px'; panel.classList.remove('open'); });
    }else{
      panel.classList.add('open');
      panel.style.maxHeight = panel.scrollHeight + 'px';
    }
  });
});
</script>
</body></html>
"""

def render_landing():
    users, sessions, sat, retention = compute_metrics()
    labels, prod, mood = compute_trend_series()
    html = (LANDING
            .replace("__SESS__", str(max(sessions,0)))
            .replace("__USERS__", str(max(users,1)))
            .replace("__SAT__", str(max(min(sat,100),0)))
            .replace("__RET__", str(max(min(retention,100),0)))
            .replace("__X_LABELS__", json.dumps(labels))
            .replace("__P_SERIES__", json.dumps(prod))
            .replace("__M_SERIES__", json.dumps(mood)))
    st_html(html, height=5200, width=1280, scrolling=True)

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

# ---------- Router ----------
page=st.session_state.page
if page=="landing": render_landing()
elif page=="home": render_home()
elif page=="chat": render_chat()
elif page=="checkin": render_checkin()
elif page=="analytics": render_analytics()

st.markdown("<div style='text-align:center;color:#9AA3B2;margin-top:16px'>© 2025 MindMate. Nije medicinski alat. Za hitne slučajeve — 112.</div>", unsafe_allow_html=True)
