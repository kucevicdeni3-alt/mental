# app.py — MindMate • premium landing sa vidljivom “planet” glow pozadinom,
# smanjen VSL (tvoj link), Flower Mira maskota, hook, dodatne metrike/trust,
# Početna/Chat/Check-in/Analitika (Plotly) — sve responsive.

import os, json, requests, math
import streamlit as st
from datetime import datetime, date, timedelta
from streamlit.components.v1 import html as st_html

# ===== Plotly / Pandas (za Analitiku) =====
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

APP_TITLE = "MindMate"
DB_PATH   = os.environ.get("MINDMATE_DB", "mindmate_db.json")  # JSON datoteka

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

# ---------- Globalni stil okvira (responsive padding) ----------
st.markdown("""
<style>
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

# ---------- JSON “baza” ----------
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

# --------- Metričke pomoćne funkcije ---------
def compute_metrics():
    db = _get_db()
    uids = set([r.get("uid","") for r in db["checkins"]] + [r.get("uid","") for r in db["chat_events"]])
    uids.discard("")
    users = len(uids) or 1
    sessions = sum(1 for r in db["chat_events"] if r.get("role")=="user")

    # Zadovoljstvo iz poslednjih 30 dana (proxy iz checkin total skora)
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

    # Dodatne metrike (fallback vrednosti + lagani heuristike)
    avg_minutes = max(4, min(11, 4 + sessions//12))   # prosečno trajanje angažmana
    streaks     = max(1, min(14, len(recent)//3))     # prosečan streak u danima
    retention   = min(99, 60 + (len(recent)//5))      # mesečni retention %
    nps         = min(90, 60 + (sat//2))              # aproksimacija NPS iz satisfakcije

    return users, sessions, sat, avg_minutes, streaks, retention, nps

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

def current_month_progress():
    db = _get_db()
    today=date.today(); start=today.replace(day=1).isoformat()
    count=len([r for r in db["checkins"] if (r.get("date") or "")>=start]); goal=20
    pct=min(100,int(100*count/max(goal,1)))
    return pct, count, goal

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

# ---------- Router state ----------
if "page" not in st.session_state: st.session_state.page="landing"
if "chat_log" not in st.session_state: st.session_state.chat_log=[]
def goto(p): st.session_state.page=p; safe_rerun()

# ---------- NAVBAR ----------
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

# ---------- LANDING (hook + Flower Mira + vidljiva planeta + smanjen VSL + trust) ----------
# YouTube VSL: https://youtu.be/1qK0c9J_h10
LANDING_TEMPLATE = """
<!DOCTYPE html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
<style>
:root{
  --bg:#0B0D12; --panel:#11141C; --text:#E8EAEE; --mute:#9AA3B2;
  --g1:#7C5CFF; --g2:#4EA3FF; --g3:#9AD6FF;
  --fog1:rgba(124,92,255,.28); --fog2:rgba(78,163,255,.22);
  --ring:rgba(255,255,255,.10);
}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--text);
  font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,sans-serif; overflow-x:hidden}

/* background */
.bg-wrap{position:fixed;inset:0;z-index:0;background:
  radial-gradient(1400px 800px at 18% -10%, rgba(124,92,255,.26), transparent 60%),
  radial-gradient(1400px 800px at 82% 110%, rgba(78,163,255,.20), transparent 60%), var(--bg);}
.bg-noise{position:fixed;inset:-20%;z-index:1;pointer-events:none;opacity:.08;background-image:url('data:image/svg+xml;utf8,\
<svg xmlns=\\"http://www.w3.org/2000/svg\\" width=\\"1200\\" height=\\"1200\\"><filter id=\\"n\\"><feTurbulence type=\\"fractalNoise\\" baseFrequency=\\".9\\" numOctaves=\\"2\\" stitchTiles=\\"stitch\\"/></filter><rect width=\\"100%\\" height=\\"100%\\" filter=\\"url(%23n)\\" opacity=\\".55\\"/></svg>');}
.fog{position:fixed;inset:-10vh -10vw;z-index:2;pointer-events:none;filter:blur(48px) saturate(1.06);opacity:.40}
.fog.f1{background:radial-gradient(800px 520px at 14% 16%, var(--fog1), transparent 60%)} .fog.f2{background:radial-gradient(900px 600px at 86% 18%, var(--fog2), transparent 60%)} .fog.f3{background:radial-gradient(1000px 700px at 50% 80%, var(--fog1), transparent 60%)}
.petals{position:fixed;inset:0;z-index:3;pointer-events:none;overflow:hidden}

/* layout */
.section{width:min(1320px,95vw);margin:0 auto;padding:48px 0;position:relative;z-index:5}
.reveal{opacity:0;transform:translateY(18px);transition:all .7s ease}
.reveal.visible{opacity:1;transform:translateY(0)}

/* HERO HOOK + Flower Mira */
.hero-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:28px;align-items:center}
.hook{display:flex;flex-direction:column;gap:14px}
.hook-eyebrow{display:inline-block;padding:6px 10px;border-radius:999px;background:rgba(255,255,255,.06);border:1px solid var(--ring);font-size:12px;color:#C7CEDA}
.hook-title{font-size:clamp(28px,4.6vw,56px);line-height:1.05;margin:0}
.hook-sub{color:#9AA3B2;font-size:clamp(14px,2vw,18px);margin:0}
.hook-cta{display:flex;gap:10px;flex-wrap:wrap;margin-top:6px}
.btn{position:relative;overflow:hidden;display:inline-block;padding:14px 18px;border-radius:14px;font-weight:800;text-decoration:none;border:1px solid var(--ring);cursor:pointer; transition:transform .15s ease}
.btn:hover{transform:translateY(-1px) scale(1.03)}
.btn-primary{color:#0B0D12;background:linear-gradient(90deg,#7C5CFF,#4EA3FF)} .btn-ghost{color:#E8EAEE;background:rgba(255,255,255,.06)}

.mira-wrap{position:relative}
#flowerMira{width:100%;max-width:420px;margin-inline:auto;display:block;filter:drop-shadow(0 18px 48px rgba(124,92,255,.35))}
#flowerMira .petal{transform-origin:50% 50%;animation:petalSway 5.5s ease-in-out infinite}
#flowerMira .centerPulse{animation:centerPulse 4s ease-in-out infinite}
@keyframes petalSway{ 0%{transform:rotate(0deg)} 50%{transform:rotate(2deg)} 100%{transform:rotate(0deg)}}
@keyframes centerPulse{ 0%,100%{opacity:.9} 50%{opacity:1}}

@media (max-width: 980px){ .hero-grid{grid-template-columns:1fr} .mira-wrap{order:-1} }

/* VSL + PLANET (vidljiv, pojačan) */
.vsl-area{position:relative;margin-top:18px}
.orb-wrap{position:relative; height:160px}
.orb{
  position:absolute; inset: -240px 0 0 0; margin:auto;
  width:min(1100px,92vw); height:min(1100px,92vw);
  /* jači glow slojevi + prsten — VISIBILE */
  background:
    radial-gradient(60% 55% at 50% 40%, rgba(124,92,255,.65), transparent 62%),
    radial-gradient(58% 52% at 50% 45%, rgba(78,163,255,.58), transparent 66%),
    radial-gradient(46% 40% at 50% 52%, rgba(154,214,255,.26), transparent 70%);
  filter: blur(36px) saturate(1.08);
  opacity:.92; transform:translateZ(0); will-change:transform; z-index:0;
}
.orb:after{
  content:""; position:absolute; inset:0; border-radius:50%;
  background: conic-gradient(from 210deg at 50% 50%, rgba(124,92,255,.0), rgba(124,92,255,.45) 18%, rgba(78,163,255,.45) 55%, rgba(124,92,255,.0) 80%);
  filter:blur(18px); opacity:.95; pointer-events:none;
}
.vsl-shell{
  max-width:1100px;margin:0 auto 8px;padding:10px;
  background:rgba(255,255,255,.05);border:1px solid var(--ring);border-radius:18px;
  box-shadow:0 32px 90px rgba(0,0,0,.65); position:relative; z-index:1;
  transition:transform .25s ease, box-shadow .25s ease
}
.vsl-shell:hover{transform:translateY(-2px) scale(1.01); box-shadow:0 36px 110px rgba(0,0,0,.7)}
/* SMANJENI video: 16/7 da ne zauzima previše */
.vsl-iframe{width:100%;aspect-ratio:16/7;height:auto;min-height:320px;border:0;border-radius:12px;background:#000}
@media (max-width: 920px){ .orb{inset:-180px 0 0 0} .vsl-iframe{min-height:220px;aspect-ratio:16/9} }

/* trust badges + metrics grid */
.trust{display:grid;grid-template-columns:repeat(12,1fr);gap:18px;margin-top:6px}
.badge{grid-column:span 3;padding:12px;border-radius:14px;background:rgba(255,255,255,.06);border:1px solid var(--ring);color:#C7CEDA;font-weight:700;text-align:center}
@media (max-width:920px){ .badge{grid-column:span 6} }

.kpis{display:grid;grid-template-columns:repeat(12,1fr);gap:18px}
.kpi{grid-column:span 3;background:rgba(17,20,28,.72);border:1px solid var(--ring);border-radius:18px;padding:18px;text-align:center; transition:transform .15s}
.kpi:hover{transform:translateY(-2px) scale(1.01)}
.kpi .num{font-size:clamp(22px,3.2vw,34px);font-weight:900;background:linear-gradient(90deg,#7C5CFF,#4EA3FF);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.kpi .label{color:#9AA3B2;margin-top:6px}

/* Mini demo graf (SVG) sa glow trail) */
.chart-wrap{background:#0F1219;border:1px solid var(--ring);border-radius:18px;padding:18px;box-shadow:0 14px 36px rgba(0,0,0,.28)}
.legend{display:flex;gap:14px;align-items:center;color:#C7CEDA;margin-bottom:8px}.dot{width:12px;height:12px;border-radius:50%}
.dot-prod{background:#7C5CFF}.dot-mood{background:#4EA3FF}

/* timeline / features / comparison */
.timeline{display:grid;grid-template-columns:repeat(12,1fr);gap:18px}
.ti{grid-column:span 3;background:#0F1219;border:1px solid var(--ring);border-radius:18px;padding:18px}
.features{display:grid;grid-template-columns:repeat(12,1fr);gap:18px}
.f-card{grid-column:span 4;background:#0F1219;border:1px solid var(--ring);border-radius:18px;padding:18px}
.f-title{font-weight:900;font-size:1.12rem;margin:6px 0}.f-text{color:#C7CEDA;margin:.2rem 0}

.compare{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.comp-card{background:#0F1219;border:1px solid var(--ring);border-radius:18px;padding:18px}
.li{display:flex;gap:8px;align-items:flex-start;color:#C7CEDA;margin:6px 0}
.mini-dot{width:8px;height:8px;border-radius:50%;background:linear-gradient(90deg,#7C5CFF,#4EA3FF);margin-top:7px}
@media (max-width:920px){ .compare{grid-template-columns:1fr} }

/* testimonials / faq / integrations */
.t-wrap{position:relative;overflow:hidden;border:1px solid var(--ring);background:#0F1219;border-radius:18px;padding:18px}
.t-rail{display:flex;gap:18px;transition:transform .5s ease}
.t-card{min-width:calc(33.33% - 12px);background:rgba(255,255,255,.04);border:1px solid var(--ring);border-radius:14px;padding:16px}
.t-name{font-weight:800;margin:.4rem 0}.t-role{color:#9AA3B2;font-size:.92rem;margin:0 0 .6rem 0}
.t-nav{position:absolute;top:50%;left:8px;right:8px;display:flex;justify-content:space-between;transform:translateY(-50%)}
.t-btn{padding:8px 10px;border-radius:12px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);cursor:pointer}

.integrations{display:grid;grid-template-columns:repeat(12,1fr);gap:18px}
.int-card{grid-column:span 3;background:#0F1219;border:1px solid var(--ring);border-radius:18px;padding:18px;text-align:center;color:#C7CEDA}
@media (max-width:920px){ .int-card{grid-column:span 6} }
.faq{border:1px solid var(--ring);border-radius:18px;background:#0F1219}
.faq-item{border-top:1px solid rgba(255,255,255,.06)}
.faq-item:first-child{border-top:none}
.faq-q{width:100%;text-align:left;background:none;border:none;color:#E8EAEE;font-weight:800;padding:16px;cursor:pointer}
.faq-a{max-height:0;overflow:hidden;color:#C7CEDA;padding:0 16px;transition:max-height .35s ease,padding .35s ease}

/* Sticky CTA */
.sticky-cta{position:fixed;left:0;right:0;bottom:16px;z-index:50;display:flex;justify-content:center;pointer-events:none;transform:translateY(110%);opacity:0;transition:transform .4s,opacity .4s}
.sticky-cta.show{transform:translateY(0);opacity:1}
.sticky-cta .inner{pointer-events:auto;width:min(1100px,92vw);background:rgba(20,24,33,.7);border:1px solid rgba(255,255,255,.09);backdrop-filter:blur(14px) saturate(1.05);box-shadow:0 24px 60px rgba(0,0,0,.45);border-radius:18px;padding:16px 18px;display:grid;grid-template-columns:1fr auto;gap:16px;align-items:center}
.sticky-cta .actions{display:flex;gap:10px}.sticky-cta .btn{padding:10px 14px;border-radius:12px;font-weight:800;text-decoration:none;border:1px solid var(--ring)}

.cursor-flower{position:fixed;top:0;left:0;width:14px;height:14px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#7C5CFF,#4EA3FF);box-shadow:0 0 12px rgba(124,92,255,.7); pointer-events:none; transform:translate(-50%,-50%) scale(.95);opacity:.28; transition:opacity .15s ease, transform .1s ease}
.cursor-boost{opacity:1!important; transform:translate(-50%,-50%) scale(1.08)!important;}
</style>
</head>
<body>
<div class="cursor-flower" id="cursorFlower"></div>
<div class="bg-wrap"></div><div class="bg-noise"></div>
<div class="fog f1" id="fog1"></div><div class="fog f2" id="fog2"></div><div class="fog f3" id="fog3"></div>
<svg class="petals" id="petals" xmlns="http://www.w3.org/2000/svg"></svg>

<!-- HERO HOOK + MIRA -->
<section class="section reveal">
  <div class="hero-grid">
    <div class="hook">
      <div class="hook-eyebrow">MindMate • Mentalni wellness</div>
      <h1 class="hook-title">Preusmeri 80% briga u konkretne korake — <br/> za 5 minuta dnevno.</h1>
      <p class="hook-sub">Kratki check-in, mikro-navike i empatičan razgovor. Jasni trendovi, tvoj ritam.</p>
      <div class="hook-cta">
        <a class="btn btn-primary fx-ripple" href="?home">Kreni odmah</a>
        <a class="btn btn-ghost fx-ripple" href="?home">Pogledaj kako radi</a>
      </div>
    </div>
    <div class="mira-wrap">
      <!-- Flower Mira (SVG) -->
      <svg id="flowerMira" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Flower Mira">
        <defs>
          <linearGradient id="petalG" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stop-color="#7C5CFF"/><stop offset="100%" stop-color="#4EA3FF"/>
          </linearGradient>
          <radialGradient id="coreG" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="#FFF7" /><stop offset="100%" stop-color="#7C5CFF" />
          </radialGradient>
        </defs>
        <g class="petal" opacity="0.95">
          <path d="M100,20 C85,45 85,75 100,95 C115,75 115,45 100,20 Z" fill="url(#petalG)"/>
          <path d="M55,40 C40,70 52,95 95,105 C78,84 72,60 55,40 Z" fill="url(#petalG)" opacity="0.75"/>
          <path d="M145,40 C160,70 148,95 105,105 C122,84 128,60 145,40 Z" fill="url(#petalG)" opacity="0.75"/>
        </g>
        <circle class="centerPulse" cx="100" cy="110" r="12" fill="url(#coreG)"/>
        <!-- blagi osmeh -->
        <path d="M88 128 Q100 136 112 128" stroke="#E8EAEE" stroke-width="3" fill="none" stroke-linecap="round" opacity="0.85"/>
        <circle cx="88" cy="122" r="2.8" fill="#E8EAEE" opacity="0.9"/>
        <circle cx="112" cy="122" r="2.8" fill="#E8EAEE" opacity="0.9"/>
      </svg>
    </div>
  </div>
</section>

<!-- VSL + PLANET GLOW (VIDLJIVO) -->
<section class="section reveal vsl-area">
  <div class="orb-wrap"><div class="orb" id="orb"></div></div>
  <div class="vsl-shell">
    <iframe class="vsl-iframe" src="https://www.youtube.com/embed/1qK0c9J_h10?rel=0&modestbranding=1"
            title="MindMate VSL" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>
  </div>
  <div class="trust">
    <div class="badge">✔️ 1000+ dnevnih check-inova</div>
    <div class="badge">✔️ AI na srpskom</div>
    <div class="badge">✔️ CBT/ACT/Mindfulness osnova</div>
    <div class="badge">✔️ Privatnost & sigurnost</div>
  </div>
</section>

<!-- KPI blok (dinamički brojevi) -->
<section class="section reveal">
  <div class="kpis" id="kpiBlock">
    <div class="kpi"><div class="num" data-target="__USERS__">0</div><div class="label">Aktivnih korisnika</div></div>
    <div class="kpi"><div class="num" data-target="__SESS__">0</div><div class="label">Ukupno sesija</div></div>
    <div class="kpi"><div class="num" data-target="__SAT__">0</div><div class="label">Zadovoljstvo (%)</div></div>
    <div class="kpi"><div class="num" data-target="__RET__">0</div><div class="label">Mesečna zadržanost (%)</div></div>
  </div>
</section>

<!-- Mini demo graf -->
<section class="section reveal">
  <div class="chart-wrap">
    <div style="font-weight:900;margin:0 0 10px 0">Produktivnost & Raspoloženje (poslednje sesije)</div>
    <div class="legend"><div class="dot dot-prod"></div><div>Produktivnost</div><div class="dot dot-mood" style="margin-left:12px"></div><div>Raspoloženje</div></div>
    <svg id="mmChart" viewBox="0 0 1100 360" width="100%" height="360" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="gProd" x1="0" x2="1" y1="0" y2="0"><stop offset="0%" stop-color="#7C5CFF"/><stop offset="100%" stop-color="#4EA3FF"/></linearGradient>
        <linearGradient id="gMood" x1="0" x2="1" y1="0" y2="0"><stop offset="0%" stop-color="#4EA3FF"/><stop offset="100%" stop-color="#7C5CFF"/></linearGradient>
        <filter id="softGlow"><feGaussianBlur in="SourceGraphic" stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      <g id="grid"></g>
      <path id="prodGlow" fill="none" stroke="#7C5CFF" stroke-opacity=".18" stroke-width="10" stroke-linecap="round" filter="url(#softGlow)"/>
      <path id="moodGlow" fill="none" stroke="#4EA3FF" stroke-opacity=".18" stroke-width="10" stroke-linecap="round" filter="url(#softGlow)"/>
      <path id="prodPath" fill="none" stroke="url(#gProd)" stroke-width="3" stroke-linecap="round"/>
      <path id="moodPath" fill="none" stroke="url(#gMood)" stroke-width="3" stroke-linecap="round"/>
      <g id="xlabels"></g>
    </svg>
  </div>
</section>

<!-- Kako radi -->
<section class="section reveal">
  <h2 style="margin:0 0 12px 0">Kako radi MindMate?</h2>
  <div class="timeline">
    <div class="ti"><h4>1) Kratak check-in</h4><p>2 pitanja + beleška. Potpuno bez “frke”.</p></div>
    <div class="ti"><h4>2) Mikro-navike</h4><p>5–10 minuta zadaci koji grade momentum.</p></div>
    <div class="ti"><h4>3) Razgovor</h4><p>Empatičan chat u tvom tonu — motivacija bez pritiska.</p></div>
    <div class="ti"><h4>4) Trendovi</h4><p>Jasni grafovi: raspoloženje, fokus, obrasci.</p></div>
  </div>
</section>

<!-- Zasniva se na nauci -->
<section class="section reveal">
  <h2 style="margin:0 0 12px 0">Zasniva se na nauci</h2>
  <div class="features">
    <div class="f-card"><div class="f-title">CBT</div><p class="f-text">Promena obrasca misli kroz male eksperimente.</p></div>
    <div class="f-card"><div class="f-title">ACT</div><p class="f-text">Prihvatanje, vrednosti i akcije uprkos nelagodi.</p></div>
    <div class="f-card"><div class="f-title">Mindfulness</div><p class="f-text">Povratak u telo i trenutak; fokus i smirenost.</p></div>
  </div>
</section>

<!-- Poređenje -->
<section class="section reveal">
  <h2 style="margin:0 0 12px 0">Zašto MindMate?</h2>
  <div class="compare">
    <div class="comp-card">
      <h3>Bez plana</h3>
      <div class="li"><div class="mini-dot"></div><div>Nasumične navike, bez praćenja.</div></div>
      <div class="li"><div class="mini-dot"></div><div>Preplavljenost, odustajanje posle par dana.</div></div>
      <div class="li"><div class="mini-dot"></div><div>Bez jasnih trendova i povratne informacije.</div></div>
    </div>
    <div class="comp-card">
      <h3>Sa MindMate</h3>
      <div class="li"><div class="mini-dot"></div><div>Check-in od 2 pitanja + mikro-koraci (5–10 min).</div></div>
      <div class="li"><div class="mini-dot"></div><div>Empatičan razgovor u tvom tonu.</div></div>
      <div class="li"><div class="mini-dot"></div><div>Grafovi napretka i jasni obrasci.</div></div>
    </div>
  </div>
</section>

<!-- Integracije / Trust -->
<section class="section reveal">
  <h2 style="margin:0 0 12px 0">Privatnost & Integracije</h2>
  <div class="integrations">
    <div class="int-card">🔒 Lokalno čuvanje podataka (MVP)</div>
    <div class="int-card">🧠 AI na srpskom</div>
    <div class="int-card">📊 Analitika napretka</div>
    <div class="int-card">📱 Radi na telefonu i računaru</div>
  </div>
</section>

<!-- Testimonials -->
<section class="section reveal">
  <div class="t-wrap">
    <div class="t-rail" id="tRail">
      <div class="t-card"><div class="t-name">Mila</div><div class="t-role">28 • Beograd</div><div>“Check-in me drži u ritmu. 5 minuta i osećam pomak.”</div></div>
      <div class="t-card"><div class="t-name">Nikola</div><div class="t-role">31 • Novi Sad</div><div>“Sviđa mi se što je sve na srpskom i u mom fazonu.”</div></div>
      <div class="t-card"><div class="t-name">Sara</div><div class="t-role">24 • Niš</div><div>“Grafovi mi jasno pokažu kada padam i zašto.”</div></div>
      <div class="t-card"><div class="t-name">Vuk</div><div class="t-role">35 • Kragujevac</div><div>“Nije terapija, ali je odličan dnevni alat.”</div></div>
      <div class="t-card"><div class="t-name">Ana</div><div class="t-role">29 • Subotica</div><div>“Mini-navike su pogodile — taman koliko mogu.”</div></div>
    </div>
    <div class="t-nav"><div class="t-btn" id="tPrev">◀</div><div class="t-btn" id="tNext">▶</div></div>
  </div>
</section>

<!-- FAQ -->
<section class="section reveal">
  <div class="faq" id="faq">
    <div class="faq-item"><button class="faq-q">Da li je MindMate zamena za terapiju?</button>
      <div class="faq-a">Ne. Nije medicinski alat. Ako si u riziku — pozovi 112 i potraži stručnu pomoć.</div></div>
    <div class="faq-item"><button class="faq-q">Koliko vremena mi treba dnevno?</button>
      <div class="faq-a">Obično 3–5 minuta. Dovoljno da zadržiš momentum bez preplavljivanja.</div></div>
    <div class="faq-item"><button class="faq-q">Kako čuvate privatnost?</button>
      <div class="faq-a">Podaci su lokalno u okviru app-a za MVP; bez deljenja. Uvek možeš obrisati istoriju.</div></div>
  </div>
</section>

<div class="sticky-cta" id="stickyCta">
  <div class="inner">
    <div class="copy">
      <h3>Tvoj bolji dan počinje sada</h3>
      <p>Uđi u ritam: check-in, mikro-navike, jasni trendovi.</p>
    </div>
    <div class="actions">
      <a class="btn btn-primary fx-ripple" href="?home">Isprobaj besplatno</a>
      <a class="btn btn-ghost fx-ripple" href="?home">Promeni sebe</a>
    </div>
  </div>
</div>

<div style="text-align:center;color:#9AA3B2;margin-top:22px">© 2025 MindMate. Nije medicinski alat. Za hitne slučajeve — 112.</div>

<script>
// ===== Cursor + ripple =====
const flower=document.getElementById('cursorFlower');
document.addEventListener('mousemove',(e)=>{ flower.style.left=e.clientX+'px'; flower.style.top=e.clientY+'px'; });
document.querySelectorAll('a,.btn').forEach(el=>{
  el.addEventListener('mouseenter',()=>flower.classList.add('cursor-boost'));
  el.addEventListener('mouseleave',()=>flower.classList.remove('cursor-boost'));
});
document.addEventListener('click', function(e){
  const b=e.target.closest('.fx-ripple'); if(!b) return;
  const r=document.createElement('span'); r.className='ink';
  const rect=b.getBoundingClientRect(); const size=Math.max(rect.width, rect.height);
  r.style.position='absolute'; r.style.borderRadius='50%'; r.style.background='rgba(255,255,255,.45)';
  r.style.width=r.style.height=size+'px'; r.style.left=(e.clientX-rect.left-size/2)+'px'; r.style.top=(e.clientY-rect.top-size/2)+'px';
  r.style.transform='scale(0)'; r.style.animation='ripple .6s linear';
  b.appendChild(r); setTimeout(()=>r.remove(),600);
}, {passive:true});

// ===== Reveal on scroll =====
const io=new IntersectionObserver(es=>es.forEach(x=>{if(x.isIntersecting)x.target.classList.add('visible')}),{threshold:.18});
document.querySelectorAll('.reveal').forEach(el=>io.observe(el));

// ===== Global falling petals (lagano) =====
const svgNS="http://www.w3.org/2000/svg"; const petals=document.getElementById('petals');
function addPetal(scale, opacity, durMin, durMax){
  const s=(12+Math.random()*22)*scale;
  const g=document.createElementNS(svgNS,'g');
  const p=document.createElementNS(svgNS,'path');
  p.setAttribute('d','M10,0 C22,8 22,32 10,42 C-2,32 -2,8 10,0 Z');
  if(!document.getElementById('petalGrad')){
    const defs=document.createElementNS(svgNS,'defs');
    const lg=document.createElementNS(svgNS,'linearGradient'); lg.id='petalGrad'; lg.setAttribute('x1','0'); lg.setAttribute('y1','0'); lg.setAttribute('x2','1'); lg.setAttribute('y2','1');
    const s1=document.createElementNS(svgNS,'stop'); s1.setAttribute('offset','0%'); s1.setAttribute('stop-color','#7C5CFF');
    const s2=document.createElementNS(svgNS,'stop'); s2.setAttribute('offset','100%'); s2.setAttribute('stop-color','#4EA3FF');
    lg.appendChild(s1); lg.appendChild(s2); defs.appendChild(lg); petals.appendChild(defs);
  }
  p.setAttribute('fill','url(#petalGrad)'); p.setAttribute('opacity',opacity); g.appendChild(p);
  const x = Math.random()*window.innerWidth; const rot = (Math.random()*60 - 30);
  g.setAttribute('transform',`translate(${x},-30) scale(${s/42}) rotate(${rot})`); petals.appendChild(g);
  const drift = (-60 + Math.random()*120); const dur = durMin + Math.random()*(durMax-durMin);
  const kyframes = [{transform:`translate(${x}px,-30px) scale(${s/42}) rotate(${rot}deg)`},
                    {transform:`translate(${x+drift}px, ${window.innerHeight+60}px) scale(${s/42}) rotate(${rot+360}deg)`}];
  g.animate(kyframes,{duration:dur,easing:'linear'}); setTimeout(()=>g.remove(), dur);
}
for(let i=0;i<20;i++) addPetal(1, .70, 6500, 9500);
setInterval(()=>addPetal(1.0, .70, 7000, 11000), 900);

// ===== KPI count-up =====
function countUp(el){const t=parseInt(el.getAttribute('data-target'))||0,d=1400,s=performance.now();
  function tick(now){const p=Math.min((now-s)/d,1);el.textContent=Math.floor(t*(.1+.9*p)).toLocaleString(); if(p<1) requestAnimationFrame(tick)}
  requestAnimationFrame(tick)}
const kio=new IntersectionObserver(e=>{e.forEach(x=>{if(x.isIntersecting){x.target.querySelectorAll('.num').forEach(countUp);kio.unobserve(x.target)}})},{threshold:.35});
document.querySelectorAll('#kpiBlock').forEach(el=>kio.observe(el));

// ===== Mini demo graf (SVG path + labels + glow trails) =====
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
const prodGlow=document.getElementById('prodGlow'), moodGlow=document.getElementById('moodGlow');
const d1=path(prod), d2=path(mood);
prodGlow.setAttribute("d",d1); moodGlow.setAttribute("d",d2);
prodPath.setAttribute("d",d1); moodPath.setAttribute("d",d2);
function strokeAnim(p,d=1600){const L=p.getTotalLength();p.style.strokeDasharray=L;p.style.strokeDashoffset=L;p.getBoundingClientRect();p.style.transition=`stroke-dashoffset ${d}ms ease`;p.style.strokeDashoffset="0"}
const cio=new IntersectionObserver(e=>{e.forEach(x=>{if(x.isIntersecting){strokeAnim(prodPath,1400);setTimeout(()=>strokeAnim(moodPath,1600),200);cio.unobserve(svg)}})},{threshold:.3});
cio.observe(svg);

// ===== Testimonials carousel =====
(function(){const rail=document.getElementById('tRail');if(!rail) return; let i=0;
  const cards=rail.children.length; function go(d){i=(i+d+cards)%cards; rail.style.transform=`translateX(${-i*(rail.children[0].offsetWidth+18)}px)`;}
  document.getElementById('tPrev').onclick=()=>go(-1); document.getElementById('tNext').onclick=()=>go(1);
})();

// ===== FAQ toggle =====
document.querySelectorAll('.faq-q').forEach(q=>q.addEventListener('click',()=>{
  const a=q.parentElement.querySelector('.faq-a'); const open=a.style.maxHeight && a.style.maxHeight!=='0px';
  a.style.maxHeight=open?'0':a.scrollHeight+'px'; a.style.padding=open?'0 16px':'12px 16px';
}));

// ===== Sticky CTA =====
const sticky=document.getElementById('stickyCta'); let shown=false;
function chk(){const st=scrollY||0, dh=Math.max(document.body.scrollHeight,document.documentElement.scrollHeight), wh=innerHeight, ratio=(st+wh)/dh; const s=ratio>0.72;
  if(s!==shown){shown=s; sticky.classList.toggle('show',s)}}
addEventListener('scroll',chk,{passive:true}); addEventListener('resize',chk,{passive:true}); setTimeout(chk,400);
</script>
</body></html>
"""

def render_landing():
    users, sessions, sat, avg_minutes, streaks, retention, nps = compute_metrics()
    labels, prod, mood = compute_trend_series()
    quotes = [
        "Mali koraci, veliki pomaci.",
        "Danas bolje nego juče, sutra bolje nego danas.",
        "Ne moraš sve — dovoljno je malo, ali svaki dan.",
        "Disanje. Fokus. Jedan korak napred.",
        "Kad ne ide — budi blag/a prema sebi."
    ]
    html = (LANDING_TEMPLATE
            .replace("__SESS__", str(max(sessions,0)))
            .replace("__USERS__", str(max(users,1)))
            .replace("__SAT__", str(max(min(sat,100),0)))
            .replace("__RET__", str(max(min(retention,100),0)))
            .replace("__X_LABELS__", json.dumps(labels))
            .replace("__P_SERIES__", json.dumps(prod))
            .replace("__M_SERIES__", json.dumps(mood))
            )
    # dovoljno visoko da planeta + sekcije stanu bez seckanja
    st_html(html, height=5600, width=1280, scrolling=True)

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

st.markdown("<div style='text-align:center;color:#9AA3B2;margin-top:18px'>© 2025 MindMate. Nije medicinski alat. Za hitne slučajeve — 112.</div>", unsafe_allow_html=True)
