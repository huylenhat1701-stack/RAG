from datetime import datetime
from html import escape as html_escape
from typing import Any, Dict, List

import requests
import streamlit as st

API_BASE = "http://localhost:8000"
API_SESSION = requests.Session()
API_SESSION.trust_env = False

st.set_page_config(layout="wide", page_title="RAG · Gemini")


def inject_gemini_like_css() -> None:
    st.markdown(
        """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500&display=swap');
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #131314 !important;
        color-scheme: dark;
    }
    .stApp {
        background-color: #131314;
    }
    [data-testid="stHeader"] { background-color: rgba(19,19,20,0.85); backdrop-filter: blur(8px); }
             [data-testid="stToolbar"] { display: none !important; }
    [data-testid="stDecoration"] { display: none; }
    div.block-container {
        padding-top: 1.25rem !important;
        padding-bottom: 4rem !important;
        max-width: 820px !important;
    }
    .gemini-page-title {
        text-align: center;
        font-family: "Google Sans", "Segoe UI", system-ui, sans-serif;
        font-size: 1.15rem;
        font-weight: 500;
        color: #e8eaed;
        margin: 0 0 0.35rem 0;
        letter-spacing: 0.01em;
    }
    .gemini-page-sub {
        text-align: center;
        font-size: 0.8rem;
        color: #9aa0a6;
        margin-bottom: 1.25rem;
    }
    .gemini-chat-scroll {
        min-height: 42vh;
        margin-bottom: 0.5rem;
    }
    .bubble-user-wrap {
        display: flex;
        justify-content: flex-end;
        margin: 1rem 0;
    }
    .bubble-user {
        background: #303030;
        color: #e8eaed;
        padding: 0.75rem 1.1rem;
        border-radius: 1.35rem;
        max-width: 88%;
        font-size: 0.95rem;
        line-height: 1.45;
        white-space: pre-wrap;
        word-wrap: break-word;
    }
    .bubble-assistant-row {
        display: flex;
        gap: 0.65rem;
        margin: 1.1rem 0;
        align-items: flex-start;
    }
    .gemini-spark {
        flex-shrink: 0;
        width: 28px;
        height: 28px;
        margin-top: 4px;
        border-radius: 50%;
        background: linear-gradient(135deg, #4b88ff, #8ab4ff);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        line-height: 1;
        color: white;
    }
    .bubble-assistant-body {
        flex: 1;
        min-width: 0;
    }
    .assistant-markdown {
        color: #e8eaed;
        font-size: 0.95rem;
        line-height: 1.55;
    }
    .assistant-markdown p { margin: 0 0 0.6rem 0; }
    .gemini-footer-note {
        text-align: center;
        font-size: 0.72rem;
        color: #80868b;
        margin-top: 1.5rem;
        padding: 0 1rem 2rem 1rem;
        line-height: 1.4;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #1e1f20;
        border-radius: 999px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] { color: #9aa0a6; }
    .stTabs [aria-selected="true"] { color: #e8eaed !important; background: #303030 !important; border-radius: 999px; }
    div[data-testid="stChatInput"] {
        background-color: #1e1f20 !important;
        border: 1px solid #444746 !important;
        border-radius: 1.75rem !important;
        padding: 0.35rem 0.5rem !important;
    }
    textarea[data-testid="stChatInputTextArea"] {
        color: #e8eaed !important;
        caret-color: #8ab4ff;
    }
    .stSpinner > div { border-color: #8ab4ff transparent transparent transparent !important; }
    [data-testid="stSidebar"] {
        background-color: #1e1f20;
        border-right: 1px solid #3c4043;
    }
    [data-testid="stSidebar"] .stMarkdown { color: #e8eaed; }
    section[data-testid="stSidebar"] > div { color: #e8eaed; }
</style>
        """,
        unsafe_allow_html=True,
    )


inject_gemini_like_css()

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []


def _migrate_legacy_chat(messages: List[Any]) -> List[Dict[str, Any]]:
    if not messages:
        return []
    first = messages[0]
    if not isinstance(first, dict) or "role" in first:
        return messages
    if "question" not in first:
        return messages
    out: List[Dict[str, Any]] = []
    for m in messages:
        out.append({"role": "user", "content": m.get("question", "")})
        out.append(
            {
                "role": "assistant",
                "content": m.get("answer", ""),
                "sources": m.get("sources", []),
                "timestamp": m.get("timestamp"),
            }
        )
    return out


st.session_state.chat_messages = _migrate_legacy_chat(st.session_state.chat_messages)


def fetch_documents() -> List[Dict]:
    response = API_SESSION.get(f"{API_BASE}/documents", timeout=30)
    response.raise_for_status()
    return response.json()


def upload_document(file_obj) -> Dict:
    files = {"file": (file_obj.name, file_obj.getvalue(), file_obj.type or "application/octet-stream")}
    response = API_SESSION.post(f"{API_BASE}/documents/upload", files=files, timeout=120)
    response.raise_for_status()
    return response.json()


def delete_document(document_id: str) -> None:
    response = API_SESSION.delete(f"{API_BASE}/documents/{document_id}", timeout=30)
    response.raise_for_status()


def ask_question(question: str, top_k: int = 5) -> Dict:
    payload = {"question": question, "top_k": top_k}
    response = API_SESSION.post(f"{API_BASE}/chat/ask", json=payload, timeout=180)
    response.raise_for_status()
    return response.json()


def fetch_history(limit: int = 50) -> List[Dict]:
    response = API_SESSION.get(f"{API_BASE}/chat/history", params={"limit": limit}, timeout=30)
    response.raise_for_status()
    return response.json()


def _try_copy(text: str) -> None:
    try:
        import pyperclip

        pyperclip.copy(text)
        st.toast("Da sao chep vao clipboard.")
    except Exception:
        st.info("Khong the sao chep tu dong — hay chon va Ctrl+C trong hop van ban ben duoi.")
        st.text_area("Noi dung de sao chep", value=text, height=200, key=f"_copy_manual_{hash(text) % 10_000_000}")


def render_welcome_assistant() -> None:
    st.markdown(
        """
<div class="bubble-assistant-row">
  <div class="gemini-spark" title="RAG + Gemini">✦</div>
  <div class="bubble-assistant-body">
    <div class="assistant-markdown">
      <p><strong>Xin chao.</strong> Toi la tro ly dua tren tai lieu ban da tai (RAG) va Gemini.</p>
      <p><strong>Huong dan</strong></p>
      <ol>
        <li>O <strong>sidebar</strong>: tai PDF / DOCX / TXT va doi trang thai <strong>INDEXED</strong>.</li>
        <li>O duoi: go cau hoi — <strong>Enter</strong> de gui.</li>
        <li>Mo <strong>Nguon tham chieu</strong> de xem <em>toan bo</em> doan trich tu file.</li>
      </ol>
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_message_gemi_style(idx: int, message: Dict[str, Any]) -> None:
    role = message.get("role", "user")
    content = message.get("content") or ""

    if role == "user":
        st.markdown(
            f'<div class="bubble-user-wrap"><div class="bubble-user">{html_escape(content)}</div></div>',
            unsafe_allow_html=True,
        )
        return

    spark_m, body_m = st.columns([0.08, 0.92])
    with spark_m:
        st.markdown(
            '<div class="gemini-spark" title="Gemini">✦</div>',
            unsafe_allow_html=True,
        )
    with body_m:
        st.markdown(content)

    a1, a2, a3, _ = st.columns([1, 1, 1, 10])
    with a1:
        if st.button("👍", key=f"th_up_{idx}", help="Huu ich"):
            st.toast("Cam on ban da gop y!")
    with a2:
        if st.button("👎", key=f"th_dn_{idx}", help="Chua tot"):
            st.toast("Da ghi nhan.")
    with a3:
        if st.button("📋", key=f"cp_{idx}", help="Sao chep cau tra loi"):
            _try_copy(content)

    if message.get("sources"):
        with st.expander("Nguon tham chieu — day du noi dung chunk", expanded=False):
            for sidx, source in enumerate(message["sources"], start=1):
                fn = source.get("filename", "")
                pg = source.get("page_number")
                sc = source.get("similarity_score", 0.0)
                st.markdown(f"**{sidx}.** `{fn}` · trang `{pg}` · diem `{sc:.4f}`")
                chunk = source.get("chunk_text", "") or ""
                h = min(320, max(100, min(len(chunk) // 40 + 4, 40)))
                st.text_area(
                    "Trich doan day du",
                    value=chunk,
                    height=h,
                    disabled=True,
                    key=f"src_{idx}_{sidx}",
                    label_visibility="collapsed",
                )


st.sidebar.title("Tai lieu")
uploaded_file = st.sidebar.file_uploader("Chon file (pdf / docx / txt)", type=["pdf", "docx", "txt"])

if st.sidebar.button("Tai len & Index", use_container_width=True):
    if not uploaded_file:
        st.sidebar.warning("Vui long chon file truoc khi tai len.")
    else:
        with st.spinner("Dang tai len va indexing..."):
            try:
                result = upload_document(uploaded_file)
                st.sidebar.success(f"OK: {result.get('filename')} ({result.get('status')})")
            except requests.RequestException as exc:
                st.sidebar.error(f"That bai: {exc}")

st.sidebar.markdown("---")
st.sidebar.markdown("**Cai dat**")
top_k = st.sidebar.number_input("Top K", min_value=1, max_value=20, value=5, step=1)
if st.sidebar.button("Xoa cuoc tro chuyen", use_container_width=True):
    st.session_state.chat_messages = []
    st.rerun()

st.sidebar.markdown("### Danh sach tai lieu")
try:
    documents = fetch_documents()
    if not documents:
        st.sidebar.info("Chua co tai lieu.")
    for doc in documents:
        col_a, col_b = st.sidebar.columns([4, 1])
        with col_a:
            status = doc.get("status", "UNKNOWN")
            badge = ":green[INDEXED]" if status == "INDEXED" else ":orange[UPLOADED]" if status == "UPLOADED" else ":red[FAILED]"
            st.markdown(f"**{doc.get('filename', 'Unknown')}**  \n{badge}")
        with col_b:
            if st.button("Xoa", key=f"delete_{doc.get('id')}"):
                try:
                    doc_id = doc.get("id")
                    if doc_id:
                        delete_document(doc_id)
                    st.rerun()
                except requests.RequestException as exc:
                    st.sidebar.error(f"Khong the xoa: {exc}")
except requests.RequestException as exc:
    st.sidebar.error(f"Khong tai duoc danh sach: {exc}")


tab_chat, tab_history = st.tabs(["Chat", "Lich su cu"])

with tab_chat:
    st.markdown('<p class="gemini-page-title">Ho tro cong viec va tai lieu</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="gemini-page-sub">RAG + Gemini — tra loi dua tren file ban da index. Chat ben duoi.</p>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="gemini-chat-scroll">', unsafe_allow_html=True)
    for i, msg in enumerate(st.session_state.chat_messages):
        render_message_gemi_style(i, msg)
    if not st.session_state.chat_messages:
        render_welcome_assistant()
    st.markdown("</div>", unsafe_allow_html=True)

    chat_prompt = st.chat_input("Hoi RAG (Gemini + tai lieu)...", key="rag_chat_input")
    to_send = (chat_prompt or "").strip()

    if to_send:
        st.session_state.chat_messages.append({"role": "user", "content": to_send})
        try:
            with st.spinner("Gemini dang doc tai lieu va tra loi…"):
                result = ask_question(to_send, int(top_k))
            st.session_state.chat_messages.append(
                {
                    "role": "assistant",
                    "content": result.get("answer", "") or "_Khong co noi dung tra loi._",
                    "sources": result.get("sources", []),
                    "timestamp": result.get("timestamp"),
                }
            )
        except requests.HTTPError as exc:
            detail = ""
            if exc.response is not None:
                try:
                    detail = exc.response.json().get("detail", "")
                except Exception:
                    detail = exc.response.text or str(exc)
            st.session_state.chat_messages.append(
                {"role": "assistant", "content": f"**Loi he thong**\n\n{detail or exc}", "sources": []}
            )
        except requests.RequestException as exc:
            st.session_state.chat_messages.append(
                {
                    "role": "assistant",
                    "content": f"**Khong ket noi backend** `{API_BASE}`\n\n{exc}",
                    "sources": [],
                }
            )
        st.rerun()

    st.markdown(
        '<p class="gemini-footer-note">Gemini la AI va co the mac sai. Kiem tra lai voi tai lieu goc va nguon tham chieu.</p>',
        unsafe_allow_html=True,
    )

with tab_history:
    st.markdown("### Lich su hoi dap (server)")
    limit = st.slider("So ban ghi", min_value=10, max_value=200, value=50, step=10)
    if st.button("Tai lai"):
        st.rerun()
    try:
        history_items = fetch_history(limit=limit)
        if not history_items:
            st.info("Chua co lich su.")
        for item in history_items:
            ts = item.get("timestamp", "")
            question_text = item.get("question", "")
            answer_text = item.get("answer", "")
            answer_short = (answer_text[:120] + "...") if len(answer_text) > 120 else answer_text
            with st.expander(f"{ts} | {question_text} | {answer_short}", expanded=False):
                left, right = st.columns([1, 2])
                with left:
                    st.markdown("**Thoi gian**")
                    st.write(ts)
                    st.markdown("**Cau hoi**")
                    st.write(question_text)
                with right:
                    st.markdown("**Tra loi day du**")
                    st.write(answer_text)
                    st.markdown("**Nguon (chunk day du)**")
                    for source in item.get("sources", []):
                        st.caption(
                            f"{source.get('filename', '')} | trang {source.get('page_number')} | "
                            f"{source.get('similarity_score', 0):.4f}"
                        )
                        st.text(source.get("chunk_text", "") or "")
    except requests.RequestException as exc:
        st.error(f"Khong tai duoc lich su: {exc}")

st.caption(f"He thong: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
