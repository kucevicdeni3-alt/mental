# app.py — MindMate: Landing (sa grafovima/FAQ/PRICING), Login/Register, Guarded pages — CLEAN + Kendo login UI
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
            json.dump({"checkins": [], "chat_events": [], "users":[]}, f)
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {"checkins": [], "chat_events": [], "users":[]}
        data.setdefault("checkins", [])
        data.setdefault("chat_events", [])
        data.setdefault("users", [])
        return data
    except Exception:
        return {"checkins": [], "chat_events": [], "users":[]}

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

# ---------- Auth helpers (demo) ----------
def register_user(email, password):
    db = _get_db()
    if any(u.get("email","").lower()==email.lower() for u in db["users"]):
        return False, "Nalog već postoji."
    db["users"].append({"email":email, "password":password, "created": datetime.utcnow().isoformat()})
    _persist_db()
    return True, "Registracija uspešna."

def authenticate(email, password):
    db = _get_db()
    u = next((u for u in db["users"] if u.get("email","").lower()==email.lower()), None)
    if not u: return False
    return u.get("password")==password

def require_auth_guard(target_page_key:str):
    if not st.session_state.get("auth_ok", False):
        st.session_state.page = "login"
        safe_rerun()
        return False
    return True

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

# ---------- Session defaults ----------
if "page" not in st.session_state: st.session_state.page="landing"
if "chat_log" not in st.session_state: st.session_state.chat_log=[]
if "auth_ok" not in st.session_state: st.session_state.auth_ok=False
if "auth_email" not in st.session_state: st.session_state.auth_email=""

def goto(p): st.session_state.page=p; safe_rerun()

# ---------- NAV (Apple-style, veća opacity) ----------
def render_navbar():
    auth = st.session_state.get("auth_ok", False)
    cta_label = "Izloguj se" if auth else "Prijava"
    cta_href  = "?logout=1" if auth else "?login"

    navbar_html = """
<style>
/* Wrapper */
.mm-nav{position:sticky;top:0;inset-inline:0;z-index:1000;}
/* Bar */
.mm-bar{
  background: rgba(16,20,27,.88);
  -webkit-backdrop-filter: saturate(160%) blur(10px);
  backdrop-filter: saturate(160%) blur(10px);
  border-bottom:1px solid var(--ring);
  transition: background .22s cubic-bezier(.22,.95,.57,1.01), box-shadow .22s, border-color .22s;
}
.mm-bar.scrolled{ background: var(--bg); box-shadow: 0 10px 30px rgba(0,0,0,.25); border-bottom-color: transparent; }
.mm-inner{max-width:1180px;margin:0 auto;padding:10px 8px;display:flex;align-items:center;justify-content:space-between;gap:.75rem}
/* Brand */
.mm-brand{display:flex;align-items:center;gap:10px;color:var(--ink);font-weight:900;text-decoration:none}
.mm-dot{width:10px;height:10px;border-radius:50%;
  background:linear-gradient(90deg,var(--g1),var(--g2));
  box-shadow:0 0 12px color-mix(in oklab, var(--g1) 60%, transparent);
}
/* Links row */
.mm-menu{display:flex;align-items:center;gap:10px}
.mm-links{position:relative;display:flex;align-items:center;gap:4px;padding:4px;border-radius:999px}
.mm-link{
  --padx:.9rem;
  display:inline-flex;align-items:center;justify-content:center;height:40px;
  padding:0 var(--padx);border-radius:999px;text-decoration:none;
  color:var(--mut);font-weight:800;transition:color .16s, transform .16s;
}
.mm-link:hover{ color:var(--ink); transform:translateY(-1px); }
/* Sliding indicator “pill” */
.mm-indicator{
  position:absolute; left:0; bottom:3px; height:34px; border-radius:999px;
  background:rgba(255,255,255,.06); border:1px solid var(--ring);
  transition: width .22s cubic-bezier(.22,.95,.57,1.01), transform .22s cubic-bezier(.22,.95,.57,1.01), opacity .22s;
  transform: translateX(0); opacity:0; z-index:-1;
}
.mm-link.is-active ~ .mm-indicator{ opacity:1; }
/* CTA */
.mm-cta{
  display:inline-flex;align-items:center;justify-content:center;height:40px;padding:0 1rem;
  border-radius:999px;text-decoration:none;font-weight:800;color:#0B0D12;
  background:linear-gradient(90deg,var(--g1),var(--g2)); border:1px solid var(--ring);
  box-shadow:0 8px 20px rgba(0,0,0,.25); transition:transform .16s, box-shadow .16s;
}
.mm-cta:hover{ transform:translateY(-1px) scale(1.03); }
/* Hamburger (mobile) */
.mm-toggle{
  --bar:2px; display:none; position:relative; width:38px; height:38px; border:0; background:transparent; border-radius:12px; cursor:pointer;
}
.mm-toggle span{ position:absolute; left:8px; right:8px; height:var(--bar); background:var(--ink);
  border-radius:999px; transition: transform .22s cubic-bezier(.22,.95,.57,1.01), opacity .22s; }
.mm-toggle span:nth-child(1){ top:11px; }
.mm-toggle span:nth-child(2){ top:18px; }
.mm-toggle span:nth-child(3){ top:25px; }
@media (max-width: 900px){
  .mm-toggle{ display:block; }
  .mm-menu{
    position:fixed; left:0; right:0; top:62px;
    background:var(--bg);
    border-bottom:1px solid var(--ring);
    transform:translateY(-8px); opacity:0; pointer-events:none;
    flex-direction:column; align-items:stretch; gap:.5rem; padding:.75rem 1rem 1rem;
    transition: opacity .22s, transform .22s;
  }
  .mm-menu.open{ transform:translateY(0); opacity:1; pointer-events:auto; }
  .mm-links{ justify-content:center; }
  .mm-link{ height:44px; }
  .mm-cta{ height:44px; }
}
@media (prefers-reduced-motion: reduce){
  .mm-bar, .mm-bar *{ transition:none !important; animation:none !important; }
}
</style>
<div class="mm-nav">
  <div class="mm-bar" id="mmBar">
    <div class="mm-inner">
      <a class="mm-brand" href="?landing"><div class="mm-dot"></div><div>MindMate</div></a>
      <button class="mm-toggle" id="mmToggle" aria-label="Open menu" aria-expanded="false" aria-controls="mmMenu">
        <span></span><span></span><span></span>
      </button>
      <nav class="mm-menu" id="mmMenu" aria-label="Glavna navigacija">
        <div class="mm-links" id="mmLinks">
          <a class="mm-link" href="?landing" data-page="landing">Welcome</a>
          <a class="mm-link" href="?home" data-page="home">Početna</a>
          <a class="mm-link" href="?chat" data-page="chat">Chat</a>
          <a class="mm-link" href="?checkin" data-page="checkin">Check-in</a>
          <a class="mm-link" href="?analytics" data-page="analytics">Analitika</a>
          <span class="mm-indicator" id="mmIndicator" aria-hidden="true"></span>
        </div>
        <a class="mm-cta" href="__CTA_HREF__">__CTA_LABEL__</a>
      </nav>
    </div>
  </div>
</div>
<script>
(function(){
  const bar = document.getElementById('mmBar');
  const toggle = document.getElementById('mmToggle');
  const menu = document.getElementById('mmMenu');
  const linksWrap = document.getElementById('mmLinks');
  const indicator = document.getElementById('mmIndicator');
  const links = [...document.querySelectorAll('.mm-link')];
  const onScroll = () => bar.classList.toggle('scrolled', window.scrollY > 8);
  onScroll(); addEventListener('scroll', onScroll, {passive:true});
  const qs = new URLSearchParams(location.search);
  const key = ['landing','home','chat','checkin','analytics','login','register'].find(k => qs.has(k)) || 'landing';
  const active = links.find(a => a.dataset.page === key) || links[0];
  active.classList.add('is-active');
  function moveIndicator(el){
    if(!el || !indicator) return;
    const r = el.getBoundingClientRect();
    const rw = linksWrap.getBoundingClientRect();
    indicator.style.opacity = '1';
    indicator.style.width = r.width + 'px';
    indicator.style.transform = `translateX(${r.left - rw.left}px)`;
  }
  moveIndicator(active);
  links.forEach(a=>{
    a.addEventListener('mouseenter', ()=> moveIndicator(a));
    a.addEventListener('focus', ()=> moveIndicator(a));
    a.addEventListener('click', ()=>{
      links.forEach(l=>l.classList.remove('is-active'));
      a.classList.add('is-active'); moveIndicator(a);
      if(menu.classList.contains('open')) setMenu(false);
    });
  });
  linksWrap.addEventListener('mouseleave', ()=> moveIndicator(document.querySelector('.mm-link.is-active')));
  function setMenu(open){
    menu.classList.toggle('open', open);
    toggle.setAttribute('aria-expanded', open);
    const [a,b,c] = toggle.querySelectorAll('span');
    if(open){
      a.style.transform = 'translateY(7px) rotate(45deg)';
      b.style.opacity = '0';
      c.style.transform = 'translateY(-7px) rotate(-45deg)';
    }else{
      a.style.transform = ''; b.style.opacity = ''; c.style.transform = '';
    }
  }
  toggle?.addEventListener('click', ()=> setMenu(!menu.classList.contains('open')));
  menu?.addEventListener('click', e => { if(e.target.closest('a')) setMenu(false); });
  addEventListener('keydown', e => { if(e.key==='Escape' && menu.classList.contains('open')) setMenu(false); });
  let rAF=null; addEventListener('resize', ()=>{
    cancelAnimationFrame(rAF);
    rAF=requestAnimationFrame(()=>moveIndicator(document.querySelector('.mm-link.is-active')||active));
  });
})();
</script>
"""
    navbar_html = navbar_html.replace("__CTA_HREF__", cta_href).replace("__CTA_LABEL__", cta_label)
    st.markdown(navbar_html, unsafe_allow_html=True)

# ---------- Query params & logout handling ----------
qp = st.query_params
if "logout" in qp:
    st.session_state.auth_ok = False
    st.session_state.auth_email = ""
    st.session_state.page = "landing"
    st.query_params.clear()
    safe_rerun()

if   "landing"  in qp: st.session_state.page="landing"
elif "home"     in qp: st.session_state.page="home"
elif "chat"     in qp: st.session_state.page="chat"
elif "checkin"  in qp: st.session_state.page="checkin"
elif "analytics"in qp: st.session_state.page="analytics"
elif "login"    in qp: st.session_state.page="login"
elif "register" in qp: st.session_state.page="register"

# Render navbar
render_navbar()

# ---------- LANDING (cta → login) ----------
# (NE MENJAM – isti kao u tvom kodu, skraćen radi prostora)
LANDING = """<html>...SAV TVOJ LANDING KOD OVDE IZOSTAVLJEN RADI DUŽINE...
"""  # <-- ostavi tvoj originalni LANDING iz poruke; radi skraćenja ovde je izostavljen

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

# ---------- LOGIN / REGISTER — Apple/Kendo style ----------
LOGIN_CSS = """
<style>
/* full-page gradient + grain */
.mm-auth-bg{
  position:fixed; inset:0; z-index:-1;
  background:
    radial-gradient(1200px 600px at 20% -10%, #7C5CFF10, transparent 55%),
    radial-gradient(1200px 600px at 80% 110%, #4EA3FF10, transparent 55%),
    linear-gradient(180deg, #0B0D12 0%, #0C1016 100%);
}
.mm-auth-bg:after{
  content:""; position:absolute; inset:0;
  background-image:url('data:image/svg+xml;utf8,\
  <svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">\
  <filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="4" stitchTiles="stitch"/></filter>\
  <rect width="160" height="160" filter="url(%23n)" opacity="0.04"/></svg>');
  background-size:160px 160px; mix-blend-mode:overlay; pointer-events:none;
}
/* center wrapper */
.mm-auth-wrap{max-width:960px;margin:6vh auto 4vh;}
.mm-auth-card{
  display:grid; grid-template-columns:1fr 1fr; gap:0; overflow:hidden;
  border-radius:20px; border:1px solid var(--ring); background:#0F1219; box-shadow:0 30px 80px rgba(0,0,0,.45);
}
.mm-auth-left{padding:28px 28px 24px}
.mm-auth-right{
  position:relative; min-height:520px; display:flex; align-items:flex-end; color:#C7CEDA;
  background:
    linear-gradient(0deg, rgba(11,13,18,.55), rgba(11,13,18,.55)),
    url('https://images.unsplash.com/photo-1520975892533-01adf8d46a49?q=80&w=1200&auto=format&fit=crop') center/cover no-repeat;
}
.mm-auth-right .inner{padding:22px}
.mm-logo{display:flex;align-items:center;gap:10px;font-weight:900}
.mm-dot{width:12px;height:12px;border-radius:50%;background:linear-gradient(90deg,var(--g1),var(--g2));box-shadow:0 0 16px #7C5CFF66}
.mm-title{font-size:22px;font-weight:900;margin:8px 0 2px}
.mm-sub{color:#A7B0BE;margin-bottom:14px}
.mm-sep{height:1px;background:rgba(255,255,255,.08);margin:14px 0}

/* streamlit controls restyle */
.mm-auth-left .stTextInput>div>div>input{
  background:#0E131A; border:1px solid var(--ring); color:var(--ink);
  height:44px; border-radius:12px;
}
.mm-auth-left .stTextInput>label{font-weight:700;color:#D5DAE4}
.mm-auth-left .stButton>button{
  width:100%; height:46px; border-radius:12px; font-weight:800;
  background:linear-gradient(90deg,var(--g1),var(--g2))!important; color:#0B0D12!important; border:none!important;
}
.mm-foot{color:#9AA3B2;text-align:center;margin-top:14px}
@media (max-width:900px){
  .mm-auth-card{grid-template-columns:1fr}
  .mm-auth-right{min-height:220px}
}
</style>
<div class="mm-auth-bg"></div>
"""

def render_login():
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    st.markdown('<div class="mm-auth-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="mm-auth-card">', unsafe_allow_html=True)

    # LEFT: form
    st.markdown('<div class="mm-auth-left">', unsafe_allow_html=True)
    st.markdown('<div class="mm-logo"><div class="mm-dot"></div><div>MindMate</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="mm-title">Prijava u nalog</div>', unsafe_allow_html=True)
    st.markdown('<div class="mm-sub">Prijavi se da nastaviš ka svojoj kontrolnoj tabli.</div>', unsafe_allow_html=True)
    with st.form("login_form"):
        email = st.text_input("Email", key="login_email")
        pw    = st.text_input("Lozinka", type="password", key="login_pw")
        st.markdown('<div class="mm-sep"></div>', unsafe_allow_html=True)
        ok = st.form_submit_button("Prijavi se")
    st.markdown('Nemaš nalog? 👉 [Registracija](?register)', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)  # close left

    # RIGHT: image + quote
    st.markdown('<div class="mm-auth-right"><div class="inner">', unsafe_allow_html=True)
    st.write("**„Mikro-navike su nam porasle, a tim je samouvereniji.** MindMate nam je pomogao da izgradimo ritam i lakše prepoznamo obrasce.”")
    st.caption("— Kody, korisnik MindMate-a")
    st.markdown('</div></div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)   # card
    st.markdown('<div class="mm-foot">© 2025 MindMate. Nije medicinski alat. Za hitne slučajeve — 112.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)   # wrap

    if ok:
        if authenticate(email.strip(), pw):
            st.session_state.auth_ok = True
            st.session_state.auth_email = email.strip()
            st.session_state.page = "home"
            st.query_params.clear(); st.query_params["home"] = ""
            st.success("Dobrodošao/la! Preusmeravam…")
            safe_rerun()
        else:
            st.error("Pogrešan email ili lozinka.")

def render_register():
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    st.markdown('<div class="mm-auth-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="mm-auth-card">', unsafe_allow_html=True)

    # LEFT: form
    st.markdown('<div class="mm-auth-left">', unsafe_allow_html=True)
    st.markdown('<div class="mm-logo"><div class="mm-dot"></div><div>MindMate</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="mm-title">Kreiraj nalog</div>', unsafe_allow_html=True)
    st.markdown('<div class="mm-sub">Potreban je samo email i lozinka.</div>', unsafe_allow_html=True)
    with st.form("register_form"):
        email = st.text_input("Email", key="reg_email")
        pw    = st.text_input("Lozinka", type="password", key="reg_pw")
        st.markdown('<div class="mm-sep"></div>', unsafe_allow_html=True)
        ok = st.form_submit_button("Registruj se")
    st.markdown('Već imaš nalog? 👉 [Prijava](?login)', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)  # close left

    # RIGHT: image + quote
    st.markdown('<div class="mm-auth-right"><div class="inner">', unsafe_allow_html=True)
    st.write("**„Od kako sam dodala 5-min check-in, jasno vidim kada posustanem.”** Grafovi i male akcije prave razliku.")
    st.caption("— Mila, korisnica MindMate-a")
    st.markdown('</div></div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)   # card
    st.markdown('<div class="mm-foot">© 2025 MindMate. Nije medicinski alat. Za hitne slučajeve — 112.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)   # wrap

    if ok:
        if not email or not pw:
            st.error("Unesi email i lozinku.")
        else:
            ok2, msg = register_user(email.strip(), pw)
            if ok2:
                st.success("Registracija uspešna. Uloguj se.")
                st.session_state.page = "login"
                st.query_params.clear(); st.query_params["login"] = ""
                safe_rerun()
            else:
                st.error(msg)

# ---------- Router + Guard ----------
PROTECTED = {"home","chat","checkin","analytics"}
page = st.session_state.page
if page in PROTECTED and not st.session_state.get("auth_ok", False):
    st.session_state.page = "login"
    page = "login"

if page=="landing":
    render_landing()
elif page=="login":
    render_login()
elif page=="register":
    render_register()
elif page=="home":
    if require_auth_guard("home"): render_home()
elif page=="chat":
    if require_auth_guard("chat"): render_chat()
elif page=="checkin":
    if require_auth_guard("checkin"): render_checkin()
elif page=="analytics":
    if require_auth_guard("analytics"): render_analytics()

st.markdown("<div style='text-align:center;color:#9AA3B2;margin-top:16px'>© 2025 MindMate. Nije medicinski alat. Za hitne slučajeve — 112.</div>", unsafe_allow_html=True)
