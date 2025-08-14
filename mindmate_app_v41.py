# app.py — MindMate (light/minimal) • sticky navbar + login/register modal + personalizovane notifikacije
# Pokretanje: streamlit run app.py

import os, re, json, math, requests
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from streamlit.components.v1 import html as st_html
import plotly.express as px
import plotly.graph_objects as go

# ------------------------- App meta -------------------------
APP_TITLE = "MindMate"
st.set_page_config(page_title=APP_TITLE, page_icon="🌸", layout="wide")

# ------------------------- Fake DB (lokalni JSON) -------------------------
DB_PATH = os.environ.get("MINDMATE_DB", "mindmate_db.json")

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

if "DB" not in st.session_state:
    st.session_state.DB = _init_db()

def _get_db(): return st.session_state.DB
def _persist_db(): _save_db(st.session_state.DB)

# ------------------------- Session (auth, nav, notif) -------------------------
def _ss(key, default):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]

_ss("page", "landing")
_ss("auth_open", False)         # da li je modal otvoren
_ss("auth_mode", "login")       # login | register
_ss("user", None)               # {"name":..., "email":...}
_ss("notifications", [])        # lista {ts, text}
_ss("notif_unread", 0)
_ss("chat_log", [])

def safe_rerun():
    if hasattr(st, "rerun"): st.rerun()
    else: st.experimental_rerun()

# ------------------------- Helpers -------------------------
def add_notification(text: str):
    st.session_state.notifications.append({"ts": datetime.utcnow().isoformat(), "text": text})
    st.session_state.notif_unread += 1

def mark_notifications_read():
    st.session_state.notif_unread = 0

def is_valid_email(e: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", e or ""))

# ------------------------- UI: Global light theme + Navbar -------------------------
st.markdown("""
<style>
:root{
  --ink:#0E1116; --mut:#6B7280; --ring:rgba(15,23,42,.10);
  --bg:#FFFFFF; --card:#F8FAFC; --brand:#6E56CF; --brand2:#5B9BFA;
}
html,body{background:var(--bg); color:var(--ink); font-family:Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;}
.main .block-container{padding-top:0.5rem; max-width:1240px}

a { color: var(--brand); text-decoration: none; }

/* Sticky topbar */
.mm-top{
  position: sticky; top: 0; z-index: 999;
  background: rgba(255,255,255,.75); backdrop-filter: saturate(160%) blur(10px);
  border-bottom: 1px solid var(--ring);
}
.mm-nav{
  display:flex; align-items:center; justify-content:space-between;
  max-width:1240px; margin:0 auto; padding:10px 8px;
}
.mm-left{display:flex; align-items:center; gap:14px}
.mm-brand{
  display:flex; align-items:center; gap:10px; font-weight:900;
}
.mm-dot{
  width:12px;height:12px;border-radius:999px;
  background: radial-gradient(60% 60% at 40% 40%, #B2C7FF, transparent 62%),
              linear-gradient(90deg, var(--brand), var(--brand2));
  box-shadow: 0 0 0 4px rgba(110,86,207,.10), 0 4px 18px rgba(91,155,250,.30);
}
.mm-links{display:flex; align-items:center; gap:4px; flex-wrap:wrap}
.mm-link{
  padding:8px 12px; border-radius:10px; border:1px solid transparent; font-weight:700; color:#0E1116;
  transition: transform .14s ease, border-color .14s ease, background .14s ease;
}
.mm-link:hover{ transform: translateY(-1px) scale(1.03); background:#F3F4F6; border-color:var(--ring); }
.mm-link.active{ background:#EEF2FF; border-color:rgba(99,102,241,.25); }
.mm-cta{display:flex; gap:8px; align-items:center}
.mm-btn{
  padding:8px 12px; border-radius:10px; border:1px solid var(--ring); font-weight:800; color:#0E1116; background:white;
  transition: transform .14s ease, box-shadow .14s ease;
}
.mm-btn:hover{ transform: translateY(-1px) scale(1.03); box-shadow: 0 6px 18px rgba(0,0,0,.06); }
.mm-btn.primary{
  background: linear-gradient(90deg, var(--brand), var(--brand2)); color:white; border: none;
}

/* Notif badge */
.badge{
  display:inline-flex; align-items:center; justify-content:center;
  min-width:18px; height:18px; padding:0 6px; font-size:12px; font-weight:800;
  border-radius:999px; color:white; background:#EF4444;
}

/* Hero orb */
.hero-orb{
  width:min(980px, 92vw); height:340px; margin:24px auto 0; border-radius:24px;
  background:
    radial-gradient(120px 80px at 20% 40%, rgba(110,86,207,.25), transparent 62%),
    radial-gradient(160px 100px at 75% 55%, rgba(91,155,250,.25), transparent 65%),
    linear-gradient(180deg, #FAFBFF 0%, #F5F7FF 50%, #F9FAFF 100%);
  border:1px solid var(--ring);
  position:relative; overflow:hidden;
}
.hero-orb::after{
  content:""; position:absolute; inset:-40px -10% auto -10%; height:260px;
  background:
    radial-gradient(240px 120px at 20% 60%, rgba(110,86,207,.20), transparent 65%),
    radial-gradient(200px 100px at 60% 40%, rgba(91,155,250,.18), transparent 60%),
    radial-gradient(220px 110px at 85% 70%, rgba(185,220,255,.16), transparent 65%);
  filter: blur(16px); opacity:.9; animation: cloudFloat 26s linear infinite;
}
@keyframes cloudFloat{0%{transform:translateX(-6%)} 50%{transform:translateX(6%)} 100%{transform:translateX(-6%)}}

/* Cards */
.card{background:var(--card); border:1px solid var(--ring); border-radius:14px; padding:16px;
      transition: transform .16s ease, box-shadow .16s ease}
.card:hover{ transform: translateY(-2px) scale(1.01); box-shadow:0 10px 28px rgba(2,6,23,.06) }

/* Section helpers */
.section{padding:28px 6px}
.h2{font-size:clamp(22px,2.4vw,30px); margin:0 0 12px}
.grid-12{display:grid; grid-template-columns: repeat(12, 1fr); gap:12px}
@media (max-width:900px){ .grid-12{grid-template-columns: repeat(6,1fr)} }
.small{color:var(--mut)}

/* Modal auth */
.mm-modal-mask{
  position:fixed; inset:0; background:rgba(2,6,23,.35); backdrop-filter: blur(4px);
  display:flex; align-items:center; justify-content:center; z-index:1000;
}
.mm-modal{ width:min(520px, 92vw); background:white; border:1px solid var(--ring); border-radius:16px; padding:18px 16px; }
.modal-title{font-weight:900; font-size:20px; margin:0 0 6px}
.modal-sub{color:var(--mut); margin-bottom:10px}
.input{width:100%; padding:10px 12px; border:1px solid var(--ring); border-radius:10px}
.row{display:flex; gap:10px}
.err{color:#DC2626; font-size:13px; margin-top:6px}
.ok{color:#16A34A; font-size:13px; margin-top:6px}

/* FAQ */
.faq-item{ border:1px solid var(--ring); border-radius:12px; overflow:hidden; background:white; }
.faq-q{ width:100%; text-align:left; padding:14px 14px; font-weight:800; border:0; background:white; }
.faq-a{ padding:0 14px 14px; color:#374151; display:none }
.faq-item.open .faq-a{ display:block }

/* Pricing */
.price-card{ background:white; border:1px solid var(--ring); border-radius:14px; padding:16px }
.price-btn{ display:inline-block; padding:10px 12px; border-radius:10px; font-weight:800; border:1px solid var(--ring) }
.price-btn.primary{ background: linear-gradient(90deg, var(--brand), var(--brand2)); color:white; border:none }

/* Footer */
.footer{ color:#6B7280; text-align:center; padding:18px 0 28px }
</style>
""", unsafe_allow_html=True)

# ------------------------- Top Navbar (React-like with simple state) -------------------------
def top_navbar():
    user = st.session_state.user
    unread = st.session_state.notif_unread

    # Active link helper
    def acls(slug):
        return "mm-link active" if st.session_state.page == slug else "mm-link"

    c1, = st.columns(1)
    with c1:
        st_html(f"""
<div class="mm-top">
  <div class="mm-nav">
    <div class="mm-left">
      <div class="mm-brand">
        <div class="mm-dot"></div>
        <div>MindMate</div>
      </div>
      <div class="mm-links">
        <a class="{acls('landing')}" href="?landing">Početna</a>
        <a class="{acls('home')}" href="?home">Kontrolna tabla</a>
        <a class="{acls('chat')}" href="?chat">Chat</a>
        <a class="{acls('checkin')}" href="?checkin">Check-in</a>
        <a class="{acls('analytics')}" href="?analytics">Analitika</a>
      </div>
    </div>
    <div class="mm-cta">
      <a class="mm-btn" href="?notifications">🔔 Obaveštenja{(' <span class=badge>'+str(unread)+'</span>') if unread>0 else ''}</a>
      {(
        '<span class="small" style="margin-right:6px">Zdravo, '+user.get('name','Prijatelju')+'</span>' +
        '<a class="mm-btn" href="?logout">Odjavi se</a>'
      ) if user else (
        '<a class="mm-btn" href="?login">Prijava</a>' +
        '<a class="mm-btn primary" href="?register">Registracija</a>'
      )}
    </div>
  </div>
</div>
        """, height=64)
    qp = st.query_params
    if "landing" in qp: st.session_state.page = "landing"
    if "home" in qp: st.session_state.page = "home"
    if "chat" in qp: st.session_state.page = "chat"
    if "checkin" in qp: st.session_state.page = "checkin"
    if "analytics" in qp: st.session_state.page = "analytics"
    if "notifications" in qp:
        st.session_state.page = "notifications"
    if "login" in qp:
        st.session_state.auth_open = True
        st.session_state.auth_mode = "login"
    if "register" in qp:
        st.session_state.auth_open = True
        st.session_state.auth_mode = "register"
    if "logout" in qp:
        st.session_state.user = None
        add_notification("Odjava uspešna. Vidimo se uskoro! 👋")
        st.query_params.clear()
        safe_rerun()

# ------------------------- Landing (svetli) -------------------------
def landing_section():
    st.markdown("""
<div class="hero-orb"></div>
""", unsafe_allow_html=True)

    col1, col2 = st.columns([1.2, 0.8])
    with col1:
        st.markdown("### Preusmeri brige u konkretne korake — za 5 minuta dnevno.")
        st.markdown(
            "Kratki check-in, mikro-navike i empatičan razgovor. "
            "Jasni trendovi, tvoj ritam. Bez komplikacija."
        )
        cta1, cta2 = st.columns(2)
        with cta1:
            if st.button("Kreni odmah", use_container_width=True):
                st.session_state.page = "home"; safe_rerun()
        with cta2:
            if st.button("Pogledaj kako radi", use_container_width=True):
                add_notification("🎬 Demo video uskoro! Do tada, istraži Kontrolnu tablu.")
    with col2:
        st.markdown("""
<div class="card">
  <b>Highlights</b>
  <ul>
    <li>2 pitanja dnevno</li>
    <li>Mikro-navike (5–10 min)</li>
    <li>Grafovi i obrasci</li>
  </ul>
</div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="section"></div>', unsafe_allow_html=True)

    st.markdown("#### Zašto početi danas")
    f1, f2, f3 = st.columns(3)
    with f1:
        st.markdown('<div class="card"><b>Brz check-in</b><div class="small">Bez frke, gradi ritam.</div></div>', unsafe_allow_html=True)
    with f2:
        st.markdown('<div class="card"><b>Mikro-navike</b><div class="small">Male akcije → napredak.</div></div>', unsafe_allow_html=True)
    with f3:
        st.markdown('<div class="card"><b>Jasni trendovi</b><div class="small">Vidi raspoloženje i fokus.</div></div>', unsafe_allow_html=True)

# ------------------------- Notifications page -------------------------
def notifications_page():
    st.subheader("🔔 Obaveštenja")
    mark_notifications_read()
    if not st.session_state.notifications:
        st.info("Trenutno nema obaveštenja.")
    else:
        for n in reversed(st.session_state.notifications):
            ts = n["ts"].replace("T", " ")[:19]
            st.markdown(f"- {ts} — {n['text']}")
    if st.button("Pošalji probno obaveštenje"):
        name = (st.session_state.user or {}).get("name", "Prijatelju")
        add_notification(f"🌸 Ej {name}, stigla je nova poruka u chatu!")
        st.success("Poslato!")

# ------------------------- Mini data viz + checkins -------------------------
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

def home_page():
    st.subheader("🧭 Tvoja kontrolna tabla")
    u,s,sa,re = compute_metrics()
    st.markdown(f"""
<div class="grid-12">
  <div class="card" style="grid-column:span 3"><b style="font-size:22px">{u}</b><div class="small">Aktivnih korisnika</div></div>
  <div class="card" style="grid-column:span 3"><b style="font-size:22px">{s}</b><div class="small">Ukupno sesija</div></div>
  <div class="card" style="grid-column:span 3"><b style="font-size:22px">{sa}%</b><div class="small">Zadovoljstvo</div></div>
  <div class="card" style="grid-column:span 3"><b style="font-size:22px">{re}%</b><div class="small">Mesečna zadržanost</div></div>
</div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="section"></div>', unsafe_allow_html=True)

    st.markdown("#### Brze akcije")
    c1,c2,c3 = st.columns(3)
    with c1:
        if st.button("💬 Otvori chat", use_container_width=True):
            st.session_state.page = "chat"; safe_rerun()
    with c2:
        if st.button("🗓️ Uradi check-in", use_container_width=True):
            st.session_state.page = "checkin"; safe_rerun()
    with c3:
        if st.button("📈 Vidi analitiku", use_container_width=True):
            st.session_state.page = "analytics"; safe_rerun()

def chat_page():
    st.subheader("💬 Chat (demo)")
    st.info("Ovde može ići tvoj chat backend. (Za sada demo poruke.)")
    for role,msg in st.session_state.chat_log:
        with st.chat_message(role): st.markdown(msg)
    user=st.chat_input("Upiši poruku…")
    if user:
        st.session_state.chat_log.append(("user",user))
        with st.chat_message("assistant"):
            reply = "Razumem. Hajde da to raščlanimo u male korake. Šta je prvi mikro-korak za 5 min?"
            st.markdown(reply)
            st.session_state.chat_log.append(("assistant",reply))
            name = (st.session_state.user or {}).get("name", "Prijatelju")
            add_notification(f"🧠 {name}, tvoj asistent je odgovorio u chatu.")

def checkin_page():
    st.subheader("🗓️ Daily Check-in")
    c1,c2 = st.columns(2)
    with c1:
        phq1 = st.slider("Gubitak interesovanja / zadovoljstva",0,3,0)
        phq2 = st.slider("Potištenost / tuga / beznađe",0,3,0)
    with c2:
        gad1 = st.slider("Nervoza / anksioznost / napetost",0,3,0)
        gad2 = st.slider("Teško prestajem da brinem",0,3,0)
    notes = st.text_area("Napomene (opciono)")
    if st.button("Sačuvaj današnji check-in", use_container_width=True):
        save_checkin(get_or_create_uid(), phq1,phq2,gad1,gad2, notes)
        name = (st.session_state.user or {}).get("name", "Prijatelju")
        add_notification(f"✅ Sjajno {name}! Check-in zabeležen za danas.")

def analytics_page():
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
    fig1.update_layout(paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF", font_color="#0E1116",
                       xaxis_title="Datum", yaxis_title="Skor (0–12)",
                       margin=dict(l=10,r=10,t=50,b=10))
    st.plotly_chart(fig1, use_container_width=True)

    mood = (95 - df["total"]*4).clip(40, 100)
    prod = (92 - df["total"]*3 + (df.index%3==0)*2).clip(35, 100)
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=df["date"], y=prod, mode="lines+markers", name="Produktivnost"))
    fig2.add_trace(go.Scatter(x=df["date"], y=mood, mode="lines+markers", name="Raspoloženje"))
    fig2.update_layout(title="Raspoloženje & Produktivnost",
                       paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF", font_color="#0E1116",
                       xaxis_title="Datum", yaxis_title="Skor (0–100)",
                       margin=dict(l=10,r=10,t=50,b=10))
    st.plotly_chart(fig2, use_container_width=True)

# ------------------------- AUTH MODAL (login/register) -------------------------
def auth_modal():
    if not st.session_state.auth_open:
        return

    mode = st.session_state.auth_mode  # login | register
    name_key = f"{mode}_name"
    email_key = f"{mode}_email"
    pass_key = f"{mode}_pass"

    # Defaults
    _ss(name_key, st.session_state.user["name"] if st.session_state.user else "")
    _ss(email_key, st.session_state.user["email"] if st.session_state.user else "")
    _ss(pass_key, "")

    # Modal body
    with st.container():
        st_html(f"""
<div class="mm-modal-mask">
  <div class="mm-modal">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px">
      <div class="modal-title">{'Prijava' if mode=='login' else 'Registracija'}</div>
      <button onclick="window.parent.postMessage({{type:'closeAuth'}}, '*')" class="mm-btn">Zatvori</button>
    </div>
    <div class="modal-sub">{'Dobrodošao nazad 👋' if mode=='login' else 'Kreiraj nalog za 10 sekundi 🚀'}</div>

    {"<div class='small' style='margin:6px 0 6px 2px'>Ime</div>" if mode=='register' else ""}
    {"<input id='mm_name' class='input' placeholder='npr. Deni' value='"+st.session_state[name_key].replace("'", "&#39;")+"'/>" if mode=='register' else ""}

    <div class='small' style='margin:10px 0 6px 2px'>Email</div>
    <input id='mm_email' class='input' placeholder='ti@primer.com' value='{st.session_state[email_key].replace("'", "&#39;")}'/>

    <div class='small' style='margin:10px 0 6px 2px'>Lozinka</div>
    <input id='mm_pass' type='password' class='input' placeholder='min. 6 karaktera' value='{st.session_state[pass_key].replace("'", "&#39;")}'/>

    <div style="display:flex; gap:10px; margin-top:12px">
      <button class="mm-btn primary" onclick="window.parent.postMessage({{type:'authSubmit', mode:'{mode}'}}, '*')">
        {'Prijavi se' if mode=='login' else 'Registruj se'}
      </button>
      <button class="mm-btn" onclick="window.parent.postMessage({{type:'authSwitch', to:'{'register' if mode=='login' else 'login'}'}}, '*')">
        {'Nemaš nalog? Registruj se' if mode=='login' else 'Imaš nalog? Prijavi se'}
      </button>
    </div>
  </div>
</div>

<script>
window.addEventListener('message', (e)=>{
  const msg=e.data||{};
  if(msg.type==='authGet'){ // vrati vrednosti polja
    const name_el=document.getElementById('mm_name');
    const email_el=document.getElementById('mm_email');
    const pass_el=document.getElementById('mm_pass');
    const payload={{name: name_el?name_el.value:'', email: (email_el&&email_el.value)||'', password: (pass_el&&pass_el.value)||''}};
    window.parent.postMessage({{type:'authFields', payload}}, '*');
  }
});
</script>
        """, height=380)

    # JS <-> Python bridge: pokupimo vrednosti polja
    # 1) presretnemo poruke iz iframa koristeći streamlit-js-events (ugrađeni postMessage hack)
    #    Ovaj deo simuliramo preko "on_click" dugmadi iznad; JS šalje authSubmit -> mi ovde pollujemo.
    #    Streamlit ne expose-uje direktan listener, pa radimo u dva pasa: ako dođe authSubmit, zatraži authGet.

# ------------------------- JS bridge (hack) -------------------------
# Implementacija: koristimo query parametar kao trigger iz JS dugmadi (pošto smo već koristili ?login/?register,
# možemo i ?authSubmit). Minimalan hack: klik na dugme doda parametar; ovde ga očitamo.
# Da bismo ostali čisti, napravićemo male pomoćne linkove ispod (ne prikazuju se), ali to je već urađeno preko postMessage.
# Praktično: JS šalje postMessage, ali Streamlit to ne hvata. Rešenje: dugmad gore su prava dugmad koja NE menjaju URL.
# Zato ćemo ovde ponuditi Python-side mini formu kada je modal otvoren (submit sa validacijom).

def render_auth_python_side():
    """Fallback/Python-side forma (isti stil) — radi validaciju i zapisuje session user.
       Zove se kada je modal otvoren, kako bi zaista obavila submit (jer JS u iframu ne može direktno setovati state)."""
    if not st.session_state.auth_open:
        return
    mode = st.session_state.auth_mode
    with st.expander("🔐 (Skriveno) Unos podataka – klikni ako modal ne reaguje", expanded=False):
        if mode == "register":
            name = st.text_input("Ime", value=st.session_state.get("register_name",""))
        else:
            name = st.session_state.get("login_name","")
        email = st.text_input("Email", value=st.session_state.get(f"{mode}_email",""))
        pwd = st.text_input("Lozinka", type="password", value=st.session_state.get(f"{mode}_pass",""))

        err = []
        if not is_valid_email(email): err.append("Unesi validan email.")
        if len(pwd) < 6: err.append("Lozinka mora imati bar 6 karaktera.")
        if mode=="register" and not (name and len(name.strip())>=2):
            err.append("Unesi ime (min. 2 karaktera).")
        if err:
            st.caption(" / ".join(err))
        if st.button("Potvrdi", type="primary"):
            if not err:
                st.session_state.user = {"name": name.strip() if mode=="register" else (st.session_state.user["name"] if st.session_state.user else "Korisnik"),
                                         "email": email.strip()}
                st.session_state.auth_open = False
                add_notification(f"🎉 Dobrodošao/la {st.session_state.user['name']}! Tvoj nalog je spreman.")
                st.success("Uspešno!")
                safe_rerun()

# ------------------------- Footer -------------------------
def footer():
    st.markdown('<div class="footer">© 2025 MindMate. Nije medicinski alat. Za hitne slučajeve — 112.</div>', unsafe_allow_html=True)

# ------------------------- Router -------------------------
def route():
    top_navbar()

    # Otvaranje auth modala kad klikneš dugme u navbaru (preko query parametara)
    qp = st.query_params
    if "login" in qp or "register" in qp:
        st.session_state.auth_open = True
        st.session_state.auth_mode = "login" if "login" in qp else "register"
        st.query_params.clear()

    # Stranice
    pg = st.session_state.page
    if pg == "landing":
        landing_section()
    elif pg == "home":
        home_page()
    elif pg == "chat":
        chat_page()
    elif pg == "checkin":
        checkin_page()
    elif pg == "analytics":
        analytics_page()
    elif pg == "notifications":
        notifications_page()
    else:
        landing_section()

    # Modal auth (UI) + fallback python forma
    auth_modal()
    render_auth_python_side()

    footer()

# ------------------------- RUN -------------------------
route()
