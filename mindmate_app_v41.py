# app.py — MindMate: landing + Kendo-style navbar + Auth (login/signup) + Chat/Check-in/Analytics

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

# ------------ Sesija / "auth" helpers ------------
if "page" not in st.session_state: st.session_state.page="landing"
if "chat_log" not in st.session_state: st.session_state.chat_log=[]
if "user_email" not in st.session_state: st.session_state.user_email=None

def is_authed() -> bool:
    return bool(st.session_state.user_email)

def set_user(email:str):
    st.session_state.user_email = (email or "").strip() or None

def logout():
    st.session_state.user_email=None
    # opcionalno: očisti logove četa samo za demo
    # st.session_state.chat_log=[]

def goto(p): 
    st.session_state.page=p; safe_rerun()

# ------------ Global stil ------------
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

# ------------ “Baza” ------------
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

# ------------ Chat backends ------------
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

# ------------ NAV (Kendo style) ------------
def nav_html():
    # desni deo: ili Sign up / Log in, ili Dashboard / Logout
    if is_authed():
        right = """
        <a class="k-ghost" href="?home">Dashboard</a>
        <a class="k-cta" href="?logout=1">Logout</a>
        """
    else:
        right = """
        <a class="k-ghost" href="?auth=login">Log in</a>
        <a class="k-cta" href="?auth=signup">Sign up</a>
        """
    return f"""
<style>
.k-wrap{{position:sticky;top:0;z-index:20;background:rgba(17,20,28,.65);backdrop-filter:blur(10px);
         border-bottom:1px solid var(--ring)}}
.k-nav{{max-width:1180px;margin:0 auto;padding:10px 6px;display:flex;align-items:center;justify-content:space-between}}
.k-left{{display:flex;align-items:center;gap:16px}}
.k-brand{{display:flex;align-items:center;gap:10px;font-weight:900;color:#E8EAEE}}
.k-dot{{width:10px;height:10px;border-radius:50%;background:linear-gradient(90deg,var(--g1),var(--g2));
        box-shadow:0 0 12px rgba(124,92,255,.7)}}
.k-links{{display:flex;gap:6px;flex-wrap:wrap}}
.k-link,.k-ghost,.k-cta{{text-decoration:none; font-weight:700; border-radius:12px; padding:8px 12px;}}
.k-link{{color:#E8EAEE;border:1px solid var(--ring);background:rgba(255,255,255,.02)}}
.k-ghost{{color:#E8EAEE;border:1px solid var(--ring);background:rgba(255,255,255,.04)}}
.k-cta{{color:#0B0D12;background:linear-gradient(90deg,var(--g1),var(--g2));}}
.k-link:hover,.k-ghost:hover{{transform:translateY(-1px) scale(1.03);border-color:rgba(255,255,255,.18)}}
</style>
<div class="k-wrap"><div class="k-nav">
  <div class="k-left">
    <div class="k-brand"><div class="k-dot"></div><div>MindMate</div></div>
    <div class="k-links">
      <a class="k-link" href="?landing">Welcome</a>
      <a class="k-link" href="?home">Početna</a>
      <a class="k-link" href="?chat">Chat</a>
      <a class="k-link" href="?checkin">Check-in</a>
      <a class="k-link" href="?analytics">Analitika</a>
    </div>
  </div>
  <div class="k-links">{right}</div>
</div></div>
"""
st.markdown(nav_html(), unsafe_allow_html=True)

# query params → page/mode
qp = st.query_params
if "logout" in qp:
    logout()
    st.query_params.clear()
    st.session_state.page="landing"

if   "landing"  in qp: st.session_state.page="landing"
elif "home"     in qp: st.session_state.page="home"
elif "chat"     in qp: st.session_state.page="chat"
elif "checkin"  in qp: st.session_state.page="checkin"
elif "analytics"in qp: st.session_state.page="analytics"
elif "auth"     in qp: 
    st.session_state.page="auth"
    st.session_state.auth_mode = qp.get("auth", "login")

# ------------ LANDING (ostaje kao pre) ------------
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

/* BIG FAQ / PRICING / Reveal same as pre */
.faq-zone{position:relative;overflow:hidden;border-radius:20px;border:1px solid var(--ring);background:linear-gradient(180deg,#0F1219, #0E131A 55%, #0C1016)}
.faq-clouds:before, .faq-clouds:after{{content:""; position:absolute; inset:auto -20% -40% -20%; height:240px;
  background:
    radial-gradient(240px 120px at 20% 60%, rgba(255,255,255,.06), transparent 65%),
    radial-gradient(200px 100px at 60% 40%, rgba(255,255,255,.05), transparent 60%),
    radial-gradient(220px 110px at 85% 70%, rgba(255,255,255,.04), transparent 65%);
  filter:blur(12px); opacity:.7; animation:cloudFloat 26s linear infinite;}}
.faq-clouds:after{{ inset:auto -25% -45% -25%; animation-duration:32s; opacity:.55 }}
@keyframes cloudFloat{{0%{{transform:translateX(-6%)}} 50%{{transform:translateX(6%)}} 100%{{transform:translateX(-6%)}}}}
.faq-header{{text-align:center; padding:28px 16px 10px}}
.badge{{display:inline-flex;gap:6px;align-items:center;color:#C7CEDA;font-size:13px;padding:7px 12px;border:1px solid var(--ring);border-radius:999px;background:rgba(255,255,255,.05)}}
.faq-title{{font-size:clamp(26px,4.2vw,44px);margin:8px 0 6px 0}}
.faq-sub{{color:#A7B0BE;max-width:860px;margin:0 auto 18px}}
.faq{{max-width:920px;margin:0 auto 26px;background:transparent;border:0}}
.faq-item{{border:1px solid var(--ring);border-radius:14px;background:#0F1219;margin:12px 0;overflow:hidden;box-shadow:0 10px 26px rgba(0,0,0,.25); transition:transform .18s ease, box-shadow .18s ease}}
.faq-item:hover{{transform:translateY(-1px); box-shadow:0 14px 36px rgba(0,0,0,.33)}}
.faq-q{{width:100%;text-align:left;background:none;border:none;color:#E8EAEE;font-weight:800;padding:18px 18px;cursor:pointer; display:flex; align-items:center; justify-content:space-between}}
.faq-q .txt{{pointer-events:none}}
.chev{{width:22px;height:22px;border-radius:6px;border:1px solid var(--ring);display:grid;place-items:center;transition:transform .28s cubic-bezier(.2,.8,.2,1)}}
.chev svg{{width:12px;height:12px}}
.faq-a{{max-height:0;overflow:hidden;color:#C7CEDA;padding:0 18px;transition:max-height .42s cubic-bezier(.2,.8,.2,1), padding .42s cubic-bezier(.2,.8,.2,1)}}
.faq-a.open{{padding:12px 18px 18px}}
.contact-mini{{display:flex;align-items:center;justify-content:center;gap:10px;color:#C7CEDA;padding:8px 0 18px}}

.pricing .wrap{{border:1px solid var(--ring);border-radius:20px;padding:24px;background:#0F1219}}
.price-grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:stretch}}
.price-card{{background:rgba(17,20,28,.9);border:1px solid var(--ring);border-radius:18px;padding:22px;box-shadow:0 16px 44px rgba(0,0,0,.35); transition:transform .18s, box-shadow .18s}}
.price-card:hover{{transform:translateY(-2px) scale(1.02); box-shadow:0 22px 60px rgba(0,0,0,.45)}}
.price-title{{font-weight:900;margin:0 0 6px 0}}
.price-row{{display:flex;align-items:baseline;gap:8px}}
.price-num{{font-size:clamp(28px,4vw,36px);font-weight:900}}
.price-unit{{color:#9AA3B2;font-weight:700}}
.hr{{height:1px;background:rgba(255,255,255,.08);margin:12px 0}}
.li{{display:flex;gap:10px;align-items:flex-start;color:#C7CEDA;margin:8px 0}}
.bullet{{width:8px;height:8px;border-radius:50%;background:linear-gradient(90deg,var(--g1),var(--g2));margin-top:8px}}
.price-btn{{margin-top:14px;display:inline-block;padding:12px 16px;border-radius:12px;font-weight:800;text-decoration:none;border:1px solid var(--ring)}}
.price-btn.primary{{background:linear-gradient(90deg,var(--g1),var(--g2));color:#0B0D12}}
.price-btn.ghost{{background:rgba(255,255,255,.06);color:#E8EAEE}}
@media (max-width:900px){{ .price-grid{{grid-template-columns:1fr}} }}

.reveal{{opacity:0;transform:translateY(20px);transition:opacity 1.2s ease, transform 1.2s ease}}
.reveal.v{{opacity:1;transform:translateY(0)}}

.footer{{color:#9AA3B2;text-align:center;padding:16px 0 22px}}
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
        <a class="btn btn-ghost" href="?auth=signup">Kreiraj nalog</a>
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

<!-- (ostali delovi: VSL/Trusted/Features/Compare/Chart/KPIs/Integracije/Testimonials/FAQ/Pricing/CTA) -->
<!-- ====== SKRAĆENO: isti sadržaj kao kod tebe (nije menjan) ====== -->

<div class="footer">© 2025 MindMate. Nije medicinski alat. Za hitne slučajeve — 112.</div>

<script>
// Reveal
const ob=new IntersectionObserver(es=>es.forEach(x=>x.isIntersecting&&x.target.classList.add('v')),{threshold:.2});
document.querySelectorAll('.reveal').forEach(el=>ob.observe(el));
</script>
</body></html>
"""

def render_landing():
    users, sessions, sat, retention = compute_metrics()
    labels, prod, mood = compute_trend_series()
    # (graf/faq/pricing deo je skraćen iznad — po potrebi možeš vratiti sve kako je bilo;
    # za funkcionalnost auth-a nije bitno)
    st_html(LANDING, height=1400, width=1280, scrolling=True)

# ------------ AUTH page (Kendo-like) ------------
def render_auth(mode="login"):
    mode = (mode or "login").lower()
    title = "Login to MindMate" if mode=="login" else "Create your account"
    cta   = "Sign In" if mode=="login" else "Create Account"
    swap_txt = "Don't have an account? " if mode=="login" else "Already have an account? "
    swap_link= "<a href='?auth=signup'>Sign up</a>" if mode=="login" else "<a href='?auth=login'>Log in</a>"

    # kartica + brand pozadina
    html = f"""
<!DOCTYPE html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
:root{{--bg:#0B0D12;--ink:#E8EAEE;--mut:#9AA3B2;--ring:rgba(255,255,255,.10);--g1:#7C5CFF;--g2:#4EA3FF}}
body{{margin:0;background:radial-gradient(1200px 600px at 70% 20%, rgba(124,92,255,.15), transparent 60%),
                 radial-gradient(1000px 520px at 80% 60%, rgba(78,163,255,.10), transparent 60%), #0B0D12; color:var(--ink);
     font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
.wrap{{max-width:980px;margin:4.5rem auto;padding:0 16px;display:grid;grid-template-columns:1fr 1fr;gap:22px}}
.card{{background:#0F1219;border:1px solid var(--ring);border-radius:18px;padding:24px}}
.brand{{background:linear-gradient(180deg,rgba(255,255,255,.05),rgba(255,255,255,.02));
        border:1px solid var(--ring);border-radius:18px;position:relative;overflow:hidden}}
.brand:before{{content:"";position:absolute;inset:-20% -20% auto -20%;height:240px;
  background:radial-gradient(260px 120px at 20% 60%, rgba(255,255,255,.06), transparent 65%),
             radial-gradient(200px 100px at 60% 40%, rgba(255,255,255,.05), transparent 60%),
             radial-gradient(220px 110px at 85% 70%, rgba(255,255,255,.04), transparent 65%);
  filter:blur(12px);opacity:.6}}
.logo{{display:flex;align-items:center;gap:10px;margin-bottom:8px}}
.dot{{width:12px;height:12px;border-radius:50%;background:linear-gradient(90deg,var(--g1),var(--g2));
      box-shadow:0 0 12px rgba(124,92,255,.7)}}
.h{{font-weight:900}}
label{{display:block;font-size:13px;color:#C7CEDA;margin:8px 0 6px}}
input[type=email]{{width:100%;padding:12px 14px;border-radius:12px;border:1px solid var(--ring);background:#0B0D12;color:var(--ink)}}
.btn{{width:100%;margin-top:14px;padding:12px 16px;border-radius:12px;font-weight:900;border:1px solid var(--ring);cursor:pointer}}
.primary{{background:linear-gradient(90deg,var(--g1),var(--g2));color:#0B0D12}}
.ghost{{background:rgba(255,255,255,.06);color:#E8EAEE}}
.sep{{display:flex;align-items:center;gap:10px;color:#9AA3B2;font-size:13px;margin:12px 0}}
.sep:before,.sep:after{{content:"";flex:1;height:1px;background:rgba(255,255,255,.08)}}
.small{{color:#9AA3B2;font-size:12px;margin-top:10px}}
@media (max-width:900px){{.wrap{{grid-template-columns:1fr}}}}
</style></head>
<body>
<div class="wrap">
  <div class="card">
    <div class="logo"><div class="dot"></div><div class="h">MindMate</div></div>
    <h2 style="margin:.2rem 0 0">{title}</h2>
    <p style="color:#9AA3B2;margin:.2rem 0 1rem">Please enter your email to continue.</p>
    <form onsubmit="return false;">
      <label>Email</label>
      <input id="mm_email" type="email" placeholder="your@email.com" required />
      <button class="btn primary" id="mm_submit">{cta}</button>
    </form>
    <div class="sep">Or continue with</div>
    <button class="btn ghost">Login with Google</button>
    <div class="small">{swap_txt}{swap_link}</div>
    <div class="small">By clicking continue, you agree to our <u>Terms</u> and <u>Privacy</u>.</div>
    <script>
      document.getElementById('mm_submit').addEventListener('click', ()=>{
        st.markdown("""
<script>
document.getElementById('loginBtn').addEventListener('click', function() {
    const v = document.getElementById('mm_email').value || '';
    alert("Email: " + v);
});
</script>
""", unsafe_allow_html=True)

        // trik: preusmeri nazad u Streamlit sa email-om kroz query
        const params=new URLSearchParams(window.location.search);
        params.delete('auth');
        params.set('login_email', v);
        window.location.search='?'+params.toString();
      });
    </script>
  </div>
  <div class="brand">
    <div style="padding:22px">
      <div style="font-weight:800;opacity:.9">“Kratki check-in nam je podigao fokus i smanjio brigu.”</div>
      <div style="color:#9AA3B2;margin-top:6px">— MindMate korisnik</div>
      <div style="height:420px;display:flex;align-items:center;justify-content:center;opacity:.9">
        <svg viewBox="0 0 200 200" width="220" height="220" aria-hidden="true">
          <defs>
            <linearGradient id="lg" x1="0" x2="1" y1="0" y2="1"><stop offset="0%" stop-color="#7C5CFF"/><stop offset="100%" stop-color="#4EA3FF"/></linearGradient>
          </defs>
          <circle cx="100" cy="100" r="80" fill="none" stroke="url(#lg)" stroke-width="14" opacity=".25"/>
          <circle cx="100" cy="100" r="64" fill="none" stroke="url(#lg)" stroke-width="10" opacity=".45"/>
          <circle cx="100" cy="100" r="48" fill="none" stroke="url(#lg)" stroke-width="8"  opacity=".75"/>
        </svg>
      </div>
    </div>
  </div>
</div>
</body></html>
"""
    st_html(html, height=760, scrolling=True)

# ------------ HOME / CHAT / CHECKIN / ANALYTICS ------------
def render_home():
    st.markdown("### Tvoja kontrolna tabla")
    if is_authed():
        st.caption(f"Prijavljen: **{st.session_state.user_email}**")
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

# ------------ ROUTER + auth prijem e-maila ------------
# preuzmi email iz query-a (dolazi iz JS-a sa auth stranice)
login_email = qp.get("login_email")
if login_email:
    set_user(login_email)
    # očisti query da ne ostane parametar
    st.query_params.clear()
    st.session_state.page="home"

page=st.session_state.page
if page=="landing": 
    render_landing()
elif page=="home": 
    render_home()
elif page=="chat": 
    render_chat()
elif page=="checkin": 
    if not is_authed():
        st.info("Za check-in se prvo prijavi.")
    render_checkin()
elif page=="analytics": 
    if not is_authed():
        st.info("Za detaljnu analitiku se prvo prijavi.")
    render_analytics()
elif page=="auth": 
    render_auth(st.session_state.get("auth_mode","login"))

st.markdown("<div style='text-align:center;color:#9AA3B2;margin-top:16px'>© 2025 MindMate. Nije medicinski alat. Za hitne slučajeve — 112.</div>", unsafe_allow_html=True)
