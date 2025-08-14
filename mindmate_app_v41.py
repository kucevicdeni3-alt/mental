import streamlit as st

# =================== PAGE CONFIG ===================
st.set_page_config(
    page_title="MindMate",
    page_icon="💜",
    layout="wide"
)

# =================== CUSTOM CSS + ANIMATIONS ===================
st.markdown(
    """
    <style>
    /* Navbar Styles */
    .k-nav {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 1.5rem;
        padding: 1rem;
        background: rgba(0,0,0,0.6);
        backdrop-filter: blur(8px);
        border-radius: 12px;
        position: sticky;
        top: 0;
        z-index: 100;
        animation: fadeInDown 0.6s ease-in-out;
    }
    .k-nav a {
        color: white;
        text-decoration: none;
        font-weight: 600;
        padding: 0.4rem 0.8rem;
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    .k-nav a:hover {
        background: linear-gradient(90deg, #7b2ff7, #f107a3);
        transform: scale(1.1);
    }
    @keyframes fadeInDown {
        from {opacity: 0; transform: translateY(-10px);}
        to {opacity: 1; transform: translateY(0);}
    }

    /* Glow Planet Background */
    .hero-glow {
        background: radial-gradient(circle at center, rgba(123,47,247,0.4) 0%, transparent 70%);
        border-radius: 50%;
        position: absolute;
        width: 500px;
        height: 500px;
        filter: blur(80px);
        left: 50%;
        top: 10%;
        transform: translateX(-50%);
        z-index: -1;
    }

    /* Fade-in Animation */
    .fade-in {
        animation: fadeIn 1.5s ease-in-out;
    }
    @keyframes fadeIn {
        from {opacity: 0;}
        to {opacity: 1;}
    }

    /* Section Titles */
    h1, h2, h3 {
        font-family: 'Segoe UI', sans-serif;
        font-weight: 700;
    }

    /* Button Hover */
    .cta-btn:hover {
        transform: scale(1.05);
        transition: 0.3s ease-in-out;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# =================== NAVBAR ===================
st.markdown(
    """
    <div class="k-nav">
        <a href="#welcome">Welcome</a>
        <a href="#pocetna">Početna</a>
        <a href="#chat">Chat</a>
        <a href="#check-in">Check-in</a>
        <a href="#analitika">Analitika</a>
    </div>
    """,
    unsafe_allow_html=True
)

# =================== HERO SECTION ===================
st.markdown('<div class="hero-glow"></div>', unsafe_allow_html=True)

st.markdown("## 💜 MindMate – Tvoj AI saveznik za mentalno zdravlje", unsafe_allow_html=True)
st.write("Brini o svom mentalnom zdravlju uz dnevne check-inove, analitiku napretka i personalizovane savete.")

# Hook poruka
st.markdown(
    "<h2 class='fade-in'>Započni put ka mirnijem i srećnijem životu uz pomoć AI podrške.</h2>",
    unsafe_allow_html=True
)

# VSL – YouTube embed
st.video("https://youtu.be/1qK0c9J_h10")
# =================== METRICS SECTION ===================
st.markdown("---")
st.markdown("## 📊 Naši Rezultati", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
col1.metric("Korisnika", "12K+", "🌱")
col2.metric("Prosečno zadovoljstvo", "97%", "💜")
col3.metric("Dnevni check-in", "5 min", "⚡")

# =================== TRUSTED BY / TESTIMONIALS ===================
st.markdown("---")
st.markdown("## 🤝 Trusted by", unsafe_allow_html=True)
st.write("Više od 12,000 korisnika i 50+ kompanija koristi MindMate svakodnevno.")

tb1, tb2, tb3 = st.columns(3)
with tb1:
    st.image("https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg", width=100)
with tb2:
    st.image("https://upload.wikimedia.org/wikipedia/commons/0/08/Google_Logo.svg", width=100)
with tb3:
    st.image("https://upload.wikimedia.org/wikipedia/commons/a/a9/Amazon_logo.svg", width=100)

# Testimonials
st.markdown("### Šta kažu naši korisnici:")
t1, t2, t3 = st.columns(3)
with t1:
    st.markdown(
        """
        > “MindMate mi je pomogao da se izborim sa stresom i organizujem svoj dan.”
        — **Maja, 29**
        """
    )
with t2:
    st.markdown(
        """
        > “Neverovatno jednostavan alat, koristim ga svako jutro.”
        — **Milan, 34**
        """
    )
with t3:
    st.markdown(
        """
        > “Konačno aplikacija koja me razume.”
        — **Jelena, 41**
        """
    )

# =================== FEATURES SECTION ===================
st.markdown("---")
st.markdown("## 🚀 Zašto MindMate?", unsafe_allow_html=True)

f1, f2, f3 = st.columns(3)
with f1:
    st.image("https://cdn-icons-png.flaticon.com/512/2910/2910768.png", width=60)
    st.markdown("### Personalizovan pristup")
    st.write("AI prilagođen tvom stilu komunikacije i potrebama.")
with f2:
    st.image("https://cdn-icons-png.flaticon.com/512/1827/1827504.png", width=60)
    st.markdown("### Brzi check-in")
    st.write("Dnevni check-in od 2 pitanja, samo 5 minuta dnevno.")
with f3:
    st.image("https://cdn-icons-png.flaticon.com/512/3208/3208750.png", width=60)
    st.markdown("### Analitika napretka")
    st.write("Prati svoje raspoloženje i napredak kroz vreme uz jednostavne grafikone.")
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
