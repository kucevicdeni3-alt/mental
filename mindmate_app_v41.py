# app.py — Streamlit verzija (jedan fajl)
# - Landing sa VSL u krugu (video preko kruga)
# - "Planeta" pozadina (orb + suptilna animacija)
# - Brending (flower strelica/SVG)
# - Latice padaju stalno, kroz ceo skrol
# - Hover efekti (scale) na CTA dugmad
# - AI chat preko Ollama (lokalno, bez API ključa)
# Pokretanje: streamlit run app.py
# Zav.: pip install streamlit requests

import os
import json
import requests
import streamlit as st

# =========================
# KONFIG
# =========================
APP_NAME = "MindBloom"
DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")  # npr: llama3.1, mistral, qwen2.5

SYSTEM_GUARDRAIL = (
    "You are a supportive, empathetic mental-health companion. "
    "You are NOT a substitute for a licensed professional. "
    "Avoid medical or clinical instructions. "
    "If the user mentions self-harm, harming others, or a crisis, respond with empathy and suggest immediate help from local emergency services, a trusted person, or a crisis hotline. "
    "Keep replies short, gentle, and encouraging."
)

BRAND_ARROW_SVG = """
<svg width="28" height="28" viewBox="0 0 24 24" aria-hidden="true">
  <defs>
    <radialGradient id="g" cx="50%" cy="50%" r="70%">
      <stop offset="0%" stop-color="#ff66b3"></stop>
      <stop offset="100%" stop-color="#ff2e63"></stop>
    </radialGradient>
  </defs>
  <g fill="url(#g)">
    <path d="M12 2c-1.2 2.8-3.3 4.9-6.1 6.1C8.7 9.3 10.8 11.4 12 14c1.2-2.6 3.3-4.7 6.1-5.9C15.3 6.9 13.2 4.8 12 2z"/>
    <path d="M11 12l9 9-3 1-2-4-4-2z"/>
  </g>
</svg>
"""

# =========================
# HELPER: OLLAMA CHAT
# =========================
def ollama_chat(ollama_host, model, convo_messages, stream=False, options=None):
    """
    convo_messages: list[{"role": "system|user|assistant", "content": "..."}]
    """
    url = f"{ollama_host.rstrip('/')}/api/chat"
    payload = {"model": model, "messages": convo_messages, "stream": stream}
    if options:
        payload["options"] = options

    try:
        if stream:
            with requests.post(url, json=payload, stream=True, timeout=300) as r:
                r.raise_for_status()
                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]
        else:
            r = requests.post(url, json=payload, timeout=300)
            r.raise_for_status()
            data = r.json()
            yield data.get("message", {}).get("content", "")
    except requests.RequestException as e:
        yield f"(Greška pri povezivanju sa Ollama: {e})"


# =========================
# STREAMLIT UI
# =========================
st.set_page_config(page_title=f"{APP_NAME} — mentalno zdravlje", page_icon="💮", layout="wide")

# Sidebar: konfiguracija modela
with st.sidebar:
    st.markdown(f"### {APP_NAME} • Podešavanja")
    ollama_host = st.text_input("OLLAMA_HOST", value=DEFAULT_OLLAMA_HOST, help="npr. http://127.0.0.1:11434")
    model = st.text_input("Model", value=DEFAULT_MODEL, help="npr. llama3.1, mistral, qwen2.5")
    st.markdown("---")
    st.markdown("**VSL video URL (mp4 / webm)**")
    vsl_url = st.text_input("VSL link", value="https://cdn.coverr.co/videos/coverr-girl-in-the-forest-4692/1080p.mp4", help="Postavi svoj video link ovde")
    st.caption("Saveti: .mp4 ili .webm, sa CORS dozvolom za embeding.")

# ========== LANDING (HTML komponenta sa animacijama) ==========
landing_html = f"""
<style>
  :root {{
    --bg: #0b0b12;
    --text: #e9e9ef;
    --muted: #b7b7c7;
    --brand: #ff2e63;
    --brand2: #ff66b3;
    --card: #12121b;
    --ring: rgba(255,255,255,0.08);
    --shadow: 0 10px 35px rgba(0,0,0,0.35);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin:0; padding:0; background:var(--bg); color:var(--text);
    font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, 'Helvetica Neue', Arial;
  }}
  a {{ color: inherit; text-decoration: none; }}
  .wrap {{
    position: relative;
    min-height: 120vh;
    overflow: hidden;
    background:
      radial-gradient(60vmax 60vmax at 110% -10%, rgba(255,46,99,0.12), transparent 60%),
      radial-gradient(50vmax 50vmax at -10% 0%, rgba(255,102,179,0.10), transparent 60%);
  }}

  /* PLANETA (orb) */
  .orb {{
    position: absolute;
    right: -20vmax; top: -20vmax;
    width: 80vmax; height: 80vmax; border-radius: 50%;
    background: radial-gradient(circle at 30% 30%, rgba(255,102,179,0.35), rgba(255,46,99,0.15) 35%, rgba(255,46,99,0.05) 60%, transparent 70%);
    filter: blur(10px);
    animation: float 18s ease-in-out infinite alternate;
    pointer-events: none;
  }}
  @keyframes float {{
    from {{ transform: translate3d(0,0,0) rotate(0deg); }}
    to   {{ transform: translate3d(-2vmax,1.5vmax,0) rotate(8deg); }}
  }}

  /* Latice koje padaju */
  .petals {{
    position: fixed; inset: 0; pointer-events:none; z-index: 1;
  }}
  .petal {{
    position: absolute; top:-10vh;
    width: 10px; height: 10px; border-radius: 50%;
    background: radial-gradient(circle at 30% 30%, var(--brand2), var(--brand));
    opacity: 0.8; filter: blur(0.2px);
    animation: fall linear infinite;
  }}
  @keyframes fall {{
    0%   {{ transform: translateY(-10vh) translateX(0) rotate(0deg); opacity: 0; }}
    10%  {{ opacity: 0.9; }}
    100% {{ transform: translateY(120vh) translateX(10vw) rotate(360deg); opacity: 0; }}
  }}

  /* Hero sekcija */
  .container {{ position: relative; max-width: 1200px; margin: 0 auto; padding: 64px 20px; z-index: 2; }}
  .hero {{
    display: grid; grid-template-columns: 1.2fr 1fr; gap: 40px; align-items: center; margin-top: 40px;
  }}
  .badge {{
    display:inline-flex; align-items:center; gap:8px; padding:8px 12px; border:1px solid var(--ring); border-radius:999px; backdrop-filter: blur(6px);
    background: rgba(255,255,255,0.03);
  }}
  .title {{ font-size: clamp(36px, 4.8vw, 58px); line-height: 1.06; letter-spacing: -0.02em; margin: 12px 0 10px; }}
  .lead {{ color: var(--muted); font-size: clamp(16px, 2.2vw, 18px); }}

  .cta-row {{ display:flex; gap:14px; margin-top:28px; flex-wrap:wrap; }}
  .btn {{
    padding: 14px 18px; border-radius: 14px; background: #1a1a26; border:1px solid var(--ring);
    box-shadow: var(--shadow); transition: transform .18s ease, box-shadow .18s ease, background .18s ease;
    display:inline-flex; align-items:center; gap:10px; cursor:pointer;
  }}
  .btn:hover {{ transform: scale(1.03); background:#1d1d2b; box-shadow: 0 14px 40px rgba(0,0,0,0.4); }}

  /* VSL u krugu */
  .vsl-wrap {{ position: relative; width: 100%; aspect-ratio: 1/1; }}
  .vsl-circle {{
    position:absolute; inset:0; border-radius:50%;
    background: radial-gradient(circle at 35% 35%, rgba(255,102,179,0.25), rgba(255,46,99,0.15) 40%, rgba(255,46,99,0.08) 62%, transparent 70%);
    filter: blur(0.5px);
  }}
  .vsl {{
    position:absolute; inset:6%; border-radius:50%; overflow:hidden; border:1px solid var(--ring);
    box-shadow: 0 20px 50px rgba(0,0,0,0.6);
  }}
  .vsl video {{
    width:100%; height:100%; object-fit: cover;
  }}

  /* Sekcije */
  .grid-3 {{ display:grid; grid-template-columns: repeat(3,1fr); gap:16px; margin-top: 24px; }}
  .card {{
    background: var(--card); border:1px solid var(--ring); border-radius: 16px; padding: 18px; min-height: 120px;
    transition: transform .18s ease, box-shadow .18s ease; box-shadow: var(--shadow);
  }}
  .card:hover {{ transform: translateY(-3px); box-shadow: 0 18px 45px rgba(0,0,0,.45); }}

  .section-title {{ font-size: 22px; margin-top: 36px; margin-bottom: 8px; }}
  .muted {{ color: var(--muted); }}

  @media (max-width: 960px) {{
    .hero {{ grid-template-columns: 1fr; }}
  }}
</style>

<div class="wrap">
  <div class="orb"></div>

  <!-- Latice -->
  <div class="petals" id="petals"></div>

  <div class="container">
    <div class="badge">{BRAND_ARROW_SVG} <span>Dobrodošao u {APP_NAME}</span></div>
    <h1 class="title">Diskretna podrška mentalnom zdravlju — odmah, 24/7</h1>
    <p class="lead">Siguran AI saputnik koji sluša, postavlja blaga pitanja i pomaže ti da napraviš sledeći mali korak napred.</p>

    <div class="hero">
      <div>
        <div class="cta-row">
          <a class="btn" href="#benefits">{BRAND_ARROW_SVG} Pogledaj benefite</a>
          <a class="btn" href="#how">Kako radi</a>
          <a class="btn" href="#faq">FAQ</a>
        </div>

        <h3 class="section-title" id="benefits">Benefiti</h3>
        <div class="grid-3">
          <div class="card">
            <strong>Odmah dostupno</strong>
            <div class="muted">Bez zakazivanja, bez čekanja. Otvori i započni razgovor.</div>
          </div>
          <div class="card">
            <strong>Empatično</strong>
            <div class="muted">Topao ton, kratke poruke, fokus na sledeći mali korak.</div>
          </div>
          <div class="card">
            <strong>Privatno</strong>
            <div class="muted">Radi lokalno uz Ollama—bez API ključeva.</div>
          </div>
        </div>

        <h3 class="section-title" id="how">Kako radi</h3>
        <div class="card">
          <div class="muted">1. Pritisneš <em>Start chat</em> ispod • 2. AI te sluša i postavlja blaga pitanja • 3. Dobijaš male, praktične korake. U svakom trenutku možeš da prekineš ili obrišeš istoriju.</div>
        </div>

        <h3 class="section-title" id="faq">FAQ</h3>
        <div class="card">
          <strong>Da li je ovo zamena za terapeuta?</strong>
          <div class="muted">Ne. {APP_NAME} je podrška i nije medicinski savet. U hitnim situacijama, odmah kontaktiraj službe pomoći.</div>
        </div>
      </div>

      <!-- VSL u krugu -->
      <div class="vsl-wrap">
        <div class="vsl-circle"></div>
        <div class="vsl">
          <video src="{vsl_url}" autoplay muted playsinline loop></video>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
  // Dinamičko generisanje latica
  const petals = document.getElementById('petals');
  const PETALS_COUNT = 40; // broj latica u "cirkulaciji"
  function spawnPetal() {{
    const p = document.createElement('span');
    p.className = 'petal';
    const size = 6 + Math.random()*10;
    p.style.width = size + 'px';
    p.style.height = size + 'px';
    p.style.left = Math.random()*100 + 'vw';
    const dur = 8 + Math.random()*10;
    p.style.animationDuration = dur + 's';
    p.style.animationDelay = (-Math.random()*dur) + 's';
    p.style.opacity = 0.6 + Math.random()*0.4;
    petals.appendChild(p);
  }}
  for (let i=0;i<PETALS_COUNT;i++) spawnPetal();
  // Dodaj nove povremeno (zadržava konstantan efekat kroz skrol)
  setInterval(()=>{{ if (document.querySelectorAll('.petal').length < PETALS_COUNT+10) spawnPetal(); }}, 1500);
</script>
"""

st.components.v1.html(landing_html, height=900, scrolling=True)

st.markdown("---")
st.subheader("💬 Start chat")

# Session state za chat
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": SYSTEM_GUARDRAIL},
        {"role": "assistant", "content": "Zdravo! Kako se osećaš danas? Ako želiš, možemo da krenemo od nečeg malog što te muči."},
    ]

# Render dosadašnji razgovor (bez system poruke)
for m in st.session_state.messages:
    if m["role"] == "system":
        continue
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Unos korisnika
user_msg = st.chat_input("Napiši poruku…")
if user_msg:
    st.session_state.messages.append({"role": "user", "content": user_msg})
    with st.chat_message("user"):
        st.markdown(user_msg)

    # Poziv ka Ollama (stream)
    with st.chat_message("assistant"):
        placeholder = st.empty()
        acc = ""
        for chunk in ollama_chat(ollama_host, model, st.session_state.messages, stream=True):
            acc += chunk
            placeholder.markdown(acc)

        # Dodaj finalni odgovor u istoriju
        st.session_state.messages.append({"role": "assistant", "content": acc})

# Kontrole
col1, col2 = st.columns(2)
with col1:
    if st.button("🧹 Obriši istoriju razgovora"):
        st.session_state.messages = [
            {"role": "system", "content": SYSTEM_GUARDRAIL},
            {"role": "assistant", "content": "Počinjemo iz početka. Kako si danas?"},
        ]
        st.experimental_rerun()
with col2:
    st.caption("Napomena: {0} nije zamena za stručnu pomoć. U hitnim slučajevima, odmah pozovi lokalne službe.".format(APP_NAME))
