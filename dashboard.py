import uuid

import requests
import streamlit as st

API_BASE = "https://enterprise-rag-assistant-53ke.onrender.com"

# Read from Streamlit Cloud's Secrets, which are server-side only. This
# request happens from Streamlit's Python backend to the FastAPI backend,
# never from the visitor's browser, so the key is never exposed to whoever
# is viewing the public dashboard, only whoever has the actual secret.
try:
    _API_KEY = st.secrets.get("API_KEY", "")
except Exception:
    _API_KEY = ""  # no secrets.toml at all (e.g. local dev without one), fine, gate is a no-op


def _auth_headers() -> dict:
    return {"X-API-Key": _API_KEY} if _API_KEY else {}


st.set_page_config(
    page_title="Proposal Response Assistant",
    page_icon=":material/description:",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_id" not in st.session_state:
    st.session_state.user_id = ""

with st.sidebar:
    st.subheader("Settings", anchor=False)
    api_base = st.text_input("API base URL", value=API_BASE)

    st.subheader("Documents", anchor=False)
    docs = None
    docs_error = None
    try:
        # Render's free tier spins the backend down after inactivity and
        # cold-starts in ~30-60s on the next request, so a short timeout here
        # would misreport a cold start as "API unreachable".
        resp = requests.get(f"{api_base}/documents", headers=_auth_headers(), timeout=70)
        if resp.ok:
            docs = resp.json()
        else:
            docs_error = resp.text
    except requests.RequestException:
        pass

    if docs is None:
        st.error(
            docs_error
            or f"Can't reach API at {api_base}. If it's hosted on Render's free tier, it may be cold-starting, try again in ~30s.",
            icon=":material/error:",
        )
    elif not docs:
        st.caption("No documents ingested yet.")
    else:
        st.dataframe(
            [
                {
                    "Filename": d["filename"],
                    "Chunks": d["num_chunks"],
                    "Uploaded": d["uploaded_at"][:10],
                }
                for d in docs
            ],
            hide_index=True,
            width="stretch",
        )

    uploaded = st.file_uploader("Upload a document", type=["pdf", "md", "txt"])
    if uploaded and st.button("Ingest document", icon=":material/upload:", width="stretch"):
        with st.spinner("Ingesting..."):
            resp = requests.post(
                f"{api_base}/documents",
                files={"file": (uploaded.name, uploaded.getvalue())},
                headers=_auth_headers(),
                timeout=120,
            )
        if resp.ok:
            st.success(f"Ingested {uploaded.name} ({resp.json()['num_chunks']} chunks)")
            st.rerun()
        else:
            st.error(resp.text)

    st.subheader("Memory", anchor=False)
    st.session_state.user_id = st.text_input(
        "User ID (optional)",
        value=st.session_state.user_id,
        help="Set this to recall relevant exchanges from your earlier sessions, "
        "even after starting a new session below. Leave blank for no cross-session memory.",
    )

    if st.button("New session", icon=":material/add_circle:", width="stretch"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()  # user_id is intentionally NOT reset; that's what makes memory cross-session

    st.caption("[GitHub](https://github.com/vishnu0529/enterprise-rag-assistant) · v0.1")

st.title(":material/description: Proposal Response Assistant")
st.caption(
    "Bid-team RAG: drafts answers from your own proposals, credentials and rate card, "
    "every claim cited"
)
with st.container(horizontal=True):
    st.badge("Qdrant", icon=":material/database:", color="blue")
    st.badge("FastAPI", icon=":material/bolt:", color="green")
    st.badge("Cited answers", icon=":material/link:", color="violet")

st.info(
    "The backend runs on Render's free tier, which sleeps after ~15 minutes of "
    "inactivity. If your first request fails or times out, that's expected. "
    "Wait ~30-60s for it to wake up, then try again.",
    icon=":material/schedule:",
)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sub_queries"):
            queries = ", ".join(f"“{q}”" for q in msg["sub_queries"])
            n = len(msg["sub_queries"])
            with st.expander(
                f"Retrieval Strategist's plan: {n} quer{'y' if n == 1 else 'ies'}",
                icon=":material/route:",
            ):
                st.markdown(f"**Searched for:** {queries}")
                if msg.get("strategist_reasoning"):
                    st.caption(msg["strategist_reasoning"])
        if msg.get("citations"):
            with st.expander(f"{len(msg['citations'])} source(s)", icon=":material/link:"):
                for c in msg["citations"]:
                    loc = f"p.{c['page']}" if c.get("page") else f"chunk {c['chunk_index']}"
                    with st.container(border=True):
                        st.caption(f"{c['filename']} ({loc}) · score {c['score']:.2f}")
                        st.text(c["text"])
        if msg.get("latency_ms") is not None:
            st.caption(
                f":material/timer: {msg['latency_ms']:.0f}ms · "
                f"{msg['prompt_tokens']}+{msg['completion_tokens']} tokens"
            )
        if msg.get("faithfulness_score") is not None:
            extras = [f":material/check_circle: faithfulness {msg['faithfulness_score']:.2f}"]
            if msg.get("retries"):
                extras.append(f":material/refresh: Strategist re-planned {msg['retries']}x")
            if msg.get("used_memory"):
                extras.append(":material/psychology: recalled a past session")
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
            # Generous: a cold Render start (~30-60s) can stack with up to 3
            # strategize/draft/critique rounds if the corrective loop retries.
            headers=_auth_headers(),
            timeout=120,
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
                "sub_queries": data.get("sub_queries", []),
                "strategist_reasoning": data.get("strategist_reasoning", ""),
            }
        )
    except requests.RequestException as exc:
        cold_start_status = (
            isinstance(exc, requests.exceptions.HTTPError)
            and exc.response is not None
            and exc.response.status_code in (502, 503, 504)
        )
        is_cold_start = (
            isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError))
            or cold_start_status
        )
        if is_cold_start:
            content = (
                "The backend looks like it's still waking up from Render's free-tier "
                "sleep. Wait ~30-60s and try again."
            )
        else:
            content = f"Error contacting API: {exc}"
        st.session_state.messages.append({"role": "assistant", "content": content})
    st.rerun()
