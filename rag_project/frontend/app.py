"""
Streamlit Frontend - Hệ thống Đọc Tài Liệu Thông Minh
Smart Document Reader v2.0
Sinh viên: Lê Nhật Huy - B23DCAT126 | Phạm Hải Đông - B23DCVT090
"""

import json
import time
import requests
import streamlit as st
from pathlib import Path
from datetime import datetime

# ==============1==============================================
# Cấu hình trang
# ============================================================
st.set_page_config(
    page_title="📖 Smart Document Reader",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# URL của FastAPI Backend
BACKEND_URL = "http://localhost:8000/api/v1"

# ============================================================
# Premium CSS - Dark Theme với Glassmorphism
# ============================================================
st.markdown("""
<style>
    /* ===== IMPORT FONT ===== */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* ===== GLOBAL ===== */
    * { font-family: 'Inter', sans-serif; }
    .main { background: #0a0e1a; }
    .stApp { background: linear-gradient(180deg, #0a0e1a 0%, #111827 50%, #0a0e1a 100%); }

    /* ===== SCROLLBAR ===== */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #1a1f35; }
    ::-webkit-scrollbar-thumb { background: #6366f1; border-radius: 3px; }

    /* ===== HERO HEADER ===== */
    .hero-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 30%, #f093fb 60%, #4facfe 100%);
        background-size: 300% 300%;
        animation: gradient-shift 8s ease infinite;
        padding: 2.5rem 2rem;
        border-radius: 1.25rem;
        text-align: center;
        margin-bottom: 2rem;
        position: relative;
        overflow: hidden;
        box-shadow: 0 20px 60px rgba(102, 126, 234, 0.3);
    }
    .hero-header::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,0.15);
        border-radius: 1.25rem;
    }
    .hero-header h1 {
        margin: 0;
        font-size: 2.2rem;
        font-weight: 800;
        color: white;
        position: relative;
        z-index: 1;
        text-shadow: 0 2px 10px rgba(0,0,0,0.3);
        letter-spacing: -0.5px;
    }
    .hero-header p {
        margin: 0.6rem 0 0;
        opacity: 0.9;
        color: white;
        position: relative;
        z-index: 1;
        font-weight: 400;
        font-size: 1rem;
    }
    @keyframes gradient-shift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    /* ===== GLASS CARD ===== */
    .glass-card {
        background: rgba(255,255,255,0.03);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 1rem;
        padding: 1.5rem;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }
    .glass-card:hover {
        border-color: rgba(99,102,241,0.3);
        box-shadow: 0 8px 32px rgba(99,102,241,0.15);
        transform: translateY(-2px);
    }

    /* ===== STAT CARD ===== */
    .stat-card {
        background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.08));
        backdrop-filter: blur(10px);
        border: 1px solid rgba(99,102,241,0.2);
        border-radius: 1rem;
        padding: 1.2rem;
        text-align: center;
        transition: all 0.3s ease;
    }
    .stat-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 30px rgba(99,102,241,0.2);
    }
    .stat-value {
        font-size: 2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #6366f1, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.2;
    }
    .stat-label {
        font-size: 0.8rem;
        color: #94a3b8;
        margin-top: 0.3rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* ===== DOC CARD ===== */
    .doc-card {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 0.75rem;
        padding: 1rem 1.2rem;
        margin-bottom: 0.75rem;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .doc-card:hover {
        background: rgba(99,102,241,0.05);
        border-color: rgba(99,102,241,0.2);
        transform: translateX(4px);
    }
    .doc-icon {
        font-size: 2rem;
        min-width: 2.5rem;
        text-align: center;
    }
    .doc-info { flex: 1; }
    .doc-name {
        font-weight: 600;
        color: #e2e8f0;
        font-size: 0.95rem;
        margin-bottom: 0.2rem;
    }
    .doc-meta {
        font-size: 0.75rem;
        color: #64748b;
    }

    /* ===== STATUS BADGE ===== */
    .badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-indexed {
        background: linear-gradient(135deg, #059669, #10b981);
        color: white;
        box-shadow: 0 2px 8px rgba(16,185,129,0.3);
    }
    .badge-uploading {
        background: linear-gradient(135deg, #d97706, #f59e0b);
        color: white;
    }
    .badge-indexing {
        background: linear-gradient(135deg, #4f46e5, #6366f1);
        color: white;
        animation: pulse-badge 2s ease-in-out infinite;
    }
    .badge-error {
        background: linear-gradient(135deg, #dc2626, #ef4444);
        color: white;
    }
    @keyframes pulse-badge {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }

    /* ===== CHAT STYLES ===== */
    .chat-user-msg {
        background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(139,92,246,0.08));
        border-left: 3px solid #6366f1;
        padding: 1rem 1.2rem;
        border-radius: 0 0.75rem 0.75rem 0;
        margin: 0.5rem 0;
    }
    .chat-ai-msg {
        background: rgba(16,185,129,0.06);
        border-left: 3px solid #10b981;
        padding: 1rem 1.2rem;
        border-radius: 0 0.75rem 0.75rem 0;
        margin: 0.5rem 0;
    }
    .source-chip {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        background: rgba(99,102,241,0.1);
        border: 1px solid rgba(99,102,241,0.25);
        color: #a5b4fc;
        padding: 0.2rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 500;
        margin: 0.15rem;
        transition: all 0.2s ease;
    }
    .source-chip:hover {
        background: rgba(99,102,241,0.2);
        transform: scale(1.05);
    }

    /* ===== CONTENT READER ===== */
    .reader-container {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 1rem;
        padding: 2rem;
        max-height: 600px;
        overflow-y: auto;
        line-height: 1.8;
        font-size: 0.95rem;
        color: #cbd5e1;
    }
    .reader-stats {
        display: flex;
        gap: 1.5rem;
        margin-bottom: 1rem;
    }
    .reader-stat-item {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        font-size: 0.8rem;
        color: #64748b;
    }

    /* ===== SUMMARY BOX ===== */
    .summary-box {
        background: linear-gradient(135deg, rgba(16,185,129,0.08), rgba(6,182,212,0.05));
        border: 1px solid rgba(16,185,129,0.2);
        border-radius: 1rem;
        padding: 1.5rem;
        line-height: 1.8;
        color: #cbd5e1;
    }
    .summary-box h4 {
        color: #10b981;
        margin-bottom: 0.75rem;
        font-weight: 700;
    }

    /* ===== EMPTY STATE ===== */
    .empty-state {
        text-align: center;
        padding: 4rem 2rem;
        color: #475569;
    }
    .empty-state .icon {
        font-size: 4rem;
        margin-bottom: 1rem;
        opacity: 0.5;
    }
    .empty-state h3 {
        color: #64748b;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    .empty-state p {
        color: #475569;
        font-size: 0.9rem;
        max-width: 400px;
        margin: 0 auto;
    }

    /* ===== SIDEBAR ===== */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f1629 0%, #0a0e1a 100%);
        border-right: 1px solid rgba(255,255,255,0.05);
    }
    section[data-testid="stSidebar"] .stMarkdown h3 {
        background: linear-gradient(135deg, #667eea, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }

    /* ===== METRIC OVERRIDE ===== */
    div[data-testid="metric-container"] {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 0.75rem;
        padding: 0.75rem;
    }

    /* ===== TABS ===== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background: rgba(255,255,255,0.02);
        border-radius: 0.75rem;
        padding: 0.3rem;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 0.5rem;
        font-weight: 600;
        font-size: 0.85rem;
        padding: 0.6rem 1.2rem;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    }

    /* ===== BUTTON OVERRIDE ===== */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        border: none;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 4px 20px rgba(99,102,241,0.4);
        transform: translateY(-1px);
    }

    /* ===== DIVIDER ===== */
    hr {
        border-color: rgba(255,255,255,0.05) !important;
    }
    
    /* ===== HISTORY ITEM ===== */
    .history-item {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 0.75rem;
        padding: 1rem;
        margin-bottom: 0.5rem;
        transition: all 0.2s ease;
    }
    .history-item:hover {
        border-color: rgba(99,102,241,0.2);
    }
    .history-question {
        color: #a5b4fc;
        font-weight: 600;
        font-size: 0.9rem;
    }
    .history-time {
        color: #475569;
        font-size: 0.75rem;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# Hàm gọi API
# ============================================================
def api_get(endpoint: str, params: dict = None):
    """Gọi GET request tới backend."""
    try:
        resp = requests.get(f"{BACKEND_URL}{endpoint}", params=params, timeout=60)
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"Lỗi {resp.status_code}: {resp.text}"
    except requests.ConnectionError:
        return None, "❌ Không kết nối được Backend. Hãy chạy: `start.bat`"
    except Exception as e:
        return None, str(e)


def api_post(endpoint: str, json_data: dict = None, files=None):
    """Gọi POST request tới backend."""
    try:
        if files:
            resp = requests.post(f"{BACKEND_URL}{endpoint}", files=files, timeout=120)
        else:
            resp = requests.post(f"{BACKEND_URL}{endpoint}", json=json_data, timeout=120)
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"Lỗi {resp.status_code}: {resp.json().get('detail', resp.text)}"
    except requests.ConnectionError:
        return None, "❌ Không kết nối được Backend."
    except Exception as e:
        return None, str(e)


def api_delete(endpoint: str):
    """Gọi DELETE request."""
    try:
        resp = requests.delete(f"{BACKEND_URL}{endpoint}", timeout=30)
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"Lỗi {resp.status_code}: {resp.text}"
    except Exception as e:
        return None, str(e)


def format_file_size(size_bytes: int) -> str:
    """Format kích thước file đẹp."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def get_file_icon(file_type: str) -> str:
    """Trả về icon theo loại file."""
    icons = {
        "pdf": "📕",
        "docx": "📘",
        "txt": "📄",
        "md": "📝",
    }
    return icons.get(file_type, "📄")


def get_status_badge(status: str) -> str:
    """Trả về HTML badge cho trạng thái."""
    badges = {
        "INDEXED": '<span class="badge badge-indexed">✓ Indexed</span>',
        "INDEXING": '<span class="badge badge-indexing">⟳ Đang xử lý</span>',
        "UPLOADED": '<span class="badge badge-uploading">↑ Chờ xử lý</span>',
        "ERROR": '<span class="badge badge-error">✕ Lỗi</span>',
    }
    return badges.get(status, f'<span class="badge">{status}</span>')


# ============================================================
# Sidebar - Thông tin hệ thống
# ============================================================
with st.sidebar:
    st.markdown("### 📖 Smart Document Reader")
    st.caption("Hệ thống Đọc Tài Liệu Thông Minh v2.0")

    st.markdown("---")

    # Trạng thái backend
    health_data, health_err = api_get("/health")
    if health_err:
        st.error("🔴 Backend: OFFLINE")
        st.caption(health_err)
    else:
        codex_ok = health_data.get("codex_connected", False)
        rag_ok = health_data.get("rag_ready", False)
        kb_ok = health_data.get("kb_loaded", False)

        if codex_ok:
            st.success("🟢 Hệ thống: ONLINE")
        else:
            st.warning("🟡 Hệ thống: Chưa kết nối Codex")

        # Mini status indicators
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.caption(f"{'✅' if codex_ok else '❌'} CodexOAuth")
            st.caption(f"{'✅' if rag_ok else '⏳'} RAG Engine")
        with col_s2:
            st.caption(f"{'✅' if kb_ok else '📭'} Knowledge Base")
            if kb_ok:
                st.caption(f"📦 {health_data.get('kb_chunk_count', 0)} chunks")

    st.markdown("---")

    # Thống kê nhanh
    docs_data, _ = api_get("/documents")
    hist_data, _ = api_get("/chat/history", {"limit": 1})

    total_docs = docs_data.get("total", 0) if docs_data else 0
    total_hist = hist_data.get("total", 0) if hist_data else 0

    st.markdown(f"""
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">
        <div class="stat-card">
            <div class="stat-value">{total_docs}</div>
            <div class="stat-label">Tài liệu</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{total_hist}</div>
            <div class="stat-label">Câu hỏi</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if docs_data and docs_data.get("documents"):
        docs = docs_data["documents"]
        indexed = sum(1 for d in docs if d["status"] == "INDEXED")
        total_chunks = sum(d.get("chunk_count", 0) for d in docs)
        total_size = sum(d.get("file_size", 0) for d in docs)

        st.markdown(f"""
        <div style="margin-top: 0.5rem; display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">
            <div class="stat-card">
                <div class="stat-value">{indexed}</div>
                <div class="stat-label">Đã index</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{total_chunks}</div>
                <div class="stat-label">Chunks</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Credits
    st.markdown("""
    <div style="text-align:center; padding: 0.5rem;">
        <p style="color: #475569; font-size: 0.7rem; margin-bottom: 0.3rem;">Sinh viên thực hiện</p>
        <p style="color: #94a3b8; font-size: 0.75rem; font-weight: 600; margin: 0;">Lê Nhật Huy — B23DCAT126</p>
        <p style="color: #94a3b8; font-size: 0.75rem; font-weight: 600; margin: 0;">Phạm Hải Đông — B23DCVT090</p>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# Hero Header
# ============================================================
st.markdown("""
<div class="hero-header">
    <h1>📖 Đọc Tài Liệu Thông Minh</h1>
    <p>Smart Document Reader · RAG + ChromaDB + CodexOAuth (GPT-5)</p>
</div>
""", unsafe_allow_html=True)


# ============================================================
# Tabs chính
# ============================================================
tab_docs, tab_read, tab_summary, tab_exercise, tab_chat, tab_history = st.tabs([
    "📁 Quản Lý Tài Liệu",
    "📖 Đọc Tài Liệu",
    "🤖 Tóm Tắt AI",
    "📝 Tạo Bài Tập",
    "💬 Hỏi & Đáp",
    "📚 Lịch Sử",
])


# ============================================================
# TAB 1: Quản lý tài liệu
# ============================================================
with tab_docs:
    st.markdown("#### 📁 Quản Lý Tài Liệu")

    # Upload section
    with st.container():
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
                st.info(f"📄 **{uploaded_file.name}**\n\n{size_str}")

            if st.button("⬆️ Upload & Xử lý", type="primary", use_container_width=True, disabled=not uploaded_file):
                with st.spinner("Đang upload và xử lý tài liệu..."):
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                    result, err = api_post("/documents/upload", files=files)
                    if err:
                        st.error(err)
                    else:
                        st.success(f"✅ Đã upload: **{result['file_name']}**")
                        st.caption("Đang index trong nền...")
                        time.sleep(1.5)
                        st.rerun()

    st.divider()

    # Danh sách tài liệu
    docs_data, err = api_get("/documents")
    if err:
        st.error(err)
    elif not docs_data or docs_data["total"] == 0:
        st.markdown("""
        <div class="empty-state">
            <div class="icon">📁</div>
            <h3>Chưa có tài liệu nào</h3>
            <p>Upload tài liệu đầu tiên (PDF, DOCX, TXT, MD) để bắt đầu khám phá!</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        docs = docs_data["documents"]
        indexed = sum(1 for d in docs if d["status"] == "INDEXED")

        # Stats row
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{docs_data['total']}</div>
                <div class="stat-label">Tổng tài liệu</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{indexed}</div>
                <div class="stat-label">Đã index</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            total_chunks = sum(d.get("chunk_count", 0) for d in docs)
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{total_chunks}</div>
                <div class="stat-label">Tổng chunks</div>
            </div>""", unsafe_allow_html=True)
        with c4:
            total_size = sum(d.get("file_size", 0) for d in docs)
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{format_file_size(total_size)}</div>
                <div class="stat-label">Dung lượng</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("")

        # Document list
        for doc in docs:
            icon = get_file_icon(doc.get("file_type", ""))
            badge = get_status_badge(doc["status"])
            size_str = format_file_size(doc.get("file_size", 0))
            chunks = doc.get("chunk_count", 0)
            pages = doc.get("page_count", 0)

            try:
                dt = datetime.fromisoformat(doc.get("uploaded_at", "").replace("Z", "+00:00"))
                time_str = dt.strftime("%d/%m/%Y %H:%M")
            except Exception:
                time_str = str(doc.get("uploaded_at", ""))[:16]

            col_main, col_status, col_actions = st.columns([4, 1.5, 1.5])

            with col_main:
                preview = doc.get("content_preview", "") or ""
                preview_short = (preview[:80] + "...") if len(preview) > 80 else preview
                st.markdown(f"""
                <div class="doc-card">
                    <div class="doc-icon">{icon}</div>
                    <div class="doc-info">
                        <div class="doc-name">{doc['file_name']}</div>
                        <div class="doc-meta">
                            {size_str} · {doc.get('file_type', '').upper()} · {chunks} chunks
                            {f' · {pages} trang' if pages else ''}
                            · {time_str}
                        </div>
                        {f'<div class="doc-meta" style="margin-top:0.2rem; color:#64748b; font-style:italic;">{preview_short}</div>' if preview_short else ''}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with col_status:
                st.markdown(f"<div style='padding-top:0.8rem;'>{badge}</div>", unsafe_allow_html=True)
                if doc.get("error_message"):
                    st.caption(f"⚠️ {doc['error_message'][:40]}...")

            with col_actions:
                st.markdown("<div style='padding-top:0.5rem;'></div>", unsafe_allow_html=True)
                if st.button("🗑️ Xóa", key=f"del_{doc['id']}", help=f"Xóa {doc['file_name']}"):
                    result, err = api_delete(f"/documents/{doc['id']}")
                    if err:
                        st.error(err)
                    else:
                        st.success("Đã xóa!")
                        st.rerun()

                file_url = f"{BACKEND_URL}/documents/{doc['id']}/download?source=original"
                extracted_url = f"{BACKEND_URL}/documents/{doc['id']}/download?source=extracted"
                st.markdown(f"""
                    <div style='margin-top:0.75rem; display:flex; gap:0.4rem; flex-wrap:wrap;'>
                        <a class='doc-link' href='{file_url}' target='_blank'>📄 Mở file gốc</a>
                        <a class='doc-link' href='{extracted_url}' target='_blank'>📝 Mở file Text AI</a>
                    </div>
                """, unsafe_allow_html=True)

        # Refresh button
        if st.button("🔄 Làm mới danh sách", use_container_width=False):
            st.rerun()


# ============================================================
# TAB 2: Đọc Tài Liệu
# ============================================================
with tab_read:
    st.markdown("#### 📖 Đọc Nội Dung Tài Liệu")

    docs_data, err = api_get("/documents")
    if err:
        st.error(err)
    elif not docs_data or docs_data["total"] == 0:
        st.markdown("""
        <div class="empty-state">
            <div class="icon">📖</div>
            <h3>Chưa có tài liệu để đọc</h3>
            <p>Hãy upload tài liệu ở tab "Quản Lý Tài Liệu" trước.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        docs = docs_data["documents"]
        # Dropdown chọn tài liệu
        doc_options = {
            f"{get_file_icon(d.get('file_type', ''))} {d['file_name']} ({format_file_size(d.get('file_size', 0))})": d['id']
            for d in docs
        }

        selected_doc = st.selectbox(
            "Chọn tài liệu cần đọc",
            options=list(doc_options.keys()),
            index=0,
            help="Chọn một tài liệu để xem nội dung đầy đủ"
        )

        if selected_doc:
            doc_id = doc_options[selected_doc]

            if st.button("📖 Đọc tài liệu", type="primary", use_container_width=False):
                with st.spinner("Đang tải nội dung tài liệu..."):
                    content_data, err = api_get(f"/documents/{doc_id}/content")

                if err:
                    st.error(err)
                elif content_data:
                    # Stats bar
                    st.markdown(f"""
                    <div class="reader-stats">
                        <div class="reader-stat-item">📄 {content_data.get('page_count', 0)} trang</div>
                        <div class="reader-stat-item">📝 {content_data.get('word_count', 0):,} từ</div>
                        <div class="reader-stat-item">🔤 {content_data.get('char_count', 0):,} ký tự</div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Content display
                    st.markdown(f"""
                    <div class="reader-container">
                        {content_data['content'][:50000].replace(chr(10), '<br>')}
                    </div>
                    """, unsafe_allow_html=True)

                    # Download text button
                    st.download_button(
                        "⬇️ Tải về dạng Text",
                        data=content_data['content'],
                        file_name=f"{content_data['file_name']}.txt",
                        mime="text/plain",
                    )


# ============================================================
# TAB 3: Tóm Tắt AI
# ============================================================
with tab_summary:
    st.markdown("#### 🤖 Tóm Tắt Tài Liệu Bằng AI")
    st.caption("Sử dụng CodexOAuth (GPT-5) để tạo tóm tắt thông minh cho tài liệu.")

    docs_data, err = api_get("/documents")
    if err:
        st.error(err)
    elif not docs_data or docs_data["total"] == 0:
        st.markdown("""
        <div class="empty-state">
            <div class="icon">🤖</div>
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
                f"{get_file_icon(d.get('file_type', ''))} {d['file_name']}": d['id']
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
                # Check if already has summary
                current_doc = next((d for d in indexed_docs if d['id'] == doc_id), None)

                if current_doc and current_doc.get("summary"):
                    st.markdown(f"""
                    <div class="summary-box">
                        <h4>📝 Tóm tắt (đã lưu)</h4>
                        {current_doc['summary'].replace(chr(10), '<br>')}
                    </div>
                    """, unsafe_allow_html=True)

                    # Offer to regenerate
                    if st.button("🔄 Tạo tóm tắt mới", use_container_width=False):
                        with st.spinner("🧠 AI đang đọc và tóm tắt tài liệu..."):
                            # Force re-summarize by clearing first
                            result, err = api_post(f"/documents/{doc_id}/summarize")
                        if err:
                            st.error(err)
                        elif result:
                            st.markdown(f"""
                            <div class="summary-box">
                                <h4>📝 Tóm tắt mới</h4>
                                {result['summary'].replace(chr(10), '<br>')}
                            </div>
                            """, unsafe_allow_html=True)
                            st.caption(f"Model: `{result.get('model_used', 'N/A')}`")
                else:
                    if st.button("🤖 Tạo tóm tắt bằng AI", type="primary", use_container_width=False):
                        with st.spinner("🧠 AI đang đọc và tóm tắt tài liệu... (có thể mất 15-30 giây)"):
                            result, err = api_post(f"/documents/{doc_id}/summarize")
                        if err:
                            st.error(err)
                        elif result:
                            st.markdown(f"""
                            <div class="summary-box">
                                <h4>📝 Tóm tắt</h4>
                                {result['summary'].replace(chr(10), '<br>')}
                            </div>
                            """, unsafe_allow_html=True)
                            st.caption(f"Model: `{result.get('model_used', 'N/A')}`")
                            st.success("✅ Tóm tắt đã được lưu!")


# ============================================================
# TAB 4: Tạo Bài Tập
with tab_exercise:
    st.markdown("#### 📝 Tạo Bài Tập Từ Giáo Trình")
    st.caption("Sử dụng AI để tạo câu hỏi trắc nghiệm, tự luận hoặc thảo luận dựa trên tài liệu đã upload.")

    docs_data, err = api_get("/documents")
    if err:
        st.error(err)
    elif not docs_data or docs_data["total"] == 0:
        st.markdown(
            """
            <div class="empty-state">
                <div class="icon">📝</div>
                <h3>Chưa có tài liệu để tạo bài tập</h3>
                <p>Upload tài liệu trước ở tab "Quản Lý Tài Liệu".</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        docs = docs_data["documents"]
        indexed_docs = [d for d in docs if d["status"] == "INDEXED"]

        if not indexed_docs:
            st.warning("Chưa có tài liệu nào được index xong. Vui lòng chờ xử lý hoàn tất.")
        else:
            doc_options = {
                f"{get_file_icon(d.get('file_type', ''))} {d['file_name']}": d['id']
                for d in indexed_docs
            }
            selected_doc = st.selectbox(
                "Chọn tài liệu để tạo bài tập",
                options=list(doc_options.keys()),
                index=0,
                key="exercise_doc_select"
            )
            exercise_type = st.radio(
                "Chọn dạng bài tập",
                options=["trắc nghiệm", "tự luận", "thảo luận"],
                horizontal=True,
            )
            num_questions = st.slider(
                "Số lượng câu hỏi",
                min_value=1,
                max_value=20,
                value=5,
                help="Số lượng câu hỏi AI sẽ tạo",
            )

            if st.button("📝 Tạo bài tập", type="primary", use_container_width=False):
                doc_id = doc_options[selected_doc]
                with st.spinner("AI đang tạo bài tập... (có thể mất 15-30 giây)"):
                    result, err = api_post(
                        f"/documents/{doc_id}/exercise",
                        json_data={"exercise_type": exercise_type, "count": num_questions},
                    )
                if err:
                    st.error(err)
                elif result:
                    st.markdown(f"""
                        <div class="summary-box">
                            <h4>📝 Bài tập AI tạo</h4>
                            {result['exercise_text'].replace(chr(10), '<br>')}
                        </div>
                    """, unsafe_allow_html=True)
                    st.caption(f"Model: `{result.get('model_used', 'N/A')}`")
                    st.download_button(
                        "⬇️ Tải bài tập về",
                        data=result['exercise_text'],
                        file_name=f"{result['file_name']}_baitap.txt",
                        mime="text/plain",
                    )


# ============================================================
# TAB 5: Hỏi & Đáp
# ============================================================
with tab_chat:
    st.markdown("#### 💬 Hỏi & Đáp Thông Minh")
    st.caption("Đặt câu hỏi về tài liệu — AI sẽ tìm kiếm và trả lời dựa trên nội dung.")

    # Khởi tạo chat history trong session
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # Settings
    with st.expander("⚙️ Cài đặt truy vấn", expanded=False):
        top_k = st.slider(
            "Số chunk tài liệu tìm kiếm (Top K)",
            min_value=1, max_value=10, value=5,
            help="Số đoạn văn bản liên quan nhất đưa vào ngữ cảnh cho AI"
        )

    # Chat display
    chat_container = st.container()
    with chat_container:
        if not st.session_state.chat_messages:
            st.markdown("""
            <div class="empty-state">
                <div class="icon">💬</div>
                <h3>Bắt đầu hỏi đáp</h3>
                <p>Hỏi bất kỳ câu hỏi nào về tài liệu đã upload.<br>
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
                        st.markdown(msg["content"])
                        if msg.get("sources"):
                            st.markdown("**📎 Nguồn trích dẫn:**")
                            sources_html = " ".join([
                                f'<span class="source-chip">📄 {s["file_name"]} ({s["relevance_score"]:.0%})</span>'
                                for s in msg["sources"]
                            ])
                            st.markdown(sources_html, unsafe_allow_html=True)

    # Input
    question = st.chat_input("Nhập câu hỏi của bạn về tài liệu...")

    if question:
        st.session_state.chat_messages.append({"role": "user", "content": question})

        with st.spinner("🔍 Đang tìm kiếm và tạo câu trả lời..."):
            result, err = api_post("/chat/ask", json_data={"question": question, "top_k": top_k})

        if err:
            st.error(err)
        else:
            st.session_state.chat_messages.append({
                "role": "assistant",
                "content": result["answer"],
                "sources": result.get("sources", []),
            })
            st.rerun()

    # Clear chat
    col_clear, _ = st.columns([1, 4])
    with col_clear:
        if st.button("🗑️ Xóa cuộc trò chuyện", use_container_width=True):
            st.session_state.chat_messages = []
            st.rerun()


# ============================================================
# TAB 5: Lịch sử hỏi đáp
# ============================================================
with tab_history:
    st.markdown("#### 📚 Lịch Sử Hỏi Đáp")

    col_c1, col_c2, col_c3 = st.columns([1, 1, 3])
    with col_c1:
        limit = st.selectbox("Hiển thị", [10, 25, 50, 100], index=0, key="hist_limit")
    with col_c2:
        if st.button("🔄 Làm mới", use_container_width=True, key="hist_refresh"):
            st.rerun()
    with col_c3:
        if st.button("🗑️ Xóa toàn bộ lịch sử", type="secondary", key="hist_clear"):
            result, err = api_delete("/chat/history")
            if err:
                st.error(err)
            else:
                st.success(result["message"])
                st.rerun()

    # Fetch history
    hist_data, err = api_get("/chat/history", {"limit": limit})

    if err:
        st.error(err)
    elif not hist_data or hist_data["total"] == 0:
        st.markdown("""
        <div class="empty-state">
            <div class="icon">📚</div>
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

            with st.expander(f"#{item['id']} · {item['question'][:70]}... · {time_str}"):
                st.markdown(f"""
                <div class="chat-user-msg">
                    <strong>❓ Câu hỏi</strong><br>{item['question']}
                </div>
                """, unsafe_allow_html=True)

                st.markdown(f"""
                <div class="chat-ai-msg">
                    <strong>🤖 Câu trả lời</strong><br>{item['answer'].replace(chr(10), '<br>')}
                </div>
                """, unsafe_allow_html=True)

                if item.get("sources"):
                    sources_html = " ".join([
                        f'<span class="source-chip">📄 {src}</span>'
                        for src in item["sources"]
                    ])
                    st.markdown(f"**📎 Nguồn:** {sources_html}", unsafe_allow_html=True)

                st.caption(f"Model: `{item.get('model_used', 'N/A')}` · {time_str}")
