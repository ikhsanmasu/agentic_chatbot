import json
from collections.abc import Generator

from app.agents.planner import create_planner_agent
from app.modules.chatbot.repository import ChatRepository
from app.modules.chatbot.schemas import ChatRequest, ChatResponse


def _build_history(request: ChatRequest) -> list[dict]:
    return [{"role": m.role, "content": m.content} for m in request.history]


def chat(request: ChatRequest) -> ChatResponse:
    planner = create_planner_agent()
    history = _build_history(request)
    result = planner.execute(request.message, history=history)

    return ChatResponse(
        status="success",
        response=result.output,
        usage=result.metadata,
    )


def chat_stream(request: ChatRequest) -> Generator[str, None, None]:
    planner = create_planner_agent()
    history = _build_history(request)

    for event in planner.execute_stream(request.message, history=history):
        yield f"data: {json.dumps(event)}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# Conversation services.
def create_conversation(user_id: str, title: str = "New Chat") -> dict:
    return ChatRepository().create_conversation(user_id, title)


def list_conversations(user_id: str) -> list[dict]:
    return ChatRepository().list_conversations(user_id)


def get_conversation(user_id: str, conversation_id: str) -> dict | None:
    return ChatRepository().get_conversation(user_id, conversation_id)


def delete_conversation(user_id: str, conversation_id: str) -> bool:
    return ChatRepository().delete_conversation(user_id, conversation_id)


def update_conversation_title(user_id: str, conversation_id: str, title: str) -> bool:
    return ChatRepository().update_conversation_title(user_id, conversation_id, title)


def save_messages(
    user_id: str,
    conversation_id: str,
    user_message: str,
    assistant_content: str,
    assistant_thinking: str | None = None,
) -> bool:
    return ChatRepository().save_messages(
        user_id,
        conversation_id,
        user_message,
        assistant_content,
        assistant_thinking,
    )


def list_history(
    user_id: str,
    conversation_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    return ChatRepository().list_history(
        user_id=user_id,
        conversation_id=conversation_id,
        limit=limit,
    )


def clear_history(user_id: str, conversation_id: str | None = None) -> int:
    return ChatRepository().clear_history(
        user_id=user_id,
        conversation_id=conversation_id,
    )
