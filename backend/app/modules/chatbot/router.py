from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.modules.chatbot.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationSummary,
    CreateConversationRequest,
    QueryRequest,
    QueryResponse,
    SaveMessagesRequest,
    UpdateConversationTitleRequest,
)
from app.modules.chatbot.service import (
    chat,
    chat_stream,
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
    query,
    query_stream,
    save_messages,
    update_conversation_title,
)

router = APIRouter(tags=["Chatbot"], prefix="/v1/chatbot")


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    return chat(request=request)


@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    return StreamingResponse(
        chat_stream(request),
        media_type="text/event-stream",
    )

@router.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    return query(request=request)


@router.post("/query/stream")
async def query_stream_endpoint(request: QueryRequest):
    return StreamingResponse(
        query_stream(request),
        media_type="text/event-stream",
    )


# ── Conversation endpoints ──

@router.get("/conversations/{user_id}", response_model=list[ConversationSummary])
async def list_conversations_endpoint(user_id: str):
    return list_conversations(user_id)


@router.post("/conversations/{user_id}", response_model=ConversationSummary)
async def create_conversation_endpoint(user_id: str, request: CreateConversationRequest):
    return create_conversation(user_id, request.title)


@router.get("/conversations/{user_id}/{conversation_id}", response_model=ConversationDetail)
async def get_conversation_endpoint(user_id: str, conversation_id: str):
    conv = get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.delete("/conversations/{user_id}/{conversation_id}")
async def delete_conversation_endpoint(user_id: str, conversation_id: str):
    deleted = delete_conversation(user_id, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}


@router.patch("/conversations/{user_id}/{conversation_id}/title")
async def update_title_endpoint(
    user_id: str, conversation_id: str, request: UpdateConversationTitleRequest
):
    updated = update_conversation_title(conversation_id, request.title)
    if not updated:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "updated"}


@router.post("/conversations/{user_id}/{conversation_id}/messages")
async def save_messages_endpoint(
    user_id: str, conversation_id: str, request: SaveMessagesRequest
):
    saved = save_messages(
        conversation_id,
        request.user_message,
        request.assistant_content,
        request.assistant_thinking,
    )
    if not saved:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "saved"}
