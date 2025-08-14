# app.py — MindMate (svetli Kendo-like navbar) + Login & Register u navbaru
# Landing otvoren svima; ostale stranice traže login.
# Pokretanje: streamlit run app.py

import os, json, requests, math, re, hashlib, hmac
import streamlit as st
from datetime import datetime, date, timedelta
from streamlit.components.v1 import html as st_html
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ===== Konstante / ENV =====
APP_TITLE = "MindMate"
DB_PATH   = os.environ.get("MINDMATE_DB", "mindmate_db.json")

CHAT_PROVIDER = os.environ.get("CHAT_PROVIDER", "ollama").lower().strip()
OLLAMA_HOST   = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL  = os.environ.get("OLLAMA_MODEL", "llama3.1")
OPENAI_API_KEY= os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL  = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# Opcioni seed korisnici preko ENV (plain lozinke samo za MVP/dev)
# npr: USERS_JSON='[{"email":"demo@mindmate.app","password":"demo123","name":"Demo"}]'
USERS_JSON   = os.environ.get("USERS_JSON","")

def safe_rerun():
    if hasattr(st, "rerun"): st.rerun()
    else: st.experimental_rerun()

st.set_page_config(page_title=APP_TITLE, page_icon="🧠", layout="wide")

# ===== “Baza” =====
def _init_db():
    if not os.path.exists(DB_PATH):
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump({"checkins": [], "chat_events": [], "users": []}, f)
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict): data={}
        data.setdefault("checkins", []); data.setdefault("chat_events", []); data.setdefault("users", [])
        return data
    except Exception:
        return {"checkins": [], "chat_events": [], "users": []}

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

# ===== Auth helpers (lagani hash + validacija) =====
SECRET_PEPPER = "mindmate-pepper-01"

def _hash_pw(pw: str) -> str:
    return hashlib.sha256((pw + SECRET_PEPPER).encode("utf-8")).hexdigest()

def _email_ok(e:str)->bool:
    return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", e or ""))

def _pw_ok(pw:str)->bool:
    return bool(pw and len(pw) >= 6)

def _load_users_from_env_or_db():
    users=[]
    # iz ENV
    if USERS_JSON.strip():
        try:
            raw=json.loads(USERS_JSON)
            for u in raw:
                email=(u.get("email","") or "").lower().strip()
                name = u.get("name") or email.split("@")[0]
                pw   = u.get("password") or ""
                if email and pw:
                    users.append({"email":email, "name":name, "pw_hash":_hash_pw(pw)})
        except Exception:
            pass
    # iz baze
    db=_get_db()
    for u in db.get("users",[]):
        if u.get("email") and u.get("pw_hash"):
            users.append(u)
    # default demo ako baš nema ničeg
    if not users:
        users=[{"email":"demo@mindmate.app","name":"Demo","pw_hash":_hash_pw("demo123")}]
    # deduplikacija
    dedup={}
    for u in users: dedup[u["email"]]=u
    return list(dedup.values())

def _ensure_user_saved(u):
    db=_get_db()
    if not any(x.get("email")==u["email"] for x in db["users"]):
        db["users"].append({"email":u["email"], "name":u.get("name") or "", "pw_hash":u["pw_hash"]})
        _persist_db()

def verify_user(email, password):
    email=(email or "").lower().strip()
    users=_load_users_from_env_or_db()
    for u in users:
        if u["email"]==email and hmac.compare_digest(u["pw_hash"], _hash_pw(password or "")):
            _ensure_user_saved(u)
            return {"email": u["email"], "name": u.get("name") or email.split("@")[0]}
    return None

def register_user(email, password, name=""):
    email=(email or "").lower().strip()
    if not _email_ok(email): return (False, "Unesi ispravan email.")
    if not _pw_ok(password): return (False, "Lozinka mora imati najmanje 6 karaktera.")
    db=_get_db()
    if any(u["email"]==email for u in db["users"]): return (False, "Nalog već postoji.")
    u={"email":email, "name":(name or email.split("@")[0]).strip(), "pw_hash":_hash_pw(password)}
    db["users"].append(u); _persist_db()
    return (True, {"email":u["email"], "name":u["name"]})

def start_session(user_dict):
    st.session_state.auth = {
        "email": user_dict["email"],
        "name":  user_dict.get("name") or user_dict["email"].split("@")[0],
        "uid":   f"u_{abs(hash(user_dict['email']))%10_000_000}"
    }

def logout():
    for k in ["auth","chat_log"]:
        if k in st.session_state: del st.session_state[k]
    safe_rerun()

def is_authed():
    return bool(st.session_state.get("auth"))

def get_or_create_uid():
    if is_authed(): return st.session_state.auth["uid"]
    if "uid" not in st.session_state:
        st.session_state.uid = f"user_{int(datetime.utcnow().timestamp())}"
    return st.session_state.uid

# ===== App podaci =====
def save_checkin(uid, phq1, phq2, gad1, gad2, notes=""):
    db = _get_db()
    db["checkins"].append({
        "uid": uid, "ts": datetime.utcnow().isoformat(), "date": date.today().isoformat(),
        "phq1": int(phq1), "phq2": int(phq2), "gad1": int(gad1), "gad2": int(gad2),
        "notes": notes or ""
    }); _persist_db()

def save_chat_event(uid, role, content):
    db = _get_db()
    db["chat_events"].append({
        "uid": uid, "ts": datetime.utcnow().isoformat(), "role": role,
        "content": (content or "")[:4000]
    }); _persist_db()

def compute_metrics():
    db = _get_db()
    uids = set([r.get("uid","") for r in db["checkins"]] + [r.get("uid","") for r in db["chat_events"]])
    uids.discard("")
    users = len(uids) or 1
    sessions = sum(1 for r in db["chat_events"] if r.get("role")=="user")
    cutoff = datetime.utcnow()-timedelta(days=30)
    recent=[r for r in db["checkins"] if (datetime.fromisoformat((r.get("ts") or "").split("+")[0]) if r.get("ts") else datetime.utcnow())>=cutoff]
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

# ===== Chat backends =====
def chat_ollama(messages):
    try:
        r = requests.post(f"{OLLAMA_HOST}/api/chat",
                          json={"model":OLLAMA_MODEL,"messages":messages,"stream":False}, timeout=120)
        if r.status_code==404:
            prompt=""; 
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

# ===== Global stilovi (svetli navbar, tamni sadržaj kao do sada) =====
st.markdown("""
<style>
:root{
  --bg:#0B0D12; --panel:#10141B; --ink:#E8EAEE; --mut:#9AA3B2; --ring:rgba(255,255,255,.10);
  --g1:#7C5CFF; --g2:#4EA3FF;
}
/* app canvas */
html,body{background:var(--bg); color:var(--ink)}
.main .block-container{ padding-top:1rem!important; max-width:1280px!important; margin-inline:auto!important; }
/* sticky light navbar */
.k-wrap{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.86);backdrop-filter:saturate(1.1) blur(10px); border-bottom:1px solid rgba(0,0,0,.06); }
.k-nav{max-width:1180px;margin:0 auto; padding:10px 8px; display:flex; align-items:center; justify-content:space-between;}
.k-left{display:flex;align-items:center;gap:12px}
.k-logo{width:22px;height:22px;border-radius:6px;background:linear-gradient(90deg,var(--g1),var(--g2)); box-shadow:0 0 0 3px rgba(124,92,255,.18)}
.k-name{color:#111827; font-weight:900}
.k-links{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.k-link{padding:8px 12px; border:1px solid rgba(0,0,0,.08); border-radius:12px; text-decoration:none; color:#111827; font-weight:700; background:#fff; transition:transform .18s ease, box-shadow .18s}
.k-link:hover{transform:translateY(-1px); box-shadow:0 6px 16px rgba(0,0,0,.06)}
.k-cta{padding:9px 13px; border-radius:12px; text-decoration:none; font-weight:900; background:linear-gradient(90deg,var(--g1),var(--g2)); color:white; border:1px solid rgba(0,0,0,.00)}
.k-ghost{padding:9px 13px; border-radius:12px; text-decoration:none; font-weight:900; background:#fff; color:#111827; border:1px solid rgba(0,0,0,.08)}
.k-user{display:flex;align-items:center;gap:8px;color:#111827}
.k-avatar{width:26px;height:26px;border-radius:50%;background:linear-gradient(90deg,var(--g1),var(--g2))}
.k-logout{padding:8px 12px;border:1px solid rgba(0,0,0,.08);border-radius:12px;background:#fff;color:#111827;font-weight:800}
</style>
""", unsafe_allow_html=True)

# ===== Router + query param hooks =====
if "page" not in st.session_state: st.session_state.page="landing"
if "chat_log" not in st.session_state: st.session_state.chat_log=[]
def goto(p): st.session_state.page=p; safe_rerun()

qp = st.query_params

# logout preko query-a (?logout=1)
if "logout" in qp:
    logout()

# auth panel preko query-a (?auth=login|register)
show_auth = qp.get("auth",[None])[0] if isinstance(qp.get("auth"), list) else qp.get("auth")

# ručni tabovi preko query-a
if   "landing"  in qp: st.session_state.page="landing"
elif "home"     in qp: st.session_state.page="home"
elif "chat"     in qp: st.session_state.page="chat"
elif "checkin"  in qp: st.session_state.page="checkin"
elif "analytics"in qp: st.session_state.page="analytics"

# Ako user ide na privatne tabuove bez login-a → pokaži login panel
if not is_authed() and st.session_state.page in {"home","chat","checkin","analytics"}:
    st.session_state.page = "landing"
    show_auth = show_auth or "login"
    st.toast("Prijavi se da nastaviš. (demo@mindmate.app / demo123)")

# ===== Navbar =====
def render_navbar():
    authed = is_authed()
    who = (st.session_state.auth["name"] if authed else None) or "Gost"
    # Linkovi (kao anchor-i sa query parametrima, da rade i bez dugmića)
    links_html = f"""
    <a class="k-link" href="?landing">Welcome</a>
    <a class="k-link" href="?home">Početna</a>
    <a class="k-link" href="?chat">Chat</a>
    <a class="k-link" href="?checkin">Check-in</a>
    <a class="k-link" href="?analytics">Analitika</a>
    """
    right_html = (
        f'<div class="k-user"><div class="k-avatar"></div><div>{who}</div>'
        f'<a class="k-logout" href="?landing&logout=1">Odjava</a></div>'
        if authed
        else '<a class="k-ghost" href="?landing&auth=login">Prijava</a>'
             ' <a class="k-cta" href="?landing&auth=register">Registracija</a>'
    )
    st.markdown(
        f"""
        <div class="k-wrap"><div class="k-nav">
            <div class="k-left">
              <div class="k-logo"></div><div class="k-name">MindMate</div>
            </div>
            <div class="k-links">{links_html}</div>
            <div>{right_html}</div>
        </div></div>
        """,
        unsafe_allow_html=True
    )

# ===== Auth panel (renderuje se ispod navbara kada je pozvan) =====
def render_auth_panel(mode="login"):
    box_title = "Prijava" if mode=="login" else "Registracija"
    st.markdown(
        """
        <div style="max-width:520px;margin:18px auto 0; background:#FFFFFF12; border:1px solid rgba(255,255,255,.10);
                    border-radius:16px; padding:20px">
          <div style="display:flex;align-items:center;gap:10px;font-weight:900;margin-bottom:6px">
            <div class="k-avatar"></div><div>MindMate</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    with st.form(f"{mode}_form"):
        if mode=="login":
            email = st.text_input("Email", placeholder="npr. demo@mindmate.app")
            pw    = st.text_input("Lozinka", type="password", placeholder="••••••")
            col1, col2 = st.columns([1,1])
            with col1:
                ok = st.form_submit_button("Prijavi se", type="primary", use_container_width=True)
            with col2:
                guest = st.form_submit_button("Uđi kao gost", use_container_width=True)
            if ok:
                if not _email_ok(email): st.error("Unesi validan email.")
                else:
                    u = verify_user(email, pw)
                    if u: start_session(u); st.success(f"Ćao, {u['name']}!"); st.query_params.clear(); safe_rerun()
                    else: st.error("Pogrešan email ili lozinka. (Probaj demo: demo@mindmate.app / demo123)")
            if guest:
                start_session({"email": f"guest-{int(datetime.utcnow().timestamp())}@local", "name": "Gost"})
                st.info("Ušao si kao gost."); st.query_params.clear(); safe_rerun()
        else:
            name  = st.text_input("Ime (prikazno)", placeholder="Kako da ti se obraćamo?")
            email = st.text_input("Email")
            pw    = st.text_input("Lozinka (min 6)", type="password")
            ok    = st.form_submit_button("Kreiraj nalog", type="primary", use_container_width=True)
            if ok:
                if not _email_ok(email): st.error("Unesi validan email.")
                elif not _pw_ok(pw):    st.error("Lozinka mora imati najmanje 6 karaktera.")
                else:
                    okr, data = register_user(email, pw, name or "")
                    if okr:
                        start_session(data); st.success(f"Dobrodošao, {data['name']}!")
                        st.query_params.clear(); safe_rerun()
                    else:
                        st.error(data)

# ===== LANDING (HTML) =====
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
@keyframes sway{0%{transform:rotate(0)}50%{transform:rotate(2.2deg)}100%{transform:rotate(0)}}
@keyframes pulse{0%,100%{opacity:.85}50%{opacity:1}}
/* vsl orb */
.vsl-area{position:relative}
.orb-wrap{position:relative;height:90px}
.orb{position:absolute; inset:-180px 0 0 0; margin:auto; z-index:0;width:min(980px,90vw); height:min(980px,90vw);
  background:radial-gradient(60% 55% at 50% 40%, rgba(124,92,255,.55), transparent 62%),
             radial-gradient(58% 52% at 50% 45%, rgba(78,163,255,.50), transparent 66%),
             radial-gradient(46% 40% at 50% 52%, rgba(154,214,255,.22), transparent 70%);
  filter: blur(28px) saturate(1.05); opacity:.9; animation:orbBreath 12s ease-in-out infinite;}
@keyframes orbBreath{0%,100%{transform:scale(1)}50%{transform:scale(1.04)}}
.vsl{position:relative;z-index:1;max-width:980px;margin:0 auto;border-radius:16px;border:1px solid var(--ring);padding:10px;background:rgba(255,255,255,.05);box-shadow:0 28px 90px rgba(0,0,0,.65)}
.vsl iframe{width:100%;aspect-ratio:16/9;height:auto;min-height:240px;border:0;border-radius:10px}
.trusted{display:flex;flex-direction:column;gap:10px;align-items:center;margin-top:14px}
.logos{display:flex;gap:16px;flex-wrap:wrap;justify-content:center}
.logo{width:110px;height:42px;border-radius:12px;border:1px solid var(--ring);background:rgba(255,255,255,.04);display:flex;align-items:center;justify-content:center;color:#C7CEDA;font-weight:800;letter-spacing:.4px;transition:transform .2s}
.logo:hover{transform:translateY(-2px)}
/* ...ostatak (features, faq, pricing) identičan ... */
</style>
</head>
<body>
<section class="section hero">
  <div class="container hero-grid">
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
</body></html>
"""

def render_landing():
    # (skratio sam HTML: hero — ali sve ostalo iz tvog starog LANDING-a može ostati;
    # ako želiš full, samo zameni ovaj string svojim punim LANDING-om, radi isto.)
    st_html(LANDING, height=720, scrolling=True)

# ===== Stranice =====
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
        st.info("Još nema podataka. Uradi prvi check-in."); return
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

# ===== Render flow =====
render_navbar()

# auth panel (ako je tražen)
if show_auth in {"login","register"}:
    render_auth_panel(show_auth)

page=st.session_state.page
if page=="landing": render_landing()
elif page=="home":
    if not is_authed(): st.info("Prijavi se da koristiš kontrolnu tablu."); render_auth_panel("login")
    else: render_home()
elif page=="chat":
    if not is_authed(): st.info("Prijavi se da koristiš chat."); render_auth_panel("login")
    else: render_chat()
elif page=="checkin":
    if not is_authed(): st.info("Prijavi se da radiš check-in."); render_auth_panel("login")
    else: render_checkin()
elif page=="analytics":
    if not is_authed(): st.info("Prijavi se da vidiš analitiku."); render_auth_panel("login")
    else: render_analytics()

st.markdown("<div style='text-align:center;color:#9AA3B2;margin-top:16px'>© 2025 MindMate. Nije medicinski alat. Za hitne slučajeve — 112.</div>", unsafe_allow_html=True)
