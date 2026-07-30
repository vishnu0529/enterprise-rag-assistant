from sqlmodel import Session, select

from app.models.schemas import ChatMessage, ChatSession


def get_or_create_session(session: Session, session_id: str) -> ChatSession:
    existing = session.get(ChatSession, session_id)
    if existing:
        return existing
    new_session = ChatSession(id=session_id)
    session.add(new_session)
    session.commit()
    session.refresh(new_session)
    return new_session


def get_history(session: Session, session_id: str, limit: int = 10) -> list[dict]:
    statement = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = session.exec(statement).all()
    recent = messages[-limit:]
    return [{"role": m.role, "content": m.content} for m in recent]


def add_message(session: Session, session_id: str, role: str, content: str) -> None:
    message = ChatMessage(session_id=session_id, role=role, content=content)
    session.add(message)
    session.commit()
