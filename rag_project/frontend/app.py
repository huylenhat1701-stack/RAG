"""
Streamlit Frontend - Hệ thống Hỏi Đáp RAG
Sinh viên: Lê Nhật Huy - B23DCAT126 | Phạm Hải Đông - B23DCVT090
"""

import json
import time
import requests
import streamlit as st
from pathlib import Path
from datetime import datetime

# ============================================================
# Cấu hình trang
# ============================================================
st.set_page_config(
    page_title="RAG Q&A System",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# URL của FastAPI Backend
BACKEND_URL = "http://localhost:8000/api/v1"

# Custom CSS
st.markdown("""
<style>
    /* Màu chủ đạo */
    .main { background-color: #0f172a; }
    
    /* Header app */
    .app-header {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #06b6d4 100%);
        padding: 2rem;
        border-radius: 1rem;
        text-align: center;
        margin-bottom: 1.5rem;
        color: white;
    }
    .app-header h1 { margin: 0; font-size: 2rem; }
    .app-header p { margin: 0.5rem 0 0; opacity: 0.85; }

    /* Status badge */
    .status-badge {
        display: inline-block;
        padding: 0.2rem 0.7rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .status-indexed { background: #10b981; color: white; }
    .status-uploaded { background: #f59e0b; color: white; }
    .status-indexing { background: #6366f1; color: white; }
    .status-error { background: #ef4444; color: white; }

    /* Chat bubble */
    .chat-user {
        background: #1e293b;
        border-left: 4px solid #6366f1;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .chat-ai {
        background: #0f172a;
        border-left: 4px solid #10b981;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .source-tag {
        display: inline-block;
        background: #1e293b;
        border: 1px solid #6366f1;
        color: #a5b4fc;
        padding: 0.2rem 0.6rem;
        border-radius: 0.25rem;
        font-size: 0.8rem;
        margin: 0.2rem;
    }
    
    /* Nút upload */
    .upload-area {
        border: 2px dashed #6366f1;
        border-radius: 1rem;
        padding: 2rem;
        text-align: center;
    }
    
    /* Metric card */
    div[data-testid="metric-container"] {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 0.5rem;
        padding: 1rem;
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
        return None, "❌ Không kết nối được Backend. Hãy chạy: `uvicorn backend.main:app --reload`"
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


# ============================================================
# Sidebar - Thông tin hệ thống
# ============================================================
with st.sidebar:
    st.markdown("### 🤖 RAG Q&A System")
    st.caption("Hệ thống Hỏi Đáp Thông Minh")

    # Trạng thái backend
    health_data, health_err = api_get("/health")
    if health_err:
        st.error(f"Backend: OFFLINE\n{health_err}")
    else:
        status_color = "🟢" if health_data.get("codex_connected") else "🟡"
        st.success(f"{status_color} Backend: ONLINE")
        if health_data.get("codex_connected"):
            st.caption(f"LLM: CodexOAuth ✅")
        else:
            st.warning("Chưa kết nối Codex OAuth")
        if health_data.get("kb_loaded"):
            st.caption(f"Knowledge Base: {health_data.get('kb_chunk_count', 0)} chunks")

    st.divider()

    # Thống kê nhanh
    docs_data, _ = api_get("/documents")
    hist_data, _ = api_get("/chat/history", {"limit": 1})

    col1, col2 = st.columns(2)
    with col1:
        total_docs = docs_data.get("total", 0) if docs_data else 0
        st.metric("📄 Tài liệu", total_docs)
    with col2:
        total_hist = hist_data.get("total", 0) if hist_data else 0
        st.metric("💬 Câu hỏi", total_hist)

    st.divider()
    st.caption("**Sinh viên thực hiện:**")
    st.caption("Lê Nhật Huy - B23DCAT126")
    st.caption("Phạm Hải Đông - B23DCVT090")


# ============================================================
# Header
# ============================================================
st.markdown("""
<div class="app-header">
    <h1>🤖 Hệ Thống Hỏi Đáp RAG</h1>
    <p>Retrieval-Augmented Generation · FastAPI + ChromaDB + CodexOAuth</p>
</div>
""", unsafe_allow_html=True)


# ============================================================
# Tabs chính
# ============================================================
tab_docs, tab_chat, tab_history = st.tabs([
    "📁 Quản Lý Tài Liệu",
    "💬 Hỏi & Đáp",
    "📚 Lịch Sử",
])


# ============================================================
# TAB 1: Quản lý tài liệu
# ============================================================
with tab_docs:
    st.subheader("📁 Quản Lý Tài Liệu Cục Bộ")

    # Upload section
    with st.container():
        st.markdown("#### Upload Tài Liệu Mới")
        uploaded_file = st.file_uploader(
            "Chọn file để upload",
            type=["pdf", "txt", "docx", "md"],
            help="Hỗ trợ PDF, TXT, DOCX, Markdown (tối đa 50MB)",
            label_visibility="collapsed",
        )

        col_upload, col_info = st.columns([1, 2])
        with col_upload:
            if st.button("⬆️ Upload & Xử lý", type="primary", use_container_width=True, disabled=not uploaded_file):
                with st.spinner("Đang upload và xử lý tài liệu..."):
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                    result, err = api_post("/documents/upload", files=files)
                    if err:
                        st.error(err)
                    else:
                        st.success(f"✅ Đã upload: **{result['file_name']}** (đang index nền...)")
                        time.sleep(1)
                        st.rerun()

        with col_info:
            if uploaded_file:
                size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
                st.info(
                    f"📄 **{uploaded_file.name}** "
                    f"| Loại: `{uploaded_file.type}` "
                    f"| Kích thước: `{size_mb:.2f} MB`"
                )

    st.divider()

    # Danh sách tài liệu
    st.markdown("#### Danh Sách Tài Liệu Đã Upload")

    docs_data, err = api_get("/documents")
    if err:
        st.error(err)
    elif not docs_data or docs_data["total"] == 0:
        st.info("Chưa có tài liệu nào. Upload tài liệu đầu tiên để bắt đầu!")
    else:
        # Hiển thị thống kê
        docs = docs_data["documents"]
        indexed = sum(1 for d in docs if d["status"] == "INDEXED")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st.metric("Tổng tài liệu", docs_data["total"])
        with col_m2:
            st.metric("Đã index ✅", indexed)
        with col_m3:
            total_chunks = sum(d["chunk_count"] for d in docs)
            st.metric("Tổng chunks", total_chunks)
        with col_m4:
            total_size = sum(d["file_size"] for d in docs) / (1024 * 1024)
            st.metric("Tổng dung lượng", f"{total_size:.1f} MB")

        st.markdown("")

        # Bảng tài liệu
        for doc in docs:
            with st.container():
                col_name, col_status, col_info2, col_del = st.columns([3, 1.5, 2, 1])

                with col_name:
                    icon = "📄" if doc["file_type"] == "pdf" else "📝"
                    st.markdown(f"**{icon} {doc['file_name']}**")
                    size_kb = doc["file_size"] / 1024
                    st.caption(f"ID: {doc['id']} · {size_kb:.1f} KB · {doc['file_type'].upper()}")

                with col_status:
                    status = doc["status"]
                    status_map = {
                        "INDEXED": ("✅ Indexed", "success"),
                        "INDEXING": ("⏳ Đang xử lý", "info"),
                        "UPLOADED": ("📤 Chờ xử lý", "warning"),
                        "ERROR": ("❌ Lỗi", "error"),
                    }
                    label, msg_type = status_map.get(status, (status, "info"))
                    if msg_type == "success":
                        st.success(label)
                    elif msg_type == "warning":
                        st.warning(label)
                    elif msg_type == "error":
                        st.error(label)
                    else:
                        st.info(label)

                with col_info2:
                    st.caption(f"Chunks: **{doc['chunk_count']}**")
                    uploaded_at = doc.get("uploaded_at", "")
                    if uploaded_at:
                        try:
                            dt = datetime.fromisoformat(uploaded_at.replace("Z", "+00:00"))
                            st.caption(f"Upload: {dt.strftime('%d/%m/%Y %H:%M')}")
                        except Exception:
                            st.caption(f"Upload: {uploaded_at[:16]}")
                    if doc.get("error_message"):
                        st.caption(f"⚠️ {doc['error_message'][:50]}...")

                with col_del:
                    if st.button("🗑️", key=f"del_{doc['id']}", help="Xóa tài liệu này"):
                        result, err = api_delete(f"/documents/{doc['id']}")
                        if err:
                            st.error(err)
                        else:
                            st.success("Đã xóa!")
                            st.rerun()

                st.divider()

        # Nút refresh
        if st.button("🔄 Làm mới danh sách"):
            st.rerun()


# ============================================================
# TAB 2: Hỏi & Đáp
# ============================================================
with tab_chat:
    st.subheader("💬 Hỏi & Đáp Thông Minh")

    # Khởi tạo chat history trong session
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # Settings trong expander
    with st.expander("⚙️ Cài đặt truy vấn", expanded=False):
        top_k = st.slider(
            "Số chunk tài liệu tìm kiếm (Top K)",
            min_value=1, max_value=10, value=5,
            help="Số lượng đoạn văn bản liên quan nhất được đưa vào ngữ cảnh cho AI"
        )

    # Hiển thị lịch sử chat trong session
    chat_container = st.container()
    with chat_container:
        if not st.session_state.chat_messages:
            st.markdown("""
            <div style="text-align:center; padding: 3rem; color: #64748b;">
                <div style="font-size: 3rem;">💬</div>
                <h3>Bắt đầu hỏi đáp</h3>
                <p>Hỏi bất kỳ câu hỏi nào về các tài liệu đã upload.</p>
                <p>Ví dụ: "Tóm tắt nội dung chính của tài liệu?", "Giải thích khái niệm X?"</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            for msg in st.session_state.chat_messages:
                if msg["role"] == "user":
                    with st.chat_message("user"):
                        st.markdown(msg["content"])
                else:
                    with st.chat_message("assistant"):
                        st.markdown(msg["content"])
                        if msg.get("sources"):
                            st.markdown("**📎 Nguồn trích dẫn:**")
                            sources_html = " ".join([
                                f'<span class="source-tag">📄 {s["file_name"]} ({s["relevance_score"]:.0%})</span>'
                                for s in msg["sources"]
                            ])
                            st.markdown(sources_html, unsafe_allow_html=True)

    # Input câu hỏi
    question = st.chat_input("Nhập câu hỏi của bạn về tài liệu...")

    if question:
        # Thêm câu hỏi vào session
        st.session_state.chat_messages.append({"role": "user", "content": question})

        # Gọi API
        with st.spinner("🔍 Đang tìm kiếm và tạo câu trả lời..."):
            result, err = api_post("/chat/ask", json_data={"question": question, "top_k": top_k})

        if err:
            st.error(err)
        else:
            # Thêm câu trả lời vào session
            st.session_state.chat_messages.append({
                "role": "assistant",
                "content": result["answer"],
                "sources": result.get("sources", []),
            })
            st.rerun()

    # Nút xóa chat
    col_clear, col_new = st.columns([1, 4])
    with col_clear:
        if st.button("🗑️ Xóa chat", use_container_width=True):
            st.session_state.chat_messages = []
            st.rerun()


# ============================================================
# TAB 3: Lịch sử hỏi đáp
# ============================================================
with tab_history:
    st.subheader("📚 Lịch Sử Hỏi Đáp")

    col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1, 1, 3])
    with col_ctrl1:
        limit = st.selectbox("Hiển thị", [10, 25, 50, 100], index=0)
    with col_ctrl2:
        if st.button("🔄 Làm mới", use_container_width=True):
            st.rerun()
    with col_ctrl3:
        if st.button("🗑️ Xóa toàn bộ lịch sử", type="secondary"):
            result, err = api_delete("/chat/history")
            if err:
                st.error(err)
            else:
                st.success(result["message"])
                st.rerun()

    # Lấy lịch sử từ backend
    hist_data, err = api_get("/chat/history", {"limit": limit})

    if err:
        st.error(err)
    elif not hist_data or hist_data["total"] == 0:
        st.info("Chưa có lịch sử hỏi đáp nào.")
    else:
        st.caption(f"Tổng: **{hist_data['total']}** phiên | Đang hiển thị {min(limit, len(hist_data['histories']))} mục mới nhất")

        for item in hist_data["histories"]:
            # Format thời gian
            try:
                dt = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
                time_str = dt.strftime("%d/%m/%Y %H:%M:%S")
            except Exception:
                time_str = item["created_at"]

            with st.expander(f"#{item['id']} · {item['question'][:80]}... · {time_str}"):
                st.markdown(f"**❓ Câu hỏi:**\n{item['question']}")
                st.divider()
                st.markdown(f"**🤖 Câu trả lời:**\n{item['answer']}")

                if item.get("sources"):
                    st.divider()
                    st.markdown("**📎 Nguồn:**")
                    for src in item["sources"]:
                        st.caption(f"• {src}")

                st.caption(f"Model: `{item.get('model_used', 'N/A')}` · Thời gian: {time_str}")
