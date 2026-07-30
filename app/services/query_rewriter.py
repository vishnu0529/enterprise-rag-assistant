"""Rewrites a user's raw question into a standalone search query, resolving
references to prior conversation turns (e.g. "what about the second one?",
"and the parental leave policy?") before it's used for retrieval. Falls
back to the original question on any LLM failure, matching the defensive
pattern used throughout app/services/evaluation.py.
"""

from app.services.llm_client import call_llm

SYSTEM_PROMPT = (
    "You rewrite a user's question into a standalone search query suitable "
    "for document retrieval, resolving any pronouns or implicit references "
    "using the conversation history. If the question is already standalone, "
    "return it unchanged. Respond with ONLY the rewritten query — no "
    "preamble, no quotes, no explanation."
)


def rewrite_query(question: str, history: list[dict] | None = None) -> str:
    if not history:
        # Nothing to resolve without prior turns — skip the LLM call
        # entirely rather than spend quota on a no-op.
        return question

    history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history)
    user_prompt = f"Conversation so far:\n{history_text}\n\nQuestion: {question}"
    try:
        result = call_llm(SYSTEM_PROMPT, user_prompt)
        rewritten = result.text.strip().strip('"')
        return rewritten if rewritten else question
    except Exception:
        return question
