import uuid

import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="Enterprise Knowledge Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
*, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.header-dark { background: #0f172a; border-radius: 14px; padding: 1.75rem 2rem; margin-bottom: 1.25rem; border: 1px solid rgba(255,255,255,0.06); }
.header-dark h1 { color: #f8fafc; font-size: 1.6rem; font-weight: 600; margin: 0 0 4px; letter-spacing: -0.3px; }
.header-dark p { color: #94a3b8; font-size: 0.85rem; margin: 0; }
.hbadge { display: inline-block; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: 500; margin-right: 5px; font-family: 'JetBrains Mono', monospace; }
.hb-blue { background: #1e3a5f; color: #93c5fd; border: 1px solid #1d4ed8; }
.hb-green { background: #052e16; color: #86efac; border: 1px solid #166534; }
.hb-purple { background: #2e1065; color: #d8b4fe; border: 1px solid #7e22ce; }
.chat-u { background: #1e3a5f; color: #e0f2fe; padding: 10px 14px; border-radius: 10px; margin: 6px 0 6px 2rem; font-size: 0.9rem; line-height: 1.5; }
.chat-a { background: #f8fafc; color: #1e293b; padding: 10px 14px; border-radius: 10px; margin: 6px 2rem 6px 0; font-size: 0.9rem; line-height: 1.5; border: 1px solid #e2e8f0; }
.citation { background: #fafafa; border-left: 2px solid #6366f1; border-radius: 0 8px 8px 0; padding: 8px 12px; margin-bottom: 6px; font-size: 0.8rem; color: #334155; }
.citation-meta { font-size: 0.72rem; color: #6366f1; font-weight: 600; font-family: 'JetBrains Mono', monospace; margin-bottom: 3px; }
</style>
""",
    unsafe_allow_html=True,
)

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_id" not in st.session_state:
    st.session_state.user_id = ""

with st.sidebar:
    st.markdown("### Settings")
    api_base = st.text_input("API base URL", value=API_BASE)
    st.divider()
    st.markdown("### Documents")
    try:
        docs = requests.get(f"{api_base}/documents", timeout=5).json()
    except requests.RequestException:
        docs = None

    if docs is None:
        st.error(f"Can't reach API at {api_base}. Is it running?")
    elif not docs:
        st.caption("No documents ingested yet.")
    else:
        for d in docs:
            st.markdown(f"**{d['filename']}** — {d['num_chunks']} chunks")

    uploaded = st.file_uploader("Upload a document", type=["pdf", "md", "txt"])
    if uploaded and st.button("Ingest document", use_container_width=True):
        with st.spinner("Ingesting..."):
            resp = requests.post(
                f"{api_base}/documents",
                files={"file": (uploaded.name, uploaded.getvalue())},
                timeout=120,
            )
        if resp.ok:
            st.success(f"Ingested {uploaded.name} ({resp.json()['num_chunks']} chunks)")
            st.rerun()
        else:
            st.error(resp.text)

    st.divider()
    st.markdown("### Memory")
    st.session_state.user_id = st.text_input(
        "User ID (optional)",
        value=st.session_state.user_id,
        help="Set this to recall relevant exchanges from your earlier sessions, "
        "even after starting a new session below. Leave blank for no cross-session memory.",
    )

    st.divider()
    if st.button("New session", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()  # user_id is intentionally NOT reset — that's what makes memory cross-session

    st.divider()
    st.markdown("[GitHub](https://github.com/vishnu0529/enterprise-rag-assistant) · v0.1")

st.markdown(
    """
<div class="header-dark">
<h1>📚 Enterprise Knowledge Assistant</h1>
<p>Production-style RAG: ingestion, cited chat, and rigorous evaluation</p>
<div style="margin-top:10px;">
<span class="hbadge hb-blue">Qdrant</span>
<span class="hbadge hb-green">FastAPI</span>
<span class="hbadge hb-purple">Cited answers</span>
</div>
</div>
""",
    unsafe_allow_html=True,
)

for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f'<div class="chat-u">{msg["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-a">{msg["content"]}</div>', unsafe_allow_html=True)
        if msg.get("citations"):
            with st.expander(f"📎 {len(msg['citations'])} source(s)"):
                for c in msg["citations"]:
                    loc = f"p.{c['page']}" if c.get("page") else f"chunk {c['chunk_index']}"
                    st.markdown(
                        f'<div class="citation"><div class="citation-meta">'
                        f"{c['filename']} ({loc}) · score {c['score']:.2f}</div>"
                        f"{c['text']}</div>",
                        unsafe_allow_html=True,
                    )
        if msg.get("latency_ms") is not None:
            st.caption(
                f"⏱ {msg['latency_ms']:.0f}ms · "
                f"{msg['prompt_tokens']}+{msg['completion_tokens']} tokens"
            )
        if msg.get("faithfulness_score") is not None:
            extras = [f"🧭 faithfulness {msg['faithfulness_score']:.2f}"]
            if msg.get("retries"):
                extras.append(f"🔁 {msg['retries']} reformulation(s)")
            if msg.get("used_memory"):
                extras.append("🧠 recalled a past session")
            st.caption(" · ".join(extras))

question = st.chat_input("Ask a question about your documents...")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    try:
        resp = requests.post(
            f"{api_base}/chat",
            json={
                "question": question,
                "session_id": st.session_state.session_id,
                "user_id": st.session_state.user_id or None,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": data["answer"],
                "citations": data["citations"],
                "latency_ms": data["latency_ms"],
                "prompt_tokens": data["prompt_tokens"],
                "completion_tokens": data["completion_tokens"],
                "faithfulness_score": data.get("faithfulness_score"),
                "retries": data.get("retries", 0),
                "used_memory": data.get("used_memory", False),
            }
        )
    except requests.RequestException as exc:
        st.session_state.messages.append(
            {"role": "assistant", "content": f"Error contacting API: {exc}"}
        )
    st.rerun()
