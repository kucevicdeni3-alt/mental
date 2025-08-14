# app.py — MindMate (Kendo-style navbar, premium landing, BIG FAQ + PRICING + Početna/Chat/Check-in/Analitika)

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
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

st.set_page_config(page_title=APP_TITLE, page_icon="🧠", layout="wide")

# ---------- Global stil ----------
st.markdown("""
<style>
:root{
  --bg:#0B0D12; --bg-2:#0B0E15; --bg-3:#0B0D13; --panel:#0F1219;
  --ink:#E8EAEE; --mut:#A4AEC0; --ring:rgba(255,255,255,.10);
  --g1:#7C5CFF; --g2:#4EA3FF; --g3:#00E0FF; --warn:#FFE28B;
  --max:1280px;
}
html,body{background:var(--bg); color:var(--ink)}
.main .block-container{
  padding-top:0!important; padding-left:0!important; padding-right:0!important;
  max-width:unset!important;
}
section.mm-wrap{width:100%; display:block;}
.mm-container{max-width:var(--max); margin:0 auto; padding:0 20px;}
/* global btns */
.mm-btn{display:inline-flex; align-items:center; gap:8px; padding:12px 16px; border-radius:14px;
  border:1px solid var(--ring); text-decoration:none; font-weight:800; transition:transform .22s ease, box-shadow .22s ease}
.mm-btn:hover{transform:translateY(-1px) scale(1.02)}
.mm-btn.primary{background:linear-gradient(90deg,var(--g1),var(--g2)); color:#0B0D12}
.mm-btn.ghost{background:rgba(255,255,255,.06); color:var(--ink)}
/* slow reveal */
.reveal{opacity:0; transform:translateY(22px); transition:opacity 1.3s ease, transform 1.3s ease}
.reveal.v{opacity:1; transform:translateY(0)}
/* bg stripes per section (theme shift on scroll) */
.mm-section{position:relative; padding:64px 0; background:radial-gradient(80% 100% at 50% 0%, rgba(124,92,255,.10), transparent 50%), var(--bg)}
.mm-section.alt{background:radial-gradient(80% 100% at 50% 0%, rgba(78,163,255,.12), transparent 50%), var(--bg-2)}
.mm-section.alt2{background:radial-gradient(80% 100% at 50% 0%, rgba(0,224,255,.12), transparent 50%), var(--bg-3)}
/* cards */
.mm-card{background:var(--panel); border:1px solid var(--ring); border-radius:18px; padding:18px;
  transition:transform .22s ease, box-shadow .22s ease}
.mm-card:hover{transform:translateY(-2px) scale(1.02); box-shadow:0 16px 60px rgba(0,0,0,.45)}
/* grid helpers */
.grid{display:grid; gap:18px}
.g12{grid-template-columns:repeat(12,1fr)}
.span-12{grid-column:span 12}
.span-6{grid-column:span 6}
.span-4{grid-column:span 4}
.span-3{grid-column:span 3}
@media (max-width:1024px){ .span-6,.span-4,.span-3{grid-column:span 12} .g12{grid-template-columns:repeat(12,1fr)} }
/* headings */
.h-eyebrow{display:inline-flex; gap:8px; align-items:center; padding:7px 12px; border-radius:999px; border:1px solid var(--ring);
  background:rgba(255,255,255,.05); color:#C7CEDA; font-size:12px; letter-spacing:.3px}
.h-title{font-size:clamp(28px,4.8vw,56px); line-height:1.06; margin:10px 0 6px}
.h-sub{color:var(--mut); margin:0 0 10px}
.h2{font-size:clamp(22px,2.6vw,30px); margin:0 0 14px}

/* ---------- KENDO-STYLE NAVBAR ---------- */
.mm-top{position:sticky; top:0; z-index:1000; pointer-events:none}
.k-nav-shell{pointer-events:auto; position:relative; margin:0 auto; max-width:var(--max); padding:10px 20px}
.k-nav{display:flex; align-items:center; justify-content:space-between; gap:12px;
  background:rgba(13,16,23,.65); border:1px solid var(--ring);
  border-radius:16px; padding:8px 10px; backdrop-filter:blur(14px);
  transition:transform .35s ease, box-shadow .35s ease, background .35s ease}
.k-left{display:flex; align-items:center; gap:10px; font-weight:900}
.k-dot{width:10px; height:10px; border-radius:50%;
  background:conic-gradient(from 0deg, var(--g1), var(--g2), var(--g3), var(--g1));
  box-shadow:0 0 12px rgba(124,92,255,.7)}
.k-mid{display:flex; align-items:center; gap:6px; background:rgba(255,255,255,.04);
  border:1px solid var(--ring); border-radius:12px; padding:4px}
.k-tab{position:relative; display:inline-flex; align-items:center; justify-content:center;
  padding:8px 12px; border-radius:10px; color:#E8EAEE; text-decoration:none; font-weight:800; letter-spacing:.2px;
  transition:transform .18s ease}
.k-tab:hover{transform:translateY(-1px)}
.k-underline{position:absolute; height:2px; background:linear-gradient(90deg,var(--g1),var(--g2));
  bottom:-2px; left:0; width:100%; border-radius:2px; opacity:.9}
.k-cta{display:inline-flex; align-items:center; gap:8px; padding:10px 12px; border-radius:12px; font-weight:900;
  border:1px solid var(--ring); background:linear-gradient(90deg,var(--g1),var(--g2)); color:#0B0D12; text-decoration:none}
.k-shadow{position:absolute; inset:-14px -14px -14px -14px; border-radius:22px; z-index:-1;
  background:radial-gradient(60% 50% at 20% 10%, rgba(124,92,255,.18), transparent 60%),
             radial-gradient(60% 50% at 80% 20%, rgba(78,163,255,.18), transparent 60%)}
.k-hide{transform:translateY(-120%); box-shadow:none}
.k-show{transform:translateY(0)}
/* active pill feedback like Kendo */
.k-tab[data-active="true"]{background:rgba(255,255,255,.08)}

/* ---------- HERO ---------- */
.hero{display:grid; grid-template-columns:1.1fr .9fr; gap:28px; align-items:center}
@media (max-width:1024px){ .hero{grid-template-columns:1fr} }
.mira{display:flex; justify-content:center}
#flower{width:min(420px,72vw); filter:drop-shadow(0 14px 42px rgba(124,92,255,.35))}
#flower .p{transform-origin:50% 50%; animation:sway 6.6s ease-in-out infinite}
#flower .c{animation:pulse 6s ease-in-out infinite}
@keyframes sway{0%{transform:rotate(0)} 50%{transform:rotate(2.2deg)} 100%{transform:rotate(0)}}
@keyframes pulse{0%,100%{opacity:.85} 50%{opacity:1}}

/* ---------- VSL + GLOW ORB ---------- */
.vsl-wrap{position:relative}
.orb{
  position:absolute; inset:-200px 0 0 0; margin:auto; z-index:0;
  width:min(1020px,92vw); height:min(1020px,92vw);
  background:
   radial-gradient(60% 55% at 50% 40%, rgba(124,92,255,.55), transparent 62%),
   radial-gradient(58% 52% at 50% 45%, rgba(78,163,255,.50), transparent 66%),
   radial-gradient(46% 40% at 50% 52%, rgba(154,214,255,.22), transparent 70%);
  filter: blur(28px) saturate(1.05); opacity:.9; animation:orbBreath 12s ease-in-out infinite;
}
@keyframes orbBreath{0%,100%{transform:scale(1)} 50%{transform:scale(1.04)}}
.vsl{position:relative; z-index:1; max-width:1020px; margin:0 auto; border-radius:16px; border:1px solid var(--ring);
  padding:10px; background:rgba(255,255,255,.05); box-shadow:0 28px 90px rgba(0,0,0,.65)}
.vsl iframe{width:100%; aspect-ratio:16/9; height:auto; min-height:240px; border:0; border-radius:10px}

/* ---------- TRUSTED BY ---------- */
.trusted{display:flex; flex-direction:column; gap:10px; align-items:center; margin-top:14px}
.logos{display:flex; gap:16px; flex-wrap:wrap; justify-content:center}
.logo{width:120px; height:44px; border-radius:12px; border:1px solid var(--ring);
  background:rgba(255,255,255,.04); display:flex; align-items:center; justify-content:center;
  color:#C7CEDA; font-weight:800; letter-spacing:.4px; transition:transform .2s}
.logo:hover{transform:translateY(-2px)}

/* ---------- FEATURE 3-UP ---------- */
.f3 .mm-card{min-height:120px}

/* ---------- COMPARE ---------- */
.compare{display:grid; grid-template-columns:1fr 1fr; gap:18px}
@media (max-width:1024px){ .compare{grid-template-columns:1fr} }

/* ---------- DEMO CHART (SVG) ---------- */
.chart-wrap{background:var(--panel); border:1px solid var(--ring); border-radius:16px; padding:18px}
.legend{display:flex; gap:12px; align-items:center; color:#C7CEDA; margin-bottom:6px}
.dot{width:12px; height:12px; border-radius:50%}
.dot-prod{background:#7C5CFF}.dot-mood{background:#4EA3FF}

/* ---------- KPIs ---------- */
.kpis .mm-card{text-align:center}
.knum{font-size:clamp(22px,3vw,30px); font-weight:900;
  background:linear-gradient(90deg,var(--g1),var(--g2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent}
.kcap{color:var(--mut)}

/* ---------- INTEGRATIONS ---------- */
.int .mm-card{text-align:center; color:#C7CEDA}

/* ---------- TESTIMONIALS (carousel) ---------- */
.twrap{border:1px solid var(--ring); border-radius:16px; padding:16px; background:var(--panel); position:relative; overflow:hidden}
.trail{display:flex; gap:16px; transition:transform .45s ease}
.tcard{min-width:calc(33.33% - 10.6px); background:rgba(255,255,255,.04); border:1px solid var(--ring); border-radius:12px; padding:14px}
.tnav{position:absolute; top:50%; left:8px; right:8px; display:flex; justify-content:space-between; transform:translateY(-50%)}
.tbtn{padding:7px 10px; border-radius:12px; background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.12); cursor:pointer; transition:transform .18s}
.tbtn:hover{transform:scale(1.06)}
@media (max-width:1024px){ .tcard{min-width:calc(100% - 10.6px)} }

/* ---------- BIG FAQ ---------- */
.faq-zone{position:relative; overflow:hidden; border-radius:20px; border:1px solid var(--ring);
  background:linear-gradient(180deg,#0F1219, #0E131A 55%, #0C1016)}
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
.badge{display:inline-flex; gap:6px; align-items:center; color:#C7CEDA; font-size:13px; padding:7px 12px; border:1px solid var(--ring);
  border-radius:999px; background:rgba(255,255,255,.05)}
.faq-title{font-size:clamp(26px,4.2vw,44px); margin:8px 0 6px 0}
.faq-sub{color:#A7B0BE; max-width:860px; margin:0 auto 18px}

.faq{max-width:920px; margin:0 auto 26px; background:transparent; border:0}
.faq-item{border:1px solid var(--ring); border-radius:14px; background:#0F1219; margin:12px 0; overflow:hidden;
  box-shadow:0 10px 26px rgba(0,0,0,.25); transition:transform .18s ease, box-shadow .18s ease}
.faq-item:hover{transform:translateY(-1px); box-shadow:0 14px 36px rgba(0,0,0,.33)}
.faq-q{width:100%; text-align:left; background:none; border:none; color:#E8EAEE; font-weight:800; padding:18px 18px; cursor:pointer;
  display:flex; align-items:center; justify-content:space-between}
.faq-q .txt{pointer-events:none}
.chev{width:22px; height:22px; border-radius:6px; border:1px solid var(--ring); display:grid; place-items:center; transition:transform .28s cubic-bezier(.2,.8,.2,1)}
.chev svg{width:12px; height:12px}
.faq-a{max-height:0; overflow:hidden; color:#C7CEDA; padding:0 18px; transition:max-height .5s cubic-bezier(.2,.8,.2,1), padding .5s cubic-bezier(.2,.8,.2,1)}
.faq-a.open{padding:12px 18px 18px}
.contact-mini{display:flex; align-items:center; justify-content:center; gap:10px; color:#C7CEDA; padding:8px 0 18px}

/* ---------- PRICING ---------- */
.pricing .wrap{border:1px solid var(--ring); border-radius:20px; padding:24px; background:var(--panel)}
.price-grid{display:grid; grid-template-columns:1fr 1fr; gap:18px; align-items:stretch}
.price-card{background:rgba(17,20,28,.9); border:1px solid var(--ring); border-radius:18px; padding:22px;
  box-shadow:0 16px 44px rgba(0,0,0,.35); transition:transform .18s, box-shadow .18s}
.price-card:hover{transform:translateY(-2px) scale(1.02); box-shadow:0 22px 60px rgba(0,0,0,.45)}
.price-title{font-weight:900; margin:0 0 6px 0}
.price-row{display:flex; align-items:baseline; gap:8px}
.price-num{font-size:clamp(28px,4vw,36px); font-weight:900}
.price-unit{color:#9AA3B2; font-weight:700}
.hr{height:1px; background:rgba(255,255,255,.08); margin:12px 0}
.li{display:flex; gap:10px; align-items:flex-start; color:#C7CEDA; margin:8px 0}
.bullet{width:8px; height:8px; border-radius:50%; background:linear-gradient(90deg,var(--g1),var(--g2)); margin-top:8px}
.price-btn{margin-top:14px; display:inline-block; padding:12px 16px; border-radius:12px; font-weight:800; text-decoration:none; border:1px solid var(--ring)}
.price-btn.primary{background:linear-gradient(90deg,var(--g1),var(--g2)); color:#0B0D12}
.price-btn.ghost{background:rgba(255,255,255,.06); color:#E8EAEE}
@media (max-width:1024px){ .price-grid{grid-template-columns:1fr} }

/* ---------- FOOTER ---------- */
.mm-foot{text-align:center; color:#9AA3B2; padding:16px 0 22px}

/* Streamlit primary buttons tweak */
.stButton>button[kind="primary"]{
  background:linear-gradient(90deg,var(--g1),var(--g2))!important; color:#0B0D12!important;
  font-weight:800!important; border:none!important
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

# ---------- Kendo-style NAVBAR (HTML + JS) ----------
NAVBAR = """
<div class="mm-top">
  <div class="k-nav-shell">
    <div id="kNav" class="k-nav k-show">
      <div class="k-left">
        <div class="k-dot"></div>
        <div>MindMate</div>
      </div>
      <div class="k-mid">
        <a class="k-tab" data-id="landing" href="?landing">Welcome<span class="k-underline" style="display:none"></span></a>
        <a class="k-tab" data-id="home" href="?home">Početna<span class="k-underline" style="display:none"></span></a>
        <a class="k-tab" data-id="chat" href="?chat">Chat<span class="k-underline" style="display:none"></span></a>
        <a class="k-tab" data-id="checkin" href="?checkin">Check-in<span class="k-underline" style="display:none"></span></a>
        <a class="k-tab" data-id="analytics" href="?analytics">Analitika<span class="k-underline" style="display:none"></span></a>
      </div>
      <a class="k-cta" href="?home">Kreni besplatno</a>
      <div class="k-shadow"></div>
    </div>
  </div>
</div>
<script>
(function(){
  // Active tab highlight by query param
  const tabs = Array.from(document.querySelectorAll('.k-tab'));
  function activeId(){
    const q = new URLSearchParams(window.location.search);
    const ids = ["landing","home","chat","checkin","analytics"];
    for(const id of ids){ if(q.has(id)) return id; }
    return "landing";
  }
  function setActive(){
    const id = activeId();
    tabs.forEach(t=>{
      const on = t.getAttribute('data-id')===id;
      t.setAttribute('data-active', on ? 'true' : 'false');
      const u = t.querySelector('.k-underline');
      if(u) u.style.display = on ? 'block' : 'none';
    });
  }
  setActive();

  // Hide on scroll down / show on scroll up
  const nav = document.getElementById('kNav');
  let lastY = window.scrollY;
  let ticking = false;
  function onScroll(){
    const y = window.scrollY;
    if(!ticking){
      window.requestAnimationFrame(()=>{
        if(y>lastY && y>64){ nav.classList.add('k-hide'); nav.classList.remove('k-show'); }
        else { nav.classList.remove('k-hide'); nav.classList.add('k-show'); }
        lastY = y;
        ticking = false;
      });
      ticking = true;
    }
  }
  window.addEventListener('scroll', onScroll, {passive:true});

  // When Streamlit re-renders, keep underline consistent
  window.addEventListener('popstate', setActive);
})();
</script>
"""

# ---------- Parse query for routing ----------
qp = st.query_params
if   "landing"   in qp: st.session_state.page = "landing"
elif "home"      in qp: st.session_state.page = "home"
elif "chat"      in qp: st.session_state.page = "chat"
elif "checkin"   in qp: st.session_state.page = "checkin"
elif "analytics" in qp: st.session_state.page = "analytics"

# ---------- LANDING (premium) ----------
LANDING = """
<!DOCTYPE html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
</head>
<body>
<!-- HERO -->
<section class="mm-section">
  <div class="mm-container">
    <div class="hero reveal">
      <div>
        <div class="h-eyebrow">MindMate • Mentalni wellness</div>
        <h1 class="h-title">Preusmeri 80% briga u konkretne korake — za 5 minuta dnevno.</h1>
        <p class="h-sub">Kratki check-in, mikro-navike i empatičan razgovor. Jasni trendovi, tvoj ritam.</p>
        <div style="display:flex; gap:10px; flex-wrap:wrap">
          <a class="mm-btn primary" href="?home">Kreni odmah</a>
          <a class="mm-btn ghost" href="#vsl">Pogledaj kako radi</a>
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
  </div>
</section>

<!-- VSL + planeta (orb) + Trusted by -->
<section id="vsl" class="mm-section alt">
  <div class="mm-container reveal">
    <div class="vsl-wrap">
      <div class="orb"></div>
      <div class="vsl"><iframe src="https://www.youtube.com/embed/1qK0c9J_h10?rel=0&modestbranding=1" title="MindMate VSL" allowfullscreen></iframe></div>
    </div>
    <div class="trusted">
      <div style="opacity:.9">Trusted by folks from:</div>
      <div class="logos">
        <div class="logo">Health+</div><div class="logo">Calmify</div><div class="logo">WellLabs</div>
        <div class="logo">FocusHub</div><div class="logo">MindBank</div>
      </div>
    </div>
  </div>
</section>

<!-- Benefiti -->
<section class="mm-section">
  <div class="mm-container">
    <h2 class="h2">Zašto početi danas</h2>
    <div class="grid g12 f3 reveal">
      <div class="mm-card span-4"><b>2 pitanja dnevno</b><br><span style="color:#9AA3B2">Brz check-in bez frke; gradi ritam.</span></div>
      <div class="mm-card span-4"><b>Mikro-navike (5–10 min)</b><br><span style="color:#9AA3B2">Male akcije → vidljiv napredak.</span></div>
      <div class="mm-card span-4"><b>Grafovi i obrasci</b><br><span style="color:#9AA3B2">Jasno vidiš raspoloženje i fokus.</span></div>
    </div>
  </div>
</section>

<!-- Poređenje -->
<section class="mm-section alt2">
  <div class="mm-container reveal">
    <h2 class="h2">Bez plana vs. sa MindMate</h2>
    <div class="compare">
      <div class="mm-card"><b>Bez plana</b><ul style="color:#9AA3B2;margin:.5rem 0 0 1rem">
        <li>Nasumične navike, bez praćenja</li><li>Preplavljenost</li><li>Nema jasnih trendova</li></ul></div>
      <div class="mm-card"><b>Sa MindMate</b><ul style="color:#9AA3B2;margin:.5rem 0 0 1rem">
        <li>2 pitanja + mikro-koraci</li><li>Empatičan razgovor u tvom tonu</li><li>Grafovi napretka</li></ul></div>
    </div>
  </div>
</section>

<!-- Mini demo graf -->
<section class="mm-section">
  <div class="mm-container reveal">
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
<section class="mm-section alt">
  <div class="mm-container">
    <div class="grid g12 kpis reveal">
      <div class="mm-card span-3"><div class="knum" data-k="__USERS__">0</div><div class="kcap">Aktivnih korisnika</div></div>
      <div class="mm-card span-3"><div class="knum" data-k="__SESS__">0</div><div class="kcap">Ukupno sesija</div></div>
      <div class="mm-card span-3"><div class="knum" data-k="__SAT__">0</div><div class="kcap">Zadovoljstvo (%)</div></div>
      <div class="mm-card span-3"><div class="knum" data-k="__RET__">0</div><div class="kcap">Mesečna zadržanost (%)</div></div>
    </div>
  </div>
</section>

<!-- Integracije -->
<section class="mm-section">
  <div class="mm-container">
    <h2 class="h2">Privatnost & Integracije</h2>
    <div class="grid g12 int reveal">
      <div class="mm-card span-3">🔒 Lokalno čuvanje (MVP)</div>
      <div class="mm-card span-3">🧠 AI na srpskom</div>
      <div class="mm-card span-3">📊 Analitika napretka</div>
      <div class="mm-card span-3">📱 Telefon & računar</div>
    </div>
  </div>
</section>

<!-- Testimonials -->
<section class="mm-section alt2">
  <div class="mm-container reveal">
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

<!-- BIG FAQ -->
<section class="mm-section">
  <div class="mm-container faq-zone faq-clouds reveal">
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

<!-- PRICING -->
<section class="mm-section alt">
  <div class="mm-container reveal">
    <div class="pricing">
      <div class="wrap">
        <h2 class="h2" style="margin-bottom:10px">Odaberi svoj ritam</h2>
        <div class="price-grid">
          <div class="price-card">
            <div class="price-title">Free Trial</div>
            <div class="price-row"><div class="price-num">0</div><div class="price-unit">RSD / 14 dana</div></div>
            <div class="hr"></div>
            <div class="li"><div class="bullet"></div><div>Kompletne funkcije 14 dana</div></div>
            <div class="li"><div class="bullet"></div><div>Dnevni check-in i analitika</div></div>
            <div class="li"><div class="bullet"></div><div>AI chat (srpski)</div></div>
            <a class="price-btn primary" href="?home">Započni besplatno</a>
          </div>
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
  </div>
</section>

<!-- CTA -->
<section class="mm-section">
  <div class="mm-container reveal" style="text-align:center">
    <a class="mm-btn primary" href="?home">Kreni besplatno</a>
  </div>
</section>

<div class="mm-foot">© 2025 MindMate. Nije medicinski alat. Za hitne slučajeve — 112.</div>

<script>
// Slow reveal
const ob=new IntersectionObserver(es=>es.forEach(x=>x.isIntersecting&&x.target.classList.add('v')),{threshold:.22});
document.querySelectorAll('.reveal').forEach(el=>ob.observe(el));

// KPI count-up (slightly longer)
function cu(el){const t=parseInt(el.getAttribute('data-k'))||0,d=1600,s=performance.now();
function tick(n){const p=Math.min((n-s)/d,1); el.textContent=Math.floor(t*(.12+.88*p)).toLocaleString(); if(p<1) requestAnimationFrame(tick)} requestAnimationFrame(tick)}
const ko=new IntersectionObserver(es=>es.forEach(x=>{if(x.isIntersecting){x.target.querySelectorAll('.knum').forEach(cu); ko.unobserve(x.target)}}),{threshold:.35});
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
function sAnim(p,d=1500){const L=p.getTotalLength();p.style.strokeDasharray=L;p.style.strokeDashoffset=L;p.getBoundingClientRect();p.style.transition=`stroke-dashoffset ${d}ms ease`;p.style.strokeDashoffset="0"}
const cio=new IntersectionObserver(e=>{e.forEach(x=>{if(x.isIntersecting){sAnim(prodPath,1500);setTimeout(()=>sAnim(moodPath,1800),160);cio.unobserve(svg)}})},{threshold:.35});
cio.observe(svg);

// Testimonials slider
(function(){const rail=document.getElementById('trail'); if(!rail) return; let i=0; const cards=rail.children.length;
function go(d){i=(i+d+cards)%cards; const w=rail.children[0].offsetWidth+16; rail.style.transform=`translateX(${-i*w}px)`;}
document.getElementById('prev').onclick=()=>go(-1); document.getElementById('next').onclick=()=>go(1);})();

// FAQ expand (no cut off)
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
    html = (NAVBAR + LANDING
            .replace("__SESS__", str(max(sessions,0)))
            .replace("__USERS__", str(max(users,1)))
            .replace("__SAT__", str(max(min(sat,100),0)))
            .replace("__RET__", str(max(min(retention,100),0)))
            .replace("__X_LABELS__", json.dumps(labels))
            .replace("__P_SERIES__", json.dumps(prod))
            .replace("__M_SERIES__", json.dumps(mood)))
    st_html(html, height=5600, scrolling=True)

# ---------- HOME / CHAT / CHECKIN / ANALYTICS (part 1/2) ----------
def render_home():
    st.markdown(NAVBAR, unsafe_allow_html=True)
    st.markdown("<section class='mm-wrap mm-section'><div class='mm-container'><h2 class='h2'>Tvoja kontrolna tabla</h2></div></section>", unsafe_allow_html=True)
    c1,c2,c3=st.columns(3)
    with c1:
        st.markdown("**Chat** — AI na srpskom, praktičan i podržavajući.")
        if st.button("Otvori chat →", use_container_width=True): goto("chat")
    with c2:
        st.markdown("**Check-in** — 2 pitanja + mikro-ciljevi i streak.")
        if st.button("Idi na check-in →", use_container_width=True): goto("checkin")
    with c3:
        st.markdown("**Analitika** — trendovi i talasne linije napretka.")
        if st.button("Vidi trendove →", use_container_width=True): goto("analytics")

def chat_reply(sys, log):
    msgs=[{"role":"system","content":sys}] + [{"role":r,"content":m} for r,m in log]
    return chat_openai(msgs) if CHAT_PROVIDER=="openai" else chat_ollama(msgs)

def render_chat():
    st.markdown(NAVBAR, unsafe_allow_html=True)
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
    st.markdown(NAVBAR, unsafe_allow_html=True)
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
    st.markdown(NAVBAR, unsafe_allow_html=True)
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

st.markdown("<div class='mm-foot'>© 2025 MindMate. Nije medicinski alat. Za hitne slučajeve — 112.</div>", unsafe_allow_html=True)
# =================== FAQ SECTION ===================
st.markdown("---")
st.markdown("## ❓ Često postavljena pitanja", unsafe_allow_html=True)

faq_items = {
    "Da li je MindMate zamena za terapiju?": 
        "Ne, MindMate nije medicinski alat, već podrška za svakodnevno mentalno zdravlje. "
        "Uvek se posavetujte sa stručnjakom za ozbiljne probleme.",
    "Koliko vremena mi treba dnevno?": 
        "Samo 5–10 minuta dnevno za check-in i pregled napretka.",
    "Kako čuvate privatnost?": 
        "Svi podaci se čuvaju lokalno na vašem uređaju i ne dele se sa trećim licima.",
    "Da li mogu koristiti MindMate besplatno?": 
        "Da, postoji besplatna verzija sa osnovnim funkcijama.",
    "Šta dobijam u premium planu?": 
        "Napredna analitika, AI coach 24/7 i personalizovani mikro-koraci."
}

for question, answer in faq_items.items():
    with st.expander(question, expanded=False):
        st.write(answer)

# =================== PRICING SECTION ===================
st.markdown("---")
st.markdown("## 💳 Izaberi plan", unsafe_allow_html=True)

pc1, pc2 = st.columns(2)

with pc1:
    st.markdown("### 🆓 Free Plan")
    st.write("✅ Dnevni check-in")
    st.write("✅ Osnovna analitika")
    st.write("✅ Pristup osnovnim savetima")
    st.markdown("**Cena:** 0€/mesec")
    if st.button("Izaberi Free", key="free_plan"):
        st.success("Izabrali ste Free Plan!")

with pc2:
    st.markdown("### 💜 Premium Plan")
    st.write("✅ Sve iz Free plana")
    st.write("✅ Napredna analitika")
    st.write("✅ AI coach 24/7")
    st.write("✅ Personalizovani mikro-koraci")
    st.markdown("**Cena:** 9.99€/mesec")
    if st.button("Izaberi Premium", key="premium_plan"):
        st.success("Izabrali ste Premium Plan!")

# =================== ADDITIONAL TRUST SECTION ===================
st.markdown("---")
st.markdown("## 🌟 Naš uticaj", unsafe_allow_html=True)

impact_cols = st.columns(4)
impact_data = [
    ("📈", "Povećano zadovoljstvo", "92% korisnika prijavilo bolju organizaciju života"),
    ("🧠", "Smanjen stres", "80% korisnika se oseća smirenije posle 30 dana"),
    ("⏳", "Ušteda vremena", "Prosečno 25 minuta dnevno ušteđeno"),
    ("💬", "Pozitivni komentari", "5000+ pozitivnih recenzija")
]

for col, (icon, title, desc) in zip(impact_cols, impact_data):
    with col:
        st.markdown(f"### {icon} {title}")
        st.write(desc)

# =================== BACKGROUND COLOR SCROLL EFFECT ===================
st.markdown(
    """
    <script>
    document.addEventListener('scroll', function() {
        const y = window.scrollY;
        if (y > 500 && y < 1200) {
            document.body.style.background = 'linear-gradient(180deg, #f0e6ff, #ffffff)';
        } else if (y >= 1200) {
            document.body.style.background = 'linear-gradient(180deg, #ffe6f0, #ffffff)';
        } else {
            document.body.style.background = 'white';
        }
    });
    </script>
    """,
    unsafe_allow_html=True
)

# =================== FOOTER ===================
st.markdown("---")
footer_col1, footer_col2, footer_col3 = st.columns(3)

with footer_col1:
    st.markdown("### 📍 O nama")
    st.write("MindMate je AI platforma posvećena svakodnevnoj brizi o mentalnom zdravlju.")

with footer_col2:
    st.markdown("### 🔗 Linkovi")
    st.write("[Početna](#pocetna)")
    st.write("[Chat](#chat)")
    st.write("[Analitika](#analitika)")

with footer_col3:
    st.markdown("### 📬 Kontakt")
    st.write("Email: support@mindmate.ai")
    st.write("Telefon: +381 60 123 4567")

st.markdown(
    "<p style='text-align:center; color:gray; font-size:14px;'>© 2025 MindMate. Sva prava zadržana.</p>",
    unsafe_allow_html=True
)
