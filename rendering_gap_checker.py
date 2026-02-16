import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import json
import plotly.graph_objects as go
import os

# --- 1. THEME & UI CUSTOMIZATION ---
st.set_page_config(page_title="TITAN SEO AUDITOR", layout="wide", page_icon="🛡️")

# Custom CSS to force White Text on Dark Background
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    
    /* Global Background and Text */
    .stApp { background-color: #0b0e14; }
    html, body, [class*="css"], .stMarkdown, p, span, label { 
        font-family: 'Inter', sans-serif; 
        color: #ffffff !important; 
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 { color: #ffffff !important; font-weight: 700; }

    /* Metrics */
    div[data-testid="stMetricValue"] { color: #ffffff !important; font-weight: bold; font-size: 32px; }
    div[data-testid="stMetricLabel"] p { color: #ffffff !important; font-size: 16px; }

    /* Tables */
    .stTable, table, th, td {
        color: #ffffff !important;
        background-color: #161b22 !important;
        border: 1px solid #30363d !important;
    }

    /* Tabs */
    button[data-baseweb="tab"] p { color: #ffffff !important; font-size: 18px; }
    button[aria-selected="true"] { border-bottom-color: #FF4B4B !important; }

    /* Glowing Health Score */
    .health-score {
        font-size: 72px;
        font-weight: bold;
        text-align: center;
        color: #ffffff !important;
        text-shadow: 0 0 30px rgba(255, 255, 255, 0.4);
        margin: 20px 0;
    }

    /* Cards */
    .audit-card {
        background: #161b22;
        padding: 25px;
        border-radius: 12px;
        border: 1px solid #30363d;
        margin-bottom: 25px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA EXTRACTION ENGINE ---

def deep_audit(html, url):
    if not html: return None
    soup = BeautifulSoup(html, 'html.parser')
    
    # Metadata
    meta = {
        "Title": soup.title.string if soup.title else "N/A",
        "Description": (soup.find("meta", attrs={"name": "description"}) or {}).get("content", "N/A"),
        "Canonical": (soup.find("link", rel="canonical") or {}).get("href", "N/A"),
        "Robots": (soup.find("meta", attrs={"name": "robots"}) or {}).get("content", "index, follow"),
        "OG Title": (soup.find("meta", property="og:title") or {}).get("content", "N/A"),
        "Hreflang": [link.get('hreflang') for link in soup.find_all('link', hreflang=True)]
    }

    # Structure
    headings = {f"H{i}": [h.text.strip() for h in soup.find_all(f'h{i}')] for i in range(1, 4)}
    links = [a.get('href') for a in soup.find_all('a', href=True)]
    images = soup.find_all('img')
    img_data = {"total": len(images), "missing_alt": len([img for img in images if not img.get('alt')])}
    scripts = soup.find_all('script', src=True)
    
    # Schema
    schemas = soup.find_all("script", type="application/ld+json")
    schema_types = []
    for s in schemas:
        try:
            val = json.loads(s.string)
            if isinstance(val, dict): schema_types.append(val.get("@type"))
            elif isinstance(val, list): schema_types.append(val[0].get("@type"))
        except: pass

    # Content
    clean_text = soup.get_text()
    words = clean_text.split()
    
    return {
        "meta": meta,
        "headings": headings,
        "links": links,
        "images": img_data,
        "scripts": len(scripts),
        "word_count": len(words),
        "schema": schema_types,
        "html_size": len(html) / 1024,
        "raw_text": clean_text
    }

def run_analysis(url):
    # Static Fetch
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1)'}
    t0 = time.time()
    res = requests.get(url, headers=headers, timeout=15)
    t_static = time.time() - t0
    static_audit = deep_audit(res.text, url)
    
    # Rendered Fetch (Selenium)
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # Detect Environment (Cloud vs Local)
    try:
        if os.path.exists("/usr/bin/chromedriver"):
            service = Service("/usr/bin/chromedriver")
            driver = webdriver.Chrome(service=service, options=options)
        else:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        st.error(f"Hardware Error: {e}")
        st.stop()

    t1 = time.time()
    driver.get(url)
    time.sleep(5) 
    rendered_html = driver.page_source
    t_rendered = time.time() - t1
    rendered_audit = deep_audit(rendered_html, url)
    driver.quit()
    
    return static_audit, rendered_audit, t_static, t_rendered

# --- 3. UI DASHBOARD ---

st.title("🛡️ TITAN: Enterprise Technical Auditor")
st.write("Cross-analyzing server response vs. browser hydration.")

url_input = st.text_input("Enter Target Domain URL:", placeholder="https://www.nike.com/in")

if st.button("EXECUTE DEEP SCAN"):
    if url_input:
        with st.spinner("🕵️ CRAWLING: Running Googlebot and Selenium Engine..."):
            s, r, ts, tr = run_analysis(url_input)
            
            # --- CALCULATE HEALTH SCORE ---
            score = 100
            if r['meta']['Canonical'] == "N/A": score -= 15
            if not r['headings']['H1']: score -= 15
            if r['images']['missing_alt'] > 5: score -= 10
            js_gap = abs(r['word_count'] - s['word_count']) / r['word_count'] if r['word_count'] > 0 else 0
            if js_gap > 0.3: score -= 20

            # --- SCORE DISPLAY ---
            st.markdown(f"<div class='health-score'>{score}/100</div>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center; color:#ffffff; font-weight:bold;'>TITAN SEO HEALTH SCORE</p>", unsafe_allow_html=True)
            st.markdown("---")

            # --- EXECUTIVE COMPARISON TABLE ---
            st.subheader("📋 Executive Audit Matrix")
            comp_df = pd.DataFrame({
                "Metric": ["Word Count", "Total Links", "H1 Tag", "Canonical URL", "Schema Objects", "HTML Size (KB)", "Images Found", "Scripts Detected"],
                "Static (Server)": [s['word_count'], len(s['links']), s['headings']['H1'][0] if s['headings']['H1'] else "❌ Missing", s['meta']['Canonical'][:30]+"...", len(s['schema']), round(s['html_size'], 1), s['images']['total'], s['scripts']],
                "Rendered (JS)": [r['word_count'], len(r['links']), r['headings']['H1'][0] if r['headings']['H1'] else "❌ Missing", r['meta']['Canonical'][:30]+"...", len(r['schema']), round(r['html_size'], 1), r['images']['total'], r['scripts']],
                "Delta": [f"{r['word_count']-s['word_count']}", f"{len(r['links'])-len(s['links'])}", "Match", "Match", f"{len(r['schema'])-len(s['schema'])}", f"{round(r['html_size']-s['html_size'], 1)}", 0, r['scripts']-s['scripts']]
            })
            st.table(comp_df)

            # --- TABS FOR DEEP ANALYSIS ---
            tab1, tab2, tab3, tab4 = st.tabs(["💎 Content Integrity", "🏗️ Technical SEO", "🎨 Visual & Social", "🔍 Schema Explorer"])

            with tab1:
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("#### Headings Hierarchy")
                    for level in ['H1', 'H2', 'H3']:
                        st.write(f"**{level}:** {len(r['headings'][level])} found")
                        with st.expander(f"View {level} Tags"):
                            for h in r['headings'][level]: st.text(h)
                with col_b:
                    st.markdown("#### JavaScript Content Gap")
                    reliance = round(((r['word_count'] - s['word_count']) / r['word_count']) * 100, 1) if r['word_count'] > 0 else 0
                    fig = go.Figure(go.Indicator(
                        mode = "gauge+number", value = reliance,
                        title = {'text': "JS Dependency %", 'font': {'color': "white"}},
                        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#FF4B4B"}}
                    ))
                    fig.update_layout(paper_bgcolor="#161b22", font={'color': "white"}, height=280, margin=dict(l=20, r=20, t=50, b=20))
                    st.plotly_chart(fig, use_container_width=True)

            with tab2:
                st.subheader("Performance & Directives")
                c1, c2, c3 = st.columns(3)
                c1.metric("TTFB (Static)", f"{round(ts, 2)}s")
                c2.metric("Full Render Time", f"{round(tr, 2)}s")
                c3.metric("Images Missing Alt", r['images']['missing_alt'])
                
                st.write("**Robots Tag:**", r['meta']['Robots'])
                st.write("**Hreflang Configuration:**", r['meta']['Hreflang'] if r['meta']['Hreflang'] else "None Detected")

            with tab3:
                st.subheader("Social Graph & Metadata")
                st.write("**OpenGraph Title:**", r['meta']['OG Title'])
                st.write("**Meta Description:**", r['meta']['Description'])
                st.write("**Canonical URL:**", r['meta']['Canonical'])

            with tab4:
                st.subheader("JSON-LD Structured Data Explorer")
                if r['schema']:
                    st.success(f"Detected {len(r['schema'])} Schema Objects")
                    st.write("Types found:", list(set(r['schema'])))
                else:
                    st.error("No JSON-LD Detected on this URL.")

            # Recommendations
            st.markdown("---")
            st.subheader("🛡️ Titan Actionable Insights")
            if reliance > 25: st.warning("⚠️ High JS Reliance detected. Optimize for Server-Side Rendering (SSR).")
            if r['images']['missing_alt'] > 0: st.info(f"💡 Fix Alt-Text for {r['images']['missing_alt']} images to improve accessibility and image rankings.")
            if len(r['headings']['H1']) != 1: st.error("❌ Warning: Heading structure should contain exactly one H1 tag.")
