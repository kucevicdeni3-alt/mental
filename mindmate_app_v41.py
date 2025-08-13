import streamlit as st

# ========================
# PAGE CONFIG
# ========================
st.set_page_config(
    page_title="MindMate",
    page_icon="🌸",
    layout="wide"
)

# ========================
# CUSTOM CSS + NAVBAR + ANIMACIJE
# ========================
st.markdown("""
<style>
html, body, [class*="css"] {
    margin: 0;
    padding: 0;
}

/* Background gradient that changes on scroll */
body {
    background: linear-gradient(180deg, #0d0d15 0%, #1a1a2e 100%);
    transition: background 1s ease;
}
body.scrolled {
    background: linear-gradient(180deg, #1a1a2e 0%, #0d0d15 100%);
}

/* Navbar styles */
.k-nav {
    position: fixed;
    top: 20px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    gap: 16px;
    justify-content: center;
    align-items: center;
    padding: 12px 20px;
    background-color: rgba(10, 10, 15, 0.8);
    backdrop-filter: blur(8px);
    border-radius: 12px;
    transition: all 0.4s ease;
    margin: 6px auto;
    z-index: 999;
}
.k-nav a {
    text-decoration: none;
    font-weight: 600;
    padding: 6px 14px;
    border-radius: 8px;
    transition: all 0.3s ease;
    color: white;
}
.k-nav a:hover {
    background: rgba(255, 255, 255, 0.1);
    transform: scale(1.05);
}
.k-nav.scrolled {
    background-color: rgba(10, 10, 15, 0.95);
    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    padding: 8px 20px;
}

/* Fade-in on scroll */
.fade-in {
    opacity: 0;
    transform: translateY(20px);
    transition: opacity 1.5s ease, transform 1.5s ease;
}
.fade-in.visible {
    opacity: 1;
    transform: translateY(0);
}

/* Hero section */
.hero {
    position: relative;
    text-align: center;
    padding: 120px 20px 60px;
    color: white;
}
.hero h1 {
    font-size: clamp(2rem, 5vw, 3.5rem);
    margin-bottom: 20px;
}
.hero p {
    font-size: clamp(1rem, 2vw, 1.25rem);
    opacity: 0.85;
}
.planet {
    position: absolute;
    top: -100px;
    left: 50%;
    transform: translateX(-50%);
    width: 500px;
    height: 500px;
    background: radial-gradient(circle at center, rgba(255,102,179,0.4), transparent 70%);
    border-radius: 50%;
    filter: blur(80px);
    z-index: -1;
}

/* Trusted by */
.trusted {
    text-align: center;
    padding: 40px 0;
    color: white;
}
.trusted img {
    height: 40px;
    margin: 0 15px;
    opacity: 0.8;
    transition: opacity 0.5s ease;
}
.trusted img:hover {
    opacity: 1;
}

/* Testimonials */
.testimonials {
    display: flex;
    justify-content: center;
    gap: 20px;
    padding: 40px 20px;
}
.testimonial {
    background: rgba(255,255,255,0.05);
    padding: 20px;
    border-radius: 12px;
    width: 300px;
    text-align: center;
    color: white;
    transition: transform 0.3s ease;
}
.testimonial:hover {
    transform: translateY(-5px);
}

/* FAQ */
.faq {
    padding: 60px 20px;
    max-width: 800px;
    margin: 0 auto;
}
.faq-item {
    background: rgba(255,255,255,0.05);
    margin-bottom: 10px;
    border-radius: 8px;
    overflow: hidden;
}
.faq-question {
    padding: 15px;
    cursor: pointer;
    font-weight: bold;
    color: white;
}
.faq-answer {
    padding: 0 15px 15px;
    color: rgba(255,255,255,0.85);
    display: none;
}

/* Pricing Cards */
.pricing {
    display: flex;
    justify-content: center;
    gap: 20px;
    padding: 40px 20px;
}
.card {
    background: rgba(255,255,255,0.05);
    border-radius: 12px;
    padding: 20px;
    color: white;
    width: 300px;
    text-align: center;
    transition: transform 0.3s ease;
}
.card:hover {
    transform: translateY(-5px);
    background: rgba(255,255,255,0.1);
}
</style>

<div id="navbar" class="k-nav">
    <a href="#welcome">Welcome</a>
    <a href="#features">Features</a>
    <a href="#faq">FAQ</a>
    <a href="#pricing">Pricing</a>
</div>

<script>
window.addEventListener('scroll', function() {
    let navbar = document.getElementById('navbar');
    if (window.scrollY > 50) {
        navbar.classList.add('scrolled');
        document.body.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
        document.body.classList.remove('scrolled');
    }

    // Fade-in effect
    document.querySelectorAll('.fade-in').forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.top < window.innerHeight - 100) {
            el.classList.add('visible');
        }
    });
});
</script>
""", unsafe_allow_html=True)

# ========================
# HERO SECTION
# ========================
st.markdown("""
<div class="hero fade-in" id="welcome">
    <div class="planet"></div>
    <h1>Preusmeri energiju ka napretku</h1>
    <p>MindMate ti pomaže da upravljaš stresom, pratiš raspoloženje i gradiš mir svakog dana.</p>
    <iframe width="560" height="315" src="https://www.youtube.com/embed/1qK0c9J_h10"
        title="YouTube video player" frameborder="0" allowfullscreen></iframe>
</div>
""", unsafe_allow_html=True)

# ========================
# TRUSTED BY
# ========================
st.markdown("""
<div class="trusted fade-in">
    <p>Trusted by professionals worldwide</p>
    <img src="https://upload.wikimedia.org/wikipedia/commons/a/a6/Logo_NIKE.svg">
    <img src="https://upload.wikimedia.org/wikipedia/commons/0/0e/Netflix_logo.svg">
    <img src="https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg">
</div>
""", unsafe_allow_html=True)

# ========================
# TESTIMONIALS
# ========================
st.markdown("""
<div class="testimonials fade-in">
    <div class="testimonial">"MindMate mi je promenio život. Osećam se fokusiranije." – Ana, 29</div>
    <div class="testimonial">"Najbolja aplikacija za mentalno zdravlje." – Marko, 35</div>
    <div class="testimonial">"Koristim je svakog jutra." – Jelena, 24</div>
</div>
""", unsafe_allow_html=True)

# ========================
# FAQ
# ========================
st.markdown("""
<div class="faq fade-in" id="faq">
    <div class="faq-item">
        <div class="faq-question" onclick="this.nextElementSibling.style.display =
        this.nextElementSibling.style.display === 'block' ? 'none' : 'block'">
        Kako MindMate funkcioniše?</div>
        <div class="faq-answer">Pruža ti dnevne check-inove, alate za refleksiju i analitiku raspoloženja.</div>
    </div>
    <div class="faq-item">
        <div class="faq-question" onclick="this.nextElementSibling.style.display =
        this.nextElementSibling.style.display === 'block' ? 'none' : 'block'">
        Da li je besplatna?</div>
        <div class="faq-answer">Da, postoji besplatna verzija sa osnovnim funkcijama.</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ========================
# PRICING
# ========================
st.markdown("""
<div class="pricing fade-in" id="pricing">
    <div class="card">
        <h3>Free</h3>
        <p>Osnovne funkcije</p>
        <p>$0 / mesec</p>
    </div>
    <div class="card">
        <h3>Pro</h3>
        <p>Sve funkcije + analitika</p>
        <p>$9 / mesec</p>
    </div>
</div>
""", unsafe_allow_html=True)
