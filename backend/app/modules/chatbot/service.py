import json
from collections.abc import Generator

from app.agents.database import DatabaseAgent
from app.agents.planner import PlannerAgent
from app.core.llm import create_llm
from app.core.redis import get_redis
from app.modules.chatbot.repository import ChatRepository
from app.modules.chatbot.schemas import ChatRequest, ChatResponse, QueryRequest, QueryResponse


def _create_llm():
    return create_llm()


def _create_database_agent() -> DatabaseAgent:
    return DatabaseAgent(llm=_create_llm())


def _create_planner() -> PlannerAgent:
    llm = _create_llm()
    database_agent = DatabaseAgent(llm=llm)
    return PlannerAgent(llm=llm, database_agent=database_agent)


def _build_history(request: ChatRequest) -> list[dict]:
    return [{"role": m.role, "content": m.content} for m in request.history]


def chat(request: ChatRequest) -> ChatResponse:
    planner = _create_planner()
    history = _build_history(request)
    result = planner.execute(request.message, history=history)

    return ChatResponse(
        status="success",
        response=result.output,
        usage=result.metadata,
    )


def chat_stream(request: ChatRequest) -> Generator[str, None, None]:
    planner = _create_planner()
    history = _build_history(request)

    for event in planner.execute_stream(request.message, history=history):
        yield f"data: {json.dumps(event)}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


def query(request: QueryRequest) -> QueryResponse:
    agent = _create_database_agent()
    result = agent.execute(request.question)

    return QueryResponse(
        status="success",
        response=result.output,
        sql=result.metadata.get("sql", ""),
        row_count=result.metadata.get("row_count", 0),
    )


def query_stream(request: QueryRequest) -> Generator[str, None, None]:
    from app.agents.planner.agent import _parse_think_tags
    from app.agents.planner.prompts import SYNTHESIS_SYSTEM, SYNTHESIS_USER

    llm = _create_llm()
    agent = DatabaseAgent(llm=llm)

    # Stream step-by-step thinking from DatabaseAgent
    db_result = None
    for event in agent.execute_stream(request.question):
        if event.get("type") == "_result":
            db_result = event["data"]
        else:
            yield f"data: {json.dumps(event)}\n\n"

    if db_result is None:
        yield f"data: {json.dumps({'type': 'content', 'content': 'Error: Database agent returned no result.'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    # Stream synthesis
    messages = [
        {"role": "system", "content": SYNTHESIS_SYSTEM},
        {"role": "user", "content": SYNTHESIS_USER.format(
            question=request.question,
            results=db_result.output,
        )},
    ]
    chunks = llm.generate_stream(messages=messages)
    for event in _parse_think_tags(chunks):
        yield f"data: {json.dumps(event)}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ── Conversation services ──

def _get_repository() -> ChatRepository:
    return ChatRepository(get_redis())


def create_conversation(user_id: str, title: str = "New Chat") -> dict:
    return _get_repository().create_conversation(user_id, title)


def list_conversations(user_id: str) -> list[dict]:
    return _get_repository().list_conversations(user_id)


def get_conversation(conversation_id: str) -> dict | None:
    return _get_repository().get_conversation(conversation_id)


def delete_conversation(user_id: str, conversation_id: str) -> bool:
    return _get_repository().delete_conversation(user_id, conversation_id)


def update_conversation_title(conversation_id: str, title: str) -> bool:
    return _get_repository().update_conversation_title(conversation_id, title)


def save_messages(
    conversation_id: str,
    user_message: str,
    assistant_content: str,
    assistant_thinking: str | None = None,
) -> bool:
    return _get_repository().save_messages(
        conversation_id, user_message, assistant_content, assistant_thinking
    )
