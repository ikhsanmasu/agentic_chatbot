from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.modules.chatbot.schemas import ChatRequest, ChatResponse
from app.modules.chatbot.service import chat, chat_stream

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
