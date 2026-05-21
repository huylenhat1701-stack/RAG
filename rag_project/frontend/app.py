"""
Streamlit Frontend - Hệ thống Đọc Tài Liệu Thông Minh
Smart Document Reader v2.0
Sinh viên: Lê Nhật Huy - B23DCAT126 | Phạm Hải Đông - B23DCVT090
"""

import json
import html as _html
import os
import time
import requests
import streamlit as st
from pathlib import Path
from datetime import datetime

# Create a requests session that ignores proxy environment variables
requests_session = requests.Session()
requests_session.trust_env = False

# ============================================================
# Cấu hình trang
# ============================================================
st.set_page_config(
    page_title="Smart Document Reader",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# URL của FastAPI Backend
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000/api/v1")

# ============================================================
# CSS — Light / Neutral Academic Theme
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
/* ═══════════════════════════════════════════════════════════
   STREAMLIT THEME INJECTION
   Override Streamlit's built-in CSS variables so the default
   red/purple accent doesn't bleed through on tabs, sliders,
   checkboxes, etc.
   ═══════════════════════════════════════════════════════════ */
:root,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"] {
    --primary-color:            #1e40af !important;
    --background-color:         #f5f4f1 !important;
    --secondary-background-color: #ffffff !important;
    --text-color:               #0d0d0d !important;
    --font:                     'Inter', system-ui, -apple-system, sans-serif !important;
}

/* ── DESIGN TOKENS ──────────────────────────────────────── */
:root {
    --bg:          #f6f5f2;
    --surface:     #ffffff;
    --surface-alt: #f0ede8;
    --border:      #d6d3cc;
    --border-mid:  #b8b4ac;

    /* Text — maximum readability, pure black family */
    --tx1:  #0d0d0d;   /* headings, labels — near-black  */
    --tx2:  #1a1a1a;   /* body text — very dark          */
    --tx3:  #4a4744;   /* captions, meta — medium dark   */
    --tx4:  #7a7672;   /* placeholder, muted             */

    /* Accent — stable blue (not Streamlit red) */
    --ac:   #1e40af;
    --ac-s: #eff6ff;
    --ac-m: #bfdbfe;

    /* Semantic */
    --ok:   #14532d;  --ok-bg:   #f0fdf4;  --ok-bd:  #86efac;
    --wn:   #78350f;  --wn-bg:   #fffbeb;  --wn-bd:  #fde68a;
    --er:   #7f1d1d;  --er-bg:   #fef2f2;  --er-bd:  #fecaca;

    --r-sm: 6px;
    --r:    10px;
    --r-lg: 14px;
    --sh-sm: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.05);
    --sh:    0 4px 12px rgba(0,0,0,0.10), 0 1px 4px rgba(0,0,0,0.06);
}

/* ── BASE & RESET ────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important;
    color: #1a1a1a !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

/* Headings and bold custom HTML use sharper color */
h1, h2, h3, h4, h5, h6,
.page-header h1,
.section-heading,
.sidebar-title {
    font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important;
    color: #0a0a0a !important;
    font-weight: 700;
}

.main { background: var(--bg) !important; }
.stApp { background: var(--bg) !important; }
.block-container { padding-top: 1.5rem !important; }

::-webkit-scrollbar       { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--surface-alt); }
::-webkit-scrollbar-thumb { background: var(--border-mid); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--tx4); }

/* ── SIDEBAR ─────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] > div { padding-top: 1.25rem !important; }
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label {
    color: var(--tx2) !important;
}

.sidebar-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--tx1) !important;
    letter-spacing: -0.01em;
    margin: 0 0 0.15rem 0;
}
.sidebar-subtitle {
    font-size: 0.7rem;
    color: var(--tx3) !important;
    margin-bottom: 1rem;
}

/* Status pill */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.28rem 0.7rem;
    border-radius: 9999px;
    font-size: 0.73rem;
    font-weight: 600;
    letter-spacing: 0.01em;
}
.status-pill.online  { background: var(--ok-bg); color: var(--ok); border: 1px solid var(--ok-bd); }
.status-pill.offline { background: var(--er-bg); color: var(--er); border: 1px solid var(--er-bd); }
.status-pill.warning { background: var(--wn-bg); color: var(--wn); border: 1px solid var(--wn-bd); }

.status-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    display: inline-block;
    flex-shrink: 0;
}
.status-dot.green  { background: #22c55e; }
.status-dot.red    { background: #ef4444; }
.status-dot.yellow { background: #f59e0b; }

.system-detail {
    font-size: 0.71rem;
    color: var(--tx3) !important;
    line-height: 1.9;
    margin-top: 0.65rem;
}
.system-detail b   { color: var(--tx2) !important; font-weight: 600; }
.system-detail code {
    background: var(--surface-alt);
    padding: 0.05rem 0.3rem;
    border-radius: 3px;
    font-size: 0.67rem;
    color: var(--ac) !important;
    border: 1px solid var(--border);
    font-family: 'SF Mono', 'Fira Code', monospace !important;
}

/* ── STAT CARDS ──────────────────────────────────────────── */
.stat-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.45rem;
    margin: 0.75rem 0;
}
.stat-card {
    background: var(--surface-alt);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    padding: 0.6rem 0.7rem;
    text-align: center;
}
.stat-value {
    font-size: 1.45rem;
    font-weight: 700;
    color: var(--tx1) !important;
    line-height: 1.2;
}
.stat-label {
    font-size: 0.62rem;
    color: var(--tx4) !important;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-top: 0.1rem;
}

/* Credits */
.credits { text-align: center; padding: 0.5rem 0; }
.credits p { font-size: 0.7rem; color: var(--tx4) !important; margin: 0.1rem 0; }
.credits .name { color: var(--tx3) !important; font-weight: 600; }

/* ── PAGE HEADER ─────────────────────────────────────────── */
.page-header {
    border-bottom: 2px solid #0d0d0d;
    padding-bottom: 0.9rem;
    margin-bottom: 1.5rem;
}
.page-header h1 {
    font-size: 1.6rem;
    font-weight: 800;
    color: #0a0a0a !important;
    margin: 0 0 0.25rem;
    letter-spacing: -0.03em;
    font-family: 'Inter', sans-serif !important;
}
.page-header p {
    font-size: 0.82rem;
    color: #4a4744 !important;
    margin: 0;
    font-style: italic;
    font-weight: 400;
}

/* ── TABS ────────────────────────────────────────────────── */
/* Tab list strip */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1.5px solid var(--border) !important;
    border-radius: 0 !important;
    gap: 0 !important;
    padding: 0 !important;
    margin-bottom: 1.25rem !important;
}
/* Individual tab */
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    margin-bottom: -1.5px !important;
    padding: 0.55rem 1rem !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
    color: var(--tx4) !important;
    transition: color 0.12s ease !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: var(--tx2) !important;
    background: transparent !important;
}
/* Active tab — black underline, no Streamlit red */
.stTabs [aria-selected="true"] {
    color: var(--tx1) !important;
    border-bottom: 2px solid var(--tx1) !important;
    background: transparent !important;
}
/* Hide Streamlit's own animated indicator bar (the red one) */
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }
.stTabs [data-baseweb="tab-border"]    { display: none !important; }

/* ── SECTION TYPOGRAPHY ──────────────────────────────────── */
.section-heading {
    font-size: 1rem;
    font-weight: 700;
    color: #0a0a0a !important;
    margin: 0 0 0.25rem;
    letter-spacing: -0.02em;
    font-family: 'Inter', sans-serif !important;
}
.section-caption {
    font-size: 0.78rem;
    color: #4a4744 !important;
    font-style: italic;
    margin-bottom: 1.1rem;
    font-weight: 400;
}
.doc-selector-label {
    font-size: 0.7rem;
    color: #4a4744 !important;
    font-weight: 600;
    margin-bottom: 0.35rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

/* ── DOC CARDS ───────────────────────────────────────────── */
.doc-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 0.8rem 1rem;
    margin-bottom: 0.45rem;
    display: flex;
    align-items: flex-start;
    gap: 0.8rem;
    box-shadow: var(--sh-sm);
    transition: border-color 0.15s, box-shadow 0.15s;
}
.doc-card:hover {
    border-color: var(--ac-m);
    box-shadow: var(--sh);
}
.doc-type-tag {
    font-size: 0.6rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: var(--tx3) !important;
    background: var(--surface-alt);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 0.12rem 0.38rem;
    min-width: 2.7rem;
    text-align: center;
    margin-top: 0.12rem;
    flex-shrink: 0;
    font-family: 'SF Mono', 'Fira Code', monospace !important;
}
.doc-info  { flex: 1; min-width: 0; }
.doc-name  {
    font-weight: 600;
    color: var(--tx1) !important;
    font-size: 0.87rem;
    margin-bottom: 0.18rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.doc-meta    { font-size: 0.71rem; color: var(--tx4) !important; line-height: 1.65; }
.doc-preview { font-size: 0.74rem; color: var(--tx3) !important; font-style: italic; margin-top: 0.2rem; line-height: 1.5; }

/* ── BADGES ──────────────────────────────────────────────── */
.badge {
    display: inline-block;
    padding: 0.12rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.62rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.badge-indexed   { background: var(--ok-bg); color: var(--ok); border: 1px solid var(--ok-bd); }
.badge-uploading { background: var(--wn-bg); color: var(--wn); border: 1px solid var(--wn-bd); }
.badge-indexing  { background: var(--ac-s);  color: var(--ac); border: 1px solid var(--ac-m); }
.badge-error     { background: var(--er-bg); color: var(--er); border: 1px solid var(--er-bd); }

/* ── DOC DOWNLOAD LINKS ──────────────────────────────────── */
.doc-link {
    display: inline-block;
    padding: 0.13rem 0.45rem;
    border-radius: var(--r-sm);
    background: var(--surface-alt);
    color: var(--ac) !important;
    font-size: 0.68rem;
    text-decoration: none;
    border: 1px solid var(--border);
    margin-right: 0.25rem;
    transition: background 0.1s, border-color 0.1s;
}
.doc-link:hover { background: var(--ac-s); border-color: var(--ac-m); }

/* ── CHAT MESSAGES ───────────────────────────────────────── */
.chat-user-msg {
    background: #eff6ff;
    border-left: 3.5px solid #1e40af;
    padding: 0.9rem 1.1rem;
    border-radius: 0 var(--r) var(--r) 0;
    margin: 0.6rem 0;
    color: #0d0d0d !important;
    line-height: 1.8;
    font-size: 0.875rem;
    font-weight: 500;
    font-family: 'Inter', sans-serif !important;
}
.chat-user-msg strong {
    color: #0a0a0a !important;
    font-weight: 700;
    display: block;
    margin-bottom: 0.3rem;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #1e40af !important;
}
.chat-ai-msg {
    background: #ffffff;
    border: 1px solid #d6d3cc;
    border-left: 3.5px solid #1e40af;
    padding: 0.9rem 1.1rem;
    border-radius: 0 var(--r) var(--r) 0;
    margin: 0.6rem 0;
    color: #0d0d0d !important;
    line-height: 1.85;
    font-size: 0.875rem;
    font-family: 'Inter', sans-serif !important;
    box-shadow: 0 2px 8px rgba(30,64,175,0.07), 0 1px 3px rgba(0,0,0,0.05);
}
.chat-ai-msg strong {
    color: #0a0a0a !important;
    font-weight: 700;
    display: block;
    margin-bottom: 0.3rem;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #1e40af !important;
}
.chat-ai-msg br + * , .chat-ai-msg p {
    color: #1a1a1a !important;
}
.source-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    color: #1e40af !important;
    padding: 0.15rem 0.55rem;
    border-radius: 9999px;
    font-size: 0.68rem;
    font-weight: 600;
    margin: 0.1rem;
    font-family: 'Inter', sans-serif !important;
}

/* ── SUMMARY / EXERCISE BOX ──────────────────────────────── */
.summary-box {
    background: #ffffff;
    border: 1px solid #d6d3cc;
    border-left: 4px solid #1e40af;
    border-radius: 0 var(--r-lg) var(--r-lg) 0;
    padding: 1.3rem 1.5rem;
    line-height: 1.9;
    color: #1a1a1a !important;
    font-size: 0.9rem;
    font-family: 'Inter', sans-serif !important;
    box-shadow: 0 2px 10px rgba(30,64,175,0.07), 0 1px 3px rgba(0,0,0,0.05);
}
.summary-box h4 {
    color: #1e40af !important;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.85rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #e5e7eb;
    font-family: 'Inter', sans-serif !important;
}

/* ── READER ──────────────────────────────────────────────── */
.reader-container {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 1.5rem 2rem;
    max-height: 620px;
    overflow-y: auto;
    line-height: 1.9;
    font-size: 0.9rem;
    color: var(--tx2) !important;
    box-shadow: var(--sh-sm);
}
.reader-stats {
    display: flex;
    gap: 1.5rem;
    margin-bottom: 0.9rem;
    padding-bottom: 0.7rem;
    border-bottom: 1px solid var(--border);
}
.reader-stat-item { font-size: 0.73rem; color: var(--tx4) !important; }
.reader-stat-item b { color: var(--tx3) !important; }

/* ── EMPTY STATE ─────────────────────────────────────────── */
.empty-state {
    text-align: center;
    padding: 3rem 2rem;
    border: 1.5px dashed var(--border);
    border-radius: var(--r-lg);
    background: var(--surface);
    margin: 0.75rem 0;
}
.empty-state h3 {
    color: var(--tx2) !important;
    font-size: 0.95rem;
    font-weight: 600;
    margin: 0 0 0.3rem;
}
.empty-state p {
    color: var(--tx3) !important;
    font-size: 0.8rem;
    max-width: 360px;
    margin: 0 auto;
    font-style: italic;
    line-height: 1.6;
}

/* Mode badges (RAG / Full-Context) */
.mode-badge-rag  { background: var(--ac-s); color: var(--ac); border: 1px solid var(--ac-m); padding: 0.12rem 0.5rem; border-radius: 9999px; font-size: 0.65rem; font-weight: 700; }
.mode-badge-full { background: var(--ok-bg); color: var(--ok); border: 1px solid var(--ok-bd); padding: 0.12rem 0.5rem; border-radius: 9999px; font-size: 0.65rem; font-weight: 700; }

/* ═══════════════════════════════════════════════════════════
   STREAMLIT COMPONENT OVERRIDES
   These fix the file uploader dark theme, input borders,
   button colors, and other component-level issues.
   ═══════════════════════════════════════════════════════════ */

/* ── App background ──────────────────────────────────────── */
.stApp, [data-testid="stAppViewContainer"] { background: var(--bg) !important; }
[data-testid="stHeader"] { background: var(--bg) !important; border-bottom: 1px solid var(--border) !important; }

/* ── Main content padding ────────────────────────────────── */
.main .block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; }

/* ── Buttons ─────────────────────────────────────────────── */
.stButton > button {
    border-radius: var(--r-sm) !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    font-family: 'Inter', sans-serif !important;
    background: var(--surface) !important;
    color: #0d0d0d !important;
    border: 1px solid var(--border-mid) !important;
    padding: 0.38rem 0.9rem !important;
    transition: all 0.15s ease !important;
    box-shadow: var(--sh-sm) !important;
    letter-spacing: 0.01em !important;
}
.stButton > button:hover {
    background: var(--surface-alt) !important;
    border-color: #1e40af !important;
    color: #1e40af !important;
    box-shadow: 0 0 0 2px #eff6ff !important;
}
.stButton > button[kind="primary"] {
    background: #1e40af !important;
    color: #ffffff !important;
    border-color: #1e40af !important;
    box-shadow: 0 2px 8px rgba(30,64,175,0.25) !important;
}
.stButton > button[kind="primary"]:hover {
    background: #1d3a9e !important;
    border-color: #1d3a9e !important;
    box-shadow: 0 3px 12px rgba(30,64,175,0.35) !important;
}

/* ── Download button ─────────────────────────────────────── */
[data-testid="stDownloadButton"] > button {
    background: var(--surface) !important;
    color: var(--ac) !important;
    border: 1px solid var(--ac-m) !important;
    border-radius: var(--r-sm) !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
}
[data-testid="stDownloadButton"] > button:hover {
    background: var(--ac-s) !important;
}

/* ── Text inputs, selects, textareas ─────────────────────── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div,
[data-baseweb="input"] input,
[data-baseweb="textarea"] textarea {
    background: var(--surface) !important;
    color: #0d0d0d !important;
    border: 1.5px solid var(--border-mid) !important;
    border-radius: var(--r-sm) !important;
    font-size: 0.86rem !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 400 !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #1e40af !important;
    box-shadow: 0 0 0 2.5px #eff6ff !important;
    outline: none !important;
}

/* Select dropdown menu */
[data-baseweb="popover"] { background: var(--surface) !important; border: 1px solid var(--border) !important; }
[data-baseweb="menu"] li { color: var(--tx2) !important; font-size: 0.84rem !important; }
[data-baseweb="menu"] li:hover { background: var(--surface-alt) !important; }
[role="option"]  { color: var(--tx2) !important; }

/* ── Multiselect ─────────────────────────────────────────── */
[data-baseweb="tag"] {
    background: var(--ac-s) !important;
    border: 1px solid var(--ac-m) !important;
    border-radius: 9999px !important;
}
[data-baseweb="tag"] span { color: var(--ac) !important; font-size: 0.72rem !important; }
[data-baseweb="tag"] button { color: var(--ac) !important; }

/* ── Chat input ──────────────────────────────────────────── */
[data-testid="stChatInput"] textarea,
.stChatInputContainer textarea {
    background: var(--surface) !important;
    color: #0d0d0d !important;
    border: 1.5px solid var(--border-mid) !important;
    border-radius: var(--r) !important;
    font-size: 0.88rem !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 400 !important;
}
[data-testid="stChatInput"] textarea:focus,
.stChatInputContainer textarea:focus {
    border-color: #1e40af !important;
    box-shadow: 0 0 0 2px #eff6ff !important;
}
.stChatInputContainer {
    background: var(--bg) !important;
    border-top: 1px solid var(--border) !important;
    padding-top: 0.5rem !important;
}

/* ── File uploader — force light theme ───────────────────── */
[data-testid="stFileUploader"] {
    background: var(--surface) !important;
}
[data-testid="stFileUploadDropzone"] {
    background: var(--surface) !important;
    border: 1.5px dashed var(--border-mid) !important;
    border-radius: var(--r) !important;
    color: var(--tx2) !important;
}
[data-testid="stFileUploadDropzone"]:hover {
    border-color: var(--ac) !important;
    background: var(--ac-s) !important;
}
/* Override Streamlit's injected dark background on the inner section */
[data-testid="stFileUploadDropzone"] section {
    background: transparent !important;
    color: var(--tx2) !important;
}
[data-testid="stFileUploadDropzone"] button {
    background: var(--surface-alt) !important;
    color: var(--tx1) !important;
    border: 1px solid var(--border-mid) !important;
    border-radius: var(--r-sm) !important;
    font-size: 0.8rem !important;
}
[data-testid="stFileUploadDropzone"] button:hover {
    background: var(--ac-s) !important;
    border-color: var(--ac) !important;
    color: var(--ac) !important;
}
/* The "Drag and drop" / label text */
[data-testid="stFileUploadDropzone"] span,
[data-testid="stFileUploadDropzone"] p,
[data-testid="stFileUploadDropzone"] small {
    color: var(--tx3) !important;
    font-size: 0.82rem !important;
}
/* Remove duplicate "upload" text that Streamlit adds via SVG label */
[data-testid="stFileUploadDropzone"] .uploadInstruction { display: none !important; }

/* ── Slider ──────────────────────────────────────────────── */
[data-baseweb="slider"] [role="slider"] {
    background: var(--ac) !important;
    border-color: var(--ac) !important;
}
[data-baseweb="slider"] [data-testid="stSliderTrack"] { background: var(--border) !important; }
[data-baseweb="slider"] [data-testid="stSliderTrackFill"] { background: var(--ac) !important; }

/* ── Radio buttons ───────────────────────────────────────── */
.stRadio label {
    font-size: 0.82rem !important;
    color: var(--tx2) !important;
}
.stRadio [data-baseweb="radio"] div:first-child {
    border-color: var(--border-mid) !important;
}
.stRadio [aria-checked="true"] div:first-child {
    border-color: var(--ac) !important;
    background: var(--ac) !important;
}

/* ── Selectbox label + widget ────────────────────────────── */
.stSelectbox label { font-size: 0.8rem !important; color: var(--tx2) !important; font-weight: 600 !important; }
[data-baseweb="select"] > div {
    background: var(--surface) !important;
    border: 1px solid var(--border-mid) !important;
    border-radius: var(--r-sm) !important;
}
[data-baseweb="select"] > div:focus-within {
    border-color: var(--ac) !important;
    box-shadow: 0 0 0 2px var(--ac-s) !important;
}
[data-baseweb="select"] [data-testid="stMarkdownContainer"] p { color: var(--tx2) !important; }

/* ── Labels (all widgets) ────────────────────────────────── */
.stTextInput label, .stTextArea label, .stMultiSelect label,
.stSlider label, .stSelectbox label {
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    color: var(--tx2) !important;
}

/* ── Alerts ──────────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: var(--r-sm) !important;
    font-size: 0.83rem !important;
}
.stSuccess, [data-baseweb="notification"][kind="positive"] {
    background: var(--ok-bg) !important;
    border: 1px solid var(--ok-bd) !important;
    color: var(--ok) !important;
}
.stError, [data-baseweb="notification"][kind="negative"] {
    background: var(--er-bg) !important;
    border: 1px solid var(--er-bd) !important;
    color: var(--er) !important;
}
.stWarning, [data-baseweb="notification"][kind="warning"] {
    background: var(--wn-bg) !important;
    border: 1px solid var(--wn-bd) !important;
    color: var(--wn) !important;
}
.stInfo, [data-baseweb="notification"][kind="info"] {
    background: var(--ac-s) !important;
    border: 1px solid var(--ac-m) !important;
    color: var(--ac) !important;
}

/* ── Expanders ───────────────────────────────────────────── */
[data-testid="stExpander"] summary {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
    font-size: 0.83rem !important;
    font-weight: 600 !important;
    color: var(--tx1) !important;
    padding: 0.5rem 0.75rem !important;
}
[data-testid="stExpander"] summary:hover { background: var(--surface-alt) !important; }
[data-testid="stExpander"] > div { border: 1px solid var(--border) !important; border-top: none !important; background: var(--surface) !important; border-radius: 0 0 var(--r-sm) var(--r-sm) !important; }

/* ── Spinner ─────────────────────────────────────────────── */
[data-testid="stSpinner"] { color: var(--ac) !important; }

/* ── Caption / small text ────────────────────────────────── */
.stCaption, [data-testid="stCaptionContainer"] {
    color: var(--tx4) !important;
    font-size: 0.7rem !important;
}

/* ── Divider ─────────────────────────────────────────────── */
hr { border-color: var(--border) !important; margin: 0.85rem 0 !important; }

/* ── Sidebar divider ─────────────────────────────────────── */
section[data-testid="stSidebar"] hr { border-color: var(--border) !important; }

/* ── Chat message avatars area ───────────────────────────── */
[data-testid="stChatMessage"] {
    background: transparent !important;
    padding: 0.2rem 0 !important;
}

/* ══════════════════════════════════════════════════════════
   QUIZ COMPETITION STYLES
   ══════════════════════════════════════════════════════════ */
.quiz-header {
    background: linear-gradient(135deg, #1e40af 0%, #3b82f6 50%, #60a5fa 100%);
    border-radius: var(--r-lg);
    padding: 1.5rem 2rem;
    margin-bottom: 1.5rem;
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 4px 20px rgba(30,64,175,0.3);
}
.quiz-header h2 {
    color: #ffffff !important;
    font-size: 1.3rem;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.02em;
    font-family: 'Inter', sans-serif !important;
}
.quiz-header .quiz-meta {
    font-size: 0.8rem;
    color: rgba(255,255,255,0.85);
    margin-top: 0.2rem;
}
.quiz-score-badge {
    background: rgba(255,255,255,0.2);
    border: 2px solid rgba(255,255,255,0.4);
    border-radius: 9999px;
    padding: 0.5rem 1.2rem;
    color: #ffffff;
    font-size: 1.1rem;
    font-weight: 800;
    text-align: center;
    min-width: 100px;
}
.quiz-score-badge .score-label {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    opacity: 0.85;
    display: block;
}
.quiz-progress-bar {
    height: 8px;
    background: #e2e8f0;
    border-radius: 9999px;
    margin-bottom: 1.5rem;
    overflow: hidden;
}
.quiz-progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #1e40af, #3b82f6);
    border-radius: 9999px;
    transition: width 0.4s ease;
}
.quiz-question-card {
    background: #ffffff;
    border: 1.5px solid #d6d3cc;
    border-radius: var(--r-lg);
    padding: 1.8rem 2rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 4px 16px rgba(0,0,0,0.07);
}
.quiz-question-num {
    font-size: 0.72rem;
    font-weight: 700;
    color: #1e40af;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    margin-bottom: 0.6rem;
    font-family: 'Inter', sans-serif !important;
}
.quiz-question-text {
    font-size: 1.05rem;
    font-weight: 600;
    color: #0a0a0a;
    line-height: 1.65;
    font-family: 'Inter', sans-serif !important;
    margin: 0;
}
.quiz-option-btn {
    width: 100%;
    text-align: left;
    background: #f8f9fa;
    border: 2px solid #e5e7eb;
    border-radius: var(--r);
    padding: 0.85rem 1.1rem;
    margin: 0.35rem 0;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 500;
    color: #1a1a1a;
    transition: all 0.15s ease;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-family: 'Inter', sans-serif !important;
}
.quiz-option-btn:hover {
    border-color: #1e40af;
    background: #eff6ff;
    color: #1e40af;
}
.quiz-option-key {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px; height: 28px;
    border-radius: 50%;
    background: #e5e7eb;
    color: #4a4744;
    font-size: 0.78rem;
    font-weight: 700;
    flex-shrink: 0;
    transition: all 0.15s ease;
}
.quiz-opt-correct {
    background: #f0fdf4 !important;
    border-color: #22c55e !important;
    color: #14532d !important;
}
.quiz-opt-correct .quiz-option-key {
    background: #22c55e !important;
    color: #ffffff !important;
}
.quiz-opt-wrong {
    background: #fef2f2 !important;
    border-color: #ef4444 !important;
    color: #7f1d1d !important;
}
.quiz-opt-wrong .quiz-option-key {
    background: #ef4444 !important;
    color: #ffffff !important;
}
.quiz-feedback-correct {
    background: #f0fdf4;
    border: 1.5px solid #86efac;
    border-left: 4px solid #22c55e;
    border-radius: 0 var(--r) var(--r) 0;
    padding: 0.9rem 1.1rem;
    color: #14532d;
    font-size: 0.88rem;
    font-weight: 500;
    margin: 0.6rem 0;
    font-family: 'Inter', sans-serif !important;
}
.quiz-feedback-wrong {
    background: #fef2f2;
    border: 1.5px solid #fecaca;
    border-left: 4px solid #ef4444;
    border-radius: 0 var(--r) var(--r) 0;
    padding: 0.9rem 1.1rem;
    color: #7f1d1d;
    font-size: 0.88rem;
    font-weight: 500;
    margin: 0.6rem 0;
    font-family: 'Inter', sans-serif !important;
}
.quiz-explanation {
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: var(--r-sm);
    padding: 0.7rem 0.9rem;
    color: #78350f;
    font-size: 0.82rem;
    margin-top: 0.5rem;
    font-style: italic;
    font-family: 'Inter', sans-serif !important;
}
.quiz-result-card {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #1e40af 100%);
    border-radius: var(--r-lg);
    padding: 2.5rem 2rem;
    text-align: center;
    color: #ffffff;
    box-shadow: 0 8px 32px rgba(30,64,175,0.35);
    margin: 1rem 0;
}
.quiz-result-trophy { font-size: 3.5rem; margin-bottom: 0.75rem; display: block; }
.quiz-result-score {
    font-size: 3rem;
    font-weight: 900;
    color: #fbbf24;
    letter-spacing: -0.03em;
    line-height: 1;
    font-family: 'Inter', sans-serif !important;
}
.quiz-result-label {
    font-size: 0.85rem;
    color: rgba(255,255,255,0.75);
    margin-top: 0.3rem;
    font-family: 'Inter', sans-serif !important;
}
.quiz-result-grade {
    display: inline-block;
    background: rgba(255,255,255,0.15);
    border: 2px solid rgba(255,255,255,0.3);
    border-radius: 9999px;
    padding: 0.4rem 1.2rem;
    font-size: 1rem;
    font-weight: 700;
    color: #ffffff;
    margin-top: 0.8rem;
    font-family: 'Inter', sans-serif !important;
}
.quiz-stat-row {
    display: flex;
    justify-content: center;
    gap: 2rem;
    margin-top: 1.2rem;
}
.quiz-stat-item { text-align: center; }
.quiz-stat-num { font-size: 1.5rem; font-weight: 800; color: #ffffff; font-family: 'Inter', sans-serif !important; }
.quiz-stat-lbl { font-size: 0.7rem; color: rgba(255,255,255,0.65); text-transform: uppercase; letter-spacing: 0.07em; }
.quiz-review-item {
    background: #ffffff;
    border: 1px solid #d6d3cc;
    border-radius: var(--r);
    padding: 1rem 1.2rem;
    margin: 0.5rem 0;
    border-left: 4px solid #e5e7eb;
}
.quiz-review-item.correct { border-left-color: #22c55e; }
.quiz-review-item.wrong   { border-left-color: #ef4444; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# Hàm gọi API  (không thay đổi)
# ============================================================
def api_get(endpoint: str, params: dict = None):
    try:
        resp = requests_session.get(f"{BACKEND_URL}{endpoint}", params=params, timeout=600)
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"Lỗi {resp.status_code}: {resp.text}"
    except requests.ConnectionError:
        return None, "Không kết nối được Backend. Hãy chạy: `start.bat`"
    except Exception as e:
        return None, str(e)


def api_post(endpoint: str, json_data: dict = None, files=None):
    try:
        if files:
            resp = requests_session.post(f"{BACKEND_URL}{endpoint}", files=files, timeout=300)
        else:
            resp = requests_session.post(f"{BACKEND_URL}{endpoint}", json=json_data, timeout=600)
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"Lỗi {resp.status_code}: {resp.json().get('detail', resp.text)}"
    except requests.ConnectionError:
        return None, "Không kết nối được Backend."
    except requests.Timeout:
        return None, "Hết thời gian chờ — tài liệu có thể quá lớn. Hãy thử lại hoặc chọn tài liệu nhỏ hơn."
    except Exception as e:
        return None, str(e)


def api_delete(endpoint: str):
    try:
        resp = requests_session.delete(f"{BACKEND_URL}{endpoint}", timeout=120)
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"Lỗi {resp.status_code}: {resp.text}"
    except Exception as e:
        return None, str(e)


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def get_file_type_tag(file_type: str) -> str:
    return (file_type or "FILE").upper()


def get_status_badge(status: str) -> str:
    badges = {
        "INDEXED":  '<span class="badge badge-indexed">Indexed</span>',
        "INDEXING": '<span class="badge badge-indexing">Processing</span>',
        "UPLOADED": '<span class="badge badge-uploading">Pending</span>',
        "ERROR":    '<span class="badge badge-error">Error</span>',
    }
    return badges.get(status, f'<span class="badge">{status}</span>')


# ============================================================
# Sidebar
# ============================================================
with st.sidebar:
    st.markdown('<p class="sidebar-title">Smart Document Reader</p>', unsafe_allow_html=True)
    st.markdown('<p class="sidebar-subtitle">Local RAG · ChromaDB · LM Studio</p>', unsafe_allow_html=True)

    # ── Single health check call ──────────────────────────
    health_data, health_err = api_get("/health")

    if health_err:
        st.markdown('<span class="status-pill offline"><span class="status-dot red"></span>Backend offline</span>', unsafe_allow_html=True)
        st.caption(health_err)
    else:
        codex_ok  = health_data.get("codex_connected", False)
        rag_ok    = health_data.get("rag_ready", False)
        kb_ok     = health_data.get("kb_loaded", False)
        model_name   = health_data.get("model_name", "local-model")
        chunk_count  = health_data.get("kb_chunk_count", 0)
        ctx_tokens   = health_data.get("context_window_tokens", "?")
        max_chars    = health_data.get("max_content_chars", 0)

        if codex_ok:
            st.markdown('<span class="status-pill online"><span class="status-dot green"></span>System online</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-pill warning"><span class="status-dot yellow"></span>LM Studio not connected</span>', unsafe_allow_html=True)

        def _check(ok): return "✓" if ok else "✗"

        st.markdown(f"""
        <div class="system-detail">
            {_check(codex_ok)} LM Studio &nbsp;·&nbsp;
            {_check(rag_ok)} RAG Engine &nbsp;·&nbsp;
            {_check(kb_ok)} KB<br>
            Model: <code>{model_name}</code><br>
            Vectors: <b>{chunk_count} chunks</b><br>
            Context: <b>{ctx_tokens:,} tokens</b> / <b>{max_chars:,} chars</b>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # ── Single documents + history call ──────────────────
    docs_data, _ = api_get("/documents")
    hist_data, _ = api_get("/chat/history", {"limit": 1})

    total_docs = docs_data.get("total", 0) if docs_data else 0
    total_hist = hist_data.get("total", 0) if hist_data else 0

    if docs_data and docs_data.get("documents"):
        docs_sb      = docs_data["documents"]
        indexed_sb   = sum(1 for d in docs_sb if d["status"] == "INDEXED")
        chunks_sb    = sum(d.get("chunk_count", 0) for d in docs_sb)

        st.markdown(f"""
        <div class="stat-grid">
            <div class="stat-card"><div class="stat-value">{total_docs}</div><div class="stat-label">Documents</div></div>
            <div class="stat-card"><div class="stat-value">{total_hist}</div><div class="stat-label">Questions</div></div>
            <div class="stat-card"><div class="stat-value">{indexed_sb}</div><div class="stat-label">Indexed</div></div>
            <div class="stat-card"><div class="stat-value">{chunks_sb}</div><div class="stat-label">Chunks</div></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="stat-grid">
            <div class="stat-card"><div class="stat-value">{total_docs}</div><div class="stat-label">Documents</div></div>
            <div class="stat-card"><div class="stat-value">{total_hist}</div><div class="stat-label">Questions</div></div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    st.markdown("""
    <div class="credits">
        <p>Sinh viên thực hiện</p>
        <p class="name">Lê Nhật Huy — B23DCAT126</p>
        <p class="name">Phạm Hải Đông — B23DCVT090</p>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# Page Header
# ============================================================
st.markdown("""
<div class="page-header">
    <h1>Smart Document Reader</h1>
    <p>Local RAG + ChromaDB + LM Studio (Gemma) — chạy hoàn toàn offline</p>
</div>
""", unsafe_allow_html=True)


# ============================================================
# Tabs
# ============================================================
tab_docs, tab_read, tab_summary, tab_exercise, tab_chat, tab_history = st.tabs([
    "Tài Liệu",
    "Đọc",
    "Tóm Tắt",
    "Bài Tập",
    "Hỏi & Đáp",
    "Lịch Sử",
])


# ============================================================
# TAB 1: Quản lý tài liệu
# ============================================================
with tab_docs:
    st.markdown('<p class="section-heading">Quản Lý Tài Liệu</p>', unsafe_allow_html=True)

    col_upload_area, col_upload_btn = st.columns([3, 1])

    with col_upload_area:
        uploaded_file = st.file_uploader(
            "Kéo thả hoặc chọn file để upload",
            type=["pdf", "txt", "docx", "md"],
            help="Hỗ trợ PDF, DOCX, TXT, Markdown — tối đa 50MB",
            label_visibility="visible",
        )

    with col_upload_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if uploaded_file:
            size_str = format_file_size(len(uploaded_file.getvalue()))
            st.info(f"**{uploaded_file.name}** · {size_str}")

        if st.button("Upload & Xử lý", type="primary", use_container_width=True, disabled=not uploaded_file):
            with st.spinner("Đang upload và xử lý tài liệu..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                result, err = api_post("/documents/upload", files=files)
                if err:
                    st.error(err)
                else:
                    st.success(f"Đã upload: **{result['file_name']}**")
                    st.caption("Đang index trong nền...")
                    time.sleep(1.5)
                    st.rerun()

    st.divider()

    docs_data, err = api_get("/documents")
    if err:
        st.error(err)
    elif not docs_data or docs_data["total"] == 0:
        st.markdown("""
        <div class="empty-state">
            <h3>Chưa có tài liệu nào</h3>
            <p>Upload tài liệu đầu tiên (PDF, DOCX, TXT, MD) để bắt đầu.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        docs = docs_data["documents"]
        indexed = sum(1 for d in docs if d["status"] == "INDEXED")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<div class="stat-card"><div class="stat-value">{docs_data["total"]}</div><div class="stat-label">Tổng tài liệu</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="stat-card"><div class="stat-value">{indexed}</div><div class="stat-label">Đã index</div></div>', unsafe_allow_html=True)
        with c3:
            total_chunks = sum(d.get("chunk_count", 0) for d in docs)
            st.markdown(f'<div class="stat-card"><div class="stat-value">{total_chunks}</div><div class="stat-label">Tổng chunks</div></div>', unsafe_allow_html=True)
        with c4:
            total_size = sum(d.get("file_size", 0) for d in docs)
            st.markdown(f'<div class="stat-card"><div class="stat-value">{format_file_size(total_size)}</div><div class="stat-label">Dung lượng</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        for doc in docs:
            file_type_tag = get_file_type_tag(doc.get("file_type", ""))
            badge         = get_status_badge(doc["status"])
            size_str      = format_file_size(doc.get("file_size", 0))
            chunks        = doc.get("chunk_count", 0)
            pages         = doc.get("page_count", 0)

            try:
                dt = datetime.fromisoformat(doc.get("uploaded_at", "").replace("Z", "+00:00"))
                time_str = dt.strftime("%d/%m/%Y %H:%M")
            except Exception:
                time_str = str(doc.get("uploaded_at", ""))[:16]

            col_main, col_status, col_actions = st.columns([4, 1.5, 1.5])

            with col_main:
                preview = doc.get("content_preview", "") or ""
                preview_short = (preview[:100] + "…") if len(preview) > 100 else preview
                preview_html = f'<div class="doc-preview">{preview_short}</div>' if preview_short else ""

                st.markdown(f"""
                <div class="doc-card">
                    <div class="doc-type-tag">{file_type_tag}</div>
                    <div class="doc-info">
                        <div class="doc-name">{doc['file_name']}</div>
                        <div class="doc-meta">
                            {size_str} &nbsp;·&nbsp; {chunks} chunks
                            {f" &nbsp;·&nbsp; {pages} trang" if pages else ""}
                            &nbsp;·&nbsp; {time_str}
                        </div>
                        {preview_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with col_status:
                st.markdown(f"<div style='padding-top:0.85rem;'>{badge}</div>", unsafe_allow_html=True)
                if doc.get("error_message"):
                    st.caption(doc['error_message'][:50])

            with col_actions:
                st.markdown("<div style='padding-top:0.5rem;'></div>", unsafe_allow_html=True)
                if st.button("Xóa", key=f"del_{doc['id']}", help=f"Xóa {doc['file_name']}"):
                    result, err = api_delete(f"/documents/{doc['id']}")
                    if err:
                        st.error(err)
                    else:
                        st.success("Đã xóa.")
                        st.rerun()

                file_url      = f"{BACKEND_URL}/documents/{doc['id']}/download?source=original"
                extracted_url = f"{BACKEND_URL}/documents/{doc['id']}/download?source=extracted"
                st.markdown(f"""
                <div style='margin-top:0.5rem;'>
                    <a class='doc-link' href='{file_url}' target='_blank'>File gốc</a>
                    <a class='doc-link' href='{extracted_url}' target='_blank'>Text AI</a>
                </div>
                """, unsafe_allow_html=True)

        if st.button("Làm mới danh sách"):
            st.rerun()


# ============================================================
# TAB 2: Đọc Tài Liệu
# ============================================================
with tab_read:
    st.markdown('<p class="section-heading">Đọc Nội Dung Tài Liệu</p>', unsafe_allow_html=True)

    docs_data, err = api_get("/documents")
    if err:
        st.error(err)
    elif not docs_data or docs_data["total"] == 0:
        st.markdown("""
        <div class="empty-state">
            <h3>Chưa có tài liệu để đọc</h3>
            <p>Hãy upload tài liệu ở tab "Tài Liệu" trước.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        docs = docs_data["documents"]
        doc_options = {
            f"{d['file_name']} ({format_file_size(d.get('file_size', 0))})": d['id']
            for d in docs
        }

        selected_doc = st.selectbox(
            "Chọn tài liệu cần đọc",
            options=list(doc_options.keys()),
            index=0,
        )

        if selected_doc:
            doc_id = doc_options[selected_doc]

            if st.button("Đọc tài liệu", type="primary"):
                with st.spinner("Đang tải nội dung tài liệu..."):
                    content_data, err = api_get(f"/documents/{doc_id}/content")

                if err:
                    st.error(err)
                elif content_data:
                    st.markdown(f"""
                    <div class="reader-stats">
                        <div class="reader-stat-item"><b>{content_data.get('page_count', 0)}</b> trang</div>
                        <div class="reader-stat-item"><b>{content_data.get('word_count', 0):,}</b> từ</div>
                        <div class="reader-stat-item"><b>{content_data.get('char_count', 0):,}</b> ký tự</div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown(f"""
                    <div class="reader-container">
                        {content_data['content'][:50000].replace(chr(10), '<br>')}
                    </div>
                    """, unsafe_allow_html=True)

                    st.download_button(
                        "Tải về dạng Text",
                        data=content_data['content'],
                        file_name=f"{content_data['file_name']}.txt",
                        mime="text/plain",
                    )


# ============================================================
# TAB 3: Tóm Tắt AI
# ============================================================
with tab_summary:
    st.markdown('<p class="section-heading">Tóm Tắt Tài Liệu</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-caption">Sử dụng Local LLM (Gemma) để tạo tóm tắt thông minh.</p>', unsafe_allow_html=True)

    docs_data, err = api_get("/documents")
    if err:
        st.error(err)
    elif not docs_data or docs_data["total"] == 0:
        st.markdown("""
        <div class="empty-state">
            <h3>Chưa có tài liệu để tóm tắt</h3>
            <p>Upload tài liệu trước để AI có thể tóm tắt nội dung.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        docs = docs_data["documents"]
        indexed_docs = [d for d in docs if d["status"] == "INDEXED"]

        if not indexed_docs:
            st.warning("Chưa có tài liệu nào được index xong. Vui lòng chờ xử lý hoàn tất.")
        else:
            doc_options = {
                f"{d['file_name']}": d['id']
                for d in indexed_docs
            }

            selected_doc = st.selectbox(
                "Chọn tài liệu cần tóm tắt",
                options=list(doc_options.keys()),
                index=0,
                key="summary_doc_select"
            )

            if selected_doc:
                doc_id = doc_options[selected_doc]
                current_doc = next((d for d in indexed_docs if d['id'] == doc_id), None)

                if current_doc and current_doc.get("summary"):
                    st.markdown(f"""
                    <div class="summary-box">
                        <h4>Tóm tắt (đã lưu)</h4>
                        {current_doc['summary'].replace(chr(10), '<br>')}
                    </div>
                    """, unsafe_allow_html=True)

                    if st.button("Tạo lại tóm tắt"):
                        with st.spinner("AI đang đọc và tóm tắt tài liệu..."):
                            result, err = api_post(f"/documents/{doc_id}/summarize")
                        if err:
                            st.error(err)
                        elif result:
                            st.markdown(f"""
                            <div class="summary-box">
                                <h4>Tóm tắt mới</h4>
                                {result['summary'].replace(chr(10), '<br>')}
                            </div>
                            """, unsafe_allow_html=True)
                            st.caption(f"Model: `{result.get('model_used', 'N/A')}`")
                else:
                    if st.button("Tạo tóm tắt", type="primary"):
                        with st.spinner("AI đang đọc và tóm tắt tài liệu... (15–30 giây)"):
                            result, err = api_post(f"/documents/{doc_id}/summarize")
                        if err:
                            st.error(err)
                        elif result:
                            st.markdown(f"""
                            <div class="summary-box">
                                <h4>Tóm tắt</h4>
                                {result['summary'].replace(chr(10), '<br>')}
                            </div>
                            """, unsafe_allow_html=True)
                            st.caption(f"Model: `{result.get('model_used', 'N/A')}`")
                            st.success("Tóm tắt đã được lưu.")


# ============================================================
# TAB 4: Thi Trắc Nghiệm (Quiz Competition)
# ============================================================
with tab_exercise:

    # ── Session state cho quiz ───────────────────────────────
    for _k, _v in {
        "quiz_questions": [],      # Danh sách câu hỏi
        "quiz_index": 0,           # Câu đang thi
        "quiz_score": 0,           # Số câu đúng
        "quiz_answered": {},       # {idx: "A"/"B"/"C"/"D"}
        "quiz_phase": "setup",     # "setup" | "playing" | "result"
        "quiz_doc_name": "",
        "quiz_doc_id": 0,
        "quiz_model": "",
        "quiz_wrong_chunks": [],   # chunk_id của các câu trả lời sai
        "show_learning_path": False,
        "learning_path_data": None,
    }.items():
        if _k not in st.session_state:
            st.session_state[_k] = _v

    # ── Lấy dữ liệu tài liệu ─────────────────────────────────
    qz_docs_data, qz_err = api_get("/documents")
    qz_indexed = []
    if qz_docs_data and qz_docs_data.get("documents"):
        qz_indexed = [d for d in qz_docs_data["documents"] if d["status"] == "INDEXED"]

    # ════════════════════════════════════════════════════════
    # PHASE 1: SETUP — chọn tài liệu, số câu, bắt đầu thi
    # ════════════════════════════════════════════════════════
    if st.session_state.quiz_phase == "setup":
        st.markdown('<p class="section-heading">🏆 Thi Trắc Nghiệm</p>', unsafe_allow_html=True)
        st.markdown('<p class="section-caption">AI tạo bộ câu hỏi từ tài liệu — trả lời từng câu, xem điểm số ngay.</p>', unsafe_allow_html=True)

        if qz_err:
            st.error(qz_err)
        elif not qz_indexed:
            st.markdown("""
            <div class="empty-state">
                <h3>Chưa có tài liệu để thi</h3>
                <p>Upload và index tài liệu ở tab "Tài Liệu" trước.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            qz_doc_opts = {d["file_name"]: d["id"] for d in qz_indexed}

            col_sel, col_num = st.columns([3, 1])
            with col_sel:
                qz_selected = st.selectbox("📄 Chọn tài liệu để thi", list(qz_doc_opts.keys()), key="qz_doc_sel")
            with col_num:
                qz_count = st.slider("Số câu", 3, 20, 10, key="qz_count")

            st.markdown("<br>", unsafe_allow_html=True)

            if st.button("🚀 Bắt Đầu Thi", type="primary", use_container_width=True):
                doc_id = qz_doc_opts[qz_selected]
                with st.spinner(f"🤖 AI đang tạo {qz_count} câu hỏi từ tài liệu... (30–60 giây)"):
                    result, err = api_post(f"/documents/{doc_id}/quiz", json_data={"count": qz_count})
                if err:
                    st.error(f"Lỗi tạo quiz: {err}")
                elif result and result.get("questions"):
                    st.session_state.quiz_questions = result["questions"]
                    st.session_state.quiz_index = 0
                    st.session_state.quiz_score = 0
                    st.session_state.quiz_answered = {}
                    st.session_state.quiz_phase = "playing"
                    st.session_state.quiz_doc_name = result.get("file_name", qz_selected)
                    st.session_state.quiz_doc_id = doc_id
                    st.session_state.quiz_model = result.get("model_used", "")
                    st.rerun()
                else:
                    st.error("Không tạo được câu hỏi. Hãy thử lại.")

    # ════════════════════════════════════════════════════════
    # PHASE 2: PLAYING — hiển thị từng câu hỏi
    # ════════════════════════════════════════════════════════
    elif st.session_state.quiz_phase == "playing":
        qs   = st.session_state.quiz_questions
        idx  = st.session_state.quiz_index
        total = len(qs)
        score = st.session_state.quiz_score
        pct   = int((idx / total) * 100) if total else 0

        # Header + Score
        st.markdown(f"""
        <div class="quiz-header">
            <div>
                <h2>🏆 Đang Thi</h2>
                <div class="quiz-meta">📄 {st.session_state.quiz_doc_name} &nbsp;·&nbsp; Câu {idx+1}/{total}</div>
            </div>
            <div class="quiz-score-badge">
                <span class="score-label">Điểm</span>
                {score}/{idx}
            </div>
        </div>
        <div class="quiz-progress-bar">
            <div class="quiz-progress-fill" style="width:{pct}%"></div>
        </div>
        """, unsafe_allow_html=True)

        q = qs[idx]
        q_id   = q.get("id", idx + 1)
        q_text = q.get("question", "")
        opts   = q.get("options", {})
        correct = q.get("answer", "A")
        expl   = q.get("explanation", "")

        already_answered = idx in st.session_state.quiz_answered

        # Card câu hỏi — escape text từ AI
        safe_q_text = _html.escape(str(q_text))
        st.markdown(f"""
        <div class="quiz-question-card">
            <div class="quiz-question-num">Câu {idx + 1} / {total}</div>
            <p class="quiz-question-text">{safe_q_text}</p>
        </div>
        """, unsafe_allow_html=True)

        # Nút đáp án A/B/C/D
        if not already_answered:
            col1, col2 = st.columns(2)
            cols = [col1, col2, col1, col2]
            for i, key in enumerate(["A", "B", "C", "D"]):
                text = opts.get(key, "")
                with cols[i]:
                    if st.button(
                        f"{key}. {text}",
                        key=f"qz_opt_{idx}_{key}",
                        use_container_width=True,
                    ):
                        st.session_state.quiz_answered[idx] = key
                        is_correct = (key == correct)
                        if is_correct:
                            st.session_state.quiz_score += 1

                        # Gọi API submit kết quả để cập nhật BKT
                        chunk_id = q.get("chunk_id", "")
                        if chunk_id:
                            api_post(
                                f"/documents/{st.session_state.quiz_doc_id}/quiz/submit",
                                json_data={
                                    "session_id": "default_user",
                                    "chunk_id": chunk_id,
                                    "is_correct": is_correct
                                }
                            )
                            # Thu thập chunk_id của câu sai để tạo lộ trình
                            if not is_correct and chunk_id not in st.session_state.quiz_wrong_chunks:
                                st.session_state.quiz_wrong_chunks.append(chunk_id)
                        st.rerun()
        else:
            # Đã trả lời — hiển thị kết quả
            chosen = st.session_state.quiz_answered[idx]
            col1, col2 = st.columns(2)
            cols = [col1, col2, col1, col2]
            for i, key in enumerate(["A", "B", "C", "D"]):
                text = opts.get(key, "")
                if key == correct:
                    css = "quiz-opt-correct"
                elif key == chosen and key != correct:
                    css = "quiz-opt-wrong"
                else:
                    css = ""
                with cols[i]:
                    safe_text = _html.escape(str(text))
                    st.markdown(f"""
                    <div class="quiz-option-btn {css}">
                        <span class="quiz-option-key">{key}</span>
                        {safe_text}
                    </div>
                    """, unsafe_allow_html=True)

            # Phản hồi
            if chosen == correct:
                st.markdown(f'<div class="quiz-feedback-correct">✅ <strong>Chính xác!</strong> Bạn đã chọn đúng đáp án <strong>{correct}</strong>.</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="quiz-feedback-wrong">❌ <strong>Sai rồi!</strong> Bạn chọn <strong>{chosen}</strong>, đáp án đúng là <strong>{correct}</strong>.</div>', unsafe_allow_html=True)

            if expl:
                safe_expl = _html.escape(str(expl))
                st.markdown(f'<div class="quiz-explanation">💡 {safe_expl}</div>', unsafe_allow_html=True)

            step_expl = q.get("step_by_step_explanation", "")
            if step_expl:
                st.markdown('<div class="quiz-explanation"><strong>Bước giải chi tiết (CoT):</strong></div>', unsafe_allow_html=True)
                st.info(step_expl)

            st.markdown("<br>", unsafe_allow_html=True)

            # Nút điều hướng
            nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
            with nav_col1:
                if idx > 0:
                    if st.button("← Câu trước", key="qz_prev"):
                        st.session_state.quiz_index -= 1
                        st.rerun()
            with nav_col3:
                if idx < total - 1:
                    if st.button("Câu tiếp →", key="qz_next", type="primary"):
                        st.session_state.quiz_index += 1
                        st.rerun()
                else:
                    if st.button("🏁 Xem Kết Quả", key="qz_finish", type="primary"):
                        st.session_state.quiz_phase = "result"
                        st.rerun()

    # ════════════════════════════════════════════════════════
    # PHASE 3: RESULT — bảng kết quả cuối
    # ════════════════════════════════════════════════════════
    elif st.session_state.quiz_phase == "result":
        qs      = st.session_state.quiz_questions
        total   = len(qs)
        score   = st.session_state.quiz_score
        wrong   = total - score
        pct_val = int((score / total) * 100) if total else 0

        if pct_val >= 90:
            trophy, grade = "🏆", "Xuất Sắc"
        elif pct_val >= 75:
            trophy, grade = "🥇", "Giỏi"
        elif pct_val >= 55:
            trophy, grade = "🥈", "Khá"
        else:
            trophy, grade = "🥉", "Cần Cố Gắng"

        st.markdown(f"""
        <div class="quiz-result-card">
            <span class="quiz-result-trophy">{trophy}</span>
            <div class="quiz-result-score">{pct_val}%</div>
            <div class="quiz-result-label">{score} đúng / {total} câu &nbsp;·&nbsp; {st.session_state.quiz_doc_name}</div>
            <div class="quiz-result-grade">{grade}</div>
            <div class="quiz-stat-row">
                <div class="quiz-stat-item">
                    <div class="quiz-stat-num">{score}</div>
                    <div class="quiz-stat-lbl">✅ Đúng</div>
                </div>
                <div class="quiz-stat-item">
                    <div class="quiz-stat-num">{wrong}</div>
                    <div class="quiz-stat-lbl">❌ Sai</div>
                </div>
                <div class="quiz-stat-item">
                    <div class="quiz-stat-num">{total}</div>
                    <div class="quiz-stat-lbl">📝 Tổng</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Nút hành động
        btn1, btn2, btn3, btn4 = st.columns(4)
        with btn1:
            if st.button("🔁 Thi Lại", use_container_width=True):
                st.session_state.quiz_phase = "setup"
                st.session_state.quiz_questions = []
                st.session_state.quiz_answered = {}
                st.session_state.quiz_score = 0
                st.session_state.quiz_index = 0
                st.session_state.quiz_wrong_chunks = []
                st.session_state.show_learning_path = False
                st.session_state.learning_path_data = None
                st.rerun()
        with btn2:
            if st.button("📋 Xem Lại Đáp Án", use_container_width=True):
                st.session_state["show_review"] = not st.session_state.get("show_review", False)
                st.rerun()
        with btn3:
            # Nút Lộ Trình — chỉ hiện khi có câu sai
            if wrong > 0:
                lp_label = "✅ Đã có Lộ Trình" if st.session_state.show_learning_path else "🗺️ Lộ Trình Học Tập"
                if st.button(lp_label, use_container_width=True, type="primary" if not st.session_state.show_learning_path else "secondary"):
                    if not st.session_state.show_learning_path:
                        # Gọi API tạo lộ trình
                        with st.spinner("🤖 AI đang phân tích và tạo lộ trình học tập..."):
                            lp_result, lp_err = api_post(
                                f"/documents/{st.session_state.quiz_doc_id}/learning-path",
                                json_data={
                                    "session_id": "default_user",
                                    "wrong_chunk_ids": st.session_state.quiz_wrong_chunks,
                                }
                            )
                        if lp_err:
                            st.error(f"Lỗi tạo lộ trình: {lp_err}")
                        else:
                            st.session_state.learning_path_data = lp_result
                            st.session_state.show_learning_path = True
                    else:
                        st.session_state.show_learning_path = False
                    st.rerun()
        with btn4:
            if st.button("🏠 Về Trang Chủ", use_container_width=True):
                st.session_state.quiz_phase = "setup"
                st.rerun()

        # ── PHẦN LỘ TRÌNH HỌC TẬP ────────────────────────────────
        if st.session_state.show_learning_path and st.session_state.learning_path_data:
            lp = st.session_state.learning_path_data
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, #1e3a5f 0%, #1e40af 100%);
                border-radius: 14px;
                padding: 1.5rem 2rem;
                margin-bottom: 1.2rem;
                color: #fff;
            ">
                <div style="font-size:1.15rem;font-weight:800;letter-spacing:-0.02em;margin-bottom:0.3rem;">
                    🗺️ Lộ Trình Học Tập Cá Nhân Hóa
                </div>
                <div style="font-size:0.82rem;opacity:0.85;">
                    Dựa trên kết quả của bạn — AI đã phân tích và đề xuất các chủ đề cần ôn luyện
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Nhận xét tổng thể
            overall_msg = lp.get("overall_message", "")
            if overall_msg:
                st.markdown(f"""
                <div style="
                    background:#fffbeb;border:1px solid #fde68a;border-left:4px solid #f59e0b;
                    border-radius:0 10px 10px 0;padding:0.9rem 1.2rem;margin-bottom:1.2rem;
                    color:#78350f;font-size:0.9rem;font-weight:500;
                ">💬 {_html.escape(overall_msg)}</div>
                """, unsafe_allow_html=True)

            lp_items = lp.get("items", [])
            if not lp_items:
                st.info("Không tìm thấy nội dung cụ thể để tạo lộ trình. Hãy thử làm thêm câu hỏi!")
            else:
                import re
                for step_idx, item in enumerate(lp_items, 1):
                    topic      = _html.escape(str(item.get("topic", f"Chủ đề {step_idx}")))
                    
                    raw_snippet = str(item.get("content_snippet", ""))
                    # Lọc bỏ ký tự lạ (như 🗹 hoặc unicode rác từ PDF)
                    # Giu lai ky tu co the hien thi (loai bo garbage chars tu PDF)
                    clean_snippet = "".join(
                        ch for ch in raw_snippet
                        if ch.isprintable() and ord(ch) < 0x2000
                    )
                    snippet    = _html.escape(clean_snippet)
                    
                    advice     = _html.escape(str(item.get("advice", "")))
                    
                    bkt_pct    = int(item.get("bkt_probability", 0))

                    # Màu thanh tiến trình BKT
                    if bkt_pct >= 70:
                        bar_color = "#22c55e"
                        bkt_label = f"Hiểu bài: {bkt_pct}% ✅"
                    elif bkt_pct >= 40:
                        bar_color = "#f59e0b"
                        bkt_label = f"Cần ôn: {bkt_pct}% ⚠️"
                    else:
                        bar_color = "#ef4444"
                        bkt_label = f"Yếu: {bkt_pct}% 🔴" if bkt_pct > 0 else "Chưa có dữ liệu"

                    st.markdown(f"""
                    <div style="
                        background:#fff;border:1.5px solid #e5e7eb;border-radius:12px;
                        padding:1.2rem 1.5rem;margin-bottom:0.9rem;
                        box-shadow:0 2px 10px rgba(30,64,175,0.06);
                        border-left:5px solid #1e40af;
                    ">
                        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.6rem;">
                            <div style="display:flex;align-items:center;gap:0.6rem;">
                                <span style="
                                    background:#1e40af;color:#fff;border-radius:50%;
                                    width:26px;height:26px;display:inline-flex;
                                    align-items:center;justify-content:center;
                                    font-size:0.75rem;font-weight:700;flex-shrink:0;
                                ">{step_idx}</span>
                                <strong style="color:#0a0a0a;font-size:0.97rem;">{topic}</strong>
                            </div>
                            <span style="font-size:0.72rem;color:#6b7280;">{bkt_label}</span>
                        </div>
                        <!-- Thanh BKT -->
                        <div style="height:5px;background:#e5e7eb;border-radius:9999px;margin-bottom:0.8rem;overflow:hidden;">
                            <div style="height:100%;width:{bkt_pct}%;background:{bar_color};border-radius:9999px;transition:width 0.4s;"></div>
                        </div>
                        <!-- Nội dung trích dẫn -->
                        <div style="
                            background:#f8f9fb;border:1px solid #e5e7eb;border-radius:8px;
                            padding:0.7rem 0.9rem;margin-bottom:0.7rem;
                            font-size:0.82rem;color:#374151;line-height:1.65;
                            max-height:100px;overflow:hidden;
                            display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;
                        ">
                            📖 <em>{snippet[:300]}{"..." if len(snippet) > 300 else ""}</em>
                        </div>
                        <!-- Lời khuyên AI -->
                        <div style="
                            background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;
                            padding:0.65rem 0.9rem;font-size:0.85rem;color:#1e40af;font-weight:500;
                        ">
                            💡 {advice}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                # Nút thi lại với nội dung đã ôn
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🚀 Thi Lại Bộ Câu Hỏi Mới (Tập Trung Điểm Yếu)", type="primary", use_container_width=True):
                    st.session_state.quiz_phase = "setup"
                    st.session_state.quiz_questions = []
                    st.session_state.quiz_answered = {}
                    st.session_state.quiz_score = 0
                    st.session_state.quiz_index = 0
                    st.session_state.quiz_wrong_chunks = []
                    st.session_state.show_learning_path = False
                    st.session_state.learning_path_data = None
                    st.rerun()

        # Phần xem lại đáp án
        if st.session_state.get("show_review", False):
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<p class="section-heading">📋 Chi Tiết Từng Câu</p>', unsafe_allow_html=True)
            answered = st.session_state.quiz_answered

            for i, q in enumerate(qs):
                chosen  = answered.get(i, "—")
                correct = q.get("answer", "A")
                is_ok   = chosen == correct
                opts    = q.get("options", {})
                css     = "correct" if is_ok else "wrong"
                icon    = "✅" if is_ok else "❌"
                chosen_text = opts.get(chosen, chosen)
                correct_text = opts.get(correct, correct)

                safe_q    = _html.escape(str(q.get('question', '')))
                safe_ct   = _html.escape(str(chosen_text))
                safe_crt  = _html.escape(str(correct_text))
                safe_expl = _html.escape(str(q.get('explanation', '')))

                wrong_part = f" &nbsp;·&nbsp; Đáp án đúng: <strong>{correct}. {safe_crt}</strong>" if not is_ok else ""
                expl_part  = f"<br><small style='color:#78350f;font-style:italic'>💡 {safe_expl}</small>" if safe_expl else ""

                st.markdown(f"""
                <div class="quiz-review-item {css}">
                    <strong>{icon} Câu {i+1}:</strong> {safe_q}<br>
                    <small>Bạn chọn: <strong>{chosen}. {safe_ct}</strong>{wrong_part}</small>
                    {expl_part}
                </div>
                """, unsafe_allow_html=True)



# ============================================================
# TAB 5: Hỏi & Đáp

# ============================================================
with tab_chat:
    st.markdown('<p class="section-heading">Hỏi & Đáp</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-caption">Đặt câu hỏi về tài liệu — AI tìm kiếm và trả lời dựa trên nội dung.</p>', unsafe_allow_html=True)

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    chat_docs_data, _ = api_get("/documents")
    chat_indexed_docs = []
    if chat_docs_data and chat_docs_data.get("documents"):
        chat_indexed_docs = [d for d in chat_docs_data["documents"] if d["status"] == "INDEXED"]

    col_docs_sel, col_topk = st.columns([3, 1])
    with col_docs_sel:
        if chat_indexed_docs:
            doc_label_to_id = {
                f"{d['file_name']}": d["id"]
                for d in chat_indexed_docs
            }
            st.markdown('<div class="doc-selector-label">Lọc theo tài liệu (để trống = tìm tất cả)</div>', unsafe_allow_html=True)

            col_sel, col_btn = st.columns([4, 1])
            with col_sel:
                selected_doc_labels = st.multiselect(
                    "Tài liệu",
                    options=list(doc_label_to_id.keys()),
                    default=[],
                    key="chat_doc_filter",
                    label_visibility="collapsed",
                )
            with col_btn:
                if st.button("Tất cả", key="select_all_docs", use_container_width=True):
                    st.session_state["chat_doc_filter"] = list(doc_label_to_id.keys())
                    st.rerun()

            selected_doc_ids = [doc_label_to_id[lbl] for lbl in selected_doc_labels]
        else:
            st.info("Chưa có tài liệu nào được index. Hãy upload ở tab Tài Liệu.")
            selected_doc_ids = []

    with col_topk:
        top_k = st.slider("Top K (RAG)", min_value=3, max_value=50, value=15)

    st.divider()

    if not st.session_state.chat_messages:
        st.markdown("""
        <div class="empty-state">
            <h3>Bắt đầu hỏi đáp</h3>
            <p>Chọn tài liệu ở trên rồi gõ câu hỏi phía dưới.<br>
            Ví dụ: "Tóm tắt nội dung chính?", "Giải thích khái niệm X?"</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        for msg in st.session_state.chat_messages:
            if msg["role"] == "user":
                with st.chat_message("user", avatar="👤"):
                    st.markdown(msg["content"])
            else:
                with st.chat_message("assistant", avatar="🤖"):
                    if msg.get("mode_badge"):
                        st.markdown(msg["mode_badge"], unsafe_allow_html=True)
                    st.markdown(msg["content"])
                    if msg.get("sources"):
                        st.markdown("**Nguồn trích dẫn:**")
                        sources_html = " ".join([
                            f'<span class="source-chip">{s["file_name"]} ({s["relevance_score"]:.0%})</span>'
                            for s in msg["sources"]
                        ])
                        st.markdown(sources_html, unsafe_allow_html=True)
                    if msg.get("filtered_docs"):
                        st.caption(f"Tìm kiếm trong: {', '.join(msg['filtered_docs'])}")

    question = st.chat_input("Nhập câu hỏi của bạn về tài liệu...")

    if question:
        st.session_state.chat_messages.append({"role": "user", "content": question})

        with st.spinner("AI đang đọc tài liệu và phân tích..."):
            history_to_send = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.chat_messages[:-1]
            ]
            ask_payload = {
                "question": question,
                "top_k": top_k,
                "history": history_to_send[-8:],
            }
            if selected_doc_ids:
                ask_payload["doc_ids"] = selected_doc_ids

            result, err = api_post("/chat/ask", json_data=ask_payload)

        if err:
            st.error(err)
        else:
            filtered_names = [
                d["file_name"] for d in chat_indexed_docs if d["id"] in selected_doc_ids
            ] if selected_doc_ids else []

            mode         = result.get("mode", "rag")
            context_chars = result.get("context_chars", 0)

            if mode == "full_context":
                mode_badge = f'<span class="mode-badge-full">Full-Context · {context_chars:,} chars</span>'
            else:
                mode_badge = f'<span class="mode-badge-rag">RAG · {context_chars:,} chars</span>'

            st.session_state.chat_messages.append({
                "role": "assistant",
                "content": result["answer"],
                "mode_badge": mode_badge,
                "sources": result.get("sources", []),
                "filtered_docs": filtered_names,
            })
            st.rerun()

    col_clear, _ = st.columns([1, 4])
    with col_clear:
        if st.button("Xóa cuộc trò chuyện", use_container_width=True):
            st.session_state.chat_messages = []
            st.rerun()


# ============================================================
# TAB 6: Lịch Sử
# ============================================================
with tab_history:
    st.markdown('<p class="section-heading">Lịch Sử Hỏi Đáp</p>', unsafe_allow_html=True)

    col_c1, col_c2, col_c3 = st.columns([1, 1, 3])
    with col_c1:
        limit = st.selectbox("Hiển thị", [10, 25, 50, 100], index=0, key="hist_limit")
    with col_c2:
        if st.button("Làm mới", use_container_width=True, key="hist_refresh"):
            st.rerun()
    with col_c3:
        if st.button("Xóa toàn bộ lịch sử", type="secondary", key="hist_clear"):
            result, err = api_delete("/chat/history")
            if err:
                st.error(err)
            else:
                st.success(result["message"])
                st.rerun()

    hist_data, err = api_get("/chat/history", {"limit": limit})

    if err:
        st.error(err)
    elif not hist_data or hist_data["total"] == 0:
        st.markdown("""
        <div class="empty-state">
            <h3>Chưa có lịch sử</h3>
            <p>Các phiên hỏi đáp sẽ được lưu tại đây.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.caption(f"Tổng: **{hist_data['total']}** phiên · Hiển thị {min(limit, len(hist_data['histories']))} mục mới nhất")

        for item in hist_data["histories"]:
            try:
                dt = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
                time_str = dt.strftime("%d/%m/%Y %H:%M:%S")
            except Exception:
                time_str = item["created_at"]

            with st.expander(f"#{item['id']} · {item['question'][:70]}… · {time_str}"):
                st.markdown(f"""
                <div class="chat-user-msg">
                    <strong>Câu hỏi</strong><br>{item['question']}
                </div>
                """, unsafe_allow_html=True)

                st.markdown(f"""
                <div class="chat-ai-msg">
                    <strong>Câu trả lời</strong><br>{item['answer'].replace(chr(10), '<br>')}
                </div>
                """, unsafe_allow_html=True)

                if item.get("sources"):
                    sources_html = " ".join([
                        f'<span class="source-chip">{src}</span>'
                        for src in item["sources"]
                    ])
                    st.markdown(f"**Nguồn:** {sources_html}", unsafe_allow_html=True)

                st.caption(f"Model: `{item.get('model_used', 'N/A')}` · {time_str}")